"""Zdroje dát pre Slovenskú republiku (ŠÚKL).

Spustenie (v priečinku projektu, so zapnutým .venv):
    python -m pipeline.sources_sk

Zatiaľ hotové:
- register liekov cez API ŠÚKL (ŠÚKL kód, ATC, držiteľ, forma, balenie)

Doplníme neskôr:
- hlásenia o prerušení/zrušení/obnovení dodávok z portálu ŠÚKL
- kategorizácia MZ SR (ceny a úhrady)
"""

import html
import json
import time
from pathlib import Path

import pandas as pd
import requests

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


def download_all() -> None:
    """Stiahne všetky SK zdroje (zatiaľ len register)."""
    download_register()


if __name__ == "__main__":
    download_register()
    summarize_register(load_register())
