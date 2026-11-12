"""Zdroje dát pre Českú republiku (SÚKL).

Doplníme po audite dát:
- databáza liekov (ATC, účinná látka, sila, forma, držiteľ registrácie)
- hlásenia o prerušení / obnovení / ukončení dodávok (aj história)
- dodávky distribútorov DIS-13
- ceny a úhrady
- zoznam liekov s obmedzeným vývozom (§ 77c / § 77d)
"""

from pathlib import Path

RAW_DIR = Path("data/raw/cz")


def download_all() -> None:
    """Stiahne všetky CZ zdroje do data/raw/cz."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # TODO: doplniť po audite dát
