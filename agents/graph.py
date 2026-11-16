"""Multiagentný systém LiekRadar (LangGraph + Gemini).

Graf kopíruje cyklus competitive intelligence:

    orchestrátor (plánovanie, LLM) -> zber (bez LLM) -> analytik (analýza, LLM)
        -> reportér (šírenie, LLM) -> kritik (kontrola v kóde + LLM)
                                        ├─ neschválené -> reportér (najviac 1 oprava)
                                        ├─ po oprave zostali len cudzie znaky -> korektúra (LLM, len slová)
                                        └─ schválené a jazyk odpovede nie je sk -> preklad (LLM + kontrola zhody)

Orchestrátor najprv overí rozsah otázky: otázka pacienta (vzory v kóde v agents/rozsah.py alebo rozhodnutie
orchestrátora) graf hneď ukončí s pevným textom bez nástrojov a bez ďalších volaní modelu.

Systémový prompt každého agenta = vault/AGENTS.md + krátky popis jeho roly.
Čísla počítajú len nástroje z agents.tools (obaly nad pipeline.analytika), nie model.
Na jednu otázku najviac 8 volaní modelu: orchestrátor, analytik, reportér, kritik,
pri oprave ešte reportér a kritik, prípadne jazyková korektúra a nakoniec preklad (cs / en).

Použitie:
    from agents.graph import spusti
    vysledok = spusti("Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?", "lekaren")
"""

from __future__ import annotations

import csv
import os
import datetime as dt
import json
import operator
import re
import time
import unicodedata
from pathlib import Path
from typing import Annotated, Callable, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agents import korektura as kor
from agents import preklad as prekl
from agents import tools
from agents.rozsah import (JAZYKY, jazyk_textu, je_pacientska_otazka, odpoved_pre_pacienta, pacientsky_vzor,
                           urci_jazyk)
from agents.kontrola_cisel import kontrola_cisel
from agents.llm import LLM, MAX_VOLANI_NA_OTAZKU, LLMChyba

KOREN = Path(__file__).resolve().parent.parent
VAULT = KOREN / "vault"
AGENTS_MD = VAULT / "AGENTS.md"
MANIFEST = VAULT / "manifest_zdrojov.csv"

MAX_VOLANI_NASTROJOV = 6        # v pláne orchestrátora
MAX_VOLANI_PO_DOPLNENI = 8      # po doplnení zástupcu "z_top_rizikove"
MAX_OPRAV = 1
ZASTUPCA = "z_top_rizikove"     # hodnota argumentu, ktorú zber doplní z výsledku top_rizikove
ZASTUPCA_POCET = 2              # koľko najrizikovejších liekov sa takto doplní

PERSONY = {
    "vyrobca": "výrobca generík / distribútor – hľadá príležitosti, konkurentov a trhové medzery (doplnkovo "
               "riziko výpadku a časový posun ČR–SR)",
    "lekaren": "nákupca lekárenskej siete – sleduje riziká výpadkov, náhrady a potrebu predzásobenia (doplnkovo "
               "časový posun ČR–SR)",
}

KIQ_POPIS = {
    "KIQ1": "riziko výpadku – ktoré lieky bez nahláseného výpadku majú najvyššie skóre rizika",
    "KIQ2": "časový posun – či výpadok v jednej krajine predchádza výpadku v druhej",
    "KIQ3": "náhrady – čím nahradiť liek vo výpadku v tej istej krajine",
    "KIQ4": "konkurenti – výrobcovia v skupine ATC, ich výpadky a podiel na dodávkach",
    "KIQ5": "trhové medzery – látky s dlhým výpadkom a málo dodávateľmi",
}

# Ako sa KIQ volajú v texte pre zákazníka (označenia KIQ1–KIQ5 sú len v priebehu a v Case Logu)
KIQ_TEMA = {"KIQ1": "riziko výpadku", "KIQ2": "časový posun ČR–SR", "KIQ3": "náhrady", "KIQ4": "konkurenti",
            "KIQ5": "trhové medzery"}

# Krajina zdroja: fakt o SR necituje české zdroje a naopak
KRAJINA_ZDROJA = {"E001": "CZ", "E002": "CZ", "E003": "CZ", "E004": "SK", "E005": "SK"}

PHIA = ["zanedbateľná pravdepodobnosť", "veľmi nepravdepodobné", "nepravdepodobné", "reálna možnosť",
        "pravdepodobné", "veľmi pravdepodobné", "takmer isté"]
# výrazy PHIA v ľubovoľnom páde a rode („reálnu možnosť“, „pravdepodobný“, „takmer istý“)
PHIA_VZOR = re.compile(r"zanedbateľn\w*\s+pravdepodobnos\w*|(?:veľmi\s+)?(?:ne)?pravdepodobn\w*|"
                       r"reáln\w*\s+možnos\w*|takmer\s+ist\w*", re.IGNORECASE)

SEKCIE_BLUF = [  # (kľúčové slovo v nadpise, názov sekcie v šablóne kurzu)
    ("bottom line", "Bottom line up front"),
    ("key judgement", "Key judgements"),
    ("discussion", "Discussion"),
    ("alternative explanation", "Alternative explanations"),
    ("key assumption", "Key assumptions and gaps"),
    ("indicators", "Indicators to watch"),
    ("sources and method", "Sources and method annex"),
    ("ai use", "AI use statement"),
]


# ---------------------------------------------------------------------------
# Stav grafu a štruktúrované výstupy
# ---------------------------------------------------------------------------

class Stav(TypedDict, total=False):
    otazka: str
    persona: str
    plan: dict                                       # plán orchestrátora (po kontrole v kóde)
    data: dict                                       # výsledky nástrojov: označenie volania -> záznam
    analyza: str                                     # zistenia analytika (Fact / Inference)
    brief: str                                       # správa BLUF od reportéra
    kritika: dict                                    # výsledok kritika
    pocet_oprav: int
    priebeh: Annotated[list[str], operator.add]      # kroky agentov pre aplikáciu
    case_log: Annotated[list[dict], operator.add]    # záznamy do Case Logu
    chyba: Optional[str]
    rozsah: str                                      # "ok" alebo "pacient" (otázka pacienta – bez nástrojov)
    jazyk_appky: Optional[str]                       # jazyk z appky (sk / cs / en)
    jazyk: str                                       # jazyk odpovede: jazyk otázky, inak jazyk appky
    brief_preklad: Optional[str]                     # schválená správa preložená do jazyka odpovede
    preklad: dict                                    # stav prekladu: ok / vratene_sk / neschvalene / vynechany


class Volanie(BaseModel):
    nastroj: Literal["top_rizikove", "detail_latky", "posun_latky", "nahrady", "nahrady_za_latku", "konkurenti",
                     "trhove_medzery"]
    krajina: Optional[Literal["CZ", "SK"]] = Field(None, description="CZ alebo SK")
    atc_prefix: Optional[str] = Field(None, description="začiatok ATC kódu, napr. J01 alebo J01C")
    atc: Optional[str] = Field(None, description=f"ATC7 látky, napr. J01CR02, alebo '{ZASTUPCA}'")
    kod: Optional[str] = Field(None, description=f"kód lieku SÚKL/ŠÚKL, alebo '{ZASTUPCA}'")
    n: Optional[int] = Field(None, description="počet riadkov, najviac 10")
    preco: str = Field("", description="jedna veta, prečo toto volanie")


class Plan(BaseModel):
    rozsah: Literal["ok", "pacient"] = Field("ok", description="pacient = pacient sa pýta na vlastný liek, jeho "
                                                                "náhradu, užívanie alebo dávkovanie; inak ok")
    jazyk: Optional[Literal["sk", "cs", "en"]] = Field(None, description="jazyk otázky: sk, cs alebo en")
    kiq: list[Literal["KIQ1", "KIQ2", "KIQ3", "KIQ4", "KIQ5"]]
    krajiny: list[Literal["CZ", "SK"]]
    atc_prefix: Optional[str] = Field(None, description="ATC prefix z otázky, napr. J01; inak null")
    zdovodnenie: str = Field(description="1–2 vety, prečo tieto KIQ a nástroje")
    volania: list[Volanie] = Field(description=f"najviac {MAX_VOLANI_NASTROJOV} volaní nástrojov")


class Posudok(BaseModel):
    schvalene: bool = Field(description="true, ak správa spĺňa pravidlá AGENTS.md")
    problemy: list[str] = Field(default_factory=list, description="konkrétne problémy, každý v jednej vete")


# ---------------------------------------------------------------------------
# Pomocné funkcie
# ---------------------------------------------------------------------------

