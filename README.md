# LiekRadar

Multiagentný systém na včasné varovanie pred výpadkami liekov v Českej a Slovenskej republike.
Tímový projekt v predmete 4IT529 Competitive Intelligence (VŠE, ZS 2026).

## Čo systém robí

- Zbiera verejné dáta SÚKL (CZ), ŠÚKL (SK) a EMA (EÚ).
- Páruje lieky medzi krajinami cez ATC kód, účinnú látku, silu a liekovú formu.
- Počíta skóre rizika výpadku pre každý liek v CZ a SK.
- Multiagentný systém (LangGraph + Gemini) odpovedá na otázky výrobcov generík a lekárenských sietí.
- Výsledky zobrazuje webová aplikácia v Streamlite.

## Štruktúra

```
app.py                  Streamlit aplikácia (vstupný bod)
pipeline/               sťahovanie, čistenie, párovanie dát a skóre rizika
  sources_cz.py         zdroje SÚKL
  sources_sk.py         zdroje ŠÚKL a MZ SR
  sources_eu.py         zdroje EMA
  normalize.py          čistenie a zjednotenie formátov
  match_cz_sk.py        párovanie liekov CZ <-> SK
  risk_score.py         skóre rizika výpadku
  run_pipeline.py       spustí celý pipeline
agents/                 multiagentný systém
  graph.py              LangGraph: orchestrátor -> zber -> analytik -> reportér
  tools.py              nástroje, ktoré agenti volajú (dotazy do dát)
data/raw/               stiahnuté surové dáta (nie sú v gite)
data/processed/         spracované dáta pre aplikáciu
docs/                   dokumentácia architektúry
```

## Spustenie lokálne

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# do .streamlit/secrets.toml vlož svoj GEMINI_API_KEY

python -m pipeline.run_pipeline  # stiahne a spracuje dáta
streamlit run app.py             # spustí aplikáciu
```

## Bezpečnosť

- API kľúč patrí **iba** do `.streamlit/secrets.toml` (lokálne) a do Secrets v Streamlit Cloude.
- `.streamlit/secrets.toml` je v `.gitignore`. Nikdy ho necommitujte.
- Projekt pracuje len s verejnými dátami, bez osobných údajov.
- Ak kľúč unikne, v Google AI Studio vytvorte nový a starý vypnite.

## Tím

Nikola Slivoňová, Emma Schniererová, Adam Havlena, Filip Stehno
