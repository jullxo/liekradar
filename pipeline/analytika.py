"""Analytické funkcie LiekRadaru nad tabuľkami v data/processed.

Tieto funkcie volajú agenti ako nástroje a používa ich aj generátor wiki (pipeline.wiki).
Zásada: čísla počíta kód, nie jazykový model. Každý výsledok nesie zdroje vo formáte
[evidenčné ID, Admiralty] podľa vault/manifest_zdrojov.csv.

    stav_liekov(k_datumu=None)                 aktuálny stav každého lieku (dodáva sa / výpadok / zrušené)
    detail_latky(atc)                          prehľad látky v ČR a SR
    posun_latky(atc)                           KIQ2: vlny výpadkov látky v ČR a SR a ich časový posun
    nahrady(krajina, kod)                      KIQ3: náhrady za liek
    konkurenti(atc_prefix, krajina)            KIQ4: výrobcovia v skupine, ich výpadky a zmena podielu počas výpadkov iných
    trhove_medzery(krajina, n=10)              KIQ5: látky s dlhým výpadkom a málo dodávateľmi
    top_rizikove(krajina, atc_prefix, n, k_datumu)   KIQ1: lieky s najvyšším rizikom výpadku
    signaly_rizika(krajina, k_datumu)          KIQ1: signály pre všetky lieky (pre spätný test)

Ukážka v termináli:
    python -m pipeline.analytika J01CR02
"""

from __future__ import annotations

import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

import json

import numpy as np
import pandas as pd

from pipeline.kiq2_posun import ATC_SKUPINY

PROCESSED = Path("data/processed")
RAW = Path("data/raw")
SPOLOCNE_OD = pd.Timestamp("2019-04-15")

# KIQ5: kedy je výpadok "trhová medzera" (tieto čísla musia sedieť s textom KIQ5 v reporte)
MEDZERA_MIN_DNI = 56           # výpadok trvá aspoň 8 týždňov
MEDZERA_MAX_DODAVATELIA = 2    # látku ešte dodávajú najviac 2 výrobcovia
MEDZERA_MAX_DNI = 730          # dlhšie "výpadky" sú skôr ukončený predaj bez hlásenia o zrušení

# KIQ1: okno, v ktorom hľadáme varovné signály
SIGNAL_OKNO_DNI = 60

ZDROJ = {
    ("CZ", "hlasenia"): "[E001, A2]", ("CZ", "lieky"): "[E002, A1]", ("CZ", "dodavky"): "[E003, A2]",
    ("SK", "hlasenia"): "[E005, A2]", ("SK", "lieky"): "[E004, A1]",
}
DRUHA = {"CZ": "SK", "SK": "CZ"}
STAV_PODLA_TYPU = {"prerusenie": "vo výpadku", "zrusenie": "zrušené", "obnovenie": "dodáva sa", "uvedenie": "dodáva sa"}


# ---------------------------------------------------------------------------
# Načítanie dát a pomocné funkcie
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _tab(nazov: str) -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED / f"{nazov}.parquet")
    if "kod" in df.columns:  # české kódy SÚKL majú vždy 7 číslic (DIS-13 ich píše bez núl na začiatku)
        cz = df["krajina"].eq("CZ") if "krajina" in df.columns else pd.Series(True, index=df.index)
        df.loc[cz, "kod"] = df.loc[cz, "kod"].astype(str).str.strip().str.zfill(7)
    return df


@lru_cache(maxsize=None)
def _podla_atc(nazov: str) -> dict:
    """Tabuľka rozdelená podľa ATC kódu, aby sa opakované hľadanie robilo rýchlo."""
    df = _tab(nazov)
    return {atc: skupina for atc, skupina in df.groupby("atc")}


def obnov_cache() -> None:
    """Zabudne načítané tabuľky (po novom behu pipeline)."""
    for funkcia in (_tab, _podla_atc, _stav_cache, _nazvy_atc, _firma_mapa):
        funkcia.cache_clear()


def _dnes() -> pd.Timestamp:
    return pd.Timestamp.today().normalize()


def _datum(hodnota) -> str | None:
    return None if pd.isna(hodnota) else pd.Timestamp(hodnota).strftime("%Y-%m-%d")


def _prazdna(df: pd.DataFrame) -> pd.DataFrame:
    return df.iloc[0:0]


@lru_cache(maxsize=None)
def firma_kluc(nazov) -> str:
    """Zjednotí názov držiteľa registrácie medzi krajinami.

    'Sandoz Pharmaceuticals d.d.' aj 'Sandoz GmbH' -> 'sandoz', 'G.L. Pharma GmbH' -> 'glpharma'.
    Berie prvé slová názvu, kým majú spolu aspoň 4 znaky.
    """
    if nazov is None or (isinstance(nazov, float) and pd.isna(nazov)):
        return ""
    text = unicodedata.normalize("NFKD", str(nazov)).encode("ascii", "ignore").decode().lower()
    kluc = ""
    for slovo in re.findall(r"[a-z0-9]+", text):
        kluc += slovo
        if len(kluc) >= 4:
            break
    return kluc


@lru_cache(maxsize=None)
def _firma_mapa() -> dict:
    """Pre každý kľúč firmy najčastejší celý názov (na zobrazenie)."""
    lieky = _tab("lieky")
    nazvy = lieky["drzitel"].dropna().astype(str)
    df = pd.DataFrame({"kluc": nazvy.map(firma_kluc), "nazov": nazvy})
    return df.groupby("kluc")["nazov"].agg(lambda s: s.value_counts().index[0]).to_dict()