def _teraz_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _riadok(text, dlzka: int = 220) -> str:
    """Text v jednom riadku pre Case Log."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= dlzka else text[: dlzka - 1] + "…"


def _zaznam(agent: str, nastroj: str, vstup, vysledok) -> dict:
    return {"cas_utc": _teraz_utc(), "agent": agent, "nastroj": nastroj,
            "vstup": _riadok(vstup), "vysledok": _riadok(vysledok)}


def _json(objekt) -> str:
    return json.dumps(objekt, ensure_ascii=False, separators=(",", ":"), default=str)


def nacitaj_manifest() -> dict:
    """ID zdroja -> {zdroj, admiralty, stiahnute_utc (najnovší súbor)}."""
    zdroje: dict = {}
    if not MANIFEST.exists():
        return zdroje
    with MANIFEST.open(encoding="utf-8") as subor:
        for r in csv.DictReader(subor):
            z = zdroje.setdefault(r["id"], {"zdroj": r["zdroj"], "admiralty": r["admiralty"], "stiahnute_utc": ""})
            z["stiahnute_utc"] = max(z["stiahnute_utc"], r.get("stiahnute_utc", ""))
    return zdroje


def _system(rola: str) -> str:
    pravidla = AGENTS_MD.read_text(encoding="utf-8")
    return f"{pravidla}\n\n---\n\n## Tvoja rola v LiekRadare\n{rola}\n\nDnešný dátum: {dt.date.today():%Y-%m-%d}."


def _normalizuj_personu(persona: str) -> str:
    p = unicodedata.normalize("NFKD", str(persona)).encode("ascii", "ignore").decode().lower().strip()
    if p.startswith("vyrob") or p.startswith("distrib"):
        return "vyrobca"
    if p.startswith("lekar"):
        return "lekaren"
    raise ValueError(f"Neznáma persona '{persona}'. Povolené: {', '.join(PERSONY)}.")


def kratky_nazov(otazka: str, max_slov: int = 6) -> str:
    """'Ktoré antibiotiká (J01) hrozí…' -> 'antibiotika-j01-chybat-slovensku'."""
    text = unicodedata.normalize("NFKD", otazka).encode("ascii", "ignore").decode().lower()
    stop = {"ktore", "ktory", "ktora", "ake", "aky", "aka", "ako", "hrozi", "budu", "bude", "maju", "ma", "su",
            "je", "na", "v", "vo", "a", "za", "pre", "do", "od", "ze", "sa", "si", "co", "kde", "kedy", "preco"}
    slova = [s for s in re.findall(r"[a-z0-9]+", text) if s not in stop]
    return "-".join(slova[:max_slov])[:60] or "otazka"


# ---------------------------------------------------------------------------
# Kontrola plánu (orchestrátor môže navrhnúť len povolené nástroje a argumenty)
# ---------------------------------------------------------------------------

_ATC_PREFIX = re.compile(r"^[A-Z](\d{2}([A-Z]([A-Z](\d{2})?)?)?)?$")
_ATC7 = re.compile(r"^[A-Z]\d{2}[A-Z]{2}\d{2}$")
_KOD = re.compile(r"^\d{1,7}$")


def over_plan(plan: Plan) -> tuple[list[dict], list[str]]:
    """Vráti zoznam platných volaní {'nastroj', 'argumenty'} a zoznam vyradených s dôvodom."""
    platne, vyradene, videne = [], [], set()
    predvolena_krajina = plan.krajiny[0] if plan.krajiny else None
    for v in plan.volania:
        if v.nastroj not in tools.NASTROJE:
            vyradene.append(f"{v.nastroj}: nástroj nie je v zozname")
            continue
        _, _, povinne, _ = tools.NASTROJE[v.nastroj]
        arg = {
            "krajina": v.krajina or predvolena_krajina,
            "atc_prefix": (v.atc_prefix or plan.atc_prefix or "").strip().upper() or None,
            "atc": (v.atc or "").strip() or None,
            "kod": (v.kod or "").strip() or None,
            "n": None if v.n is None else max(1, min(int(v.n), tools.MAX_RIADKOV)),
        }
        if arg["atc"] and arg["atc"] != ZASTUPCA:
            arg["atc"] = arg["atc"].upper()
        chyba = None
        for p in povinne:
            if not arg.get(p):
                chyba = f"chýba argument {p}"
        if arg["atc_prefix"] and not _ATC_PREFIX.match(arg["atc_prefix"]):
            chyba = f"neplatný ATC prefix {arg['atc_prefix']}"
        if "atc" in povinne and arg["atc"] and arg["atc"] != ZASTUPCA and not _ATC7.match(arg["atc"]):
            chyba = f"neplatný ATC7 {arg['atc']}"
        if "kod" in povinne and arg["kod"] and arg["kod"] != ZASTUPCA and not _KOD.match(arg["kod"]):
            chyba = f"neplatný kód lieku {arg['kod']}"
        if chyba:
            vyradene.append(f"{v.nastroj}: {chyba}")
            continue
        # len argumenty, ktoré daný nástroj prijíma
        import inspect
        prijima = inspect.signature(tools.NASTROJE[v.nastroj][0]).parameters
        arg = {k: h for k, h in arg.items() if k in prijima and h is not None}
        kluc = (v.nastroj, tuple(sorted(arg.items())))
        if kluc in videne:
            continue
        videne.add(kluc)
        platne.append({"nastroj": v.nastroj, "argumenty": arg, "preco": v.preco})
    if len(platne) > MAX_VOLANI_NASTROJOV:
        vyradene.append(f"nad limit {MAX_VOLANI_NASTROJOV} volaní: {len(platne) - MAX_VOLANI_NASTROJOV}")
        platne = platne[:MAX_VOLANI_NASTROJOV]
    return platne, vyradene


_OTAZKA_NAHRADY = re.compile(r"n[aá]hrad|nahradi|alternat[ií]v|z[aá]m[eě]n|zamieň|zamen|replac|substitut",
                             re.IGNORECASE)
# slovenské/české pomenovania, ktoré v číselníku ATC chýbajú (len pre základný plán bez modelu)
_SYNONYMA_LATOK = {"klavul": "inhibitor beta", "clavul": "inhibitor beta"}


def je_otazka_na_nahrady(otazka: str) -> bool:
    return bool(_OTAZKA_NAHRADY.search(otazka))


def _kmene(text: str) -> list[str]:
    bez = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [s[:6] for s in re.findall(r"[a-z]{5,}", bez)]


def atc_z_otazky(otazka: str) -> str | None:
    """ATC7 z otázky: priamo (J01CR02), inak podľa názvu látky v číselníku ATC (heuristika pre plán bez modelu)."""
    priamo = re.search(r"\b([A-Z]\d{2}[A-Z]{2}\d{2})\b", otazka)
    if priamo:
        return priamo.group(1)
    from pipeline import analytika
    kmene = set(_kmene(otazka))
    hladane = kmene | {_kmene(v)[0] for k, v in _SYNONYMA_LATOK.items() if k in kmene}
    najlepsie, skore = None, 0
    for atc, nazov in analytika._nazvy_atc().items():
        if len(atc) != 7:
            continue
        slova = set(_kmene(nazov))
        zhoda = len(slova & hladane)
        if zhoda > skore or (zhoda == skore and zhoda and najlepsie and len(slova) < len(set(_kmene(
                analytika.nazov_atc(najlepsie))))):
            najlepsie, skore = atc, zhoda
    return najlepsie if skore else None


def zabezpec_nahrady_za_latku(otazka: str, plan: Plan, volania: list[dict]) -> tuple[list[dict], list[str]]:
    """Ak sa otázka pýta na náhrady a plán pozná látku (ATC7), musí volať nahrady_za_latku.
    Náhrady so zástupcom z_top_rizikove bez volania top_rizikove by zber aj tak vynechal – vyradíme ich."""
    poznamky: list[str] = []
    if not je_otazka_na_nahrady(otazka):
        return volania, poznamky
    atc = next((v["argumenty"]["atc"] for v in volania if _ATC7.match(str(v["argumenty"].get("atc", "")))), None)
    if not atc and plan.atc_prefix and _ATC7.match(plan.atc_prefix):
        atc = plan.atc_prefix
    if not atc:
        return volania, poznamky
    ma_top = any(v["nastroj"] == "top_rizikove" for v in volania)
    nove = [v for v in volania if ma_top or ZASTUPCA not in v["argumenty"].values()]
    if len(nove) < len(volania):
        poznamky.append("vyradené volania so z_top_rizikove (top_rizikove nie je v pláne)")
    krajiny = plan.krajiny or ["SK", "CZ"]
    for krajina in reversed(krajiny):
        if not any(v["nastroj"] == "nahrady_za_latku" and v["argumenty"].get("krajina") == krajina for v in nove):
            nove.insert(0, {"nastroj": "nahrady_za_latku", "argumenty": {"krajina": krajina, "atc": atc, "n": 5},
                            "preco": "otázka na náhrady za látku (doplnené kódom)"})
            poznamky.append(f"doplnené nahrady_za_latku({krajina}, {atc})")
    return nove[:MAX_VOLANI_NASTROJOV], poznamky


def zakladny_plan(otazka: str, persona: str) -> Plan:
    """Plán bez modelu: z otázky vyberie ATC prefix a krajiny, nástroje podľa persony.
    Používa ho režim LIEKRADAR_FAKE_LLM a záloha, keď model navrhne len neplatné volania."""
    atc = re.search(r"\b([A-Z]\d{2}(?:[A-Z]{1,2}(?:\d{2})?)?)\b", otazka)
    atc_prefix = atc.group(1) if atc else None
    t = otazka.lower()
    krajiny = []
    if "česk" in t or "czech" in t or "čr" in re.findall(r"\b\w+\b", t) or re.search(r"\bCZ\b", otazka):
        krajiny.append("CZ")
    if "sloven" in t or "slovak" in t or re.search(r"\b(SR|SK)\b", otazka):
        krajiny.append("SK")
    krajiny = krajiny or ["CZ", "SK"]
    volania: list[Volanie] = []
    atc7 = atc_z_otazky(otazka) if je_otazka_na_nahrady(otazka) else None
    if atc7:
        kiq = ["KIQ3", "KIQ1"]
        volania += [Volanie(nastroj="nahrady_za_latku", krajina=k, atc=atc7, n=5,
                            preco="náhrady za látku z otázky (KIQ3)") for k in krajiny]
        volania.append(Volanie(nastroj="detail_latky", atc=atc7, preco="výpadky látky v ČR a SR (KIQ1)"))
        return Plan(jazyk=jazyk_textu(otazka), kiq=kiq, krajiny=krajiny, atc_prefix=atc7,
                    zdovodnenie=f"Základný plán – otázka na náhrady za {atc7}: KIQ3, KIQ1.", volania=volania)
    if persona == "lekaren":
        kiq = ["KIQ1", "KIQ2", "KIQ3"]
        volania += [Volanie(nastroj="top_rizikove", krajina=k, atc_prefix=atc_prefix, n=10,
                            preco="najrizikovejšie lieky (KIQ1)") for k in krajiny]
        volania.append(Volanie(nastroj="posun_latky", atc=ZASTUPCA, preco="posun CZ–SK pri najrizikovejších (KIQ2)"))
        volania.append(Volanie(nastroj="nahrady", krajina=krajiny[0], kod=ZASTUPCA,
                               preco="náhrady za najrizikovejšie lieky (KIQ3)"))
    else:
        kiq = ["KIQ5", "KIQ4", "KIQ1"]
        for k in krajiny:
            volania.append(Volanie(nastroj="trhove_medzery", krajina=k, n=10, preco="trhové medzery (KIQ5)"))
            volania.append(Volanie(nastroj="konkurenti", krajina=k, atc_prefix=atc_prefix or "J01",
                                   preco="konkurenti v skupine (KIQ4)"))
        volania.append(Volanie(nastroj="top_rizikove", krajina=krajiny[0], atc_prefix=atc_prefix, n=10,
                               preco="kde konkurentom hrozí výpadok (KIQ1)"))
    return Plan(jazyk=jazyk_textu(otazka), kiq=kiq, krajiny=krajiny, atc_prefix=atc_prefix,
                zdovodnenie=f"Základný plán pre personu {persona}: {', '.join(kiq)}.", volania=volania)


# ---------------------------------------------------------------------------
# Kontrola správy v kóde (kritik)
# ---------------------------------------------------------------------------

# Citácia je hranatá zátvorka s aspoň jedným ID zdroja: [E001, A2] alebo zlúčená [E001, A2, E005, A2].
# Odkazy na wiki [[J01XD01]] nie sú citácie (neobsahujú ID E/W).
_SKUPINA = re.compile(r"\[([^\[\]]*\b[EW]\d{3}\b[^\[\]]*)\]")
_PAR = re.compile(r"\b([EW]\d{3})\s*,\s*([A-F][1-6])\b")
_SKUPINA_PLNA = re.compile(r"^\s*[EW]\d{3}\s*,\s*[A-F][1-6]\s*(?:[,;]\s*[EW]\d{3}\s*,\s*[A-F][1-6]\s*)*$")
ZAKAZANE_SLOVA = re.compile(r"\b(preuk[aá]z\w*|dok[aá]z\w*|elimin\w*|isto)\b", re.IGNORECASE)
_SKRATKY = {"napr", "tzv", "resp", "atď", "č", "porov", "cca", "min", "max", "tj", "t.j", "st", "sv"}


def citacie(text: str) -> list[tuple[str, str]]:
    """Všetky dvojice (ID, Admiralty) z platných citácií v texte, aj zo zlúčeného tvaru."""
    return [p for s in _SKUPINA.findall(text) if _SKUPINA_PLNA.match(s) for p in _PAR.findall(s)]


def zle_citacie(text: str) -> list[str]:
    """Zátvorky s ID zdroja, ktoré nie sú v tvare [ID, Admiralty] (napr. [E004] alebo [E001, E005])."""
    return [f"[{s}]" for s in _SKUPINA.findall(text) if not _SKUPINA_PLNA.match(s)]


def _prve_vety(text: str, pocet: int = 2) -> str:
    """Prvých `pocet` viet prvého neprázdneho odseku. Bodka po iniciále (B. Braun), po skratke
    (napr.) alebo vnútri slova (s.r.o.) vetu nekončí."""
    odsek = next((o.strip() for o in re.split(r"\n\s*\n", text) if o.strip()), "")
    konce = 0
    for m in re.finditer(r"[.!?](?=\s+\S)", odsek):
        slovo = re.search(r"(\S+)$", odsek[: m.start()])
        slovo = re.sub(r"^[*_(\[]+", "", slovo.group(1)) if slovo else ""
        if len(slovo) <= 1 or "." in slovo or slovo.lower() in _SKRATKY:
            continue
        konce += 1
        if konce == pocet:
            return odsek[: m.end()]
    return odsek


_SLOVESO_NAHRAD = re.compile(r"\b(slúž\w*|dodáva\w*|ponúka\w*|k\s+dispozícii|možno\s+použiť|nahrad\w*\s+ho|"
                             r"odporúča\w*|sú|je)\b", re.IGNORECASE)


def _zoznam_nahrad(veta: str) -> str:
    """Časť vety, kde sú vymenované náhrady: za dvojbodkou, inak za slovesom („slúži …“, „dodávajú sa …“).
    Liek, za ktorý sa náhrada hľadá („náhrada za X“), je pred ním a nepočíta sa."""
    if ":" in veta:
        return veta.split(":", 1)[1]
    m = _SLOVESO_NAHRAD.search(veta, veta.lower().find("náhrad") + 1)
    if m:
        return veta[m.end():]
    slovo = re.search(r"náhrad\w*", veta, re.IGNORECASE)  # „… tieto náhrady MEDOCLAV, …“ bez slovesa za nimi
    zvysok = veta[slovo.end():] if slovo else ""
    return "" if re.match(r"\s*za\b", zvysok) else zvysok


def _vety(text: str) -> list[str]:
    """Rozdelí text na vety rovnako ako _prve_vety (bodka po iniciále alebo skratke vetu nekončí)."""
    vety, zaciatok = [], 0
    for m in re.finditer(r"[.!?](?=\s+\S)", text):
        slovo = re.search(r"(\S+)$", text[: m.start()])
        slovo = re.sub(r"^[*_(\[]+", "", slovo.group(1)) if slovo else ""
        if len(slovo) <= 1 or "." in slovo or slovo.lower() in _SKRATKY:
            continue
        vety.append(text[zaciatok: m.end()].strip())
        zaciatok = m.end()
    if text[zaciatok:].strip():
        vety.append(text[zaciatok:].strip())
    return vety


def _prva_veta(text: str) -> str:
    return _prve_vety(text, 1)
_ZACIATOK_USUDKU = re.compile(rf"odhadujeme\b|(?:je\s+)?(?:{PHIA_VZOR.pattern})", re.IGNORECASE)
_RIADOK_FAKT = re.compile(r"^\s*(?:[-*+]|\d+\.)?\s*[*_]*\s*(fakt|fact)\b", re.IGNORECASE)
_RIADOK_USUDOK = re.compile(r"^\s*(?:[-*+]|\d+\.)?\s*[*_]*\s*(úsudok|úsudek|inference)\b[*_:\s]*", re.IGNORECASE)
# V Discussion sú povolené len tieto označenia riadkov – appka ich prekladá podľa presného textu
POVOLENE_OZNACENIA = ("**Fakt:**", "**Úsudok:**", "**Upozornenie:**")
_OZNACENIE_TUCNE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(\*\*[^*\n]{1,40}?:\s*\*\*|\*\*[^*:\n]{1,40}?\*\*\s*:)")
_OZNACENIE_ZNAME = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+[*_]*\s*(fakt|fact|facts|fakta|úsudok|úsudek|usudok|inference|"
                              r"odhad|zjištění|zistenie|upozornenie|upozornění|varovanie|varování|warning|poznámka)"
                              r"\b\s*[*_]*\s*:", re.IGNORECASE)
_SPRAVNE_OZNACENIE = {"fakt": "**Fakt:**", "fact": "**Fakt:**", "facts": "**Fakt:**", "fakta": "**Fakt:**",
                      "zjištění": "**Fakt:**", "zistenie": "**Fakt:**", "úsudok": "**Úsudok:**",
                      "úsudek": "**Úsudok:**", "usudok": "**Úsudok:**", "inference": "**Úsudok:**",
                      "odhad": "**Úsudok:**", "upozornenie": "**Upozornenie:**", "upozornění": "**Upozornenie:**",
                      "varovanie": "**Upozornenie:**", "varování": "**Upozornenie:**", "warning": "**Upozornenie:**",
                      "poznámka": "**Upozornenie:**"}
_RIADOK_UPOZORNENIE = re.compile(r"^\s*(?:[-*+]|\d+\.)?\s*[*_]*\s*upozornenie\b", re.IGNORECASE)
_ODRAZKA = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")


def _sekcie(brief: str) -> dict[str, str]:
    """Nadpis (malými písmenami) -> text sekcie po ďalší nadpis rovnakej alebo vyššej úrovne ##."""
    sekcie, nadpis, riadky = {}, "", []
    for r in brief.splitlines():
        if re.match(r"^#{1,2}\s", r):
            sekcie[nadpis] = "\n".join(riadky)
            nadpis, riadky = r.lstrip("#").strip().lower(), []
        else:
            riadky.append(r)
    sekcie[nadpis] = "\n".join(riadky)
    return sekcie


_ISTOTA = re.compile(r"istot\w*[^.\n]{0,30}?\b(nízk|stredn|vysok)\w*|\b(nízk|stredn|vysok)\w*\s+istot\w*",
                     re.IGNORECASE)
_VYSOKA_ISTOTA = re.compile(r"istot\w*[^.\n;]{0,30}?\bvysok\w*|\bvysok\w*\s+istot\w*", re.IGNORECASE)
_NAD_STROP = re.compile(r"veľmi\s+pravdepodobn\w*|takmer\s+ist\w*", re.IGNORECASE)
_CUDZIE_ZNAKY = re.compile(r"[śćłńżąęőűŚĆŁŃŻĄĘŐŰ]")
_CUDZIE_SLOVO = re.compile(r"\w*[śćłńżąęőűŚĆŁŃŻĄĘŐŰ]\w*")
_NA_SLOVENSKE = {"ś": "s", "ł": "l", "ń": "ň", "ż": "ž", "ą": "a", "ę": "e", "ő": "ó", "ű": "ú",
                 "Ś": "S", "Ł": "L", "Ń": "Ň", "Ż": "Ž", "Ą": "A", "Ę": "E", "Ő": "Ó", "Ű": "Ú"}


def navrh_slovensky(slovo: str) -> str:
    """Návrh opravy slova s cudzími znakmi: „możność“ -> „možnosť“, „być“ -> „byť“ (len návrh)."""
    s = re.sub(r"ąc", "úc", slovo)              # prebiehające -> prebiehajúce (príčastie -úci/-úca/-úce)
    s = re.sub(r"ść", "sť", s)
    s = re.sub(r"ć\b", "ť", s)          # koncové ć zodpovedá slovenskému ť (możność, być)
    s = s.replace("ć", "č").replace("Ć", "Č")
    return "".join(_NA_SLOVENSKE.get(c, c) for c in s)


_SR_VZOR = re.compile(r"\b(?:SR|SK)\b|[Ss]lovensk\w*|ŠÚKL")
_CR_VZOR = re.compile(r"\b(?:ČR|CZ)\b|[Čč]esk\w*|\bSÚKL")
_KIQ = re.compile(r"\bKIQ\s*-?\s*\d*", re.IGNORECASE)
_BALENIE_NAHRADY = re.compile(r"\d+(?:[,.]\d+)?\s*x\s*\d+(?:[,.]\d+)?(?:\s*x\s*\d+(?:[,.]\d+)?)?\s*"
                              r"(?:ml|mg|g|cm|ks|l)\b", re.IGNORECASE)
_INA_FORMA = re.compile(r"\bin\w*\s+(?:liekov\w*\s+)?form\w*", re.IGNORECASE)


def _bez_medzier(text) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower().replace(",", ".")


