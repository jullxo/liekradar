# KIT a KIQ

Key Intelligence Topic (KIT) vymedzuje hlavnú tému, ktorú má konkurenčné spravodajstvo pokryť, a Key Intelligence Questions (KIQ) ju rozkladajú na konkrétne otázky, na ktoré LiekRadar odpovedá. Spolu určujú, pre koho je riešenie určené a aké rozhodnutia podporuje.

## KIT

Riziká a príležitosti vyplývajúce z výpadkov dodávok liekov na českom a slovenskom trhu: včasné varovanie, overenie náhrad a identifikácia konkurentov, ktorí výpadky spôsobujú alebo z nich profitujú.

**Cieľová skupina:**

- **Primárne:** výrobca generík, distribútor alebo paralelný dovozca. Rozhoduje, kde a kedy navýšiť dodávky a ktorí konkurenti sú nespoľahliví.
- **Sekundárne:** nákupca lekárenskej siete. Rozhoduje, čo predzásobiť a aké náhrady pripraviť.

Oba typy používateľov pracujú s rovnakými dátami. Líšia sa rozhodnutím, preto LiekRadar pre každý z nich vytvára samostatný manažérsky výstup.

## KIQ

### KIQ1: Riziko

Ktoré lieky majú v ČR a SR najvyššie riziko výpadku v horizonte 4–8 týždňov, vrátane liekov, pri ktorých držiteľ registrácie výpadok ešte nenahlásil? Riziko odvodzujeme od signálov: výpadok rovnakej látky v druhej krajine, pokles dodávok, obmedzenie vývozu a počet zostávajúcich alternatív.

| Pole | Hodnota |
| --- | --- |
| Pre koho | Obaja |
| Rozhodnutie | Čo sledovať a predzásobiť |
| Horizont | 4–8 týždňov |
| Indikátory | Výpadok rovnakej látky v druhej krajine, pokles dodávok, obmedzenie vývozu, počet zostávajúcich alternatív |
| Zdroje ČR | Hlásenia SÚKL, DIS-13, zoznam obmedzeného vývozu |
| Zdroje SR | Hlásenia ŠÚKL, oznámenia o vývoze |

### KIQ2: Časový posun

Predchádzajú výpadky v ČR výpadkom tej istej látky v SR (alebo naopak), s akým časovým posunom a v ktorých ATC skupinách je tento vzťah najsilnejší?

| Pole | Hodnota |
| --- | --- |
| Pre koho | Obaja |
| Rozhodnutie | Kedy reagovať v druhej krajine |
| Horizont | Nie je v reporte uvedený |
| Indikátory | Výpadky tej istej látky v ČR a SR, časový posun medzi nimi, ATC skupina |
| Zdroje ČR | História hlásení SÚKL |
| Zdroje SR | História hlásení ŠÚKL |

### KIQ3: Náhrady

Aké náhrady sú pre každý ohrozený liek dostupné v danej krajine? Hľadáme rovnakú účinnú látku v inej sile či forme, prípadne inú látku v rovnakej ATC skupine. Kto je ich držiteľom registrácie, aká je ich cena a úhrada a nie sú samy hlásené ako nedostupné?

| Pole | Hodnota |
| --- | --- |
| Pre koho | Lekárenská sieť |
| Rozhodnutie | Čím nahradiť |
| Horizont | Nie je v reporte uvedený |
| Indikátory | Rovnaká látka v inej sile alebo forme, iná látka v rovnakej ATC skupine, držiteľ registrácie, cena a úhrada, dostupnosť náhrady |
| Zdroje ČR | Databáza liekov, ceny a úhrady SÚKL |
| Zdroje SR | Register ŠÚKL, kategorizácia MZ SR |

### KIQ4: Konkurenti

Ktorí držitelia registrácie hlásia v sledovaných ATC skupinách najviac prerušení a zrušení dodávok (počet a dĺžka výpadkov) a ktorí konkurenti počas týchto výpadkov zvýšili dodávky náhrad?

| Pole | Hodnota |
| --- | --- |
| Pre koho | Výrobca |
| Rozhodnutie | Komu veriť, kde získať podiel |
| Horizont | Nie je v reporte uvedený |
| Indikátory | Počet a dĺžka výpadkov podľa držiteľa registrácie, nárast dodávok náhrad počas cudzích výpadkov |
| Zdroje ČR | Hlásenia + DIS-13 |
| Zdroje SR | Hlásenia; dodávky [OVERIŤ dostupnosť] |

### KIQ5: Príležitosť

Pri ktorých liekoch je trhová medzera v ČR alebo SR dosť veľká na vstup alebo navýšenie dodávok? Za medzeru považujeme výpadok trvajúci aspoň **[DOPLNIŤ: napr. 8]** týždňov, pri ktorom náhrady s rovnakou látkou dodávajú najviac **[DOPLNIŤ: napr. 2]** držitelia registrácie alebo sú samy ohrozené.

| Pole | Hodnota |
| --- | --- |
| Pre koho | Výrobca |
| Rozhodnutie | Kam navýšiť dodávky |
| Horizont | Výpadok trvajúci aspoň [DOPLNIŤ: napr. 8] týždňov |
| Indikátory | Dĺžka výpadku, počet držiteľov registrácie dodávajúcich náhrady s rovnakou látkou |
| Zdroje ČR | KIQ1 + KIQ3 + KIQ4 |
| Zdroje SR | KIQ1 + KIQ3 + KIQ4 |

## Prehľad

| KIQ | Pre koho | Rozhodnutie | Dáta ČR | Dáta SR |
| --- | --- | --- | --- | --- |
| **KIQ1 Riziko** | Obaja | Čo sledovať a predzásobiť | Hlásenia SÚKL, DIS-13, zoznam obmedzeného vývozu | Hlásenia ŠÚKL, oznámenia o vývoze |
| **KIQ2 Časový posun** | Obaja | Kedy reagovať v druhej krajine | História hlásení SÚKL | História hlásení ŠÚKL |
| **KIQ3 Náhrady** | Lekárenská sieť | Čím nahradiť | Databáza liekov, ceny a úhrady SÚKL | Register ŠÚKL, kategorizácia MZ SR |
| **KIQ4 Konkurenti** | Výrobca | Komu veriť, kde získať podiel | Hlásenia + DIS-13 | Hlásenia; dodávky [OVERIŤ dostupnosť] |
| **KIQ5 Príležitosť** | Výrobca | Kam navýšiť dodávky | KIQ1 + KIQ3 + KIQ4 | KIQ1 + KIQ3 + KIQ4 |
