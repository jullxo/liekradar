---
typ: sprava
otazka: "Čím nahradiť amoxicilín s kyselinou klavulánovou, ak chýba na Slovensku?"
persona: lekaren
vytvorene_utc: 2026-11-15T13:07:46Z
model: gemini-3.5-flash-lite
kritik: schvalene
case_log: "[[cases/2026-11-15-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]]"
verified: false
---

# Možnosti náhrad amoxicilínu s kyselinou klavulánovou na slovenskom trhu

## Bottom line up front
Na Slovensku sa ako náhrada za vypadnuté tablety Amoksiklav 625 mg dodávajú MEDOCLAV 625 mg, MEGAMOX 625 forte, MEDOCLAV 1 g a MEDOCLAV 375 mg [E004, A1] [E005, A2]. Že tieto alternatívy zostanú dostupné aj v najbližších týždňoch, je pravdepodobné (istota: stredná).

## Key judgements
- Pravdepodobné je, že výpadok vybraných balení Amoksiklavu na Slovensku zvýši dopyt po alternatívnych liekoch s rovnakou účinnou látkou [E004, A1] [E005, A2]. Istota úsudku je stredná.
- Reálna možnosť je, že lekárne budú musieť flexibilne zabezpečovať zásoby iných síl alebo foriem v rámci rovnakej ATC skupiny [E004, A1] [E005, A2]. Istota úsudku je stredná.

## Discussion
- **Fakt:** Na slovenskom trhu sú hlásené výpadky liekov Amoksiklav 625 mg a Amoksiklav 457 mg/5 ml [E004, A1] [E005, A2].
- **Fakt:** Pre výpadok tablety Amoksiklav 625 mg sú dostupné náhrady MEDOCLAV 625 mg, MEGAMOX 625 forte, MEDOCLAV 1 g a MEDOCLAV 375 mg [E004, A1] [E005, A2].
- **Fakt:** Pre výpadok suspenzie Amoksiklav 457 mg/5 ml sú dostupné náhrady MEDOCLAV 400 mg/5 ml, MEDOCLAV FORTE 312,5 mg, MEDOCLAV 156,25 mg a MEGAMOX DUO [E004, A1] [E005, A2].
- **Úsudok:** Odhadujeme, že dopyt po alternatívnych značkách ako Medoclav a Megamox môže pri pretrchávajúcich výpadkoch rásť [E004, A1] [E005, A2].
- **Upozornenie:** Zámenu inej látky alebo liekovej formy môže urobiť len lekár; správa nie je odporúčanie pre pacientov.

## Alternative explanations
- Výpadok konkrétnych balení Amoksiklavu môže súvisieť s krátkodobými logistickými problémami výrobcu, zatiaľ čo zásoby iných síl u distribútorov sú dostatočné.

## Key assumptions and gaps
- Predpokladáme, že dostupné alternatívy s rovnakou liekovou formou sú pre pacientov zameniteľné po posúdení ošetrujúcim lekárom alebo lekárnikom.
- Dáta neobsahujú presné objemy aktuálnych fyzických zásob u distribútorov na slovenskom trhu ani presné trvanie hlásených výpadkov.

## Indicators to watch
- Vývoj hlásení o dodávkach a obnove distribúcie dotknutých liekov na portáli ŠÚKL.
- Stav dostupnosti alternatívnych síl a foriem v distribučných sieťach.

## Sources and method annex
- Zdroj [E004, A1]: ŠÚKL – register liekov (API).
- Zdroj [E005, A2]: ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok.
- Nástroje: `nahrady_za_latku`.

## AI use statement
- **Modely:** hlavný gemini-3.5-flash-lite.
- **Agenti (5) a kroky:**
  1. Orchestrátor – plánovanie: témy otázky (náhrady) a volania nástrojov (LLM gemini-3.5-flash-lite).
  2. Zber – nástroje nad pipeline.analytika, bez LLM: nahrady_za_latku.
  3. Analytik – zistenia Fact / Inference z výsledkov nástrojov (LLM gemini-3.5-flash-lite).
  4. Reportér – správa BLUF, raz opravená podľa kritika (LLM gemini-3.5-flash-lite).
  5. Kritik – kontrola v kóde (sekcie, citácie podľa manifestu, mierka PHIA, čísla proti nástrojom, náhrady) a LLM (gemini-3.5-flash-lite).
- **Kolá opravy:** 1 (najviac 1).
- **Výsledok kontroly:** schválené v 2. kole (kontrola v kóde aj LLM).
- **Volania modelu:** 6 (požiadaviek na Gemini vrátane opakovaní 6).
- **Ľudská kontrola:** správa nie je overená (verified: false); overí ju človek podľa Case Logu [[cases/2026-11-15-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]].