def kandidati_nahrad(data: dict) -> list[dict]:
    """Kandidáti z nástroja nahrady a vzory, podľa ktorých ich nájdeme v správe aj bez kódu a balenia:
    kód, celý názov, prvé slovo názvu + sila (napr. „Efloran 400 mg“) a pri inej forme aj najkratší
    začiatok názvu, ktorý nemá žiadny liek rovnakej formy (napr. „GARAMYCIN“)."""
    vysledok = []
    for z in data.values():
        v = z.get("vysledok") or {}
        if z.get("nastroj") == "nahrady" and "povodny_liek" in v:
            povodne = [v["povodny_liek"]]
        elif z.get("nastroj") == "nahrady_za_latku" and isinstance(v.get("zaznamy"), list):
            povodne = v.get("vo_vypadku") or []
        else:
            continue
        zaznamy = v.get("zaznamy", []) + [dict(r, ine_balenie_toho_isteho=True)
                                          for r in v.get("ine_balenia_toho_isteho") or []]
        # nahrady_za_latku bez liekov vo výpadku: rovnaka_forma je None (nie je s čím porovnať) -> ako rovnaká
        zaznamy = [dict(r, rovnaka_forma=True) if r.get("rovnaka_forma") is None else r for r in zaznamy]
        nazvy_povodnych = [str(p.get("nazov") or "") for p in povodne]
        povodny = {"nazov": " / ".join(nazvy_povodnych) or "liek vo výpadku",
                   "forma": " / ".join(dict.fromkeys(str(p.get("forma") or "") for p in povodne)) or "–"}
        rovnake = [str(r.get("nazov") or "") for r in zaznamy if r.get("rovnaka_forma")] + nazvy_povodnych
        for r in zaznamy:
            nazov = str(r.get("nazov") or "").strip()
            slova = nazov.split()
            vzory = {_bez_medzier(nazov)}
            if slova and r.get("sila"):
                vzory.add(_bez_medzier(f"{slova[0]} {r['sila']}"))
            if not r.get("rovnaka_forma"):
                for i in range(1, min(len(slova), 3) + 1):
                    predpona = " ".join(slova[:i]).lower()
                    if not any(n.lower().startswith(predpona) for n in rovnake):
                        vzory.add(_bez_medzier(predpona))
                        break
                # vzor, ktorý sedí aj na liek rovnakej formy (Efloran tbl vs. Efloran inf), nerozlíši – vyradíme ho
                vzory = {v for v in vzory if not any(_bez_medzier(n).startswith(v) for n in rovnake)}
            vysledok.append({"kod": str(r["kod"]), "nazov": nazov, "sila": r.get("sila"), "forma": r.get("forma"),
                             "rovnaka_forma": bool(r.get("rovnaka_forma")),
                             "ine_balenie": bool(r.get("ine_balenie_toho_isteho")),
                             "skupina": (r.get("za_lieky") or [povodny["nazov"]])[0],
                             "je_povodny_nazov": _bez_medzier(nazov) in {_bez_medzier(n) for n in nazvy_povodnych},
                             "povodna_forma": povodny["forma"], "povodny": povodny["nazov"],
                             "povodny_popis": ", ".join(r.get("za_lieky") or [])
                             or f"{povodny['nazov']} ({povodny['forma']})",
                             "vzory": sorted(v for v in vzory if len(v) >= 4)})
    # Pri viacerých výsledkoch náhrad (napr. tablety aj injekcia, v ČR názvy bez sily – „MEDOCLAV“) môže byť ten
    # istý názov v jednom výsledku rovnakou formou a v druhom inou. Vzor názvu, ktorý sedí aj na liek rovnakej
    # formy z ktoréhokoľvek výsledku, nerozlíši – pri inej forme ostane len kód a jednoznačné vzory.
    def tvary(nazov, sila) -> set[str]:  # názov, názov + sila, prvé slovo + sila
        nazov, sila = str(nazov or "").strip(), str(sila or "").strip()
        vysl = {_bez_medzier(nazov)}
        if sila:
            vysl |= {_bez_medzier(f"{nazov} {sila}"), _bez_medzier(f"{(nazov.split() or [''])[0]} {sila}")}
        return vysl

    rovnake_vsetky: set[str] = set()
    for k in vysledok:
        if k["rovnaka_forma"]:
            rovnake_vsetky |= tvary(k["nazov"], k["sila"])
    for z in data.values():  # aj pôvodné lieky (vo výpadku) zo všetkých výsledkov – ich zmienka nie je náhrada
        v = z.get("vysledok") or {}
        for p in ([v["povodny_liek"]] if v.get("povodny_liek") else []) + list(v.get("vo_vypadku") or []):
            rovnake_vsetky |= tvary(p.get("nazov"), p.get("sila"))
    for k in vysledok:
        if not k["rovnaka_forma"]:
            k["vzory"] = [v for v in k["vzory"] if not any(n.startswith(v) for n in rovnake_vsetky)]
    return vysledok


def _spomina(riadok: str, kandidat: dict) -> bool:
    """Je kandidát v riadku spomenutý kódom, názvom alebo názvom so silou?"""
    if re.search(rf"(?<![\w]){re.escape(kandidat['kod'])}(?![\w])", riadok):
        return True
    norm = _bez_medzier(riadok)
    return any(v in norm for v in kandidat["vzory"])


def nahrady_inej_formy(data: dict) -> list[dict]:
    return [k for k in kandidati_nahrad(data) if not k["rovnaka_forma"]]


MAX_NAHRAD = 5
_POPIS_BALENIA = re.compile(r"\((?:fľ|fl|blis|strip|vre|amp|liek\.?\s*skl|vak|tuba|tub)\b", re.IGNORECASE)


def je_namietka_k_jazyku(problem: str, slova: list[str]) -> bool:
    """Námietka LLM kritika k jazyku / cudzím slovám, ktoré už našiel kód (rieši ich korektúra)."""
    p = problem.lower()
    return (any(s.lower() in p for s in slova) or bool(_CUDZIE_ZNAKY.search(problem))
            or bool(re.search(r"pravopis|jazyk|poľ|po česky|česk\w* tvar|preklep|cudz\w* (slov|znak)", p)))


def cudzie_slova(brief: str) -> list[tuple[str, str]]:
    """(slovo s cudzími znakmi, veta, v ktorej je) – každé slovo raz."""
    vysledok, videne = [], set()
    for riadok in brief.splitlines():
        for veta in _vety(riadok):
            for m in _CUDZIE_SLOVO.finditer(veta):
                if m.group(0) not in videne:
                    videne.add(m.group(0))
                    vysledok.append((m.group(0), veta))
    return vysledok


def je_namietka_ku_krajine_citacie(problem: str) -> bool:
    """Námietka LLM kritika ku krajine zdroja / zmiešaným citáciám (tú posudzuje len kód)."""
    p = problem.lower()
    o_citacii = re.search(r"citáci|zdroj|e00[1-5]", p)
    o_krajine = re.search(r"krajin|česk|slovensk|\bčr\b|\bsr\b|zmieša|e00[1-3].{0,40}e00[45]|e00[45].{0,40}e00[1-3]", p)
    return bool(o_citacii and o_krajine)


def kontrola_v_kode(brief: str, data: dict, manifest: dict) -> tuple[list[str], list[str]]:
    """Pravidlá z AGENTS.md (a z pokynov tímu), ktoré sa dajú overiť bez modelu.
    `data` sú výsledky nástrojov zo stavu grafu. Vracia (problémy, ktoré blokujú schválenie; upozornenia)."""
    problemy, upozornenia = [], []
    data_json = _json(data)
    kandidati = kandidati_nahrad(data)
    ine_formy = [k for k in kandidati if not k["rovnaka_forma"]]
    nizke = brief.lower()
    sekcie = _sekcie(brief)

    # 1. Štruktúra BLUF (sekcia 8 AGENTS.md)
    nadpisy = " | ".join(re.findall(r"^#{1,4}\s*(.+)$", brief, re.MULTILINE)).lower()
    for kluc, nazov in SEKCIE_BLUF:
        if kluc not in nadpisy:
            problemy.append(f"Chýba sekcia „{nazov}“ (formát BLUF, sekcia 8 AGENTS.md).")

    # 2. Citácie [ID, Admiralty] musia sedieť s manifestom (každá dvojica ID + známka, aj v zlúčenom tvare)
    for idz, znamka in sorted(set(citacie(brief))):
        if idz.startswith("W"):
            problemy.append(f"Citácia [{idz}, {znamka}]: zdroj z webu nie je v Case Logu tohto behu.")
        elif idz not in manifest:
            problemy.append(f"Citácia [{idz}, {znamka}]: ID nie je v manifeste zdrojov.")
        elif manifest[idz]["admiralty"] != znamka:
            problemy.append(f"Citácia [{idz}, {znamka}]: podľa manifestu má zdroj známku {manifest[idz]['admiralty']}.")
    for zla in sorted(set(zle_citacie(brief))):
        problemy.append(f"Citácia {zla} nie je v tvare [ID, Admiralty] (správne napr. [E001, A2] [E005, A2]).")

    # 3. Každý fakt má citáciu (kdekoľvek v riadku), každý úsudok začína „Odhadujeme…“ alebo výrazom PHIA
    for r in brief.splitlines():
        if _RIADOK_FAKT.match(r) and not citacie(r):
            problemy.append(f"Fakt bez citácie [ID, Admiralty]: „{_riadok(r, 120)}“")
        m = _RIADOK_USUDOK.match(r)
        if m:
            zvysok = r[m.end():].lstrip("*_: ").lower()
            if "upozorň" in zvysok or ("zámen" in zvysok and "lekár" in zvysok):
                problemy.append("Upozornenie, že zámenu môže urobiť len lekár, nie je úsudok – napíš ho ako "
                                f"samostatný riadok „- **Upozornenie:** …“: „{_riadok(r, 100)}“")
            elif not _ZACIATOK_USUDKU.match(zvysok):
                problemy.append("Úsudok nezačína „Odhadujeme…“ ani výrazom z mierky PHIA (napr. „Pravdepodobne…“, "
                                f"„Pravdepodobné je…“, „Reálna možnosť je…“): „{_riadok(r, 120)}“")

    # 4. Skóre rizika nie je pravdepodobnosť a nesmie byť v percentách
    for m in re.finditer(r"skór\w*[^.\n%]{0,40}?\d+(?:[,.]\d+)?\s?(%|percent)", nizke):
        problemy.append(f"Skóre rizika prepočítané na percentá: „{_riadok(m.group(0), 100)}“")
    for m in re.finditer(r"skór\w*[^.\n]{0,40}?pravdepodobnos\w*", nizke):
        if not re.search(r"\bnie\b|\bne\w+|nepredstavuje|neznamená", m.group(0)):
            problemy.append(f"Skóre rizika vydávané za pravdepodobnosť: „{_riadok(m.group(0), 100)}“")

    # 5. Pravdepodobnosť len slovami mierky PHIA
    for m in re.finditer(r"pravdepodobnos\w*[^.\n]{0,30}?\d+(?:[,.]\d+)?\s?%|\d+(?:[,.]\d+)?\s?%[^.\n]{0,15}"
                         r"pravdepodobnos\w*", nizke):
        problemy.append(f"Pravdepodobnosť číslom namiesto výrazu z mierky PHIA: „{_riadok(m.group(0), 100)}“")
    for m in re.finditer(r"\b(vysok|nízk|mal|veľk|stredn|značn|reáln[ae])\w*\s+pravdepodobnos\w*|\bšanc\w*|"
                         r"\bs istotou\b", nizke):
        problemy.append(f"Výraz mimo mierky PHIA: „{m.group(0)}“")
    kj = next((t for n, t in sekcie.items() if "key judgement" in n), "")
    for r in kj.splitlines():
        if _ODRAZKA.match(r):
            if not PHIA_VZOR.search(r):
                problemy.append(f"Kľúčový úsudok bez výrazu z mierky PHIA: „{_riadok(r, 120)}“")
            elif not _ISTOTA.search(r):
                upozornenia.append(f"Kľúčový úsudok bez istoty (nízka/stredná): „{_riadok(r, 80)}“")

    # 5b. BLUF: prvá veta odpovedá na otázku, výraz z mierky PHIA a istota sú v 1. alebo 2. vete
    bluf = next((t for n, t in sekcie.items() if "bottom line" in n), "")
    dve = _prve_vety(bluf, 2)
    if bluf and not (PHIA_VZOR.search(dve) and _ISTOTA.search(dve)):
        chyba = " a ".join(x for x, ok in [("výraz z mierky PHIA", PHIA_VZOR.search(dve)),
                                           ("istotu (nízka/stredná)", _ISTOTA.search(dve))] if not ok)
        problemy.append(f"Prvé dve vety BLUF nemajú {chyba}: „{_riadok(dve, 160)}“")

    # 5c. Skóre a historické súbehy sú signály, nie dôkaz: bez nezávislého potvrdenia (zdroj W…)
    #     najviac „pravdepodobné“ a istota najviac stredná; zakázané slová preháňajúce istotu
    nezavisle = any(i.startswith("W") for i, _ in citacie(brief))
    for m in ZAKAZANE_SLOVA.finditer(brief):
        problemy.append(f"Zakázané slovo „{m.group(0)}“ (preháňa istotu; skóre a súbehy sú signály, nie dôkaz).")
    if not nezavisle:
        for m in _NAD_STROP.finditer(brief):
            problemy.append(f"„{m.group(0)}“ bez nezávislého potvrdenia – najviac „pravdepodobné“.")
        for m in _VYSOKA_ISTOTA.finditer(brief):
            problemy.append(f"Vysoká istota bez nezávislého potvrdenia – najviac stredná: „{_riadok(m.group(0), 60)}“")

    # 6. Náhrady: zámenu inej látky môže urobiť len lekár (červené čiary) – ako samostatné upozornenie
    upozornenie = [r for r in brief.splitlines() if _RIADOK_UPOZORNENIE.match(r) and "lekár" in r.lower()]
    if "náhrad" in nizke and not upozornenie:
        problemy.append("Správa hovorí o náhradách, ale chýba samostatný riadok „- **Upozornenie:** Zámenu inej "
                        "látky môže urobiť len lekár…“ (napr. na konci Discussion).")

    # 6b. Náhrady inej liekovej formy smú byť len s označením „iná forma, len po posúdení lekárom“
    for kandidat in ine_formy or []:
        for r in brief.splitlines():
            if not _spomina(r, kandidat):
                continue
            if not (_INA_FORMA.search(r) and "lekár" in r.lower()):
                problemy.append(f"{kandidat['nazov']} ({kandidat['kod']}) má inú liekovú formu ({kandidat['forma']}) "
                                f"ako {kandidat['povodny_popis']}; uveď ho najviac ako "
                                f"„iná forma, len po posúdení lekárom“: „{_riadok(r, 90)}“")
                break

    # 6c. Náhrady ako názov + sila: najviac MAX_NAHRAD v riadku a bez popisu balenia
    for r in brief.splitlines():
        if r.lstrip().startswith("#"):
            continue
        # kandidát s rovnakým názvom ako pôvodný liek (iná veľkosť balenia) neznamená, že riadok je o náhradách
        spomenute = [k for k in kandidati if not k["je_povodny_nazov"] and _spomina(r, k)]
        po_skupinach: dict[str, set] = {}
        for k in spomenute:
            if k["rovnaka_forma"] and not k["ine_balenie"]:
                po_skupinach.setdefault(k["skupina"], set()).add(_bez_medzier(k["nazov"]))
        for skupina, nazvy in po_skupinach.items():
            if len(nazvy) > MAX_NAHRAD:
                problemy.append(f"Riadok vymenúva {len(nazvy)} náhrad za {skupina} – uveď najviac {MAX_NAHRAD} na "
                                f"jeden liek vo výpadku (názov + sila): „{_riadok(r, 90)}“")
        if spomenute or "náhrad" in r.lower():
            nazvy_vsetky = [_bez_medzier(k["nazov"]) for k in kandidati]
            balenia = [m.group(0) for m in _BALENIE_NAHRADY.finditer(r)
                       if not any(_bez_medzier(m.group(0)) in n for n in nazvy_vsetky)]
            balenia += [m.group(0) for m in _POPIS_BALENIA.finditer(r)]
            if balenia:
                problemy.append(f"Náhrady uvádzaj ako názov + sila, bez popisu balenia (v správe „{balenia[0]}“): "
                                f"„{_riadok(r, 90)}“")

    # 6h. Iné balenie toho istého lieku nie je náhrada: vo vete o náhradách smie byť jeho názov len ako liek
    #     vo výpadku („za Amoksiklav 625 mg“, „Amoksiklav 625 mg je vo výpadku“) alebo s textom „iné balenie“
    for kandidat in [k for k in kandidati if k["ine_balenie"]]:
        vzor = re.compile(r"[\s*_]*".join(re.escape(s) for s in kandidat["nazov"].split()), re.IGNORECASE)
        for r in brief.splitlines():
            if r.lstrip().startswith("#"):
                continue
            for veta in _vety(_OZNACENIE_TUCNE.sub("", r)):
                if "náhrad" not in veta.lower() or re.search(r"in[ée]\w*\s+balen", veta, re.IGNORECASE):
                    continue
                zoznam = _zoznam_nahrad(veta)
                zle = [m for m in vzor.finditer(zoznam)
                       if not re.match(r"[\s*_]*(\([^)]*\)\s*)?(je|sú|bol\w*)?\s*(vo\s+výpadku|chýb)",
                                       zoznam[m.end():])
                       # „za Amoksiklav 625 mg …“, „za tablety Amoksiklav 625 mg …“ = liek vo výpadku, nie náhrada
                       and not re.search(r"\bza(?:\s+[^\W\d]+){0,2}[\s*_]*$", zoznam[:m.start()], re.IGNORECASE)]
                if zle:
                    problemy.append(f"{kandidat['nazov']} je iné balenie toho istého lieku, ktorý je vo výpadku – nie "
                                    f"je to náhrada; napíš ho ako „iné balenie toho istého lieku“ a medzi náhradami "
                                    f"ho nevymenúvaj: „{_riadok(veta, 100)}“")
                    break
            else:
                continue
            break

    # 6d. Citácie podľa krajiny: E001–E003 sú české zdroje, E004–E005 slovenské. Len v riadkoch „Fakt“ –
    #     BLUF, Key judgements a úsudky spájajú dáta z oboch krajín; fakt o oboch krajinách je tiež v poriadku.
    #     Problém je len fakt o jednej krajine, ktorý cituje VÝHRADNE zdroje druhej. Zmiešané citácie sú
    #     v poriadku – každá patrí k svojej časti vety („výpadok v ČR [E001, A2] a historické výpadky [E005, A2]“).
    for r in brief.splitlines():
        if not _RIADOK_FAKT.match(r):
            continue
        krajiny_citacii = {KRAJINA_ZDROJA.get(i) for i, _ in citacie(r)} - {None}
        if not krajiny_citacii:
            continue
        sr, cr = bool(_SR_VZOR.search(r)), bool(_CR_VZOR.search(r))
        if sr and not cr and krajiny_citacii == {"CZ"}:
            zle = sorted({i for i, _ in citacie(r) if KRAJINA_ZDROJA.get(i) == "CZ"})
            problemy.append(f"Fakt o SR cituje len český zdroj {', '.join(zle)} (E001–E003 sú zdroje ČR, pre SR "
                            f"použi E004 alebo E005): „{_riadok(r, 100)}“")
        if cr and not sr and krajiny_citacii == {"SK"}:
            zle = sorted({i for i, _ in citacie(r) if KRAJINA_ZDROJA.get(i) == "SK"})
            problemy.append(f"Fakt o ČR cituje len slovenský zdroj {', '.join(zle)} (E004–E005 sú zdroje SR, pre "
                            f"ČR použi E001, E002 alebo E003): „{_riadok(r, 100)}“")

    # 6g. Označenia riadkov v Discussion: len **Fakt:**, **Úsudok:**, **Upozornenie:** (presne v tomto tvare)
    diskusia = next((t for n, t in sekcie.items() if n.startswith("discussion")), "")
    for r in diskusia.splitlines():
        tucne, zname = _OZNACENIE_TUCNE.match(r), _OZNACENIE_ZNAME.match(r)
        oznacenie = tucne.group(1).strip() if tucne else (zname.group(0).strip(" -*+") if zname else None)
        if not oznacenie:
            continue
        normalizovane = re.sub(r"\s+", "", oznacenie)
        if normalizovane in POVOLENE_OZNACENIA:
            continue
        slovo = re.sub(r"[*_:\s]", "", oznacenie).lower()
        navrh = _SPRAVNE_OZNACENIE.get(slovo)
        problemy.append(f"Nepovolené označenie riadku „{oznacenie}“ v Discussion – povolené sú len "
                        f"{', '.join(POVOLENE_OZNACENIA)}" + (f"; oprav na {navrh}" if navrh else "")
                        + f": „{_riadok(r, 80)}“")

    # 6f. Jazyk: znaky z poľštiny a maďarčiny („możność“ namiesto „možnosť“)
    videne_slova = set()
    for m in _CUDZIE_SLOVO.finditer(brief):
        slovo = m.group(0)
        if slovo in videne_slova:
            continue
        videne_slova.add(slovo)
        znaky = list(dict.fromkeys(_CUDZIE_ZNAKY.findall(slovo)))
        problemy.append(f"{'Znaky' if len(znaky) > 1 else 'Znak'} „{', '.join(znaky)}“ v slovenčine nie "
                        f"{'sú' if len(znaky) > 1 else 'je'}: „{slovo}“ – oprav napr. na „{navrh_slovensky(slovo)}“.")

    # 6e. Označenia KIQ1–KIQ5 nepatria do správy pre zákazníka
    kiq = [r for r in brief.splitlines() if _KIQ.search(r)]
    if kiq:
        problemy.append(f"Správa obsahuje označenie KIQ ({len(kiq)}× v riadkoch) – v texte pre zákazníka napíš tému "
                        f"(napr. riziko výpadku, náhrady, časový posun): „{_riadok(kiq[0], 90)}“")

    # 7. Čísla vo faktoch by mali byť vo výsledkoch nástrojov (len upozornenie)
    data_cisla = data_json.replace(",", ".")
    for r in brief.splitlines():
        if not _RIADOK_FAKT.match(r):
            continue
        bez_citacii = _SKUPINA.sub("", r)
        bez_kodov = re.sub(r"\b[A-Z]\d{2}[A-Z0-9]*\b", "", bez_citacii)
        for cislo in re.findall(r"(?<![\w.])\d+(?:[,.]\d+)?(?![\w])", bez_kodov):
            if len(cislo) >= 2 and cislo.replace(",", ".") not in data_cisla:
                upozornenia.append(f"Číslo {cislo} vo fakte sa nenašlo vo výsledkoch nástrojov: „{_riadok(r, 80)}“")

    # 8. Skóre, kódy liekov s balením a časový posun sa musia zhodovať s výsledkami nástrojov
    problemy += kontrola_cisel(brief, data)
    return problemy, upozornenia


