"""Kontrola rozsahu otázky a jazyk otázky (bez modelu).

LiekRadar je pre nákupcov lekárenských sietí a výrobcov liekov, nie pre pacientov. Ak sa niekto pýta
ako pacient (prvá osoba a užívanie lieku: „došiel mi xanax, čo si môžem dať“, „můžu si místo X vzít Y“,
„I ran out of my pills, what can I take“), systém nenavrhuje náhrady ani dávkovanie a vráti pevný text
bez jazykového modelu. Vzory nižšie sú poistka v kóde; orchestrátor rozsah určuje aj sám.
"""

from __future__ import annotations

import re
import unicodedata

JAZYKY = ("sk", "cs", "en")


def _norm(text: str) -> str:
    """Malé písmená bez diakritiky („Došiel mi“ -> „dosiel mi“, „můžu“ -> „muzu“)."""
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()


# Prvá osoba + užívanie / dochádzanie / zámena vlastného lieku, alebo dávkovanie pre seba (po normalizácii)
_PACIENT = [
    # SK
    r"\b(dosiel|dosla|doslo|dosli|minul|minula|minulo|minuli)\s+(sa\s+)?mi\b",
    r"\bmi\s+(dosiel|dosla|doslo|dosli)\b",
    r"\b(beriem|uzivam|pouzivam)\b",
    r"\bmozem\s+(si\s+)?(dat|vziat|zobrat|brat|uzit|uzivat|pouzit|nahradit|vymenit)\b",
    r"\bco\s+(ine\s+)?(si\s+)?(mozem|mam|by\s+som\s+mal\w*)\s+(si\s+)?(dat|vziat|zobrat|brat|uzit)\b",
    r"\b(moj|moje|moju|mojho|mojom|mojich)\s+(liek|lieky|lieku|liekov|tabletk\w*|tablet\w*|antibiotik\w*)\b",
    r"\b(predpisal|predpisala|predpisali)\s+mi\b",
    r"\bkolko\s+(tabliet|tabletiek|kapsul|mg|kvapiek)\b.{0,30}\b(si|mam|mozem|smiem)\b",
    # CZ
    r"\b(dosel|dosla|doslo|dosly)\s+mi\b",
    r"\b(muzu|smim|mohu|muzeme)\s+(si\s+)?(vzit|dat|brat|uzit|uzivat|pouzit|nahradit|vymenit)\b",
    r"\bco\s+(jineho\s+)?(si\s+)?(muzu|mam|smim)\s+(si\s+)?(vzit|dat|brat)\b",
    r"\b(beru|uzivam|pouzivam)\b",
    r"\b(muj|moje|mou|meho|mych)\s+(lek|leky|leku|lecivo|prasek|prasky|tablet\w*|antibiotik\w*)\b",
    r"\bmisto\b.{0,40}\b(vzit|brat|dat)\b",
    r"\bpredepsal\w*\s+mi\b",
    # EN
    r"\bi\s+(take|am\s+taking|have\s+been\s+taking|ran\s+out|run\s+out|have\s+run\s+out|need\s+to\s+take)\b",
    r"\bi'?m\s+(taking|out\s+of)\b",
    r"\b(can|could|should|may)\s+i\s+(take|use|switch|replace|substitute|stop)\b",
    r"\bwhat\s+(else\s+)?(can|could|should)\s+i\s+(take|use)\b",
    r"\bmy\s+(medication|medications|medicine|medicines|pills|prescription|tablets|meds|antibiotics|drug)\b",
    r"\bhow\s+(many|much)\b.{0,40}\bshould\s+i\b",
]
_PACIENT_VZOR = re.compile("|".join(f"(?:{v})" for v in _PACIENT))


def je_pacientska_otazka(otazka: str) -> bool:
    """Poistka v kóde: otázka pacienta o vlastnom lieku, jeho náhrade alebo dávkovaní."""
    return bool(_PACIENT_VZOR.search(_norm(otazka)))


def pacientsky_vzor(otazka: str) -> str | None:
    """Ktorý úsek otázky vzor zachytil (do Case Logu)."""
    m = _PACIENT_VZOR.search(_norm(otazka))
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Jazyk otázky (heuristika bez modelu; orchestrátor určuje jazyk aj sám)
# ---------------------------------------------------------------------------

