# KIQ1 – spätný test skóre rizika

Generované 2026-11-13 10:56 UTC skriptom `pipeline.kiq1_spatny_test`. Neupravovať ručne.

**Otázka:** keby LiekRadar bežal v minulosti, mali by lieky s najvyšším skóre častejšie výpadok v nasledujúcich 56 dňoch (8 týždňov) ako náhodne vybrané lieky?

**Metóda:** k 15. dňu každého mesiaca sme spočítali skóre všetkých liekov, ktoré vtedy neboli vo výpadku ani nemali ohlásený výpadok, len z informácií známych k tomu dňu (hlásenia podané do toho dňa, zverejnené mesiace dodávok). Potom sme overili, či liek mal výpadok do 56 dní. Presnosť top 100 = koľko zo 100 liekov s najvyšším skóre naozaj malo výpadok. Lift = koľkokrát je to viac ako pri náhodnom výbere. Váhy v1 sa naučila logistická regresia na starších 2/3 dátumov a hodnotia sa len na novšej 1/3, ktorú model nevidel. Zdroje: [E001, A2] [E003, A2] [E005, A2] [E002, A1] [E004, A1].

## Česko

- Obdobie: 06/2024 – 09/2026, 28 dátumov, v priemere 6 820 liekov na dátum.
- Náhodne vybraný liek mal výpadok do 8 týždňov v **2,8 %** prípadov.

| Model | Obdobie hodnotenia | Presnosť top 100 | Lift | Zachytené výpadky v top 100 | AUC |
|---|---|---|---|---|---|
| v0 (odhadnuté váhy) | celé obdobie | 14,6 % | 5,3× | 7,8 % | 0,71 |
| v0 (odhadnuté váhy) | od 12/2025 | 14,3 % | 4,8× | 6,8 % | 0,70 |
| v1 (logistická regresia) | od 12/2025 | 14,1 % | 4,7× | 6,7 % | 0,73 |

**Použitý model: v0.**

Sila jednotlivých signálov (celé obdobie):

| Signál | Lieky so signálom | Výpadok so signálom | Výpadok bez signálu | Lift | Váha v0 | Váha v1 |
|---|---|---|---|---|---|---|
| veľa výpadkov výrobcu za posledný rok | 83,4 % | 3,2 % | 0,5 % | 7,0× | 0,10 | 0,37 |
| výpadky tohto lieku za posledné 3 roky | 33,2 % | 5,4 % | 1,4 % | 3,7× | 0,20 | 0,29 |
| výpadok tej istej látky u toho istého výrobcu v druhej krajine | 4,9 % | 7,8 % | 2,5 % | 3,1× | 0,30 | 0,09 |
| nový výpadok iného lieku s touto látkou doma | 39,2 % | 4,3 % | 1,8 % | 2,4× | 0,25 | 0,15 |
| výpadok tej istej látky v druhej krajine | 23,2 % | 4,5 % | 2,2 % | 2,1× | 0,15 | 0,05 |
| veľký podiel vývozu (len ČR) | 13,0 % | 3,5 % | 2,6 % | 1,3× | 0,00 | 0,04 |
| pokles dodávok do lekární (len ČR) | 49,6 % | 2,5 % | 3,0 % | 0,8× | 0,00 | 0,00 |

## Slovensko

- Obdobie: 02/2020 – 09/2026, 80 dátumov, v priemere 51 456 liekov na dátum.
- Náhodne vybraný liek mal výpadok do 8 týždňov v **0,2 %** prípadov.

| Model | Obdobie hodnotenia | Presnosť top 100 | Lift | Zachytené výpadky v top 100 | AUC |
|---|---|---|---|---|---|
| v0 (odhadnuté váhy) | celé obdobie | 6,7 % | 30,3× | 5,9 % | 0,71 |
| v0 (odhadnuté váhy) | od 07/2024 | 8,2 % | 33,6× | 6,6 % | 0,69 |
| v1 (logistická regresia) | od 07/2024 | 13,6 % | 55,7× | 10,9 % | 0,80 |

**Použitý model: v1.**

Sila jednotlivých signálov (celé obdobie):

| Signál | Lieky so signálom | Výpadok so signálom | Výpadok bez signálu | Lift | Váha v0 | Váha v1 |
|---|---|---|---|---|---|---|
| výpadky tohto lieku za posledné 3 roky | 2,1 % | 4,8 % | 0,1 % | 38,5× | 0,20 | 0,57 |
| veľa výpadkov výrobcu za posledný rok | 76,5 % | 0,3 % | 0,1 % | 3,9× | 0,10 | 0,28 |
| výpadok tej istej látky u toho istého výrobcu v druhej krajine | 7,9 % | 0,6 % | 0,2 % | 3,3× | 0,30 | 0,06 |
| nový výpadok iného lieku s touto látkou doma | 24,1 % | 0,4 % | 0,2 % | 2,0× | 0,25 | 0,06 |
| výpadok tej istej látky v druhej krajine | 39,3 % | 0,3 % | 0,2 % | 1,8× | 0,15 | 0,03 |

## Obmedzenia

- Slovenský register je aktuálny stav: v minulých dátumoch chýbajú lieky, ktoré medzitým zanikli, a sú tam lieky registrované až neskôr.
- Dodávky DIS-13 sú od 2024, preto je test pre ČR kratší a signály z dodávok sú len pre ČR.
- Top 100 zachytí len menšinu všetkých výpadkov (stĺpec Zachytené výpadky). Väčšina výpadkov prichádza bez varovného signálu v dátach. Model pomáha určiť, ktoré lieky sledovať, výpadky nepredpovedá s istotou.
- V SR nemáme dáta o dodávkach, preto do testu vstupujú všetky registrované balenia vrátane tých, ktoré sa nepredávajú. Náhodná miera je preto veľmi nízka a lift vysoký. ČR a SR porovnávajte podľa presnosti top 100, nie podľa liftu.
- Skóre nie je pravdepodobnosť. Presnosť top 100 hovorí, aký podiel z odporúčaného zoznamu mal v minulosti naozaj výpadok.
- Výpadok počítame podľa dátumu účinnosti v hláseniach SÚKL/ŠÚKL; výpadky, ktoré firma nenahlásila, nevidíme.