# ---------------------------------------------------------------------------
# Pevné odpovede pre režim LIEKRADAR_FAKE_LLM=1
# ---------------------------------------------------------------------------

def _fake_analyza(stav: Stav) -> str:
    riadky = ["## Zistenia (Fact)"]
    for oznacenie, z in stav.get("data", {}).items():
        v = z.get("vysledok") or {}
        zdroj = (v.get("spolocne") or {}).get("zdroj") or " ".join(v.get("zdroje", [])) or "[E005, A2]"
        pocet = v.get("riadkov_spolu", "–")
        riadky.append(f"- Fakt: nástroj {oznacenie} vrátil {pocet} záznamov {zdroj}")
    riadky += ["", "## Úsudky (Inference)",
               "- Odhadujeme, že lieky s najvyšším skóre sú reálna možnosť ďalších výpadkov (istota: nízka; "
               "odpoveď v režime FAKE_LLM)."]
    return "\n".join(riadky)


def _nazov_a_sila(r: dict) -> str:
    """„MEDOCLAV 625 mg“ – sila sa pridá, len ak už nie je v názve."""
    nazov, sila = str(r.get("nazov") or "").strip(), re.sub(r"\s+", " ", str(r.get("sila") or "")).strip()
    sila_v_nazve = _bez_medzier(sila) in _bez_medzier(nazov) or re.search(r"\d\s*(?:mg|g|ml|%|iu)", nazov, re.I)
    return nazov if not sila or sila_v_nazve else f"{nazov} {sila}"


def _fake_nahrady_zoznam(v: dict, rovnaka: bool) -> list[str]:
    """Názvy + sila kandidátov rovnakej (alebo inej) formy, každý liek raz, najviac MAX_NAHRAD.
    rovnaka_forma None (nahrady_za_latku bez lieku vo výpadku) berieme ako rovnakú formu."""
    vysledok: list[str] = []
    for r in v.get("zaznamy", []):
        if r.get("ine_balenie_toho_isteho"):
            continue
        if (r.get("rovnaka_forma") is not False) == rovnaka and _nazov_a_sila(r) not in vysledok:
            vysledok.append(_nazov_a_sila(r) + ("" if rovnaka else f" ({r.get('forma')})"))
    return vysledok[:MAX_NAHRAD]


def _vysledky_nahrad(stav: Stav) -> list[tuple[str, dict, str]]:
    """(za čo sú náhrady, výsledok nástroja, citácia) pre nahrady aj nahrady_za_latku."""
    vysledok = []
    for z in stav.get("data", {}).values():
        v = z.get("vysledok") or {}
        zdroj = (v.get("spolocne") or {}).get("zdroj", "")
        if z["nastroj"] == "nahrady" and "povodny_liek" in v:
            vysledok.append((_nazov_a_sila(v["povodny_liek"]), v, zdroj or v["povodny_liek"]["zdroj"]))
        elif z["nastroj"] == "nahrady_za_latku" and v.get("zaznamy"):
            krajina = "na Slovensku" if v.get("krajina") == "SK" else "v Česku"
            vysledok.append((f"{str(v.get('latka') or v.get('atc')).lower()} {krajina}", v, zdroj))
    return vysledok


def _fake_odpoved(stav: Stav) -> str:
    """Prvá veta BLUF: priama odpoveď (pri náhradách ich zoznam, inak najrizikovejšie lieky)."""
    for za, v, _ in _vysledky_nahrad(stav):
        skupiny: dict[str, list[str]] = {}
        for r in v.get("zaznamy", []):  # nahrady_za_latku: náhrady za každý liek vo výpadku zvlášť
            if r.get("za_lieky") and r.get("rovnaka_forma") is not False and not r.get("ine_balenie_toho_isteho"):
                zoznam = skupiny.setdefault(r["za_lieky"][0], [])
                if len(zoznam) < MAX_NAHRAD and _nazov_a_sila(r) not in zoznam:
                    zoznam.append(_nazov_a_sila(r))
        if len(skupiny) > 1:
            casti = [f"za {liek} {', '.join(nahrady)}" for liek, nahrady in skupiny.items()]
            return f"Na Slovensku sa dodávajú tieto náhrady s rovnakou látkou a formou – {'; '.join(casti)}."
        if _fake_nahrady_zoznam(v, True):
            return f"Za {za} sa dodávajú tieto náhrady s rovnakou látkou a formou: {', '.join(_fake_nahrady_zoznam(v, True))}."
    top = next((z["vysledok"] for z in stav.get("data", {}).values()
                if z["nastroj"] == "top_rizikove" and z.get("vysledok")), {"zaznamy": []})
    nazvy = ", ".join(str(r.get("nazov")) for r in top.get("zaznamy", [])[:3])
    return f"Najvyššie skóre rizika výpadku majú {nazvy}." if nazvy else "Nástroje nevrátili žiadne lieky."


def _fake_nahrady(stav: Stav) -> list[str]:
    """Náhrady podľa liekovej formy (rovnaká forma = náhrada, iná forma = len po posúdení lekárom)."""
    riadky = []
    for za, v, zdroj in _vysledky_nahrad(stav):
        rovnake, ine = _fake_nahrady_zoznam(v, True), _fake_nahrady_zoznam(v, False)
        if rovnake:
            riadky.append(f"- **Fakt:** Náhrady za {za} s rovnakou formou: {', '.join(rovnake)} {zdroj}")
        if ine:
            riadky.append(f"- **Fakt:** Iná forma, len po posúdení lekárom: {', '.join(ine)} {zdroj}")
        balenia = list(dict.fromkeys(_nazov_a_sila(r) for r in v.get("zaznamy", []) + (v.get("ine_balenia_toho_isteho") or [])
                                     if r.get("ine_balenie_toho_isteho")))
        if balenia:
            riadky.append(f"- **Fakt:** Dodáva sa aj iné balenie toho istého lieku: {', '.join(balenia)} {zdroj}")
    return riadky


def _fake_brief(stav: Stav, oprava: bool) -> str:
    persona = stav.get("persona", "lekaren")
    top = next((z["vysledok"] for z in stav.get("data", {}).values()
                if z["nastroj"] == "top_rizikove" and z.get("vysledok")), {"zaznamy": []})
    fakty = []
    for i, r in enumerate(top.get("zaznamy", [])[:3]):
        dovod = (r.get("dovody") or "").split(";")[0].strip()
        skore = r.get("skore")
        if not oprava and i == 2 and isinstance(skore, int):
            skore += 1  # prvá verzia má zámerne zlé skóre (test kontroly čísel)
        fakty.append(f"- **Fakt:** {r.get('nazov')} ({r.get('drzitel')}) má skóre rizika {skore} zo 100; "
                     f"dôvod: {dovod}")
    if not oprava:  # prvá verzia má zámerne fakt bez citácie, aby sa otestovala oprava cez kritika
        fakty.append(f"- **Fakt:** Nástroj top_rizikove vrátil {top.get('riadkov_spolu', 0)} liekov.")
    else:
        fakty.append(f"- **Fakt:** Nástroj top_rizikove vrátil {top.get('riadkov_spolu', 0)} liekov [E005, A2].")
    return "\n".join([
        f"# LiekRadar – {stav.get('otazka', '')}",
        "",
        "## Bottom line up front",
        f"{_fake_odpoved(stav)} Že pri liekoch s najvyšším skóre príde ďalší výpadok, je reálna možnosť "
        f"(istota: nízka). Testovacia správa (LIEKRADAR_FAKE_LLM=1) pre personu {persona}.",
        "",
        "## Key judgements",
        "- Odhadujeme, že najrizikovejšie lieky z tabuľky rizika výpadku čaká výpadok – reálna možnosť, "
        "istota: nízka.",
        *(["- Odhadujeme, že pri prechode na alternatívne sily alebo iné balenia bude potrebná opatrnosť pri "
           "výdaji…"] if oprava and os.environ.get("LIEKRADAR_FAKE_RIADKY") else []),
        "",
        "## Discussion",
        *fakty,
        *_fake_nahrady(stav),
        "- **Úsudok:** Odhadujeme, že skóre je len poradie liekov, nie pravdepodobnosť."
        + (" [E004, A1] [E005, A2]" if oprava and os.environ.get("LIEKRADAR_FAKE_RIADKY") else ""),
        "- **Upozornenie:** Zámenu inej látky alebo liekovej formy môže urobiť len lekár; správa nie je "
        "odporúčanie pre pacientov.",
        "",
        "## Alternative explanations",
        "- Výpadky môžu byť administratívne (zmena balenia), nie skutočný nedostatok.",
        "",
        "## Key assumptions and gaps",
        "- Predpokladáme, že hlásenia sú úplné. Pri náhradách: zámenu inej látky môže urobiť len lekár.",
        "",
        "## Indicators to watch",
        "- Nové hlásenia o prerušení dodávok rovnakého výrobcu v druhej krajine."
        + (" Sledujte aj prebiehające výpadky v ČR." if oprava and os.environ.get("LIEKRADAR_FAKE_KOREKTURA") else ""),
        "",
        "## Sources and method annex",
        "- [E004, A1] ŠÚKL – register liekov; [E005, A2] ŠÚKL – hlásenia o dodávkach.",
        "",
        "## AI use statement",
        "Doplní systém po kontrole kritikom.",
    ])


# ---------------------------------------------------------------------------
# Agenti (uzly grafu)
# ---------------------------------------------------------------------------

ROLA_ORCHESTRATOR = f"""Si **orchestrátor** (fáza CI: plánovanie). Z otázky a persony vyber KIQ, krajiny,
ATC prefix a zoznam volaní nástrojov. Nič nepočítaš a neodpovedáš na otázku – len plánuješ.

KIQ: {_json(KIQ_POPIS)}

Povolené nástroje (iné neexistujú):
{chr(10).join('- ' + t[3] for t in tools.NASTROJE.values())}

Pravidlá plánu:
- Najviac {MAX_VOLANI_NASTROJOV} volaní. Krajina je CZ alebo SK. ATC prefix napr. J01, ATC7 napr. J01CR02.
- Kódy liekov ani ATC7 si nevymýšľaj. Ak chceš detail, posun alebo náhrady pre lieky z výsledku KIQ1,
  daj do `atc` alebo `kod` hodnotu "{ZASTUPCA}" – zberný krok doplní {ZASTUPCA_POCET} najrizikovejšie lieky.
  Zástupca funguje len vtedy, keď plán volá aj top_rizikove.
- Keď otázka menuje látku alebo ATC a pýta sa na náhrady (čím nahradiť, náhrada, alternatíva), VŽDY použi
  nahrady_za_latku(krajina, atc) s ATC7 látky (napr. amoxicilín s kyselinou klavulánovou = J01CR02),
  pre každú krajinu z otázky. Nástroj nahrady (podľa kódu lieku) vtedy nepoužívaj.
- Ak otázka nespomína krajinu, ber obe (CZ aj SK).
- Rozsah: "pacient", ak sa pýta pacient (alebo za blízkeho) na VLASTNÝ liek – čo si môže vziať namiesto
  neho, či ho môže vymeniť, ako ho užívať alebo dávkovať (napr. „došiel mi xanax, čo iné si môžem dať“,
  „můžu si místo X vzít Y“, „I ran out of my pills, what can I take“). Vtedy nástroje nenavrhuj.
  Inak "ok" – otázky nákupcu lekárenskej siete alebo výrobcu o trhu, rizikách a náhradách v sortimente.
- Jazyk: jazyk, v ktorom je otázka napísaná – "sk", "cs" alebo "en"."""

