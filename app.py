"""LiekRadar – Streamlit aplikácia.

Spustenie lokálne (z priečinka liekradar):
    streamlit run app.py

Čísla počítajú funkcie z pipeline/analytika.py nad dátami v data/processed.
Časť „Opýtajte sa AI“ volá multiagentný systém z agents/graph.py (funkcia spusti).
Texty rozhrania sú v slovenčine, češtine a angličtine (slovník TEXTY nižšie).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="LiekRadar", page_icon="💊", layout="wide")

DATA = Path("data/processed")
METODIKA = Path("vault/metodika")
MANIFEST = Path("vault/manifest_zdrojov.csv")
MODRA, SVETLA = "#24578f", "#8fb3dc"
JAZYKY = {"sk": "SK", "cs": "CZ", "en": "EN"}


# ---------------------------------------------------------------------------
# Texty v troch jazykoch (slovenčina, čeština, angličtina)
# ---------------------------------------------------------------------------

TEXTY = {
    # hlavička a bočný panel
    "brand_sub": ("Radar výpadkov liekov v Česku a na Slovensku", "Radar výpadků léků v Česku a na Slovensku",
                  "Drug shortage radar for Czechia and Slovakia"),
    "hero_sub": ("Dozviete sa o výpadkoch liekov skôr, než začnú chýbať v lekárňach.",
                 "Dozvíte se o výpadcích léků dřív, než začnou chybět v lékárnách.",
                 "Know about drug shortages before they reach pharmacy shelves."),
    "hero_sub2": ("Včasné varovanie, náhrady a príležitosti na trhu v Česku a na Slovensku – z oficiálnych údajov SÚKL a ŠÚKL.",
                  "Včasné varování, náhrady a příležitosti na trhu v Česku a na Slovensku – z oficiálních dat SÚKL a ŠÚKL.",
                  "Early warning, substitutes and market opportunities in Czechia and Slovakia – built on official SÚKL and ŠÚKL data."),
    "pohlad": ("Som", "Jsem", "I am"),
    "p_lekaren": ("Lekáreň / lekárenská sieť", "Lékárna / lékárenský řetězec", "Pharmacy / pharmacy chain"),
    "p_vyrobca": ("Výrobca / distribútor", "Výrobce / distributor", "Manufacturer / distributor"),
    "datum": ("Údaje SÚKL a ŠÚKL k {d}", "Data SÚKL a ŠÚKL k {d}", "SÚKL and ŠÚKL data as of {d}"),
    "zdroje_info": ("Pri každom čísle je uvedený zdroj, napr. [E001, A2]. Vysvetlenie nájdete v časti Zdroje a presnosť.",
                    "U každého čísla je uveden zdroj, např. [E001, A2]. Vysvětlení najdete v části Zdroje a přesnost.",
                    "Every figure cites its source, e.g. [E001, A2]. See Data & accuracy for details."),
    "chyba_dat": ("Chýbajú údaje v `data/processed`. Spustite najprv `python -m pipeline.run_pipeline`.",
                  "Chybí data v `data/processed`. Spusťte nejdřív `python -m pipeline.run_pipeline`.",
                  "Data in `data/processed` is missing. Run `python -m pipeline.run_pipeline` first."),
    # karty s číslami
    "k_cz": ("liekov v Česku práve chýba", "léků v Česku právě chybí", "products currently unavailable in Czechia"),
    "k_sk": ("liekov na Slovensku práve chýba", "léků na Slovensku právě chybí", "products currently unavailable in Slovakia"),
    "k_rok": ("nových výpadkov za posledný rok", "nových výpadků za poslední rok", "new shortages in the past year"),
    "k_latky": ("účinných látok sledujeme v oboch krajinách", "účinných látek sledujeme v obou zemích",
                "active substances tracked in both countries"),
    "k_presnost": ("varovaní v Česku sa v minulosti naplnilo", "varování v Česku se v minulosti naplnilo",
                   "of warnings in Czechia came true (backtest)"),
    # navigácia
    "nav_rizika": ("Hroziace výpadky", "Hrozící výpadky", "Shortage risk"),
    "nav_latka": ("Látka a náhrady", "Látka a náhrady", "Substance & substitutes"),
    "nav_trh": ("Trh a konkurencia", "Trh a konkurence", "Market & competitors"),
    "nav_ai": ("Opýtajte sa AI", "Zeptejte se AI", "Ask the AI"),
    "nav_metodika": ("Zdroje a presnosť", "Zdroje a přesnost", "Data & accuracy"),
    # spoločné
    "upozornenie": ("Skóre rizika nie je pravdepodobnosť, ale poradie rizika. LiekRadar neposkytuje lekárske "
                    "odporúčania; zámenu za inú účinnú látku môže urobiť len lekár.",
                    "Skóre rizika není pravděpodobnost, ale pořadí rizika. LiekRadar neposkytuje lékařská "
                    "doporučení; záměnu za jinou účinnou látku může provést pouze lékař.",
                    "The risk score is a ranking, not a probability. LiekRadar does not provide medical advice; "
                    "only a physician can switch a patient to a different active substance."),
    "c_liek": ("Liek", "Lék", "Product"), "c_balenie": ("Balenie", "Balení", "Pack"),
    "c_latka": ("Látka", "Látka", "Substance"), "c_drzitel": ("Držiteľ registrácie", "Držitel registrace", "MA holder"),
    "c_kod": ("Kód", "Kód", "Code"), "c_riziko": ("Riziko", "Riziko", "Risk"), "c_od": ("Od", "Od", "From"),
    "skupina": ("skupina", "skupina", "group"),
    # hroziace výpadky
    "r_kicker": ("Včasné varovanie", "Včasné varování", "Early warning"),
    "r_title": ("Lieky, ktorým hrozí výpadok", "Léky, kterým hrozí výpadek", "Products at risk of a shortage"),
    "r_desc_lekaren": ("Lieky, ktoré sú dnes bežne dostupné, zoradené podľa rizika výpadku v najbližších 8 týždňoch. "
                       "Pri najrizikovejších zvážte včasné objednanie zásob alebo prípravu náhrady.",
                       "Léky, které jsou dnes běžně dostupné, seřazené podle rizika výpadku v příštích 8 týdnech. "
                       "U nejrizikovějších zvažte včasné objednání zásob nebo přípravu náhrady.",
                       "Products available today, ranked by the risk of a shortage within the next 8 weeks. "
                       "For the riskiest ones, consider ordering stock early or lining up a substitute."),
    "r_desc_vyrobca": ("Lieky, ktoré sú dnes na trhu, zoradené podľa rizika výpadku v najbližších 8 týždňoch. "
                       "Keď výpadok hrozí konkurencii, vaša náhrada môže získať podiel na trhu.",
                       "Léky, které jsou dnes na trhu, seřazené podle rizika výpadku v příštích 8 týdnech. "
                       "Když výpadek hrozí konkurenci, vaše náhrada může získat podíl na trhu.",
                       "Products on the market today, ranked by the risk of a shortage within the next 8 weeks. "
                       "When a competitor is at risk, your alternative can gain market share."),
    "r_skupina": ("Skupina liekov", "Skupina léků", "Drug group"),
    "r_vsetky": ("Všetky skupiny", "Všechny skupiny", "All groups"),
    "r_pocet": ("Počet liekov", "Počet léků", "Number of products"),
    "r_ziadne": ("Žiadny liek s varovným signálom.", "Žádný lék s varovným signálem.", "No products with a warning signal."),
    "m_ml": ("Predpoveď: model strojového učenia", "Předpověď: model strojového učení", "Forecast: machine-learning model"),
    "m_lr": ("Predpoveď: štatistický model", "Předpověď: statistický model", "Forecast: statistical model"),
    "m_rules": ("Predpoveď: pravidlá", "Předpověď: pravidla", "Forecast: rule-based"),
    "r_presnost": ("Overené na histórii: z prvej stovky liekov malo výpadok do 8 týždňov {p}.",
                   "Ověřeno na historii: z první stovky léků mělo výpadek do 8 týdnů {p}.",
                   "Backtested: {p} of the top 100 products had a shortage within 8 weeks."),
    "r_preco": ("Prečo práve tieto lieky? ({k})", "Proč právě tyto léky? ({k})", "Why these products? ({k})"),
    # látka a náhrady
    "l_kicker": ("Prehľad látky", "Přehled látky", "Substance overview"),
    "l_title": ("Účinná látka v Česku a na Slovensku", "Účinná látka v Česku a na Slovensku",
                "An active substance in Czechia and Slovakia"),
    "l_desc": ("Vyberte látku a zistite, koľko liekov s ňou chýba, ako dlho výpadky trvajú a čím chýbajúci liek nahradiť.",
               "Vyberte látku a zjistěte, kolik léků s ní chybí, jak dlouho výpadky trvají a čím chybějící lék nahradit.",
               "Pick a substance to see how many products are short, how long shortages last and what to use instead."),
    "l_vyber": ("Účinná látka – napíšte názov alebo ATC kód", "Účinná látka – napište název nebo ATC kód",
                "Active substance – type a name or ATC code"),
    "l_balenia": ("registrovaných balení", "registrovaných balení", "registered packs"),
    "l_od2019": ("výpadkov od roku 2019", "výpadků od roku 2019", "shortages since 2019"),
    "l_rok": ("za posledný rok", "za poslední rok", "in the past year"),
    "l_teraz": ("práve chýba", "právě chybí", "unavailable now"),
    "l_trva": ("Výpadok zvyčajne trvá {d} dní.", "Výpadek obvykle trvá {d} dní.", "A shortage typically lasts {d} days."),
    "l_dodavky": ("Do lekární sa za obdobie {o} dodalo {n} balení ({z} oproti predchádzajúcim 3 mesiacom).",
                  "Do lékáren bylo za období {o} dodáno {n} balení ({z} oproti předchozím 3 měsícům).",
                  "{n} packs were delivered to pharmacies in {o} ({z} vs. the previous 3 months)."),
    "g_kicker": ("Vývoj", "Vývoj", "Trend"),
    "g_title": ("Kedy sa výpadky začínali", "Kdy výpadky začínaly", "When shortages started"),
    "g_x": ("Štvrťrok", "Čtvrtletí", "Quarter"), "g_krajina": ("Krajina", "Země", "Country"),
    "g_y": ("Počet výpadkov", "Počet výpadků", "Shortages"),
    "s_kicker": ("Česko a Slovensko", "Česko a Slovensko", "Czechia and Slovakia"),
    "s_title": ("Prichádzajú výpadky v oboch krajinách naraz?", "Přicházejí výpadky v obou zemích současně?",
                "Do shortages hit both countries at once?"),
    "s_text": ("Vlny výpadkov tejto látky: v Česku {cz}, na Slovensku {sk}. V oboch krajinách do týždňa: {s}×. "
               "Česko o 1–8 týždňov skôr: {c}×. Slovensko o 1–8 týždňov skôr: {k}×.",
               "Vlny výpadků této látky: v Česku {cz}, na Slovensku {sk}. V obou zemích do týdne: {s}×. "
               "Česko o 1–8 týdnů dříve: {c}×. Slovensko o 1–8 týdnů dříve: {k}×.",
               "Shortage waves for this substance: Czechia {cz}, Slovakia {sk}. Both countries within a week: {s}×. "
               "Czechia 1–8 weeks earlier: {c}×. Slovakia 1–8 weeks earlier: {k}×."),
    "s_lift": (" V celej skupine liekov prichádzajú výpadky naraz {l}× častejšie, než by zodpovedalo náhode.",
               " V celé skupině léků přicházejí výpadky současně {l}× častěji, než by odpovídalo náhodě.",
               " Across the whole drug group, simultaneous shortages are {l}× more frequent than chance."),
    "n_kicker": ("Náhrady", "Náhrady", "Substitutes"),
    "n_title": ("Čo práve chýba a čím to nahradiť", "Co právě chybí a čím to nahradit", "What is missing and what to use instead"),
    "n_ohlasene": ("Ohlásené budúce výpadky", "Ohlášené budoucí výpadky", "Announced upcoming shortages"),
    "n_nic": ("Žiadny liek s touto látkou momentálne nechýba.", "Žádný lék s touto látkou momentálně nechybí.",
              "No product with this substance is currently unavailable."),
    "n_vyber": ("Liek, ktorý chýba", "Lék, který chybí", "Unavailable product"),
    "n_chyba_od": ("chýba od", "chybí od", "unavailable since"),
    "n_ziadna": ("Náhradu s rovnakou látkou ani v rovnakej skupine sme nenašli.",
                 "Náhradu se stejnou látkou ani ve stejné skupině jsme nenašli.",
                 "No substitute with the same substance or in the same group was found."),
    "n_ina": ("Liek s rovnakou látkou nie je dostupný. Ponúkame lieky z rovnakej skupiny – o zámene musí rozhodnúť lekár.",
              "Lék se stejnou látkou není dostupný. Nabízíme léky ze stejné skupiny – o záměně musí rozhodnout lékař.",
              "No product with the same substance is available. Showing products from the same group – "
              "a physician must decide on the switch."),
    "c_odporucil": ("Odporučil úrad", "Doporučil úřad", "Regulator recommended"),
    "c_sila": ("Rovnaká sila", "Stejná síla", "Same strength"),
    "c_dalsie": ("Ďalšie balenia", "Další balení", "Other pack sizes"),
    "c_dodane": ("Dodané za 3 mesiace", "Dodáno za 3 měsíce", "Delivered (3 months)"),
    # trh
    "t_kicker": ("Trh", "Trh", "Market"),
    "t_title": ("Príležitosti a konkurencia", "Příležitosti a konkurence", "Opportunities and competitors"),
    "t_desc": ("Kde na trhu chýba dodávateľ a ako spoľahlivo dodávajú jednotliví výrobcovia.",
               "Kde na trhu chybí dodavatel a jak spolehlivě dodávají jednotliví výrobci.",
               "Where the market lacks a supplier and how reliably each manufacturer delivers."),
    "t_krajina": ("Krajina", "Země", "Country"),
    "t_prefix": ("ATC kód skupiny liekov (napr. J01 alebo J01CR)",
                 "ATC kód skupiny léků (např. J01 nebo J01CR)",
                 "ATC code of the drug group (e.g. J01 or J01CR)"),
    "g2_kicker": ("Príležitosti", "Příležitosti", "Opportunities"),
    "g2_title": ("Kde na trhu chýba dodávateľ", "Kde na trhu chybí dodavatel", "Where the market lacks a supplier"),
    "g2_desc": ("Látky, ktoré chýbajú aspoň 8 týždňov a dodávajú ich najviac dvaja ďalší výrobcovia. "
                "Pre výrobcu príležitosť, pre lekáreň riziko. Prehľad za celý trh, všetky skupiny liekov.",
                "Látky, které chybí alespoň 8 týdnů a dodávají je nejvýše dva další výrobci. "
                "Pro výrobce příležitost, pro lékárnu riziko. Přehled za celý trh, všechny skupiny léků.",
                "Substances short for at least 8 weeks with no more than two other suppliers. "
                "An opportunity for manufacturers, a risk for pharmacies. Whole market, all drug groups."),
    "g2_nic": ("Momentálne nie sú žiadne také látky.", "Momentálně nejsou žádné takové látky.", "No such substances right now."),
    "c_chybajuce": ("Chýbajúce balenia", "Chybějící balení", "Packs unavailable"),
    "c_najdlhsi": ("Najdlhší výpadok (dni)", "Nejdelší výpadek (dny)", "Longest shortage (days)"),
    "c_typicka": ("Typická dĺžka (dni)", "Typická délka (dny)", "Typical length (days)"),
    "c_dodavatelia": ("Ďalší dodávatelia", "Další dodavatelé", "Other suppliers"),
    "c_trh": ("Trh (balení mesačne)", "Trh (balení měsíčně)", "Market (packs/month)"),
    "k2_kicker": ("Konkurencia", "Konkurence", "Competitors"),
    "k2_title": ("Výrobcovia v skupine liekov", "Výrobci ve skupině léků", "Manufacturers in a drug group"),
    "k2_vysledky": ("Výsledky pre ATC kód **{p}**", "Výsledky pro ATC kód **{p}**", "Results for ATC code **{p}**"),
    "k2_desc": ("Ako spoľahlivo dodávajú a kto získava podiel na trhu, keď ostatným chýba tovar.",
                "Jak spolehlivě dodávají a kdo získává podíl na trhu, když ostatním chybí zboží.",
                "How reliably they deliver and who gains share when others run short."),
    "k2_kratky": ("Zadajte aspoň 3 znaky ATC kódu.", "Zadejte alespoň 3 znaky ATC kódu.", "Enter at least 3 characters of an ATC code."),
    "k2_nic": ("V tejto skupine nie sú registrované lieky.", "V této skupině nejsou registrované léky.",
               "No registered products in this group."),
    "c_vyrobca": ("Výrobca (skupina)", "Výrobce (skupina)", "Manufacturer (group)"),
    "c_balenia": ("Balenia", "Balení", "Packs"),
    "c_vyp2019": ("Výpadky od 2019", "Výpadky od 2019", "Shortages since 2019"),
    "c_vyprok": ("Za posledný rok", "Za poslední rok", "Past year"),
    "c_teraz": ("Práve chýba", "Právě chybí", "Unavailable now"),
    "c_podiel": ("Podiel na dodávkach", "Podíl na dodávkách", "Delivery share"),
    "c_zmena": ("Zmena podielu, keď chýba konkurencia (p. b.)", "Změna podílu, když chybí konkurence (p. b.)",
                "Share change when rivals are short (pp)"),
    "c_kolko": ("Počet takých výpadkov", "Počet takových výpadků", "Rival shortages observed"),
    "k2_pozn": ("Firmy sú zoskupené podľa skupiny, napr. Sandoz ČR a Sandoz SI ako jeden výrobca.",
                "Firmy jsou seskupené podle skupiny, např. Sandoz ČR a Sandoz SI jako jeden výrobce.",
                "Companies are grouped, e.g. Sandoz CZ and Sandoz SI count as one manufacturer."),
    # AI
    "a_kicker": ("AI analytik", "AI analytik", "AI analyst"),
    "a_title": ("Opýtajte sa LiekRadaru", "Zeptejte se LiekRadaru", "Ask LiekRadar"),
    "a_desc": ("Napíšte otázku vlastnými slovami. Tím AI agentov vyhľadá údaje, vyhodnotí ich, napíše stručnú správu "
               "so zdrojmi a nezávislý kontrolór overí každé číslo.",
               "Napište dotaz vlastními slovy. Tým AI agentů vyhledá data, vyhodnotí je, napíše stručnou zprávu "
               "se zdroji a nezávislý kontrolor ověří každé číslo.",
               "Ask in your own words. A team of AI agents gathers the data, analyses it, writes a short sourced "
               "report, and an independent reviewer checks every figure."),
    "a_nedostupne": ("AI analytik sa pripravuje. Ostatné časti počítajú tie isté údaje, z ktorých bude vychádzať.",
                     "AI analytik se připravuje. Ostatní části počítají stejná data, ze kterých bude vycházet.",
                     "The AI analyst is being prepared. The other sections show the same data it will use."),
    "a_kluc": ("AI analytik nie je pripojený: chýba API kľúč (GEMINI_API_KEY v súbore .streamlit/secrets.toml).",
               "AI analytik není připojen: chybí API klíč (GEMINI_API_KEY v souboru .streamlit/secrets.toml).",
               "The AI analyst is not connected: the API key is missing (GEMINI_API_KEY in .streamlit/secrets.toml)."),
    "a_otazka": ("Vaša otázka", "Váš dotaz", "Your question"),
    "a_placeholder": ("Napr. Ktoré lieky na tlak môžu v Česku chýbať tento mesiac?",
                      "Např. Které léky na tlak mohou v Česku chybět tento měsíc?",
                      "E.g. Which blood pressure drugs may run short in Czechia this month?"),
    "a_prazdna": ("Najprv napíšte otázku alebo vyberte jeden z príkladov.",
                  "Nejdřív napište dotaz nebo vyberte jeden z příkladů.", "Type a question first or pick one of the examples."),
    "a_skuste": ("Alebo vyberte príklad", "Nebo vyberte příklad", "Or pick an example"),
    "a_pdf": ("Stiahnuť správu (PDF)", "Stáhnout zprávu (PDF)", "Download report (PDF)"),
    "a_pdf_pata": ("LiekRadar · Správu pripravil jazykový model z údajov SÚKL a ŠÚKL; pred dôležitým rozhodnutím ju overte. "
                   "Neposkytuje lekárske odporúčania, zámenu inej účinnej látky môže urobiť len lekár.",
                   "LiekRadar · Zprávu připravil jazykový model z dat SÚKL a ŠÚKL; před důležitým rozhodnutím ji ověřte. "
                   "Neposkytuje lékařská doporučení, záměnu jiné účinné látky může provést pouze lékař.",
                   "LiekRadar · Written by a language model from SÚKL and ŠÚKL data; verify before important decisions. "
                   "Not medical advice; only a physician can switch to a different active substance."),
    "a_strana": ("Strana", "Strana", "Page"),
    "a_spustit": ("Spustiť analýzu", "Spustit analýzu", "Run analysis"),
    "a_bezi": ("AI agenti pracujú…", "AI agenti pracují…", "AI agents at work…"),
    "a_hotovo": ("Analýza je hotová", "Analýza je hotová", "Analysis complete"),
    "a_zlyhalo": ("Analýza sa nepodarila", "Analýza se nepodařila", "Analysis failed"),
    "a_ok": ("Automatická kontrola faktov: všetky čísla v odpovedi sme overili v zdrojových údajoch.",
             "Automatická kontrola faktů: všechna čísla v odpovědi jsme ověřili ve zdrojových datech.",
             "Automatic fact-check: every figure in this answer was verified against the source data."),
    "a_nok": ("Automatická kontrola faktov našla v odpovedi nezrovnalosti ({n}). Pred rozhodnutím si čísla overte.",
              "Automatická kontrola faktů našla v odpovědi nesrovnalosti ({n}). Před rozhodnutím si čísla ověřte.",
              "The automatic fact-check found {n} issue(s) in this answer. Verify the figures before deciding."),
    "a_nok_detail": ("Čo kontrola našla", "Co kontrola našla", "What the check found"),
    "a_odpoved": ("Stručná odpoveď", "Stručná odpověď", "Short answer"),
    "a_zistenia": ("Hlavné zistenia", "Hlavní zjištění", "Key findings"),
    "a_podklady": ("Podklady a čísla", "Podklady a čísla", "Evidence and figures"),
    "a_sledovat": ("Čo sledovať ďalej", "Co sledovat dál", "What to watch next"),
    "a_alternativy": ("Iné možné vysvetlenia", "Jiná možná vysvětlení", "Other possible explanations"),
    "a_predpoklady": ("Predpoklady a čo nevieme", "Předpoklady a co nevíme", "Assumptions and gaps"),
    "a_zdroje": ("Zdroje", "Zdroje", "Sources"),
    "a_vznik": ("Ako táto odpoveď vznikla", "Jak tato odpověď vznikla", "How this answer was made"),
    "a_fakt": ("Fakt:", "Fakt:", "Fact:"),
    "a_odhad": ("Náš odhad:", "Náš odhad:", "Our assessment:"),
    "a_upozornenie": ("Upozornenie:", "Upozornění:", "Important:"),
    "a_chyba": ("AI analytik narazil na problém: {e}", "AI analytik narazil na problém: {e}", "The AI analyst ran into a problem: {e}"),
    "a_model": ("Jazykový model: {m} · volaní modelu: {n}", "Jazykový model: {m} · volání modelu: {n}",
                "Language model: {m} · model calls: {n}"),
    "a_jazyk": ("", "", ""),
    "a_overte": ("Správu pripravil jazykový model z údajov LiekRadaru. Pred dôležitým rozhodnutím ju overte.",
                 "Zprávu připravil jazykový model z dat LiekRadaru. Před důležitým rozhodnutím ji ověřte.",
                 "This report was written by a language model from LiekRadar data. Verify it before important decisions."),
    # metodika
    "d_kicker": ("Dôvera", "Důvěra", "Trust"),
    "d_title": ("Odkiaľ sú údaje a ako presné sú predpovede", "Odkud jsou data a jak přesné jsou předpovědi",
                "Where the data comes from and how accurate the forecasts are"),
    "d_zdroje": ("Zdroje údajov", "Zdroje dat", "Data sources"),
    "d_zdroje_desc": ("Oficiálne otvorené údaje liekových úradov. Spoľahlivosť je hodnotená Admiralty kódom: "
                      "písmeno hodnotí zdroj (A = úplne spoľahlivý), číslo informáciu (1 = potvrdená, 2 = pravdepodobne pravdivá).",
                      "Oficiální otevřená data lékových úřadů. Spolehlivost je hodnocena Admiralty kódem: "
                      "písmeno hodnotí zdroj (A = zcela spolehlivý), číslo informaci (1 = potvrzená, 2 = pravděpodobně pravdivá).",
                      "Official open data from the medicines agencies. Reliability uses the Admiralty code: the letter "
                      "rates the source (A = completely reliable), the number the information (1 = confirmed, 2 = probably true)."),
    "d_nic": ("Prehľad zdrojov nie je k dispozícii.", "Přehled zdrojů není k dispozici.", "Source overview is not available."),
    "d_jazyk": ("", "Technická dokumentace je ve slovenštině.", "Technical documentation is available in Slovak."),
    "c_id": ("ID", "ID", "ID"), "c_zdroj": ("Zdroj", "Zdroj", "Source"), "c_hodnotenie": ("Hodnotenie", "Hodnocení", "Rating"),
    "c_stiahnute": ("Stiahnuté (UTC)", "Staženo (UTC)", "Downloaded (UTC)"), "c_url": ("Adresa", "Adresa", "URL"),
    "c_sha": ("Kontrolný súčet SHA-256", "Kontrolní součet SHA-256", "SHA-256 checksum"),
    "doc_model": ("Porovnanie predpovedných modelov", "Porovnání předpovědních modelů", "Forecast model comparison"),
    "doc_test": ("Overenie predpovedí na historických údajoch", "Ověření předpovědí na historických datech",
                 "Backtest of the forecasts on historical data"),
    "doc_pary": ("Kontrola párovania liekov medzi Českom a Slovenskom", "Kontrola párování léků mezi Českem a Slovenskem",
                 "Check of drug matching between Czechia and Slovakia"),
}

KRAJINY = {"sk": {"CZ": "Česko", "SK": "Slovensko"}, "cs": {"CZ": "Česko", "SK": "Slovensko"},
           "en": {"CZ": "Czechia", "SK": "Slovakia"}}
V_KRAJINE = {"sk": {"CZ": "v Česku", "SK": "na Slovensku"}, "cs": {"CZ": "v Česku", "SK": "na Slovensku"},
             "en": {"CZ": "in Czechia", "SK": "in Slovakia"}}

SKUPINY_CS = {"A": "Trávicí trakt a metabolismus", "B": "Krev a krvetvorné orgány", "C": "Kardiovaskulární systém",
              "D": "Dermatologika", "G": "Urogenitální systém a pohlavní hormony", "H": "Systémové hormonální přípravky",
              "J": "Antiinfektiva pro systémovou aplikaci", "L": "Cytostatika a imunomodulátory",
              "M": "Muskuloskeletální systém", "N": "Nervový systém", "P": "Antiparazitika", "R": "Respirační systém",
              "S": "Smyslové orgány", "V": "Různé"}
SKUPINY_EN = {"A": "Alimentary tract and metabolism", "B": "Blood and blood-forming organs", "C": "Cardiovascular system",
              "D": "Dermatologicals", "G": "Genito-urinary system and sex hormones", "H": "Systemic hormonal preparations",
              "J": "Anti-infectives for systemic use", "L": "Antineoplastic and immunomodulating agents",
              "M": "Musculo-skeletal system", "N": "Nervous system", "P": "Antiparasitic products", "R": "Respiratory system",
              "S": "Sensory organs", "V": "Various"}

# Dôvody rizika prichádzajú z pipeline/analytika.py po slovensky; tu ich preložíme a zjednodušíme.
DOVODY = [
    (r"rovnaký výrobca nahlásil výpadok tejto látky v (CZ|SK) za posledných (\d+) dní",
     ("rovnaký výrobca má výpadok tejto látky {v} (posledných {n} dní)",
      "stejný výrobce má výpadek této látky {v} (posledních {n} dní)",
      "the same manufacturer reported a shortage of this substance {v} (last {n} days)")),
    (r"látka má výpadok v (CZ|SK) za posledných (\d+) dní",
     ("látka má výpadok {v} (posledných {n} dní)", "látka má výpadek {v} (posledních {n} dní)",
      "the substance is short {v} (last {n} days)")),
    (r"iné lieky s touto látkou majú v (CZ|SK) nový výpadok",
     ("iné lieky s touto látkou majú {v} nový výpadok", "jiné léky s touto látkou mají {v} nový výpadek",
      "other products with this substance have a new shortage {v}")),
    (r"látku má v (CZ|SK) registrovanú len jeden výrobca",
     ("látku má {v} registrovanú len jeden výrobca", "látku má {v} registrovanou jen jeden výrobce",
      "only one manufacturer holds a licence for this substance {v}")),
    (r"liek mal v posledných 3 rokoch výpadky",
     ("liek mal v posledných 3 rokoch výpadky", "lék měl v posledních 3 letech výpadky",
      "the product had shortages in the past 3 years")),
    (r"výrobca mal za posledný rok veľa výpadkov",
     ("výrobca mal za posledný rok veľa výpadkov", "výrobce měl za poslední rok mnoho výpadků",
      "the manufacturer had many shortages in the past year")),
    (r"dodávky do lekární v poslednom mesiaci klesli oproti predchádzajúcim 3 mesiacom",
     ("dodávky do lekární v poslednom mesiaci klesli", "dodávky do lékáren v posledním měsíci klesly",
      "pharmacy deliveries fell last month")),
    (r"veľká časť dodávok ide do zahraničia",
     ("veľká časť dodávok ide do zahraničia", "velká část dodávek jde do zahraničí", "a large share of supplies is exported")),
    (r"injekčná alebo infúzna forma",
     ("injekčná alebo infúzna forma", "injekční nebo infuzní forma", "injectable or infusion form")),
]


def jazyk() -> str:
    return st.session_state.get("jazyk") or "sk"


def t(kluc: str, **kw) -> str:
    text = TEXTY[kluc][("sk", "cs", "en").index(jazyk())]
    return text.format(**kw) if kw else text


def krajiny() -> dict:
    return KRAJINY[jazyk()]


def preloz_dovod(text: str) -> str:
    """Jeden dôvod (bez citácie) do zvoleného jazyka."""
    for vzor, preklady in DOVODY:
        m = re.fullmatch(vzor, text.strip())
        if m:
            sablona = preklady[("sk", "cs", "en").index(jazyk())]
            skupiny = m.groups()
            return sablona.format(v=V_KRAJINE[jazyk()][skupiny[0]] if skupiny else "",
                                  n=skupiny[1] if len(skupiny) > 1 else "")
    return text


def dovody_html(text: str) -> str:
    casti = []
    for cast in str(text or "").split("; "):
        m = re.match(r"(.*?)\s*((?:\[E\d+, [A-F]\d\]\s*)+)$", cast)
        jadro, citacia = (m.group(1), m.group(2).strip()) if m else (cast, "")
        if jadro:
            casti.append(preloz_dovod(jadro) + (f' <span class="lr-cit">{citacia}</span>' if citacia else ""))
    return " · ".join(casti)


PRIKLADY = {
    "lekaren": {
        "sk": ["Čím nahradiť amoxicilín s kyselinou klavulánovou, ak chýba na Slovensku?",
               "Ktorým antibiotikám v Česku hrozí v najbližších týždňoch výpadok?",
               "Ktoré lieky na srdce a tlak chýbajú teraz v Česku aj na Slovensku?"],
        "cs": ["Čím nahradit amoxicilin s kyselinou klavulanovou, když chybí na Slovensku?",
               "Kterým antibiotikům v Česku hrozí v příštích týdnech výpadek?",
               "Které léky na srdce a tlak teď chybí v Česku i na Slovensku?"],
        "en": ["What can replace amoxicillin with clavulanic acid if it is short in Slovakia?",
               "Which antibiotics in Czechia are at risk of a shortage in the coming weeks?",
               "Which heart and blood pressure drugs are short in both Czechia and Slovakia right now?"],
    },
    "vyrobca": {
        "sk": ["Kde v Česku chýba dodávateľ a ktorá látka je príležitosťou pre generikum?",
               "Ktorí výrobcovia antibiotík mali na Slovensku za posledný rok najviac výpadkov?",
               "Kto získal podiel na trhu, keď v Česku chýbali lieky na cukrovku?"],
        "cs": ["Kde v Česku chybí dodavatel a která látka je příležitostí pro generikum?",
               "Kteří výrobci antibiotik měli na Slovensku za poslední rok nejvíc výpadků?",
               "Kdo získal podíl na trhu, když v Česku chyběly léky na cukrovku?"],
        "en": ["Where in Czechia is a supplier missing, and which substance is an opportunity for a generic?",
               "Which antibiotic manufacturers had the most shortages in Slovakia in the past year?",
               "Who gained market share when diabetes drugs were short in Czechia?"],
    },
}

SEKCIE_SPRAVY = {"bottom line up front": "bluf", "key judgements": "zistenia", "key judgments": "zistenia",
                 "discussion": "podklady", "alternative explanations": "alternativy",
                 "key assumptions and gaps": "predpoklady", "indicators to watch": "sledovat",
                 "sources and method annex": "zdroje", "ai use statement": "ai"}


def rozdel_spravu(brief: str) -> tuple[str, dict]:
    """Správu BLUF od agentov rozdelí na nadpis a časti (bluf, zistenia, podklady, …)."""
    nadpis, casti, aktualna = "", {}, "uvod"
    for riadok in brief.splitlines():
        if riadok.startswith("# ") and not nadpis:
            nadpis = riadok[2:].strip()
            continue
        m = re.match(r"^##\s+(.*)", riadok)
        if m:
            aktualna = SEKCIE_SPRAVY.get(m.group(1).strip().lower(), m.group(1).strip())
            continue
        casti.setdefault(aktualna, []).append(riadok)
    return nadpis, {k: "\n".join(v).strip() for k, v in casti.items() if "\n".join(v).strip()}


def ludsky_text(text: str) -> str:
    """Označenia Fakt / Úsudok z kurzu nahradí slovami pre zákazníka."""
    text = re.sub(r"\*\*Úsudok:\*\*|\bÚsudok:", f"**{t('a_odhad')}**", text)
    text = re.sub(r"\*\*Upozornenie:\*\*|\bUpozornenie:", f"**{t('a_upozornenie')}**", text)
    return re.sub(r"\*\*Fakt:\*\*|\bFakt:", f"**{t('a_fakt')}**", text)


def markdown_na_html(text: str) -> str:
    """Tučné a kurzíva z odpovede modelu do HTML (ostatné znaky sa bezpečne escapujú)."""
    import html
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    return "<br>".join(f"<p style='margin:.35rem 0 0'>{odsek}</p>" for odsek in text.split("\n\n"))


def cislo(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{int(x):,}".replace(",", "," if jazyk() == "en" else " ")


def percento(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x * 100:.1f}%" if jazyk() == "en" else f"{x * 100:.1f} %".replace(".", ",")


# ---------------------------------------------------------------------------
# Štýl
# ---------------------------------------------------------------------------

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1240px;}
h1, h2, h3, h4 {color: #24578f !important;}
.lr-hero {position: relative; overflow: hidden; border: 1px solid #dce8f4; border-radius: 22px;
          padding: 26px 36px; margin-bottom: 16px; background: #ffffff;}
.lr-hero::before {content: ""; position: absolute; width: 340px; height: 340px; border-radius: 50%;
                  background: #dce8f4; right: -90px; top: -150px;}
.lr-hero::after {content: ""; position: absolute; width: 150px; height: 150px; border-radius: 50%;
                 background: #dce8f4; right: 230px; bottom: -110px; opacity: .7;}
.lr-hero > * {position: relative; z-index: 1;}
.lr-title {font-size: 2.6rem; font-weight: 700; color: #24578f; line-height: 1.1; margin: 0 0 .35rem;}
.lr-sub {font-size: 1.15rem; font-weight: 600; color: #24578f; margin: 0;}
.lr-sub2 {font-size: .98rem; font-style: italic; color: #24578f; margin: .3rem 0 0; max-width: 760px;}
.lr-kicker {font-size: .76rem; letter-spacing: .12em; text-transform: uppercase; color: #24578f;
            font-weight: 600; margin-bottom: .2rem;}
.lr-cards {display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: 4px 0 18px;}
.lr-card {background: #f3f6fa; border: 1px solid #dce8f4; border-radius: 16px; padding: 16px 18px;}
.lr-card .v {font-size: 1.9rem; font-weight: 700; color: #24578f; line-height: 1.1;}
.lr-card .l {font-size: .8rem; color: #4a5b72; margin-top: 4px;}
.lr-sec {margin: .8rem 0 .6rem;}
.lr-sec h3 {margin: 0 0 .2rem; font-size: 1.45rem;}
.lr-sec p {color: #4a5b72; font-size: .92rem; margin: 0; max-width: 900px;}
.lr-sec.maly {margin-top: 1.6rem;}
.lr-sec.maly h3 {font-size: 1.12rem;}
.lr-mini {display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 6px;}
.lr-mini > div {background: #f3f6fa; border: 1px solid #dce8f4; border-radius: 12px; padding: 12px 14px;}
.lr-mini .v {font-size: 1.5rem; font-weight: 700; color: #24578f; line-height: 1.15;}
.lr-mini .l {font-size: .76rem; color: #4a5b72;}
.lr-pill {display: inline-block; background: #24578f; color: #fff; font-size: .72rem; font-weight: 700;
          border-radius: 999px; padding: 2px 10px; margin-right: 8px; vertical-align: middle;}
.lr-country {font-size: 1.15rem; font-weight: 700; color: #24578f; margin: 1.1rem 0 .4rem;}
.lr-note {font-size: .8rem; color: #6b7a90; border-top: 1px solid #dce8f4; padding-top: .6rem; margin-top: 1.2rem;}
.lr-cit {font-size: .75rem; color: #8a97aa;}
.lr-dovod {font-size: .88rem; margin: 0 0 .45rem;}
.lr-odpoved {font-size: 1rem; line-height: 1.55; margin-bottom: 12px;}
.lr-box {background: #f3f6fa; border: 1px solid #dce8f4; border-left: 4px solid #24578f; border-radius: 10px;
         padding: 12px 16px; font-size: .92rem;}
[data-testid="stSidebar"] .lr-brand {font-size: 1.7rem; font-weight: 700; color: #fff; margin-bottom: 0;}
[data-testid="stSidebar"] .lr-brand-sub {font-style: italic; color: #dce8f4; font-size: .9rem;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color: #dce8f4;}
</style>
""", unsafe_allow_html=True)


