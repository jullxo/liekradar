"""Párovanie ČR a SR na úrovni účinnej látky (ATC, 7 znakov) a prvý pohľad na KIQ2.

Spustenie (po pipeline.normalize):
    python -m pipeline.match_cz_sk

Výstup:
    data/processed/pary_atc.parquet   účinné látky, ktoré sú v oboch krajinách,
                                      s počtom liekov a výpadkov v každej z nich
"""

import numpy as np
import pandas as pd

from pipeline.normalize import EPIZODY_FILE, LIEKY_FILE, PROCESSED_DIR, SPOLOCNE_OD, _n

PARY_FILE = PROCESSED_DIR / "pary_atc.parquet"
OKNO_DNI = 180  # výpadky tej istej látky v druhej krajine hľadáme v okne ±180 dní


def build_pary() -> pd.DataFrame:
    lieky = pd.read_parquet(LIEKY_FILE)
    ep = pd.read_parquet(EPIZODY_FILE)
    lieky = lieky[lieky["atc"].fillna("").str.len() == 7]
    ep = ep[(ep["atc"].fillna("").str.len() == 7) & (ep["zaciatok"] >= SPOLOCNE_OD)]

    pocet_liekov = lieky.groupby(["atc", "krajina"]).size().unstack(fill_value=0)
    pocet_vypadkov = ep.groupby(["atc", "krajina"]).size().unstack(fill_value=0)
    pary = (
        pocet_liekov.add_prefix("lieky_").join(pocet_vypadkov.add_prefix("vypadky_"), how="left")
        .fillna(0).astype(int).reset_index()
    )
    for col in ["lieky_CZ", "lieky_SK", "vypadky_CZ", "vypadky_SK"]:
        if col not in pary:
            pary[col] = 0
    return pary[(pary["lieky_CZ"] > 0) & (pary["lieky_SK"] > 0)].reset_index(drop=True)


def _najblizsi_posun(sk: pd.DataFrame, cz: pd.DataFrame) -> pd.Series:
    """Pre každý slovenský výpadok nájde najbližší český výpadok tej istej látky.

    Vracia rozdiel v dňoch (kladný = Česko bolo skôr), alebo NaN, ak v okne nič nie je.
    """
    cz_podla_atc = {atc: np.sort(g["zaciatok"].values) for atc, g in cz.groupby("atc")}
    vysledky = []
    for atc, zaciatok in zip(sk["atc"], sk["zaciatok"].values):
        datumy = cz_podla_atc.get(atc)
        if datumy is None or len(datumy) == 0:
            vysledky.append(np.nan)
            continue
        rozdiely = (zaciatok - datumy) / np.timedelta64(1, "D")
        najblizsi = rozdiely[np.argmin(np.abs(rozdiely))]
        vysledky.append(najblizsi if abs(najblizsi) <= OKNO_DNI else np.nan)
    return pd.Series(vysledky, index=sk.index)


def prvy_pohlad_kiq2() -> None:
    """Predbežný pohľad: predchádzajú české výpadky slovenským? (nie je to ešte záver!)"""
    ep = pd.read_parquet(EPIZODY_FILE)
    ep = ep[(ep["atc"].fillna("").str.len() == 7) & (ep["zaciatok"] >= SPOLOCNE_OD) & ~ep["planovany"]]
    cz, sk = ep[ep.krajina == "CZ"], ep[ep.krajina == "SK"]
    sk = sk[sk["atc"].isin(set(cz["atc"]))]

    posun = _najblizsi_posun(sk, cz)

    # Porovnanie s náhodou: tie isté slovenské výpadky, ale s náhodne pomiešanými ATC kódmi.
    # Ak je skutočná zhoda oveľa vyššia ako náhodná, súvislosť medzi krajinami je reálna.
    rng = np.random.default_rng(42)
    nahodne = sk.copy()
    nahodne["atc"] = rng.permutation(nahodne["atc"].values)
    posun_nahoda = _najblizsi_posun(nahodne, cz)

    print("\n=== Prvý pohľad na KIQ2 (predbežné, na overenie zajtra) ===")
    print(f"Slovenských výpadkov s látkou, ktorá je aj v ČR: {_n(len(sk))}")
    print(f"Podiel, keď mala tá istá látka výpadok aj v ČR do ±{OKNO_DNI} dní: "
          f"{posun.notna().mean():.0%} (pri náhode {posun_nahoda.notna().mean():.0%})")
    zhoda = posun.dropna()
    if len(zhoda):
        print(f"Z nich bolo Česko skôr v {(zhoda > 0).mean():.0%} prípadov, "
              f"medián posunu {zhoda.median():.0f} dní (kladné = Česko skôr).")


def run() -> None:
    pary = build_pary()
    pary.to_parquet(PARY_FILE, index=False)
    print(f"Účinných látok (ATC7) v oboch krajinách: {_n(len(pary))}")
    print("\nLátky s najviac výpadkami na Slovensku od 15. 4. 2019:")
    print(pary.sort_values("vypadky_SK", ascending=False).head(10).to_string(index=False))
    # Presnejšia analýza KIQ2 je v pipeline.kiq2_posun (prvy_pohlad_kiq2 ostáva len pre porovnanie).


if __name__ == "__main__":
    run()