PRAVIDLO_ISTOTY = """- Skóre rizika aj historické súbehy výpadkov (CZ–SK) sú SIGNÁLY, nie dôkaz. Bez nezávislého potvrdenia
  (zdroj W… v Case Logu, v tomto behu žiadny nie je) je pravdepodobnosť najviac „pravdepodobné“ a istota
  najviac stredná. Nepoužívaj „veľmi pravdepodobné“, „takmer isté“ ani vysokú istotu.
- Zakázané slová: preukazuje, dokazuje, eliminuje, isto (ani ich tvary ako „preukázateľne“, „eliminovať“)."""

PRAVIDLO_NAHRAD = f"""- Náhrady (nástroje nahrady a nahrady_za_latku): ako náhradu uveď LEN lieky s `rovnaka_forma: true`, teda
  s rovnakou liekovou formou ako pôvodný liek (`povodny_liek.forma` pri nahrady; pri nahrady_za_latku liek vo
  výpadku v poli `za_lieky`). Pri nahrady_za_latku zoskup náhrady podľa lieku vo výpadku, za ktorý sú
  (tablety zvlášť, suspenzia zvlášť). Lieky inej formy (napr. IMP, TBL, SOL IJF namiesto SOL INF) uveď najviac
  v samostatnej odrážke s textom „iná forma, len po posúdení lekárom“ a s ich formou.
- Kandidát s `ine_balenie_toho_isteho: true` má rovnaký názov a silu ako liek vo výpadku (iný kód) – nie je to
  náhrada. Napíš ho v samostatnej vete ako „iné balenie toho istého lieku“ (napr. „Dodáva sa aj iné balenie
  toho istého lieku Amoksiklav 625 mg.“) a v BLUF ani v zozname náhrad ho nevymenúvaj.
- Náhrady píš ako názov + sila (silu len ak už nie je v názve), najviac {MAX_NAHRAD}, napr. „MEDOCLAV 625 mg,
  Penlac 875 mg/125 mg“. Bez kódov a bez popisu balenia (nie „tbl flm 21x625 mg (blis.Al/PVC)“,
  nie „plu por 1x140 ml (fľ.skl.hnedá)“). Ten istý liek v inej veľkosti balenia uveď len raz."""

PRAVIDLO_KRAJINY = """- Citácie podľa krajiny – zdroj musí patriť krajine, o ktorej je fakt:
  | ID | krajina | zdroj |
  |---|---|---|
  | E001 | ČR | SÚKL – hlásenia o dodávkach |
  | E002 | ČR | SÚKL – databáza liekov DLP |
  | E003 | ČR | SÚKL – DIS-13 dodávky distribútorov |
  | E004 | SR | ŠÚKL – register liekov |
  | E005 | SR | ŠÚKL – hlásenia o dodávkach |
  Každú citáciu daj k tej časti vety, ktorú dokladá; český údaj (napr. „látka má výpadok v ČR“) cituj českým
  zdrojom a ČR v tej časti vety napíš. Chyba je LEN fakt, ktorý spomína jednu krajinu a cituje VÝHRADNE zdroje
  druhej (napr. hovorí len o SR a cituje len E001–E003). Fakt so zmiešanými citáciami (české aj slovenské,
  napr. „výpadok v ČR [E001, A2] a historické výpadky [E005, A2]“) je v poriadku. BLUF, Key judgements
  a úsudky spájajú dáta z oboch krajín – tam môžu byť české aj slovenské zdroje spolu.
- JAZYK: píš spisovne po slovensky, nie po poľsky ani po česky. Žiadne ą, ę, ł, ś, ż, ć, ń, ő, ű
  (napr. „prebiehajúce“, nie „prebiehające“; „možnosť“, nie „możność“) ani české tvary ako „Úsudek“,
  „výpadek“, „zjištění“, „léčivo“ (správne „Úsudok“, „výpadok“, „zistenie“, „liečivo“).
- Označenia KIQ1–KIQ5 do textu nepíš; napíš tému (riziko výpadku, časový posun ČR–SR, náhrady, konkurenti,
  trhové medzery)."""

ROLA_ANALYTIK = f"""Si **analytik** (fáza CI: analýza). Z výsledkov nástrojov (JSON) urob zistenia k otázke.
- Píš VŽDY po slovensky, aj keď je otázka po česky alebo po anglicky (do jazyka otázky správu na konci
  preloží samostatný krok preklad).
- Čísla ber LEN z výsledkov nástrojov, nič neodhaduj ani neprepočítavaj z pamäte.
- Fakty a úsudky píš oddelene:
  `## Zistenia (Fact)` – odrážky „- Fakt: … [ID, Admiralty]“; citáciu prevezmi z poľa `zdroj`, `zdroje`
  alebo z textu `dovody` daného záznamu. Každý zdroj zvlášť: [E001, A2] [E005, A2].
  `## Úsudky (Inference)` – odrážky začínajú „Odhadujeme…“ alebo výrazom z mierky PHIA („Pravdepodobne…“,
  „Pravdepodobné je…“, „Reálna možnosť je…“), pravdepodobnosť len
  výrazom z mierky PHIA, istota nízka alebo stredná.
  `## Medzery v dátach` – čo nástroje nepokryli.
- Skóre rizika 0–100 je poradie liekov z modelu, nie pravdepodobnosť; nikdy ho neprepočítavaj na percentá.
{PRAVIDLO_ISTOTY}
{PRAVIDLO_NAHRAD}
{PRAVIDLO_KRAJINY}
- Zohľadni personu: výrobca hľadá príležitosti a konkurentov, lekáreň riziká, náhrady a predzásobenie.
- Píš po slovensky, stručne (najviac ~25 odrážok)."""

ROLA_REPORTER = f"""Si **reportér** (fáza CI: šírenie). Napíš správu BLUF po slovensky podľa sekcie 8 AGENTS.md.
VŽDY po slovensky, aj keď je otázka po česky alebo po anglicky – kritik kontroluje slovenskú verziu a do jazyka
otázky ju po schválení preloží samostatný krok preklad. Otázku si pre seba prelož a odpovedz na ňu po slovensky.
Použi presne tieto nadpisy úrovne ## (v tomto poradí):
## Bottom line up front
## Key judgements
## Discussion
## Alternative explanations
## Key assumptions and gaps
## Indicators to watch
## Sources and method annex
## AI use statement
Pravidlá:
- Na začiatok daj nadpis `# ` s krátkym názvom správy.
- BLUF: 2–4 vety pre danú personu. PRVÁ VETA priamo odpovedá na otázku (čo sa pýta, to vymenuj alebo povedz).
  Výraz z mierky PHIA a istota sú v 1. alebo 2. vete. Vzor podľa typu otázky:
  • otázka na riziko výpadku: prvá veta menuje najohrozenejšie lieky (so skóre) A ZÁROVEŇ obsahuje výraz PHIA
    a istotu, napr. „Najviac ohrozené sú Metronidazol B. Braun 5 mg/ml (skóre 86), Gentamicin B. Braun 3 mg/ml
    (83) a Ciprofloxacin Kabi 200 mg/100 ml (80); ich výpadok na Slovensku je reálna možnosť (istota: stredná).“
  • otázka na náhrady: „Na Slovensku sa dodávajú tieto náhrady s rovnakou látkou a formou: MEDOCLAV 625 mg,
    Penlac 875 mg/125 mg, MEGAMOX 625 forte. Že budú dostupné aj v najbližších týždňoch, je pravdepodobné
    (istota: stredná).“
  • náhrady, keď je vo výpadku viac liekov alebo foriem (`vo_vypadku` má viac položiek, napr. tablety aj
    suspenzia): BLUF uvedie náhrady pre KAŽDÝ z nich zvlášť, najviac 5 na jeden liek vo výpadku, napr.
    „Za tablety Amoksiklav 625 mg sa dodávajú MEDOCLAV 625 mg, MEGAMOX 625 forte a MEDOCLAV 1 g; za suspenziu
    Amoksiklav 2x457 mg/5 ml MEDOCLAV FORTE 312,5 mg a MEGAMOX DUO.“ Ktorá náhrada patrí ku ktorému lieku,
    je v poli `za_lieky`.
  • otázka na konkurentov alebo trhové medzery: najprv vymenuj firmy alebo látky, v 2. vete odhad s PHIA.
- Key judgements: 2–4 odrážky, každá s výrazom z mierky PHIA a istotou (nízka/stredná).
- Discussion: odrážky „- **Fakt:** … [ID, Admiralty]“ a „- **Úsudok:** …“ oddelene; úsudok začína „Odhadujeme…“
  alebo výrazom z mierky PHIA („Pravdepodobne…“, „Pravdepodobné je…“, „Reálna možnosť je…“).
  Riadok „**Úsudok:**“ píš BEZ citácií [ID, Admiralty] – úsudok nemá citáciu ako fakt (AGENTS.md, sekcia 4),
  opiera sa o fakty vyššie. Citácie, ktoré by v úsudku zostali, kód odstráni. Key judgements citácie mať môžu.
- Každý Key judgement musí mať výraz z mierky PHIA a istotu – aj odrážky o opatrnosti alebo odporúčaniach
  (napr. „Pri prechode na iné sily bude potrebná opatrnosť pri výdaji – pravdepodobné, istota: stredná.“).
  Čísla len z výsledkov nástrojov a zistení analytika. Skóre rizika je poradie 0–100, nie pravdepodobnosť,
  nikdy ho nepíš v percentách.
- Citácie: každý zdroj v samostatnej zátvorke – [E001, A2] [E005, A2], nikdy zlúčene [E001, A2, E005, A2].
{PRAVIDLO_ISTOTY}
{PRAVIDLO_NAHRAD}
{PRAVIDLO_KRAJINY}
- Čísla prepisuj presne zo záznamu TOHO lieku, o ktorom píšeš: skóre z top_rizikove (body bez jednotky),
  sila z poľa `sila` alebo z názvu, počty vĺn, dni posunu a počty prípadov z posun_latky danej látky.
  Kódy liekov a balenia (pole `doplnok`) do správy nepíš; ak kód predsa uvedieš, musí patriť danému lieku.
- Ak spomínaš náhrady, na konci Discussion pridaj samostatný riadok
  „- **Upozornenie:** Zámenu inej látky alebo liekovej formy môže urobiť len lekár; správa nie je odporúčanie
  pre pacientov.“ Upozornenie nie je fakt ani úsudok – nepíš ho do riadku „Úsudok“. Žiadne odporúčania pacientom.
- Sources and method annex: použité zdroje [ID, Admiralty] s názvom zo zoznamu zdrojov a nástroje.
- AI use statement: napíš len nadpis a vetu „Doplní systém po kontrole kritikom.“ – agentov, modely,
  kolá opravy a výsledok kontroly doplní kód.
- Vráť len markdown správy, bez úvodu a bez ``` blokov."""

ROLA_KRITIK = f"""Si **kritik** (kontrola kvality, Lint podľa AGENTS.md). Posúď správu BLUF:
1. Tvrdenia o faktoch majú citáciu a ich čísla sa dajú nájsť vo výsledkoch nástrojov.
2. Fakty a úsudky sú oddelené; úsudky začínajú „Odhadujeme…“ alebo výrazom z mierky PHIA
   („Pravdepodobne…“, „Pravdepodobné je…“).
3. Pravdepodobnosť je len výrazom z mierky PHIA; skóre rizika nie je prepočítané na percentá ani
   vydávané za pravdepodobnosť. Prvá veta BLUF priamo odpovedá na otázku (napr. pri otázke na náhrady
   ich vymenuje); výraz PHIA a istota sú v 1. alebo 2. vete BLUF.
4. Žiadne lekárske odporúčania pacientom; pri náhradách je uvedené, že zámenu urobí len lekár.
5. Správa odpovedá na otázku pre danú personu a nič si nevymýšľa.
{PRAVIDLO_ISTOTY}
{PRAVIDLO_NAHRAD}
{PRAVIDLO_KRAJINY}
Zmiešané citácie (české aj slovenské zdroje v jednom fakte, BLUF alebo úsudku) NIKDY nie sú dôvod správu
vrátiť – krajinu zdroja kontroluje kód.
Formálnu kontrolu citácií (tvar, ID a známka podľa manifestu, citácia pri každom fakte, krajina zdroja),
čísel (skóre, kódy a balenia liekov, vlny a dni posunu), počtu náhrad a označení KIQ robí kód; ak kód nehlási problém s citáciami, nevracaj správu pre ich
formát. Úsudky („**Úsudok:**“) sú podľa AGENTS.md BEZ citácií – chýbajúcu citáciu v úsudku nenamietaj
(citácie z nich odstraňuje kód). Sekciu AI use statement doplní systém po kontrole, jej obsah neposudzuj. Riadok „Upozornenie:“
nie je úsudok. Problémy z kódu dostaneš – ber ich ako
fakty. Schváľ (schvalene=true) len ak nie je žiadny vážny problém. Problémy píš konkrétne a stručne
po slovensky (čo a kde opraviť)."""


def bez_kiq(text: str) -> str:
    """„KIQ1“ -> „riziko výpadku“ (text pre modely, ktoré píšu správu pre zákazníka)."""
    return re.sub(r"\bKIQ\s*-?\s*([1-5])\b", lambda m: KIQ_TEMA[f"KIQ{m.group(1)}"], str(text))


def _plan_bez_kiq(plan: dict) -> dict:
    return {"temy": [KIQ_TEMA.get(k, k) for k in plan.get("kiq", [])], "krajiny": plan.get("krajiny"),
            "atc_prefix": plan.get("atc_prefix"), "zdovodnenie": bez_kiq(plan.get("zdovodnenie", ""))}


def _data_pre_model(stav: Stav) -> str:
    return _json({k: {"nastroj": z["nastroj"], "tema": KIQ_TEMA.get(z["kiq"], ""), "argumenty": z["argumenty"],
                      "vysledok": z.get("vysledok"), "chyba": z.get("chyba")}
                  for k, z in stav.get("data", {}).items()})


def _zdroje_pre_model(manifest: dict) -> str:
    return "\n".join(f"- [{i}, {z['admiralty']}] {z['zdroj']} (stiahnuté {z['stiahnute_utc']})"
                     for i, z in manifest.items())


