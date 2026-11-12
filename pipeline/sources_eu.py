"""Zdroje dát na úrovni EÚ (EMA).

Doplníme po audite dát:
- katalóg nedostatkov liekov EMA
- zoznam kritických liekov Únie
"""

from pathlib import Path

RAW_DIR = Path("data/raw/eu")


def download_all() -> None:
    """Stiahne všetky EÚ zdroje do data/raw/eu."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # TODO: doplniť po audite dát
