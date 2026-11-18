"""Krok „korektúra“: cielená oprava jednotlivých riadkov správy po oprave reportéra.

Ak po oprave reportéra zostanú v kontrole v kóde LEN problémy viazané na jeden riadok (cudzie znaky,
Key judgement bez PHIA alebo istoty, zlý začiatok úsudku, upozornenie v riadku úsudku, zlé označenie
riadku, prvé dve vety BLUF bez PHIA a istoty), jedno LLM volanie dostane len tieto riadky, popis problému
a mierku PHIA a vráti náhradné riadky. Kód ich vymení (zvyšok správy sa nemení) a znova spustí kontrolu
v kóde. Náhradný riadok musí mať rovnaké citácie, čísla a kódy liekov ako pôvodný – inak ho kód odmietne.

Úsudky nemajú citácie (AGENTS.md, sekcia 4): citácie z riadkov „**Úsudok:**“ v Discussion kód odstráni
deterministicky ešte pred kontrolou (odstran_citacie_z_usudkov).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# typ problému podľa začiatku správy z kontroly v kóde (agents.graph.kontrola_v_kode)
TYPY = [
    ("Znak „", "jazyk"), ("Znaky „", "jazyk"),
    ("Kľúčový úsudok bez výrazu z mierky PHIA", "kj_phia"),
    ("Úsudok nezačína", "usudok_zaciatok"),
    ("Upozornenie, že zámenu môže urobiť len lekár, nie je úsudok", "upozornenie_v_usudku"),
    ("Nepovolené označenie riadku", "oznacenie"),
    ("Prvé dve vety BLUF nemajú", "bluf"),
]
POPIS = {
    "jazyk": "obsahuje znaky, ktoré v slovenčine nie sú (ą, ę, ł, ś, ż, ć, ń, ő, ű) – napíš slová spisovne po slovensky",
    "kj_phia": "kľúčový úsudok nemá výraz z mierky PHIA – doplň jeden výraz z mierky a istotu (nízka/stredná)",
    "kj_istota": "kľúčový úsudok nemá istotu – doplň „istota: nízka“ alebo „istota: stredná“",
    "usudok_zaciatok": "text za „**Úsudok:**“ musí začínať „Odhadujeme…“ alebo výrazom z mierky PHIA",
    "upozornenie_v_usudku": "upozornenie o lekárovi nie je úsudok – riadok musí začínať „- **Upozornenie:**“",
    "oznacenie": "povolené označenia riadkov sú len **Fakt:**, **Úsudok:**, **Upozornenie:** (presne takto)",
    "bluf": "prvé dve vety BLUF musia obsahovať výraz z mierky PHIA a istotu (nízka/stredná); prvá veta ďalej "
            "priamo odpovedá na otázku",
}
NAZVY_TYPOV = {  # do AI use statement
    "sk": {"jazyk": "cudzie znaky", "kj_phia": "Key judgement bez PHIA", "kj_istota": "Key judgement bez istoty",
           "usudok_zaciatok": "začiatok úsudku", "upozornenie_v_usudku": "upozornenie v úsudku",
           "oznacenie": "označenie riadku", "bluf": "BLUF bez PHIA"},
    "cs": {"jazyk": "cizí znaky", "kj_phia": "Key judgement bez PHIA", "kj_istota": "Key judgement bez jistoty",
           "usudok_zaciatok": "začátek úsudku", "upozornenie_v_usudku": "upozornění v úsudku",
           "oznacenie": "označení řádku", "bluf": "BLUF bez PHIA"},
    "en": {"jazyk": "foreign characters", "kj_phia": "key judgement without PHIA",
           "kj_istota": "key judgement without confidence", "usudok_zaciatok": "start of an inference",
           "upozornenie_v_usudku": "warning inside an inference", "oznacenie": "line label",
           "bluf": "BLUF without PHIA"},
}

ROLA = """Si korektor správ LiekRadaru. Dostaneš niekoľko riadkov správy BLUF (po slovensky), pri každom číslo
riadku a problém, ktorý našla kontrola v kóde. Pre každý riadok vráť CELÝ opravený riadok.
Pravidlá:
- Oprav len uvedený problém, zvyšok riadku nechaj, ako je. Píš spisovne po slovensky.
- Citácie [ID, Admiralty], všetky čísla, kódy liekov, názvy liekov a sily nechaj bez zmeny – nič nepridávaj
  ani neuberaj (riadok s inými číslami alebo citáciami kód odmietne).
