"""Párovanie liekov medzi ČR a SR.

Lieky majú v každej krajine iný kód (kód SÚKL vs. kód ŠÚKL), preto ich párujeme
cez ATC kód + účinnú látku + silu + liekovú formu (+ držiteľa registrácie).

Výstup: data/processed/pary_cz_sk.parquet
"""


def run() -> None:
    # TODO: doplniť po normalizácii
    pass
