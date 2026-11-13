---
typ: case-log
otazka: "Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?"
persona: lekaren
zaciatok_utc: 2026-11-13T14:28:58Z
koniec_utc: 2026-11-13T14:29:17Z
model: gemini-3.5-flash-lite
volania_modelu: 4
poziadavky_na_model: 4
sprava: "[[reports/2026-11-13-antibiotika-j01-chybat-slovensku-3]]"
verified: false
---

# Case Log – Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?

## Plán (orchestrátor)
- KIQ: KIQ1, KIQ3, KIQ2 · krajiny: SK · ATC prefix: J01
- zdôvodnenie: Pre vybranú skupinu antibiotík (J01) na Slovensku identifikujeme rizikové lieky bez nahláseného výpadku, zistíme možné náhrady pre predzásobenie a skontrolujeme časový posun výpadkov voči ČR.

## Kroky agentov
- 2026-11-13T14:29:02Z · orchestrátor · LLM gemini-3.5-flash-lite · vstup: otázka: Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku? · persona: lekaren · výsledok: KIQ KIQ1, KIQ3, KIQ2 · krajiny SK · volania: top_rizikove(SK, J01, 10), nahrady(SK, z_top_rizikove, 5), posun_latky(z_top_rizikove)
- 2026-11-13T14:29:04Z · zber · top_rizikove · vstup: {"krajina":"SK","atc_prefix":"J01","n":10} · výsledok: 10 z 10 riadkov · [E001, A2] [E005, A2] · 1.9 s
- 2026-11-13T14:29:04Z · zber · nahrady · vstup: {"krajina":"SK","kod":"76566","n":5} · výsledok: 5 z 5 riadkov · [E004, A1] [E005, A2] · 0.0 s
- 2026-11-13T14:29:04Z · zber · nahrady · vstup: {"krajina":"SK","kod":"80181","n":5} · výsledok: 5 z 5 riadkov · [E004, A1] [E005, A2] · 0.0 s
- 2026-11-13T14:29:04Z · zber · posun_latky · vstup: {"atc":"J01XD01"} · výsledok: J01XD01 METRONIDAZOL · [E001, A2] [E005, A2] · 0.0 s
- 2026-11-13T14:29:04Z · zber · posun_latky · vstup: {"atc":"J01GB03"} · výsledok: J01GB03 GENTAMICIN · [E001, A2] [E005, A2] · 0.0 s
- 2026-11-13T14:29:08Z · analytik · LLM gemini-3.5-flash-lite · vstup: výsledky 5 volaní (10235 znakov JSON) · výsledok: 7 faktov, 3 úsudkov (3343 znakov)
- 2026-11-13T14:29:14Z · reportér · LLM gemini-3.5-flash-lite · vstup: zistenia analytika + výsledky nástrojov · výsledok: správa BLUF, 5175 znakov
- 2026-11-13T14:29:14Z · kritik · kontrola v kóde · vstup: správa 5175 znakov · výsledok: 0 problémov, 0 upozornení
- 2026-11-13T14:29:17Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: schválené

## Kritik
- výsledok: schválené (kolo 1, opráv 0)


## Bezpečnosť
- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah z webu, žiadne osobné údaje.
