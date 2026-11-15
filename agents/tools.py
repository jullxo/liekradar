"""Nástroje, ktoré agenti volajú.

Len tenké obaly nad hotovými funkciami z pipeline.analytika. Čísla počíta kód, nie jazykový
model: obal nič neprepočítava, iba prevedie výsledok na JSON (DataFrame -> zoznam záznamov,
najviac MAX_RIADKOV riadkov) a zachová citácie [E00x, Ax] zo stĺpcov `zdroj` a `dovody`.

Dáta sú v data/processed/*.parquet (nie sú v gite, vytvorí ich `python -m pipeline.run_pipeline`).
"""

from __future__ import annotations

import datetime as dt
import math
import re
from typing import Any, Callable

import numpy as np
import pandas as pd

from pipeline import analytika

MAX_RIADKOV = 10


# ---------------------------------------------------------------------------
# Prevod na JSON
# ---------------------------------------------------------------------------

def _hodnota(v: Any) -> Any:
    """Jedna hodnota do JSON: NaN/NA -> None, dátum -> 'YYYY-MM-DD', numpy -> Python."""
    if isinstance(v, dict):
        return {str(k): _hodnota(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, np.ndarray)):
        return [_hodnota(x) for x in list(v)[:MAX_RIADKOV]]
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (pd.Timestamp, dt.datetime, dt.date, np.datetime64)):
        ts = pd.Timestamp(v)
        return None if pd.isna(ts) else ts.strftime("%Y-%m-%d")
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(float(v)) else float(v)
    return v


def tabulka_na_json(df: pd.DataFrame) -> dict:
    """DataFrame -> {'riadkov_spolu', 'spolocne', 'zaznamy'}.

    Stĺpce s rovnakou hodnotou vo všetkých riadkoch (napr. `zdroj`, `verzia_modelu`) sa uvedú
    raz v `spolocne`, aby model nedostal ten istý text desaťkrát. Hodnoty sa nemenia.
    """
    if df is None or df.empty:
        return {"riadkov_spolu": 0, "spolocne": {}, "zaznamy": []}
    vyber = df.head(MAX_RIADKOV)
    spolocne = {}
    if len(vyber) > 1:
        for stlpec in vyber.columns:
            hodnoty = vyber[stlpec].astype(str).unique()
            if len(hodnoty) == 1 and stlpec in ("zdroj", "verzia_modelu", "k_datumu", "typ"):
                spolocne[stlpec] = _hodnota(vyber[stlpec].iloc[0])
    zaznamy = [{k: _hodnota(v) for k, v in riadok.items() if k not in spolocne}
               for riadok in vyber.to_dict("records")]
    return {"riadkov_spolu": int(len(df)), "spolocne": spolocne, "zaznamy": zaznamy}


# ---------------------------------------------------------------------------
# Nástroje (obaly)
# ---------------------------------------------------------------------------

def top_rizikove(krajina: str, atc_prefix: str | None = None, n: int = 10) -> dict:
    """KIQ1: lieky bez nahláseného výpadku s najvyšším skóre rizika (0–100, nie je pravdepodobnosť)."""
    return tabulka_na_json(analytika.top_rizikove(krajina, atc_prefix or None, min(n, MAX_RIADKOV)))


def detail_latky(atc: str) -> dict:
    """Prehľad účinnej látky (ATC7) v ČR aj SR."""
    return _hodnota(analytika.detail_latky(atc))


def posun_latky(atc: str) -> dict:
    """KIQ2: vlny výpadkov látky v ČR a SR a ich časový posun."""
    return _hodnota(analytika.posun_latky(atc))


