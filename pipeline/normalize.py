"""Spojí surové dáta z ČR a SR do spoločných tabuliek v data/processed/.

Spustenie (v priečinku projektu, so zapnutým .venv):
    python -m pipeline.normalize

Vstupy (musia byť stiahnuté cez sources_cz a sources_sk):
    data/raw/cz/hlasenia/mr_hlaseni.csv, data/raw/cz/dlp_lieky.parquet, data/raw/cz/dis13.parquet
    data/raw/sk/hlasenia.parquet, data/raw/sk/register.parquet

Výstupy (data/processed/):
    lieky.parquet     katalóg liekov oboch krajín (kód, názov, ATC, držiteľ, forma…)
    hlasenia.parquet  všetky hlásenia oboch krajín v jednom tvare
    epizody.parquet   výpadky ako epizódy: začiatok, koniec, dĺžka, či ešte trvajú
    dodavky.parquet   mesačné dodávky v ČR po kóde lieku (lekárne a vývoz)
"""

from pathlib import Path

import pandas as pd

from pipeline import sources_cz, sources_sk


def _n(cislo) -> str:
    """Číslo s medzerami medzi tisíckami: 12345 -> 12 345."""
    return f"{int(cislo):,}".replace(",", " ")


PROCESSED_DIR = Path("data/processed")
LIEKY_FILE = PROCESSED_DIR / "lieky.parquet"
HLASENIA_FILE = PROCESSED_DIR / "hlasenia.parquet"
EPIZODY_FILE = PROCESSED_DIR / "epizody.parquet"
DODAVKY_FILE = PROCESSED_DIR / "dodavky.parquet"

# Spoločné pomenovanie typov hlásení v oboch krajinách.
TYP_CZ = {"zahajeni": "uvedenie", "preruseni": "prerusenie", "obnoveni": "obnovenie", "ukonceni": "zrusenie"}
TYP_SK = {"U": "uvedenie", "R": "prerusenie", "O": "obnovenie", "Z": "zrusenie"}

# Spoločné obdobie, za ktoré máme dáta z oboch krajín.
SPOLOCNE_OD = pd.Timestamp("2019-04-15")


# ---------------------------------------------------------------------------
# Katalóg liekov
# ---------------------------------------------------------------------------

def _cz_drzitelia() -> dict:
    """Preklad skratky držiteľa (napr. ZNB) na názov firmy z číselníka DLP."""
    files = [p for p in sources_cz.DLP_DIR.rglob("*.csv") if p.name.lower().startswith("dlp_organizace")]
    if not files:
        return {}
    org = pd.read_csv(files[0], sep=";", encoding="cp1250", dtype=str)
    code_col = next((c for c in org.columns if "ZKR" in c.upper()), org.columns[0])
    name_col = next((c for c in org.columns if "NAZEV" in c.upper()), org.columns[1])
    return dict(zip(org[code_col].str.strip(), org[name_col].str.strip()))


def build_lieky() -> pd.DataFrame:
    """Spoločný katalóg liekov ČR a SR."""
    dlp = pd.read_parquet(sources_cz.DLP_FILE)
    nazvy = _cz_drzitelia()
    cz = pd.DataFrame({
        "krajina": "CZ",
        "kod": dlp["KOD_SUKL"].str.strip().str.zfill(7),  # DIS-13 píše kódy bez núl na začiatku
        "nazov": dlp["NAZEV"].str.strip(),
        "doplnok": dlp["DOPLNEK"].str.strip(),
        "atc": dlp["ATC_WHO"].str.strip(),
        "drzitel_kod": dlp["DRZ"].str.strip(),
        "drzitel": dlp["DRZ"].str.strip().map(nazvy).fillna(dlp["DRZ"].str.strip()),
        "sila": dlp["SILA"].str.strip(),
        "forma": dlp["FORMA"].str.strip(),
        "cesta_podania": dlp["CESTA"].str.strip(),
        "dodava_sa": dlp["DODAVKY"].str.strip() == "1" if "DODAVKY" in dlp else pd.NA,
    })

    reg = sources_sk.load_register()
    sk = pd.DataFrame({
        "krajina": "SK",
        "kod": reg["kod_sukl"].str.strip(),
        "nazov": reg["nazov"].str.strip(),
        "doplnok": reg["doplnok"].str.strip(),
        "atc": reg["atc"].str.strip(),
        "drzitel_kod": reg["drzitel_kod"].str.strip(),
        "drzitel": reg["drzitel"].str.strip(),
        "sila": reg["sila"],
        "forma": reg["forma_kod"],
        "cesta_podania": reg["cesta_podania"],
        "dodava_sa": pd.NA,
    })
    return pd.concat([cz, sk], ignore_index=True)