- Zachovaj začiatok riadku (odrážku „- “ a označenie **Fakt:**, **Úsudok:**, **Upozornenie:**), ak ho riadok má;
  pri zlom označení ho nahraď správnym.
- Pravdepodobnosť len výrazmi z mierky PHIA: zanedbateľná pravdepodobnosť, veľmi nepravdepodobné,
  nepravdepodobné, reálna možnosť, pravdepodobné (veľmi pravdepodobné a takmer isté bez nezávislého potvrdenia
  nepoužívaj). Istota: nízka alebo stredná (nie vysoká). Skóre rizika nie je pravdepodobnosť.
- Zakázané slová: preukazuje, dokazuje, eliminuje, isto.
- Vráť len opravy uvedených riadkov (číslo riadku + celý nový text v jednom riadku)."""


class OpravaRiadku(BaseModel):
    riadok: int = Field(description="číslo riadku zo vstupu")
    text: str = Field(description="celý opravený riadok (jeden riadok, bez zalomenia)")


class OpravyRiadkov(BaseModel):
    opravy: list[OpravaRiadku] = Field(default_factory=list)


def typ_problemu(problem: str) -> str | None:
    return next((typ for zaciatok, typ in TYPY if problem.startswith(zaciatok)), None)


def len_riadkove(problemy: list[str]) -> bool:
    """Všetky problémy z kontroly v kóde sa dajú opraviť výmenou jednotlivých riadkov."""
    return bool(problemy) and all(typ_problemu(p) for p in problemy)


# ---------------------------------------------------------------------------
# Riadky a ich problémy
# ---------------------------------------------------------------------------

def _sekcie_riadkov(riadky: list[str]) -> list[str]:
    """Pre každý riadok názov sekcie ## (malými písmenami), v ktorej je."""
    aktualna, vysledok = "", []
    for r in riadky:
        if re.match(r"^#{1,2}\s", r):
            aktualna = r.lstrip("#").strip().lower()
            vysledok.append("")
        else:
            vysledok.append(aktualna)
    return vysledok


def _zle_oznacenie(riadok: str) -> str | None:
    from agents import graph as g
    tucne, zname = g._OZNACENIE_TUCNE.match(riadok), g._OZNACENIE_ZNAME.match(riadok)
    oznacenie = tucne.group(1).strip() if tucne else (zname.group(0).strip(" -*+") if zname else None)
    if not oznacenie or re.sub(r"\s+", "", oznacenie) in g.POVOLENE_OZNACENIA:
        return None
    return oznacenie


def ciele(brief: str) -> list[dict]:
    """Riadky s problémami, ktoré sa dajú opraviť výmenou riadku: [{i, riadok, typy}] (i = index riadku)."""
    from agents import graph as g
    riadky = brief.splitlines()
    sekcie = _sekcie_riadkov(riadky)
    najdene: dict[int, list[str]] = {}

    def pridaj(i: int, typ: str) -> None:
        if typ not in najdene.setdefault(i, []):
            najdene[i].append(typ)

    prvy_bluf = None
    for i, (r, sekcia) in enumerate(zip(riadky, sekcie)):
        if not r.strip() or r.startswith("#"):
            continue
        if g._CUDZIE_ZNAKY.search(r):
            pridaj(i, "jazyk")
        if "key judgement" in sekcia and g._ODRAZKA.match(r):
            if not g.PHIA_VZOR.search(r):
                pridaj(i, "kj_phia")
            elif not g._ISTOTA.search(r):
                pridaj(i, "kj_istota")
        m = g._RIADOK_USUDOK.match(r)
        if m:
            zvysok = r[m.end():].lstrip("*_: ").lower()
            if "upozorň" in zvysok or ("zámen" in zvysok and "lekár" in zvysok):
                pridaj(i, "upozornenie_v_usudku")
            elif not g._ZACIATOK_USUDKU.match(zvysok):
                pridaj(i, "usudok_zaciatok")
        if sekcia.startswith("discussion") and _zle_oznacenie(r):
            pridaj(i, "oznacenie")
        if "bottom line" in sekcia and prvy_bluf is None:
            prvy_bluf = i
    if prvy_bluf is not None:
        dve = g._prve_vety(riadky[prvy_bluf], 2)
        if not (g.PHIA_VZOR.search(dve) and g._ISTOTA.search(dve)):
            pridaj(prvy_bluf, "bluf")
    return [{"i": i, "riadok": riadky[i], "typy": typy} for i, typy in sorted(najdene.items())]