def sekcia(stitok: str, nadpis: str, popis: str = "", maly: bool = False) -> None:
    trieda = "lr-sec maly" if maly else "lr-sec"
    st.markdown(f'<div class="{trieda}">{f"<div class=lr-kicker>{stitok}</div>" if stitok else ""}<h3>{nadpis}</h3>'
                f'{f"<p>{popis}</p>" if popis else ""}</div>', unsafe_allow_html=True)


def karticky(polozky: list) -> None:
    obsah = "".join(f'<div><div class="v">{v}</div><div class="l">{l}</div></div>' for v, l in polozky)
    st.markdown(f'<div class="lr-mini">{obsah}</div>', unsafe_allow_html=True)


def krajina_nadpis(krajina: str) -> None:
    st.markdown(f'<div class="lr-country"><span class="lr-pill">{krajina}</span>{krajiny()[krajina]}</div>',
                unsafe_allow_html=True)


def poznamka(text: str) -> None:
    st.markdown(f'<div class="lr-note">{text}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Bočný panel (jazyk musí byť známy skôr, než sa vypíše čokoľvek iné)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.segmented_control("Jazyk / Language", list(JAZYKY), format_func=JAZYKY.get, default="sk",
                         key="jazyk", label_visibility="collapsed")
    st.markdown(f'<div class="lr-brand">LiekRadar</div><div class="lr-brand-sub">{t("brand_sub")}</div>',
                unsafe_allow_html=True)
    st.write("")
    # Popisky sa menia s jazykom, preto má každý jazyk vlastný prepínač a výber si pamätáme zvlášť.
    st.session_state.setdefault("persona", "lekaren")
    st.session_state[f"persona_{jazyk()}"] = st.session_state["persona"]
    persona = st.radio(t("pohlad"), ["lekaren", "vyrobca"], format_func=lambda p: t(f"p_{p}"), key=f"persona_{jazyk()}",
                       on_change=lambda: st.session_state.update(persona=st.session_state[f"persona_{jazyk()}"]))
    st.divider()
    datum_miesto = st.empty()
    st.caption(t("zdroje_info"))

