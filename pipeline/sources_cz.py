"""Zdroje dát pre Českú republiku (SÚKL).

Spustenie (v priečinku projektu, so zapnutým .venv):
    python -m pipeline.sources_cz            # všetko
    python -m pipeline.sources_cz hlasenia   # len hlásenia
    python -m pipeline.sources_cz dlp        # len databáza liekov
    python -m pipeline.sources_cz dis13      # len dodávky distribútorov

Hotové:
- hlásenia o uvedení, prerušení, ukončení a obnovení dodávok (mr_hlaseni.csv)
- databáza liekov DLP (látka, sila, forma, držiteľ)
- dodávky distribútorov DIS-13 (mesačne po kóde lieku)
"""

import io
import re
import sys
import time
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


# ---------------------------------------------------------------------------
# Databáza liekov DLP
# ---------------------------------------------------------------------------

DLP_DIR = RAW_DIR / "dlp"
DLP_FILE = RAW_DIR / "dlp_lieky.parquet"
DLP_PAGE = "https://opendata.sukl.gov.cz/katalog-otevrenych-dat/databaze-lecivych-pripravku-dlp"


def download_dlp() -> Path:
    """Stiahne DLP (ZIP s viacerými CSV) a hlavnú tabuľku liekov uloží ako Parquet."""
    DLP_DIR.mkdir(parents=True, exist_ok=True)
    url = _find_zip_link(DLP_PAGE, r"DLP.*\.zip$")
    print(f"Sťahujem {url}")
    response = requests.get(url, headers=HEADERS, timeout=300)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(DLP_DIR)
        names = archive.namelist()
    print(f"Rozbalených {len(names)} súborov (číselníky aj hlavná tabuľka).")

    main = [p for p in DLP_DIR.rglob("*.csv") if p.name.lower().startswith("dlp_lecivepripravky")]
    if not main:
        raise FileNotFoundError(f"V DLP chýba dlp_lecivepripravky.csv, súbory: {names[:20]}")
    df = pd.read_csv(main[0], sep=";", encoding="cp1250", dtype=str)
    df.to_parquet(DLP_FILE, index=False)
    print(f"Uložené do {DLP_FILE}")
    return DLP_FILE


def summarize_dlp() -> None:
    df = pd.read_parquet(DLP_FILE)
    print("\n=== Prehľad českej databázy liekov (DLP) ===")
    print(f"Počet liekov (balení): {len(df):,}".replace(",", " "))
    print(f"Stĺpce: {list(df.columns)}")
    print(df.head(3).to_string(index=False))


# ---------------------------------------------------------------------------
# Dodávky distribútorov DIS-13
# ---------------------------------------------------------------------------

DIS13_DIR = RAW_DIR / "dis13"
DIS13_FILE = RAW_DIR / "dis13.parquet"
DIS13_PAGE = "https://opendata.sukl.gov.cz/katalog-otevrenych-dat/dis-13"
DIS13_FROM_YEAR = 2023  # stačia posledné roky: na spätný test aj na prototyp

# Stĺpce DIS-13 v poradí podľa dátového rozhrania SÚKL.
DIS13_COLUMNS = [
    "obdobie", "typ_odberatela", "atc", "kod_sukl", "nazov", "doplnok", "drzitel",
    "krajina_drzitela", "typ_pohybu", "pocet_baleni", "cena_vyrobcu", "ddd_v_baleni",
    "sposob_vydaja", "hradene",
]


def _dis13_links() -> list[str]:
    """Zoznam mesačných CSV a ročných ZIP súborov DIS-13 od roku DIS13_FROM_YEAR."""
    response = requests.get(DIS13_PAGE, headers=HEADERS, timeout=60)
    response.raise_for_status()
    links = re.findall(r'href="([^"]+?\.(?:csv|zip))"', response.text, flags=re.IGNORECASE)
    selected = []
    for link in dict.fromkeys(links):  # bez duplicít, v pôvodnom poradí
        name = link.split("/")[-1]
        if "dis13" not in name.lower() or "rozhrani" in name.lower():
            continue
        years = [int(y) for y in re.findall(r"(20\d\d)", name)]
        if years and max(years) >= DIS13_FROM_YEAR:
            selected.append(urljoin(DIS13_PAGE, link))
    return selected