def nahrady(krajina: str, kod: str, n: int = 15) -> dict:
    """KIQ3: náhrady za liek (kód SÚKL/ŠÚKL) v tej istej krajine.

    Navyše k výsledku pipeline: `povodny_liek` (názov, forma a sila pôvodného lieku z registra)
    a pri každom zázname `rovnaka_forma` (forma kandidáta == forma pôvodného lieku). Výsledok
    analytika.nahrady sa nemení; je to len vyhľadanie v registri a porovnanie dvoch textov.
    """
    vysledok = tabulka_na_json(analytika.nahrady(krajina, kod, n))
    povodny = _povodny_liek(krajina, kod)
    if povodny:
        vysledok["povodny_liek"] = povodny
        for z in vysledok["zaznamy"]:
            z["rovnaka_forma"] = z.get("forma") == povodny["forma"]
            z["ine_balenie_toho_isteho"] = _nazov_sila(z) == _nazov_sila(povodny)
    return vysledok


def _nazov_sila(r: dict) -> tuple:
    """Rovnaký názov a sila = ten istý liek (iný kód je len iné balenie)."""
    return _kluc_lieku(r)[:2]


def _kluc_lieku(r: dict) -> tuple:
    """Ten istý liek v inej veľkosti balenia: rovnaký názov, sila a forma."""
    def norm(x):
        return re.sub(r"\s+", "", str(x or "")).lower().replace(",", ".")
    return norm(r.get("nazov")), norm(r.get("sila")), str(r.get("forma") or "")