if not (DATA / "lieky.parquet").exists():
    st.error(t("chyba_dat"))
    st.stop()

from pipeline import analytika as an  # noqa: E402  (až po kontrole dát)
from pipeline.kiq2_posun import ATC_SKUPINY  # noqa: E402


def skupiny_atc() -> dict:
    return {"sk": ATC_SKUPINY, "cs": SKUPINY_CS, "en": SKUPINY_EN}[jazyk()]


# ---------------------------------------------------------------------------
# Výpočty (pamätajú sa hodinu, aby appka bola rýchla)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def rizikove(krajina: str, prefix: str | None, n: int) -> pd.DataFrame:
    return an.top_rizikove(krajina, prefix, n)


@st.cache_data(ttl=3600, show_spinner=False)
def detail(atc: str) -> dict:
    return an.detail_latky(atc)


@st.cache_data(ttl=3600, show_spinner=False)
def posun(atc: str) -> dict:
    return an.posun_latky(atc)


@st.cache_data(ttl=3600, show_spinner=False)
def nahrady(krajina: str, kod: str) -> pd.DataFrame:
    return an.nahrady(krajina, kod)


@st.cache_data(ttl=3600, show_spinner=False)
def konkurenti(prefix: str, krajina: str) -> pd.DataFrame:
    return an.konkurenti(prefix, krajina)