def nazov_firmy(kluc: str) -> str:
    if not kluc:
        return "(držiteľ neuvedený v registri)"
    return _firma_mapa().get(kluc, kluc)


@lru_cache(maxsize=None)
def _nazvy_atc() -> dict:
    """Názvy ATC kódov: z českého číselníka DLP, inak zo slovenského registra (anglicky)."""
    nazvy: dict = {}
    sk = RAW / "sk" / "register.parquet"
    if sk.exists():
        reg = pd.read_parquet(sk)
        if "atc_nazov" in reg:
            nazvy.update(reg.dropna(subset=["atc"]).drop_duplicates("atc").set_index("atc")["atc_nazov"].to_dict())
    for subor in (RAW / "cz" / "dlp").rglob("*.csv") if (RAW / "cz" / "dlp").exists() else []:
        if subor.name.lower().startswith("dlp_atc"):
            try:
                cz = pd.read_csv(subor, sep=";", encoding="cp1250", dtype=str)
                kod = next(c for c in cz.columns if "ATC" in c.upper())
                nazov = next(c for c in cz.columns if "NAZEV" in c.upper() and "EN" not in c.upper().replace("NAZEV", ""))
                nazvy.update(cz.dropna(subset=[kod]).set_index(kod)[nazov].to_dict())
            except (StopIteration, ValueError, KeyError):
                pass
    return {str(k).strip(): str(v).strip() for k, v in nazvy.items() if pd.notna(v)}


def nazov_atc(atc: str) -> str:
    return _nazvy_atc().get(atc, "")


def _posledne_mesiace(k_datumu: pd.Timestamp, pocet: int) -> list:
    """Posledných `pocet` celých mesiacov s dátami o dodávkach, ktoré boli známe k danému dátumu.
    Mesiac berieme až po jeho skončení (SÚKL ho zverejní v nasledujúcom mesiaci)."""
    k_datumu = pd.Timestamp(k_datumu)
    mesiace = sorted(m for m in _tab("dodavky")["mesiac"].dropna().unique()
                     if pd.Timestamp(m) + pd.DateOffset(months=1) <= k_datumu)
    return mesiace[-pocet:]


# ---------------------------------------------------------------------------
# Stav liekov
# ---------------------------------------------------------------------------

@lru_cache(maxsize=32)
def _stav_cache(k_datumu: pd.Timestamp) -> pd.DataFrame:
    hl = _tab("hlasenia").dropna(subset=["datum_ucinnosti"])
    znamy = hl["datum_hlasenia"].isna() | (hl["datum_hlasenia"] <= k_datumu)

    platne = hl[(hl["datum_ucinnosti"] <= k_datumu) & znamy].sort_values("datum_ucinnosti")
    posledne = platne.groupby(["krajina", "kod"]).tail(1)
    stav = pd.DataFrame({
        "krajina": posledne["krajina"], "kod": posledne["kod"], "atc": posledne["atc"],
        "stav": posledne["typ"].map(STAV_PODLA_TYPU), "od": posledne["datum_ucinnosti"],
    })

    buduce = hl[(hl["typ"] == "prerusenie") & (hl["datum_ucinnosti"] > k_datumu)
                & hl["datum_hlasenia"].notna() & (hl["datum_hlasenia"] <= k_datumu)]
    ohlasene = (buduce.sort_values("datum_ucinnosti").groupby(["krajina", "kod"])
                .agg(ohlaseny_vypadok_od=("datum_ucinnosti", "first"), atc_ohlasenia=("atc", "first"))
                .reset_index())
    stav = stav.merge(ohlasene, on=["krajina", "kod"], how="outer")
    stav["atc"] = stav["atc"].fillna(stav.pop("atc_ohlasenia"))
    return stav.reset_index(drop=True)


def stav_liekov(k_datumu=None) -> pd.DataFrame:
    """Stav každého lieku, ktorý má aspoň jedno hlásenie: dodáva sa / vo výpadku / zrušené.

    Lieky bez hlásení v tabuľke nie sú, berieme ich ako bežne dodávané.
    `ohlaseny_vypadok_od` = výrobca už nahlásil budúce prerušenie.
    """
    return _stav_cache(pd.Timestamp(k_datumu or _dnes()).normalize())


def _dodavky_za_mesiace(mesiace: list) -> pd.Series:
    dod = _tab("dodavky")
    return dod[dod["mesiac"].isin(mesiace)].groupby("kod")["baleni_lekarne"].sum()


# ---------------------------------------------------------------------------
# Detail látky
# ---------------------------------------------------------------------------