def vstup_pre_model(otazka: str, ciele_: list[dict]) -> str:
    casti = [f"Otázka používateľa: {otazka}", "", "Riadky na opravu:"]
    for c in ciele_:
        problemy = "; ".join(POPIS[t] for t in c["typy"])
        casti.append(f"- riadok {c['i']}: {c['riadok']}\n  problém: {problemy}")
    return "\n".join(casti)


# ---------------------------------------------------------------------------
# Výmena riadkov
# ---------------------------------------------------------------------------

def _rovnake_udaje(povodny: str, novy: str) -> list[str]:
    """Citácie, čísla a kódy liekov musia v novom riadku zostať rovnaké."""
    from agents import preklad as p
    rozdiely = []
    for nazov, funkcia in [("citácie", p._citacie), ("čísla", p._cisla), ("kódy liekov", p._kody)]:
        rozdiel = p._rozdiel(funkcia(povodny), funkcia(novy))
        if rozdiel:
            rozdiely.append(f"{nazov}: {rozdiel.replace('v preklade', 'v novom riadku')}")
    return rozdiely


def pouzi_opravy(brief: str, ciele_: list[dict], opravy: OpravyRiadkov) -> tuple[str, list[dict], list[str]]:
    """Vymení prijaté riadky. Vracia (nová správa, prijaté opravy, odmietnuté s dôvodom)."""
    riadky = brief.splitlines()
    podla_indexu = {c["i"]: c for c in ciele_}
    prijate, odmietnute = [], []
    for o in opravy.opravy:
        ciel = podla_indexu.get(o.riadok)
        novy = re.sub(r"\s*\n\s*", " ", o.text or "").strip()
        if ciel is None:
            odmietnute.append(f"riadok {o.riadok}: nebol medzi riadkami na opravu")
            continue
        povodny = ciel["riadok"]
        if not novy:
            odmietnute.append(f"riadok {o.riadok}: prázdny text")
            continue
        if povodny.lstrip().startswith("- ") and not novy.startswith(("- ", "* ")):
            novy = "- " + novy
        rozdiely = _rovnake_udaje(povodny, novy)
        if rozdiely:
            odmietnute.append(f"riadok {o.riadok}: {'; '.join(rozdiely)}")
            continue
        if any(p["i"] == o.riadok for p in prijate):
            continue
        riadky[o.riadok] = novy
        prijate.append({"i": o.riadok, "typy": ciel["typy"], "pred": povodny, "po": novy})
    return "\n".join(riadky), prijate, odmietnute


# ---------------------------------------------------------------------------
# Úsudky bez citácií (AGENTS.md, sekcia 4)
# ---------------------------------------------------------------------------

def odstran_citacie_z_usudkov(brief: str) -> tuple[str, int]:
    """Z riadkov „**Úsudok:**“ v Discussion odstráni citácie [ID, Admiralty]. Vracia (správa, počet riadkov)."""
    from agents import graph as g
    riadky = brief.splitlines()
    sekcie = _sekcie_riadkov(riadky)
    pocet = 0
    for i, (r, sekcia) in enumerate(zip(riadky, sekcie)):
        if sekcia.startswith("discussion") and g._RIADOK_USUDOK.match(r) and g._SKUPINA.search(r):
            novy = g._SKUPINA.sub("", r)
            novy = re.sub(r"\s+([.,;:!?)])", r"\1", re.sub(r"[ \t]{2,}", " ", novy)).rstrip()
            riadky[i] = novy
            pocet += 1
    return "\n".join(riadky), pocet


