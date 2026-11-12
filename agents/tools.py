"""Nástroje, ktoré agenti volajú.

Zásada: čísla počíta kód, nie jazykový model. Agent iba rozhodne, ktorý nástroj
zavolať, a výsledok interpretuje.

Doplníme po dátovom pipeline:
- top_rizikove_lieky(krajina, atc_skupina, n)
- casovy_posun(atc_skupina)                  # KIQ2
- nahrady(kod_lieku, krajina)                # KIQ3
- konkurenti(atc_skupina, krajina)           # KIQ4
- trhove_medzery(krajina)                    # KIQ5
- hladaj_spravy(dotaz)                       # web / EMA
"""