def vytvor_graf(llm: LLM):
    """Zostaví graf. Objekt `llm` drží rozpočet volaní pre jednu otázku."""
    manifest = nacitaj_manifest()
    system = {
        "orchestrator": _system(ROLA_ORCHESTRATOR),
        "analytik": _system(ROLA_ANALYTIK),
        "reporter": _system(ROLA_REPORTER),
        "kritik": _system(ROLA_KRITIK),
    }

    def nastroj_llm() -> str:
        """Model, ktorý krok spravil (pri 503 hlavného modelu záložný) – do Case Logu."""
        return f"LLM {llm.posledny_model}"

    def so_zaloznym(uzol):
        """Ak krok spravil záložný model, pripíše to do prvého riadku priebehu."""
        def obal(stav: Stav) -> dict:
            vystup = uzol(stav)
            if llm.posledny_model != llm.model and vystup.get("priebeh"):
                vystup["priebeh"] = [vystup["priebeh"][0] + f" · záložný model {llm.posledny_model} "
                                     f"(hlavný {llm.model} vrátil 503)"] + vystup["priebeh"][1:]
            return vystup
        return obal

    def pacient(stav: Stav, jazyk: str, dovod: str, nastroj: str) -> dict:
        """Otázka pacienta: pevný text bez modelu, žiadne nástroje, graf končí."""
        return {"rozsah": "pacient", "jazyk": jazyk, "brief": odpoved_pre_pacienta(jazyk),
                "kritika": {"schvalene": True, "rozsah": "pacient", "problemy_kod": [], "problemy_llm": [],
                            "upozornenia": [], "kolo": 0},
                "case_log": [_zaznam("orchestrátor", nastroj, f"otázka: {stav['otazka']}",
                                     f"rozsah: pacient ({dovod}) · jazyk {jazyk} · pevný text bez modelu, "
                                     "nástroje sa nevolajú, správa sa neukladá")],
                "priebeh": [f"Orchestrátor (kontrola rozsahu): otázka pacienta ({dovod}) – LiekRadar neodporúča "
                            "lieky ani dávkovanie pacientom; nástroje ani ďalšie volania modelu sa nespúšťajú."]}

    def orchestrator(stav: Stav) -> dict:
        persona = stav["persona"]
        jazyk_heur = jazyk_textu(stav["otazka"])
        if je_pacientska_otazka(stav["otazka"]):  # poistka v kóde: bez volania modelu
            return pacient(stav, urci_jazyk(jazyk_heur, stav.get("jazyk_appky")),
                           f"vzor v kóde: „{pacientsky_vzor(stav['otazka'])}“", "kontrola rozsahu v kóde")
        vstup = (f"Otázka: {stav['otazka']}\nPersona: {persona} – {PERSONY[persona]}\n"
                 "Urči rozsah a jazyk otázky a navrhni plán (KIQ, krajiny, ATC prefix, volania nástrojov).")
        zaloha = zakladny_plan(stav["otazka"], persona)
        try:
            plan = llm.strukturovane(system["orchestrator"], vstup, Plan, fake=zaloha)
        except LLMChyba as e:
            return {"chyba": str(e), "priebeh": [f"Orchestrátor: chyba – {e}"],
                    "case_log": [_zaznam("orchestrátor", nastroj_llm(), "otázka + persona", f"CHYBA: {e}")]}
        jazyk = urci_jazyk(plan.jazyk or jazyk_heur, stav.get("jazyk_appky"))
        if plan.rozsah == "pacient":
            return pacient(stav, jazyk, "určil orchestrátor", nastroj_llm())
        volania, vyradene = over_plan(plan)
        poznamka = ""
        if not volania:
            plan = zakladny_plan(stav["otazka"], persona)
            volania, _ = over_plan(plan)
            poznamka = " Model nenavrhol platné volania, použitý základný plán."
        volania, upravy = zabezpec_nahrady_za_latku(stav["otazka"], plan, volania)
        plan_dict = {"kiq": plan.kiq, "krajiny": plan.krajiny, "atc_prefix": plan.atc_prefix,
                     "zdovodnenie": plan.zdovodnenie, "volania": volania, "vyradene": vyradene, "upravy": upravy}
        zoznam = ", ".join(f"{v['nastroj']}({', '.join(map(str, v['argumenty'].values()))})" for v in volania)
        log = [_zaznam("orchestrátor", nastroj_llm(), f"otázka: {stav['otazka']} · persona: {persona}",
                       f"KIQ {', '.join(plan.kiq)} · krajiny {', '.join(plan.krajiny)} · volania: {zoznam}"
                       + (f" · vyradené: {'; '.join(vyradene)}" if vyradene else "")
                       + (f" · úpravy plánu v kóde: {'; '.join(upravy)}" if upravy else "") + poznamka)]
        return {"plan": plan_dict, "case_log": log, "rozsah": "ok", "jazyk": jazyk,
                "priebeh": [f"Orchestrátor (plánovanie): {', '.join(plan.kiq)} · {', '.join(plan.krajiny)}"
                            f" · jazyk odpovede {jazyk}"
                            f"{' · ATC ' + plan.atc_prefix if plan.atc_prefix else ''} · {len(volania)} volaní "
                            f"nástrojov – {plan.zdovodnenie}{poznamka}"]}

    def zber(stav: Stav) -> dict:
        volania = list(stav["plan"]["volania"])
        # volania so zástupcom až po top_rizikove, aby bolo z čoho doplniť
        volania.sort(key=lambda v: ZASTUPCA in v["argumenty"].values())
        data, log, priebeh, pocet = {}, [], [], 0
        for v in volania:
            if pocet >= MAX_VOLANI_PO_DOPLNENI:
                break
            argumenty_zoznam = [v["argumenty"]]
            if ZASTUPCA in v["argumenty"].values():
                argumenty_zoznam = _dopln_zastupcu(v, data)
                if not argumenty_zoznam:
                    log.append(_zaznam("zber", v["nastroj"], _json(v["argumenty"]),
                                       "vynechané – nie je výsledok top_rizikove na doplnenie"))
                    continue
            for arg in argumenty_zoznam:
                if pocet >= MAX_VOLANI_PO_DOPLNENI:
                    break
                pocet += 1
                oznacenie = f"{v['nastroj']}({', '.join(f'{k}={h}' for k, h in arg.items())})"
                zaciatok = time.perf_counter()
                try:
                    vysledok, chyba = tools.zavolaj(v["nastroj"], arg), None
                except Exception as e:  # noqa: BLE001 – chyba v pipeline sa zapíše, graf pokračuje
                    vysledok, chyba = None, f"{type(e).__name__}: {e}"
                trvanie = time.perf_counter() - zaciatok
                data[oznacenie] = {"nastroj": v["nastroj"], "kiq": tools.NASTROJE[v["nastroj"]][1],
                                   "argumenty": arg, "vysledok": vysledok, "chyba": chyba}
                popis = f"CHYBA: {chyba}" if chyba else _zhrn_vysledok(vysledok)
                log.append(_zaznam("zber", v["nastroj"], _json(arg), f"{popis} · {trvanie:.1f} s"))
                priebeh.append(f"  {oznacenie}: {popis}")
        uspesne = sum(1 for z in data.values() if not z["chyba"])
        return {"data": data, "case_log": log,
                "priebeh": [f"Zber (bez LLM): {uspesne} z {len(data)} volaní nástrojov úspešných"] + priebeh}

    def analytik(stav: Stav) -> dict:
        data_json = _data_pre_model(stav)
        vstup = (f"Otázka: {stav['otazka']}\nPersona: {stav['persona']} – {PERSONY[stav['persona']]}\n"
                 f"Plán: {_json(_plan_bez_kiq(stav['plan']))}\n\n"
                 f"Výsledky nástrojov (JSON):\n{data_json}")
        try:
            analyza = llm.text(system["analytik"], vstup, fake=_fake_analyza(stav))
        except LLMChyba as e:
            return {"chyba": str(e), "priebeh": [f"Analytik: chyba – {e}"],
                    "case_log": [_zaznam("analytik", nastroj_llm(), "výsledky nástrojov", f"CHYBA: {e}")]}
        fakty = len(re.findall(r"^\s*-\s*\**fakt", analyza, re.IGNORECASE | re.MULTILINE))
        usudky = len(re.findall(r"^\s*-\s*\**(odhadujeme|pravdepodobne)", analyza, re.IGNORECASE | re.MULTILINE))
        return {"analyza": analyza,
                "case_log": [_zaznam("analytik", nastroj_llm(),
                                     f"výsledky {len(stav.get('data', {}))} volaní ({len(data_json)} znakov JSON)",
                                     f"{fakty} faktov, {usudky} úsudkov ({len(analyza)} znakov)")],
                "priebeh": [f"Analytik (analýza): {fakty} faktov s citáciou, {usudky} úsudkov"]}

    def reporter(stav: Stav) -> dict:
        kritika = stav.get("kritika")
        oprava = bool(kritika) and not kritika.get("schvalene")
        vstup = (f"Otázka: {stav['otazka']}\nPersona: {stav['persona']} – {PERSONY[stav['persona']]}\n\n"
                 f"Zistenia analytika:\n{stav.get('analyza', '')}\n\n"
                 f"Výsledky nástrojov (JSON, jediný zdroj čísel):\n{_data_pre_model(stav)}\n\n"
                 f"Zoznam zdrojov (manifest):\n{_zdroje_pre_model(manifest)}")
        if oprava:
            problemy = kritika.get("problemy_kod", []) + kritika.get("problemy_llm", [])
            vstup += ("\n\nKritik správu vrátil na opravu. Oprav VŠETKY tieto problémy a vráť celú opravenú "
                      "správu:\n" + "\n".join(f"- {p}" for p in problemy) +
                      f"\n\nPôvodná správa:\n{stav.get('brief', '')}")
        try:
            brief = llm.text(system["reporter"], vstup, fake=_fake_brief(stav, oprava))
        except LLMChyba as e:
            return {"chyba": str(e), "priebeh": [f"Reportér: chyba – {e}"],
                    "case_log": [_zaznam("reportér", nastroj_llm(), "zistenia analytika", f"CHYBA: {e}")]}
        brief = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", brief.strip())
        vystup = {"brief": brief,
                  "case_log": [_zaznam("reportér", nastroj_llm(),
                                       "oprava podľa kritika" if oprava else "zistenia analytika + výsledky nástrojov",
                                       f"správa BLUF, {len(brief)} znakov")],
                  "priebeh": [("Reportér (šírenie): správa opravená podľa kritika" if oprava
                               else "Reportér (šírenie): správa BLUF napísaná")]}
        if oprava:
            vystup["pocet_oprav"] = stav.get("pocet_oprav", 0) + 1
        return vystup

    def kritik(stav: Stav) -> dict:
        # úsudky nemajú citácie ako fakty (AGENTS.md, sekcia 4) – kód ich odstráni ešte pred kontrolou
        brief, bez_citacii = kor.odstran_citacie_z_usudkov(stav.get("brief", ""))
        data_json = _data_pre_model(stav)
        problemy_kod, upozornenia = kontrola_v_kode(brief, stav.get("data", {}), manifest)
        log = ([_zaznam("kritik", "úprava v kóde", "riadky **Úsudok:** v Discussion",
                        f"odstránené citácie z {bez_citacii} riadkov úsudku (úsudok nemá citáciu ako fakt)")]
               if bez_citacii else [])
        log.append(_zaznam("kritik", "kontrola v kóde", f"správa {len(brief)} znakov",
                           f"{len(problemy_kod)} problémov, {len(upozornenia)} upozornení"
                           + (f": {problemy_kod[0]}" if problemy_kod else "")))
        problemy_llm, llm_schvalil, poznamka = [], True, ""
        if llm.pocet_volani < MAX_VOLANI_NA_OTAZKU:
            vstup = (f"Otázka: {stav['otazka']}\nPersona: {stav['persona']}\n\n"
                     f"Kontrola v kóde – problémy: {_json(problemy_kod)}; upozornenia: {_json(upozornenia)}\n\n"
                     f"Výsledky nástrojov (JSON):\n{data_json}\n\nSpráva na posúdenie:\n{brief}")
            try:
                fake_posudok = Posudok(schvalene=True)
                if os.environ.get("LIEKRADAR_FAKE_RIADKY") and stav.get("pocet_oprav", 0) >= MAX_OPRAV:
                    fake_posudok = Posudok(schvalene=False, problemy=[
                        "Druhý Key judgement („pri prechode na alternatívne sily alebo iné balenia bude potrebná "
                        "opatrnosť“) nemá výraz z mierky PHIA ani istotu.",
                        "Riadok Úsudok obsahuje citácie [E004, A1] [E005, A2], hoci úsudok nemá citáciu ako fakt."])
                posudok = llm.strukturovane(system["kritik"], vstup, Posudok, fake=fake_posudok)
                problemy_llm, llm_schvalil = list(posudok.problemy), bool(posudok.schvalene)
                kod_krajina = any("cituje len" in p for p in problemy_kod)
                odlozene = [] if kod_krajina else [p for p in problemy_llm if je_namietka_ku_krajine_citacie(p)]
                if odlozene:  # krajinu citácií posudzuje kód; zmiešané citácie sú v poriadku
                    problemy_llm = [p for p in problemy_llm if p not in odlozene]
                    upozornenia += [f"LLM kritik (neblokuje, krajinu citácií kontroluje kód): {p}" for p in odlozene]
                    llm_schvalil = llm_schvalil or not problemy_llm
                slova = [s for s, _ in cudzie_slova(brief)]
                jazykove = [p for p in problemy_llm if slova and je_namietka_k_jazyku(p, slova)]
                if jazykove:  # cudzie slová našiel kód, opraví ich korektúra – nie sú dôvod na prepisovanie správy
                    problemy_llm = [p for p in problemy_llm if p not in jazykove]
                    upozornenia += [f"LLM kritik (jazyk, rieši korektúra): {p}" for p in jazykove]
                    llm_schvalil = llm_schvalil or not problemy_llm
                citacie_usudkov = [p for p in problemy_llm if kor.je_namietka_k_citaciam_usudkov(p)]
                if citacie_usudkov:  # úsudky sú podľa AGENTS.md bez citácií, citácie z nich odstránil kód
                    problemy_llm = [p for p in problemy_llm if p not in citacie_usudkov]
                    upozornenia += [f"LLM kritik (neblokuje, úsudky sú bez citácií): {p}" for p in citacie_usudkov]
                    llm_schvalil = llm_schvalil or not problemy_llm
                if llm_schvalil:  # schválené = žiadne blokujúce problémy od modelu
                    upozornenia += problemy_llm
                    problemy_llm = []
                log.append(_zaznam("kritik", nastroj_llm(), "správa + výsledky nástrojov + kontrola v kóde",
                                   ("schválené" if llm_schvalil else "neschválené")
                                   + (f": {'; '.join(problemy_llm)}" if problemy_llm else "")))
            except LLMChyba as e:
                poznamka = f" (LLM kontrola zlyhala: {e})"
                log.append(_zaznam("kritik", nastroj_llm(), "správa", f"CHYBA: {e} – platí len kontrola v kóde"))
        else:
            poznamka = " (LLM kontrola vynechaná – rozpočet volaní)"
            log.append(_zaznam("kritik", nastroj_llm(), "správa", "vynechané – vyčerpaný rozpočet volaní"))
        schvalene = not problemy_kod and llm_schvalil
        pocet_oprav = stav.get("pocet_oprav", 0)
        # po oprave: ak zostali len problémy viazané na jednotlivé riadky, opraví ich korektúra riadkov;
        # námietky LLM kritika k tým istým riadkom sa tým považujú za vybavené, iné ďalej blokujú
        rezerva = 2 if stav.get("jazyk", "sk") != "sk" else 0  # posledné 2 volania patria prekladu a doprekladu
        opravit_riadky, vybavene = False, []
        if (not schvalene and pocet_oprav >= MAX_OPRAV and kor.len_riadkove(problemy_kod)
                and llm.pocet_volani < MAX_VOLANI_NA_OTAZKU - rezerva):
            ciele = kor.ciele(brief)
            vybavene = [p for p in problemy_llm if kor.je_namietka_k_riadkom(p, ciele)]
            if ciele and len(vybavene) == len(problemy_llm):
                opravit_riadky = True
                upozornenia += [f"LLM kritik (vybaví korektúra riadkov): {p}" for p in vybavene]
                problemy_llm = []
        if schvalene:
            verdikt = "schválené"
        elif pocet_oprav < MAX_OPRAV:
            verdikt = "vrátené reportérovi na opravu"
        elif opravit_riadky:
            verdikt = "zostali len problémy jednotlivých riadkov – nasleduje korektúra riadkov"
        else:
            verdikt = "neschválené ani po oprave – správa sa uloží s poznámkou"
        kritika = {"schvalene": schvalene, "problemy_kod": problemy_kod, "problemy_llm": problemy_llm,
                   "upozornenia": upozornenia, "kolo": pocet_oprav + 1, "opravit_riadky": opravit_riadky}
        detail = "; ".join((problemy_kod + problemy_llm)[:3])
        return {"brief": brief, "kritika": kritika, "case_log": log,
                "priebeh": [f"Kritik (kontrola): {verdikt} – {len(problemy_kod)} problémov v kóde, "
                            f"{len(problemy_llm)} od LLM{poznamka}" + (f". {detail}" if detail else "")]}

    def koniec_alebo_preklad(stav: Stav) -> str:
        """Ak odpoveď nemá byť po slovensky, posledný krok je preklad (alebo záznam, prečo sa neprekladá)."""
        if stav.get("chyba") or stav.get("jazyk", "sk") == "sk":
            return END
        return "preklad"

    def po_kritikovi(stav: Stav) -> str:
        kritika = stav["kritika"] if not stav.get("chyba") else {"schvalene": True}
        if kritika["schvalene"]:
            return koniec_alebo_preklad(stav)
        if stav.get("pocet_oprav", 0) < MAX_OPRAV:
            return "reporter"
        if kritika.get("opravit_riadky"):
            return "korektura"
        return koniec_alebo_preklad(stav)

    def preklad(stav: Stav) -> dict:
        """Schválenú slovenskú správu preloží do jazyka odpovede; kód overí zhodu čísel, citácií a názvov."""
        jazyk, brief = stav["jazyk"], stav.get("brief", "")
        if not (stav.get("kritika") or {}).get("schvalene"):
            return {"preklad": {"jazyk": jazyk, "stav": "neschvalene"},
                    "case_log": [_zaznam("preklad", "–", f"jazyk {jazyk}", "vynechaný – správa neprešla kontrolou, "
                                         "zobrazí sa slovenská verzia s poznámkou")],
                    "priebeh": [f"Preklad ({jazyk}): vynechaný – správa neschválená, zostáva slovenská verzia"]}
        if llm.pocet_volani >= MAX_VOLANI_NA_OTAZKU:
            return {"preklad": {"jazyk": jazyk, "stav": "vynechany"},
                    "case_log": [_zaznam("preklad", nastroj_llm(), f"jazyk {jazyk}", "vynechaný – vyčerpaný "
                                         "rozpočet volaní, zobrazí sa slovenská verzia")],
                    "priebeh": [f"Preklad ({jazyk}): vynechaný – vyčerpaný rozpočet volaní"]}
        try:
            text = prekl.ocisti(llm.text(prekl.rola_prekladu(jazyk), brief,
                                         fake=prekl.fake_preklad(brief, jazyk, stav.get("data", {}))))
        except LLMChyba as e:
            return {"preklad": {"jazyk": jazyk, "stav": "vynechany", "chyba": str(e)},
                    "case_log": [_zaznam("preklad", nastroj_llm(), f"jazyk {jazyk}", f"CHYBA: {e} – zostáva "
                                         "slovenská verzia")],
                    "priebeh": [f"Preklad ({jazyk}): zlyhal – {e}"]}
        data = stav.get("data", {})
        rozdiely = prekl.kontrola_prekladu(brief, text, data)
        nepreložene = [] if rozdiely else prekl.slovenske_riadky(text, jazyk, data, manifest)
        log = [_zaznam("preklad", nastroj_llm(), f"schválená správa {len(brief)} znakov → {jazyk}",
                       f"preklad {len(text)} znakov"),
               _zaznam("preklad", "kontrola v kóde", "nadpisy, označenia, citácie, čísla, kódy, názvy liekov, úplnosť",
                       "zhoda" if not rozdiely and not nepreložene else
                       f"NEZHODA – použitá slovenská verzia: {'; '.join(rozdiely)}" if rozdiely else
                       f"po slovensky zostalo {len(nepreložene)} riadkov: "
                       + "; ".join(f"riadok {i} ({', '.join(n[:4])})" for i, _, n in nepreložene))]
        doprelozene = 0
        if nepreložene and llm.pocet_volani < MAX_VOLANI_NA_OTAZKU:
            # cielený dopreklad: len riadky, ktoré zostali po slovensky; kód ich vymení a skontroluje znova
            ciele = [{"i": i, "riadok": r, "typy": ["preklad"]} for i, r, _ in nepreložene]
            try:
                opravy = llm.strukturovane(prekl.rola_doprekladu(jazyk), prekl.dopreklad_vstup(nepreložene),
                                           kor.OpravyRiadkov, fake=prekl.fake_dopreklad(text, nepreložene, jazyk, data))
                text, prijate, odmietnute = kor.pouzi_opravy(text, ciele, opravy)
                doprelozene = len(prijate)
                rozdiely = prekl.kontrola_prekladu(brief, text, data)
                nepreložene = prekl.slovenske_riadky(text, jazyk, data, manifest)
                log += [_zaznam("preklad", nastroj_llm(), f"dopreklad {len(ciele)} riadkov",
                                f"vymenené {len(prijate)}" + (f" · odmietnuté: {'; '.join(odmietnute)}" if odmietnute else "")),
                        _zaznam("preklad", "kontrola v kóde", "preklad po doprekladu",
                                "zhoda" if not rozdiely and not nepreložene else
                                f"NEZHODA: {'; '.join(rozdiely + [f'po slovensky zostalo {len(nepreložene)} riadkov'] if nepreložene else rozdiely)}")]
            except LLMChyba as e:
                log.append(_zaznam("preklad", nastroj_llm(), f"dopreklad {len(ciele)} riadkov", f"CHYBA: {e}"))
        elif nepreložene:
            log.append(_zaznam("preklad", nastroj_llm(), "dopreklad", "vynechaný – vyčerpaný rozpočet volaní"))
        if nepreložene and not rozdiely:
            rozdiely = [f"Neúplný preklad: po slovensky zostalo {len(nepreložene)} riadkov "
                        f"(napr. riadok {nepreložene[0][0]}: {', '.join(nepreložene[0][2][:4])})."]
        upozornenia = prekl.upozornenia_phia(brief, text, jazyk)
        if upozornenia:
            log.append(_zaznam("preklad", "kontrola v kóde", "výrazy PHIA v preklade", "; ".join(upozornenia)))
        if rozdiely:
            return {"preklad": {"jazyk": jazyk, "stav": "vratene_sk", "rozdiely": rozdiely, "upozornenia": upozornenia},
                    "case_log": log,
                    "priebeh": [f"Preklad ({jazyk}): nezhoda so slovenskou verziou ({rozdiely[0]}) – zobrazí sa "
                                "slovenská verzia s poznámkou"]}
        return {"brief_preklad": text, "preklad": {"jazyk": jazyk, "stav": "ok", "upozornenia": upozornenia,
                                                   "doprelozene": doprelozene},
                "case_log": log,
                "priebeh": [f"Preklad ({jazyk}): hotový" + (f" po doprekladu {doprelozene} riadkov" if doprelozene else "")
                            + " – citácie, čísla, kódy a názvy liekov sa zhodujú so slovenskou verziou, nič nezostalo "
                            "po slovensky"]}

    def korektura(stav: Stav) -> dict:
        """Po oprave zostali len problémy jednotlivých riadkov: jedno LLM volanie vráti náhradné riadky,
        kód ich vymení (zvyšok správy sa nemení) a spustí znova len kontrolu v kóde."""
        brief, kritika = stav.get("brief", ""), dict(stav["kritika"])
        ciele = kor.ciele(brief)
        popis_vstupu = "; ".join(f"riadok {c['i']}: {', '.join(c['typy'])}" for c in ciele)
        try:
            opravy = llm.strukturovane(kor.ROLA, kor.vstup_pre_model(stav["otazka"], ciele), kor.OpravyRiadkov,
                                       fake=kor.fake_opravy(ciele))
        except LLMChyba as e:
            kritika["opravit_riadky"] = False
            return {"kritika": kritika,
                    "case_log": [_zaznam("korektúra", nastroj_llm(), popis_vstupu, f"CHYBA: {e} – správa zostáva "
                                         "neschválená")],
                    "priebeh": [f"Korektúra riadkov: zlyhala – {e}"]}
        novy, prijate, odmietnute = kor.pouzi_opravy(brief, ciele, opravy)
        novy, bez_citacii = kor.odstran_citacie_z_usudkov(novy)
        problemy_kod, upozornenia = kontrola_v_kode(novy, stav.get("data", {}), manifest)
        schvalene = not problemy_kod and not kritika.get("problemy_llm")
        kritika.update({"schvalene": schvalene, "problemy_kod": problemy_kod,
                        "upozornenia": kritika.get("upozornenia", []) + upozornenia,
                        "korektura": [{"riadok": o["i"], "typy": o["typy"]} for o in prijate],
                        "opravit_riadky": False})
        zoznam = "; ".join(f"riadok {o['i']} ({', '.join(o['typy'])}): „{_riadok(o['pred'], 70)}“ → "
                           f"„{_riadok(o['po'], 90)}“" for o in prijate) or "žiadne"
        log = [_zaznam("korektúra", nastroj_llm(), f"{len(ciele)} riadkov s problémom: {popis_vstupu}",
                       f"vymenené: {zoznam}" + (f" · odmietnuté: {'; '.join(odmietnute)}" if odmietnute else "")
                       + (f" · odstránené citácie z {bez_citacii} úsudkov" if bez_citacii else "")),
               _zaznam("korektúra", "kontrola v kóde", f"správa po korektúre {len(novy)} znakov",
                       f"{len(problemy_kod)} problémov" + (f": {problemy_kod[0]}" if problemy_kod else ""))]
        return {"brief": novy, "kritika": kritika, "case_log": log,
                "priebeh": [f"Korektúra riadkov: vymenené {len(prijate)} z {len(ciele)} riadkov"
                            + (f", odmietnuté {len(odmietnute)}" if odmietnute else "")
                            + f" · kontrola v kóde: {len(problemy_kod)} problémov – "
                            + ("schválené" if schvalene else "neschválené")]}

    def dalej(cielovy: str) -> Callable[[Stav], str]:
        return lambda stav: END if stav.get("chyba") or stav.get("rozsah") == "pacient" else cielovy

    g = StateGraph(Stav)
    for nazov, uzol in [("orchestrator", so_zaloznym(orchestrator)), ("zber", zber),
                        ("analytik", so_zaloznym(analytik)), ("reporter", so_zaloznym(reporter)),
                        ("kritik", so_zaloznym(kritik)), ("korektura", so_zaloznym(korektura)),
                        ("preklad", so_zaloznym(preklad))]:
        g.add_node(nazov, uzol)
    g.add_edge(START, "orchestrator")
    g.add_conditional_edges("orchestrator", dalej("zber"), ["zber", END])
    g.add_edge("zber", "analytik")
    g.add_conditional_edges("analytik", dalej("reporter"), ["reporter", END])
    g.add_conditional_edges("reporter", dalej("kritik"), ["kritik", END])
    g.add_conditional_edges("kritik", po_kritikovi, ["reporter", "korektura", "preklad", END])
    g.add_conditional_edges("korektura", koniec_alebo_preklad, ["preklad", END])
    g.add_edge("preklad", END)
    return g.compile()


