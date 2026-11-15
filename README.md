# LiekRadar

**Včasné varovanie pred výpadkami liekov v Česku a na Slovensku.**

🔗 **Aplikácia online: <https://liekradar.streamlit.app>**

LiekRadar je multiagentný systém pre competitive intelligence. Z verejných dát liekových úradov SÚKL (ČR)
a ŠÚKL (SR) predpovedá, ktorým liekom hrozí výpadok, navrhuje náhrady a ukazuje medzery na trhu.
Pomáha nákupcom lekárenských sietí a výrobcom a distribútorom generík.

Tímový projekt v predmete 4IT529 Competitive Intelligence (VŠE, ZS 2026).

## Čo aplikácia vie

| Časť | Otázka, na ktorú odpovedá |
|---|---|
| Hroziace výpadky | Ktorým liekom hrozí výpadok v najbližších 8 týždňoch a prečo? (KIQ1) |
| Látka a náhrady | Prichádzajú výpadky v ČR a SR naraz? Čím nahradiť chýbajúci liek? (KIQ2, KIQ3) |
| Trh a konkurencia | Kde na trhu chýba dodávateľ? Ako spoľahlivo dodávajú konkurenti? (KIQ4, KIQ5) |
| Opýtajte sa AI | Otázka vlastnými slovami → 5 AI agentov → stručná správa so zdrojmi a kontrolou faktov |
| Zdroje a presnosť | Odkiaľ sú dáta (Admiralty, SHA-256) a ako presné sú predpovede (spätný test) |

Rozhranie je v slovenčine, češtine a angličtine.

**Overenie:** V spätnom teste malo zo 100 liekov s najvyšším skóre výpadok do 8 týždňov 19,5 % v ČR
(náhodný liek 2,8 %, teda asi 7× viac) a 13,6 % v SR. Podrobnosti sú v `vault/metodika/`.

## Architektúra

```
Verejné dáta SÚKL + ŠÚKL ─▶ pipeline/ (sťahovanie, manifest, čistenie, párovanie ČR–SR, modely)
                                  │
                                  ▼
                       data/processed/*.parquet
                                  │
                       pipeline/analytika.py  (nástroje KIQ1–KIQ5, čísla počíta kód)
                          │                         │
                          ▼                         ▼
                agents/ (LangGraph + Gemini)   app.py (Streamlit)
          orchestrátor → zber → analytik → reportér → kritik
```

Podrobná dokumentácia (agenti, roly, externé dáta, komunikácia, bezpečnosť): [`docs/architektura.md`](docs/architektura.md).

## Štruktúra repozitára

```
app.py                     webová aplikácia (Streamlit)
pipeline/
  sources_cz.py            sťahovanie dát SÚKL (hlásenia, DLP, DIS-13)
  sources_sk.py            sťahovanie dát ŠÚKL (register API, hlásenia)
  manifest.py              záznam zdrojov: čas UTC, SHA-256, Admiralty
  normalize.py             zjednotenie formátov, výpadky od začiatku po koniec
  match_cz_sk.py           párovanie látok ČR ↔ SR (ATC)
  kiq2_posun.py            časový posun výpadkov ČR ↔ SR
  analytika.py             nástroje KIQ1–KIQ5 pre aplikáciu aj agentov
  kiq1_spatny_test.py      spätný test modelu rizika, logistická regresia
  kiq1_ml.py               model strojového učenia (gradient boosting)
  kontrola_parov.py        ručná kontrola párovania
  wiki.py                  generátor poznámok pre Obsidian
  run_pipeline.py          spustí celý dátový pipeline
agents/
  graph.py                 multiagentný systém v LangGraph
  tools.py                 nástroje, ktoré agenti volajú
  llm.py                   pripojenie na Gemini, limity, záložný model
  kontrola_cisel.py        kontrola čísel v správe proti dátam
data/processed/            spracované dáta pre aplikáciu
vault/                     Obsidian: pravidlá agentov, wiki, správy, Case Logy, metodika, manifest zdrojov
docs/architektura.md       dokumentácia architektúry
```

## Spustenie lokálne

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# do .streamlit/secrets.toml vlož svoj GEMINI_API_KEY (len pre časť Opýtajte sa AI)

streamlit run app.py               # aplikácia nad dátami v data/processed
python -m pipeline.run_pipeline    # (voliteľné) stiahne a prepočíta čerstvé dáta
```

## Zdroje dát

| ID | Zdroj | Admiralty |
|---|---|---|
| E001 | SÚKL – hlásenia o prerušení a obnovení dodávok (ČR) | A2 |
| E002 | SÚKL – databáza liekov DLP (ČR) | A1 |
| E003 | SÚKL – DIS-13 dodávky distribútorov (ČR) | A2 |
| E004 | ŠÚKL – register liekov, API (SR) | A1 |
| E005 | ŠÚKL – hlásenia o prerušení a obnovení dodávok (SR) | A2 |

## Bezpečnosť

- API kľúč patrí **iba** do `.streamlit/secrets.toml` (lokálne, je v `.gitignore`) a do Secrets v Streamlit Cloude.
  Model sa volá na serveri, kľúč sa nedostane do prehliadača.
- Projekt pracuje len s verejnými dátami o liekoch a firmách, bez osobných údajov.
- LiekRadar neposkytuje lekárske odporúčania; zámenu inej účinnej látky môže urobiť len lekár.

## Tím

Nikola Slivoňová, Emma Schniererová, Adam Havlena, Filip Stehno