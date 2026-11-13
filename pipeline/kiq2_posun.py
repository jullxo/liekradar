"""KIQ2: Predchádzajú výpadky v ČR výpadkom tej istej látky v SR (alebo naopak)?

Spustenie (po pipeline.normalize a pipeline.match_cz_sk):
    python -m pipeline.kiq2_posun

Postup:
1. Výpadky jednotlivých balení zlúčime do "vĺn" na úrovni účinnej látky (ATC7).
   Vlna začína prvým výpadkom látky po aspoň 90 dňoch pokoja. Tak jedna udalosť
   (napr. výrobca preruší 10 balení naraz) nezaváži 10-krát.
2. Pre každú vlnu v jednej krajine pozrieme, či mala tá istá látka vlnu aj v druhej:
   - súčasne:            rozdiel do ±7 dní
   - druhá krajina neskôr: o 8 až 60 dní neskôr
3. To isté spočítame aj pri náhode: dátumy vĺn ponecháme, ale látky im náhodne
   pomiešame (50-krát). Ak je skutočná zhoda oveľa vyššia ako náhodná, súvislosť
   medzi krajinami je reálna. Pomer skutočnosť / náhoda nazývame "lift".

Výstupy (data/processed/):
    kiq2_vlny.parquet      vlny výpadkov po látkach v oboch krajinách
    kiq2_skupiny.parquet   výsledky podľa ATC skupín (kde je súvislosť najsilnejšia)
"""

import re

import numpy as np
import pandas as pd

from pipeline.match_cz_sk import PARY_FILE
from pipeline.normalize import EPIZODY_FILE, PROCESSED_DIR, SPOLOCNE_OD, _n

VLNY_FILE = PROCESSED_DIR / "kiq2_vlny.parquet"
SKUPINY_FILE = PROCESSED_DIR / "kiq2_skupiny.parquet"

POKOJ_DNI = 90       # koľko dní bez výpadku látky, aby ďalší výpadok bol nová vlna
ZACIATOK_VLNY_DNI = 30  # výpadky do 30 dní od začiatku vlny počítame do nej
SUCASNE_DNI = 7      # "súčasne" = rozdiel do ±7 dní
OKNO_DNI = 60        # "neskôr" = o 8 až 60 dní neskôr
POCET_PERMUTACII = 50

ATC_SKUPINY = {
    "A": "Tráviaci trakt a metabolizmus", "B": "Krv a krvotvorné orgány",
    "C": "Kardiovaskulárny systém", "D": "Dermatologiká", "G": "Urogenitálny systém",
    "H": "Hormóny", "J": "Antiinfektíva (antibiotiká, vakcíny…)",
    "L": "Onkológia a imunomodulácia", "M": "Svaly a kosti", "N": "Nervový systém",
    "P": "Antiparazitiká", "R": "Dýchací systém", "S": "Zmyslové orgány", "V": "Rôzne",
}


def _firma(text) -> str:
    """Zjednoduší názov držiteľa na prvé slovo: 'Sandoz Pharmaceuticals d.d.' -> 'sandoz'."""
    slova = re.findall(r"[a-z0-9]+", str(text).lower())
    return slova[0] if slova else ""


def build_vlny(ep: pd.DataFrame, latky_v_oboch: set, dnes: pd.Timestamp) -> pd.DataFrame:
    """Zlúči výpadky jednotlivých balení do vĺn na úrovni látky."""
    ep = ep[
        ep["atc"].isin(latky_v_oboch)
        & (ep["zaciatok"] >= SPOLOCNE_OD)
        & (ep["zaciatok"] <= dnes)
    ].sort_values(["krajina", "atc", "zaciatok"])

    vlny = []
    for (krajina, atc), skupina in ep.groupby(["krajina", "atc"], sort=False):
        predosly = None
        for riadok in skupina.itertuples(index=False):
            if predosly is None or (riadok.zaciatok - predosly).days > POKOJ_DNI:
                vlny.append({"krajina": krajina, "atc": atc, "zaciatok": riadok.zaciatok,
                             "pocet_vypadkov": 0, "firmy": set()})
            vlna = vlny[-1]
            if (riadok.zaciatok - vlna["zaciatok"]).days <= ZACIATOK_VLNY_DNI:
                vlna["pocet_vypadkov"] += 1
                vlna["firmy"].add(_firma(riadok.drzitel))
            predosly = riadok.zaciatok

    df = pd.DataFrame(vlny)
    if df.empty:
        return df
    df["firmy"] = df["firmy"].map(lambda s: ", ".join(sorted(f for f in s if f)))
    df["skupina"] = df["atc"].str[0]
    return df


