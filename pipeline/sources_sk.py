"""Zdroje dát pre Slovenskú republiku (ŠÚKL, MZ SR, NCZI).

Doplníme po audite dát:
- register liekov ŠÚKL (ATC, účinná látka, sila, forma, držiteľ registrácie)
- hlásenia o prerušení / obnovení / zrušení dodávok (aj história)
- rozhodnutia o zákaze vývozu
- kategorizácia MZ SR (ceny a úhrady)
- spotreba liekov NCZI (náhrada za české DIS-13)
"""

from pathlib import Path

RAW_DIR = Path("data/raw/sk")


def download_all() -> None:
    """Stiahne všetky SK zdroje do data/raw/sk."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # TODO: doplniť po audite dát
