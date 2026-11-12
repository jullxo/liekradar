"""Čistenie a zjednotenie dát z oboch krajín do spoločného formátu.

Cieľové tabuľky (data/processed/, formát Parquet):
- lieky:     krajina, kod_lieku, nazov, atc, ucinna_latka, sila, forma, drzitel
- hlasenia:  krajina, kod_lieku, typ (prerusenie/obnovenie/ukoncenie), datum_ucinnosti, datum_hlasenia, dovod
- dodavky:   krajina, kod_lieku, obdobie, pocet_baleni
"""


def run() -> None:
    # TODO: doplniť po audite dát
    pass