def _priznaky(zdroj: pd.DataFrame, ciel: pd.DataFrame, atc_ciel: np.ndarray) -> pd.DataFrame:
    """Pre každú vlnu v zdroji zistí, či mala látka vlnu v cieli súčasne alebo neskôr."""
    dni_ciel = (ciel["zaciatok"].values.astype("datetime64[D]")).astype(np.int64)
    podla_atc: dict[str, np.ndarray] = {}
    for atc, den in zip(atc_ciel, dni_ciel):
        podla_atc.setdefault(atc, []).append(den)
    podla_atc = {k: np.array(v) for k, v in podla_atc.items()}

    dni_zdroj = (zdroj["zaciatok"].values.astype("datetime64[D]")).astype(np.int64)
    sucasne = np.zeros(len(zdroj), dtype=bool)
    neskor = np.zeros(len(zdroj), dtype=bool)
    for i, (atc, den) in enumerate(zip(zdroj["atc"].values, dni_zdroj)):
        dni = podla_atc.get(atc)
        if dni is None:
            continue
        rozdiel = dni - den
        sucasne[i] = np.any(np.abs(rozdiel) <= SUCASNE_DNI)
        neskor[i] = np.any((rozdiel > SUCASNE_DNI) & (rozdiel <= OKNO_DNI))
    return pd.DataFrame({"sucasne": sucasne, "neskor": neskor}, index=zdroj.index)


