"""Multiagentný systém LiekRadar (LangGraph + Gemini).

Graf kopíruje cyklus competitive intelligence:

    orchestrátor (plánovanie, LLM) -> zber (bez LLM) -> analytik (analýza, LLM)
        -> reportér (šírenie, LLM) -> kritik (kontrola v kóde + LLM)
                                        └─ neschválené -> reportér (najviac 1 oprava)

Systémový prompt každého agenta = vault/AGENTS.md + krátky popis jeho roly.
Čísla počítajú len nástroje z agents.tools (obaly nad pipeline.analytika), nie model.
Na jednu otázku najviac 6 volaní modelu: orchestrátor, analytik, reportér, kritik
a pri oprave ešte reportér a kritik.

Použitie:
    from agents.graph import spusti
    vysledok = spusti("Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?", "lekaren")
"""

from __future__ import annotations

import csv
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

from agents import tools
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
    "vyrobca": "výrobca generík / distribútor – hľadá príležitosti, konkurentov a trhové medzery (KIQ4, KIQ5, "
               "doplnkovo KIQ1 a KIQ2)",
    "lekaren": "nákupca lekárenskej siete – sleduje riziká výpadkov, náhrady a potrebu predzásobenia (KIQ1, KIQ3, "
               "doplnkovo KIQ2)",
}

KIQ_POPIS = {
    "KIQ1": "riziko výpadku – ktoré lieky bez nahláseného výpadku majú najvyššie skóre rizika",
    "KIQ2": "časový posun – či výpadok v jednej krajine predchádza výpadku v druhej",
    "KIQ3": "náhrady – čím nahradiť liek vo výpadku v tej istej krajine",
    "KIQ4": "konkurenti – výrobcovia v skupine ATC, ich výpadky a podiel na dodávkach",
    "KIQ5": "trhové medzery – látky s dlhým výpadkom a málo dodávateľmi",
}

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


class Volanie(BaseModel):
    nastroj: Literal["top_rizikove", "detail_latky", "posun_latky", "nahrady", "konkurenti", "trhove_medzery"]
    krajina: Optional[Literal["CZ", "SK"]] = Field(None, description="CZ alebo SK")
    atc_prefix: Optional[str] = Field(None, description="začiatok ATC kódu, napr. J01 alebo J01C")
    atc: Optional[str] = Field(None, description=f"ATC7 látky, napr. J01CR02, alebo '{ZASTUPCA}'")
    kod: Optional[str] = Field(None, description=f"kód lieku SÚKL/ŠÚKL, alebo '{ZASTUPCA}'")
    n: Optional[int] = Field(None, description="počet riadkov, najviac 10")
    preco: str = Field("", description="jedna veta, prečo toto volanie")


class Plan(BaseModel):
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