def detail_latky(atc: str) -> dict:
    """Prehľad účinnej látky (ATC, 7 znakov) v ČR aj SR."""
    atc = atc.strip().upper()
    dnes = _dnes()
    lieky = _podla_atc("lieky").get(atc, _prazdna(_tab("lieky")))
    ep = _podla_atc("epizody").get(atc, _prazdna(_tab("epizody")))
    ep = ep[ep["zaciatok"] >= SPOLOCNE_OD]
    stav = stav_liekov()
    stav = stav[stav["atc"] == atc]

    vysledok = {"atc": atc, "nazov": nazov_atc(atc), "skupina": ATC_SKUPINY.get(atc[:1], ""), "krajiny": {}}
    for krajina in ["CZ", "SK"]:
        l = lieky[lieky["krajina"] == krajina]
        e = ep[(ep["krajina"] == krajina) & ~ep["planovany"]]
        s = stav[stav["krajina"] == krajina]
        vo_vypadku = s[s["stav"] == "vo výpadku"].merge(l[["kod", "nazov", "drzitel"]], on="kod", how="left")
        ohlasene = s[s["ohlaseny_vypadok_od"].notna()].merge(l[["kod", "nazov", "drzitel"]], on="kod", how="left")
        ukoncene = e[~e["trva"]]
        info = {
            "registrovane_balenia": int(len(l)),
            "vyrobcovia": l["drzitel"].dropna().value_counts().head(10).to_dict(),
            "vypadky_od_2019": int(len(e)),
            "vypadky_12m": int((e["zaciatok"] > dnes - pd.Timedelta(days=365)).sum()),
            "median_dlzky_dni": None if ukoncene.empty else float(ukoncene["dlzka_dni"].median()),
            "teraz_vo_vypadku": [
                {"kod": r.kod, "nazov": r.nazov, "drzitel": r.drzitel, "od": _datum(r.od)}
                for r in vo_vypadku.sort_values("od", ascending=False).head(10).itertuples()
            ],
            "pocet_teraz_vo_vypadku": int(len(vo_vypadku)),
            "ohlasene_vypadky": [
                {"kod": r.kod, "nazov": r.nazov, "drzitel": r.drzitel, "od": _datum(r.ohlaseny_vypadok_od)}
                for r in ohlasene.sort_values("ohlaseny_vypadok_od").head(10).itertuples()
            ],
            "zdroje": [ZDROJ[(krajina, "hlasenia")], ZDROJ[(krajina, "lieky")]],
        }
        if krajina == "CZ":
            info["dodavky"] = _dodavky_latky(atc, dnes)
            info["zdroje"].append(ZDROJ[("CZ", "dodavky")])
        vysledok["krajiny"][krajina] = info
    return vysledok


def _dodavky_latky(atc: str, k_datumu: pd.Timestamp) -> dict | None:
    """Dodávky látky do lekární a do zahraničia: posledné 3 mesiace oproti 3 predchádzajúcim."""
    dod = _podla_atc("dodavky").get(atc)
    mesiace = _posledne_mesiace(k_datumu, 6)
    if dod is None or len(mesiace) < 6:
        return None
    po_mesiacoch = dod.groupby("mesiac")[["baleni_lekarne", "baleni_vyvoz"]].sum().reindex(mesiace, fill_value=0)
    teraz, predtym = po_mesiacoch.iloc[3:].sum(), po_mesiacoch.iloc[:3].sum()
    zmena = None if predtym["baleni_lekarne"] <= 0 else teraz["baleni_lekarne"] / predtym["baleni_lekarne"] - 1
    spolu = teraz["baleni_lekarne"] + teraz["baleni_vyvoz"]
    return {
        "obdobie": f"{_datum(mesiace[3])[:7]} až {_datum(mesiace[5])[:7]}",
        "baleni_lekarne_3m": int(teraz["baleni_lekarne"]),
        "zmena_oproti_predch_3m": None if zmena is None else round(float(zmena), 3),
        "baleni_vyvoz_3m": int(teraz["baleni_vyvoz"]),
        "podiel_vyvozu": None if spolu <= 0 else round(float(teraz["baleni_vyvoz"] / spolu), 3),
    }


# ---------------------------------------------------------------------------
# KIQ2: časový posun
# ---------------------------------------------------------------------------

def posun_latky(atc: str) -> dict:
    """Vlny výpadkov látky v ČR a SR a ako sú od seba posunuté (z výstupu pipeline.kiq2_posun)."""
    atc = atc.strip().upper()
    vlny = _tab("kiq2_vlny")
    v = vlny[vlny["atc"] == atc].sort_values("zaciatok")
    cz, sk = v[v["krajina"] == "CZ"], v[v["krajina"] == "SK"]

    dvojice = []
    for vlna in cz.itertuples():
        if sk.empty:
            break
        rozdiel = (sk["zaciatok"] - vlna.zaciatok).dt.days
        najblizsi = rozdiel.loc[rozdiel.abs().idxmin()]
        if abs(najblizsi) <= 60:
            dvojice.append({"cz_zaciatok": _datum(vlna.zaciatok), "rozdiel_dni_sk_minus_cz": int(najblizsi)})

    rozdiely = pd.Series([d["rozdiel_dni_sk_minus_cz"] for d in dvojice], dtype=float)
    skupiny = _tab("kiq2_skupiny").set_index("skupina")
    skupina = skupiny.loc[atc[:1]] if atc[:1] in skupiny.index else None
    return {
        "atc": atc, "nazov": nazov_atc(atc),
        "vlny_cz": int(len(cz)), "vlny_sk": int(len(sk)),
        "posledne_vlny_cz": [_datum(d) for d in cz["zaciatok"].tail(5)],
        "posledne_vlny_sk": [_datum(d) for d in sk["zaciatok"].tail(5)],
        "dvojice_do_60_dni": dvojice[-10:],
        "sucasne_do_7_dni": int((rozdiely.abs() <= 7).sum()),
        "cr_skor_8_60_dni": int(((rozdiely > 7) & (rozdiely <= 60)).sum()),
        "sr_skor_8_60_dni": int(((rozdiely < -7) & (rozdiely >= -60)).sum()),
        "skupina_atc": None if skupina is None else {
            "nazov": skupina.get("nazov"),
            "lift_sucasne": None if pd.isna(skupina.get("lift_sucasne")) else round(float(skupina["lift_sucasne"]), 2),
            "lift_sr_neskor": None if pd.isna(skupina.get("lift_sr_neskor")) else round(float(skupina["lift_sr_neskor"]), 2),
        },
        "zdroje": [ZDROJ[("CZ", "hlasenia")], ZDROJ[("SK", "hlasenia")]],
    }


