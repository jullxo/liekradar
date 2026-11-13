# KIQ1 – porovnanie modelov (v0, v1, v2 strojové učenie)

Generované 2026-11-13 10:59 UTC skriptom `pipeline.kiq1_ml`. Neupravovať ručne.

Všetky tri modely sú hodnotené rovnako: učenie na starších 2/3 dátumov, overenie na novšej 1/3, ktorú model nevidel. v0 = ručne odhadnuté váhy 5 signálov, v1 = logistická regresia na tých istých signáloch, v2 = gradient boosting (scikit-learn HistGradientBoostingClassifier) s ďalšími príznakmi: počet výrobcov látky, lieková forma, skupina ATC, sezóna, čas od posledného výpadku, veľkosť výrobcu a v ČR objem dodávok. Zdroje: [E001, A2] [E002, A1] [E003, A2] [E004, A1] [E005, A2].

## Česko

Overenie od 12/2025, náhodne vybraný liek mal výpadok do 8 týždňov v 3,0 % prípadov.

| Model | Presnosť top 100 | Zachytené výpadky v top 100 | AUC |
|---|---|---|---|
| v0 odhadnuté váhy | 14,3 % | 6,8 % | 0,70 |
| v1 logistická regresia | 14,1 % | 6,7 % | 0,73 |
| v2 gradient boosting (ML) | 19,5 % | 9,3 % | 0,77 |

**Použitý model: v2 (gradient boosting).**

Najdôležitejšie príznaky v2 (o koľko klesne AUC, keď príznak náhodne pomiešame):

| Príznak | Pokles AUC |
|---|---|
| počet výpadkov výrobcu za rok | 0,044 |
| dni od posledného výpadku lieku | 0,031 |
| veľa výpadkov výrobcu za posledný rok | 0,026 |
| lieková forma | 0,015 |
| veľkosť výrobcu (počet registrácií) | 0,014 |
| dodávky do lekární za 3 mesiace (len ČR) | 0,013 |
| počet výpadkov látky za rok | 0,008 |
| skupina ATC (1. písmeno) | 0,008 |
| mesiac v roku (sezóna) | 0,004 |
| počet registrovaných balení látky | 0,003 |

## Slovensko

Overenie od 07/2024, náhodne vybraný liek mal výpadok do 8 týždňov v 0,2 % prípadov.

| Model | Presnosť top 100 | Zachytené výpadky v top 100 | AUC |
|---|---|---|---|
| v0 odhadnuté váhy | 8,2 % | 6,6 % | 0,69 |
| v1 logistická regresia | 13,6 % | 10,9 % | 0,80 |
| v2 gradient boosting (ML) | 10,8 % | 8,6 % | 0,86 |

**Použitý model: v2 nebol lepší, ostáva predchádzajúci.**

Najdôležitejšie príznaky v2 (o koľko klesne AUC, keď príznak náhodne pomiešame):

| Príznak | Pokles AUC |
|---|---|
| dni od posledného výpadku lieku | 0,108 |
| počet registrovaných balení látky | 0,035 |
| veľa výpadkov výrobcu za posledný rok | 0,015 |
| lieková forma | 0,009 |
| veľkosť výrobcu (počet registrácií) | 0,007 |
| počet výpadkov výrobcu za rok | 0,007 |
| výpadok tej istej látky v druhej krajine | 0,006 |
| počet výrobcov látky | 0,003 |
| počet výpadkov látky za rok | 0,003 |
| nový výpadok iného lieku s touto látkou doma | 0,003 |

## Ako to čítať

- Presnosť top 100: koľko zo 100 liekov s najvyšším skóre naozaj malo výpadok do 8 týždňov.
- Zachytené výpadky: aký podiel všetkých výpadkov v tom období bol v top 100.
- AUC: ako dobre model zoradí všetky lieky (0,5 = náhoda, 1 = dokonalé poradie).
- Ani ML model nevidí príčiny, ktoré vo verejných dátach nie sú (výrobné problémy, nedostatok suroviny, nárast dopytu). Preto zachytí len časť výpadkov.
- Počet výrobcov a balení látky je z aktuálneho registra, nie z registra k minulému dátumu.
