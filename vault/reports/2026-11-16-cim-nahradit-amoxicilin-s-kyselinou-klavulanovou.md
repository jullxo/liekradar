---
typ: sprava
otazka: "Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku?"
persona: lekaren
vytvorene_utc: 2026-11-16T11:24:53Z
model: gemini-3.5-flash-lite
kritik: schvalene
case_log: "[[cases/2026-11-16-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]]"
verified: false
---

# Možnosti náhrady liekov s obsahom amoxicilínu a inhibítora betalaktamázy pri výpadku na Slovensku

## Bottom line up front
Za tablety Amoksiklav 625 mg sa dodávajú MEDOCLAV 625 mg a MEGAMOX 625 forte; za perorálnu suspenziu Amoksiklav 156,25 mg/5 ml sa dodávajú MEDOCLAV 156,25 mg, MEDOCLAV FORTE 312,5 mg a MEGAMOX DUO [E004, A1] [E005, A2]. Zabezpečenie týchto náhrad pre lekárenskú sieť je pravdepodobné (istota: stredná).

## Key judgements
- Dostupnosť rovnakej liekovej formy a rovnakej sily pre tablety aj suspenzie u iných alternatívnych produktov na slovenskom trhu je pravdepodobná (istota: stredná).
- Zvýšený dopyt po iných silách alebo iných baleniach toho istého lieku predstavuje reálnu možnosť vzniku lokálnych nedostatkov v sieti (istota: stredná).
- Aktívne sledovanie a predzásobenie dostupnými alternatívami zo strany nákupcov lekárenských sietí je reálna možnosť na zmiernenie dopadov výpadku (istota: stredná).

## Discussion
- **Fakt:** Na slovenskom trhu sú hlásené výpadky liekov Amoksiklav 625 mg (forma TBL FLM) a Amoksiklav 156,25 mg/5 ml (forma PLU POR) patriacich do ATC skupiny J01CR02 [E004, A1] [E005, A2].
- **Fakt:** Za tablety Amoksiklav 625 mg sa dodávajú MEDOCLAV 625 mg a MEGAMOX 625 forte [E004, A1] [E005, A2].
- **Fakt:** Za perorálnu suspenziu Amoksiklav 156,25 mg/5 ml sa dodávajú MEDOCLAV 156,25 mg, MEDOCLAV FORTE 312,5 mg a MEGAMOX DUO [E004, A1] [E005, A2].
- **Fakt:** Dodáva sa aj iné balenie toho istého lieku Amoksiklav 625 mg a Amoksiklav 156,25 mg/5 ml [E004, A1] [E005, A2].
- **Úsudok:** Pravdepodobné je, že nákupcovia lekárenských sietí by mali prioritne zabezpečiť dostupné rovnaké liekové formy (napr. MEDOCLAV a MEGAMOX), pričom pri zmene sily alebo prechode na iné balenie bude potrebná opatrnosť.
- **Upozornenie:** Zámenu inej látky alebo liekovej formy môže urobiť len lekár; správa nie je odporúčanie pre pacientov.

## Alternative explanations
- Výpadok dodávok môže byť spôsobený krátkodobým logistickým výpadkom u držiteľa registrácie a dodávky sa môžu obnoviť bez nutnosti dlhodobého preorientovania na náhradné produkty.
- Alternatívne lieky môžu taktiež zaznamenať zvýšený odbyt, čo by mohlo viesť k ich vyčerpaniu u distribútorov v krátkom čase.

## Key assumptions and gaps
- Predpokladáme, že aktuálne dáta z registrov a hlásení SÚKL a ŠÚKL verne odrážajú reálny stav dostupnosti na trhu.
- Chýbajú detailné údaje o fyzických zásobách u jednotlivých distribútorov a presné dátumy ukončenia výpadku pre dotknuté lieky.

## Indicators to watch
- Zmeny v hláseniach o prerušení a obnovení dodávok liekov v registri ŠÚKL pre ATC skupinu J01CR02.
- Dostupnosť a objemy dodávok náhradných liekov MEDOCLAV a MEGAMOX v distribučnej sieti.

## Sources and method annex
- [E004, A1] ŠÚKL – register liekov (API)
- [E005, A2] ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok
- Nástroje: `nahrady_za_latku`

## AI use statement
- **Modely:** hlavný gemini-3.5-flash-lite.
- **Agenti (5) a kroky:**
  1. Orchestrátor – kontrola rozsahu otázky a plánovanie: témy otázky (náhrady) a volania nástrojov (LLM gemini-3.5-flash-lite).
  2. Zber – nástroje nad pipeline.analytika, bez LLM: nahrady_za_latku.
  3. Analytik – zistenia Fact / Inference z výsledkov nástrojov (LLM gemini-3.5-flash-lite).
  4. Reportér – správa BLUF, raz opravená podľa kritika (LLM gemini-3.5-flash-lite).
  5. Kritik – kontrola v kóde (sekcie, citácie podľa manifestu, mierka PHIA, čísla proti nástrojom, náhrady) a LLM (gemini-3.5-flash-lite); cielená oprava 1 riadkov (cudzie znaky, LLM gemini-3.5-flash-lite).
- **Kolá opravy:** 1 (najviac 1).
- **Výsledok kontroly:** schválené po korektúre riadkov v 2. kole (kontrola v kóde aj LLM).
- **Preklad:** kritik kontroloval slovenskú verziu; do jazyka CS ju preložil LLM (gemini-3.5-flash-lite) a kód overil, že citácie, čísla, kódy a názvy liekov sa zhodujú.
- **Volania modelu:** 8 (požiadaviek na Gemini vrátane opakovaní 8).
- **Ľudská kontrola:** správa nie je overená (verified: false); overí ju človek podľa Case Logu [[cases/2026-11-16-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]].
