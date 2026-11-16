"""Preklad schválenej správy do češtiny alebo angličtiny a kontrola zhody s originálom.

Agenti pracujú a kritik kontroluje po slovensky. Až schválenú správu preloží krok „preklad“ (1 LLM volanie).
- Nadpisy sekcií ## a označenia **Fakt:**, **Úsudok:**, **Upozornenie:** zostávajú presne po slovensky
  (appka ich takto hľadá a sama prekladá).
- Výrazy z mierky PHIA a istota sa prekladajú podľa pevnej tabuľky.
- Kód po preklade overí, že nadpisy, označenia, citácie [ID, Admiralty], čísla, kódy liekov a názvy liekov
  sú rovnaké ako v slovenskej verzii. Ak nie, použije sa slovenská verzia s poznámkou.
"""

from __future__ import annotations

import os
import re
from collections import Counter

from agents.kontrola_cisel import _kody_v_riadku

NAZVY_JAZYKOV = {"cs": "češtiny", "en": "angličtiny"}
OZNACENIA = ("**Fakt:**", "**Úsudok:**", "**Upozornenie:**")

# (vzor slovenského výrazu v ľubovoľnom tvare, preklad) – poradie: dlhšie výrazy skôr
PHIA_TABULKA = {
    "cs": [
        (r"zanedbateľn\w*\s+pravdepodobnos\w*", "zanedbatelná pravděpodobnost"),
        (r"veľmi\s+nepravdepodobn\w*", "velmi nepravděpodobné"),
        (r"veľmi\s+pravdepodobn\w*", "velmi pravděpodobné"),
        (r"takmer\s+ist\w*", "téměř jisté"),
        (r"nepravdepodobn\w*", "nepravděpodobné"),
        (r"reáln\w*\s+možnos\w*", "reálná možnost"),
        (r"pravdepodobn\w*", "pravděpodobné"),
    ],
    "en": [
        (r"zanedbateľn\w*\s+pravdepodobnos\w*", "remote chance"),
        (r"veľmi\s+nepravdepodobn\w*", "highly unlikely"),
        (r"veľmi\s+pravdepodobn\w*", "highly likely"),
        (r"takmer\s+ist\w*", "almost certain"),
        (r"nepravdepodobn\w*", "unlikely"),
        (r"reáln\w*\s+možnos\w*", "realistic possibility"),
        (r"pravdepodobn\w*", "likely"),
    ],
}
ISTOTA_TABULKA = {
    "cs": {"istota": "jistota", "nízka": "nízká", "stredná": "střední", "vysoká": "vysoká"},
    "en": {"istota": "confidence", "nízka": "low", "stredná": "moderate", "vysoká": "high"},
}
# podľa čoho poznáme výraz PHIA v preklade (kontrola, či preklad tabuľku dodržal; len upozornenie)
PHIA_V_PREKLADE = {
    "cs": r"zanedbateln\w*\s+pravděpodobnost|nepravděpodobn\w*|pravděpodobn\w*|reáln\w*\s+možnost\w*|téměř\s+jist\w*",
    "en": r"remote\s+chance|highly\s+unlikely|unlikely|realistic\s+possibility|highly\s+likely|likely|almost\s+certain",
}

POZNAMKY = {
    "vratene_sk": {
        "cs": "_Poznámka: překlad se nepodařilo ověřit (část textu zůstala slovensky nebo se citace, čísla či "
              "názvy léčiv lišily od slovenské verze), proto zobrazujeme slovenskou verzi._",
        "en": "_Note: the translation could not be verified (part of the text stayed in Slovak or citations, numbers "
              "or drug names differed from the Slovak version), so the Slovak version is shown._",
    },
    "neschvalene": {
        "cs": "_Poznámka: zpráva neprošla automatickou kontrolou, proto nebyla přeložena; zobrazujeme slovenskou "
              "verzi._",
        "en": "_Note: the report did not pass the automatic review, so it was not translated; the Slovak version "
              "is shown._",
    },
    "vynechany": {
        "cs": "_Poznámka: překlad nebyl k dispozici (limit volání jazykového modelu nebo chyba), zobrazujeme "
              "slovenskou verzi._",
        "en": "_Note: the translation was not available (language model call limit or error), so the Slovak "
              "version is shown._",
    },
}