@st.cache_data(ttl=3600, show_spinner=False)
def medzery(krajina: str, n: int) -> pd.DataFrame:
    return an.trhove_medzery(krajina, n)


@st.cache_data(ttl=3600, show_spinner=False)
def zoznam_latok() -> dict:
    """ATC7 -> popis do výberu; najprv látky s najviac výpadkami."""
    ep = an._tab("epizody")
    pocty = ep[ep["zaciatok"] >= an.SPOLOCNE_OD].groupby("atc").size()
    atc = an._tab("lieky")["atc"].dropna()
    atc = sorted(set(atc[atc.str.len() == 7]), key=lambda a: (-pocty.get(a, 0), a))
    return {a: f"{a} – {an.nazov_atc(a) or '?'}" for a in atc}


@st.cache_data(ttl=3600, show_spinner=False)
def vypadky_stvrtrocne(atc: str) -> pd.DataFrame:
    """Počet začiatkov výpadkov po štvrťrokoch: stĺpce stvrtrok, krajina (CZ/SK), pocet."""
    ep = an._tab("epizody")
    ep = ep[(ep["atc"] == atc) & (ep["zaciatok"] >= an.SPOLOCNE_OD) & ~ep["planovany"]]
    if ep.empty:
        return pd.DataFrame()
    tab = ep.groupby([ep["zaciatok"].dt.to_period("Q"), "krajina"]).size().unstack(fill_value=0)
    vsetky = pd.period_range(pd.Period(an.SPOLOCNE_OD, "Q"), pd.Period(an._dnes(), "Q"), freq="Q")
    tab = tab.reindex(vsetky, fill_value=0).reindex(columns=["CZ", "SK"], fill_value=0)
    tab.index = [f"{p.year} Q{p.quarter}" for p in tab.index]
    return tab.rename_axis("stvrtrok").reset_index().melt("stvrtrok", var_name="krajina", value_name="pocet")


