"""KIQ1 – model strojového učenia (v2: gradient boosting) a porovnanie s v0 a v1.

Gradient boosting (HistGradientBoostingClassifier zo scikit-learn) je súbor stoviek malých
rozhodovacích stromov. Na rozdiel od logistickej regresie (v1) vie nájsť kombinácie, napr.
„injekcia + jediný výrobca látky + zima“. Dostane jednoduché signály z v0 a navyše:

    vypadky_lieku_3r        koľko výpadkov mal liek za posledné 3 roky (presný počet)
    dni_od_vypadku          koľko dní uplynulo od posledného výpadku lieku (prázdne = nikdy)
    vypadky_latky_12m       koľko výpadkov mala látka v krajine za posledný rok
    vypadky_firmy_12m       koľko výpadkov mal výrobca za posledný rok
    vyrobcov_latky          koľko výrobcov má látku registrovanú (1 = krehký trh)
    baleni_latky            koľko balení látky je registrovaných
    velkost_firmy           koľko balení má výrobca registrovaných
    injekcia                injekčná alebo infúzna forma
    mesiac                  mesiac v roku (sezóna)
    skupina_atc, forma      kategórie
    baleni_3m               (len ČR) koľko balení išlo do lekární za posledné 3 mesiace

Hodnotenie je rovnaké ako pri v0 a v1: učenie na starších 2/3 dátumov, overenie na novšej 1/3.
Ak je v2 na overení lepšia, model sa naučí na všetkých dátumoch a uloží do
pipeline/model_kiq1_<krajina>.joblib. Funkcia analytika.top_rizikove ho potom použije.

Spustenie (po pipeline.kiq1_spatny_test, ktorý pripraví dáta):
    python -m pipeline.kiq1_ml

Výstup do reportu: vault/metodika/KIQ1 model ML.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance

from pipeline import analytika as an
from pipeline import kiq1_spatny_test as st

MODEL_DIR = Path(__file__).parent
SPRAVA_FILE = Path("vault/metodika/KIQ1 model ML.md")
PODIEL_NEGATIVNYCH_SK = 0.2   # SR má 51 tisíc balení na dátum; na učenie stačí 20 % liekov bez výpadku
TOP_FORIEM = 40

PRIZNAKY_SPOLOCNE = list(an.VAHY_V0) + [
    "vypadky_lieku_3r", "dni_od_vypadku", "vypadky_latky_12m", "vypadky_firmy_12m",
    "vyrobcov_latky", "baleni_latky", "velkost_firmy", "injekcia", "mesiac", "skupina_atc", "forma",
]
KATEGORIE = ["skupina_atc", "forma"]

NAZVY = dict(st.NAZVY_SIGNALOV) | {
    "vypadky_lieku_3r": "počet výpadkov lieku za 3 roky",
    "dni_od_vypadku": "dni od posledného výpadku lieku",
    "vypadky_latky_12m": "počet výpadkov látky za rok",
    "vypadky_firmy_12m": "počet výpadkov výrobcu za rok",
    "vyrobcov_latky": "počet výrobcov látky",
    "baleni_latky": "počet registrovaných balení látky",
    "velkost_firmy": "veľkosť výrobcu (počet registrácií)",
    "injekcia": "injekčná / infúzna forma",
    "mesiac": "mesiac v roku (sezóna)",
    "skupina_atc": "skupina ATC (1. písmeno)",
    "forma": "lieková forma",
    "baleni_3m": "dodávky do lekární za 3 mesiace (len ČR)",
}


def priznaky_krajiny(krajina: str) -> list:
    return PRIZNAKY_SPOLOCNE + (an.SIGNALY_CZ + ["baleni_3m"] if krajina == "CZ" else [])


# ---------------------------------------------------------------------------
# Príznaky
# ---------------------------------------------------------------------------

def _dni(x) -> np.ndarray:
    return pd.to_datetime(x).values.astype("datetime64[D]").astype(np.int64)


def _udalosti(kluce: pd.Series, datumy: pd.Series):
    """Zoradené udalosti ako jedno číslo kľúč*10^6 + deň, aby sa dalo hľadať naraz (searchsorted)."""
    kody = {k: i for i, k in enumerate(pd.unique(kluce))}
    hodnoty = np.sort(kluce.map(kody).to_numpy(np.int64) * 1_000_000 + _dni(datumy))
    return kody, hodnoty


def _pocet_v_okne(kody: dict, hodnoty: np.ndarray, kluce: pd.Series, t_dni: np.ndarray, okno: int) -> np.ndarray:
    idx = kluce.map(kody)
    ma = idx.notna().to_numpy()
    zaklad = np.where(ma, idx.fillna(0).to_numpy(np.int64), 0) * 1_000_000
    pocet = np.searchsorted(hodnoty, zaklad + t_dni, side="right") - np.searchsorted(hodnoty, zaklad + t_dni - okno, side="right")
    return np.where(ma, pocet, 0)


def _dni_od_posledneho(kody: dict, hodnoty: np.ndarray, kluce: pd.Series, t_dni: np.ndarray) -> np.ndarray:
    idx = kluce.map(kody)
    ma = idx.notna().to_numpy()
    zaklad = np.where(ma, idx.fillna(0).to_numpy(np.int64), 0) * 1_000_000
    pozicia = np.searchsorted(hodnoty, zaklad + t_dni, side="right") - 1
    posledna = hodnoty[np.clip(pozicia, 0, None)]
    platne = ma & (pozicia >= 0) & (posledna // 1_000_000 == zaklad // 1_000_000)
    return np.where(platne, t_dni - posledna % 1_000_000, np.nan)


def pridaj_priznaky(df: pd.DataFrame) -> pd.DataFrame:
    """df musí mať stĺpce krajina, datum, kod, atc, firma a signály v0 (z analytika.signaly_rizika).
    Všetky príznaky používajú len udalosti známe k dátumu (hlásenie podané najneskôr v ten deň)."""
    df = df.copy()
    krajina = df["krajina"].iloc[0]
    t_dni = _dni(df["datum"])

    ep = an._tab("epizody")
    ep = ep[ep["krajina"] == krajina].copy()
    # udalosť je známa až keď je výpadok účinný a zároveň nahlásený
    znama = np.maximum(_dni(ep["zaciatok"]), _dni(ep["datum_hlasenia"].fillna(ep["zaciatok"])))
    ep["znama"] = pd.to_datetime(znama.astype("datetime64[D]"))
    ep["firma"] = ep["drzitel"].map(an.firma_kluc)

    kody, hodnoty = _udalosti(ep["kod"], ep["znama"])
    df["vypadky_lieku_3r"] = _pocet_v_okne(kody, hodnoty, df["kod"], t_dni, 3 * 365)
    df["dni_od_vypadku"] = _dni_od_posledneho(kody, hodnoty, df["kod"], t_dni)
    s_atc = ep.dropna(subset=["atc"])
    kody, hodnoty = _udalosti(s_atc["atc"], s_atc["znama"])
    df["vypadky_latky_12m"] = _pocet_v_okne(kody, hodnoty, df["atc"], t_dni, 365)
    kody, hodnoty = _udalosti(ep["firma"], ep["znama"])
    df["vypadky_firmy_12m"] = _pocet_v_okne(kody, hodnoty, df["firma"], t_dni, 365)

    lieky = an._tab("lieky")
    lieky = lieky[lieky["krajina"] == krajina].copy()
    lieky["firma"] = lieky["drzitel"].map(an.firma_kluc)
    df["vyrobcov_latky"] = df["atc"].map(lieky.groupby("atc")["firma"].nunique()).fillna(0).to_numpy()
    df["baleni_latky"] = df["atc"].map(lieky.groupby("atc").size()).fillna(0).to_numpy()
    df["velkost_firmy"] = df["firma"].map(lieky.groupby("firma").size()).fillna(0).to_numpy()

    forma = df["kod"].map(lieky.drop_duplicates("kod").set_index("kod")["forma"]).fillna("").astype(str).str.upper()
    df["injekcia"] = forma.str.contains(r"\bINJ|\bINF|INJEK|INFUZ", regex=True).astype(int).to_numpy()
    df["forma"] = forma.to_numpy()
    df["skupina_atc"] = df["atc"].fillna("?").str[0].to_numpy()
    df["mesiac"] = pd.to_datetime(df["datum"]).dt.month.to_numpy()

    if krajina == "CZ":
        dod = an._tab("dodavky")
        mesacne = dod.groupby(["kod", "mesiac"])["baleni_lekarne"].sum().unstack(fill_value=0)
        stlpce = sorted(mesacne.columns)
        df["baleni_3m"] = 0.0
        for t in df["datum"].unique():
            zname = [m for m in stlpce if pd.Timestamp(m) + pd.DateOffset(months=1) <= pd.Timestamp(t)][-3:]
            riadky = df["datum"] == t
            if zname:
                df.loc[riadky, "baleni_3m"] = df.loc[riadky, "kod"].map(mesacne[zname].sum(axis=1)).fillna(0).to_numpy()
        df["baleni_3m"] = np.log1p(df["baleni_3m"])
    return df


def _matica(df: pd.DataFrame, krajina: str, kategorie: dict) -> pd.DataFrame:
    """Kategórie prevedieme na čísla podľa slovníka z učenia (neznáme = -1 -> chýbajúca hodnota)."""
    X = df[priznaky_krajiny(krajina)].copy()
    for k in KATEGORIE:
        X[k] = X[k].map(kategorie[k]).astype(float)
    return X.astype(float)


def _slovnik_kategorii(df: pd.DataFrame) -> dict:
    formy = df["forma"].value_counts().head(TOP_FORIEM).index
    return {"skupina_atc": {v: i for i, v in enumerate(sorted(df["skupina_atc"].unique()))},
            "forma": {v: i for i, v in enumerate(formy)}}


def _vzorka_na_ucenie(df: pd.DataFrame, krajina: str) -> pd.DataFrame:
    """V SR necháme všetky lieky s výpadkom a 20 % ostatných (s väčšou váhou), aby sa šetrila pamäť."""
    if krajina != "SK":
        return df.assign(_vaha=1.0)
    rng = np.random.default_rng(42)
    nech = (df["vypadok"] == 1) | (rng.random(len(df)) < PODIEL_NEGATIVNYCH_SK)
    return df[nech].assign(_vaha=np.where(df.loc[nech, "vypadok"] == 1, 1.0, 1 / PODIEL_NEGATIVNYCH_SK))


def _nauc(df: pd.DataFrame, krajina: str, kategorie: dict) -> HistGradientBoostingClassifier:
    """df už má príznaky a stĺpec _vaha (z _vzorka_na_ucenie)."""
    vahy = df["_vaha"].to_numpy() if "_vaha" in df else None
    X = _matica(df, krajina, kategorie)
    model = HistGradientBoostingClassifier(
        learning_rate=0.05, max_iter=300, max_leaf_nodes=31, min_samples_leaf=100,
        l2_regularization=1.0, categorical_features=[c in KATEGORIE for c in X.columns], random_state=42,
    )
    model.fit(X, df["vypadok"], sample_weight=vahy)
    return model


# ---------------------------------------------------------------------------
# Použitie v aplikácii
# ---------------------------------------------------------------------------

def nacitaj_model(krajina: str):
    cesta = MODEL_DIR / f"model_kiq1_{krajina}.joblib"
    if not cesta.exists():
        return None
    try:
        return joblib.load(cesta)
    except Exception:  # napr. iná verzia scikit-learn
        return None


def skoruj(balik: dict, signaly: pd.DataFrame) -> pd.DataFrame:
    """Vráti signály doplnené o príznaky a stĺpec skore 0–100 = percentil rizika medzi všetkými
    liekmi krajiny (99 = medzi 1 % najrizikovejších). Skóre nie je pravdepodobnosť."""
    df = pridaj_priznaky(signaly.assign(datum=signaly["k_datumu"]))
    p = balik["model"].predict_proba(_matica(df, balik["krajina"], balik["kategorie"]))[:, 1]
    df["skore"] = pd.Series(p, index=df.index).rank(pct=True).mul(100).round(0).astype(int).clip(upper=99)
    return df


# ---------------------------------------------------------------------------
# Hlavný beh
# ---------------------------------------------------------------------------

def run() -> None:
    if not st.VYSLEDKY_FILE.exists():
        raise SystemExit("Najprv spusti: python -m pipeline.kiq1_spatny_test")
    data = pd.read_parquet(st.VYSLEDKY_FILE)

    sprava = ["# KIQ1 – porovnanie modelov (v0, v1, v2 strojové učenie)", "",
              f"Generované {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC skriptom `pipeline.kiq1_ml`. Neupravovať ručne.", "",
              "Všetky tri modely sú hodnotené rovnako: učenie na starších 2/3 dátumov, overenie na novšej 1/3, "
              "ktorú model nevidel. v0 = ručne odhadnuté váhy 5 signálov, v1 = logistická regresia na tých istých "
              "signáloch, v2 = gradient boosting (scikit-learn HistGradientBoostingClassifier) s ďalšími príznakmi: "
              "počet výrobcov látky, lieková forma, skupina ATC, sezóna, čas od posledného výpadku, veľkosť výrobcu "
              "a v ČR objem dodávok. Zdroje: [E001, A2] [E002, A1] [E003, A2] [E004, A1] [E005, A2].", ""]

    for krajina, nazov in (("CZ", "Česko"), ("SK", "Slovensko")):
        df = data[data["krajina"] == krajina].reset_index(drop=True)
        if df.empty:
            continue
        signaly = list(an.VAHY_V0) + (an.SIGNALY_CZ if krajina == "CZ" else [])
        datumy = sorted(df["datum"].unique())
        hranica = pd.Timestamp(datumy[int(len(datumy) * st.PODIEL_UCENIA)])

        print(f"\n=== {nazov} ===")
        print("Počítam príznaky a učím model na starších dátumoch…")
        ucenie = pridaj_priznaky(_vzorka_na_ucenie(df[df["datum"] < hranica], krajina))
        kategorie = _slovnik_kategorii(ucenie)
        model = _nauc(ucenie, krajina, kategorie)
        del ucenie

        print("Hodnotím na novších dátumoch…")
        vahy_v1, _ = st.nauc_v1(df, signaly)
        casti, vzorky = [], []
        for d in [x for x in datumy if pd.Timestamp(x) >= hranica]:
            cast = pridaj_priznaky(df[df["datum"] == d])
            cast["skore_v2"] = model.predict_proba(_matica(cast, krajina, kategorie))[:, 1]
            cast["skore_v0"] = an.skore_rizika(cast, an.VAHY_V0)
            cast["skore_v1"] = an.skore_rizika(cast, vahy_v1) if vahy_v1 else 0.0
            casti.append(cast[["datum", "vypadok", "skore_v0", "skore_v1", "skore_v2"]])
            vzorky.append(cast.sample(min(len(cast), 15_000), random_state=42))
        test = pd.concat(casti, ignore_index=True)

        m = {v: st.zmeraj(test, f"skore_{v}") for v in ("v0", "v1", "v2")}
        najlepsi_skor = max(m["v0"]["presnost_top"], m["v1"]["presnost_top"])
        lepsi = m["v2"]["presnost_top"] > najlepsi_skor and m["v2"]["auc"] >= max(m["v0"]["auc"], m["v1"]["auc"]) - 0.01

        for v, popis in (("v0", "odhadnuté váhy"), ("v1", "logistická regresia"), ("v2", "gradient boosting")):
            print(f"  {v} ({popis}): top {st.TOP_N} presnosť {st._p(m[v]['presnost_top'])}, "
                  f"zachytené {st._p(m[v]['zachytene_top'])}, AUC {st._c(m[v]['auc'])}")

        # dôležitosť príznakov: o koľko klesne AUC, keď príznak náhodne pomiešame (na vzorke)
        vzorka = pd.concat(vzorky, ignore_index=True)
        vzorka = vzorka.sample(min(len(vzorka), 150_000), random_state=42)
        dol = permutation_importance(model, _matica(vzorka, krajina, kategorie), vzorka["vypadok"],
                                     scoring="roc_auc", n_repeats=3, random_state=42)
        dolezitost = pd.Series(dol.importances_mean, index=priznaky_krajiny(krajina)).sort_values(ascending=False)

        sprava += [f"## {nazov}", "",
                   f"Overenie od {hranica:%m/%Y}, náhodne vybraný liek mal výpadok do 8 týždňov v "
                   f"{st._p(m['v0']['zakladna_miera'])} prípadov.", "",
                   "| Model | Presnosť top 100 | Zachytené výpadky v top 100 | AUC |", "|---|---|---|---|"]
        for v, popis in (("v0", "v0 odhadnuté váhy"), ("v1", "v1 logistická regresia"), ("v2", "v2 gradient boosting (ML)")):
            sprava.append(f"| {popis} | {st._p(m[v]['presnost_top'])} | {st._p(m[v]['zachytene_top'])} | {st._c(m[v]['auc'])} |")
        sprava += ["", f"**Použitý model: {'v2 (gradient boosting)' if lepsi else 'v2 nebol lepší, ostáva predchádzajúci'}.**", "",
                   "Najdôležitejšie príznaky v2 (o koľko klesne AUC, keď príznak náhodne pomiešame):", "",
                   "| Príznak | Pokles AUC |", "|---|---|"]
        for p, hodnota in dolezitost.head(10).items():
            sprava.append(f"| {NAZVY.get(p, p)} | {st._c(hodnota, 3)} |")
        sprava.append("")

        cesta = MODEL_DIR / f"model_kiq1_{krajina}.joblib"
        if lepsi:
            print("→ v2 je lepší, učím finálny model na všetkých dátumoch a ukladám")
            vsetko = pridaj_priznaky(_vzorka_na_ucenie(df, krajina))
            kategorie_all = _slovnik_kategorii(vsetko)
            finalny = _nauc(vsetko, krajina, kategorie_all)
            del vsetko
            joblib.dump({
                "model": finalny, "krajina": krajina, "kategorie": kategorie_all,
                "popis": f"v2 (gradient boosting, spätný test od {hranica:%Y-%m}: top {st.TOP_N} presnosť "
                         f"{st._p(m['v2']['presnost_top'])}; skóre = percentil rizika, nie pravdepodobnosť)",
                "metriky": {k: float(v) for k, v in m["v2"].items()},
            }, cesta, compress=3)
            print(f"   uložené: {cesta}")
        else:
            print("→ v2 nie je lepší, ostáva v0/v1")
            if cesta.exists():
                cesta.unlink()

    sprava += ["## Ako to čítať", "",
               "- Presnosť top 100: koľko zo 100 liekov s najvyšším skóre naozaj malo výpadok do 8 týždňov.",
               "- Zachytené výpadky: aký podiel všetkých výpadkov v tom období bol v top 100.",
               "- AUC: ako dobre model zoradí všetky lieky (0,5 = náhoda, 1 = dokonalé poradie).",
               "- Ani ML model nevidí príčiny, ktoré vo verejných dátach nie sú (výrobné problémy, nedostatok "
               "suroviny, nárast dopytu). Preto zachytí len časť výpadkov.",
               "- Počet výrobcov a balení látky je z aktuálneho registra, nie z registra k minulému dátumu.", ""]
    SPRAVA_FILE.parent.mkdir(parents=True, exist_ok=True)
    SPRAVA_FILE.write_text("\n".join(sprava), encoding="utf-8")
    print(f"\nZhrnutie do reportu: {SPRAVA_FILE}")


if __name__ == "__main__":
    run()