# ---------------------------------------------------------------------------
# Hlásenia
# ---------------------------------------------------------------------------

def _rozdel_drzitela(text: pd.Series) -> tuple[pd.Series, pd.Series]:
    """'Viatris Limited (VIM)' -> ('Viatris Limited', 'VIM')."""
    parts = text.str.extract(r"^(.*?)\s*\(([^()]+)\)\s*$")
    return parts[0].fillna(text).str.strip(), parts[1]


def build_hlasenia(lieky: pd.DataFrame) -> pd.DataFrame:
    """Všetky hlásenia oboch krajín v jednom tvare, doplnené o ATC a držiteľa."""
    mr = sources_cz.load_hlasenia()
    cz = pd.DataFrame({
        "krajina": "CZ",
        "kod": mr["KOD_SUKL"].str.strip().str.zfill(7),
        "nazov": mr["NAZEV"].str.strip(),
        "doplnok": mr["DOPLNEK"].str.strip(),
        "atc_hlasenie": mr["ATC"].str.strip(),
        "typ": mr["TYP_OZNAMENI"].str.strip().str.lower().map(TYP_CZ),
        "datum_ucinnosti": mr["PLATNOST_OD"],
        "datum_hlasenia": mr["DATUM_HLASENI"],
        "dovod": mr["DUVOD_PRERUSENI_UKONCENI"],
        "nahrady_kody": mr["NAHRAZUJICI_LP"],
        "nahrady_poznamka": mr["NAHRAZUJICI_LP_POZNAMKA"],
        "predpokladane_obnovenie": mr["TERMIN_OBNOVENI"],
        "drzitel_hlasenie": pd.NA,
    })

    sk_raw = sources_sk.load_hlasenia()
    drzitel, _ = _rozdel_drzitela(sk_raw["drzitel"])
    sk = pd.DataFrame({
        "krajina": "SK",
        "kod": sk_raw["kod_sukl"].str.strip(),
        "nazov": sk_raw["liek"].str.strip(),
        "doplnok": pd.NA,
        "atc_hlasenie": pd.NA,
        "typ": sk_raw["predmet"].map(TYP_SK),
        "datum_ucinnosti": sk_raw["datum_ucinnosti"],
        "datum_hlasenia": sk_raw["datum_podania"],
        "dovod": pd.NA,
        "nahrady_kody": pd.NA,
        "nahrady_poznamka": pd.NA,
        "predpokladane_obnovenie": pd.NaT,
        "drzitel_hlasenie": drzitel,
    })

    hl = pd.concat([cz, sk], ignore_index=True)
    katalog = lieky[["krajina", "kod", "atc", "drzitel"]].drop_duplicates(["krajina", "kod"])
    hl = hl.merge(katalog, on=["krajina", "kod"], how="left")
    # ATC z hlásenia má prednosť, ak chýba, berieme ho z katalógu.
    hl["atc"] = hl["atc_hlasenie"].where(hl["atc_hlasenie"].notna() & (hl["atc_hlasenie"] != ""), hl["atc"])
    hl["drzitel"] = hl["drzitel"].fillna(hl["drzitel_hlasenie"])
    hl = hl.drop(columns=["atc_hlasenie", "drzitel_hlasenie"])
    return hl[hl["typ"].notna()].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Epizódy výpadkov
# ---------------------------------------------------------------------------

def build_epizody(hl: pd.DataFrame, dnes: pd.Timestamp | None = None) -> pd.DataFrame:
    """Z hlásení poskladá epizódy výpadkov: od prerušenia po obnovenie alebo zrušenie.

    Opakované prerušenie počas trvajúceho výpadku berieme ako pokračovanie
    toho istého výpadku. Ak obnovenie nikto nenahlásil, výpadok podľa dát trvá.
    """
    dnes = dnes or pd.Timestamp.today().normalize()
    data = hl.dropna(subset=["datum_ucinnosti"]).sort_values(["krajina", "kod", "datum_ucinnosti"])
    epizody = []
    for (krajina, kod), skupina in data.groupby(["krajina", "kod"], sort=False):
        zaciatok = None
        prvy = None
        for riadok in skupina.itertuples(index=False):
            if riadok.typ == "prerusenie" and zaciatok is None:
                zaciatok, prvy = riadok.datum_ucinnosti, riadok
            elif riadok.typ in ("obnovenie", "zrusenie", "uvedenie") and zaciatok is not None:
                epizody.append(_epizoda(krajina, kod, prvy, zaciatok, riadok.datum_ucinnosti, riadok.typ, dnes))
                zaciatok = None
        if zaciatok is not None:
            epizody.append(_epizoda(krajina, kod, prvy, zaciatok, pd.NaT, None, dnes))
    return pd.DataFrame(epizody)