@st.cache_data(ttl=3600, show_spinner=False)
def modely() -> dict:
    """Pre každú krajinu: typ modelu (ml / lr / rules) a presnosť top 100 zo spätného testu."""
    vysledok = {}
    for krajina in ("CZ", "SK"):
        try:
            from pipeline import kiq1_ml
            balik = kiq1_ml.nacitaj_model(krajina)
            if balik:
                vysledok[krajina] = ("ml", balik["metriky"]["presnost_top"])
                continue
        except Exception:
            pass
        try:
            vysledok[krajina] = ("lr", json.loads(an.VAHY_SUBOR.read_text(encoding="utf-8"))[krajina]["presnost_top"])
        except Exception:
            vysledok[krajina] = ("rules", None)
    return vysledok


@st.cache_data(ttl=3600, show_spinner=False)
def prehlad() -> dict:
    stav = an.stav_liekov()
    ep = an._tab("epizody")
    rok = ep[(ep["zaciatok"] > an._dnes() - pd.Timedelta(days=365)) & ~ep["planovany"]]
    try:
        latky_oboch = len(pd.read_parquet(DATA / "pary_atc.parquet"))
    except Exception:
        latky_oboch = None
    vo_vypadku = stav[stav["stav"] == "vo výpadku"].groupby("krajina").size()
    return {"teraz_cz": int(vo_vypadku.get("CZ", 0)), "teraz_sk": int(vo_vypadku.get("SK", 0)),
            "rok": int(len(rok)), "latky_oboch": latky_oboch}