def zakladny_plan(otazka: str, persona: str) -> Plan:
    """Plán bez modelu: z otázky vyberie ATC prefix a krajiny, nástroje podľa persony.
    Používa ho režim LIEKRADAR_FAKE_LLM a záloha, keď model navrhne len neplatné volania."""
    atc = re.search(r"\b([A-Z]\d{2}(?:[A-Z]{1,2}(?:\d{2})?)?)\b", otazka)
    atc_prefix = atc.group(1) if atc else None
    t = otazka.lower()
    krajiny = []
    if "česk" in t or "čr" in re.findall(r"\b\w+\b", t) or re.search(r"\bCZ\b", otazka):
        krajiny.append("CZ")
    if "sloven" in t or re.search(r"\b(SR|SK)\b", otazka):
        krajiny.append("SK")
    krajiny = krajiny or ["CZ", "SK"]
    volania: list[Volanie] = []
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
    return Plan(kiq=kiq, krajiny=krajiny, atc_prefix=atc_prefix,
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


def _prva_veta(text: str) -> str:
    """Prvá veta prvého neprázdneho odseku. Bodka po iniciále (B. Braun), po skratke (napr.)
    alebo vnútri slova (s.r.o.) vetu nekončí."""
    odsek = next((o.strip() for o in re.split(r"\n\s*\n", text) if o.strip()), "")
    for m in re.finditer(r"[.!?](?=\s+\S)", odsek):
        slovo = re.search(r"(\S+)$", odsek[: m.start()])
        slovo = re.sub(r"^[*_(\[]+", "", slovo.group(1)) if slovo else ""
        if len(slovo) <= 1 or "." in slovo or slovo.lower() in _SKRATKY:
            continue
        return odsek[: m.end()]
    return odsek
_RIADOK_FAKT = re.compile(r"^\s*(?:[-*+]|\d+\.)?\s*[*_]*\s*(fakt|fact)\b", re.IGNORECASE)
_RIADOK_USUDOK = re.compile(r"^\s*(?:[-*+]|\d+\.)?\s*[*_]*\s*(úsudok|inference)\b[*_:\s]*", re.IGNORECASE)
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
_INA_FORMA = re.compile(r"\bin\w*\s+(?:liekov\w*\s+)?form\w*", re.IGNORECASE)


def nahrady_inej_formy(data: dict) -> list[dict]:
    """Kandidáti z nástroja nahrady, ktorí majú inú liekovú formu ako pôvodný liek, a vzory
    (kód, názov), podľa ktorých ich nájdeme v správe."""
    vysledok = []
    for z in data.values():
        v = z.get("vysledok") or {}
        if z.get("nastroj") != "nahrady" or "povodny_liek" not in v:
            continue
        povodny, zaznamy = v["povodny_liek"], v.get("zaznamy", [])
        rovnake = [str(r.get("nazov") or "") for r in zaznamy if r.get("rovnaka_forma")] + [str(povodny["nazov"] or "")]
        for r in zaznamy:
            if r.get("rovnaka_forma"):
                continue
            vzory = [str(r["kod"])]
            slova = str(r.get("nazov") or "").split()
            for i in range(1, min(len(slova), 3) + 1):  # najkratší začiatok názvu, ktorý nemá liek rovnakej formy
                predpona = " ".join(slova[:i]).lower()
                if not any(n.lower().startswith(predpona) for n in rovnake):
                    vzory.append(" ".join(slova[:i]))
                    break
            vysledok.append({"kod": r["kod"], "nazov": r.get("nazov"), "forma": r.get("forma"),
                             "povodna_forma": povodny["forma"], "povodny": povodny["nazov"], "vzory": vzory})
    return vysledok


def kontrola_v_kode(brief: str, data: dict, manifest: dict) -> tuple[list[str], list[str]]:
    """Pravidlá z AGENTS.md (a z pokynov tímu), ktoré sa dajú overiť bez modelu.
    `data` sú výsledky nástrojov zo stavu grafu. Vracia (problémy, ktoré blokujú schválenie; upozornenia)."""
    problemy, upozornenia = [], []
    data_json = _json(data)
    ine_formy = nahrady_inej_formy(data)
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

    # 3. Každý fakt má citáciu (kdekoľvek v riadku), každý úsudok začína „Odhadujeme…“ / „Pravdepodobne…“
    for r in brief.splitlines():
        if _RIADOK_FAKT.match(r) and not citacie(r):
            problemy.append(f"Fakt bez citácie [ID, Admiralty]: „{_riadok(r, 120)}“")
        m = _RIADOK_USUDOK.match(r)
        if m:
            zvysok = r[m.end():].lstrip("*_: ").lower()
            if "upozorň" in zvysok or ("zámen" in zvysok and "lekár" in zvysok):
                problemy.append("Upozornenie, že zámenu môže urobiť len lekár, nie je úsudok – napíš ho ako "
                                f"samostatný riadok „- **Upozornenie:** …“: „{_riadok(r, 100)}“")
            elif not (zvysok.startswith("odhadujeme") or zvysok.startswith("pravdepodobne")):
                problemy.append(f"Úsudok nezačína „Odhadujeme…“ ani „Pravdepodobne…“: „{_riadok(r, 120)}“")

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

    # 5b. BLUF: prvá veta má výraz z mierky PHIA aj istotu
    bluf = next((t for n, t in sekcie.items() if "bottom line" in n), "")
    prva = _prva_veta(bluf)
    if bluf and not (PHIA_VZOR.search(prva) and _ISTOTA.search(prva)):
        chyba = " a ".join(x for x, ok in [("výraz z mierky PHIA", PHIA_VZOR.search(prva)),
                                           ("istotu (nízka/stredná)", _ISTOTA.search(prva))] if not ok)
        problemy.append(f"Prvá veta BLUF nemá {chyba}: „{_riadok(prva, 120)}“")

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
            if not any(v.lower() in r.lower() for v in kandidat["vzory"]):
                continue
            if not (_INA_FORMA.search(r) and "lekár" in r.lower()):
                problemy.append(f"{kandidat['nazov']} ({kandidat['kod']}) má inú liekovú formu ({kandidat['forma']}) "
                                f"ako {kandidat['povodny']} ({kandidat['povodna_forma']}); uveď ho najviac ako "
                                f"„iná forma, len po posúdení lekárom“: „{_riadok(r, 90)}“")
                break

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


def _fake_nahrady(stav: Stav) -> list[str]:
    """Náhrady podľa liekovej formy (rovnaká forma = náhrada, iná forma = len po posúdení lekárom)."""
    riadky = []
    for z in stav.get("data", {}).values():
        v = z.get("vysledok") or {}
        if z["nastroj"] != "nahrady" or "povodny_liek" not in v:
            continue
        p, zaznamy = v["povodny_liek"], v.get("zaznamy", [])
        zdroj = (v.get("spolocne") or {}).get("zdroj", p["zdroj"])
        rovnake = ", ".join(f"{r['nazov']} ({r['kod']})" for r in zaznamy if r.get("rovnaka_forma"))
        ine = ", ".join(f"{r['nazov']} ({r['kod']}, {r['forma']})" for r in zaznamy if not r.get("rovnaka_forma"))
        if rovnake:
            riadky.append(f"- **Fakt:** Náhrady za {p['nazov']} ({p['kod']}, {p['forma']}) s rovnakou formou: "
                          f"{rovnake} {zdroj}")
        if ine:
            riadky.append(f"- **Fakt:** Iná forma, len po posúdení lekárom: {ine} {zdroj}")
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
        "Odhadujeme, že pri liekoch s najvyšším skóre je ďalší výpadok reálna možnosť (istota: nízka). "
        f"Testovacia správa (LIEKRADAR_FAKE_LLM=1) pre personu {persona}.",
        "",
        "## Key judgements",
        "- Odhadujeme, že najrizikovejšie lieky z tabuľky KIQ1 čaká výpadok – reálna možnosť, istota: nízka.",
        "",
        "## Discussion",
        *fakty,
        *_fake_nahrady(stav),
        "- **Úsudok:** Odhadujeme, že skóre je len poradie liekov, nie pravdepodobnosť.",
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
        "- Nové hlásenia o prerušení dodávok rovnakého výrobcu v druhej krajine.",
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
- Ak otázka nespomína krajinu, ber obe (CZ aj SK)."""

PRAVIDLO_ISTOTY = """- Skóre rizika aj historické súbehy výpadkov (CZ–SK) sú SIGNÁLY, nie dôkaz. Bez nezávislého potvrdenia
  (zdroj W… v Case Logu, v tomto behu žiadny nie je) je pravdepodobnosť najviac „pravdepodobné“ a istota
  najviac stredná. Nepoužívaj „veľmi pravdepodobné“, „takmer isté“ ani vysokú istotu.
- Zakázané slová: preukazuje, dokazuje, eliminuje, isto (ani ich tvary ako „preukázateľne“, „eliminovať“)."""

PRAVIDLO_NAHRAD = """- Náhrady (nástroj nahrady): ako náhradu uveď LEN lieky s `rovnaka_forma: true`, teda s rovnakou liekovou
  formou ako `povodny_liek.forma` (stĺpec `forma`). Lieky inej formy (napr. IMP, TBL, SOL IJF namiesto SOL INF)
  uveď najviac v samostatnej odrážke s textom „iná forma, len po posúdení lekárom“ a s ich formou."""

ROLA_ANALYTIK = f"""Si **analytik** (fáza CI: analýza). Z výsledkov nástrojov (JSON) urob zistenia k otázke.
- Čísla ber LEN z výsledkov nástrojov, nič neodhaduj ani neprepočítavaj z pamäte.
- Fakty a úsudky píš oddelene:
  `## Zistenia (Fact)` – odrážky „- Fakt: … [ID, Admiralty]“; citáciu prevezmi z poľa `zdroj`, `zdroje`
  alebo z textu `dovody` daného záznamu. Každý zdroj zvlášť: [E001, A2] [E005, A2].
  `## Úsudky (Inference)` – odrážky začínajú „Odhadujeme…“ alebo „Pravdepodobne…“, pravdepodobnosť len
  výrazom z mierky PHIA, istota nízka alebo stredná.
  `## Medzery v dátach` – čo nástroje nepokryli.
- Skóre rizika 0–100 je poradie liekov z modelu, nie pravdepodobnosť; nikdy ho neprepočítavaj na percentá.
{PRAVIDLO_ISTOTY}
{PRAVIDLO_NAHRAD}
- Zohľadni personu: výrobca hľadá príležitosti a konkurentov, lekáreň riziká, náhrady a predzásobenie.
- Píš po slovensky, stručne (najviac ~25 odrážok)."""

ROLA_REPORTER = f"""Si **reportér** (fáza CI: šírenie). Napíš správu BLUF po slovensky podľa sekcie 8 AGENTS.md.
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
- BLUF: 2–4 vety, odpoveď na otázku pre danú personu. PRVÁ VETA obsahuje výraz z mierky PHIA a istotu, napr.
  „Odhadujeme, že výpadok infúznych antibiotík B. Braun na Slovensku je reálna možnosť (istota: stredná).“
- Key judgements: 2–4 odrážky, každá s výrazom z mierky PHIA a istotou (nízka/stredná).
- Discussion: odrážky „- **Fakt:** … [ID, Admiralty]“ a „- **Úsudok:** Odhadujeme…/Pravdepodobne…“ oddelene.
  Čísla len z výsledkov nástrojov a zistení analytika. Skóre rizika je poradie 0–100, nie pravdepodobnosť,
  nikdy ho nepíš v percentách.
- Citácie: každý zdroj v samostatnej zátvorke – [E001, A2] [E005, A2], nikdy zlúčene [E001, A2, E005, A2].
{PRAVIDLO_ISTOTY}
{PRAVIDLO_NAHRAD}
- Čísla prepisuj presne zo záznamu TOHO lieku, o ktorom píšeš: skóre z top_rizikove (body bez jednotky),
  kód a balenie (pole `doplnok`, napr. „20x80 ml/240 mg“) z toho istého záznamu, počty vĺn, dni posunu
  a počty prípadov z posun_latky danej látky. Balenie iného kódu (iná veľkosť) nikdy nepripisuj inému kódu.
- Ak spomínaš náhrady, na konci Discussion pridaj samostatný riadok
  „- **Upozornenie:** Zámenu inej látky alebo liekovej formy môže urobiť len lekár; správa nie je odporúčanie
  pre pacientov.“ Upozornenie nie je fakt ani úsudok – nepíš ho do riadku „Úsudok“. Žiadne odporúčania pacientom.
- Sources and method annex: použité zdroje [ID, Admiralty] s názvom zo zoznamu zdrojov a nástroje.
- AI use statement: napíš len nadpis a vetu „Doplní systém po kontrole kritikom.“ – agentov, modely,
  kolá opravy a výsledok kontroly doplní kód.
- Vráť len markdown správy, bez úvodu a bez ``` blokov."""

ROLA_KRITIK = f"""Si **kritik** (kontrola kvality, Lint podľa AGENTS.md). Posúď správu BLUF:
1. Tvrdenia o faktoch majú citáciu a ich čísla sa dajú nájsť vo výsledkoch nástrojov.
2. Fakty a úsudky sú oddelené; úsudky začínajú „Odhadujeme…“ alebo „Pravdepodobne…“.
3. Pravdepodobnosť je len výrazom z mierky PHIA; skóre rizika nie je prepočítané na percentá ani
   vydávané za pravdepodobnosť. Prvá veta BLUF má výraz PHIA aj istotu.
4. Žiadne lekárske odporúčania pacientom; pri náhradách je uvedené, že zámenu urobí len lekár.
5. Správa odpovedá na otázku pre danú personu a nič si nevymýšľa.
{PRAVIDLO_ISTOTY}
{PRAVIDLO_NAHRAD}
Formálnu kontrolu citácií (tvar, ID a známka podľa manifestu, citácia pri každom fakte) a čísel (skóre, kódy
a balenia liekov, vlny a dni posunu) robí kód; ak kód nehlási problém s citáciami, nevracaj správu pre ich
formát. Sekciu AI use statement doplní systém po kontrole, jej obsah neposudzuj. Riadok „Upozornenie:“
nie je úsudok. Problémy z kódu dostaneš – ber ich ako
fakty. Schváľ (schvalene=true) len ak nie je žiadny vážny problém. Problémy píš konkrétne a stručne
po slovensky (čo a kde opraviť)."""


def _data_pre_model(stav: Stav) -> str:
    return _json({k: {"nastroj": z["nastroj"], "kiq": z["kiq"], "argumenty": z["argumenty"],
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

    def orchestrator(stav: Stav) -> dict:
        persona = stav["persona"]
        vstup = (f"Otázka: {stav['otazka']}\nPersona: {persona} – {PERSONY[persona]}\n"
                 "Navrhni plán (KIQ, krajiny, ATC prefix, volania nástrojov).")
        try:
            plan = llm.strukturovane(system["orchestrator"], vstup, Plan,
                                     fake=zakladny_plan(stav["otazka"], persona))
        except LLMChyba as e:
            return {"chyba": str(e), "priebeh": [f"Orchestrátor: chyba – {e}"],
                    "case_log": [_zaznam("orchestrátor", nastroj_llm(), "otázka + persona", f"CHYBA: {e}")]}
        volania, vyradene = over_plan(plan)
        poznamka = ""
        if not volania:
            plan = zakladny_plan(stav["otazka"], persona)
            volania, _ = over_plan(plan)
            poznamka = " Model nenavrhol platné volania, použitý základný plán."
        plan_dict = {"kiq": plan.kiq, "krajiny": plan.krajiny, "atc_prefix": plan.atc_prefix,
                     "zdovodnenie": plan.zdovodnenie, "volania": volania, "vyradene": vyradene}
        zoznam = ", ".join(f"{v['nastroj']}({', '.join(map(str, v['argumenty'].values()))})" for v in volania)
        log = [_zaznam("orchestrátor", nastroj_llm(), f"otázka: {stav['otazka']} · persona: {persona}",
                       f"KIQ {', '.join(plan.kiq)} · krajiny {', '.join(plan.krajiny)} · volania: {zoznam}"
                       + (f" · vyradené: {'; '.join(vyradene)}" if vyradene else "") + poznamka)]
        return {"plan": plan_dict, "case_log": log,
                "priebeh": [f"Orchestrátor (plánovanie): {', '.join(plan.kiq)} · {', '.join(plan.krajiny)}"
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
                 f"Plán: {_json({k: stav['plan'][k] for k in ('kiq', 'krajiny', 'atc_prefix', 'zdovodnenie')})}\n\n"
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
        brief = stav.get("brief", "")
        data_json = _data_pre_model(stav)
        problemy_kod, upozornenia = kontrola_v_kode(brief, stav.get("data", {}), manifest)
        log = [_zaznam("kritik", "kontrola v kóde", f"správa {len(brief)} znakov",
                       f"{len(problemy_kod)} problémov, {len(upozornenia)} upozornení"
                       + (f": {problemy_kod[0]}" if problemy_kod else ""))]
        problemy_llm, llm_schvalil, poznamka = [], True, ""
        if llm.pocet_volani < MAX_VOLANI_NA_OTAZKU:
            vstup = (f"Otázka: {stav['otazka']}\nPersona: {stav['persona']}\n\n"
                     f"Kontrola v kóde – problémy: {_json(problemy_kod)}; upozornenia: {_json(upozornenia)}\n\n"
                     f"Výsledky nástrojov (JSON):\n{data_json}\n\nSpráva na posúdenie:\n{brief}")
            try:
                posudok = llm.strukturovane(system["kritik"], vstup, Posudok, fake=Posudok(schvalene=True))
                problemy_llm, llm_schvalil = list(posudok.problemy), bool(posudok.schvalene)
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
        if schvalene:
            verdikt = "schválené"
        elif pocet_oprav < MAX_OPRAV:
            verdikt = "vrátené reportérovi na opravu"
        else:
            verdikt = "neschválené ani po oprave – správa sa uloží s poznámkou"
        kritika = {"schvalene": schvalene, "problemy_kod": problemy_kod, "problemy_llm": problemy_llm,
                   "upozornenia": upozornenia, "kolo": pocet_oprav + 1}
        detail = "; ".join((problemy_kod + problemy_llm)[:3])
        return {"kritika": kritika, "case_log": log,
                "priebeh": [f"Kritik (kontrola): {verdikt} – {len(problemy_kod)} problémov v kóde, "
                            f"{len(problemy_llm)} od LLM{poznamka}" + (f". {detail}" if detail else "")]}

    def po_kritikovi(stav: Stav) -> str:
        if stav.get("chyba"):
            return END
        if not stav["kritika"]["schvalene"] and stav.get("pocet_oprav", 0) < MAX_OPRAV:
            return "reporter"
        return END

    def dalej(cielovy: str) -> Callable[[Stav], str]:
        return lambda stav: END if stav.get("chyba") else cielovy

    g = StateGraph(Stav)
    for nazov, uzol in [("orchestrator", so_zaloznym(orchestrator)), ("zber", zber),
                        ("analytik", so_zaloznym(analytik)), ("reporter", so_zaloznym(reporter)),
                        ("kritik", so_zaloznym(kritik))]:
        g.add_node(nazov, uzol)
    g.add_edge(START, "orchestrator")
    g.add_conditional_edges("orchestrator", dalej("zber"), ["zber", END])
    g.add_edge("zber", "analytik")
    g.add_conditional_edges("analytik", dalej("reporter"), ["reporter", END])
    g.add_conditional_edges("reporter", dalej("kritik"), ["kritik", END])
    g.add_conditional_edges("kritik", po_kritikovi, ["reporter", END])
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


def ai_use_statement(stav: dict, llm: LLM, nazov: str) -> str:
    """AI use statement podľa skutočného priebehu (Case Logu) – píše ho kód, nie model."""
    log = stav.get("case_log", [])
    kritika = stav.get("kritika") or {}
    pocet_oprav = stav.get("pocet_oprav", 0)

    def model(agent: str) -> str:
        modely = _modely_agenta(log, agent)
        return " → ".join(modely) if modely else "nedokončené"

    zber = [z["nastroj"] for z in log if z["agent"] == "zber" and not z["vysledok"].startswith("vynechané")]
    nastroje = ", ".join(f"{n} ×{zber.count(n)}" if zber.count(n) > 1 else n for n in dict.fromkeys(zber))
    zalozny = llm.zalozny_model in llm.pouzite_modely
    if not kritika:
        vysledok = "kritik neprebehol"
    elif kritika.get("schvalene"):
        vysledok = f"schválené v {kritika.get('kolo')}. kole (kontrola v kóde aj LLM)"
    else:
        vysledok = (f"neschválené – {len(kritika.get('problemy_kod', []))} problémov v kóde, "
                    f"{len(kritika.get('problemy_llm', []))} od LLM; zoznam je na konci správy a v Case Logu")
    riadky = [
        "## AI use statement",
        f"- **Modely:** hlavný {llm.model}" + (f"; záložný {llm.zalozny_model} (použitý, lebo hlavný model "
                                               "vrátil 503 aj po opakovaní)" if zalozny else "") + ".",
        "- **Agenti (5) a kroky:**",
        f"  1. Orchestrátor – plánovanie: KIQ a volania nástrojov (LLM {model('orchestrátor')}).",
        f"  2. Zber – nástroje nad pipeline.analytika, bez LLM: {nastroje or 'žiadne'}.",
        f"  3. Analytik – zistenia Fact / Inference z výsledkov nástrojov (LLM {model('analytik')}).",
        f"  4. Reportér – správa BLUF" + (", raz opravená podľa kritika" if pocet_oprav else "")
        + f" (LLM {model('reportér')}).",
        f"  5. Kritik – kontrola v kóde (sekcie, citácie podľa manifestu, mierka PHIA, čísla proti nástrojom, "
        f"náhrady) a LLM ({model('kritik')}).",
        f"- **Kolá opravy:** {pocet_oprav} (najviac {MAX_OPRAV}).",
        f"- **Výsledok kontroly:** {vysledok}.",
        f"- **Volania modelu:** {llm.pocet_volani} (požiadaviek na Gemini vrátane opakovaní {llm.pocet_pokusov}).",
    ]
    if stav.get("chyba"):
        riadky.append(f"- **Chyba behu:** {stav['chyba']}")
    riadky.append(f"- **Ľudská kontrola:** správa nie je overená (verified: false); overí ju človek podľa "
                  f"Case Logu [[cases/{nazov}]].")
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
    brief = _nahrad_ai_use(stav["brief"], ai_use_statement(stav, llm, nazov)) if stav.get("brief") else ""

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
            + f"\n## Kroky agentov\n{kroky}\n\n"
            f"## Kritik\n{kritik_text}\n"
            + (f"\n## Chyba\n{stav['chyba']}\n" if stav.get("chyba") else "")
            + "\n## Bezpečnosť\n- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah "
              "z webu, žiadne osobné údaje.\n")
    (cases / f"{nazov}.md").write_text(case, encoding="utf-8")
    subory["case_log"] = f"vault/cases/{nazov}.md"
    return subory, brief


def spusti(otazka: str, persona: str, pri_kroku: Callable[[str], None] | None = None) -> dict:
    """Spustí multiagentný systém pre jednu otázku.

    Vracia dict pre Streamlit: brief, priebeh, case_log (riadky), subory (cesty k správe a Case Logu),
    plan, kritika, schvalene, model (hlavný), modely (ktoré naozaj odpovedali), volania_llm, poziadavky_llm,
    chyba (None alebo zrozumiteľná správa). V správe je sekcia AI use statement doplnená kódom po kritikovi.
    `pri_kroku` (voliteľné) dostane každý nový riadok priebehu hneď, ako vznikne.
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
                  "chyba": None}
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
    }
