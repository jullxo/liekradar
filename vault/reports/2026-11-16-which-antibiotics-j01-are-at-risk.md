---
typ: sprava
otazka: "Which antibiotics (J01) are at risk of shortage in Slovakia?"
persona: lekaren
vytvorene_utc: 2026-11-16T10:23:03Z
model: gemini-3.5-flash-lite
kritik: schvalene
case_log: "[[cases/2026-11-16-which-antibiotics-j01-are-at-risk]]"
verified: false
---

# Prehľad rizikových antibiotík a odporúčania pre nákupcov lekárenských sietí na Slovensku

## Bottom line up front
Odhadujeme, že vznik výpadkov vybraných antibiotík (skupina J01) na slovenskom trhu je reálna možnosť (istota: stredná). Na slovenskom trhu čelia zvýšenému riziku výpadkov v skupine antibiotík (J01) predovšetkým lieky s vyšším rizikovým skóre, ako sú Metronidazol B. Braun 5 mg/ml (skóre 86), Gentamicin B. Braun 3 mg/ml infúzny roztok (skóre 83) a Ciprofloxacin Kabi 200 mg/100 ml (skóre 80) [E001, A2] [E005, A2]. Pre nákupcov lekárenských sietí je to signál na včasnú kontrolu skladových zásob, sledovanie dodávok a zabezpečenie dostupných alternatív [E001, A2] [E005, A2].

## Key judgements
- Odhadujeme, že prepojenie medzi výpadkami v Českej republike a historickými výpadkami na Slovensku predstavuje pre slovenský trh reálnu možnosť vzniku dodávkových problémov u sledovaných antibiotík (istota: stredná) [E001, A2] [E005, A2].
- Pravdepodobné je, že nákupcovia lekárenských sietí by mali venovať zvýšenú pozornosť predzásobeniu alternatívnymi baleniami a sledovať vývoj dodávok predovšetkým u preparátov s rizikovým skóre nad 70 (istota: stredná) [E005, A2].

## Discussion
- **Fakt:** Najvyššie rizikové skóre 86 v skupine antibiotík (J01) na slovenskom trhu dosahuje liek Metronidazol B. Braun 5 mg/ml, pričom príslušná účinná látka eviduje výpadok v ČR a výrobca aj samotný liek zaznamenali výpadky v predchádzajúcom období [E001, A2] [E005, A2].
- **Fakt:** Gentamicin B. Braun 3 mg/ml infúzny roztok dosahuje skóre 83 na základe historických výpadkov lieku a výrobcu na Slovensku [E005, A2].
- **Fakt:** Ciprofloxacin Kabi 200 mg/100 ml (skóre 80) a Ciprinol (skóre 68) vykazujú rizikové signály pre prepojenie s výpadkami ciprofloxacínu v ČR, novými výpadkami iných liekov s touto látkou v SR a históriou výpadkov výrobcov [E001, A2] [E005, A2].
- **Fakt:** Ďalšími liekmi so zvýšeným rizikom výpadku na Slovensku sú BISEPTOL 100 mg/20 mg (skóre 70), AXETINE 250 mg (skóre 70), KLERIMED 250 mg (skóre 67), MEDOCLAV 400 mg/5 ml + 57 mg/5 ml prášok na perorálnu suspenziu (skóre 65), Amikacin B.Braun 5 mg/ml (skóre 64) a Linezolid Sandoz 600 mg filmom obalené tablety (skóre 63) [E001, A2] [E005, A2].
- **Fakt:** Pre uvedené lieky sú k dispozícii iné balenia toho istého lieku, napríklad pre Metronidazol B. Braun 5 mg/ml, Gentamicin B. Braun 3 mg/ml infúzny roztok, Ciprofloxacin Kabi 200 mg/100 ml, BISEPTOL 100 mg/20 mg, AXETINE 250 mg, Ciprinol, KLERIMED 250 mg, MEDOCLAV 400 mg/5 ml + 57 mg/5 ml prášok na perorálnu suspenziu, Amikacin B.Braun 5 mg/ml a Linezolid Sandoz 600 mg filmom obalené tablety [E005, A2].
- **Úsudok:** Odhadujeme, že prepojenie medzi výpadkami v Českej republike a historickými výpadkami na Slovensku zvyšuje riziko obmedzenia dodávok kľúčových infúznych a perorálnych antibiotík (istota: stredná) [E001, A2] [E005, A2].
- **Úsudok:** Pravdepodobné je, že včasná identifikácia alternatívnych balení a aktívne riadenie zásob znížia dopad prípadných výpadkov v lekárenských sietiach (istota: stredná) [E005, A2].

## Alternative explanations
- Zvýšené rizikové skóre môže byť dôsledkom štatistických modelov a minulých výpadkov, ktoré sa v súčasnom období nemusia nutne premeniť na reálny nedostatok liekov na trhu.
- Výrobcovia môžu aktuálne výpadky alebo obmedzenia dodávok v susednej Českej republike kompenzovať presunom zásob na slovenský trh, čo zmierni riziko nedostatku.

## Key assumptions and gaps
- Dostupnosť reálnych skladových zásob u distribútorov a v jednotlivých lekárňach nie je v poskytnutých údajoch priamo zachytená.
- Chýbajú priame a aktuálne vyhlásenia držiteľov registrácie o presnom trvaní očakávaných obmedzení dodávok na slovenskom trhu.

## Indicators to watch
- Hlásenia o prerušení a obnovení dodávok liekov zo strany ŠÚKL pre skupinu J01.
- Vývoj hlásení o výpadkoch rovnakých účinných látok v registri SÚKL v Českej republike.
- Zmeny v skóre rizika a hlásenia o dodávkach od kľúčových výrobcov (B. Braun, Fresenius Kabi, Medochemie, Sandoz, Krka, Adamed Pharma).

## Sources and method annex
- SÚKL – hlásenia o uvedení, prerušení, ukončení a obnovení dodávok [E001, A2]
- ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok [E005, A2]
- Nástroj: `top_rizikove`

## AI use statement
- **Modely:** hlavný gemini-3.5-flash-lite.
- **Agenti (5) a kroky:**
  1. Orchestrátor – kontrola rozsahu otázky a plánovanie: témy otázky (riziko výpadku) a volania nástrojov (LLM gemini-3.5-flash-lite).
  2. Zber – nástroje nad pipeline.analytika, bez LLM: top_rizikove.
  3. Analytik – zistenia Fact / Inference z výsledkov nástrojov (LLM gemini-3.5-flash-lite).
  4. Reportér – správa BLUF, raz opravená podľa kritika (LLM gemini-3.5-flash-lite).
  5. Kritik – kontrola v kóde (sekcie, citácie podľa manifestu, mierka PHIA, čísla proti nástrojom, náhrady) a LLM (gemini-3.5-flash-lite).
- **Kolá opravy:** 1 (najviac 1).
- **Výsledok kontroly:** schválené v 2. kole (kontrola v kóde aj LLM).
- **Preklad:** kritik kontroloval slovenskú verziu; do jazyka EN ju preložil LLM (gemini-3.5-flash-lite) a kód overil, že citácie, čísla, kódy a názvy liekov sa zhodujú.
- **Volania modelu:** 7 (požiadaviek na Gemini vrátane opakovaní 7).
- **Ľudská kontrola:** správa nie je overená (verified: false); overí ju človek podľa Case Logu [[cases/2026-11-16-which-antibiotics-j01-are-at-risk]].
