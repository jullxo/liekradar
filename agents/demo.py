"""Ukážka multiagentného systému LiekRadar.

    .venv/bin/python -m agents.demo                       # naostro s Gemini
    LIEKRADAR_FAKE_LLM=1 .venv/bin/python -m agents.demo  # bez kľúča, pevné odpovede

Voliteľne vlastná otázka a persona:
    .venv/bin/python -m agents.demo "Kde sú trhové medzery v ČR?" vyrobca
"""

import sys

from agents.graph import spusti

OTAZKA = "Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?"
PERSONA = "lekaren"


def main() -> int:
    otazka = sys.argv[1] if len(sys.argv) > 1 else OTAZKA
    persona = sys.argv[2] if len(sys.argv) > 2 else PERSONA
    print(f"Otázka: {otazka}\nPersona: {persona}\n")
    print("=== Priebeh ===")
    vysledok = spusti(otazka, persona, pri_kroku=print)

    print(f"\n=== Správa ({'schválená kritikom' if vysledok['schvalene'] else 'NESCHVÁLENÁ kritikom'}) ===")
    print(vysledok["brief"] or "(správa nevznikla)")
    print("\n=== Case Log ===")
    print("\n".join(vysledok["case_log"]))
    print(f"\nModel: {vysledok['model']} · volaní modelu: {vysledok['volania_llm']} "
          f"(požiadaviek vrátane opakovaní: {vysledok.get('poziadavky_llm', vysledok['volania_llm'])})")
    for druh, cesta in vysledok["subory"].items():
        print(f"Uložené ({druh}): {cesta}")
    if vysledok["chyba"]:
        print(f"\nCHYBA: {vysledok['chyba']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