def rola_prekladu(jazyk: str) -> str:
    """Systémový prompt prekladateľa (krátky, bez celého AGENTS.md – správa už je skontrolovaná)."""
    tabulka = "\n".join(f"  | {sk} | {cil} |" for sk, cil in [
        ("zanedbateľná pravdepodobnosť", PHIA_TABULKA[jazyk][0][1]), ("veľmi nepravdepodobné", PHIA_TABULKA[jazyk][1][1]),
        ("nepravdepodobné", PHIA_TABULKA[jazyk][4][1]), ("reálna možnosť", PHIA_TABULKA[jazyk][5][1]),
        ("pravdepodobné", PHIA_TABULKA[jazyk][6][1]), ("veľmi pravdepodobné", PHIA_TABULKA[jazyk][2][1]),
        ("takmer isté", PHIA_TABULKA[jazyk][3][1])])
    ist = ISTOTA_TABULKA[jazyk]
    priklad = PRIKLAD_RIADKU[jazyk]
    return f"""Si prekladateľ správ LiekRadaru. Prelož správu zo slovenčiny do {NAZVY_JAZYKOV[jazyk]}.
Správu už skontroloval kritik – nič nepridávaj, nevynechávaj a neopravuj, ale PRELOŽ CELÝ TEXT KAŽDÉHO RIADKU:
nadpis „# “, BLUF, všetky odrážky Key judgements, celé riadky Fakt, Úsudok a Upozornenie (aj text za
označením), Alternative explanations, Key assumptions, Indicators a vysvetľujúci text v Sources and method annex.
V preklade nesmie zostať ani jeden slovenský riadok či slovo (napr. „sú“, „liek“, „výpadok“, „pre“, „istota“).
Bez zmeny ostáva LEN:
- nadpisy sekcií začínajúce „## “ (napr. „## Bottom line up front“, „## Key judgements“, „## Discussion“),
- samotné označenia **Fakt:**, **Úsudok:**, **Upozornenie:** na začiatku riadku – text ZA nimi prelož,
- citácie [ID, Admiralty] (napr. [E004, A1] [E005, A2]), všetky čísla, sily (625 mg, 156,25 mg/5 ml),
  kódy liekov, ATC kódy a skratky liekových foriem (TBL FLM, PLU POR),
- oficiálne názvy liekov (napr. MEDOCLAV 625 mg, Amoksiklav 625 mg) a zdrojov (napr. „ŠÚKL – register
  liekov (API)“) – neprekladaj ich a neskloňuj.
Príklad:
  slovensky: {priklad[0]}
  preklad:   {priklad[1]}
Výrazy z mierky pravdepodobnosti PHIA prelož LEN podľa tejto tabuľky (v správnom tvare vety):
  | slovensky | preklad |
  |---|---|
{tabulka}
Istotu prelož ako „{ist['istota']}: {ist['nízka']}“ / „{ist['istota']}: {ist['stredná']}“ / „{ist['istota']}: {ist['vysoká']}“
(slovensky „istota: nízka / stredná / vysoká“; slovo „istota“ v preklade nesmie zostať).
Zachovaj markdown (odrážky, **tučné**, *kurzívu*) a poradie aj počet riadkov. Vráť len preloženú správu,
bez úvodu a bez ``` blokov."""


