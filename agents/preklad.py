"""Preklad schválenej správy do češtiny alebo angličtiny a kontrola zhody s originálom.

Agenti pracujú a kritik kontroluje po slovensky. Až schválenú správu preloží krok „preklad“.
1. Pred prekladom kód nahradí všetko, čo sa nesmie meniť, značkami ⟦0⟧, ⟦1⟧, …: nadpisy ## sekcií, označenia
   **Fakt:** / **Úsudok:** / **Upozornenie:**, citácie [ID, Admiralty], kódy liekov, názvy liekov z výsledkov
   nástrojov (celé, aj „prášok na perorálnu suspenziu“), názvy zdrojov a istotu (tá má hodnotu už v cieľovom
   jazyku: „jistota: střední“, „confidence: moderate“ – nahradí ju kód, nie model). Sekcia AI use statement
   sa neprekladá, doplní ju kód.
2. Model dostane text so značkami a pokyn značky nemeniť ani nevynechať (1 LLM volanie).
3. Kód skontroluje každý riadok: rovnaké značky, čísla, citácie a kódy, nič po slovensky. Zlé riadky preloží
   jedno cielené volanie znova zo slovenského originálu. Potom kód vráti pôvodné hodnoty značiek a overí
   zhodu celej správy. Ak to nepomôže, použije sa slovenská verzia s poznámkou.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field

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


def _tabulka_phia(jazyk: str) -> str:
    return "\n".join(f"  | {sk} | {cil} |" for sk, cil in [
        ("zanedbateľná pravdepodobnosť", PHIA_TABULKA[jazyk][0][1]), ("veľmi nepravdepodobné", PHIA_TABULKA[jazyk][1][1]),
        ("nepravdepodobné", PHIA_TABULKA[jazyk][4][1]), ("reálna možnosť", PHIA_TABULKA[jazyk][5][1]),
        ("pravdepodobné", PHIA_TABULKA[jazyk][6][1]), ("veľmi pravdepodobné", PHIA_TABULKA[jazyk][2][1]),
        ("takmer isté", PHIA_TABULKA[jazyk][3][1])])


PRAVIDLA_ZNACIEK = """Text obsahuje značky ⟦0⟧, ⟦1⟧, ⟦2⟧, … – zastupujú nadpisy, označenia riadkov, citácie, kódy, názvy liekov
a zdrojov a istotu. KAŽDÚ značku prepíš presne v tvare ⟦číslo⟧, presne raz a v tom istom riadku, kde je
v origináli. Značky neprekladaj, nemeň, nevynechávaj, nespájaj a nepridávaj nové. Riadok, ktorý obsahuje
len značky (napr. „⟦3⟧“), nechaj presne tak. Všetok ostatný text prelož CELÝ – v preklade nesmie zostať
slovenské slovo. Čísla a sily (625 mg, 156,25 mg/5 ml) prepíš bez zmeny."""


def rola_prekladu(jazyk: str) -> str:
    """Systémový prompt prekladateľa (krátky, bez celého AGENTS.md – správa už je skontrolovaná)."""
    priklad = PRIKLAD_RIADKU[jazyk]
    return f"""Si prekladateľ správ LiekRadaru. Prelož správu zo slovenčiny do {NAZVY_JAZYKOV[jazyk]}.
Správu už skontroloval kritik – nič nepridávaj, nevynechávaj a neopravuj.
{PRAVIDLA_ZNACIEK}
Príklad:
  slovensky: {priklad[0]}
  preklad:   {priklad[1]}
