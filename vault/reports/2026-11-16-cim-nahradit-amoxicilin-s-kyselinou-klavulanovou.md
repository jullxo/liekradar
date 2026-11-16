---
typ: sprava
otazka: "Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku?"
persona: lekaren
vytvorene_utc: 2026-11-16T10:44:28Z
model: gemini-3.5-flash-lite
kritik: schvalene
case_log: "[[cases/2026-11-16-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]]"
verified: false
---

# Náhrady za lieky s obsahom amoxicilínu a inhibítora beta-laktamázy na slovenskom trhu

## Bottom line up front
Za tablety Amoksiklav 625 mg sa dodávajú MEDOCLAV 625 mg, MEGAMOX 625 forte, MEDOCLAV 1 g a MEDOCLAV 375 mg; za suspenziu Amoksiklav 156,25 mg/5 ml sa dodávajú MEDOCLAV 156,25 mg, MEDOCLAV 400 mg/5 ml + 57 mg/5 ml prášok na perorálnu suspenziu, MEDOCLAV FORTE 312,5 mg a MEGAMOX DUO [E004, A1] [E005, A2]. Zabezpečenie kontinuity liečby pre lekárenské siete prostreditectvom týchto generických alternatív je reálna možnosť (istota: stredná).

## Key judgements
- Zaistenie kontinuity liečby prostredníctvom generických alternatív s rovnakou liekovou formou je reálna možnosť, pričom istota tohto úsudku je stredná.
- Výpadky v Českej republike pôsobia ako signál pre možné riziko výpadkov súvisiacich liekov aj na slovenskom trhu – pravdepodobné je, že dodávateľské reťazce vykazujú prepojenosť (istota: stredná).
- Pri predzásobení lekárenskej siete je potrebné zohľadniť, že model identifikuje zvýšené riziko výpadku pre vybrané alternatívy na základe predchádzajúcich výpadkov – pravdepodobné, istota: stredná.

## Discussion
- **Fakt:** Na slovenskom trhu sú hlásené výpadky liekov s obsahom účinnej látky amoxicilín a inhibitor beta-laktamázy (`J01CR02`), konkrétne pre lieky Amoksiklav 625 mg a Amoksiklav 156,25 mg/5 ml [E004, A1] [E005, A2].
- **Fakt:** Za tablety Amoksiklav 625 mg sa v rovnakej liekovej forme dodávajú MEDOCLAV 625 mg, MEGAMOX 625 forte, MEDOCLAV 1 g, MEDOCLAV 375 mg a MEGAMOX BID 1 g [E004, A1] [E005, A2].
- **Fakt:** Za suspenziu Amoksiklav 156,25 mg/5 ml sa v rovnakej liekovej forme dodávajú MEDOCLAV 156,25 mg, MEDOCLAV 400 mg/5 ml + 57 mg/5 ml prášok na perorálnu suspenziu, MEDOCLAV FORTE 312,5 mg a MEGAMOX DUO [E004, A1] [E005, A2].
- **Fakt:** Pre liek Amoksiklav 625 mg existuje iné balenie toho istého lieku pod kódom 9232D [E004, A1] [E005, A2].
- **Fakt:** Pre liek Amoksiklav 156,25 mg/5 ml existuje iné balenie toho istého lieku pod kódom 0634E, pričom iným balením toho istého lieku je aj Amoksiklav 2x457 mg/5 ml [E004, A1] [E005, A2].
- **Fakt:** Model identifikuje riziko výpadku pre liek MEDOCLAV prášok na perorálnu suspenziu so skóre 65, pričom dôvodom je výpadok látky v ČR za posledných 60 dní a historické výpadky na Slovensku [E001, A2] [E005, A2].
- **Úsudok:** Odhadujeme, že pre lekárenské siete existuje reálna možnosť zabezpečiť kontinuitu liečby pre pacientov prostredníctvom dostupných generických alternatív s rovnakou liekovou formou.
- **Úsudok:** Pravdepodobné je, že výpadky v Českej republike môžu slúžiť ako signál pre možné riziko výpadkov súvisiacich liekov aj na slovenskom trhu, vzhľadom na prepojenosť dodávateľských reťazcov.
- **Upozornenie:** Zámenu inej látky alebo liekovej formy môže urobiť len lekár; správa nie je odporúčanie pre pacientov.

## Alternative explanations
- Zvýšené riziko výpadku modelované pre alternatívne lieky nemusí viesť k reálnemu výpadku na trhu, ak držitelia registrácie včas navýšia dodávky distribútorom.
- Výpadky v ČR nemusia nevyhnutne predikovať výpadky na slovenskom trhu, nakoľko distribučné a dodávateľské kanály sa môžu medzi oboma krajinami líšiť.

## Key assumptions and gaps
- Dáta neobsahujú informácie o reálnych skladových zásobách u jednotlivých distribútorov v SR, ale iba registračné údaje a hlásenia výpadkov.
- Predpokladá sa, že súčasní dodávatelia generických alternatív dokážu pokryť zvýšený dopyt lekárenských sietí pri výpadku pôvodných liekov.

## Indicators to watch
- Hlásenia o prerušení alebo obnovení dodávok liekov s účinnou látkou amoxicilín a inhibítor beta-laktamázy v registri ŠÚKL.
- Vývoj skóre rizika pre lieky MEDOCLAV a ďalšie alternatívy v modelovom hodnotení pre slovenský trh.
- Dostupnosť a stav skladových zásob u hlavných distribútorov v SR.

## Sources and method annex
- [E001, A2] SÚKL – hlásenia o uvedení, prerušení, ukončení a obnovení dodávok (ČR)
- [E004, A1] ŠÚKL – register liekov (API) (SR)
- [E005, A2] ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok (SR)
- Nástroje: `nahrady_za_latku`, `top_rizikove`

## AI use statement
- **Modely:** hlavný gemini-3.5-flash-lite.
- **Agenti (5) a kroky:**
  1. Orchestrátor – kontrola rozsahu otázky a plánovanie: témy otázky (náhrady, riziko výpadku) a volania nástrojov (LLM gemini-3.5-flash-lite).
  2. Zber – nástroje nad pipeline.analytika, bez LLM: nahrady_za_latku, top_rizikove.
  3. Analytik – zistenia Fact / Inference z výsledkov nástrojov (LLM gemini-3.5-flash-lite).
  4. Reportér – správa BLUF, raz opravená podľa kritika (LLM gemini-3.5-flash-lite).
  5. Kritik – kontrola v kóde (sekcie, citácie podľa manifestu, mierka PHIA, čísla proti nástrojom, náhrady) a LLM (gemini-3.5-flash-lite).
- **Kolá opravy:** 1 (najviac 1).
- **Výsledok kontroly:** schválené v 2. kole (kontrola v kóde aj LLM).
- **Preklad:** preklad do jazyka CS sa nepoužil (nezhoda údajov alebo neúplný preklad); zobrazená je slovenská verzia.
- **Volania modelu:** 7 (požiadaviek na Gemini vrátane opakovaní 7).
- **Ľudská kontrola:** správa nie je overená (verified: false); overí ju človek podľa Case Logu [[cases/2026-11-16-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]].