# ---------------------------------------------------------------------------
# KIQ3: náhrady
# ---------------------------------------------------------------------------

def _sila(text) -> str:
    """Sila v porovnateľnom tvare: '875MG/125MG' aj '875 mg/125 mg' -> '875mg/125mg'."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return re.sub(r"\s+", "", str(text)).lower().replace(",", ".")


def nahrady(krajina: str, kod: str, n: int = 15) -> pd.DataFrame:
    """Náhrady za liek v tej istej krajine.

    1. Lieky s rovnakou účinnou látkou (ATC7), ktoré nie sú vo výpadku ani zrušené
       (v ČR navyše museli byť dodané do lekární za posledné 3 mesiace).
    2. Ak žiadne nie sú, iné látky z rovnakej skupiny (ATC5). Tie môže zameniť len lekár.
    Poradie: bez ohláseného výpadku, odporučené SÚKL pri hlásení, rovnaká sila, rovnaká forma,
    v ČR potom podľa dodávok. Každý liek je raz, ďalšie veľkosti balenia sú v `dalsie_balenia`.
    """
    krajina, kod = krajina.strip().upper(), str(kod).strip()
    lieky = _tab("lieky")
    lieky_kraj = lieky[lieky["krajina"] == krajina]
    povodny = lieky_kraj[lieky_kraj["kod"] == kod]
    if povodny.empty:
        hl = _tab("hlasenia")
        hl = hl[(hl["krajina"] == krajina) & (hl["kod"] == kod)]
        atc = hl["atc"].dropna().iloc[0] if hl["atc"].notna().any() else None
        forma, sila = None, None
    else:
        atc, forma = povodny["atc"].iloc[0], povodny["forma"].iloc[0]
        sila = _sila(povodny["sila"].iloc[0])
    if not atc or pd.isna(atc):
        return pd.DataFrame()

    stav = stav_liekov()
    stav = stav[stav["krajina"] == krajina].set_index("kod")

    odporucene: set = set()
    if krajina == "CZ":
        ep = _tab("epizody")
        posledna = ep[(ep["krajina"] == "CZ") & (ep["kod"] == kod)].sort_values("zaciatok").tail(1)
        if not posledna.empty and pd.notna(posledna["nahrady_kody"].iloc[0]):
            odporucene = set(re.findall(r"\b\d{1,7}\b", str(posledna["nahrady_kody"].iloc[0])))
            odporucene = {k.zfill(7) for k in odporucene}

    dodane = _dodavky_za_mesiace(_posledne_mesiace(_dnes(), 3)) if krajina == "CZ" else pd.Series(dtype=float)
    ma_dodavky = krajina == "CZ" and not dodane.empty

    def kandidati(maska, typ: str) -> pd.DataFrame:
        k = lieky_kraj[maska & (lieky_kraj["kod"] != kod)].copy()
        k["stav"] = k["kod"].map(stav["stav"]).fillna("dodáva sa")
        k["ohlaseny_vypadok_od"] = k["kod"].map(stav["ohlaseny_vypadok_od"])
        k = k[~k["stav"].isin(["vo výpadku", "zrušené"])]
        if ma_dodavky:
            k["baleni_lekarne_3m"] = k["kod"].map(dodane).fillna(0).astype(int)
            k = k[k["baleni_lekarne_3m"] > 0]
        k["typ"] = typ
        k["odporucil_sukl"] = k["kod"].isin(odporucene)
        k["rovnaka_sila"] = k["sila"].map(_sila) == sila if sila else False
        k["rovnaka_forma"] = k["forma"] == forma
        return k

    vysledok = kandidati(lieky_kraj["atc"] == atc, "rovnaká látka")
    if vysledok.empty:
        vysledok = kandidati(lieky_kraj["atc"].fillna("").str[:5] == atc[:5],
                             "iná látka v skupine – zámenu môže urobiť len lekár")
    if vysledok.empty:
        return vysledok

    vysledok["bez_ohlasenia"] = vysledok["ohlaseny_vypadok_od"].isna()  # lieky s ohláseným výpadkom až na koniec
    poradie = ["bez_ohlasenia", "odporucil_sukl", "rovnaka_sila", "rovnaka_forma"] + (
        ["baleni_lekarne_3m"] if ma_dodavky else [])
    vysledok = vysledok.sort_values(poradie, ascending=False)
    # jeden riadok na liek (názov + sila + forma); ostatné veľkosti balenia len spočítame
    liek = vysledok["nazov"].astype(str) + "|" + vysledok["sila"].astype(str) + "|" + vysledok["forma"].astype(str)
    vysledok["dalsie_balenia"] = liek.map(liek.value_counts()) - 1
    vysledok = vysledok[~liek.duplicated()].head(n)
    stlpce = ["kod", "nazov", "doplnok", "atc", "drzitel", "forma", "sila", "typ", "stav", "odporucil_sukl",
              "rovnaka_sila", "ohlaseny_vypadok_od", "dalsie_balenia"] + (["baleni_lekarne_3m"] if ma_dodavky else [])
    vysledok = vysledok[stlpce].reset_index(drop=True)
    vysledok["zdroj"] = ZDROJ[(krajina, "lieky")] + " " + ZDROJ[(krajina, "hlasenia")] + (
        " " + ZDROJ[("CZ", "dodavky")] if ma_dodavky else "")
    return vysledok


# ---------------------------------------------------------------------------
# KIQ4: konkurenti
# ---------------------------------------------------------------------------

def konkurenti(atc_prefix: str, krajina: str) -> pd.DataFrame:
    """Výrobcovia (držitelia registrácie) v skupine ATC: koľko majú výpadkov, a v ČR aj
    aký majú podiel na dodávkach a ako sa im menil podiel, keď mal výpadok niekto iný.

    Firmy sú zlúčené podľa začiatku názvu (Medochemie Ltd, Medochemie Bohemia -> medochemie),
    teda ide o skupinu, nie o jednu právnickú osobu.
    """
    prefix, krajina = atc_prefix.strip().upper(), krajina.strip().upper()
    dnes = _dnes()

    lieky = _tab("lieky")
    l = lieky[(lieky["krajina"] == krajina) & lieky["atc"].fillna("").str.startswith(prefix)].copy()
    if l.empty:
        return pd.DataFrame()
    l["firma"] = l["drzitel"].map(firma_kluc)

    ep = _tab("epizody")
    e = ep[(ep["krajina"] == krajina) & ep["atc"].fillna("").str.startswith(prefix)
           & (ep["zaciatok"] >= SPOLOCNE_OD) & ~ep["planovany"]].copy()
    e["firma"] = e["drzitel"].map(firma_kluc)

    stav = stav_liekov()
    vo_vypadku = stav[(stav["krajina"] == krajina) & (stav["stav"] == "vo výpadku")
                      & stav["atc"].fillna("").str.startswith(prefix)]
    vo_vypadku = vo_vypadku.merge(l[["kod", "firma"]], on="kod", how="inner")

    tab = l.groupby("firma").agg(registrovane_balenia=("kod", "size"))
    tab["vypadky_od_2019"] = e.groupby("firma").size()
    tab["vypadky_12m"] = e[e["zaciatok"] > dnes - pd.Timedelta(days=365)].groupby("firma").size()
    tab["teraz_vo_vypadku"] = vo_vypadku.groupby("firma").size()
    tab["median_dlzky_dni"] = e[~e["trva"]].groupby("firma")["dlzka_dni"].median()
    tab = tab.fillna({"vypadky_od_2019": 0, "vypadky_12m": 0, "teraz_vo_vypadku": 0})
    tab = tab.astype({"vypadky_od_2019": int, "vypadky_12m": int, "teraz_vo_vypadku": int})

    if krajina == "CZ":
        dod = _tab("dodavky")
        dod = dod[dod["atc"].fillna("").str.startswith(prefix)].copy()
        if not dod.empty:
            kod_na_nazov = lieky[lieky["krajina"] == "CZ"].drop_duplicates("drzitel_kod").set_index("drzitel_kod")["drzitel"]
            dod["firma"] = dod["drzitel"].map(kod_na_nazov).fillna(dod["drzitel"]).map(firma_kluc)
            mesiace = _posledne_mesiace(dnes, 12)
            posledny_rok = dod[dod["mesiac"].isin(mesiace)].groupby("firma")["baleni_lekarne"].sum()
            if posledny_rok.sum() > 0:
                tab["podiel_dodavok_12m"] = (posledny_rok / posledny_rok.sum()).round(3)
            zmena = _podiel_pocas_vypadkov(e, dod)
            tab["zmena_podielu_pb"] = zmena["zmena_podielu_pb"]
            tab["vypadkov_konkurencie"] = zmena["vypadkov_konkurencie"].astype("Int64")

    tab.insert(0, "nazov", [nazov_firmy(k) for k in tab.index])
    tab = tab.reset_index().sort_values(["vypadky_od_2019", "registrovane_balenia"], ascending=False)
    zdroje = [ZDROJ[(krajina, "lieky")], ZDROJ[(krajina, "hlasenia")]] + ([ZDROJ[("CZ", "dodavky")]] if krajina == "CZ" else [])
    tab["zdroj"] = " ".join(zdroje)
    return tab.reset_index(drop=True)


def _podiel_pocas_vypadkov(epizody: pd.DataFrame, dod: pd.DataFrame) -> pd.DataFrame:
    """Ako sa firme zmenil podiel na dodávkach látky do lekární, keď mal výpadok iný výrobca
    tej istej látky: 3 mesiace od začiatku výpadku oproti 3 mesiacom pred ním, v percentuálnych
    bodoch, priemer cez všetky také výpadky. Podiel (nie počet balení) odstráni vplyv sezóny,
    napr. viac antibiotík v zime. Len ČR, dodávky sú od 2024."""
    mesacne = dod.groupby(["atc", "mesiac", "firma"])["baleni_lekarne"].sum()
    latky_s_dodavkami = set(mesacne.index.get_level_values(0))
    prvy_mesiac = dod["mesiac"].min()
    posledny_mesiac = dod["mesiac"].max()
    zmeny: dict = {}
    for vypadok in epizody.itertuples():
        if vypadok.atc not in latky_s_dodavkami:
            continue
        zaciatok = pd.Timestamp(vypadok.zaciatok).to_period("M").to_timestamp()
        pred = pd.date_range(zaciatok - pd.DateOffset(months=3), periods=3, freq="MS")
        pocas = pd.date_range(zaciatok, periods=3, freq="MS")
        if pred[0] < prvy_mesiac or pocas[-1] > posledny_mesiac:
            continue
        latka = mesacne.loc[vypadok.atc].unstack(fill_value=0)  # riadky mesiace, stĺpce firmy
        suma_pred = latka.reindex(pred, fill_value=0).sum()
        suma_pocas = latka.reindex(pocas, fill_value=0).sum()
        if suma_pred.sum() == 0 or suma_pocas.sum() == 0:
            continue
        rozdiel = (suma_pocas / suma_pocas.sum() - suma_pred / suma_pred.sum()) * 100
        for firma, pb in rozdiel.items():
            if firma != vypadok.firma:
                zmeny.setdefault(firma, []).append(pb)
    return pd.DataFrame({
        "zmena_podielu_pb": {f: round(float(np.mean(v)), 1) for f, v in zmeny.items()},
        "vypadkov_konkurencie": {f: len(v) for f, v in zmeny.items()},
    })


# ---------------------------------------------------------------------------
# KIQ5: trhové medzery
# ---------------------------------------------------------------------------

def trhove_medzery(krajina: str, n: int = 10, max_dni: int = MEDZERA_MAX_DNI) -> pd.DataFrame:
    """Látky, pri ktorých výpadok trvá aspoň MEDZERA_MIN_DNI dní a dodávajú ich najviac
    MEDZERA_MAX_DODAVATELIA výrobcovia. V ČR je aj veľkosť trhu (balenia mesačne za posledný rok).

    Výpadky dlhšie ako `max_dni` (2 roky) vynecháva: vtedy firma liek pravdepodobne prestala
    predávať a nenahlásila zrušenie, takže nejde o aktuálnu príležitosť.
    """
    krajina = krajina.strip().upper()
    dnes = _dnes()
    stav = stav_liekov()
    stav = stav[stav["krajina"] == krajina]
    vypadky = stav[stav["stav"] == "vo výpadku"].dropna(subset=["atc"]).copy()
    vypadky = vypadky[vypadky["atc"].str.len() == 7]
    vypadky["dni"] = (dnes - vypadky["od"]).dt.days
    vypadky = vypadky[vypadky["dni"] <= max_dni]
    if vypadky.empty:
        return pd.DataFrame()

    lieky = _tab("lieky")
    l = lieky[(lieky["krajina"] == krajina) & lieky["atc"].isin(vypadky["atc"])].copy()
    l["stav"] = l["kod"].map(stav.set_index("kod")["stav"]).fillna("dodáva sa")
    dostupne = l[l["stav"] == "dodáva sa"]
    if krajina == "CZ":
        dodane = _dodavky_za_mesiace(_posledne_mesiace(dnes, 3))
        if not dodane.empty:
            dostupne = dostupne[dostupne["kod"].map(dodane).fillna(0) > 0]
    dodavatelia = dostupne.assign(firma=dostupne["drzitel"].map(firma_kluc)).groupby("atc")["firma"].nunique()

    tab = vypadky.groupby("atc").agg(balenia_vo_vypadku=("kod", "size"), najdlhsi_vypadok_dni=("dni", "max"),
                                    median_vypadku_dni=("dni", "median"))
    tab["dodavatelia_dostupni"] = dodavatelia.reindex(tab.index).fillna(0).astype(int)
    tab = tab[(tab["najdlhsi_vypadok_dni"] >= MEDZERA_MIN_DNI) & (tab["dodavatelia_dostupni"] <= MEDZERA_MAX_DODAVATELIA)]

    triedenie = ["dodavatelia_dostupni", "najdlhsi_vypadok_dni"]
    smer = [True, False]
    if krajina == "CZ":
        dod = _tab("dodavky")
        rok = dod[dod["mesiac"].isin(_posledne_mesiace(dnes, 12))]
        trh = rok.groupby("atc")["baleni_lekarne"].sum() / max(rok["mesiac"].nunique(), 1)
        tab["trh_baleni_mesacne"] = trh.reindex(tab.index).fillna(0).round(0).astype(int)
        triedenie, smer = ["dodavatelia_dostupni", "trh_baleni_mesacne"], [True, False]

    tab = tab.sort_values(triedenie, ascending=smer).head(n).reset_index()
    tab.insert(1, "nazov", tab["atc"].map(nazov_atc))
    zdroje = [ZDROJ[(krajina, "hlasenia")], ZDROJ[(krajina, "lieky")]] + ([ZDROJ[("CZ", "dodavky")]] if krajina == "CZ" else [])
    tab["zdroj"] = " ".join(zdroje)
    return tab


# ---------------------------------------------------------------------------
# KIQ1: riziko výpadku
# ---------------------------------------------------------------------------

VAHY_V0 = {
    "ina_krajina_ta_ista_firma": 0.30,
    "ina_krajina_ta_ista_latka": 0.15,
    "doma_ta_ista_latka": 0.25,
    "historia_lieku": 0.20,
    "spolahlivost_firmy": 0.10,
}
SIGNALY_CZ = ["pokles_dodavok", "podiel_vyvozu"]  # len ČR, z dodávok DIS-13
VAHY_SUBOR = Path(__file__).with_name("vahy_kiq1.json")  # váhy v1 zo spätného testu (pipeline.kiq1_spatny_test)


def _vahy(krajina: str) -> tuple[dict, str]:
    """Váhy signálov: v1 zo spätného testu, ak existujú a boli lepšie ako v0, inak v0."""
    try:
        data = json.loads(VAHY_SUBOR.read_text(encoding="utf-8"))
        v1 = data[krajina]
        return v1["vahy"], v1["popis"]
    except (OSError, KeyError, ValueError):
        return VAHY_V0, "v0 (odhadnuté váhy, bez spätného testu)"


def signaly_rizika(krajina: str, k_datumu=None, atc_prefix: str | None = None) -> pd.DataFrame:
    """Všetky lieky, ktoré k dátumu nie sú vo výpadku, zrušené ani nemajú ohlásený výpadok,
    a pri každom hodnoty signálov 0–1. Používa len to, čo bolo k dátumu známe:
    hlásenia podané najneskôr v ten deň a dodávky za mesiace, ktoré už boli zverejnené."""
    krajina = krajina.strip().upper()
    t = pd.Timestamp(k_datumu or _dnes()).normalize()
    okno_od = t - pd.Timedelta(days=SIGNAL_OKNO_DNI)

    lieky = _tab("lieky")
    l = lieky[(lieky["krajina"] == krajina) & (lieky["atc"].fillna("").str.len() == 7)].copy()
    if atc_prefix:
        l = l[l["atc"].str.startswith(atc_prefix.strip().upper())]
    l["firma"] = l["drzitel"].map(firma_kluc)

    # vylúčime lieky, ktoré k dátumu t už sú vo výpadku, zrušené alebo majú ohlásený výpadok
    stav = stav_liekov(t)
    stav = stav[stav["krajina"] == krajina].set_index("kod")
    vylucene = stav.index[stav["stav"].isin(["vo výpadku", "zrušené"]) | stav["ohlaseny_vypadok_od"].notna()]
    l = l[~l["kod"].isin(set(vylucene))]
    mesiace = _posledne_mesiace(t, 4) if krajina == "CZ" else []
    if krajina == "CZ":  # len lieky, ktoré sa naozaj dodávajú
        if len(mesiace) < 4:
            return pd.DataFrame()
        dodane = _dodavky_za_mesiace(mesiace[-3:])
        l = l[l["kod"].map(dodane).fillna(0) > 0]
    if l.empty:
        return pd.DataFrame()

    ep = _tab("epizody")
    znamy = ep["datum_hlasenia"].isna() | (ep["datum_hlasenia"] <= t)
    ep = ep[znamy & ep["atc"].notna()].copy()
    ep["firma"] = ep["drzitel"].map(firma_kluc)
    nedavne = ep[ep["zaciatok"] > okno_od]  # aj ohlásené do budúcna, ak hlásenie už bolo podané
    druha = nedavne[nedavne["krajina"] == DRUHA[krajina]]
    doma = nedavne[nedavne["krajina"] == krajina]

    latky_druha = set(druha["atc"])
    latka_firma_druha = set(zip(druha["atc"], druha["firma"]))
    doma_kody = doma.groupby("atc")["kod"].apply(set).to_dict()

    minule = ep[(ep["krajina"] == krajina) & (ep["zaciatok"] <= t)]
    historia = minule[minule["zaciatok"] > t - pd.Timedelta(days=3 * 365)].groupby("kod").size()
    rok = minule[minule["zaciatok"] > t - pd.Timedelta(days=365)]
    vypadky_firmy = rok.groupby("firma").size()
    balenia_firmy = lieky[lieky["krajina"] == krajina]["drzitel"].map(firma_kluc).value_counts()
    miera_firmy = (vypadky_firmy / balenia_firmy).reindex(l["firma"]).fillna(0).values

    l["ina_krajina_ta_ista_firma"] = [float((a, f) in latka_firma_druha) for a, f in zip(l["atc"], l["firma"])]
    l["ina_krajina_ta_ista_latka"] = l["atc"].isin(latky_druha).astype(float).values
    l["doma_ta_ista_latka"] = [float(len(doma_kody.get(a, set()) - {k}) > 0) for a, k in zip(l["atc"], l["kod"])]
    l["historia_lieku"] = (l["kod"].map(historia).fillna(0).clip(upper=3) / 3).values
    l["spolahlivost_firmy"] = np.clip(miera_firmy / 0.2, 0, 1)

    if krajina == "CZ":
        dod = _tab("dodavky")
        dod = dod[dod["mesiac"].isin(mesiace)]
        lekarne = dod.pivot_table(index="kod", columns="mesiac", values="baleni_lekarne", aggfunc="sum", fill_value=0)
        lekarne = lekarne.reindex(columns=mesiace, fill_value=0)
        posledny, predtym = lekarne[mesiace[-1]], lekarne[mesiace[:-1]].mean(axis=1)
        pokles = (1 - posledny / predtym.where(predtym > 0)).clip(0, 1).fillna(0)
        vyvoz = dod[dod["mesiac"].isin(mesiace[-3:])].groupby("kod")[["baleni_lekarne", "baleni_vyvoz"]].sum()
        podiel = (vyvoz["baleni_vyvoz"] / vyvoz.sum(axis=1).where(lambda s: s > 0)).fillna(0)
        l["pokles_dodavok"] = l["kod"].map(pokles).fillna(0).values
        l["podiel_vyvozu"] = (l["kod"].map(podiel).fillna(0) / 0.3).clip(0, 1).values

    l["k_datumu"] = t
    return l


def skore_rizika(signaly: pd.DataFrame, vahy: dict) -> pd.Series:
    """Vážený súčet signálov prepočítaný na 0–100 (100 = všetky signály naplno)."""
    spolu = sum(vahy.values()) or 1
    return (sum(signaly[s].astype(float) * v for s, v in vahy.items() if s in signaly) / spolu * 100)


def top_rizikove(krajina: str, atc_prefix: str | None = None, n: int = 10, k_datumu=None,
                 zoskupit: bool = True) -> pd.DataFrame:
    """Lieky bez nahláseného výpadku s najvyšším rizikom, že výpadok príde (KIQ1).

    Skóre 0–100 je vážený súčet signálov. Váhy sú v1 zo spätného testu (súbor vahy_kiq1.json),
    ak ešte neexistuje, odhadnuté v0. Skóre NIE JE pravdepodobnosť.
    `k_datumu` umožňuje spočítať riziko tak, ako by vyzeralo k minulému dátumu.
    `zoskupit=True`: jeden riadok na výrobcu a látku (najrizikovejšie balenie, ostatné kódy
    v `dalsie_kody`).
    """
    krajina = krajina.strip().upper()
    l = signaly_rizika(krajina, k_datumu, atc_prefix)
    if l.empty:
        return pd.DataFrame()
    t = l["k_datumu"].iloc[0]
    vahy, verzia = _vahy(krajina)
    l["skore"] = skore_rizika(l, vahy).round(0).astype(int)

    druha = DRUHA[krajina]
    popis = {
        "ina_krajina_ta_ista_firma": f"rovnaký výrobca nahlásil výpadok tejto látky v {druha} za posledných {SIGNAL_OKNO_DNI} dní {ZDROJ[(druha, 'hlasenia')]}",
        "ina_krajina_ta_ista_latka": f"látka má výpadok v {druha} za posledných {SIGNAL_OKNO_DNI} dní {ZDROJ[(druha, 'hlasenia')]}",
        "doma_ta_ista_latka": f"iné lieky s touto látkou majú v {krajina} nový výpadok {ZDROJ[(krajina, 'hlasenia')]}",
        "historia_lieku": f"liek mal v posledných 3 rokoch výpadky {ZDROJ[(krajina, 'hlasenia')]}",
        "spolahlivost_firmy": f"výrobca mal za posledný rok veľa výpadkov {ZDROJ[(krajina, 'hlasenia')]}",
        "pokles_dodavok": f"dodávky do lekární v poslednom mesiaci klesli oproti predchádzajúcim 3 mesiacom {ZDROJ[('CZ', 'dodavky')]}",
        "podiel_vyvozu": f"veľká časť dodávok ide do zahraničia {ZDROJ[('CZ', 'dodavky')]}",
    }
    pouzite = [s for s, v in vahy.items() if v > 0 and s in l]
    l["dovody"] = ["; ".join(popis[s] for s in pouzite if r[s] > 0) for _, r in l[pouzite].iterrows()]
    l = l[l["skore"] > 0].sort_values(["skore", "kod"], ascending=[False, True])
    stlpce = ["kod", "nazov", "doplnok", "atc", "drzitel", "skore", "dovody"]
    if zoskupit:
        skupina = l["atc"] + "|" + l["firma"]
        ostatne = l.groupby(skupina)["kod"].agg(lambda s: ", ".join(map(str, list(s)[1:11])))
        l = l[~skupina.duplicated()].copy()
        l["dalsie_kody"] = (l["atc"] + "|" + l["firma"]).map(ostatne)
        stlpce.append("dalsie_kody")
    l = l.head(n)
    vysledok = l[stlpce].reset_index(drop=True)
    vysledok.insert(4, "latka", vysledok["atc"].map(nazov_atc))
    vysledok["k_datumu"] = _datum(t)
    vysledok["verzia_modelu"] = verzia
    return vysledok


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.max_colwidth", 60)
    atc = sys.argv[1] if len(sys.argv) > 1 else "J01CR02"

    print(f"=== detail_latky('{atc}') ===")
    d = detail_latky(atc)
    print(d["atc"], d["nazov"], "|", d["skupina"])
    for krajina, info in d["krajiny"].items():
        print(f"  {krajina}: registrované {info['registrovane_balenia']}, výpadky od 2019 {info['vypadky_od_2019']}, "
              f"za 12 mesiacov {info['vypadky_12m']}, teraz vo výpadku {info['pocet_teraz_vo_vypadku']}, "
              f"ohlásené {len(info['ohlasene_vypadky'])}, medián dĺžky {info['median_dlzky_dni']} dní")
        if info.get("dodavky"):
            print(f"      dodávky: {info['dodavky']}")

    print(f"\n=== posun_latky('{atc}') ===")
    p = posun_latky(atc)
    print({k: p[k] for k in ["vlny_cz", "vlny_sk", "sucasne_do_7_dni", "cr_skor_8_60_dni", "sr_skor_8_60_dni"]})

    for krajina in ["CZ", "SK"]:
        vypadok = d["krajiny"][krajina]["teraz_vo_vypadku"]
        if vypadok:
            kod = vypadok[0]["kod"]
            print(f"\n=== nahrady('{krajina}', '{kod}')  ({vypadok[0]['nazov']}) ===")
            print(nahrady(krajina, kod).head(5).drop(columns=["zdroj"]).to_string(index=False))

    print(f"\n=== konkurenti('{atc[:3]}', 'CZ') ===")
    print(konkurenti(atc[:3], "CZ").head(8).drop(columns=["zdroj"]).to_string(index=False))

    for krajina in ["CZ", "SK"]:
        print(f"\n=== trhove_medzery('{krajina}') ===")
        print(trhove_medzery(krajina, 5).drop(columns=["zdroj"]).to_string(index=False))

    print(f"\n=== top_rizikove('SK', '{atc[:3]}') ===")
    riziko = top_rizikove("SK", atc[:3], 5)
    print(riziko.drop(columns=["dovody", "verzia_modelu"]).to_string(index=False))
    if not riziko.empty:
        print(f"\nPrečo {riziko['nazov'].iloc[0]} ({riziko['skore'].iloc[0]} bodov): {riziko['dovody'].iloc[0]}")
