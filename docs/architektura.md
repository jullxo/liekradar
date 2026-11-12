# Architektúra LiekRadaru

Tento súbor priebežne dopĺňame. Slúži ako podklad pre kapitolu 4 reportu.

## Vrstvy

1. **Dátová vrstva** (`pipeline/`, raz denne): stiahne dáta SÚKL, ŠÚKL a EMA, spáruje lieky CZ ↔ SK a vypočíta skóre rizika.
2. **Multiagentný systém** (`agents/`, na požiadanie): LangGraph + Gemini.
3. **Webová aplikácia** (`app.py`): Streamlit na Streamlit Community Cloud.

## Agenti a fázy cyklu CI

| Agent | Fáza CI | Úloha |
| --- | --- | --- |
| Orchestrátor | Plánovanie | Rozloží otázku podľa KIQ a vybraného používateľa |
| Zberné agenty (CZ, SK, EÚ/web) | Zber | Načítajú údaje cez nástroje |
| Analytik | Analýza | Riziko, časový posun, náhrady, konkurenti |
| Reportér | Šírenie | Manažérsky brief pre výrobcu alebo lekáreň |
| Spätná väzba používateľa | Spätná väzba | Hodnotenie briefu |

## Externé dáta

Doplníme po audite dát (URL, formát, frekvencia, história).
