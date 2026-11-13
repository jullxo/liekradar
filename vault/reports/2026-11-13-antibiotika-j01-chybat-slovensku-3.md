---
typ: sprava
otazka: "Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?"
persona: lekaren
vytvorene_utc: 2026-11-13T14:29:17Z
model: gemini-3.5-flash-lite
kritik: schvalene
case_log: "[[cases/2026-11-13-antibiotika-j01-chybat-slovensku-3]]"
verified: false
---

# Riziká výpadkov antibiotík (J01) na Slovensku a možnosti predzásobenia

## Bottom line up front
Odhadujeme, že riziko výpadku najrizikovejších infúznych antibiotík na Slovensku, najmä liekov `Metronidazol B. Braun 5 mg/ml` a `Gentamicin B. Braun 3 mg/ml infúzny roztok`, je pravdepodobné (istota: stredná). Nákupca lekárenskej siete by mal včas reagovať na signály z modelov a sledovať dostupné alternatívy s rovnakou liekovou formou.

## Key judgements
- Odhadujeme, že predzásobenie alternatívnymi baleniami a registrovanými náhradami s rovnakou liekovou formou (`SOL INF`) pre lieky `Metronidazol B. Braun 5 mg/ml` a `Gentamicin B. Braun 3 mg/ml infúzny roztok` je pravdepodobné (istota: stredná).
- Pravdepodobne nastane reálna potreba sledovať aj ciprofloxacinové prípravky (`Ciprofloxacin Kabi`, `MEDOCIPRIN`, `Ciprinol`), nakoľko látka vykazuje súbežné výpadky v Českej republike a nové výpadky iných liekov s touto látkou na Slovensku (pravdepodobnosť: reálna možnosť, istota: stredná).
- Odhadujeme, že časový posun výpadkov z ČR do SR pri antiinfektívach zohráva signifikantnú úlohu, čo pre lekárenskú sieť vytvára časové okno na preventívne predzásobenie (pravdepodobnosť: pravdepodobné, istota: stredná).

## Discussion
- **Fakt:** Model identifikoval 10 najrizikovejších antibiotík (ATC skupina J01) na Slovensku, pričom na prvom mieste je liek `Metronidazol B. Braun 5 mg/ml` (kód 76566, doplnok `sol inf 20x100 ml/500 mg (fľ. PE)`, ATC `J01XD01`, skóre 86) [E001, A2] [E005, A2].
- **Fakt:** Druhým najrizikovejším liekom je `Gentamicin B. Braun 3 mg/ml infúzny roztok` (kód 80181, doplnok `sol inf 20x80 ml/240 mg (fľ. LDPE)`, ATC `J01GB03`, skóre 83) [E005, A2].
- **Fakt:** Medzi ďalšie rizikové lieky s vysokým skóre patria `Ciprofloxacin Kabi 200 mg/100 ml` (skóre 80), `BISEPTOL 100 mg/20 mg` (skóre 70), `AXETINE 250 mg` (skóre 70), `MEDOCIPRIN 500 mg` (skóre 70), `Ciprinol` (skóre 68), `KLERIMED 250 mg` (skóre 67), `MEDOCLAV` (skóre 65) a `Amikacin B.Braun 5 mg/ml` (skóre 64) [E001, A2] [E005, A2].
- **Fakt:** Pre liek `Metronidazol B. Braun 5 mg/ml` (76566) sú dostupné náhrady s rovnakou formou `SOL INF`: `Metronidazol B. Braun 5 mg/ml` (iná veľkosť balenia 10x100 ml, kód 76559), `Efloran` (kód 88214), `METRONIDAZOL 0,5 % - POLPHARMA` (kód 3334D), `Metronidazole Noridem 5 mg/ml` (kód 4256D) a `Metronidazole VIOSER 5 mg/ml` (kód 3960F) [E004, A1] [E005, A2].
- **Fakt:** Pre liek `Gentamicin B. Braun 3 mg/ml infúzny roztok` (80181) sú dostupné náhrady s rovnakou formou `SOL INF`: `Gentamicin B. Braun 3 mg/ml` (iná veľkosť balenia 20x120 ml/360 mg, kód 80183) a `Gentamicin B. Braun 1 mg/ml` (kód 80179) [E004, A1] [E005, A2].
- **Fakt:** U gentamicinu (`J01GB03`) sa v minulosti zaznamenali súbežné výpadky v ČR a SR v 3 prípadoch do 7 dní a v 1 prípade do 60 dní [E001, A2] [E005, A2].
- **Úsudok:** Odhadujeme, že pre nákupcu lekárenskej siete predstavujú najvyššie riziko výpadku infúzne formy antibiotík od spoločnosti B.Braun, pričom predzásobenie alternatívnymi baleniami s rovnakou liekovou formou zmierni dopad prípadných výpadkov.
- **Úsudok:** Pravdepodobne nastane reálna potreba sledovať aj ciprofloxacinové prípravky kvôli prebiehajúcim výpadkom látky v Českej republike a novým výpadkom iných liekov s touto látkou na Slovensku.
- Iná forma, len po posúdení lekárom: Pre gentamicin (`J01GB03`) evidujú nástroje aj formy `IMP` (implantát `GARAMYCIN SCHWAMM`, kód 8767D) a `SOL IJF` (injekčný roztok `Gentamicin Noridem`, kódy 0943F, 0940F) [E004, A1] [E005, A2].
- **Upozornenie:** Zámenu inej látky alebo liekovej formy môže urobiť len lekár; správa nie je odporúčanie pre pacientov.