def _epizoda(krajina, kod, prvy, zaciatok, koniec, koniec_typ, dnes) -> dict:
    trva = pd.isna(koniec)
    dlzka = ((dnes if trva else koniec) - zaciatok).days
    return {
        "krajina": krajina,
        "kod": kod,
        "nazov": prvy.nazov,
        "atc": prvy.atc,
        "drzitel": prvy.drzitel,
        "zaciatok": zaciatok,
        "koniec": koniec,
        "ako_skoncil": {"obnovenie": "obnovenie", "zrusenie": "zrusenie", "uvedenie": "obnovenie"}.get(koniec_typ),
        "trva": trva and zaciatok <= dnes,
        "planovany": zaciatok > dnes,
        "dlzka_dni": max(dlzka, 0),
        "datum_hlasenia": prvy.datum_hlasenia,
        "dovod": prvy.dovod,
        "nahrady_kody": prvy.nahrady_kody,
    }


# ---------------------------------------------------------------------------
# Dodávky (len ČR)
# ---------------------------------------------------------------------------

def build_dodavky() -> pd.DataFrame:
    """Mesačné dodávky po kóde lieku: lekárne a vývoz do zahraničia (vratky odčítané)."""
    dis = pd.read_parquet(sources_cz.DIS13_FILE)
    znamienko = dis["typ_pohybu"].str.strip().map({"D": 1, "V": -1}).fillna(1)
    dis["baleni"] = dis["pocet_baleni"].abs() * znamienko
    vyvoz = {"DISTRIBUTOR_EU", "DISTRIBUTOR_MIMO_EU", "ZAHRANICI"}
    dis["kanal"] = dis["typ_odberatela"].map(lambda t: "vyvoz" if t in vyvoz else ("lekarne" if t == "LEKARNA" else "ostatne"))
    dis = dis[dis["kanal"] != "ostatne"]
    tab = (
        dis.pivot_table(index=["obdobie", "kod_sukl", "atc", "drzitel"], columns="kanal",
                        values="baleni", aggfunc="sum", fill_value=0)
        .reset_index()
        .rename(columns={"kod_sukl": "kod", "lekarne": "baleni_lekarne", "vyvoz": "baleni_vyvoz"})
    )
    for col in ["baleni_lekarne", "baleni_vyvoz"]:
        if col not in tab:
            tab[col] = 0
    tab["mesiac"] = pd.to_datetime(tab["obdobie"].str.replace(".", "-", regex=False) + "-01", errors="coerce")
    tab["kod"] = tab["kod"].str.strip().str.zfill(7)  # v DIS-13 chýbajú nuly na začiatku kódu
    return tab.drop(columns=["obdobie"])


# ---------------------------------------------------------------------------

def run() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("1/4 Katalóg liekov…")
    lieky = build_lieky()
    lieky.to_parquet(LIEKY_FILE, index=False)
    print(f"    {_n(len(lieky))} liekov (CZ {_n(sum(lieky.krajina == 'CZ'))}, SK {_n(sum(lieky.krajina == 'SK'))})")

    print("2/4 Hlásenia…")
    hl = build_hlasenia(lieky)
    hl.to_parquet(HLASENIA_FILE, index=False)
    s_atc = (hl["atc"].fillna("").str.len() >= 5).mean()
    print(f"    {_n(len(hl))} hlásení, s ATC kódom {s_atc:.0%}")

    print("3/4 Epizódy výpadkov…")
    ep = build_epizody(hl)
    ep.to_parquet(EPIZODY_FILE, index=False)
    for krajina in ["CZ", "SK"]:
        e = ep[(ep.krajina == krajina) & (ep.zaciatok >= SPOLOCNE_OD)]
        ukoncene = e[~e.trva & ~e.planovany]
        print(f"    {krajina}: {_n(len(e))} výpadkov od 15. 4. 2019, teraz trvá {_n(int(e.trva.sum()))}, "
              f"ohlásených dopredu {_n(int(e.planovany.sum()))}, medián dĺžky ukončených "
              f"{ukoncene.dlzka_dni.median():.0f} dní")

    print("4/4 Dodávky v ČR…")
    dod = build_dodavky()
    dod.to_parquet(DODAVKY_FILE, index=False)
    print(f"    {_n(len(dod))} riadkov (mesiac × liek)")

    print(f"\nHotovo. Tabuľky sú v {PROCESSED_DIR}")


if __name__ == "__main__":
    run()
