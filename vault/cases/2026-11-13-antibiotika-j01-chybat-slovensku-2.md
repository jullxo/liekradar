---
typ: case-log
otazka: "Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?"
persona: lekaren
zaciatok_utc: 2026-11-13T13:50:13Z
koniec_utc: 2026-11-13T13:50:36Z
model: gemini-3.5-flash-lite
volania_modelu: 6
poziadavky_na_model: 6
sprava: "[[reports/2026-11-13-antibiotika-j01-chybat-slovensku-2]]"
verified: false
---

# Case Log – Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?

## Plán (orchestrátor)
- KIQ: KIQ1, KIQ3, KIQ2 · krajiny: SK, CZ · ATC prefix: J01
- zdôvodnenie: Pre vybrané antibiotiká (J01) na Slovensku identifikujeme najrizikovejšie lieky bez nahláseného výpadku, overíme ich časový posun oproti ČR a vyhľadáme vhodné náhrady pre zaistenie predzásobenia lekárenskej siete.

## Kroky agentov
- 2026-11-13T13:50:15Z · orchestrátor · LLM gemini-3.5-flash-lite · vstup: otázka: Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku? · persona: lekaren · výsledok: KIQ KIQ1, KIQ3, KIQ2 · krajiny SK, CZ · volania: top_rizikove(SK, J01, 5), nahrady(SK, z_top_rizikove, 5), posun_latky(z_top_rizikove)
- 2026-11-13T13:50:17Z · zber · top_rizikove · vstup: {"krajina":"SK","atc_prefix":"J01","n":5} · výsledok: 5 z 5 riadkov · [E001, A2] [E005, A2] · 1.8 s
- 2026-11-13T13:50:17Z · zber · nahrady · vstup: {"krajina":"SK","kod":"76566","n":5} · výsledok: 5 z 5 riadkov · [E004, A1] [E005, A2] · 0.0 s
- 2026-11-13T13:50:17Z · zber · nahrady · vstup: {"krajina":"SK","kod":"80181","n":5} · výsledok: 5 z 5 riadkov · [E004, A1] [E005, A2] · 0.0 s
- 2026-11-13T13:50:17Z · zber · posun_latky · vstup: {"atc":"J01XD01"} · výsledok: J01XD01 METRONIDAZOL · [E001, A2] [E005, A2] · 0.0 s
- 2026-11-13T13:50:17Z · zber · posun_latky · vstup: {"atc":"J01GB03"} · výsledok: J01GB03 GENTAMICIN · [E001, A2] [E005, A2] · 0.0 s
- 2026-11-13T13:50:22Z · analytik · LLM gemini-3.5-flash-lite · vstup: výsledky 5 volaní (7549 znakov JSON) · výsledok: 8 faktov, 3 úsudkov (3244 znakov)
- 2026-11-13T13:50:28Z · reportér · LLM gemini-3.5-flash-lite · vstup: zistenia analytika + výsledky nástrojov · výsledok: správa BLUF, 5654 znakov
- 2026-11-13T13:50:28Z · kritik · kontrola v kóde · vstup: správa 5654 znakov · výsledok: 6 problémov, 0 upozornení: Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Medzi ďalšie rizikové lieky v skupine J01 patria *Ciprofloxacin Kabi 200 mg/100 ml* (skóre 80), *BISEPTOL 1…“
- 2026-11-13T13:50:29Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: neschválené: Fakt bez citácie [ID, Admiralty] v odseku o ďalších rizikových liekoch v skupine J01.; Fakt bez citácie [ID, Admiralty] pri popise náhrad pre liek Metronidazol B. Braun.; Fakt bez citácie [ID, Admiralty] pr…
- 2026-11-13T13:50:35Z · reportér · LLM gemini-3.5-flash-lite · vstup: oprava podľa kritika · výsledok: správa BLUF, 5715 znakov
- 2026-11-13T13:50:35Z · kritik · kontrola v kóde · vstup: správa 5715 znakov · výsledok: 5 problémov, 0 upozornení: Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Medzi ďalšie rizikové lieky v skupine J01 patria *Ciprofloxacin Kabi 200 mg/100 ml* (skóre 80) [E001, A2, E…“
- 2026-11-13T13:50:36Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: neschválené: Niektoré fakty v sekcii Discussion neobsahujú povinnú citáciu [ID, Admiralty] na konci vety.; Tvrdenie o Ciprofloxacine a iných liekoch v zozname rizikových liekov má neúplné alebo chýbajúce zdrojové značky…

## Kritik
- výsledok: neschválené (kolo 2, opráv 1)
- problém: Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Medzi ďalšie rizikové lieky v skupine J01 patria *Ciprofloxacin Kabi 200 mg/100 ml* (skóre 80) [E001, A2, E…“
- problém: Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Pre liek *Metronidazol B. Braun 5 mg/ml* (kód `76566`) sú v SR dostupné náhrady s rovnakou účinnou látkou, …“
- problém: Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Pre liek *Gentamicin B. Braun 3 mg/ml* (kód `80181`) sú k dispozícii náhrady ako *Gentamicin B. Braun* (iná…“
- problém: Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Analýza časového posunu pre látku *METRONIDAZOL* (`J01XD01`) eviduje 8 vĺn výpadkov v ČR a 7 v SR, pričom v…“
- problém: Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Pre látku *GENTAMICIN* (`J01GB03`) eviduje model 7 vĺn výpadkov v ČR a 5 v SR, pričom v 3 prípadoch prebehl…“
- problém: Niektoré fakty v sekcii Discussion neobsahujú povinnú citáciu [ID, Admiralty] na konci vety.
- problém: Tvrdenie o Ciprofloxacine a iných liekoch v zozname rizikových liekov má neúplné alebo chýbajúce zdrojové značky v súlade s manifestom.


## Bezpečnosť
- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah z webu, žiadne osobné údaje.
