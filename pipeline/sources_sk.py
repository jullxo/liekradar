"""Zdroje dát pre Slovenskú republiku (ŠÚKL).

Spustenie (v priečinku projektu, so zapnutým .venv):
    python -m pipeline.sources_sk              # register aj hlásenia
    python -m pipeline.sources_sk register     # len register
    python -m pipeline.sources_sk hlasenia     # len hlásenia

Zatiaľ hotové:
- register liekov cez API ŠÚKL (ŠÚKL kód, ATC, držiteľ, forma, balenie)
- hlásenia o prvom uvedení, prerušení, zrušení a obnovení dodávok z portálu ŠÚKL

Doplníme neskôr:
- kategorizácia MZ SR (ceny a úhrady)
"""

import csv
import html
import io
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

from pipeline import manifest

RAW_DIR = Path("data/raw/sk")
REGISTER_FILE = RAW_DIR / "register.parquet"

# Verejné API ŠÚKL (licencia CC0). Dáta vracia po stránkach: limit = koľko riadkov,
# offset = od ktorého riadku začať.
REGISTER_API = "https://api.sukl.sk/json/lieky_ui42.php"
PAGE_SIZE = 1000
PAUSE_SECONDS = 1  # krátka pauza medzi požiadavkami, aby sme server nezaťažovali

HEADERS = {"User-Agent": "LiekRadar (studentsky projekt VSE, 4IT529)"}

# Z mnohých stĺpcov API si necháme len tie, ktoré naozaj potrebujeme.
REGISTER_COLUMNS = {
    "lie_kod": "kod_sukl",
    "lie_nazov": "nazov",
    "lie_doplnok": "doplnok",
    "atc_kod": "atc",
    "atc_nazov": "atc_nazov",
    "drz_kod": "drzitel_kod",
    "drz_nazov": "drzitel",
    "drz_sta_kod": "drzitel_stat",
    "form_kod": "forma_kod",
    "form_nazov": "forma",
    "pod_nazov": "cesta_podania",
    "lie_sila": "sila",
    "lie_balenie": "balenie",
    "vyd_kod": "vydaj",
    "stav_kod": "stav_registracie",
    "lie_registracia": "datum_registracie",
}


def _parse_json_from_html(text: str) -> list[dict]:
    """API ŠÚKL nevracia čistý JSON, ale HTML stránku, ktorá má JSON v tele (<body>).

    Najprv skúsime text načítať priamo ako JSON. Ak to nejde, vystrihneme
    časť od prvej '[' po poslednú ']' v tele stránky a načítame tú.
    """
    try:
        return json.loads(text)
    except ValueError:
        pass

    body_start = max(text.lower().find("<body"), 0)
    start = text.find("[", body_start)
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []  # prázdna stránka = koniec dát

    chunk = text[start:end + 1]
    try:
        return json.loads(chunk)
    except ValueError:
        return json.loads(html.unescape(chunk))


def _get_page(offset: int, attempts: int = 3) -> list[dict]:
    """Stiahne jednu stránku registra. Pri chybe skúsi znova."""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                REGISTER_API,
                params={"limit": PAGE_SIZE, "offset": offset},
                headers=HEADERS,
                timeout=60,
            )
            response.raise_for_status()
            return _parse_json_from_html(response.text)
        except (requests.RequestException, ValueError) as error:
            if attempt == attempts:
                raise
            print(f"  Chyba pri offset={offset} ({error}), skúšam znova…")
            time.sleep(5 * attempt)
    return []


