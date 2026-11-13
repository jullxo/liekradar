"""Nástroje, ktoré agenti volajú.

Len tenké obaly nad hotovými funkciami z pipeline.analytika. Čísla počíta kód, nie jazykový
model: obal nič neprepočítava, iba prevedie výsledok na JSON (DataFrame -> zoznam záznamov,
najviac MAX_RIADKOV riadkov) a zachová citácie [E00x, Ax] zo stĺpcov `zdroj` a `dovody`.

Dáta sú v data/processed/*.parquet (nie sú v gite, vytvorí ich `python -m pipeline.run_pipeline`).
"""

from __future__ import annotations

import datetime as dt
import math
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
    return vysledok


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