def nahrady_za_latku(krajina: str, atc: str, n: int = 5) -> dict:
    """KIQ3: náhrady za liečivo (ATC7) v krajine.

    Z detail_latky(atc) vezme lieky, ktoré sú v krajine teraz vo výpadku, a pre každý zavolá
    analytika.nahrady. Výsledky spojí a ten istý liek (názov + sila + forma) uvedie raz. Vráti len
    dodávané lieky (analytika.nahrady vyraďuje lieky vo výpadku a zrušené), zoradené: odporučil
    ŠÚKL/SÚKL, rovnaká sila, rovnaká forma ako liek vo výpadku, bez ohláseného výpadku. `n` platí na KAŽDÝ
    liek vo výpadku (spolu najviac MAX_RIADKOV záznamov, pri viacerých liekoch sa berú striedavo).
    `rovnaka_forma` platí voči liekom vo výpadku v `za_lieky` (tie s rovnakou formou, ak také sú).
    `ine_balenie_toho_isteho`: rovnaký názov a sila ako liek vo výpadku, len iný kód – nie je to náhrada,
    ale iné balenie toho istého lieku; také sú v samostatnom zozname `ine_balenia_toho_isteho`, nie v `zaznamy`. Ak v krajine nie je nič vo výpadku,
    vráti dodávané lieky tej istej látky (`rovnaka_forma` je vtedy None – nie je s čím porovnať).
    """
    krajina, atc = krajina.strip().upper(), atc.strip().upper()
    detail = analytika.detail_latky(atc)
    info = (detail.get("krajiny") or {}).get(krajina, {})
    povodne = [p for p in (_povodny_liek(krajina, r["kod"]) for r in info.get("teraz_vo_vypadku") or []) if p]

    kandidati: list[tuple[dict, dict | None]] = []
    if povodne:
        rezim = "náhrady za lieky, ktoré sú teraz vo výpadku"
        for p in povodne:
            kandidati += [(r, p) for r in analytika.nahrady(krajina, p["kod"], 15).to_dict("records")]
    else:
        rezim = "v krajine nie je nič vo výpadku – dodávané lieky tej istej látky"
        lieky = analytika._tab("lieky")
        kody = lieky[(lieky["krajina"] == krajina) & (lieky["atc"] == atc)]["kod"].head(2)
        for kod in kody:  # nahrady(kod) vynechá samotný kód, druhý kód ho doplní
            kandidati += [(r, None) for r in analytika.nahrady(krajina, kod, 15).to_dict("records")]

    vo_vypadku = {p["kod"] for p in povodne}
    nazov_sila_vo_vypadku = {_nazov_sila(p) for p in povodne}
    zlucene: dict[tuple, dict] = {}
    for r, za in kandidati:
        kod = str(r["kod"])
        if kod in vo_vypadku:
            continue
        rovnaka_forma = None if za is None else r.get("forma") == za["forma"]
        z = zlucene.get(_kluc_lieku(r))
        if z is None:
            z = zlucene[_kluc_lieku(r)] = {
                "kod": kod, "nazov": _hodnota(r.get("nazov")), "sila": _hodnota(r.get("sila")),
                "forma": _hodnota(r.get("forma")), "typ": _hodnota(r.get("typ")),
                "odporucil_sukl": bool(r.get("odporucil_sukl")), "rovnaka_sila": bool(r.get("rovnaka_sila")),
                "rovnaka_forma": rovnaka_forma, "ohlaseny_vypadok_od": _hodnota(r.get("ohlaseny_vypadok_od")),
                "ine_balenie_toho_isteho": _nazov_sila(r) in nazov_sila_vo_vypadku,
                "za_lieky": [], "dalsie_kody": [], "_za_rovnaka": [], "_za_ina": []}
        else:
            if kod != z["kod"] and kod not in z["dalsie_kody"]:
                z["dalsie_kody"].append(kod)
            z["odporucil_sukl"] |= bool(r.get("odporucil_sukl"))
            z["rovnaka_sila"] |= bool(r.get("rovnaka_sila"))
            if rovnaka_forma is not None:
                z["rovnaka_forma"] = bool(z["rovnaka_forma"]) or rovnaka_forma
        if za is not None:
            popis = f"{za['nazov']} ({za['forma']})"
            zoznam = z["_za_rovnaka"] if rovnaka_forma else z["_za_ina"]
            if popis not in zoznam:
                zoznam.append(popis)
    for z in zlucene.values():  # za ktoré lieky vo výpadku je náhradou: prednostne tie s rovnakou formou
        z["za_lieky"] = z.pop("_za_rovnaka") or z["_za_ina"]
        z.pop("_za_ina")

    poradie = sorted(zlucene.values(), key=lambda z: (z["odporucil_sukl"], z["rovnaka_sila"],
                                                       z["rovnaka_forma"] is not False,
                                                       z["ohlaseny_vypadok_od"] is None), reverse=True)
    zdroje = [analytika.ZDROJ[(krajina, "lieky")], analytika.ZDROJ[(krajina, "hlasenia")]]
    if krajina == "CZ":
        zdroje.append(analytika.ZDROJ[("CZ", "dodavky")])
    return {
        "atc": atc, "latka": detail.get("nazov"), "krajina": krajina, "rezim": rezim,
        "vo_vypadku": [{k: p[k] for k in ("kod", "nazov", "sila", "forma")} for p in povodne],
        "pocet_vo_vypadku": info.get("pocet_teraz_vo_vypadku", 0),
        "riadkov_spolu": len(poradie), "spolocne": {"zdroj": " ".join(zdroje)},
        "zaznamy": _po_lieku([z for z in poradie if not z["ine_balenie_toho_isteho"]], n, MAX_RIADKOV),
        "ine_balenia_toho_isteho": [z for z in poradie if z["ine_balenie_toho_isteho"]][:len(povodne) or 1],
    }


def _po_lieku(zoradene: list[dict], n: int, spolu: int) -> list[dict]:
    """Najviac n náhrad za KAŽDÝ liek vo výpadku (prvý v `za_lieky`) a najviac `spolu` záznamov celkom.
    Ak sa všetko nezmestí, berie sa striedavo, aby žiadny liek vo výpadku (napr. suspenzia) nezostal bez
    náhrady. V rámci lieku platí poradie zoradené."""
    skupiny: dict[str, list[dict]] = {}
    for z in zoradene:
        skupina = skupiny.setdefault((z.get("za_lieky") or [""])[0], [])
        if len(skupina) < n:
            skupina.append(z)
    vyber: list[dict] = []
    while len(vyber) < spolu and any(skupiny.values()):
        for zoznam in skupiny.values():
            if zoznam and len(vyber) < spolu:
                vyber.append(zoznam.pop(0))
    return sorted(vyber, key=zoradene.index)