def download_register() -> Path:
    """Stiahne celý register liekov po stránkach a uloží ho do data/raw/sk/register.parquet."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    seen_first_ids: set = set()
    offset = 0
    while True:
        page = _get_page(offset)
        if not page:
            break
        first_id = page[0].get("lie_id")
        if first_id in seen_first_ids:  # poistka: API by vracalo stále to isté
            print("  API vracia opakovane rovnakú stránku, končím.")
            break
        seen_first_ids.add(first_id)

        rows.extend(page)
        print(f"  Stiahnutých {len(rows):,} riadkov".replace(",", " "))
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(PAUSE_SECONDS)

    df = pd.DataFrame(rows)
    df = df[[c for c in REGISTER_COLUMNS if c in df.columns]].rename(columns=REGISTER_COLUMNS)
    df["kod_sukl"] = df["kod_sukl"].astype(str).str.strip()
    df["atc"] = df["atc"].astype("string").str.strip()
    df.to_parquet(REGISTER_FILE, index=False)
    manifest.zaznamenaj("sk_register", REGISTER_FILE, REGISTER_API)
    print(f"Uložené do {REGISTER_FILE}")
    return REGISTER_FILE


def load_register() -> pd.DataFrame:
    """Načíta uložený register."""
    if not REGISTER_FILE.exists():
        raise FileNotFoundError("Register ešte nie je stiahnutý. Spusti najprv sťahovanie.")
    return pd.read_parquet(REGISTER_FILE)


def summarize_register(df: pd.DataFrame) -> None:
    """Vypíše prvý prehľad o slovenskom registri."""
    print("\n=== Prehľad slovenského registra liekov ===")
    print(f"Počet liekov (balení): {len(df):,}".replace(",", " "))
    print(f"Unikátnych ŠÚKL kódov: {df['kod_sukl'].nunique():,}".replace(",", " "))

    atc = df["atc"].fillna("")
    print("\nDĺžka ATC kódu (7 znakov = konkrétna účinná látka):")
    print(atc.str.len().value_counts().sort_index().to_string())

    print("\nNajčastejší držitelia registrácie:")
    print(df["drzitel"].str.strip().value_counts().head(10).to_string())

    antibiotika = df[atc.str.startswith("J01")]
    print(f"\nAntibiotiká (ATC J01): {len(antibiotika):,} balení".replace(",", " "))
    print("\nUkážka 5 riadkov:")
    print(df[["kod_sukl", "nazov", "doplnok", "atc", "drzitel"]].head().to_string(index=False))


# ---------------------------------------------------------------------------
# Hlásenia o prvom uvedení, prerušení, zrušení a obnovení dodávok (portál ŠÚKL)
# ---------------------------------------------------------------------------

HLASENIA_FILE = RAW_DIR / "hlasenia.parquet"
PORTAL_BASE = "https://portal.sukl.sk/PreruseniePublic/"
PORTAL_LIST = PORTAL_BASE + "?act=PrerusenieOznList&mid=2"
PORTAL_EXPORT = PORTAL_BASE + "?act=PrerusenieOznList&export=csv"

HLASENIA_COLUMNS = ["datum_podania", "drzitel", "kod_sukl", "liek", "datum_ucinnosti", "predmet"]
PREDMET_NAZVY = {"U": "prvé uvedenie", "R": "prerušenie", "O": "obnovenie", "Z": "zrušenie"}


def _plain(text: str) -> str:
    """Malé písmená bez diakritiky, aby sme vedeli porovnávať názvy stĺpcov."""
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


def _normalize_hlasenia(df: pd.DataFrame) -> pd.DataFrame:
    """Premenuje stĺpce na naše názvy a prevedie dátumy."""
    keywords = {
        "datum_podania": ["podan"],
        "drzitel": ["drzitel"],
        "kod_sukl": ["kod"],
        "liek": ["liek", "nazov"],
        "datum_ucinnosti": ["ucinn"],
        "predmet": ["predmet", "typ"],
    }
    mapping = {}
    for column in df.columns:
        plain = _plain(column)
        for target, words in keywords.items():
            if target not in mapping.values() and any(w in plain for w in words):
                mapping[column] = target
                break
    df = df.rename(columns=mapping)

    # Keby sa názvy stĺpcov nepodarilo rozpoznať, vezmeme posledných 6 stĺpcov
    # v poradí, v akom sú na portáli.
    if not set(HLASENIA_COLUMNS).issubset(df.columns):
        if df.shape[1] < 6:
            raise ValueError(f"Neznámy formát hlásení, stĺpce: {list(df.columns)}")
        df = df.iloc[:, -6:]
        df.columns = HLASENIA_COLUMNS

    df = df[HLASENIA_COLUMNS].copy()
    for column in ["drzitel", "kod_sukl", "liek", "predmet"]:
        df[column] = df[column].astype(str).str.strip()
    df["predmet"] = df["predmet"].str.upper().str[:1]
    for column in ["datum_podania", "datum_ucinnosti"]:
        df[column] = _parse_dates(df[column])
    return df[df["predmet"].isin(PREDMET_NAZVY)]


def _parse_dates(values: pd.Series) -> pd.Series:
    """Prevedie text na dátumy. Zvláda ISO (2026-11-12) aj slovenský formát (12.11.2026).

    Pozor: ISO dátumy sa nesmú čítať s dayfirst=True, inak sa pri dňoch 1–12
    prehodí deň a mesiac.
    """
    values = values.astype(str).str.strip()
    is_iso = values.str.match(r"^\d{4}-", na=False)
    iso = pd.to_datetime(values.where(is_iso), format="mixed", errors="coerce")
    local = pd.to_datetime(values.where(~is_iso), format="mixed", dayfirst=True, errors="coerce")
    return iso.fillna(local)


def _read_csv_export(content: bytes) -> pd.DataFrame:
    """Načíta CSV export portálu: skúsi kódovanie UTF-8 aj windows-1250 a odhadne oddeľovač."""
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Export sa nedá dekódovať.")

    if text.lstrip().lower().startswith(("<!doctype", "<html")):
        raise ValueError("Namiesto CSV prišla HTML stránka.")

    try:
        delimiter = csv.Sniffer().sniff(text[:5000], delimiters=";,\t").delimiter
    except csv.Error:
        delimiter = ";"
    return pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str)


def _download_via_export(session: requests.Session) -> pd.DataFrame:
    """Hlavná cesta: stiahne celý zoznam naraz cez CSV export."""
    session.get(PORTAL_LIST, timeout=60)  # najprv otvoríme zoznam, ako by to spravil prehliadač
    response = session.get(PORTAL_EXPORT, timeout=300)
    response.raise_for_status()
    raw_copy = RAW_DIR / "hlasenia_export.csv"
    raw_copy.write_bytes(response.content)
    manifest.zaznamenaj("sk_hlasenia", raw_copy, PORTAL_EXPORT)
    print(f"  Export uložený aj v pôvodnej podobe: {raw_copy}")
    return _normalize_hlasenia(_read_csv_export(response.content))


def _parse_list_page(page_html: str) -> list[list[str]]:
    """Z jednej stránky zoznamu vytiahne riadky tabuľky s dátami."""
    rows = []
    for row in re.findall(r"<tr.*?</tr>", page_html, flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip() for c in cells]
        if len(cells) >= 6 and re.match(r"\d{1,2}\.\d{1,2}\.\d{4}", cells[-6]):
            rows.append(cells[-6:])
    return rows


def _download_via_pages(session: requests.Session, max_pages: int = 5000) -> pd.DataFrame:
    """Záložná cesta: prechádza stránky zoznamu jednu po druhej (pomalšie)."""
    all_rows: list[list[str]] = []
    previous_first = None
    for page in range(1, max_pages + 1):
        response = session.get(PORTAL_LIST, params={"goto": page}, timeout=60)
        response.raise_for_status()
        rows = _parse_list_page(response.text)
        if not rows or rows[0] == previous_first:
            break
        previous_first = rows[0]
        all_rows.extend(rows)
        if page % 50 == 0:
            print(f"  Stránka {page}, spolu {len(all_rows):,} hlásení".replace(",", " "))
        time.sleep(PAUSE_SECONDS)
    return _normalize_hlasenia(pd.DataFrame(all_rows, columns=HLASENIA_COLUMNS))


def download_hlasenia() -> Path:
    """Stiahne všetky slovenské hlásenia a uloží ich do data/raw/sk/hlasenia.parquet."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        print("Skúšam CSV export z portálu ŠÚKL…")
        df = _download_via_export(session)
        if len(df) < 1000:
            raise ValueError(f"Export obsahuje len {len(df)} hlásení, asi nie je úplný.")
    except (requests.RequestException, ValueError) as error:
        print(f"  Export nevyšiel ({error}).")
        print("Prechádzam stránky zoznamu jednu po druhej (môže to trvať 15–20 minút)…")
        df = _download_via_pages(session)
        zo_stranok = True
    else:
        zo_stranok = False

    df = df.drop_duplicates().sort_values("datum_podania").reset_index(drop=True)
    df.to_parquet(HLASENIA_FILE, index=False)
    if zo_stranok:  # pri prechádzaní stránok nemáme pôvodný súbor, zaznamenáme uložené dáta
        manifest.zaznamenaj("sk_hlasenia", HLASENIA_FILE, PORTAL_LIST)
    print(f"Uložených {len(df):,} hlásení do {HLASENIA_FILE}".replace(",", " "))
    return HLASENIA_FILE


