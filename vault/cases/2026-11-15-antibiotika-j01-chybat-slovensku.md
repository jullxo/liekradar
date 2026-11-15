---
typ: case-log
otazka: "Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?"
persona: lekaren
zaciatok_utc: 2026-11-15T13:17:20Z
koniec_utc: 2026-11-15T13:17:58Z
model: gemini-3.5-flash-lite
volania_modelu: 6
poziadavky_na_model: 7
sprava: "[[reports/2026-11-15-antibiotika-j01-chybat-slovensku]]"
verified: false
---

# Case Log – Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?

## Plán (orchestrátor)
- KIQ: KIQ1 · krajiny: SK · ATC prefix: J01
- zdôvodnenie: Pre otázku na antibiotiká s hroziacim výpadkom na Slovensku použijeme KIQ1 a nástroj top_rizikove pre ATC prefix J01.

## Kroky agentov
- 2026-11-15T13:17:40Z · orchestrátor · LLM gemini-3.5-flash-lite · vstup: otázka: Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku? · persona: lekaren · výsledok: KIQ KIQ1 · krajiny SK · volania: top_rizikove(SK, J01, 10)
- 2026-11-15T13:17:42Z · zber · top_rizikove · vstup: {"krajina":"SK","atc_prefix":"J01","n":10} · výsledok: 10 z 10 riadkov · [E001, A2] [E005, A2] · 1.8 s
- 2026-11-15T13:17:46Z · analytik · LLM gemini-3.5-flash-lite · vstup: výsledky 1 volaní (4661 znakov JSON) · výsledok: 0 faktov, 2 úsudkov (3528 znakov)
- 2026-11-15T13:17:52Z · reportér · LLM gemini-3.5-flash-lite · vstup: zistenia analytika + výsledky nástrojov · výsledok: správa BLUF, 4529 znakov
- 2026-11-15T13:17:52Z · kritik · kontrola v kóde · vstup: správa 4529 znakov · výsledok: 1 problémov, 0 upozornení: Zakázané slovo „preukázanými“ (preháňa istotu; skóre a súbehy sú signály, nie dôkaz).
- 2026-11-15T13:17:53Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: neschválené: V sekcii Key judgements sa naďalej nachádza zakázané slovo „preukázanými“ v prvom bode, čo bolo vytknuté v kontrole kódom.
- 2026-11-15T13:17:57Z · reportér · LLM gemini-3.5-flash-lite · vstup: oprava podľa kritika · výsledok: správa BLUF, 4533 znakov
- 2026-11-15T13:17:57Z · kritik · kontrola v kóde · vstup: správa 4533 znakov · výsledok: 0 problémov, 0 upozornení
- 2026-11-15T13:17:58Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: schválené

## Kritik
- výsledok: schválené (kolo 2, opráv 1)


## Bezpečnosť
- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah z webu, žiadne osobné údaje.
