---
typ: case-log
otazka: "Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?"
persona: lekaren
zaciatok_utc: 2026-11-13T13:47:08Z
koniec_utc: 2026-11-13T13:47:27Z
model: gemini-3.5-flash-lite
volania_modelu: 4
poziadavky_na_model: 4
sprava: "[[reports/2026-11-13-antibiotika-j01-chybat-slovensku]]"
verified: false
---

# Case Log – Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?

## Plán (orchestrátor)
- KIQ: KIQ1, KIQ3, KIQ2 · krajiny: SK · ATC prefix: J01
- zdôvodnenie: Identifikujeme rizikové antibiotiká bez nahláseného výpadku na Slovensku (KIQ1), preveríme ich náhrady (KIQ3) a prípadný časový posun výpadkov z Česka (KIQ2).

## Kroky agentov
- 2026-11-13T13:47:11Z · orchestrátor · LLM gemini-3.5-flash-lite · vstup: otázka: Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku? · persona: lekaren · výsledok: KIQ KIQ1, KIQ3, KIQ2 · krajiny SK · volania: top_rizikove(SK, J01, 10), nahrady(SK, z_top_rizikove, 5), posun_latky(z_top_rizikove)
- 2026-11-13T13:47:13Z · zber · top_rizikove · vstup: {"krajina":"SK","atc_prefix":"J01","n":10} · výsledok: 10 z 10 riadkov · [E001, A2] [E005, A2] · 1.6 s
- 2026-11-13T13:47:13Z · zber · nahrady · vstup: {"krajina":"SK","kod":"76566","n":5} · výsledok: 5 z 5 riadkov · [E004, A1] [E005, A2] · 0.0 s
- 2026-11-13T13:47:13Z · zber · nahrady · vstup: {"krajina":"SK","kod":"80181","n":5} · výsledok: 5 z 5 riadkov · [E004, A1] [E005, A2] · 0.0 s
- 2026-11-13T13:47:13Z · zber · posun_latky · vstup: {"atc":"J01XD01"} · výsledok: J01XD01 METRONIDAZOL · [E001, A2] [E005, A2] · 0.0 s
- 2026-11-13T13:47:13Z · zber · posun_latky · vstup: {"atc":"J01GB03"} · výsledok: J01GB03 GENTAMICIN · [E001, A2] [E005, A2] · 0.0 s
- 2026-11-13T13:47:18Z · analytik · LLM gemini-3.5-flash-lite · vstup: výsledky 5 volaní (9660 znakov JSON) · výsledok: 6 faktov, 3 úsudkov (3770 znakov)
- 2026-11-13T13:47:26Z · reportér · LLM gemini-3.5-flash-lite · vstup: zistenia analytika + výsledky nástrojov · výsledok: správa BLUF, 5644 znakov
- 2026-11-13T13:47:26Z · kritik · kontrola v kóde · vstup: správa 5644 znakov · výsledok: 0 problémov, 0 upozornení
- 2026-11-13T13:47:27Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: schválené

## Kritik
- výsledok: schválené (kolo 1, opráv 0)


## Bezpečnosť
- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah z webu, žiadne osobné údaje.