## Alternative explanations
- Výrobné výkyvy u držiteľov registrácie môžu byť dočasného charakteru a nemusia viesť k reálnemu nedostatku liekov v lekárenskej sieti, pokiaľ distribútori disponujú dostatočnými bezpečnostnými zásobami.
- Signály o výpadkoch v Českej republike sa nemusia nutne prejaviť na Slovensku s rovnakou intenzitou v závislosti od logistických tokov a nastavenia dodávateľských reťazcov jednotlivých výrobcov.

## Key assumptions and gaps
- Predpokladáme, že historické vzorce správania dodávok a časových posunov medzi ČR a SR zostávajú pre model validné aj v aktuálnom období.
- Medzerou v dátach je absencia reálnych údajov o aktuálnych skladových zásobách u jednotlivých distribútorov na Slovensku a chýbajúce presné kvantitatívne dáta o spotrebe v lekárenských sieťach.

## Indicators to watch
- Hlásenia o prerušení alebo obnovení dodávok liekov od SÚKL a ŠÚKL pre ATC skupinu J01.
- Vývoj počtu aktívnych výpadkov ciprofloxacínu a metronidazolu na slovenskom a českom trhu.
- Zmeny v stave registrácií a dostupnosti alternatívnych balení s rovnakou liekovou formou (`SOL INF`).

## Sources and method annex
- SÚKL – hlásenia o uvedení, prerušení, ukončení a obnovení dodávok [E001, A2]
- SÚKL – databáza liekov DLP [E002, A1]
- SÚKL – DIS-13 dodávky distribútorov [E003, A2]
- ŠÚKL – register liekov (API) [E004, A1]
- ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok [E005, A2]
- Nástroje: `top_rizikove`, `nahrady`, `posun_latky`

## AI use statement
- **Modely:** hlavný gemini-3.5-flash-lite.
- **Agenti (5) a kroky:**
  1. Orchestrátor – plánovanie: KIQ a volania nástrojov (LLM gemini-3.5-flash-lite).
  2. Zber – nástroje nad pipeline.analytika, bez LLM: top_rizikove, nahrady ×2, posun_latky ×2.
  3. Analytik – zistenia Fact / Inference z výsledkov nástrojov (LLM gemini-3.5-flash-lite).
  4. Reportér – správa BLUF (LLM gemini-3.5-flash-lite).
  5. Kritik – kontrola v kóde (sekcie, citácie podľa manifestu, mierka PHIA, čísla proti nástrojom, náhrady) a LLM (gemini-3.5-flash-lite).
- **Kolá opravy:** 0 (najviac 1).
- **Výsledok kontroly:** schválené v 1. kole (kontrola v kóde aj LLM).
- **Volania modelu:** 4 (požiadaviek na Gemini vrátane opakovaní 4).
- **Ľudská kontrola:** správa nie je overená (verified: false); overí ju človek podľa Case Logu [[cases/2026-11-13-antibiotika-j01-chybat-slovensku-3]].