PRIKLAD_RIADKU = {
    "cs": ("- **Fakt:** Na slovenskom trhu sú hlásené výpadky liekov Amoksiklav 625 mg (TBL FLM) [E004, A1] [E005, A2].",
           "- **Fakt:** Na slovenském trhu jsou hlášeny výpadky léčiv Amoksiklav 625 mg (TBL FLM) [E004, A1] [E005, A2]."),
    "en": ("- **Fakt:** Na slovenskom trhu sú hlásené výpadky liekov Amoksiklav 625 mg (TBL FLM) [E004, A1] [E005, A2].",
           "- **Fakt:** Shortages of Amoksiklav 625 mg (TBL FLM) are reported on the Slovak market [E004, A1] [E005, A2]."),
}

def rola_doprekladu(jazyk: str) -> str:
    ist = ISTOTA_TABULKA[jazyk]
    phia = "; ".join(f"{sk} → {cil}" for sk, cil in [
        ("zanedbateľná pravdepodobnosť", PHIA_TABULKA[jazyk][0][1]), ("veľmi nepravdepodobné", PHIA_TABULKA[jazyk][1][1]),
        ("nepravdepodobné", PHIA_TABULKA[jazyk][4][1]), ("reálna možnosť", PHIA_TABULKA[jazyk][5][1]),
        ("pravdepodobné", PHIA_TABULKA[jazyk][6][1]), ("veľmi pravdepodobné", PHIA_TABULKA[jazyk][2][1]),
        ("takmer isté", PHIA_TABULKA[jazyk][3][1])])
    return (f"""Si prekladateľ správ LiekRadaru. Dostaneš riadky správy (s číslom riadku), ktoré pri preklade do
{NAZVY_JAZYKOV[jazyk]} zostali celé alebo čiastočne po slovensky. Pre každý vráť CELÝ riadok preložený do
{NAZVY_JAZYKOV[jazyk]} v jednom riadku. Bez zmeny nechaj len odrážku „- “, označenie **Fakt:** / **Úsudok:** /
**Upozornenie:** na začiatku (text za ním prelož), citácie [ID, Admiralty], čísla, sily, kódy, skratky
liekových foriem a oficiálne názvy liekov a zdrojov. Výrazy PHIA: {phia}. Istota: „{ist['istota']}: {ist['nízka']} /
{ist['stredná']} / {ist['vysoká']}“ (slovo „istota“ nesmie zostať). Vráť len opravy uvedených riadkov.""")


def fake_preklad(brief: str, jazyk: str, data: dict | None = None, riadky: set[int] | None = None) -> str:
    """Preklad pre režim LIEKRADAR_FAKE_LLM. Každý preložený riadok nahradí zástupným textom v cieľovom jazyku
    a ponechá len to, čo sa prekladať nesmie (odrážka, označenie, názvy liekov, čísla, citácie, výraz PHIA
    a istota podľa tabuľky). Nadpisy ## a sekcia AI use statement ostanú. `riadky` = prekladať len tieto.
    LIEKRADAR_FAKE_PREKLAD_NEUPLNY=1 nechá riadky Fakt po slovensky (dopreklad ich preloží),
    =2 ich nechá po slovensky aj pri doprekladu; LIEKRADAR_FAKE_PREKLAD_CHYBA=1 zmení jedno číslo."""
    from agents.graph import _SKUPINA
    nazvy = sorted(nazvy_liekov(data or {}), key=len, reverse=True)
    vypln = {"cs": "Přeložený text", "en": "Translated text"}[jazyk]
    neuplny = os.environ.get("LIEKRADAR_FAKE_PREKLAD_NEUPLNY", "")
    vysledok, sekcia = [], ""
    for i, riadok in enumerate(brief.splitlines()):
        if riadok.startswith("## "):
            sekcia = riadok.lower()
        if (not riadok.strip() or riadok.startswith("## ") or "ai use" in sekcia
                or (riadky is not None and i not in riadky)):
            vysledok.append(riadok)
            continue
        if "**Fakt:**" in riadok and ((neuplny == "1" and riadky is None) or neuplny == "2"):
            vysledok.append(riadok)  # simulácia: model nechal riadok Fakt po slovensky
            continue
        m = re.match(r"^(\s*(?:[-*+]\s+)?(?:\*\*(?:Fakt|Úsudok|Upozornenie):\*\*\s*)?|#\s+)", riadok)
        zaciatok = m.group(1) if m else ""
        zachovat, bez = [], riadok
        for n in nazvy:  # od najdlhších; každý výskyt zvlášť, aby počty názvov a čísel sedeli
            vyskyty = len(re.findall(_vzor_nazvu(n), bez, flags=re.IGNORECASE))
            if vyskyty:
                zachovat += [n] * vyskyty
                bez = re.sub(_vzor_nazvu(n), " ", bez, flags=re.IGNORECASE)
        cisla = re.findall(r"(?<![\w])\d+(?:[.,]\d+)?", _SKUPINA.sub(" ", bez))
        phia = next((cil for vzor, cil in PHIA_TABULKA[jazyk] if re.search(vzor, riadok, re.IGNORECASE)), "")
        istota = next((f"{ISTOTA_TABULKA[jazyk]['istota']}: {ISTOTA_TABULKA[jazyk][u]}"
                       for u in ("nízka", "stredná", "vysoká") if re.search(rf"istot\w*\W+{u}", riadok)), "")
        casti = [vypln] + zachovat + cisla + [x for x in (phia, istota) if x] + _SKUPINA.findall(riadok)
        casti = [f"[{c}]" if c in _SKUPINA.findall(riadok) else c for c in casti]
        vysledok.append(zaciatok + " ".join(casti) + ".")
    text = "\n".join(vysledok)
    if os.environ.get("LIEKRADAR_FAKE_PREKLAD_CHYBA") and riadky is None:
        text = re.sub(r"(?<![\w])(\d{2})(?![\w])", lambda m: str(int(m.group(1)) + 1), text, count=1)
    return text


