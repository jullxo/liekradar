---
typ: sprava-preklad
jazyk: en
povodna: "[[reports/2026-11-16-which-antibiotics-j01-are-at-risk]]"
verified: false
---

# Overview of At-Risk Antibiotics and Recommendations for Pharmacy Chain Buyers in Slovakia

## Bottom line up front
We assess that the emergence of shortages of selected antibiotics (group J01) on the Slovak market is a realistic possibility (confidence: moderate). On the Slovak market, elevated shortage risk within the antibiotic group (J01) is faced primarily by medicinal products with a higher risk score, such as Metronidazol B. Braun 5 mg/ml (score 86), Gentamicin B. Braun 3 mg/ml infúzny roztok (score 83), and Ciprofloxacin Kabi 200 mg/100 ml (score 80) [E001, A2] [E005, A2]. For pharmacy chain buyers, this is a signal to timely check inventory levels, monitor deliveries, and secure available alternatives [E001, A2] [E005, A2].

## Key judgements
- We assess that the link between shortages in the Czech Republic and historical shortages in Slovakia represents a realistic possibility for the Slovak market to experience supply issues regarding the monitored antibiotics (confidence: moderate) [E001, A2] [E005, A2].
- It is likely that pharmacy chain buyers should pay increased attention to pre-stocking alternative packages and monitor supply developments, particularly for preparations with a risk score above 70 (confidence: moderate) [E005, A2].

## Discussion
- **Fakt:** The highest risk score of 86 in the antibiotic group (J01) on the Slovak market is reached by the medicinal product Metronidazol B. Braun 5 mg/ml, while the respective active substance registers a shortage in the Czech Republic, and both the manufacturer and the medicinal product itself experienced shortages in the previous period [E001, A2] [E005, A2].
- **Fakt:** Gentamicin B. Braun 3 mg/ml infúzny roztok reaches a score of 83 based on historical shortages of the medicinal product and the manufacturer in Slovakia [E005, A2].
- **Fakt:** Ciprofloxacin Kabi 200 mg/100 ml (score 80) and Ciprinol (score 68) exhibit risk signals due to the link with ciprofloxacin shortages in the Czech Republic, new shortages of other medicinal products containing this substance in Slovakia, and the manufacturers' history of shortages [E001, A2] [E005, A2].
- **Fakt:** Other medicinal products with an increased risk of shortage in Slovakia are BISEPTOL 100 mg/20 mg (score 70), AXETINE 250 mg (score 70), KLERIMED 250 mg (score 67), MEDOCLAV 400 mg/5 ml + 57 mg/5 ml prášok na perorálnu suspenziu (score 65), Amikacin B.Braun 5 mg/ml (score 64), and Linezolid Sandoz 600 mg filmom obalené tablety (score 63) [E001, A2] [E005, A2].
- **Fakt:** For the aforementioned medicinal products, other packages of the same medicinal product are available, for example for Metronidazol B. Braun 5 mg/ml, Gentamicin B. Braun 3 mg/ml infúzny roztok, Ciprofloxacin Kabi 200 mg/100 ml, BISEPTOL 100 mg/20 mg, AXETINE 250 mg, Ciprinol, KLERIMED 250 mg, MEDOCLAV 400 mg/5 ml + 57 mg/5 ml prášok na perorálnu suspenziu, Amikacin B.Braun 5 mg/ml, and Linezolid Sandoz 600 mg filmom obalené tablety [E005, A2].
- **Úsudok:** We assess that the link between shortages in the Czech Republic and historical shortages in Slovakia increases the risk of supply restrictions for key infusion and oral antibiotics (confidence: moderate) [E001, A2] [E005, A2].
- **Úsudok:** It is likely that the timely identification of alternative packages and active inventory management will mitigate the impact of potential shortages within pharmacy chains (confidence: moderate) [E005, A2].

## Alternative explanations
- The elevated risk score may be the result of statistical models and past shortages that may not necessarily translate into an actual shortage of medicinal products on the market during the current period.
- Manufacturers may compensate for current shortages or supply restrictions in the neighboring Czech Republic by shifting supplies to the Slovak market, which will mitigate the risk of shortages.

## Key assumptions and gaps
- The availability of actual inventory levels at distributors and in individual pharmacies is not directly captured in the provided data.
- Direct and current statements from marketing authorization holders regarding the exact duration of expected supply restrictions on the Slovak market are missing.

## Indicators to watch
- Reports on the interruption and resumption of medicinal product supplies by ŠÚKL for the J01 group.
- Trends in shortage reports for the same active substances in the SÚKL register in the Czech Republic.
- Changes in risk scores and supply reports from key manufacturers (B. Braun, Fresenius Kabi, Medochemie, Sandoz, Krka, Adamed Pharma).

## Sources and method annex
- SÚKL – hlásenia o uvedení, prerušení, ukončení a obnovení dodávok [E001, A2]
- ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok [E005, A2]
- Nástroj: `top_rizikove`

## AI use statement
- **Models:** main gemini-3.5-flash-lite.
- **Agents (5) and steps:**
  1. Orchestrator – question scope check and planning: topics of the question (shortage risk) and tool calls (LLM gemini-3.5-flash-lite).
  2. Collection – tools on top of pipeline.analytika, no LLM: top_rizikove.
  3. Analyst – findings (facts and inferences) from the tool results (LLM gemini-3.5-flash-lite).
  4. Reporter – BLUF report, revised once after the critic's review (LLM gemini-3.5-flash-lite).
  5. Critic – checks in code (sections, citations against the source manifest, PHIA scale, numbers against the tools, substitutes) and LLM (gemini-3.5-flash-lite).
- **Revision rounds:** 1 (at most 1).
- **Review result:** approved in round 2 (checks in code and LLM).
- **Translation:** the critic reviewed the Slovak version; it was translated into English by an LLM (gemini-3.5-flash-lite) and the code verified that citations, numbers, codes and drug names match.
- **Model calls:** 7 (requests to Gemini including retries 7).
- **Human review:** the report is not verified (verified: false); a person will check it against the Case Log [[cases/2026-11-16-which-antibiotics-j01-are-at-risk]].
