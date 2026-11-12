"""Zdroje dát pre Českú republiku (SÚKL).

Spustenie (v priečinku projektu, so zapnutým .venv):
    python -m pipeline.sources_cz

Zatiaľ hotové:
- hlásenia o uvedení, prerušení, ukončení a obnovení dodávok (mr_hlaseni.csv)

Doplníme neskôr:
- databáza liekov DLP, dodávky distribútorov DIS-13
"""

import io
import re
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

RAW_DIR = Path("data/raw/cz")
HLASENIA_DIR = RAW_DIR / "hlasenia"

# Stránka datasetu v katalógu otvorených dát SÚKL. Odkaz na samotný ZIP z nej
# vyčítame automaticky, aby skript fungoval, aj keď SÚKL súbor premenuje.
HLASENIA_PAGE = (
    "https://opendata.sukl.gov.cz/katalog-otevrenych-dat/"
    "hlaseni-o-uvedeni-preruseni-ukonceni-obnoveni-dodavek-leciveho-pripravku-na-trh"
)

# Slušne sa predstavíme serveru, aby bolo jasné, kto sťahuje.
HEADERS = {"User-Agent": "LiekRadar (studentsky projekt VSE, 4IT529)"}

DATE_COLUMNS = ["PLATNOST_OD", "DATUM_HLASENI", "TERMIN_OBNOVENI"]


def _find_zip_link(page_url: str, name_pattern: str) -> str:
    """Nájde na stránke odkaz na ZIP súbor, ktorého názov zodpovedá vzoru."""
    response = requests.get(page_url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    links = re.findall(r'href="([^"]+?\.zip)"', response.text, flags=re.IGNORECASE)
    for link in links:
        file_name = link.split("/")[-1]
        if re.search(name_pattern, file_name, flags=re.IGNORECASE):
            return urljoin(page_url, link)
    raise RuntimeError(
        f"Na stránke {page_url} som nenašla ZIP so vzorom {name_pattern}. "
        f"Nájdené ZIP odkazy: {links}"
    )


def download_hlasenia() -> Path:
    """Stiahne a rozbalí hlásenia o dodávkach do data/raw/cz/hlasenia."""
    HLASENIA_DIR.mkdir(parents=True, exist_ok=True)

    url = _find_zip_link(HLASENIA_PAGE, r"^MR.*\.zip$")
    print(f"Sťahujem {url}")
    response = requests.get(url, headers=HEADERS, timeout=120)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(HLASENIA_DIR)
        print(f"Rozbalené súbory: {archive.namelist()}")
    return HLASENIA_DIR


def load_hlasenia() -> pd.DataFrame:
    """Načíta mr_hlaseni.csv do tabuľky (DataFrame) a prevedie dátumy."""
    candidates = [
        p for p in HLASENIA_DIR.iterdir()
        if p.suffix.lower() == ".csv"
        and p.name.lower().startswith("mr_hlaseni")
        and "platnost" not in p.name.lower()
    ]
    if not candidates:
        raise FileNotFoundError("Nenašla som mr_hlaseni.csv. Spustila si najprv sťahovanie?")

    # SÚKL používa oddeľovač ; a české kódovanie windows-1250.
    df = pd.read_csv(candidates[0], sep=";", encoding="cp1250", dtype=str)
    for column in DATE_COLUMNS:
        if column in df.columns:
            df[column] = _parse_dates(df[column])
    return df


def _parse_dates(values: pd.Series) -> pd.Series:
    """Prevedie text na dátumy. Zvláda ISO (2023-02-01) aj český formát (01.02.2023)."""
    values = values.str.strip()
    is_iso = values.str.match(r"^\d{4}-", na=False)
    iso = pd.to_datetime(values.where(is_iso), format="mixed", errors="coerce")
    czech = pd.to_datetime(values.where(~is_iso), format="mixed", dayfirst=True, errors="coerce")
    return iso.fillna(czech)


def summarize_hlasenia(df: pd.DataFrame) -> None:
    """Vypíše prvý prehľad o dátach, aby sme vedeli, s čím pracujeme."""
    print("\n=== Prehľad českých hlásení ===")
    print(f"Počet riadkov: {len(df):,}".replace(",", " "))
    print(f"Stĺpce: {list(df.columns)}")

    if "PLATNOST_OD" in df.columns:
        print(f"Platnosť od: {df['PLATNOST_OD'].min():%d.%m.%Y} až {df['PLATNOST_OD'].max():%d.%m.%Y}")

    if "TYP_OZNAMENI" in df.columns:
        print("\nPočet hlásení podľa typu:")
        print(df["TYP_OZNAMENI"].value_counts().to_string())

    preruseni = df[df.get("TYP_OZNAMENI", pd.Series(dtype=str)).str.lower() == "preruseni"]
    if not preruseni.empty and "PLATNOST_OD" in df.columns:
        print("\nPrerušenia dodávok podľa roka (od 2019):")
        po_rokoch = preruseni["PLATNOST_OD"].dt.year.value_counts().sort_index()
        print(po_rokoch[po_rokoch.index >= 2019].to_string())

    if not preruseni.empty and "ATC" in df.columns:
        od_2019 = preruseni[preruseni["PLATNOST_OD"] >= "2019-04-15"]
        print("\nSkupiny ATC s najviac prerušeniami od 15. 4. 2019 (prvé 3 znaky ATC):")
        print(od_2019["ATC"].str[:3].value_counts().head(10).to_string())


def download_all() -> None:
    """Stiahne všetky CZ zdroje (zatiaľ len hlásenia)."""
    download_hlasenia()


if __name__ == "__main__":
    download_hlasenia()
    summarize_hlasenia(load_hlasenia())