def load_hlasenia() -> pd.DataFrame:
    """Načíta uložené slovenské hlásenia."""
    if not HLASENIA_FILE.exists():
        raise FileNotFoundError("Hlásenia ešte nie sú stiahnuté. Spusti najprv sťahovanie.")
    return pd.read_parquet(HLASENIA_FILE)


def summarize_hlasenia(df: pd.DataFrame) -> None:
    """Vypíše prehľad slovenských hlásení a koľkým z nich vieme priradiť ATC."""
    print("\n=== Prehľad slovenských hlásení ===")
    print(f"Počet hlásení: {len(df):,}".replace(",", " "))
    print(f"Dátum podania: {df['datum_podania'].min():%d.%m.%Y} až {df['datum_podania'].max():%d.%m.%Y}")
    print(f"Dátum účinnosti: {df['datum_ucinnosti'].min():%d.%m.%Y} až {df['datum_ucinnosti'].max():%d.%m.%Y}")

    print("\nPočet hlásení podľa predmetu:")
    print(df["predmet"].map(PREDMET_NAZVY).value_counts().to_string())

    prerusenia = df[df["predmet"] == "R"]
    print("\nPrerušenia dodávok podľa roka účinnosti:")
    print(prerusenia["datum_ucinnosti"].dt.year.value_counts().sort_index().to_string())

    if REGISTER_FILE.exists():
        register = load_register()[["kod_sukl", "atc"]]
        joined = prerusenia.merge(register, on="kod_sukl", how="left")
        has_atc = joined["atc"].fillna("").str.len() >= 5
        print(f"\nPrerušenia, ktorým vieme z registra priradiť ATC: {has_atc.mean():.0%}")
        print("\nSkupiny ATC s najviac prerušeniami (prvé 3 znaky ATC):")
        print(joined.loc[has_atc, "atc"].str[:3].value_counts().head(10).to_string())


def download_all() -> None:
    """Stiahne všetky SK zdroje."""
    download_register()
    download_hlasenia()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "vsetko"
    if what in ("register", "vsetko"):
        download_register()
        summarize_register(load_register())
    if what in ("hlasenia", "vsetko"):
        download_hlasenia()
        summarize_hlasenia(load_hlasenia())