# ---------------------------------------------------------------------------
# Námietky LLM kritika k tým istým riadkom (vybaví ich korektúra)
# ---------------------------------------------------------------------------

_KLUCOVE = {
    "kj_phia": r"key\s+judgement|kľúčov\w*\s+(úsud|zisten)|phia|istot|pravdepodobn",
    "kj_istota": r"key\s+judgement|kľúčov\w*\s+(úsud|zisten)|istot",
    "usudok_zaciatok": r"úsud\w*|odhadujeme|inference",
    "upozornenie_v_usudku": r"upozornen\w*|úsud\w*",
    "oznacenie": r"označen\w*|úsudek|\bfact\b|inference|label",
    "bluf": r"\bbluf\b|bottom\s+line|prv\w*\s+vet|úvod\w*\s+vet|phia|istot",
    "jazyk": r"pravopis|jazyk|poľ|po\s+česky|cudz\w*\s+(slov|znak)|preklep",
}


def _slova(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]{3,}", re.sub(r"\[[^\]]*\]|\*\*[^*]*\*\*", " ", text).lower())


def je_namietka_k_riadkom(problem: str, ciele_: list[dict]) -> bool:
    """Námietka LLM kritika sa týka niektorého z opravovaných riadkov: cituje z neho aspoň 4 slová po sebe,
    alebo hovorí o tom istom type problému (napr. Key judgement bez PHIA, začiatok úsudku, BLUF)."""
    p = " ".join(_slova(problem))
    for c in ciele_:
        slova = _slova(c["riadok"])
        if any(" ".join(slova[k:k + 4]) in p for k in range(max(len(slova) - 3, 0))):
            return True
        if any(re.search(_KLUCOVE[t], problem, re.IGNORECASE) for t in c["typy"]):
            return True
    return False


def je_namietka_k_citaciam_usudkov(problem: str) -> bool:
    """Námietka k citáciám v úsudkoch (chýbajúcim aj nadbytočným) – úsudky sú podľa AGENTS.md bez citácií."""
    return bool(re.search(r"úsud\w*.{0,80}(citáci|zdroj|\[e00)|(citáci|zdroj)\w*.{0,80}úsud", problem,
                          re.IGNORECASE))


# ---------------------------------------------------------------------------
# Pevné opravy pre režim LIEKRADAR_FAKE_LLM
# ---------------------------------------------------------------------------

def fake_opravy(ciele_: list[dict]) -> OpravyRiadkov:
    from agents import graph as g
    opravy = []
    for c in ciele_:
        r = c["riadok"]
        for typ in c["typy"]:
            if typ == "jazyk":
                r = g._CUDZIE_SLOVO.sub(lambda m: g.navrh_slovensky(m.group(0)), r)
            elif typ == "kj_phia":
                r = r.rstrip(" .…") + " – reálna možnosť, istota: stredná."
            elif typ == "kj_istota":
                r = r.rstrip(" .…") + ", istota: stredná."
            elif typ == "usudok_zaciatok":
                m = g._RIADOK_USUDOK.match(r)
                zvysok = r[m.end():].lstrip("*_: ")
                r = r[:m.end()].rstrip() + " Odhadujeme, že " + zvysok[:1].lower() + zvysok[1:]
            elif typ == "upozornenie_v_usudku":
                r = g._RIADOK_USUDOK.sub("- **Upozornenie:** ", r, count=1)
            elif typ == "oznacenie":
                zle = _zle_oznacenie(r)
                spravne = g._SPRAVNE_OZNACENIE.get(re.sub(r"[*_:\s]", "", zle or "").lower(), "**Úsudok:**")
                r = r.replace(zle, spravne, 1) if zle else r
            elif typ == "bluf":
                vety = g._vety(r)
                vety.insert(1 if vety else 0, "Ďalší výpadok je reálna možnosť (istota: stredná).")
                r = " ".join(vety)
        opravy.append(OpravaRiadku(riadok=c["i"], text=r))
    return OpravyRiadkov(opravy=opravy)
