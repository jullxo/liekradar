---
typ: sprava
otazka: "Ktoré antibiotiká (J01) hrozí, že budú chýbať na Slovensku?"
persona: lekaren
vytvorene_utc: 2026-11-15T13:17:58Z
model: gemini-3.5-flash-lite
kritik: schvalene
case_log: "[[cases/2026-11-15-antibiotika-j01-chybat-slovensku]]"
verified: false
---

# Riziká výpadkov antibiotík na Slovensku a vplyv vývoja v Česku

## Bottom line up front
Odhadujeme, že zvýšenému riziku výpadkov na Slovensku čelia najmä antibiotiká *Metronidazol B. Braun 5 mg/ml*, *Gentamicin B. Braun 3 mg/ml infúzny roztok*, *Ciprofloxacin Kabi 200 mg/100 ml*, *BISEPTOL 100 mg/20 mg*, *AXETINE 250 mg*, *Ciprinol*, *KLERIMED 250 mg*, *MEDOCLAV 400 mg/5 ml + 57 mg/5 ml*, *Amikacin B.Braun 5 mg/ml* a *Linezolid Sandoz 600 mg filmom obalené tablety*, pričom pre nákupcu lekárenskej siete ide o reálnu možnosť obmedzení dodávok (istota: stredná). Pre predzásobenie a riadenie zásob je dôležité sledovať perorálne formy, ako sú *Axetine*, *Biseptol*, *Klerimed* a *Medoclav*, a zohľadniť časové posuny výpadkov z Českej republiky [E001, A2].

## Key judgements
- Odhadujeme, že antibiotiká so signalizovanými výpadkami látok v Česku majú reálnu možnosť čeliť obmedzeniam dodávok aj na Slovensku (stredná istota).
- Pravdepodobné je, že opakované výpadky výrobcov za posledné obdobie zvýšia tlak na dostupnosť alternatívnych balení a foriem (stredná istota).
- Pravdepodobné je, že prepojenie dodávateľských reťazcov medzi Českou republikou a Slovenskom spôsobí, že výpadky hlásené v Česku sa prejavia na slovenskom trhu s miernym časovým posunom (stredná istota).

## Discussion
- **Fakt:** Najvyššie skóre rizika (86) dosahuje infúzny liek *Metronidazol B. Braun 5 mg/ml*, pričom dôvodom je výpadok látky v ČR za posledných 60 dní [E001, A2], historické výpadky v SR [E005, A2] a časté výpadky výrobcu B.Braun Melsungen AG [E005, A2].
- **Fakt:** Rizikové skóre 83 eviduje *Gentamicin B. Braun 3 mg/ml infúzny roztok* pre minulé výpadky v SR [E005, A2] a záťaž na strane výrobcu B.Braun Melsungen AG [E005, A2].
- **Fakt:** Infúzne formy ciprofloxacínu (*Ciprofloxacin Kabi 200 mg/100 ml* so skóre 80 a *Ciprinol* so skóre 68) vykazujú riziko pre výpadky látky v ČR [E001, A2], nové výpadky iných liekov s touto látkou v SR [E005, A2] a históriu výpadkov v SR [E005, A2].
- **Fakt:** Z perorálnych liekov dosahuje *BISEPTOL 100 mg/20 mg* skóre 70 pre výpadok látky v ČR [E001, A2] a históriu výrobcu Adamed Pharma S.A. v SR [E005, A2].
- **Fakt:** *AXETINE 250 mg* (látka cefuroxim) má skóre 70 pre výpadok v ČR [E001, A2], nové výpadky iných liekov s touto látkou v SR [E005, A2] a historické záznamy výrobcu MEDOCHEMIE Ltd. v SR [E005, A2].
- **Fakt:** Tabletové formy a suspenzie ako *KLERIMED 250 mg* (skóre 67) a *MEDOCLAV 400 mg/5 ml + 57 mg/5 ml prášok na perorálnu suspenziu* (skóre 65) sú ohrozené pre nové výpadky iných liekov s rovnakou látkou v SR [E005, A2] a výpadky látky v ČR [E001, A2].
- **Fakt:** Nemocničné antibiotiká *Amikacin B.Braun 5 mg/ml* (skóre 64) a *Linezolid Sandoz 600 mg filmom obalené tablety* (skóre 63) taktiež figurujú v zoznamoch s rizikovým skóre pre predchádzajúce výpadky v ČR [E001, A2] a v SR [E005, A2].
- **Úsudok:** Odhadujeme, že nákupcovia lekárenských sietí budú musieť v prípade výpadkov aktívne vyhľadávať alternatívne liekové formy alebo iných držiteľov registrácie pre látky ako cefuroxim a amoxicilín s inhibitorom beta-laktamázy.
- **Upozornenie:** Zámenu inej látky alebo liekovej formy môže urobiť len lekár; správa nie je odporúčanje pre pacientov.

## Alternative explanations
- Súčasné skóre rizika môže odrážať skôr administratívne hlásenia a historickú záťaž výrobcov než reálny akútny nedostatok liekov na slovenských lekárenských pobočkách.
- Výrobcovia môžu na hroziace výpadky v regióne zareagovať posilnením logistických tokov a presmerovaním zásob, čo zmierni dopad na koncových pacientov.

## Key assumptions and gaps
- Model neobsahuje aktuálne údaje o reálnych skladových zásobách u distribútorov na Slovensku, ale spolieha sa na historické signály výpadkov a hlásenia o dodávkach.
- Chýbajú priame kvantitatívne dáta o objeme spotreby pacientov pre jednotlivé liekové formy a balenia.

## Indicators to watch
- Hlásenia SÚKL a ŠÚKL o prerušení a obnove dodávok pre ATC skupinu J01.
- Dostupnosť alternatívnych balení a iných liekov s obsahom cefuroximu a ciprofloxacínu na slovenskom trhu.

## Sources and method annex
- Model v1 (váhy z logistickej regresie, spätný test od 2024-07: top 100 presnosť 13,6 %, lift 55,7×).
- Použité zdroje: E001 (SÚKL ČR – hlásenia o uvedení, prerušení, ukončení a obnovení dodávok) [E001, A2], E005 (ŠÚKL SR – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok) [E005, A2].
- Nástroje: `top_rizikove(krajina=SK, atc_prefix=J01, n=10)`.

## AI use statement
- **Modely:** hlavný gemini-3.5-flash-lite.
- **Agenti (5) a kroky:**
  1. Orchestrátor – plánovanie: témy otázky (riziko výpadku) a volania nástrojov (LLM gemini-3.5-flash-lite).
  2. Zber – nástroje nad pipeline.analytika, bez LLM: top_rizikove.
  3. Analytik – zistenia Fact / Inference z výsledkov nástrojov (LLM gemini-3.5-flash-lite).
  4. Reportér – správa BLUF, raz opravená podľa kritika (LLM gemini-3.5-flash-lite).
  5. Kritik – kontrola v kóde (sekcie, citácie podľa manifestu, mierka PHIA, čísla proti nástrojom, náhrady) a LLM (gemini-3.5-flash-lite).
- **Kolá opravy:** 1 (najviac 1).
- **Výsledok kontroly:** schválené v 2. kole (kontrola v kóde aj LLM).
- **Volania modelu:** 6 (požiadaviek na Gemini vrátane opakovaní 7).
- **Ľudská kontrola:** správa nie je overená (verified: false); overí ju človek podľa Case Logu [[cases/2026-11-15-antibiotika-j01-chybat-slovensku]].