Výrazy z mierky pravdepodobnosti PHIA prelož LEN podľa tejto tabuľky (v správnom tvare vety):
  | slovensky | preklad |
  |---|---|
{_tabulka_phia(jazyk)}
Zachovaj odrážky, markdown, poradie aj počet riadkov (aj prázdne riadky). Vráť len preložený text,
bez úvodu a bez ``` blokov."""


PRIKLAD_RIADKU = {
    "cs": ("- ⟦7⟧ Na slovenskom trhu sú hlásené výpadky ⟦8⟧ a ⟦9⟧ ⟦10⟧ ⟦11⟧.",
           "- ⟦7⟧ Na slovenském trhu jsou hlášeny výpadky ⟦8⟧ a ⟦9⟧ ⟦10⟧ ⟦11⟧."),
    "en": ("- ⟦7⟧ Na slovenskom trhu sú hlásené výpadky ⟦8⟧ a ⟦9⟧ ⟦10⟧ ⟦11⟧.",
           "- ⟦7⟧ Shortages of ⟦8⟧ and ⟦9⟧ are reported on the Slovak market ⟦10⟧ ⟦11⟧."),
}


def rola_doprekladu(jazyk: str) -> str:
    return f"""Si prekladateľ správ LiekRadaru. Dostaneš slovenské riadky správy (s číslom riadku), ktorých prvý
preklad do {NAZVY_JAZYKOV[jazyk]} neprešiel kontrolou (pri každom je dôvod). Každý riadok prelož znova CELÝ
do {NAZVY_JAZYKOV[jazyk]} a vráť ho v jednom riadku pod tým istým číslom.
{PRAVIDLA_ZNACIEK}
Výrazy PHIA prelož podľa tabuľky:
{_tabulka_phia(jazyk)}
Vráť len preklady uvedených riadkov."""


# ---------------------------------------------------------------------------
# Značky ⟦n⟧: čo sa nesmie prekladať
# ---------------------------------------------------------------------------

ZNACKA = re.compile(r"⟦(\d+)⟧")
_LEN_ZNACKY = re.compile(r"^[\s\-*+.,;:()]*(?:⟦\d+⟧[\s\-*+.,;:()]*)+$")
_ISTOTA_SLOVO = re.compile(r"\b[Ii]stota\b")
_ISTOTA_UROVEN = re.compile(r"\b(nízka|stredná|vysoká)\b")
_ZDROJ_V_PRILOHE = re.compile(r"[ŠS]ÚKL\s*[–-]\s*[^\[\n;(]*[^\[\n;(\s]")


@dataclass
class Maska:
    """Slovenská správa so značkami (len časť pred AI use statement) a hodnoty značiek."""
    riadky: list[str]
    hodnoty: dict[int, str]
    chvost: list[str] = field(default_factory=list)  # AI use statement a ďalej – neprekladá sa
    jazyk: str = "cs"

    @property
    def text(self) -> str:
        return "\n".join(self.riadky)

    @staticmethod
    def znacky(riadok: str) -> Counter:
        return Counter(ZNACKA.findall(riadok))

    def odmaskuj(self, riadok: str) -> str:
        return ZNACKA.sub(lambda m: self.hodnoty.get(int(m.group(1)), m.group(0)), riadok)


def maskuj(brief: str, jazyk: str, data: dict | None = None, manifest: dict | None = None) -> Maska:
    """Nahradí v slovenskej správe všetko, čo sa nesmie prekladať, značkami ⟦n⟧."""
    from agents.graph import _SKUPINA
    nazvy = sorted(nazvy_liekov(data or {}), key=len, reverse=True)
    zdroje = sorted({z["zdroj"] for z in (manifest or {}).values() if z.get("zdroj")}, key=len, reverse=True)
    ist = ISTOTA_TABULKA[jazyk]
    hodnoty: dict[int, str] = {}
    riadky_out: list[str] = []
    riadky = brief.splitlines()
    sekcia = ""
    for k, riadok in enumerate(riadky):
        if riadok.startswith("## "):
            sekcia = riadok.lower()
            if "ai use" in sekcia:
                return Maska(riadky_out, hodnoty, riadky[k:], jazyk)
        useky: list[tuple[int, int, str]] = []

        def pridaj(zac: int, kon: int, hodnota: str) -> None:
            if zac < kon and not any(zac < b and a < kon for a, b, _ in useky):
                useky.append((zac, kon, hodnota))

        if riadok.startswith("## "):
            pridaj(0, len(riadok), riadok)
        for oznacenie in OZNACENIA:
            for m in re.finditer(re.escape(oznacenie), riadok):
                pridaj(m.start(), m.end(), oznacenie)
        for m in _SKUPINA.finditer(riadok):
            pridaj(m.start(), m.end(), m.group(0))
        for m in re.finditer(r"`[^`\n]+`", riadok):
            pridaj(m.start(), m.end(), m.group(0))
        for n in nazvy:
            for m in re.finditer(_vzor_nazvu(n), riadok, flags=re.IGNORECASE):
                pridaj(m.start(), m.end(), m.group(0))
        for n in zdroje:
            for m in re.finditer(_vzor_nazvu(n), riadok):
                pridaj(m.start(), m.end(), m.group(0))
        if "sources and method" in sekcia:
            for m in _ZDROJ_V_PRILOHE.finditer(riadok):
                pridaj(m.start(), m.end(), m.group(0))
        for pozicia, kod in _kody_v_riadku(riadok):
            pridaj(pozicia, pozicia + len(kod), kod)
        for m in _ISTOTA_SLOVO.finditer(riadok):  # istota sa prekladá v kóde podľa pevnej tabuľky
            slovo = ist["istota"]
            pridaj(m.start(), m.end(), slovo[:1].upper() + slovo[1:] if m.group(0)[0].isupper() else slovo)
            uroven = _ISTOTA_UROVEN.search(riadok, m.end(), min(len(riadok), m.end() + 40))
            if uroven:
                pridaj(uroven.start(), uroven.end(), ist[uroven.group(1)])
        novy, posledny = [], 0
        for zac, kon, hodnota in sorted(useky):
            cislo = len(hodnoty)
            hodnoty[cislo] = hodnota
            novy.append(riadok[posledny:zac] + f"⟦{cislo}⟧")
            posledny = kon
        riadky_out.append("".join(novy) + riadok[posledny:])
    return Maska(riadky_out, hodnoty, [], jazyk)


def _slovenske_slova(text: str, jazyk: str) -> list[str]:
    """Slovenské znaky a slová v texte (bez značiek)."""
    text = ZNACKA.sub(" ", text)
    najdene = sorted({m.group(0) for m in re.finditer(_SK_ZNAKY[jazyk], text)})
    slova = re.findall(r"[^\W\d_]+", text.lower())
    najdene += sorted({s for s in slova if s in _SK_SLOVA[jazyk]})
    if jazyk == "cs":  # slovenská koncovka -ej (perorálnej, liekovej); česky nie, okrem -dej (výdej, prodej)
        najdene += sorted({s for s in slova if re.fullmatch(r"\w{3,}[^d\W]ej", s)})
    return najdene


def zly_riadok(maska: Maska, i: int, preklad: str) -> str | None:
    """Dôvod, prečo preložený riadok i (so značkami) neprešiel kontrolou, alebo None."""
    povodny = maska.riadky[i]
    if not preklad.strip():
        return "prázdny riadok"
    rozdiel = _rozdiel(maska.znacky(povodny), maska.znacky(preklad)).replace("v preklade", "")
    if rozdiel:
        return f"značky:{rozdiel}"
    if _LEN_ZNACKY.match(povodny) and preklad.strip() != povodny.strip():
        return "riadok len so značkami sa zmenil"
    sk, pr = maska.odmaskuj(povodny), maska.odmaskuj(preklad)
    for nazov, funkcia in [("čísla", _cisla), ("citácie", _citacie), ("kódy liekov", _kody)]:
        rozdiel = _rozdiel(funkcia(sk), funkcia(pr))
        if rozdiel:
            return f"{nazov}: {rozdiel}"
    zostalo = _slovenske_slova(preklad, maska.jazyk)
    if zostalo:
        return f"zostalo po slovensky: {', '.join(zostalo[:6])}"
    return None


def over_preklad(maska: Maska, preklad: str) -> tuple[list[str], dict[int, str]]:
    """Zarovná preklad s originálom po riadkoch. Vracia (preložené riadky so značkami, zlé riadky {i: dôvod}).
    Ak sa zmenil počet neprázdnych riadkov, sú zlé všetky riadky (preložia sa znova po jednom)."""
    neprazdne = [i for i, r in enumerate(maska.riadky) if r.strip()]
    prelozene = [r for r in preklad.splitlines() if r.strip()]
    riadky = list(maska.riadky)
    if len(prelozene) != len(neprazdne):
        return riadky, {i: f"počet riadkov sa zmenil ({len(neprazdne)} → {len(prelozene)})" for i in neprazdne}
    zle = {}
    for i, r in zip(neprazdne, prelozene):
        riadky[i] = r
        dovod = zly_riadok(maska, i, r)
        if dovod:
            zle[i] = dovod
    return riadky, zle


def dopreklad_vstup(maska: Maska, zle: dict[int, str]) -> str:
    return "Prelož znova tieto riadky (slovenský originál so značkami):\n" + "\n".join(
        f"- riadok {i}: {maska.riadky[i]}\n  dôvod: {dovod}" for i, dovod in sorted(zle.items()))


def pouzi_dopreklad(maska: Maska, riadky: list[str], zle: dict[int, str], opravy) -> tuple[list[str], dict[int, str]]:
    """Vymení zlé riadky za dopreklad, ak prejde kontrolou; ostatné ostanú zlé (s novým dôvodom)."""
    riadky, zostava = list(riadky), dict(zle)
    for o in opravy.opravy:
        if o.riadok not in zostava:
            continue
        text = re.sub(r"\s*\n\s*", " ", o.text or "").rstrip()
        if maska.riadky[o.riadok].startswith("- ") and not text.lstrip().startswith(("- ", "* ")):
            text = "- " + text.lstrip()
        dovod = zly_riadok(maska, o.riadok, text)
        if dovod:
            zostava[o.riadok] = f"aj po doprekladu – {dovod}"
        else:
            riadky[o.riadok] = text
            del zostava[o.riadok]
    return riadky, zostava


def zloz(maska: Maska, riadky: list[str]) -> str:
    """Preložené riadky s pôvodnými hodnotami značiek + neprekladaná sekcia AI use statement."""
    return "\n".join([maska.odmaskuj(r) for r in riadky] + maska.chvost)


# ---------------------------------------------------------------------------
# Pevný preklad pre režim LIEKRADAR_FAKE_LLM (nad textom so značkami)
# ---------------------------------------------------------------------------

def _fake_riadok(maska: Maska, i: int, dopreklad: bool) -> str:
    """Zástupný preklad riadku: ponechá odrážku, značky, čísla a výraz PHIA, zvyšok nahradí výplňou.
    LIEKRADAR_FAKE_PREKLAD_NEUPLNY=1 nechá riadky Fakt po slovensky (=2 aj pri doprekladu),
    LIEKRADAR_FAKE_PREKLAD_ZNACKA=1 vynechá značku v prvom riadku s citáciou (=2 aj pri doprekladu),
    LIEKRADAR_FAKE_PREKLAD_CHYBA=1 zmení číslo v prvom riadku s dvojciferným číslom (len prvý preklad)."""
    riadok = maska.riadky[i]
    if not riadok.strip() or _LEN_ZNACKY.match(riadok):
        return riadok
    neuplny = os.environ.get("LIEKRADAR_FAKE_PREKLAD_NEUPLNY", "")
    hodnoty = [maska.hodnoty[int(c)] for c in ZNACKA.findall(riadok)]
    if "**Fakt:**" in hodnoty and (neuplny == "2" or (neuplny == "1" and not dopreklad)):
        return riadok  # simulácia: model nechal riadok po slovensky
    zaciatok = re.match(r"^\s*(?:[-*+]\s+|#\s+)?(?:⟦\d+⟧\s*)?", riadok).group(0)
    if zaciatok.strip() and ZNACKA.search(zaciatok) and maska.hodnoty[int(ZNACKA.search(zaciatok).group(1))] \
            not in OZNACENIA:
        zaciatok = re.match(r"^\s*(?:[-*+]\s+|#\s+)?", riadok).group(0)
    znacky = ZNACKA.findall(riadok[len(zaciatok):])
    cisla = re.findall(r"(?<![\w⟦])\d+(?:[.,]\d+)?(?![⟧\d])", ZNACKA.sub(" ", riadok))
    phia = next((cil for vzor, cil in PHIA_TABULKA[maska.jazyk] if re.search(vzor, riadok, re.IGNORECASE)), "")
    vypln = {"cs": "Přeložený text", "en": "Translated text"}[maska.jazyk]
    casti = [vypln] + [f"⟦{c}⟧" for c in znacky] + cisla + ([phia] if phia else [])
    znacka = os.environ.get("LIEKRADAR_FAKE_PREKLAD_ZNACKA", "")
    prvy_s_citaciou = next((k for k, r in enumerate(maska.riadky)
                            if any(maska.hodnoty[int(c)].startswith("[E") for c in ZNACKA.findall(r))), None)
    if i == prvy_s_citaciou and (znacka == "2" or (znacka == "1" and not dopreklad)):
        casti = [c for c in casti if c != f"⟦{znacky[-1]}⟧"]  # simulácia: model vynechal značku
    text = zaciatok + " ".join(casti) + "."
    if os.environ.get("LIEKRADAR_FAKE_PREKLAD_CHYBA") and not dopreklad and cisla:
        prvy = next((k for k, r in enumerate(maska.riadky) if re.search(r"(?<![\w⟦])\d{2}(?![⟧\d])",
                                                                    ZNACKA.sub(" ", r))), None)
        if i == prvy:
            text = re.sub(r"(?<![\w⟦])(\d{2})(?![⟧\d])", lambda m: str(int(m.group(1)) + 1), text, count=1)
    return text


def fake_preklad(maska: Maska) -> str:
    return "\n".join(_fake_riadok(maska, i, False) for i in range(len(maska.riadky)))


def fake_dopreklad(maska: Maska, zle: dict[int, str]):
    from agents.korektura import OpravaRiadku, OpravyRiadkov
    return OpravyRiadkov(opravy=[OpravaRiadku(riadok=i, text=_fake_riadok(maska, i, True)) for i in sorted(zle)])


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