def _vzor_nazvu(nazov: str) -> str:
    """Názov lieku ako regex, ktorý toleruje rôzny počet medzier („0,5 % -  POLPHARMA“)."""
    return r"\s+".join(re.escape(s) for s in nazov.split())


def ocisti(text: str) -> str:
    return re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", text.strip())


# ---------------------------------------------------------------------------
# Kontrola zhody prekladu so slovenskou verziou
# ---------------------------------------------------------------------------

def _citacie(text: str) -> Counter:
    from agents.graph import citacie
    return Counter(f"[{i}, {z}]" for i, z in citacie(text))


def _cisla(text: str) -> Counter:
    from agents.graph import _SKUPINA
    bez_citacii = _SKUPINA.sub(" ", text)
    return Counter(c.replace(",", ".") for c in re.findall(r"(?<![\w])\d+(?:[.,]\d+)?", bez_citacii))


def _kody(text: str) -> Counter:
    return Counter(k for r in text.splitlines() for _, k in _kody_v_riadku(r))


def nazvy_liekov(data: dict) -> set[str]:
    """Názvy liekov z výsledkov nástrojov (na kontrolu, že ich preklad nezmenil)."""
    nazvy: set[str] = set()
    for z in (data or {}).values():
        v = z.get("vysledok")
        if not isinstance(v, dict):
            continue
        zoznamy = [v.get("zaznamy") or [], v.get("vo_vypadku") or [], v.get("ine_balenia_toho_isteho") or []]
        if v.get("povodny_liek"):
            zoznamy.append([v["povodny_liek"]])
        for info in (v.get("krajiny") or {}).values():
            zoznamy += [info.get("teraz_vo_vypadku") or [], info.get("ohlasene_vypadky") or []]
        for zoznam in zoznamy:
            for r in zoznam:
                if isinstance(r, dict) and r.get("nazov") and len(str(r["nazov"]).strip()) >= 4:
                    nazvy.add(re.sub(r"\s+", " ", str(r["nazov"])).strip())
    return nazvy


def _rozdiel(a: Counter, b: Counter) -> str:
    chyba, navyse = a - b, b - a
    casti = []
    if chyba:
        casti.append("v preklade chýba " + ", ".join(sorted(chyba.elements())))
    if navyse:
        casti.append("v preklade navyše " + ", ".join(sorted(navyse.elements())))
    return "; ".join(casti)