def _read_dis13_csv(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), sep=";", encoding="cp1250", dtype=str)
    df = df.iloc[:, : len(DIS13_COLUMNS)]
    df.columns = DIS13_COLUMNS[: df.shape[1]]
    return df


def download_dis13() -> Path:
    """Stiahne DIS-13 od roku DIS13_FROM_YEAR a uloží jednu spoločnú tabuľku."""
    DIS13_DIR.mkdir(parents=True, exist_ok=True)
    links = _dis13_links()
    if not links:
        raise RuntimeError("Na stránke DIS-13 som nenašla žiadne súbory na stiahnutie.")
    print(f"Našla som {len(links)} súborov DIS-13 od roku {DIS13_FROM_YEAR}.")

    frames = []
    for url in links:
        name = url.split("/")[-1]
        local = DIS13_DIR / name
        if not local.exists():  # čo už máme, nesťahujeme znova
            print(f"  Sťahujem {name}")
            response = requests.get(url, headers=HEADERS, timeout=300)
            if response.status_code == 404:
                # SÚKL na súbor odkazuje, ale na serveri chýba. Preskočíme ho.
                print(f"  ! {name} na serveri SÚKL neexistuje (404), preskakujem.")
                continue
            response.raise_for_status()
            local.write_bytes(response.content)
            time.sleep(1)
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(local) as archive:
                for inner in archive.namelist():
                    if inner.lower().endswith(".csv"):
                        frames.append(_read_dis13_csv(archive.read(inner)))
        else:
            frames.append(_read_dis13_csv(local.read_bytes()))

    df = pd.concat(frames, ignore_index=True)
    df["obdobie"] = df["obdobie"].str.strip()
    for column in ["pocet_baleni", "cena_vyrobcu", "ddd_v_baleni"]:
        df[column] = pd.to_numeric(df[column].str.replace(",", ".", regex=False), errors="coerce")
    # Ročný ZIP a mesačné CSV sa môžu prekrývať, preto odstránime duplicitné riadky.
    df = df.drop_duplicates()
    df.to_parquet(DIS13_FILE, index=False)
    print(f"Uložených {len(df):,} riadkov do {DIS13_FILE}".replace(",", " "))
    return DIS13_FILE


def summarize_dis13() -> None:
    df = pd.read_parquet(DIS13_FILE)
    print("\n=== Prehľad dodávok distribútorov (DIS-13) ===")
    print(f"Počet riadkov: {len(df):,}".replace(",", " "))
    print(f"Obdobia: {df['obdobie'].min()} až {df['obdobie'].max()} ({df['obdobie'].nunique()} mesiacov)")
    print("\nTypy odberateľov (počet riadkov):")
    print(df["typ_odberatela"].value_counts().to_string())
    lekarne = df[(df["typ_odberatela"] == "LEKARNA") & (df["typ_pohybu"] == "D")]
    po_mesiacoch = lekarne.groupby("obdobie")["pocet_baleni"].sum() / 1e6
    print("\nDodávky do lekární, milióny balení (posledných 6 mesiacov):")
    print(po_mesiacoch.tail(6).round(1).to_string())


def download_all() -> None:
    """Stiahne všetky CZ zdroje."""
    download_hlasenia()
    download_dlp()
    download_dis13()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "vsetko"
    if what in ("hlasenia", "vsetko"):
        download_hlasenia()
        summarize_hlasenia(load_hlasenia())
    if what in ("dlp", "vsetko"):
        download_dlp()
        summarize_dlp()
    if what in ("dis13", "vsetko"):
        download_dis13()
        summarize_dis13()
