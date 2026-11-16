---
typ: sprava-preklad
jazyk: cs
povodna: "[[reports/2026-11-16-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]]"
verified: false
---

# Možnosti náhrady léků s obsahem amoxicilinu a inhibitoru betalaktamázy při výpadku na Slovensku

## Bottom line up front
Za tablety Amoksiklav 625 mg se dodávají MEDOCLAV 625 mg a MEGAMOX 625 forte; za perorální suspenzi Amoksiklav 156,25 mg/5 ml se dodávají MEDOCLAV 156,25 mg, MEDOCLAV FORTE 312,5 mg a MEGAMOX DUO [E004, A1] [E005, A2]. Zabezpečení těchto náhrad pro lékárenskou síť je pravděpodobné (jistota: střední).

## Key judgements
- Dostupnost stejné lékové formy a stejné síly pro tablety i suspenze u jiných alternativních produktů na slovenském trhu je pravděpodobná (jistota: střední).
- Zvýšená poptávka po jiných silách nebo jiných baleních téhož léku představuje reálnou možnost vzniku lokálních nedostatků v síti (jistota: střední).
- Aktivní sledování a předzásobení dostupnými alternativami ze strany nákupčích lékárenských sítí je reálná možnost pro zmírnění dopadů výpadku (jistota: střední).

## Discussion
- **Fakt:** Na slovenském trhu jsou hlášeny výpadky léků Amoksiklav 625 mg (forma TBL FLM) a Amoksiklav 156,25 mg/5 ml (forma PLU POR) patřících do ATC skupiny J01CR02 [E004, A1] [E005, A2].
- **Fakt:** Za tablety Amoksiklav 625 mg se dodávají MEDOCLAV 625 mg a MEGAMOX 625 forte [E004, A1] [E005, A2].
- **Fakt:** Za perorální suspenzi Amoksiklav 156,25 mg/5 ml se dodávají MEDOCLAV 156,25 mg, MEDOCLAV FORTE 312,5 mg a MEGAMOX DUO [E004, A1] [E005, A2].
- **Fakt:** Dodává se také jiné balení téhož léku Amoksiklav 625 mg a Amoksiklav 156,25 mg/5 ml [E004, A1] [E005, A2].
- **Úsudok:** Pravděpodobné je, že nákupčí lékárenských sítí by měli prioritně zajistit dostupné stejné lékové formy (např. MEDOCLAV a MEGAMOX), přičemž při změně síly nebo přechodu na jiné balení bude nutná opatrnost.
- **Upozornenie:** Záměnu jiné látky nebo lékové formy může provést pouze lékař; zpráva není doporučením pro pacienty.

## Alternative explanations
- Výpadek dodávek může být způsoben krátkodobým logistickým výpadkem u držitele registrace a dodávky se mohou obnovit bez nutnosti dlouhodobého přeučení na náhradní produkty.
- Alternativní léky mohou rovněž zaznamenat zvýšený odbyt, což by mohlo vést k jejich vyčerpání u distributorů v krátkém čase.

## Key assumptions and gaps
- Předpokládáme, že aktuální data z registrů a hlášení SÚKL a ŠÚKL věrně odrážejí reálný stav dostupnosti na trhu.
- Chybějí detailní údaje o fyzických zásobách u jednotlivých distributorů a přesná data ukončení výpadku pro dotčené léky.

## Indicators to watch
- Změny v hlášeních o přerušení a obnovení dodávek léků v registru ŠÚKL pro ATC skupinu J01CR02.
- Dostupnost a objemy dodávek náhradních léků MEDOCLAV a MEGAMOX v distribuční síti.

## Sources and method annex
- [E004, A1] ŠÚKL – register liekov (API)
- [E005, A2] ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok
- Nástroje: `nahrady_za_latku`

## AI use statement
- **Modely:** hlavní gemini-3.5-flash-lite.
- **Agenti (5) a kroky:**
  1. Orchestrátor – kontrola rozsahu otázky a plánování: témata otázky (náhrady) a volání nástrojů (LLM gemini-3.5-flash-lite).
  2. Sběr – nástroje nad pipeline.analytika, bez LLM: nahrady_za_latku.
  3. Analytik – zjištění (fakta a úsudky) z výsledků nástrojů (LLM gemini-3.5-flash-lite).
  4. Reportér – zpráva BLUF, jednou opravená podle kritika (LLM gemini-3.5-flash-lite).
  5. Kritik – kontrola v kódu (sekce, citace podle manifestu, škála PHIA, čísla proti nástrojům, náhrady) a LLM (gemini-3.5-flash-lite); cílená oprava 1 řádků (cizí znaky, LLM gemini-3.5-flash-lite).
- **Kola oprav:** 1 (nejvýše 1).
- **Výsledek kontroly:** schváleno po korektuře řádků v 2. kole (kontrola v kódu i LLM).
- **Překlad:** kritik kontroloval slovenskou verzi; do češtiny ji přeložil LLM (gemini-3.5-flash-lite) a kód ověřil, že citace, čísla, kódy a názvy léčiv se shodují.
- **Volání modelu:** 8 (požadavků na Gemini včetně opakování 8).
- **Lidská kontrola:** zpráva není ověřena (verified: false); ověří ji člověk podle Case Logu [[cases/2026-11-16-cim-nahradit-amoxicilin-s-kyselinou-klavulanovou]].
