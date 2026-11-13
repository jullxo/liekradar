"""KIQ1 – spätný test skóre rizika výpadku.

Otázka: keby sme LiekRadar spustili v minulosti, mali by lieky s najvyšším skóre naozaj
častejšie výpadok v nasledujúcich 8 týždňoch ako ostatné lieky?

Postup:
1. Vyberieme dátumy v minulosti (15. deň každého mesiaca).
2. Ku každému dátumu spočítame signály len z toho, čo sa vtedy dalo vedieť
   (analytika.signaly_rizika: hlásenia podané do toho dňa, zverejnené mesiace dodávok).
3. Pozrieme sa, či liek mal výpadok v nasledujúcich HORIZONT_DNI dňoch.
4. Meriame presnosť top 100: koľko zo 100 liekov s najvyšším skóre naozaj malo výpadok,
   a porovnáme to s náhodným výberom (lift).
5. Logistická regresia nájde váhy signálov z dát (v1). Učí sa na starších dátumoch a hodnotí
   sa na novších, ktoré nevidela. Ak je v1 na nových dátumoch lepšia ako v0, uložíme jej váhy
   do pipeline/vahy_kiq1.json a top_rizikove ich začne používať.

Spustenie (po pipeline.normalize):
    python -m pipeline.kiq1_spatny_test

Výstupy:
    data/processed/kiq1_spatny_test.parquet     signály a výsledok pre každý liek a dátum
    pipeline/vahy_kiq1.json                     váhy v1 (len ak sú lepšie ako v0)
    vault/metodika/KIQ1 spätný test.md          zhrnutie do reportu
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from pipeline import analytika as an

HORIZONT_DNI = 56          # 8 týždňov, horizont z KIQ1
TOP_N = 100                # koľko liekov s najvyšším skóre hodnotíme
PODIEL_UCENIA = 2 / 3      # prvé 2/3 dátumov na učenie, posledná 1/3 na overenie
ZACIATOK_SK = pd.Timestamp("2020-01-15")  # po roku spoločných dát, aby história mala zmysel

VYSLEDKY_FILE = an.PROCESSED / "kiq1_spatny_test.parquet"
SPRAVA_FILE = Path("vault/metodika/KIQ1 spätný test.md")

NAZVY_SIGNALOV = {
    "ina_krajina_ta_ista_firma": "výpadok tej istej látky u toho istého výrobcu v druhej krajine",
    "ina_krajina_ta_ista_latka": "výpadok tej istej látky v druhej krajine",
    "doma_ta_ista_latka": "nový výpadok iného lieku s touto látkou doma",
    "historia_lieku": "výpadky tohto lieku za posledné 3 roky",
    "spolahlivost_firmy": "veľa výpadkov výrobcu za posledný rok",
    "pokles_dodavok": "pokles dodávok do lekární (len ČR)",
    "podiel_vyvozu": "veľký podiel vývozu (len ČR)",
}


# ---------------------------------------------------------------------------
# 1.–3. Dátumy, signály a skutočný výsledok
# ---------------------------------------------------------------------------

def _datumy(krajina: str) -> list:
    posledny = an._dnes() - pd.Timedelta(days=HORIZONT_DNI)
    if krajina == "SK":
        zaciatok = ZACIATOK_SK
    else:  # ČR: dodávky DIS-13 máme od 2024, signály potrebujú 4 zverejnené mesiace
        prvy_mesiac = pd.Timestamp(an._tab("dodavky")["mesiac"].min())
        zaciatok = prvy_mesiac + pd.DateOffset(months=4, days=14)
    return list(pd.date_range(zaciatok, posledny, freq="MS") + pd.Timedelta(days=14))


def _vypadky_po(krajina: str, t: pd.Timestamp) -> set:
    """Kódy liekov, ktorým začal výpadok v nasledujúcich HORIZONT_DNI dňoch po dátume t."""
    ep = an._tab("epizody")
    nove = ep[(ep["krajina"] == krajina) & (ep["zaciatok"] > t)
              & (ep["zaciatok"] <= t + pd.Timedelta(days=HORIZONT_DNI))]
    return set(nove["kod"])


def zostav_data() -> pd.DataFrame:
    casti = []
    vsetky = sorted({(t, k) for k in ("CZ", "SK") for t in _datumy(k)})
    print(f"Počítam signály k {len(vsetky)} dátumom (ČR a SR spolu)…")
    for i, (t, krajina) in enumerate(vsetky, 1):
        s = an.signaly_rizika(krajina, t)
        if s.empty:
            continue
        stlpce = ["kod", "atc", "firma"] + list(an.VAHY_V0) + (an.SIGNALY_CZ if krajina == "CZ" else [])
        s = s[stlpce].copy()
        s.insert(0, "krajina", krajina)
        s.insert(1, "datum", t)
        s["vypadok"] = s["kod"].isin(_vypadky_po(krajina, t)).astype(int)
        casti.append(s)
        if i % 10 == 0:
            print(f"  {i}/{len(vsetky)}")
    data = pd.concat(casti, ignore_index=True)
    data[an.SIGNALY_CZ] = data[an.SIGNALY_CZ].fillna(0)
    data.to_parquet(VYSLEDKY_FILE, index=False)
    return data


# ---------------------------------------------------------------------------
# 4. Meranie
# ---------------------------------------------------------------------------

def _top_n(df: pd.DataFrame, stlpec: str) -> pd.DataFrame:
    """Pre každý dátum TOP_N liekov s najvyšším skóre. Pri rovnakom skóre rozhodne náhoda
    (s pevným seedom), aby výsledok nezávisel od poradia kódov."""
    rng = np.random.default_rng(42)
    df = df.assign(_nahoda=rng.random(len(df)))
    return (df.sort_values([stlpec, "_nahoda"], ascending=False)
            .groupby("datum", group_keys=False).head(TOP_N))


def zmeraj(df: pd.DataFrame, stlpec: str) -> dict:
    zaklad = df["vypadok"].mean()
    top = _top_n(df, stlpec)
    presnost = top["vypadok"].mean()
    zachytene = top["vypadok"].sum() / max(df["vypadok"].sum(), 1)
    auc = roc_auc_score(df["vypadok"], df[stlpec]) if df["vypadok"].nunique() == 2 else float("nan")
    return {
        "datumov": df["datum"].nunique(),
        "liekov_na_datum": round(len(df) / max(df["datum"].nunique(), 1)),
        "zakladna_miera": zaklad,
        "presnost_top": presnost,
        "lift_top": presnost / zaklad if zaklad else float("nan"),
        "zachytene_top": zachytene,
        "auc": auc,
    }


def sila_signalov(df: pd.DataFrame, signaly: list) -> pd.DataFrame:
    """Pre každý signál: ako často mal liek výpadok, keď signál bol a keď nebol."""
    riadky = []
    for s in signaly:
        ma = df[s] > 0
        if ma.sum() == 0:
            continue
        s_signalom, bez = df.loc[ma, "vypadok"].mean(), df.loc[~ma, "vypadok"].mean()
        riadky.append({"signal": s, "podiel_liekov_so_signalom": ma.mean(), "vypadok_so_signalom": s_signalom,
                       "vypadok_bez_signalu": bez, "lift": s_signalom / bez if bez else float("nan")})
    return pd.DataFrame(riadky).sort_values("lift", ascending=False)


# ---------------------------------------------------------------------------
# 5. Logistická regresia (v1)
# ---------------------------------------------------------------------------

def nauc_v1(df: pd.DataFrame, signaly: list) -> tuple[dict, pd.Timestamp]:
    datumy = sorted(df["datum"].unique())
    hranica = datumy[int(len(datumy) * PODIEL_UCENIA)]
    ucenie = df[df["datum"] < hranica]
    model = LogisticRegression(max_iter=1000)
    model.fit(ucenie[signaly], ucenie["vypadok"])
    # záporné koeficienty (signál riziko znižuje) nastavíme na 0, aby sa skóre dalo vysvetliť
    koef = np.clip(model.coef_[0], 0, None)
    vahy = {s: round(float(k / koef.sum()), 3) for s, k in zip(signaly, koef)} if koef.sum() > 0 else {}
    return vahy, pd.Timestamp(hranica)


# ---------------------------------------------------------------------------
# Hlavný beh
# ---------------------------------------------------------------------------

def _p(x) -> str:
    return "—" if pd.isna(x) else f"{x * 100:.1f} %".replace(".", ",")


def _tis(x) -> str:
    return f"{int(x):,}".replace(",", " ")


def _c(x, d=2) -> str:
    return "—" if pd.isna(x) else f"{x:.{d}f}".replace(".", ",")


def run(prepocitat: bool = True) -> None:
    data = zostav_data() if prepocitat or not VYSLEDKY_FILE.exists() else pd.read_parquet(VYSLEDKY_FILE)

    vahy_json = {}
    sprava = ["# KIQ1 – spätný test skóre rizika", "",
              f"Generované {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC skriptom `pipeline.kiq1_spatny_test`. "
              "Neupravovať ručne.", "",
              f"**Otázka:** keby LiekRadar bežal v minulosti, mali by lieky s najvyšším skóre častejšie výpadok "
              f"v nasledujúcich {HORIZONT_DNI} dňoch (8 týždňov) ako náhodne vybrané lieky?", "",
              "**Metóda:** k 15. dňu každého mesiaca sme spočítali skóre všetkých liekov, ktoré vtedy neboli "
              "vo výpadku ani nemali ohlásený výpadok, len z informácií známych k tomu dňu "
              "(hlásenia podané do toho dňa, zverejnené mesiace dodávok). Potom sme overili, či liek mal výpadok "
              f"do {HORIZONT_DNI} dní. Presnosť top {TOP_N} = koľko zo {TOP_N} liekov s najvyšším skóre naozaj "
              "malo výpadok. Lift = koľkokrát je to viac ako pri náhodnom výbere. "
              "Váhy v1 sa naučila logistická regresia na starších 2/3 dátumov a hodnotia sa len na novšej 1/3, "
              "ktorú model nevidel. Zdroje: [E001, A2] [E003, A2] [E005, A2] [E002, A1] [E004, A1].", ""]

    for krajina, nazov in (("CZ", "Česko"), ("SK", "Slovensko")):
        df = data[data["krajina"] == krajina].copy()
        if df.empty:
            continue
        signaly = list(an.VAHY_V0) + (an.SIGNALY_CZ if krajina == "CZ" else [])
        df["skore_v0"] = an.skore_rizika(df, an.VAHY_V0)

        vahy_v1, hranica = nauc_v1(df, signaly)
        df["skore_v1"] = an.skore_rizika(df, vahy_v1) if vahy_v1 else 0.0
        test = df[df["datum"] >= hranica]

        celkovo_v0 = zmeraj(df, "skore_v0")
        test_v0, test_v1 = zmeraj(test, "skore_v0"), zmeraj(test, "skore_v1")
        lepsia = bool(vahy_v1) and test_v1["presnost_top"] > test_v0["presnost_top"] and test_v1["auc"] >= test_v0["auc"] - 0.01

        print(f"\n=== {nazov} ===")
        print(f"Dátumy {df['datum'].min():%Y-%m} až {df['datum'].max():%Y-%m}, {celkovo_v0['liekov_na_datum']} liekov na dátum")
        print(f"Náhodný liek má výpadok do {HORIZONT_DNI} dní v {_p(celkovo_v0['zakladna_miera'])} prípadov")
        print(f"v0 celé obdobie: top {TOP_N} presnosť {_p(celkovo_v0['presnost_top'])}, lift {_c(celkovo_v0['lift_top'], 1)}×, AUC {_c(celkovo_v0['auc'])}")
        print(f"Overenie od {hranica:%Y-%m}:  v0 presnosť {_p(test_v0['presnost_top'])} (AUC {_c(test_v0['auc'])}) | "
              f"v1 presnosť {_p(test_v1['presnost_top'])} (AUC {_c(test_v1['auc'])})")
        print(f"Váhy v1: {vahy_v1}")
        print("→ používame v1" if lepsia else "→ ostáva v0 (v1 nebola na nových dátach lepšia)")

        if lepsia:
            vahy_json[krajina] = {
                "vahy": vahy_v1,
                "popis": f"v1 (váhy z logistickej regresie, spätný test od {hranica:%Y-%m}: "
                         f"top {TOP_N} presnosť {_p(test_v1['presnost_top'])}, lift {_c(test_v1['lift_top'], 1)}×)",
                "presnost_top": test_v1["presnost_top"], "lift_top": test_v1["lift_top"], "auc": test_v1["auc"],
                "overenie_od": f"{hranica:%Y-%m-%d}",
            }

        sila = sila_signalov(df, signaly)
        sprava += [f"## {nazov}", "",
                   f"- Obdobie: {df['datum'].min():%m/%Y} – {df['datum'].max():%m/%Y}, {celkovo_v0['datumov']} dátumov, "
                   f"v priemere {_tis(celkovo_v0['liekov_na_datum'])} liekov na dátum.",
                   f"- Náhodne vybraný liek mal výpadok do 8 týždňov v **{_p(celkovo_v0['zakladna_miera'])}** prípadov.", "",
                   "| Model | Obdobie hodnotenia | Presnosť top 100 | Lift | Zachytené výpadky v top 100 | AUC |",
                   "|---|---|---|---|---|---|",
                   f"| v0 (odhadnuté váhy) | celé obdobie | {_p(celkovo_v0['presnost_top'])} | {_c(celkovo_v0['lift_top'], 1)}× | {_p(celkovo_v0['zachytene_top'])} | {_c(celkovo_v0['auc'])} |",
                   f"| v0 (odhadnuté váhy) | od {hranica:%m/%Y} | {_p(test_v0['presnost_top'])} | {_c(test_v0['lift_top'], 1)}× | {_p(test_v0['zachytene_top'])} | {_c(test_v0['auc'])} |",
                   f"| v1 (logistická regresia) | od {hranica:%m/%Y} | {_p(test_v1['presnost_top'])} | {_c(test_v1['lift_top'], 1)}× | {_p(test_v1['zachytene_top'])} | {_c(test_v1['auc'])} |",
                   "", f"**Použitý model: {'v1' if lepsia else 'v0'}.**", "",
                   "Sila jednotlivých signálov (celé obdobie):", "",
                   "| Signál | Lieky so signálom | Výpadok so signálom | Výpadok bez signálu | Lift | Váha v0 | Váha v1 |",
                   "|---|---|---|---|---|---|---|"]
        for r in sila.itertuples():
            sprava.append(f"| {NAZVY_SIGNALOV[r.signal]} | {_p(r.podiel_liekov_so_signalom)} | {_p(r.vypadok_so_signalom)} | "
                          f"{_p(r.vypadok_bez_signalu)} | {_c(r.lift, 1)}× | {_c(an.VAHY_V0.get(r.signal, 0))} | {_c(vahy_v1.get(r.signal, 0))} |")
        sprava.append("")

    sprava += ["## Obmedzenia", "",
               "- Slovenský register je aktuálny stav: v minulých dátumoch chýbajú lieky, ktoré medzitým zanikli, "
               "a sú tam lieky registrované až neskôr.",
               "- Dodávky DIS-13 sú od 2024, preto je test pre ČR kratší a signály z dodávok sú len pre ČR.",
               "- Top 100 zachytí len menšinu všetkých výpadkov (stĺpec Zachytené výpadky). Väčšina výpadkov "
               "prichádza bez varovného signálu v dátach. Model pomáha určiť, ktoré lieky sledovať, výpadky nepredpovedá s istotou.",
               "- V SR nemáme dáta o dodávkach, preto do testu vstupujú všetky registrované balenia vrátane tých, "
               "ktoré sa nepredávajú. Náhodná miera je preto veľmi nízka a lift vysoký. ČR a SR porovnávajte "
               "podľa presnosti top 100, nie podľa liftu.",
               "- Skóre nie je pravdepodobnosť. Presnosť top 100 hovorí, aký podiel z odporúčaného zoznamu "
               "mal v minulosti naozaj výpadok.",
               "- Výpadok počítame podľa dátumu účinnosti v hláseniach SÚKL/ŠÚKL; výpadky, ktoré firma nenahlásila, nevidíme.", ""]

    if vahy_json:
        an.VAHY_SUBOR.write_text(json.dumps(vahy_json, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nVáhy v1 uložené: {an.VAHY_SUBOR}")
    elif an.VAHY_SUBOR.exists():
        an.VAHY_SUBOR.unlink()
    SPRAVA_FILE.parent.mkdir(parents=True, exist_ok=True)
    SPRAVA_FILE.write_text("\n".join(sprava), encoding="utf-8")
    print(f"Zhrnutie do reportu: {SPRAVA_FILE}")


if __name__ == "__main__":
    import sys
    run(prepocitat="--bez-prepoctu" not in sys.argv)