def datum_dat() -> str:
    try:
        return pd.to_datetime(pd.read_csv(MANIFEST)["stiahnute_utc"]).max().strftime("%d. %m. %Y")
    except Exception:
        return "?"


def pdf_spravy(otazka: str, nadpis: str, casti: dict, schvalene: bool, pocet_problemov: int) -> bytes:
    from pdf_sprava import vytvor_pdf
    casti_ludsky = {k: ludsky_text(v) for k, v in casti.items()}
    nazvy = {"bluf": t("a_odpoved"), "zistenia": t("a_zistenia"), "podklady": t("a_podklady"),
             "sledovat": t("a_sledovat"), "alternativy": t("a_alternativy"), "predpoklady": t("a_predpoklady"),
             "zdroje": t("a_zdroje"), "ai": t("a_vznik")}
    return vytvor_pdf(nadpis, casti_ludsky, otazka=otazka, schvalene=schvalene,
                      kontrola=t("a_ok") if schvalene else t("a_nok", n=pocet_problemov or "?"),
                      nazvy=nazvy, pata=t("a_pdf_pata"), podtitul=t("brand_sub"),
                      popis_otazky=t("a_otazka"), strana=t("a_strana"))


def kratky_nazov_suboru(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", text)[:6]) or "sprava"


def kod_text(df: pd.DataFrame) -> pd.DataFrame:
    """Kódy liekov ako text, aby sa nestratili nuly na začiatku."""
    return df.assign(kod=df["kod"].astype(str)) if "kod" in df else df


def ma_ai_kluc() -> bool:
    if os.environ.get("LIEKRADAR_FAKE_LLM", "").strip() in {"1", "true", "True", "ano"}:
        return True
    try:
        if st.secrets.get("GEMINI_API_KEY"):
            return True
    except Exception:  # secrets.toml vôbec neexistuje
        pass
    return bool(os.environ.get("GEMINI_API_KEY"))


# ---------------------------------------------------------------------------
# Hlavička a čísla
# ---------------------------------------------------------------------------

datum_miesto.caption(t("datum", d=datum_dat()))
st.markdown(f"""
<div class="lr-hero">
  <div class="lr-title">LiekRadar</div>
  <div class="lr-sub">{t("hero_sub")}</div>
  <div class="lr-sub2">{t("hero_sub2")}</div>
</div>
""", unsafe_allow_html=True)

_p, _m = prehlad(), modely()
st.markdown(f"""
<div class="lr-cards">
  <div class="lr-card"><div class="v">{cislo(_p['teraz_cz'])}</div><div class="l">{t("k_cz")}</div></div>
  <div class="lr-card"><div class="v">{cislo(_p['teraz_sk'])}</div><div class="l">{t("k_sk")}</div></div>
  <div class="lr-card"><div class="v">{cislo(_p['rok'])}</div><div class="l">{t("k_rok")}</div></div>
  <div class="lr-card"><div class="v">{cislo(_p['latky_oboch'])}</div><div class="l">{t("k_latky")}</div></div>
  <div class="lr-card"><div class="v">{percento(_m['CZ'][1])}</div><div class="l">{t("k_presnost")}</div></div>
</div>
""", unsafe_allow_html=True)

latky = zoznam_latok()
if "atc" not in st.session_state:
    st.session_state["atc"] = "J01CR02" if "J01CR02" in latky else next(iter(latky))


# ---------------------------------------------------------------------------
# Časti aplikácie
# ---------------------------------------------------------------------------

def cast_rizika() -> None:
    sekcia(t("r_kicker"), t("r_title"), t(f"r_desc_{persona}"))
    c1, c2 = st.columns([3, 1])
    skupiny = {"": t("r_vsetky")} | {k: f"{k} – {v}" for k, v in skupiny_atc().items()}
    skupina = c1.selectbox(t("r_skupina"), list(skupiny), format_func=skupiny.get)
    n = c2.slider(t("r_pocet"), 10, 50, 20, step=10)

    for krajina in ("CZ", "SK"):  # Česko a pod ním Slovensko
        krajina_nadpis(krajina)
        with st.spinner(""):
            tab = rizikove(krajina, skupina or None, n)
        if tab.empty:
            st.info(t("r_ziadne"))
            continue
        typ, presnost = modely()[krajina]
        popis = t(f"m_{typ}") + (" · " + t("r_presnost", p=percento(presnost)) if presnost else "")
        st.caption(popis)
        tab = tab.reset_index(drop=True)
        tab.insert(0, "poradie", range(1, len(tab) + 1))
        st.dataframe(
            kod_text(tab[["poradie", "skore", "nazov", "doplnok", "latka", "drzitel", "kod"]]),
            hide_index=True, width="stretch", height=35 * (len(tab) + 1) + 3,
            column_config={
                "poradie": st.column_config.NumberColumn("#", width="small"),
                "skore": st.column_config.ProgressColumn(t("c_riziko"), min_value=0, max_value=100, format="%d"),
                "nazov": t("c_liek"), "doplnok": t("c_balenie"), "latka": t("c_latka"),
                "drzitel": t("c_drzitel"), "kod": t("c_kod"),
            },
        )
        with st.expander(t("r_preco", k=krajiny()[krajina])):
            for r in tab.itertuples():
                st.markdown(f'<p class="lr-dovod"><b>{r.poradie}. {r.nazov}</b> ({r.skore}): {dovody_html(r.dovody)}</p>',
                            unsafe_allow_html=True)
    poznamka(t("upozornenie"))


def graf_vypadkov(atc: str) -> None:
    data = vypadky_stvrtrocne(atc)
    if data.empty:
        return
    data = data.assign(krajina=data["krajina"].map(krajiny()))
    nazvy = [krajiny()["CZ"], krajiny()["SK"]]
    graf = alt.Chart(data).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("stvrtrok:N", title=t("g_x"), axis=alt.Axis(labelAngle=-45)),
        xOffset=alt.XOffset("krajina:N", sort=nazvy),
        y=alt.Y("pocet:Q", title=t("g_y"), axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("krajina:N", scale=alt.Scale(domain=nazvy, range=[MODRA, SVETLA]),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("stvrtrok:N", title=t("g_x")), alt.Tooltip("krajina:N", title=t("g_krajina")),
                 alt.Tooltip("pocet:Q", title=t("g_y"))],
    ).properties(height=380)
    sekcia(t("g_kicker"), t("g_title"), maly=True)
    st.altair_chart(graf, width="stretch")


def cast_latka() -> None:
    sekcia(t("l_kicker"), t("l_title"), t("l_desc"))
    atc = st.selectbox(t("l_vyber"), list(latky), format_func=lambda a: latky.get(a, a), key="atc")
    d, p = detail(atc), posun(atc)
    st.markdown(f"**{atc} {d['nazov']}** · {t('skupina')} {atc[0]} – {skupiny_atc().get(atc[0], '')}")

    for krajina in ("CZ", "SK"):
        info = d["krajiny"][krajina]
        krajina_nadpis(krajina)
        karticky([(cislo(info["registrovane_balenia"]), t("l_balenia")), (cislo(info["vypadky_od_2019"]), t("l_od2019")),
                  (cislo(info["vypadky_12m"]), t("l_rok")), (cislo(info["pocet_teraz_vo_vypadku"]), t("l_teraz"))])
        riadky = []
        if info["median_dlzky_dni"]:
            riadky.append(t("l_trva", d=f"{info['median_dlzky_dni']:.0f}"))
        if info.get("dodavky"):
            dod, zmena = info["dodavky"], info["dodavky"].get("zmena_oproti_predch_3m")
            riadky.append(t("l_dodavky", o=dod["obdobie"].replace(" až ", "–"), n=cislo(dod["baleni_lekarne_3m"]),
                            z=f"{zmena:+.0%}" if zmena is not None else "—"))
        st.caption(" ".join(riadky) + " " + " ".join(info["zdroje"]))

    graf_vypadkov(atc)

    sekcia(t("s_kicker"), t("s_title"), maly=True)
    text = t("s_text", cz=p["vlny_cz"], sk=p["vlny_sk"], s=p["sucasne_do_7_dni"], c=p["cr_skor_8_60_dni"],
             k=p["sr_skor_8_60_dni"])
    lift = (p.get("skupina_atc") or {}).get("lift_sucasne")
    if lift:
        text += t("s_lift", l=f"{lift:.1f}" if jazyk() == "en" else f"{lift:.1f}".replace(".", ","))
    st.markdown(f'<div class="lr-box">{text}</div>', unsafe_allow_html=True)

    sekcia(t("n_kicker"), t("n_title"), maly=True)
    for krajina in ("CZ", "SK"):  # Česko a pod ním Slovensko
        info = d["krajiny"][krajina]
        krajina_nadpis(krajina)
        if info["ohlasene_vypadky"]:  # žlté upozornenie, každý liek na vlastnom riadku
            riadky = "\n".join(f"- **{o['nazov']}** ({o['kod']}) – {t('c_od').lower()} {o['od']}"
                               for o in info["ohlasene_vypadky"])
            st.warning(f"**{t('n_ohlasene')}**\n\n{riadky}", icon="⚠️")
        if not info["teraz_vo_vypadku"]:
            st.success(t("n_nic"))
            continue
        moznosti = {o["kod"]: f"{o['nazov']} ({o['kod']}) – {t('n_chyba_od')} {o['od']}" for o in info["teraz_vo_vypadku"]}
        kod = st.selectbox(t("n_vyber"), list(moznosti), format_func=lambda k: moznosti.get(k, k),
                           key=f"vypadok_{krajina}_{atc}")
        nah = nahrady(krajina, kod)
        if nah.empty:
            st.error(t("n_ziadna"))
            continue
        if nah["typ"].iloc[0] != "rovnaká látka":
            st.warning(t("n_ina"))
        stlpce = ["nazov", "doplnok", "drzitel", "odporucil_sukl", "rovnaka_sila", "dalsie_balenia"]
        stlpce += ["baleni_lekarne_3m"] if "baleni_lekarne_3m" in nah else []
        st.dataframe(nah[stlpce], hide_index=True, width="stretch", column_config={
            "nazov": t("c_liek"), "doplnok": t("c_balenie"), "drzitel": t("c_drzitel"),
            "odporucil_sukl": st.column_config.CheckboxColumn(t("c_odporucil")),
            "rovnaka_sila": st.column_config.CheckboxColumn(t("c_sila")),
            "dalsie_balenia": t("c_dalsie"), "baleni_lekarne_3m": t("c_dodane"),
        })
        st.caption(nah["zdroj"].iloc[0])
    poznamka(t("upozornenie"))


def cast_trh() -> None:
    sekcia(t("t_kicker"), t("t_title"), t("t_desc"))
    krajina = st.radio(t("t_krajina"), ["CZ", "SK"], format_func=krajiny().get, horizontal=True)
    sekcia(t("g2_kicker"), t("g2_title"), t("g2_desc"), maly=True)
    med = medzery(krajina, 15)
    if med.empty:
        st.info(t("g2_nic"))
    else:
        st.dataframe(med.drop(columns=["zdroj"]), hide_index=True, width="stretch", column_config={
            "atc": "ATC", "nazov": t("c_latka"), "balenia_vo_vypadku": t("c_chybajuce"),
            "najdlhsi_vypadok_dni": t("c_najdlhsi"), "median_vypadku_dni": t("c_typicka"),
            "dodavatelia_dostupni": t("c_dodavatelia"), "trh_baleni_mesacne": t("c_trh"),
        })
        st.caption(med["zdroj"].iloc[0])

    sekcia(t("k2_kicker"), t("k2_title"), t("k2_desc"), maly=True)
    prefix = st.text_input(t("t_prefix"), value=st.session_state["atc"][:5]).strip().upper()
    if len(prefix) < 3:
        st.info(t("k2_kratky"))
        return
    kon = konkurenti(prefix, krajina)
    if kon.empty:
        st.info(t("k2_nic"))
        return
    st.markdown(t("k2_vysledky", p=prefix))
    stlpce = [c for c in ["nazov", "registrovane_balenia", "vypadky_od_2019", "vypadky_12m", "teraz_vo_vypadku",
                          "median_dlzky_dni", "podiel_dodavok_12m", "zmena_podielu_pb", "vypadkov_konkurencie"] if c in kon]
    st.dataframe(kon[stlpce].head(20), hide_index=True, width="stretch", column_config={
        "nazov": t("c_vyrobca"), "registrovane_balenia": t("c_balenia"), "vypadky_od_2019": t("c_vyp2019"),
        "vypadky_12m": t("c_vyprok"), "teraz_vo_vypadku": t("c_teraz"), "median_dlzky_dni": t("c_typicka"),
        "podiel_dodavok_12m": st.column_config.NumberColumn(t("c_podiel"), format="percent"),
        "zmena_podielu_pb": st.column_config.NumberColumn(t("c_zmena"), format="%+.1f"),
        "vypadkov_konkurencie": t("c_kolko"),
    })
    st.caption(kon["zdroj"].iloc[0] + " · " + t("k2_pozn"))


def cast_ai() -> None:
    sekcia(t("a_kicker"), t("a_title"), t("a_desc"))
    try:
        from agents.graph import spusti
    except ImportError:
        spusti = None
    if spusti is None:
        st.info(t("a_nedostupne"))
        return
    if not ma_ai_kluc():
        st.warning(t("a_kluc"))
        return
    if t("a_jazyk"):
        st.caption(t("a_jazyk"))
    kluc_prikladu = f"priklad_{persona}_{jazyk()}"

    def _pouzi_priklad() -> None:
        if st.session_state.get(kluc_prikladu):
            st.session_state["otazka"] = st.session_state[kluc_prikladu]

    otazka = st.text_area(t("a_otazka"), key="otazka", placeholder=t("a_placeholder"), height=90)
    st.pills(t("a_skuste"), PRIKLADY[persona][jazyk()], key=kluc_prikladu, on_change=_pouzi_priklad)
    spustit = st.button(t("a_spustit"), type="primary")
    if spustit and not otazka.strip():
        st.info(t("a_prazdna"))
    elif spustit:
        with st.status(t("a_bezi"), expanded=True) as stav:
            vysledok = spusti(otazka.strip(), persona, pri_kroku=lambda riadok: stav.write(riadok), jazyk=jazyk())
            zlyhalo = bool(vysledok.get("chyba")) and not vysledok.get("brief")
            stav.update(label=t("a_zlyhalo") if zlyhalo else t("a_hotovo"),
                        state="error" if zlyhalo else "complete", expanded=False)
        # výsledok si pamätáme, aby nezmizol po stiahnutí PDF alebo zmene jazyka
        st.session_state["ai_vysledok"] = {"otazka": otazka.strip(), "vysledok": vysledok}
    ulozene = st.session_state.get("ai_vysledok")
    if not ulozene:
        return
    otazka, vysledok = ulozene["otazka"], ulozene["vysledok"]
    if vysledok.get("chyba") and not vysledok.get("brief"):
        st.error(t("a_chyba", e=vysledok["chyba"]))
        return
    brief = vysledok.get("brief", "")
    nadpis, casti = rozdel_spravu(brief)
    if nadpis:
        st.markdown(f"### {nadpis}")
    if casti.get("bluf"):
        st.markdown(f'<div class="lr-box lr-odpoved"><div class="lr-kicker">{t("a_odpoved")}</div>'
                    f'{markdown_na_html(ludsky_text(casti["bluf"]))}</div>', unsafe_allow_html=True)
    kritika = vysledok.get("kritika") or {}
    problemy = list(kritika.get("problemy_kod") or []) + list(kritika.get("problemy_llm") or [])
    if vysledok.get("schvalene"):
        st.success(t("a_ok"), icon="✅")
    else:
        st.warning(t("a_nok", n=len(problemy) or "?"), icon="⚠️")
        if problemy:
            with st.expander(t("a_nok_detail")):
                for problem in problemy:
                    st.markdown(f"- {problem}")
    if casti.get("zistenia"):
        sekcia("", t("a_zistenia"), maly=True)
        st.markdown(ludsky_text(casti["zistenia"]))
    for kluc, nazov in [("podklady", "a_podklady"), ("sledovat", "a_sledovat"), ("alternativy", "a_alternativy"),
                        ("predpoklady", "a_predpoklady"), ("zdroje", "a_zdroje")]:
        if casti.get(kluc):
            with st.expander(t(nazov)):
                st.markdown(ludsky_text(casti[kluc]))
    with st.expander(t("a_vznik")):
        if casti.get("ai"):
            st.markdown(casti["ai"])
        for krok in vysledok.get("priebeh", []):
            st.markdown(f"- {krok}")
        modely_ai = ", ".join(vysledok.get("modely") or []) or vysledok.get("model", "")
        st.caption(t("a_model", m=modely_ai, n=vysledok.get("volania_llm", "?")))
    if brief:
        st.download_button(t("a_pdf"), data=pdf_spravy(otazka, nadpis, casti, bool(vysledok.get("schvalene")), len(problemy)),
                           file_name=f"liekradar-{kratky_nazov_suboru(otazka)}.pdf", mime="application/pdf",
                           type="primary", icon=":material/download:", on_click="ignore")
    poznamka(t("a_overte") + " " + t("upozornenie"))


def cast_metodika() -> None:
    sekcia(t("d_kicker"), t("d_title"))
    sekcia(t("d_zdroje"), t("d_zdroje"), t("d_zdroje_desc"), maly=True)
    try:
        m = pd.read_csv(MANIFEST).sort_values("stiahnute_utc").drop_duplicates("zdroj", keep="last")
        st.dataframe(m[["id", "zdroj", "admiralty", "stiahnute_utc", "url", "sha256"]].sort_values("id"),
                     hide_index=True, width="stretch", column_config={
                         "id": t("c_id"), "zdroj": t("c_zdroj"), "admiralty": t("c_hodnotenie"),
                         "stiahnute_utc": t("c_stiahnute"), "url": st.column_config.LinkColumn(t("c_url")),
                         "sha256": t("c_sha")})
    except Exception:
        st.info(t("d_nic"))
    if t("d_jazyk"):
        st.caption(t("d_jazyk"))
    for subor, kluc in [("KIQ1 model ML.md", "doc_model"), ("KIQ1 spätný test.md", "doc_test"),
                        ("Kontrola párovania.md", "doc_pary")]:
        cesta = METODIKA / subor
        if cesta.exists():
            with st.expander(t(kluc)):
                text = cesta.read_text(encoding="utf-8")
                st.markdown(re.sub(r"\A#[^\n]*\n", "", text))  # bez pôvodného nadpisu


CASTI = {"rizika": cast_rizika, "latka": cast_latka, "trh": cast_trh, "ai": cast_ai, "metodika": cast_metodika}
poradie = ["rizika", "latka", "trh", "ai", "metodika"]
if persona == "vyrobca":  # výrobcu zaujíma najprv trh, lekáreň riziká a náhrady
    poradie = ["trh", "rizika", "latka", "ai", "metodika"]

# Navigácia: počíta sa len otvorená časť, preto sa appka načíta rýchlo
vybrana = st.segmented_control("nav", poradie, format_func=lambda c: t(f"nav_{c}"), default=poradie[0],
                               key=f"nav_{persona}", label_visibility="collapsed", width="stretch")
CASTI[vybrana or poradie[0]]()