_SLOVA = {
    # len slová, ktoré sa po odstránení diakritiky v SK a CZ líšia (nie „na“, „Slovensku“, „čím“, „nahradit“)
    "sk": {"ktore", "ktory", "ktora", "liek", "lieky", "liekov", "lieku", "mozem", "mozno", "hrozi", "budu",
           "chybat", "sa", "pre", "ako", "alebo", "nie", "su", "som", "dosiel", "vypadok", "vyrobca", "lekaren",
           "kedy", "preco", "aky", "aka", "ake", "vo", "ak", "ci", "tieto"},
    "cs": {"ktere", "ktery", "ktera", "lek", "leky", "leku", "leciv", "lecivo", "muzu", "mohu", "jsem", "neni",
           "jsou", "budou", "chybet", "misto", "vzit", "nebo", "jaky", "jake", "proc", "kdy", "dosel", "vypadek",
           "vyrobce", "lekarna", "pro", "jak", "se", "pokud", "jestli", "tyto", "ho"},
    "en": {"the", "what", "which", "can", "could", "should", "i", "my", "is", "are", "will", "in", "of", "for",
           "to", "drug", "drugs", "medicine", "medicines", "shortage", "shortages", "replace", "replacement",
           "substitute", "slovakia", "czech", "republic", "pills", "take", "out", "ran", "be", "how", "missing"},
}


def jazyk_textu(text: str) -> str | None:
    """'sk', 'cs', 'en' alebo None, ak sa nedá rozhodnúť (napr. len ATC kód)."""
    surovy = str(text).lower()
    skore = {"sk": 0.0, "cs": 0.0, "en": 0.0}
    skore["cs"] += 3 * len(re.findall(r"[řůě]", surovy))
    skore["sk"] += 3 * len(re.findall(r"[äôľĺŕ]", surovy))
    slova = re.findall(r"[a-z']+", _norm(text))
    for j, zoznam in _SLOVA.items():
        skore[j] += sum(1 for s in slova if s in zoznam)
    if re.search(r"[áéíóúýčďňšťž]", surovy) or re.search(r"\b\w+ť\b", surovy):  # diakritika: nie angličtina
        skore["en"] = 0
        skore["sk"] += 2 * len(re.findall(r"\b\w{3,}ť\b", surovy))                 # infinitív SK: nahradiť
        skore["cs"] += 2 * len(re.findall(r"\b\w{3,}(?:it|at|ět|out|ít)\b", surovy))  # infinitív CZ: nahradit
    najlepsi = max(skore, key=skore.get)
    hodnoty = sorted(skore.values(), reverse=True)
    if hodnoty[0] <= 0 or hodnoty[0] == hodnoty[1]:
        return None
    return najlepsi


def urci_jazyk(z_otazky: str | None, z_appky: str | None) -> str:
    """Jazyk odpovede: jazyk otázky má prednosť, inak jazyk z appky, inak slovenčina."""
    for j in (z_otazky, z_appky):
        if j in JAZYKY:
            return j
    return "sk"


# ---------------------------------------------------------------------------
# Pevná odpoveď pre pacienta (bez modelu)
# ---------------------------------------------------------------------------

ODPOVED_PACIENT = {
    "sk": ("LiekRadar nie je určený pre pacientov",
           "LiekRadar slúži lekárenským sieťam a výrobcom liekov, nie pacientom, a neodporúča lieky ani dávkovanie. "
           "S otázkou, čím nahradiť váš liek, sa obráťte na svojho lekára alebo lekárnika. Liek nevysadzujte ani "
           "nemeňte bez lekára. Pri akútnych ťažkostiach volajte 155 alebo 112."),
    "cs": ("LiekRadar není určen pro pacienty",
           "LiekRadar slouží lékárenským sítím a výrobcům léčiv, nikoli pacientům, a nedoporučuje léky ani dávkování. "
           "S otázkou, čím nahradit váš lék, se obraťte na svého lékaře nebo lékárníka. Lék nevysazujte ani neměňte "
           "bez lékaře. Při akutních potížích volejte 155 nebo 112."),
    "en": ("LiekRadar is not intended for patients",
           "LiekRadar is a tool for pharmacy chains and drug manufacturers, not for patients, and it does not "
           "recommend medicines or doses. Please ask your doctor or pharmacist what could replace your medicine. "
           "Do not stop or change your medicine without a doctor. In an emergency, call 155 or 112."),
}


def odpoved_pre_pacienta(jazyk: str) -> str:
    """Pevný text pod nadpisom „## Bottom line up front“ (appka ho zobrazí v rámčeku Stručná odpoveď)."""
    nadpis, text = ODPOVED_PACIENT.get(jazyk, ODPOVED_PACIENT["sk"])
    return f"# {nadpis}\n\n## Bottom line up front\n{text}\n"
