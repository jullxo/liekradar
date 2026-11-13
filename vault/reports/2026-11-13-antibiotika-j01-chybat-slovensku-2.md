---
typ: sprava
otazka: "Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?"
persona: lekaren
vytvorene_utc: 2026-11-13T13:50:36Z
model: gemini-3.5-flash-lite
kritik: neschvalene
case_log: "[[cases/2026-11-13-antibiotika-j01-chybat-slovensku-2]]"
verified: false
---

# Riziká výpadkov antibiotík (J01) na slovenskom trhu a možnosti predzásobenia

## Bottom line up front
Na slovenskom trhu aktuálne hrozí výpadok najmä pri infúznych formách antibiotík *Metronidazol B. Braun 5 mg/ml* (modelové skóre rizika 86) a *Gentamicin B. Braun 3 mg/ml* (skóre rizika 83), pričom pre oba lieky existujú dostupné terapeutické aj balenové alternatívy [E005, A2]. Nákupcom lekárenských sietí sa odporúča vykonať revíziu skladových zásob a zvážiť preventívne predzásobenie alternatívnymi baleniami, avšak akúkoľvek zámenu lieku môže vykonať výlučne ošetrujúci lekár [E004, A1, E005, A2].

## Key judgements
- Odhadujeme, že pre látku Metronidazol (`J01XD01`) existuje reálna možnosť výpadku na Slovensku v dôsledku prebiehajúcich výpadkov v Českej republike a historickej chybovosti výrobcu; istota tohto úsudku je stredná.
- Pravdepodobne nastane potreba preventívneho predzásobenia lekárenskej siete alternatívnymi baleniami metronidazolu, keďže analýza preukazuje väzbu medzi výpadkami v ČR a SR s časovým posunom do 60 dní; istota tohto úsudku je stredná.
- Odhadujeme, že pri gentamicine (`J01GB03`) je veľmi pravdepodobný vznik koordinovaných výpadkov dodávok v oboch krajinách (historicky 3 prípady výpadkov so súbehom do 7 dní), čo pre nákupcu predstavuje bezprostredný signál na revíziu zásob; istota tohto úsudku je vysoká.

## Discussion
- **Fakt:** Najrizikovejším antibiotikom (skupina J01) na Slovensku bez aktuálne nahláseného výpadku je *Metronidazol B. Braun 5 mg/ml* (sol inf 20x100 ml/500 mg, ATC: `[[J01XD01]]`, držiteľ: *B.Braun Melsungen AG*) s modelovým skóre rizika 86 [E005, A2].
- **Fakt:** Druhým najrizikovejším liekom je *Gentamicin B. Braun 3 mg/ml infúzny roztok* (sol inf 20x80 ml/240 mg, ATC: `[[J01GB03]]`, držiteľ: *B.Braun Melsungen AG*) so skóre rizika 83 [E005, A2].
- **Fakt:** Medzi ďalšie rizikové lieky v skupine J01 patria *Ciprofloxacin Kabi 200 mg/100 ml* (skóre 80) [E001, A2, E005, A2], *BISEPTOL 100 mg/20 mg* (skóre 70) [E001, A2, E005, A2] a *AXETINE 250 mg* (skóre 70) [E001, A2, E005, A2].
- **Fakt:** Pre liek *Metronidazol B. Braun 5 mg/ml* (kód `76566`) sú v SR dostupné náhrady s rovnakou účinnou látkou, napríklad *Metronidazol B. Braun* (iná veľkosť balenia 10x100 ml, kód `76559`), *Efloran* (kód `88214`), *METRONIDAZOLE 0,5 % - POLPHARMA* (kód `3334D`), *Metronidazole Noridem* (kód `4256D`) a *Metronidazole VIOSER* (kód `3960F`), pričom všetky sa aktuálne dodávajú [E004, A1, E005, A2].
- **Fakt:** Pre liek *Gentamicin B. Braun 3 mg/ml* (kód `80181`) sú k dispozícii náhrady ako *Gentamicin B. Braun* (iná veľkosť balenia 20x120 ml, kód `80183`), *Gentamicin B. Braun 1 mg/ml* (kód `80179`), *GARAMYCIN SCHWAMM* (kód `8767D`) a injekčné formy *Gentamicin Noridem* (kódy `0943F`, `0940F`), pričom všetky sú v stave „dodáva sa“ [E004, A1, E005, A2].
- **Fakt:** Analýza časového posunu pre látku *METRONIDAZOL* (`J01XD01`) eviduje 8 vĺn výpadkov v ČR a 7 v SR, pričom v minulosti bol zaznamenaný prípad, kde ČR predchádzala SR o 54 dní [E001, A2, E005, A2].
- **Fakt:** Pre látku *GENTAMICIN* (`J01GB03`) eviduje model 7 vĺn výpadkov v ČR a 5 v SR, pričom v 3 prípadoch prebehli výpadky v oboch krajinách takmer súčasne (do 7 dní) [E001, A2, E005, A2].
- **Úsudok:** Odhadujeme, že prítomnosť skorších výpadkov metronidazolu v ČR môže viesť k reštrikciám dodávok na Slovensku v priebehu nasledujúcich týždňov, čím vzniká tlak na včasné zabezpečenie alternatívnych kódov (`76559`, `88214`).
- **Úsudok:** Odhadujeme, že predzásobenie alternatívnymi baleniami a formami (napr. iné objemy fliaš alebo injekčné roztoky gentamicinu) zmierni dopady prípadných výpadkov na lekárenskú sieť. Upozorňujeme, že zámenu lieku alebo inej látky môže urobiť len lekár, správu nemožno chápať ako lekárske odporúčanie pre pacientov.

