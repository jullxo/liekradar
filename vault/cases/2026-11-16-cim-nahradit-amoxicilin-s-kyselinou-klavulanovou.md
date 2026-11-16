---
typ: case-log
otazka: "Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku?"
persona: lekaren
zaciatok_utc: 2026-11-16T11:24:14Z
koniec_utc: 2026-11-16T11:24:53Z
model: gemini-3.5-flash-lite
volania_modelu: 8
poziadavky_na_model: 8
sprava: "[[reports/2026-11-16-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]]"
verified: false
---

# Case Log – Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku?

## Plán (orchestrátor)
- KIQ: KIQ3 · krajiny: SK · ATC prefix: J01CR
- zdôvodnenie: Otázka sa pýta na náhradu za amoxicilín s kyselinou klavulanovou (ATC J01CR02) na Slovensku, preto volíme nástroj nahrady_za_latku.
- rozsah otázky: ok · jazyk odpovede: cs (appka: cs) · preklad: ok

## Kroky agentov
- 2026-11-16T11:24:21Z · orchestrátor · LLM gemini-3.5-flash-lite · vstup: otázka: Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku? · persona: lekaren · výsledok: KIQ KIQ3 · krajiny SK · volania: nahrady_za_latku(SK, J01CR02, 5)
- 2026-11-16T11:24:21Z · zber · nahrady_za_latku · vstup: {"krajina":"SK","atc":"J01CR02","n":5} · výsledok: 10 z 24 riadkov · [E004, A1] [E005, A2] · 0.6 s
- 2026-11-16T11:24:28Z · analytik · LLM gemini-3.5-flash-lite · vstup: výsledky 1 volaní (4170 znakov JSON) · výsledok: 4 faktov, 1 úsudkov (2189 znakov)
- 2026-11-16T11:24:35Z · reportér · LLM gemini-3.5-flash-lite · vstup: zistenia analytika + výsledky nástrojov · výsledok: správa BLUF, 3086 znakov
- 2026-11-16T11:24:35Z · kritik · kontrola v kóde · vstup: správa 3086 znakov · výsledok: 0 problémov, 0 upozornení
- 2026-11-16T11:24:38Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: neschválené: Zoznam náhrad v BLUF a v texte obsahuje viac ako 5 položiek pre perorálnu suspenziu (uvedených je 7 položiek namiesto maximálne 5).
- 2026-11-16T11:24:43Z · reportér · LLM gemini-3.5-flash-lite · vstup: oprava podľa kritika · výsledok: správa BLUF, 2951 znakov
- 2026-11-16T11:24:43Z · kritik · kontrola v kóde · vstup: správa 2951 znakov · výsledok: 1 problémov, 0 upozornení: Znaky „ś, ć“ v slovenčine nie sú: „Dostupność“ – oprav napr. na „Dostupnosť“.
- 2026-11-16T11:24:44Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: schválené
- 2026-11-16T11:24:47Z · korektúra · LLM gemini-3.5-flash-lite · vstup: 1 riadkov s problémom: riadok 28: jazyk · výsledok: vymenené: riadok 28 (jazyk): „- Dostupność a objemy dodávok náhradných liekov MEDOCLAV a MEGAMOX v …“ → „- Dostupnosť a objemy dodávok náhradných liekov MEDOCLAV a MEGAMOX v distribučnej sieti.“
- 2026-11-16T11:24:47Z · korektúra · kontrola v kóde · vstup: správa po korektúre 2951 znakov · výsledok: 0 problémov
- 2026-11-16T11:24:53Z · preklad · LLM gemini-3.5-flash-lite · vstup: schválená správa so značkami (54 značiek, 27 riadkov) → cs · výsledok: preklad 2194 znakov
- 2026-11-16T11:24:53Z · preklad · kontrola v kóde · vstup: značky, čísla, citácie, kódy, úplnosť po riadkoch · výsledok: všetky riadky v poriadku
- 2026-11-16T11:24:53Z · preklad · kontrola v kóde · vstup: celá správa po vrátení značiek · výsledok: zhoda


## Kritik
- výsledok: schválené (kolo 2, opráv 1)
- upozornenie: LLM kritik (jazyk, rieši korektúra): V texte sa nachádzajú zakázané znaky v slove „Dostupność“ v sekcii Indicators to watch.


## Bezpečnosť
- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah z webu, žiadne osobné údaje.