def _dopln_zastupcu(volanie: dict, data: dict) -> list[dict]:
    """Za "z_top_rizikove" dosadí ATC7 alebo kód z najrizikovejších liekov už zozbieraných v `data`."""
    arg = volanie["argumenty"]
    krajina = arg.get("krajina")
    top = [z for z in data.values() if z["nastroj"] == "top_rizikove" and z.get("vysledok")
           and (krajina is None or z["argumenty"].get("krajina") == krajina)]
    if not top:
        return []
    zaznamy = top[0]["vysledok"].get("zaznamy", [])
    vysledky, videne = [], set()
    for r in zaznamy:
        hodnota = r.get("atc") if arg.get("atc") == ZASTUPCA else r.get("kod")
        if not hodnota or hodnota in videne:
            continue
        videne.add(hodnota)
        novy = {k: (hodnota if h == ZASTUPCA else h) for k, h in arg.items()}
        if "krajina" in novy and novy["krajina"] is None:
            novy["krajina"] = top[0]["argumenty"].get("krajina")
        vysledky.append(novy)
        if len(vysledky) >= ZASTUPCA_POCET:
            break
    return vysledky


def _zhrn_vysledok(vysledok) -> str:
    """Jeden riadok o výsledku nástroja (do Case Logu a priebehu)."""
    if not isinstance(vysledok, dict):
        return "bez výsledku"
    zdroje = " ".join(f"[{i}, {z}]" for i, z in sorted(set(citacie(_json(vysledok)))))
    if "zaznamy" in vysledok:
        return f"{len(vysledok['zaznamy'])} z {vysledok['riadkov_spolu']} riadkov · {zdroje}"
    return f"{vysledok.get('atc', '')} {vysledok.get('nazov', '')} · {zdroje}".strip()


# ---------------------------------------------------------------------------
# Uloženie správy a Case Logu, vstupný bod pre aplikáciu
# ---------------------------------------------------------------------------

def _volny_nazov(priecinky: list[Path], zaklad: str) -> str:
    """Názov súboru, ktorý ešte nie je v žiadnom z priečinkov (pri zhode pridá -2, -3…)."""
    nazov, i = zaklad, 2
    while any((p / f"{nazov}.md").exists() for p in priecinky):
        nazov, i = f"{zaklad}-{i}", i + 1
    return nazov


def _riadok_case_logu(z: dict) -> str:
    return f"- {z['cas_utc']} · {z['agent']} · {z['nastroj']} · vstup: {z['vstup']} · výsledok: {z['vysledok']}"


def _modely_agenta(log: list[dict], agent: str) -> list[str]:
    """Modely, ktoré úspešne spravili kroky daného agenta (v poradí)."""
    modely = []
    for z in log:
        if z["agent"] == agent and z["nastroj"].startswith("LLM ") and not z["vysledok"].startswith(
                ("CHYBA", "vynechané")):
            model = z["nastroj"][4:]
            if model not in modely:
                modely.append(model)
    return modely


# Texty AI use statement v jazyku odpovede (nadpis sekcie zostáva „## AI use statement“)
_AI_TEXT = {
    "sk": {"modely": "Modely", "hlavny": "hlavný", "zalozny": "záložný {z} (použitý, lebo hlavný model vrátil 503 "
           "aj po opakovaní)", "agenti": "Agenti (5) a kroky", "nedok": "nedokončené", "ziadne": "žiadne",
           "orch": "Orchestrátor – kontrola rozsahu otázky a plánovanie: témy otázky ({temy}) a volania nástrojov",
           "zber": "Zber – nástroje nad pipeline.analytika, bez LLM", "analytik": "Analytik – zistenia Fact / "
           "Inference z výsledkov nástrojov", "reporter": "Reportér – správa BLUF", "oprava": ", raz opravená podľa "
           "kritika", "kritik": "Kritik – kontrola v kóde (sekcie, citácie podľa manifestu, mierka PHIA, čísla proti "
           "nástrojom, náhrady) a LLM", "korektura": "cielená oprava {n} riadkov", "kola": "Kolá opravy",
           "najviac": "najviac", "vysledok": "Výsledok kontroly", "volania": "Volania modelu", "poziadavky":
           "požiadaviek na Gemini vrátane opakovaní", "chyba": "Chyba behu", "clovek": "Ľudská kontrola",
           "clovek_t": "správa nie je overená (verified: false); overí ju človek podľa Case Logu",
           "preklad": "Preklad", "preklad_ok": "kritik kontroloval slovenskú verziu; do jazyka {j} ju preložil LLM "
           "({m}) a kód overil, že citácie, čísla, kódy a názvy liekov sa zhodujú",
           "preklad_sk": "preklad do jazyka {j} sa nepoužil ({d}); zobrazená je slovenská verzia",
           "nespustil": "kritik neprebehol", "ok_kor": "schválené po korektúre riadkov v {k}. kole (kontrola v kóde "
           "aj LLM)", "ok": "schválené v {k}. kole (kontrola v kóde aj LLM)", "nok": "neschválené – {a} problémov "
           "v kóde, {b} od LLM; zoznam je v Case Logu"},
    "cs": {"modely": "Modely", "hlavny": "hlavní", "zalozny": "záložní {z} (použit, protože hlavní model vrátil 503 "
           "i po opakování)", "agenti": "Agenti (5) a kroky", "nedok": "nedokončeno", "ziadne": "žádné",
           "orch": "Orchestrátor – kontrola rozsahu otázky a plánování: témata otázky ({temy}) a volání nástrojů",
           "zber": "Sběr – nástroje nad pipeline.analytika, bez LLM", "analytik": "Analytik – zjištění (fakta "
           "a úsudky) z výsledků nástrojů", "reporter": "Reportér – zpráva BLUF", "oprava": ", jednou opravená podle "
           "kritika", "kritik": "Kritik – kontrola v kódu (sekce, citace podle manifestu, škála PHIA, čísla proti "
           "nástrojům, náhrady) a LLM", "korektura": "cílená oprava {n} řádků", "kola": "Kola oprav",
           "najviac": "nejvýše", "vysledok": "Výsledek kontroly", "volania": "Volání modelu", "poziadavky":
           "požadavků na Gemini včetně opakování", "chyba": "Chyba běhu", "clovek": "Lidská kontrola",
           "clovek_t": "zpráva není ověřena (verified: false); ověří ji člověk podle Case Logu",
           "preklad": "Překlad", "preklad_ok": "kritik kontroloval slovenskou verzi; do češtiny ji přeložil LLM ({m}) "
           "a kód ověřil, že citace, čísla, kódy a názvy léčiv se shodují",
           "preklad_sk": "překlad do češtiny nebyl použit ({d}); zobrazena je slovenská verze",
           "nespustil": "kritik neproběhl", "ok_kor": "schváleno po korektuře řádků v {k}. kole (kontrola v kódu "
           "i LLM)", "ok": "schváleno v {k}. kole (kontrola v kódu i LLM)", "nok": "neschváleno – {a} problémů "
           "v kódu, {b} od LLM; seznam je v Case Logu"},
    "en": {"modely": "Models", "hlavny": "main", "zalozny": "fallback {z} (used because the main model returned 503 "
           "even after a retry)", "agenti": "Agents (5) and steps", "nedok": "not completed", "ziadne": "none",
           "orch": "Orchestrator – question scope check and planning: topics of the question ({temy}) and tool calls",
           "zber": "Collection – tools on top of pipeline.analytika, no LLM", "analytik": "Analyst – findings "
           "(facts and inferences) from the tool results", "reporter": "Reporter – BLUF report", "oprava": ", "
           "revised once after the critic's review", "kritik": "Critic – checks in code (sections, citations against "
           "the source manifest, PHIA scale, numbers against the tools, substitutes) and LLM", "korektura":
           "targeted correction of {n} lines", "kola": "Revision rounds", "najviac": "at most",
           "vysledok": "Review result", "volania": "Model calls", "poziadavky": "requests to Gemini including "
           "retries", "chyba": "Run error", "clovek": "Human review", "clovek_t": "the report is not verified "
           "(verified: false); a person will check it against the Case Log",
           "preklad": "Translation", "preklad_ok": "the critic reviewed the Slovak version; it was translated into "
           "English by an LLM ({m}) and the code verified that citations, numbers, codes and drug names match",
           "preklad_sk": "the English translation was not used ({d}); the Slovak version is shown",
           "nespustil": "critic did not run", "ok_kor": "approved after line corrections in round {k} (checks "
           "in code and LLM)", "ok": "approved in round {k} (checks in code and LLM)", "nok": "not approved – {a} "
           "problems in code, {b} from the LLM; see the Case Log"},
}
_TEMY = {"sk": KIQ_TEMA,
         "cs": {"KIQ1": "riziko výpadku", "KIQ2": "časový posun ČR–SR", "KIQ3": "náhrady", "KIQ4": "konkurenti",
                "KIQ5": "tržní mezery"},
         "en": {"KIQ1": "shortage risk", "KIQ2": "CZ–SK time lag", "KIQ3": "substitutes", "KIQ4": "competitors",
                "KIQ5": "market gaps"}}