def kontrola_prekladu(sk: str, preklad: str, data: dict) -> list[str]:
    """Rozdiely medzi slovenskou verziou a prekladom; prázdny zoznam = preklad je v poriadku."""
    rozdiely = []
    nadpisy_sk = [r.strip() for r in sk.splitlines() if r.startswith("## ")]
    nadpisy_pr = [r.strip() for r in preklad.splitlines() if r.startswith("## ")]
    if nadpisy_sk != nadpisy_pr:
        rozdiely.append(f"Nadpisy sekcií sa zmenili: v slovenskej verzii {nadpisy_sk}, v preklade {nadpisy_pr}.")
    for oznacenie in OZNACENIA:
        if sk.count(oznacenie) != preklad.count(oznacenie):
            rozdiely.append(f"Označenie {oznacenie}: v slovenskej verzii {sk.count(oznacenie)}×, "
                            f"v preklade {preklad.count(oznacenie)}×.")
    for nazov, funkcia in [("Citácie", _citacie), ("Čísla", _cisla), ("Kódy liekov", _kody)]:
        rozdiel = _rozdiel(funkcia(sk), funkcia(preklad))
        if rozdiel:
            rozdiely.append(f"{nazov}: {rozdiel}.")
    norm = lambda s: re.sub(r"\s+", " ", s).lower()  # noqa: E731
    chybajuce = sorted(n for n in nazvy_liekov(data) if norm(n) in norm(sk) and norm(n) not in norm(preklad))
    if chybajuce:
        rozdiely.append(f"Názvy liekov: v preklade chýba {', '.join(chybajuce)}.")
    return rozdiely


# Slovenské slová, ktoré v cieľovom jazyku nie sú (pre češtinu len tie, čo nie sú aj české – nie „je“, „na“,
# „náhrady“, „výpadky“, „odhadujeme“; tie by hlásili aj správny český text)
_SK_SLOVA = {
    "cs": {"sú", "liek", "lieky", "liekov", "lieku", "liekmi", "liekoch", "liekom", "liekovej", "liekovou", "liekové",
           "liekových", "výpadok", "pre", "pri", "istota", "istotou", "alebo", "môže", "môžu", "aj", "len", "ktoré",
           "ktorý", "ktorá", "tieto", "tiež", "ako", "nie", "sa", "tabliet", "tabletiek", "dodáva", "dodávajú",
           "potrebná", "potrebné", "lekár", "lekárom", "lekárne", "lekárenskej", "slovenskom", "rovnakou", "rovnakej",
           "zámenu", "inej", "urobiť", "správa", "odporúčanie", "pacientov", "ich", "však", "kvôli", "obsahom",
           "hlásené"},
    "en": {"sú", "je", "sa", "na", "pre", "pri", "alebo", "aj", "len", "liek", "lieky", "liekov", "lieku", "výpadok",
           "výpadky", "výpadku", "istota", "odhadujeme", "pravdepodobné", "náhrady", "ktoré", "jsou", "léčiv", "léky",
           "lék", "jistota", "pro", "při", "nebo", "že", "pouze", "lékař", "lekár", "zámenu", "dodáva", "dodávají"},
}
_SK_ZNAKY = {"cs": r"[äôľĺŕ]", "en": r"[äôľĺŕáéíóúýčďňšťžěřů]"}