def _povodny_liek(krajina: str, kod: str) -> dict | None:
    """Pôvodný liek z registra (tabuľka lieky z pipeline), ku ktorému hľadáme náhrady."""
    krajina, kod = krajina.strip().upper(), str(kod).strip()
    lieky = analytika._tab("lieky")
    riadok = lieky[(lieky["krajina"] == krajina) & (lieky["kod"] == kod)]
    if riadok.empty:
        return None
    r = riadok.iloc[0]
    return {"kod": kod, "nazov": _hodnota(r["nazov"]), "doplnok": _hodnota(r["doplnok"]), "forma": _hodnota(r["forma"]),
            "sila": _hodnota(r["sila"]), "zdroj": analytika.ZDROJ[(krajina, "lieky")]}


def konkurenti(atc_prefix: str, krajina: str) -> dict:
    """KIQ4: výrobcovia v skupine ATC, ich výpadky a v ČR podiel na dodávkach."""
    return tabulka_na_json(analytika.konkurenti(atc_prefix, krajina))


def trhove_medzery(krajina: str, n: int = 10) -> dict:
    """KIQ5: látky s dlhým výpadkom a najviac 2 dostupnými dodávateľmi."""
    return tabulka_na_json(analytika.trhove_medzery(krajina, min(n, MAX_RIADKOV)))


# Register nástrojov: názov -> (funkcia, KIQ, povinné argumenty, popis pre orchestrátora)
NASTROJE: dict[str, tuple[Callable[..., dict], str, tuple[str, ...], str]] = {
    "top_rizikove": (top_rizikove, "KIQ1", ("krajina",),
                     "top_rizikove(krajina, atc_prefix=None, n=10): lieky bez nahláseného výpadku "
                     "s najvyšším skóre rizika výpadku (skóre 0–100 je poradie, nie pravdepodobnosť)."),
    "detail_latky": (detail_latky, "KIQ1", ("atc",),
                     "detail_latky(atc): látka (ATC7, napr. J01CR02) v ČR aj SR – výrobcovia, výpadky "
                     "teraz a od 2019, v ČR dodávky."),
    "posun_latky": (posun_latky, "KIQ2", ("atc",),
                    "posun_latky(atc): vlny výpadkov látky (ATC7) v ČR a SR a o koľko dní sú posunuté."),
    "nahrady": (nahrady, "KIQ3", ("krajina", "kod"),
                "nahrady(krajina, kod, n=15): náhrady za konkrétny liek (kód lieku) v tej istej krajine."),
    "nahrady_za_latku": (nahrady_za_latku, "KIQ3", ("krajina", "atc"),
                         "nahrady_za_latku(krajina, atc, n=5): náhrady za liečivo (ATC7, napr. J01CR02) – za lieky, "
                         "ktoré sú v krajine teraz vo výpadku; bez kódu lieku. Použi VŽDY, keď otázka menuje látku "
                         "alebo ATC a pýta sa na náhrady."),
    "konkurenti": (konkurenti, "KIQ4", ("atc_prefix", "krajina"),
                   "konkurenti(atc_prefix, krajina): výrobcovia v skupine ATC, ich výpadky a v ČR podiel "
                   "na dodávkach."),
    "trhove_medzery": (trhove_medzery, "KIQ5", ("krajina",),
                       "trhove_medzery(krajina, n=10): látky s dlhým výpadkom a najviac 2 dodávateľmi "
                       "(príležitosť pre výrobcu)."),
}


def zavolaj(nazov: str, argumenty: dict) -> dict:
    """Zavolá nástroj z registra s argumentmi, ktoré prijíma."""
    funkcia = NASTROJE[nazov][0]
    import inspect

    povolene = inspect.signature(funkcia).parameters
    return funkcia(**{k: v for k, v in argumenty.items() if k in povolene and v is not None})