def porovnaj(zdroj: pd.DataFrame, ciel: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Skutočné príznaky aj ich priemer pri náhodnom pomiešaní látok v cieli."""
    skutocne = _priznaky(zdroj, ciel, ciel["atc"].values)
    rng = np.random.default_rng(seed)
    nahoda = np.zeros((len(zdroj), 2))
    for _ in range(POCET_PERMUTACII):
        p = _priznaky(zdroj, ciel, rng.permutation(ciel["atc"].values))
        nahoda += p[["sucasne", "neskor"]].values
    nahoda /= POCET_PERMUTACII
    vysledok = skutocne.copy()
    vysledok["sucasne_nahoda"] = nahoda[:, 0]
    vysledok["neskor_nahoda"] = nahoda[:, 1]
    return vysledok


def _riadok(nazov: str, skutocne: float, nahoda: float) -> str:
    lift = skutocne / nahoda if nahoda > 0 else float("nan")
    return f"  {nazov:<34} {skutocne:6.1%}   pri náhode {nahoda:6.1%}   lift {lift:4.1f}×"


def run() -> None:
    dnes = pd.Timestamp.today().normalize()
    ep = pd.read_parquet(EPIZODY_FILE)
    ep = ep[~ep["planovany"] & (ep["atc"].fillna("").str.len() == 7)]
    latky_v_oboch = set(pd.read_parquet(PARY_FILE)["atc"])

    vlny = build_vlny(ep, latky_v_oboch, dnes)
    vlny.to_parquet(VLNY_FILE, index=False)
    cz_vsetky, sk_vsetky = vlny[vlny.krajina == "CZ"], vlny[vlny.krajina == "SK"]

    # Na "neskôr" potrebujeme 60 dní po vlne, preto vynecháme úplne čerstvé vlny.
    hranica = dnes - pd.Timedelta(days=OKNO_DNI)
    cz, sk = cz_vsetky[cz_vsetky.zaciatok <= hranica], sk_vsetky[sk_vsetky.zaciatok <= hranica]

    print("=== KIQ2: časový posun výpadkov medzi ČR a SR ===")
    print(f"Vlny výpadkov od 15. 4. 2019 (látky v oboch krajinách): ČR {_n(len(cz_vsetky))}, SR {_n(len(sk_vsetky))}")
    print(f"Priemerne výpadkov balení v jednej vlne: ČR {cz_vsetky.pocet_vypadkov.mean():.1f}, "
          f"SR {sk_vsetky.pocet_vypadkov.mean():.1f}")

    cz_sk = porovnaj(cz, sk_vsetky)
    sk_cz = porovnaj(sk, cz_vsetky)

    print("\nKeď má látka novú vlnu výpadkov v ČR, mala vlnu aj v SR:")
    print(_riadok("súčasne (±7 dní)", cz_sk.sucasne.mean(), cz_sk.sucasne_nahoda.mean()))
    print(_riadok("SR neskôr (o 8–60 dní)", cz_sk.neskor.mean(), cz_sk.neskor_nahoda.mean()))
    print("\nKeď má látka novú vlnu výpadkov v SR, mala vlnu aj v ČR:")
    print(_riadok("ČR neskôr (o 8–60 dní)", sk_cz.neskor.mean(), sk_cz.neskor_nahoda.mean()))

    # Súčasné vlny: ide o tú istú firmu? (naznačuje regionálne rozhodnutie výrobcu)
    sucasne_cz = cz[cz_sk.sucasne.values]
    rovnaka_firma = []
    for vlna in sucasne_cz.itertuples(index=False):
        okolie = sk_vsetky[(sk_vsetky.atc == vlna.atc)
                           & ((sk_vsetky.zaciatok - vlna.zaciatok).abs().dt.days <= SUCASNE_DNI)]
        firmy_cz = set(vlna.firmy.split(", ")) - {""}
        firmy_sk = set(", ".join(okolie.firmy).split(", ")) - {""}
        rovnaka_firma.append(bool(firmy_cz & firmy_sk))
    if rovnaka_firma:
        print(f"\nPri súčasných vlnách je v oboch krajinách tá istá firma v {np.mean(rovnaka_firma):.0%} prípadov.")

    # Podľa ATC skupín: kde je súvislosť najsilnejšia
    tab = pd.DataFrame({
        "skupina": cz["skupina"].values,
        "sucasne": cz_sk.sucasne.values, "sucasne_nahoda": cz_sk.sucasne_nahoda.values,
        "sr_neskor": cz_sk.neskor.values, "sr_neskor_nahoda": cz_sk.neskor_nahoda.values,
    })
    skupiny = tab.groupby("skupina").agg(
        vlny_cz=("sucasne", "size"),
        sucasne=("sucasne", "mean"), sucasne_nahoda=("sucasne_nahoda", "mean"),
        sr_neskor=("sr_neskor", "mean"), sr_neskor_nahoda=("sr_neskor_nahoda", "mean"),
    )
    tab_sk = pd.DataFrame({"skupina": sk["skupina"].values,
                           "cr_neskor": sk_cz.neskor.values, "cr_neskor_nahoda": sk_cz.neskor_nahoda.values})
    skupiny = skupiny.join(tab_sk.groupby("skupina").agg(
        vlny_sk=("cr_neskor", "size"), cr_neskor=("cr_neskor", "mean"),
        cr_neskor_nahoda=("cr_neskor_nahoda", "mean")), how="outer")
    for stlpec in ["sucasne", "sr_neskor", "cr_neskor"]:
        skupiny[f"lift_{stlpec}"] = skupiny[stlpec] / skupiny[f"{stlpec}_nahoda"].replace(0, np.nan)
    skupiny.insert(0, "nazov", skupiny.index.map(ATC_SKUPINY))
    skupiny = skupiny.reset_index()
    skupiny.to_parquet(SKUPINY_FILE, index=False)

    zobraz = skupiny[skupiny.vlny_cz.fillna(0) >= 50].sort_values("lift_sucasne", ascending=False)
    print("\nPodľa ATC skupín (len skupiny s aspoň 50 vlnami v ČR):")
    print(f"  {'skupina':<40} {'vlny ČR':>8} {'súčasne':>9} {'lift':>6} {'SR neskôr':>10} {'lift':>6}")
    for r in zobraz.itertuples(index=False):
        print(f"  {r.skupina + ' ' + str(r.nazov):<40} {int(r.vlny_cz):>8} {r.sucasne:>9.0%} "
              f"{r.lift_sucasne:>5.1f}× {r.sr_neskor:>10.0%} {r.lift_sr_neskor:>5.1f}×")

    print(f"\nUložené: {VLNY_FILE}, {SKUPINY_FILE}")


if __name__ == "__main__":
    run()