def slovenske_riadky(preklad: str, jazyk: str, data: dict | None = None,
                     manifest: dict | None = None) -> list[tuple[int, str, list[str]]]:
    """Riadky prekladu, ktoré zostali (aj čiastočne) po slovensky: [(index, riadok, nájdené slová / znaky)].
    Pred hľadaním sa vynechajú nadpisy ##, sekcia AI use statement (doplní ju kód), citácie, označenia
    riadkov, názvy liekov z dát a oficiálne názvy zdrojov (ŠÚKL / SÚKL – …)."""
    from agents.graph import _SKUPINA
    nazvy = sorted(nazvy_liekov(data or {}), key=len, reverse=True)
    zdroje = sorted({z["zdroj"] for z in (manifest or {}).values() if z.get("zdroj")}, key=len, reverse=True)
    vysledok, sekcia = [], ""
    for i, riadok in enumerate(preklad.splitlines()):
        if riadok.startswith("## "):
            sekcia = riadok.lower()
            continue
        if not riadok.strip() or "ai use" in sekcia:
            continue
        text = _SKUPINA.sub(" ", riadok)
        for oznacenie in OZNACENIA:
            text = text.replace(oznacenie, " ")
        for n in nazvy + zdroje:
            text = re.sub(_vzor_nazvu(n), " ", text, flags=re.IGNORECASE)
        if "sources and method" in sekcia:  # oficiálne názvy zdrojov ostávajú po slovensky
            text = re.sub(r"[ŠS]ÚKL\s*[–-][^;\n]*", " ", text)
        text = re.sub(r"\b[ŠS]ÚKL\b|`[^`]*`", " ", text)
        najdene = sorted({m.group(0) for m in re.finditer(_SK_ZNAKY[jazyk], text)})
        slova = re.findall(r"[^\W\d_]+", text.lower())
        najdene += sorted({s for s in slova if s in _SK_SLOVA[jazyk]})
        if jazyk == "cs":  # slovenská koncovka -ej (perorálnej, liekovej); česky nie, okrem -dej (výdej, prodej)
            najdene += sorted({s for s in slova if re.fullmatch(r"\w{3,}[^d\W]ej", s)})
        if najdene:
            vysledok.append((i, riadok, najdene))
    return vysledok


def dopreklad_vstup(nepreložene: list[tuple[int, str, list[str]]]) -> str:
    return "Prelož celé tieto riadky:\n" + "\n".join(
        f"- riadok {i}: {r}\n  (zostalo po slovensky: {', '.join(n)})" for i, r, n in nepreložene)


def fake_dopreklad(preklad: str, nepreložene: list[tuple[int, str, list[str]]], jazyk: str, data: dict):
    """Pevný dopreklad pre režim LIEKRADAR_FAKE_LLM: riadky preloží rovnako ako fake_preklad."""
    from agents.korektura import OpravaRiadku, OpravyRiadkov
    riadky = preklad.splitlines()
    novy = fake_preklad(preklad, jazyk, data, riadky={i for i, _, _ in nepreložene}).splitlines()
    return OpravyRiadkov(opravy=[OpravaRiadku(riadok=i, text=novy[i]) for i, _, _ in nepreložene if i < len(riadky)])


def upozornenia_phia(sk: str, preklad: str, jazyk: str) -> list[str]:
    """Preklad má mať aspoň toľko výrazov PHIA ako originál (neblokuje, len upozornenie)."""
    from agents.graph import PHIA_VZOR
    v_sk = len(PHIA_VZOR.findall(sk))
    v_pr = len(re.findall(PHIA_V_PREKLADE[jazyk], preklad, re.IGNORECASE))
    return [] if v_pr >= v_sk else [f"Preklad má menej výrazov z mierky PHIA ({v_pr}) ako slovenská verzia ({v_sk})."]


def pridaj_do_bluf(brief: str, poznamka: str) -> str:
    """Pridá poznámku ako posledný odsek sekcie Bottom line up front (appka ju ukáže v rámčeku)."""
    riadky = brief.splitlines()
    i = next((k for k, r in enumerate(riadky) if re.match(r"^##\s+bottom line", r, re.IGNORECASE)), None)
    if i is None:
        return f"{poznamka}\n\n{brief}"
    j = next((k for k in range(i + 1, len(riadky)) if riadky[k].startswith("## ")), len(riadky))
    while j > i + 1 and not riadky[j - 1].strip():
        j -= 1
    return "\n".join(riadky[:j] + ["", poznamka] + riadky[j:])
