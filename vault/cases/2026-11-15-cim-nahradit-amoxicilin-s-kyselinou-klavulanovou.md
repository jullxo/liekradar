---
typ: case-log
otazka: "Čím nahradiť amoxicilín s kyselinou klavulánovou, ak chýba na Slovensku?"
persona: lekaren
zaciatok_utc: 2026-11-15T13:07:30Z
koniec_utc: 2026-11-15T13:07:46Z
model: gemini-3.5-flash-lite
volania_modelu: 6
poziadavky_na_model: 6
sprava: "[[reports/2026-11-15-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]]"
verified: false
---

# Case Log – Čím nahradiť amoxicilín s kyselinou klavulánovou, ak chýba na Slovensku?

## Plán (orchestrátor)
- KIQ: KIQ3 · krajiny: SK · ATC prefix: J01CR
- zdôvodnenie: Otázka sa pýta na náhrady pre amoxicilín s kyselinou klavulánovou (ATC7 J01CR02) na Slovensku, preto volíme KIQ3 a nástroj nahrady_za_latku.

## Kroky agentov
- 2026-11-15T13:07:33Z · orchestrátor · LLM gemini-3.5-flash-lite · vstup: otázka: Čím nahradiť amoxicilín s kyselinou klavulánovou, ak chýba na Slovensku? · persona: lekaren · výsledok: KIQ KIQ3 · krajiny SK · volania: nahrady_za_latku(SK, J01CR02, 10)
- 2026-11-15T13:07:34Z · zber · nahrady_za_latku · vstup: {"krajina":"SK","atc":"J01CR02","n":10} · výsledok: 10 z 24 riadkov · [E004, A1] [E005, A2] · 0.6 s
- 2026-11-15T13:07:38Z · analytik · LLM gemini-3.5-flash-lite · vstup: výsledky 1 volaní (3552 znakov JSON) · výsledok: 3 faktov, 2 úsudkov (2958 znakov)
- 2026-11-15T13:07:41Z · reportér · LLM gemini-3.5-flash-lite · vstup: zistenia analytika + výsledky nástrojov · výsledok: správa BLUF, 2779 znakov
- 2026-11-15T13:07:41Z · kritik · kontrola v kóde · vstup: správa 2779 znakov · výsledok: 4 problémov, 0 upozornení: Prvé dve vety BLUF nemajú výraz z mierky PHIA a istotu (nízka/stredná): „Na Slovensku sa ako náhrada za vypadnuté tablety Amoksiklav 625 mg dodávajú MEDOCLAV 625 mg, MEGAMOX 625 forte, MEDOCLA…
- 2026-11-15T13:07:42Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: neschválené: V zozname náhrad pre tablety Amoksiklav 625 mg je uvedených 5 položiek, ale v niektorých častiach sa spomína viacero alternatív a je nutné presne dodržať limit najviac 5 náhrad na skupinu.; Náhrada pre susp…
- 2026-11-15T13:07:45Z · reportér · LLM gemini-3.5-flash-lite · vstup: oprava podľa kritika · výsledok: správa BLUF, 2435 znakov
- 2026-11-15T13:07:45Z · kritik · kontrola v kóde · vstup: správa 2435 znakov · výsledok: 0 problémov, 0 upozornení
- 2026-11-15T13:07:46Z · kritik · LLM gemini-3.5-flash-lite · vstup: správa + výsledky nástrojov + kontrola v kóde · výsledok: schválené

## Kritik
- výsledok: schválené (kolo 2, opráv 1)


## Bezpečnosť
- Spracované len výsledky nástrojov nad verejnými dátami SÚKL/ŠÚKL; žiadny obsah z webu, žiadne osobné údaje.
