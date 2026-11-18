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

Ktoré lieky majú v ČR a SR najvyššie riziko výpadku v horizonte do 8 týždňov, hoci ho držiteľ registrácie ešte nenahlásil? Riziko odvodzujeme zo signálov: výpadok tej istej látky u toho istého výrobcu v druhej krajine, nové výpadky látky doma, história výpadkov lieku a výrobcu, v ČR aj pokles dodávok a podiel vývozu.

| Pole | Hodnota |
| --- | --- |
| Pre koho | Obaja |
| Rozhodnutie | Čo sledovať a predzásobiť |
| Horizont | do 8 týždňov |
| Indikátory | Výpadok tej istej látky u toho istého výrobcu v druhej krajine, nové výpadky látky doma, história výpadkov lieku a výrobcu, pokles dodávok a podiel vývozu (ČR) |
| Zdroje ČR | Hlásenia SÚKL [E001], databáza liekov DLP [E002], DIS-13 [E003] |
| Zdroje SR | Hlásenia ŠÚKL [E005], register ŠÚKL [E004] |

### KIQ2: Časový posun

Predchádzajú výpadky v ČR výpadkom tej istej látky v SR (alebo naopak), s akým časovým posunom a v ktorých ATC skupinách je tento vzťah najsilnejší?

| Pole | Hodnota |
| --- | --- |
| Pre koho | Obaja |
| Rozhodnutie | Kedy reagovať v druhej krajine |
| Horizont | Súčasne (do 7 dní) alebo s posunom 8–60 dní |
| Indikátory | Výpadky tej istej látky v ČR a SR, časový posun medzi nimi, ATC skupina |
| Zdroje ČR | História hlásení SÚKL od 15. 4. 2019 [E001] |
| Zdroje SR | História hlásení ŠÚKL od 15. 4. 2019 [E005] |

### KIQ3: Náhrady

Aké náhrady sú dostupné pre liek vo výpadku v danej krajine? Hľadáme rovnakú účinnú látku v inej sile, forme či balení, prípadne inú látku v rovnakej ATC skupine (zámenu môže urobiť len lekár). Kto je ich držiteľom registrácie, odporučil ich úrad a nie sú samy vo výpadku alebo s ohláseným výpadkom?

| Pole | Hodnota |
| --- | --- |
| Pre koho | Lekárenská sieť |
| Rozhodnutie | Čím nahradiť |
| Horizont | Aktuálny stav |
| Indikátory | Rovnaká látka v inej sile, forme alebo balení, iná látka v rovnakej ATC skupine, držiteľ registrácie, odporúčanie úradu, dostupnosť náhrady, v ČR dodávky do lekární |
| Zdroje ČR | Databáza liekov DLP [E002], hlásenia SÚKL [E001], DIS-13 [E003] |
| Zdroje SR | Register ŠÚKL [E004], hlásenia ŠÚKL [E005] |

### KIQ4: Konkurenti

Ktorí držitelia registrácie hlásia v sledovaných ATC skupinách najviac prerušení a zrušení dodávok (počet a dĺžka výpadkov) a ktorí konkurenti počas týchto výpadkov zvýšili svoj podiel na dodávkach do lekární?

| Pole | Hodnota |
| --- | --- |
| Pre koho | Výrobca |
| Rozhodnutie | Komu veriť, kde získať podiel |
| Horizont | Od 15. 4. 2019, posledných 12 mesiacov |
| Indikátory | Počet a dĺžka výpadkov podľa držiteľa registrácie, podiel na dodávkach a jeho zmena počas cudzích výpadkov (p. b.) |
| Zdroje ČR | Hlásenia SÚKL [E001] + DIS-13 [E003] |
| Zdroje SR | Hlásenia ŠÚKL [E005]; verejné dáta o dodávkach v SR neexistujú, preto bez podielov na trhu |

### KIQ5: Príležitosť

Pri ktorých liekoch je trhová medzera v ČR alebo SR dosť veľká na vstup alebo navýšenie dodávok? Za medzeru považujeme výpadok trvajúci aspoň **8 týždňov**, pri ktorom látku dodávajú najviac **2** ďalší výrobcovia. V ČR uvádzame aj veľkosť trhu v baleniach mesačne. Výpadky dlhšie ako 2 roky vynechávame (ide skôr o ukončený predaj).

| Pole | Hodnota |
| --- | --- |
| Pre koho | Výrobca |
| Rozhodnutie | Kam navýšiť dodávky |
| Horizont | Výpadok trvajúci aspoň 8 týždňov |
| Indikátory | Dĺžka výpadku, počet ďalších výrobcov, ktorí látku dodávajú, veľkosť trhu (ČR) |
| Zdroje ČR | KIQ1 + KIQ3 + KIQ4 |
| Zdroje SR | KIQ1 + KIQ3 + KIQ4 |

## Prehľad

| KIQ | Pre koho | Rozhodnutie | Dáta ČR | Dáta SR |
| --- | --- | --- | --- | --- |
| **KIQ1 Riziko** | Obaja | Čo sledovať a predzásobiť | Hlásenia SÚKL, DLP, DIS-13 | Hlásenia ŠÚKL, register ŠÚKL |
| **KIQ2 Časový posun** | Obaja | Kedy reagovať v druhej krajine | História hlásení SÚKL | História hlásení ŠÚKL |
| **KIQ3 Náhrady** | Lekárenská sieť | Čím nahradiť | Databáza liekov DLP, hlásenia SÚKL, DIS-13 | Register ŠÚKL, hlásenia ŠÚKL |
| **KIQ4 Konkurenti** | Výrobca | Komu veriť, kde získať podiel | Hlásenia + DIS-13 | Hlásenia (bez dát o dodávkach) |
| **KIQ5 Príležitosť** | Výrobca | Kam navýšiť dodávky | KIQ1 + KIQ3 + KIQ4 | KIQ1 + KIQ3 + KIQ4 |

Ceny, úhrady a zoznamy obmedzeného vývozu prototyp nepoužíva; sú uvedené v reporte ako obmedzenie a možné rozšírenie.