_DOVOD_SK = {"vratene_sk": {"sk": "nezhoda údajov alebo neúplný preklad", "cs": "neshoda údajů nebo neúplný překlad",
                            "en": "data mismatch or incomplete translation"},
             "neschvalene": {"sk": "správa neprešla kontrolou", "cs": "zpráva neprošla kontrolou",
                             "en": "the report did not pass the review"},
             "vynechany": {"sk": "limit volaní alebo chyba modelu", "cs": "limit volání nebo chyba modelu",
                           "en": "call limit or model error"}}
_NAZOV_JAZYKA = {"cs": "CS", "en": "EN"}


def ai_use_statement(stav: dict, llm: LLM, nazov: str, jazyk: str = "sk") -> str:
    """AI use statement podľa skutočného priebehu (Case Logu) v jazyku odpovede – píše ho kód, nie model."""
    T = _AI_TEXT.get(jazyk, _AI_TEXT["sk"])
    log = stav.get("case_log", [])
    kritika = stav.get("kritika") or {}
    pocet_oprav = stav.get("pocet_oprav", 0)

    def model(agent: str) -> str:
        modely = _modely_agenta(log, agent)
        return " → ".join(modely) if modely else T["nedok"]

    zber = [z["nastroj"] for z in log if z["agent"] == "zber" and not z["vysledok"].startswith("vynechané")]
    nastroje = ", ".join(f"{n} ×{zber.count(n)}" if zber.count(n) > 1 else n for n in dict.fromkeys(zber))
    zalozny = llm.zalozny_model in llm.pouzite_modely
    typy_opravene = [typ for o in kritika.get("korektura") or [] for typ in o.get("typy", [])]
    korektura_popis = ", ".join(dict.fromkeys(kor.NAZVY_TYPOV[jazyk].get(typ, typ) for typ in typy_opravene))
    pocet_riadkov = len(kritika.get("korektura") or [])
    temy = ", ".join(_TEMY[jazyk].get(k, k) for k in (stav.get("plan") or {}).get("kiq", [])) or "–"
    if not kritika:
        vysledok = T["nespustil"]
    elif kritika.get("schvalene") and kritika.get("korektura"):
        vysledok = T["ok_kor"].format(k=kritika.get("kolo"))
    elif kritika.get("schvalene"):
        vysledok = T["ok"].format(k=kritika.get("kolo"))
    else:
        vysledok = T["nok"].format(a=len(kritika.get("problemy_kod", [])), b=len(kritika.get("problemy_llm", [])))
    riadky = [
        "## AI use statement",
        f"- **{T['modely']}:** {T['hlavny']} {llm.model}" + (f"; {T['zalozny'].format(z=llm.zalozny_model)}"
                                                           if zalozny else "") + ".",
        f"- **{T['agenti']}:**",
        f"  1. {T['orch'].format(temy=temy)} (LLM {model('orchestrátor')}).",
        f"  2. {T['zber']}: {nastroje or T['ziadne']}.",
        f"  3. {T['analytik']} (LLM {model('analytik')}).",
        f"  4. {T['reporter']}" + (T["oprava"] if pocet_oprav else "") + f" (LLM {model('reportér')}).",
        f"  5. {T['kritik']} ({model('kritik')})"
        + (f"; {T['korektura'].format(n=pocet_riadkov)} ({korektura_popis}, LLM {model('korektúra')})"
           if korektura_popis else "") + ".",
        f"- **{T['kola']}:** {pocet_oprav} ({T['najviac']} {MAX_OPRAV}).",
        f"- **{T['vysledok']}:** {vysledok}.",
    ]
    stav_prekladu = (stav.get("preklad") or {}).get("stav")
    if stav_prekladu == "ok":
        riadky.append(f"- **{T['preklad']}:** " + T["preklad_ok"].format(
            j=_NAZOV_JAZYKA.get(stav.get("jazyk"), ""), m=model("preklad")) + ".")
    elif stav_prekladu:
        riadky.append(f"- **{T['preklad']}:** " + T["preklad_sk"].format(
            j=_NAZOV_JAZYKA.get(stav.get("jazyk"), ""), d=_DOVOD_SK[stav_prekladu][jazyk]) + ".")
    riadky.append(f"- **{T['volania']}:** {llm.pocet_volani} ({T['poziadavky']} {llm.pocet_pokusov}).")
    if stav.get("chyba"):
        riadky.append(f"- **{T['chyba']}:** {stav['chyba']}")
    riadky.append(f"- **{T['clovek']}:** {T['clovek_t']} [[cases/{nazov}]].")
    return "\n".join(riadky)


def _nahrad_ai_use(brief: str, sekcia: str) -> str:
    """Nahradí sekciu AI use statement (po ďalší nadpis ##), alebo ju pridá na koniec."""
    riadky = brief.splitlines()
    i = next((k for k, r in enumerate(riadky) if re.match(r"^#{1,2}\s.*ai use", r, re.IGNORECASE)), None)
    if i is None:
        return brief.rstrip() + "\n\n" + sekcia
    j = next((k for k in range(i + 1, len(riadky)) if re.match(r"^#{1,2}\s", riadky[k])), len(riadky))
    return "\n".join(riadky[:i] + sekcia.splitlines() + ([""] if j < len(riadky) else []) + riadky[j:])


def _uloz(stav: dict, llm: LLM, zaciatok: str) -> tuple[dict, str]:
    """Uloží správu a Case Log. Vracia (cesty k súborom, správa s AI use statement z kódu)."""
    model, volania_llm, pokusy_llm = ", ".join(llm.pouzite_modely) or llm.model, llm.pocet_volani, llm.pocet_pokusov
    datum = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    reports, cases = VAULT / "reports", VAULT / "cases"
    reports.mkdir(parents=True, exist_ok=True)
    cases.mkdir(parents=True, exist_ok=True)
    zaklad = f"{datum}-{kratky_nazov(stav['otazka'])}"
    nazov = _volny_nazov([reports, cases], zaklad)
    kritika = stav.get("kritika") or {}
    schvalene = bool(kritika.get("schvalene"))
    otazka_yaml = stav["otazka"].replace('"', "'")
    subory = {}
    pacient = stav.get("rozsah") == "pacient"
    jazyk = stav.get("jazyk") or "sk"
    brief = ("" if pacient else _nahrad_ai_use(stav["brief"], ai_use_statement(stav, llm, nazov))
             if stav.get("brief") else "")

    if brief:
        poznamka = ""
        if not schvalene:
            zostava = kritika.get("problemy_kod", []) + kritika.get("problemy_llm", [])
            poznamka = ("\n\n---\n\n> **Kritik správu neschválil.** Zostávajúce problémy:\n"
                        + "\n".join(f"> - {p}" for p in zostava))
        sprava = (f"---\ntyp: sprava\notazka: \"{otazka_yaml}\"\npersona: {stav['persona']}\n"
                  f"vytvorene_utc: {_teraz_utc()}\nmodel: {model}\nkritik: "
                  f"{'schvalene' if schvalene else 'neschvalene'}\ncase_log: \"[[cases/{nazov}]]\"\n"
                  f"verified: false\n---\n\n{brief}{poznamka}\n")
        (reports / f"{nazov}.md").write_text(sprava, encoding="utf-8")
        subory["sprava"] = f"vault/reports/{nazov}.md"

    # odpoveď pre používateľa: pacient = pevný text; inak preklad (ak prešiel kontrolou), inak SK s poznámkou
    stav_prekladu = (stav.get("preklad") or {}).get("stav")
    if pacient:
        odpoved = stav.get("brief", "")
    elif jazyk != "sk" and stav_prekladu == "ok" and stav.get("brief_preklad"):
        odpoved = _nahrad_ai_use(stav["brief_preklad"], ai_use_statement(stav, llm, nazov, jazyk))
        (reports / f"{nazov}-{jazyk}.md").write_text(
            f"---\ntyp: sprava-preklad\njazyk: {jazyk}\npovodna: \"[[reports/{nazov}]]\"\nverified: false\n---\n\n"
            f"{odpoved}\n", encoding="utf-8")
        subory["preklad"] = f"vault/reports/{nazov}-{jazyk}.md"
    elif jazyk != "sk" and brief:
        odpoved = prekl.pridaj_do_bluf(brief, prekl.POZNAMKY[stav_prekladu or "vynechany"][jazyk])
    else:
        odpoved = brief

    plan = stav.get("plan") or {}
    kroky = "\n".join(_riadok_case_logu(z) for z in stav.get("case_log", []))
    kritik_text = "Kritik neprebehol."
    if kritika:
        kritik_text = (f"- výsledok: {'schválené' if schvalene else 'neschválené'} (kolo {kritika.get('kolo')}, "
                       f"opráv {stav.get('pocet_oprav', 0)})\n"
                       + "".join(f"- problém: {p}\n" for p in kritika.get("problemy_kod", []) + kritika.get("problemy_llm", []))
                       + "".join(f"- upozornenie: {u}\n" for u in kritika.get("upozornenia", [])))
    case = (f"---\ntyp: case-log\notazka: \"{otazka_yaml}\"\npersona: {stav['persona']}\n"
            f"zaciatok_utc: {zaciatok}\nkoniec_utc: {_teraz_utc()}\nmodel: {model}\n"
            f"volania_modelu: {volania_llm}\npoziadavky_na_model: {pokusy_llm}\nsprava: \"{'[[reports/' + nazov + ']]' if 'sprava' in subory else ''}\"\n"
            f"verified: false\n---\n\n"
            f"# Case Log – {stav['otazka']}\n\n"
            f"## Plán (orchestrátor)\n"
            f"- KIQ: {', '.join(plan.get('kiq', []))} · krajiny: {', '.join(plan.get('krajiny', []))} · "
            f"ATC prefix: {plan.get('atc_prefix') or '–'}\n"
            f"- zdôvodnenie: {_riadok(plan.get('zdovodnenie', '–'), 400)}\n"
            + "".join(f"- vyradené volanie: {v}\n" for v in plan.get("vyradene", []))
            + "".join(f"- úprava plánu v kóde: {u}\n" for u in plan.get("upravy", []))
            + f"- rozsah otázky: {stav.get('rozsah', 'ok')} · jazyk odpovede: {jazyk} (appka: "
              f"{stav.get('jazyk_appky') or '–'})"
            + (f" · preklad: {stav_prekladu}" if stav_prekladu else "") + "\n"
            + f"\n## Kroky agentov\n{kroky}\n\n"
            + ("\n## Rozsah\n- Otázka pacienta: vrátený pevný text (lekár, lekárnik, 155/112), bez nástrojov a bez "
               "ďalších volaní modelu; správa sa do vault/reports neukladá.\n" if pacient else "")
            + f"\n## Kritik\n{kritik_text}\n"
            + (f"\n## Chyba\n{stav['chyba']}\n" if stav.get("chyba") else "")
            + "\n## Bezpečnosť\n- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah "
              "z webu, žiadne osobné údaje.\n")
    (cases / f"{nazov}.md").write_text(case, encoding="utf-8")
    subory["case_log"] = f"vault/cases/{nazov}.md"
    return subory, odpoved


def spusti(otazka: str, persona: str, pri_kroku: Callable[[str], None] | None = None,
           jazyk: str | None = None) -> dict:
    """Spustí multiagentný systém pre jednu otázku.

    Vracia dict pre Streamlit: brief, priebeh, case_log (riadky), subory (cesty k správe a Case Logu),
    plan, kritika, schvalene, model (hlavný), modely (ktoré naozaj odpovedali), volania_llm, poziadavky_llm,
    chyba (None alebo zrozumiteľná správa). V správe je sekcia AI use statement doplnená kódom po kritikovi.
    `pri_kroku` (voliteľné) dostane každý nový riadok priebehu hneď, ako vznikne.
    `jazyk` (voliteľné, "sk" / "cs" / "en") je jazyk appky; jazyk otázky má prednosť. Agenti a kritik pracujú
    po slovensky, schválenú správu na konci preloží krok preklad. Navyše vracia: jazyk, rozsah, preklad.
    Pri otázke pacienta (rozsah "pacient") je brief pevný text bez modelu a správa sa neukladá.
    """
    persona = _normalizuj_personu(persona)
    zaciatok = _teraz_utc()
    try:
        llm = LLM()
    except LLMChyba as e:
        return {"brief": "", "priebeh": [f"Chyba: {e}"], "case_log": [], "subory": {}, "plan": {},
                "kritika": {}, "schvalene": False, "model": "", "volania_llm": 0, "chyba": str(e)}

    graf = vytvor_graf(llm)
    stav: dict = {"otazka": otazka, "persona": persona, "pocet_oprav": 0, "priebeh": [], "case_log": [],
                  "chyba": None, "jazyk_appky": jazyk if jazyk in JAZYKY else None, "jazyk": "sk", "rozsah": "ok"}
    zobrazene = 0
    for stav in graf.stream(stav, stream_mode="values"):
        if pri_kroku:
            for riadok in stav.get("priebeh", [])[zobrazene:]:
                pri_kroku(riadok)
        zobrazene = len(stav.get("priebeh", []))

    subory, brief = _uloz(stav, llm, zaciatok)
    kritika = stav.get("kritika") or {}
    return {
        "brief": brief,
        "priebeh": stav.get("priebeh", []),
        "case_log": [_riadok_case_logu(z) for z in stav.get("case_log", [])],
        "subory": subory,
        "plan": stav.get("plan", {}),
        "kritika": kritika,
        "schvalene": bool(kritika.get("schvalene")),
        "model": llm.model,
        "modely": llm.pouzite_modely,
        "volania_llm": llm.pocet_volani,
        "poziadavky_llm": llm.pocet_pokusov,
        "chyba": stav.get("chyba"),
        "jazyk": stav.get("jazyk", "sk"),
        "rozsah": stav.get("rozsah", "ok"),
        "preklad": stav.get("preklad") or {},
    }
