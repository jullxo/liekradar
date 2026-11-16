---
typ: case-log
otazka: "Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku?"
persona: lekaren
zaciatok_utc: 2026-11-16T10:44:05Z
koniec_utc: 2026-11-16T10:44:28Z
model: gemini-3.5-flash-lite
volania_modelu: 7
poziadavky_na_model: 7
sprava: "[[reports/2026-11-16-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]]"
verified: false
---

# Case Log – Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku?

## Plán (orchestrátor)
- KIQ: KIQ3, KIQ1 · krajiny: SK · ATC prefix: J01CR
- zdôvodnenie: Otázka sa pýta na náhradu za amoxicilín s kyselinou klavulánovou na Slovensku, preto volíme KIQ3 a nástroj nahrady_za_latku.
- rozsah otázky: ok · jazyk odpovede: cs (appka: cs) · preklad: vratene_sk

## Kroky agentov
- 2026-11-16T10:44:08Z · orchestrátor · LLM gemini-3.5-flash-lite · vstup: otázka: Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku? · persona: lekaren · výsledok: KIQ KIQ3, KIQ1 · krajiny SK · volania: nahrady_za_latku(SK, J01CR02, 5), top_rizikove(SK, J01CR, 5)
- 2026-11-16T10:44:09Z · zber · nahrady_za_latku · vstup: {"krajina":"SK","atc":"J01CR02","n":5} · výsledok: 10 z 24 riadkov · [E004, A1] [E005, A2] · 0.6 s
- 2026-11-16T10:44:10Z · zber · top_rizikove · vstup: {"krajina":"SK","atc_prefix":"J01CR","n":5} · výsledok: 5 z 5 riadkov · [E001, A2] [E005, A2] · 1.6 s
- 2026-11-16T10:44:13Z · analytik · LLM gemini-3.5-flash-lite · vstup: výsledky 2 volaní (7023 znakov JSON) · výsledok: 6 faktov, 1 úsudkov (1589 znakov)
- 2026-11-16T10:44:18Z · reportér · LLM gemini-3.5-flash-lite · vstup: zistenia analytika + výsledky nástrojov · výsledok: správa BLUF, 4279 znakov
- 2026-11-16T10:44:18Z · kritik · kontrola v kóde · vstup: správa 4279 znakov · výsledok: 3 problémov, 0 upozornení: Prvé dve vety BLUF nemajú výraz z mierky PHIA a istotu (nízka/stredná): „Na slovenskom trhu sú hlásené výpadky liekov Amoksiklav 625 mg a Amoksiklav 156,25 mg/5 ml [E004, A1] [E005, A2]. Za ta…
- 2026-11-16T10:44:20Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: neschválené: Medzi náhradami pre Amoksiklav 156,25 mg/5 ml je nesprávne uvedený liek Amoksiklav 2x457 mg/5 ml, čo je iné balenie toho istého lieku, a nie náhrada.; Liek Amoksiklav 625 mg bol v texte pôvodne uvedený v zo…
- 2026-11-16T10:44:23Z · reportér · LLM gemini-3.5-flash-lite · vstup: oprava podľa kritika · výsledok: správa BLUF, 4163 znakov
- 2026-11-16T10:44:23Z · kritik · kontrola v kóde · vstup: správa 4163 znakov · výsledok: 0 problémov, 0 upozornení
- 2026-11-16T10:44:24Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: schválené
- 2026-11-16T10:44:28Z · preklad · LLM gemini-3.5-flash-lite · vstup: schválená správa 4163 znakov → cs · výsledok: preklad 4116 znakov
- 2026-11-16T10:44:28Z · preklad · kontrola v kóde · vstup: nadpisy, označenia, citácie, čísla, kódy, názvy liekov, úplnosť · výsledok: NEZHODA – použitá slovenská verzia: Označenie **Upozornenie:**: v slovenskej verzii 1×, v preklade 0×.; Názvy liekov: v preklade chýba MEDOCLAV 400 mg/5 ml + 57 mg/5 ml prášok na perorálnu suspenziu.


## Kritik
- výsledok: schválené (kolo 2, opráv 1)


## Bezpečnosť
- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah z webu, žiadne osobné údaje.
