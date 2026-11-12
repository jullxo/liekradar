"""Skóre rizika výpadku (KIQ1).

Pre každý liek, ktorý zatiaľ NEMÁ nahlásený výpadok, počítame riziko 0–100,
že dostane hlásenie o prerušení dodávok v najbližších 4–8 týždňoch.

Signály (váhy doladíme spätným testom):
- výpadok rovnakej látky v druhej krajine (a ako dávno)
- výpadky iných držiteľov registrácie rovnakej látky
- pokles dodávok distribútorov
- obmedzenie / zákaz vývozu
- počet dostupných náhrad
- história výpadkov lieku a držiteľa
- ročné obdobie

Výstup: data/processed/skore_rizika.parquet (aj so zdôvodnením, ktoré signály prispeli)
"""


def run() -> None:
    # TODO: doplniť po párovaní
    pass