## Alternative explanations
- Vysoké skóre rizika modelu môže byť spôsobené štatistickou volatilitou a administratívnymi výpadkami hlásení zo strany výrobcov bez reálneho dopadu na dostupnosť v lekárňach.
- Zvýšený dopyt v ČR a SR môže byť saturovaný inými paralelnými distribútormi, pričom k reálnemu nedostatku liekov pre pacientov dôjsť nemusí.

## Key assumptions and gaps
- Predpokladáme, že historické vzorce časového posunu medzi českým a slovenským trhom ostávajú zachované aj pre aktuálne vlny.
- Medzera v dátach spočíva v absencii reálnych čísel o fyzických skladových zásobách u jednotlivých distribútorov na Slovensku, čo neumožňuje presne kvantifikovať bod vyčerpania zásob.
- Chýbajú priame vyhlásenia držiteľov registrácie (B. Braun, Fresenius Kabi) o logistických dôvodoch hroziacich prerušení dodávok.

## Indicators to watch
- Denné hlásenia SÚKL a ŠÚKL o prerušení a obnovení dodávok pre lieky s ATC skupinou `J01XD` a `J01GB`.
- Vývoj objemov dodávok distribútorov (DIS-13) pre liek *Metronidazol B. Braun 5 mg/ml* (`76566`) a *Gentamicin B. Braun 3 mg/ml* (`80181`).
- Následné hlásenia o výpadkoch rovnakých liekov na českom trhu, ktoré slúžia ako skorý varovný signál pre SR.

## Sources and method annex
- [E001, A2] SÚKL – hlásenia o uvedení, prerušení, ukončení a obnovení dodávok (ČR)
- [E002, A1] SÚKL – databáza liekov DLP (ČR)
- [E003, A2] SÚKL – DIS-13 dodávky distribútorov (ČR)
- [E004, A1] ŠÚKL – register liekov (API) (SR)
- [E005, A2] ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok (SR)
- Použité analytické nástroje: `top_rizikove`, `nahrady`, `posun_latky`.

## AI use statement
Model: gemini-3.5-flash-lite. Kroky systému: orchestrátor (plán) → zber údajov (nástroje `pipeline.analytika`) → spracovanie analytikom → tvorba správy reportérom → kontrola kritikom. Správa je vygenerovaná automatizovane a čaká na finálnu kontrolu človekom (verified: false).

---

> **Kritik správu neschválil.** Zostávajúce problémy:
> - Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Medzi ďalšie rizikové lieky v skupine J01 patria *Ciprofloxacin Kabi 200 mg/100 ml* (skóre 80) [E001, A2, E…“
> - Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Pre liek *Metronidazol B. Braun 5 mg/ml* (kód `76566`) sú v SR dostupné náhrady s rovnakou účinnou látkou, …“
> - Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Pre liek *Gentamicin B. Braun 3 mg/ml* (kód `80181`) sú k dispozícii náhrady ako *Gentamicin B. Braun* (iná…“
> - Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Analýza časového posunu pre látku *METRONIDAZOL* (`J01XD01`) eviduje 8 vĺn výpadkov v ČR a 7 v SR, pričom v…“
> - Fakt bez citácie [ID, Admiralty]: „- **Fakt:** Pre látku *GENTAMICIN* (`J01GB03`) eviduje model 7 vĺn výpadkov v ČR a 5 v SR, pričom v 3 prípadoch prebehl…“
> - Niektoré fakty v sekcii Discussion neobsahujú povinnú citáciu [ID, Admiralty] na konci vety.
> - Tvrdenie o Ciprofloxacine a iných liekoch v zozname rizikových liekov má neúplné alebo chýbajúce zdrojové značky v súlade s manifestom.
