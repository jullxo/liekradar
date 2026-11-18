# Matastav – manažerský report v Power BI

**Předmět:** 4IT526 Datové sklady a reporting (VŠE) · **Tým:** 25
**Soubor:** `Matastav_25_final.pbix` · **Data aktuální k:** 31. 8. 2026

Report pro vedení firmy Matastav (pronájem strojů, nákladních aut a pracovních čet). Ukazuje čtyři problémy, které jsme v datech našli, a podklady pro rozhodnutí o nich:

| # | Problém | Stránka reportu |
|---|---|---|
| 1 | Zhoršující se cash flow: příjmy zaostávají za plánem, zákazníci platí pozdě | Cashflow, Pohledávky |
| 2 | Mzdové náklady překračují plán | Mzdy |
| 3 | Rostoucí nespokojenost zákazníků | Spokojenost |
| 4 | Kategorie zákazníků neodpovídají tržbám | Kategorie |

---

## 1. Jak report otevřít a obnovit

1. Otevřete `Matastav_25_5.pbix` v **Power BI Desktop**.
2. Data se načítají konektorem **Google BigQuery**:
   - projekt `fis4it562-team25`;
   - dataset `gold_matastav`.
3. Při **Domů → Aktualizovat** se přihlaste Google účtem, který má do projektu přístup.
4. Report se otevírá na stránce **Přehled**. Mezi stránkami se přepíná navigací nahoře.

## 2. Zdroj dat a architektura

Datový sklad v BigQuery má tři vrstvy:

| Vrstva | Dataset | Obsah |
|---|---|---|
| Bronze | `bronze_matastav` | Zdrojové tabulky beze změn (t_kontrakty, t_faktury_vydane, t_prijmy_*, t_vydaje_*, t_zakaznici, …) |
| Silver | `silver_matastav` | Vyčištěná data v modelu **snowflake** (např. D_ZAKAZNIK → D_KATEGORIE_ZAKAZNIKA, D_PSC → D_OKRES → D_KRAJ, D_SCENAR) |
| Gold | `gold_matastav` | Model **star** pro reporting – z něj čte Power BI |

Power BI načítá z vrstvy Gold jen tyto tabulky:
- faktové: `F_PENEZNI_TOK`, `F_KONTRAKT`;
- dimenze: `D_DEN`, `D_ZAKAZNIK`, `D_ZAMESTNANEC`, `D_POBOCKA`, `D_ZDROJ`, `D_OPERACE`, `D_VCAS`, `D_ZAPLACENO`.

## 3. Datový model (star schema)

### Faktové tabulky

| Tabulka | 1 řádek = | Hlavní sloupce |
|---|---|---|
| `F_PENEZNI_TOK` | 1 účetní položka: plánovaná (kniha závazků a pohledávek) nebo skutečná platba (peněžní deník) | `castka_plan`, `castka_skutecnost` (příjem kladně, výdaj záporně) |
| `F_KONTRAKT` | 1 kontrakt včetně faktury a hodnocení zákazníka | `cena_celkem`, `cenikova_cena`, `sleva_kc`, `fakturovano`, `dny_po_splatnosti`, `nps` |

Plán a skutečnost jsou ve stejné tabulce a ve stejném zrnu (operace × den × zákazník × zaměstnanec × pobočka × zdroj). Proto je lze přímo porovnat.

### Vztahy

Všechny vztahy jsou typu **M:1** s jednosměrným filtrem.

| Z (fakt) | Na (dimenze) | Aktivní |
|---|---|---|
| F_PENEZNI_TOK[datum_id] | D_DEN[datum_id] | ano |
| F_PENEZNI_TOK[id_oper / zakaznik_sk / id_zam / id_pob / id_zdroje] | D_OPERACE / D_ZAKAZNIK / D_ZAMESTNANEC / D_POBOCKA / D_ZDROJ | ano |
| F_KONTRAKT[datum_od_id] (začátek kontraktu) | D_DEN[datum_id] | ano |
| F_KONTRAKT[zakaznik_sk / id_zam_obchodnik / id_pob / id_zdroje / id_vcas / id_zaplaceno] | D_ZAKAZNIK / D_ZAMESTNANEC / D_POBOCKA / D_ZDROJ / D_VCAS / D_ZAPLACENO | ano |
| F_KONTRAKT[datum_do_id, datum_vystaveni_id, datum_splatnosti_id, datum_zaplaceni_id, datum_hodnoceni_id] | D_DEN[datum_id] | ne – používají se v measures přes `USERELATIONSHIP` |

Poznámky k modelu:
- `D_DEN` je **role-playing** dimenze. Jedna kalendářní tabulka slouží pro všechna data.
- `D_ZAKAZNIK` je **SCD2**: klíč je `zakaznik_sk`, platnost určují `platny_od` a `platny_do`. Aktuální verzi zákazníka označuje `aktualni = TRUE`. Zákazníky proto počítáme measure **Počet aktuálních zákazníků**, ne počtem řádků.
- Neznámé hodnoty mají klíč `-1` („Neznámý“ / „Není relevantní“). Jde například o kontrakt bez faktury nebo bez hodnocení.

## 4. Stránky reportu

| Stránka | Otázka, na kterou odpovídá | Hlavní vizuály | Období podle |
|---|---|---|---|
| **Přehled** | Jak je na tom firma celkově? | KPI karty (odchylka cash flow a mezd od plánu, spokojenost, …), Tržby podle poboček, Hodnota a počet kontraktů podle roku | data platby / začátku kontraktu |
| **Cashflow** | Proč cash flow zaostává za plánem? | KPI příjmy a výdaje vs. plán, Čistý cash flow: skutečnost vs. plán, Příjmy z kontraktů: odchylka od plánu, dekompoziční strom „Kde vzniká odchylka cash flow“ | data platby (plán: plánované datum) |
| **Pohledávky** | Kolik nám zákazníci dluží a jak platí? | KPI Dlužná částka, Počet nezaplacených faktur, Zaplaceno po splatnosti, Průměrné zpoždění platby; Nezaplacené faktury podle roku splatnosti a kategorie; Platební morálka zákazníků; tabulka Největší dlužníci (top 15) | data splatnosti faktury |
| **Mzdy** | Proč mzdy překračují plán? | KPI plán vs. skutečnost; Mzdové náklady: plán vs. skutečnost; Proč mzdy překračují plán: odměny vs. zvýšení platů; Mzdové náklady podle poboček; Průměrná měsíční mzda a počet zaměstnanců | data výplaty |
| **Spokojenost** | Kde a od kdy jsou zákazníci nespokojení? | KPI Průměrná spokojenost a Podíl nespokojených hodnocení; Podíl nespokojených hodnocení podle roku; Průměrné hodnocení podle kategorie zákazníka; 10 nejhůře hodnocených zdrojů vs. ostatní; Zákazníci s nejnižší spokojeností | data hodnocení |
| **Kategorie** | Odpovídají kategorie zákazníků jejich tržbám? | KPI Počet aktuálních zákazníků, Zákazníci s neaktuální ABC kategorií, Skutečná sleva; matice Současná kategorie vs. ABC podle tržeb; Podíl ABC kategorií na tržbách; Hrubý zisk a poskytnuté slevy podle ABC kategorie; Dostávají zákazníci slevu podle své kategorie?; Zákazníci a jejich kategorie | data platby / začátku kontraktu |

Každá stránka má:
- nadpis se zjištěním;
- krátký popis;
- slicery Rok, Kvartál, Měsíc a Pobočka (případně další);
- kartu **Data aktuální k**.

## 5. Filtry

- **Úplná data = „Ano“** je zamčený filtr na všech stránkách. Vynechává měsíce **4/2024–1/2025**, ve kterých ve zdrojových datech chybí většina plateb a hodnocení. Bez filtru by tyto měsíce zkreslily všechny porovnání s plánem.
  - Měsíc je označen „Ne“, pokud má méně než 80 % skutečných plateb oproti plánovaným položkám.
  - Výpočet je v sloupci `D_DEN[Úplná data]`, ne pevně zadanými daty.
- **Karta Skutečná sleva** na stránce Kategorie je omezena na roky 2025–2026. Ceníková cena se počítá z aktuálního ceníku, takže pro starší kontrakty sleva nedává smysl.

## 6. Ukazatele (measures)

- Všechna čísla ve vizuálech pocházejí z pojmenovaných measures, ne z přetažených sloupců.
- Report používá 37 byznysových ukazatelů. Jejich **Definition** a **Calculation** jsou v Dawiso (Business Glossary, space Team 25) a v souboru `Business_glossary_Dawiso_FINAL.xlsx`. Technické názvy odpovídají analýze 2a (`dimenzie_fakty_FINAL.xlsx`).

| Oblast | Ukazatele |
|---|---|
| Cash flow | Čistý peněžní tok, Plánovaný čistý peněžní tok, Odchylka cash flow od plánu (Kč, %), Skutečné / Plánované příjmy, Odchylka příjmů %, Skutečné / Plánované výdaje |
| Pohledávky | Dlužná částka, Počet nezaplacených faktur, Fakturováno podle splatnosti, Podíl zaplacených pozdě, Průměrné zpoždění platby |
| Mzdy | Plánované / Skutečné mzdové náklady, Odchylka mezd od plánu (Kč, %), Překročení mezd – mimořádné odměny, Překročení mezd – zvýšení platů, Počet placených zaměstnanců, Průměrná měsíční mzda |
| Spokojenost | Průměrná spokojenost, Počet hodnocení, Počet nespokojených hodnocení, Podíl nespokojených hodnocení |
| Kategorie a kontrakty | Tržby, Hrubý zisk z kontraktů, Hodnota kontraktů, Počet kontraktů, Počet aktuálních zákazníků, Zákazníci s neaktuální ABC kategorií, Ceníková cena, Poskytnutá sleva, Skutečná sleva %, Sleva podle kategorie % |
| Společné | Data aktuální k |

Důležitá pravidla výpočtu:
- **Porovnatelný plán.** Plán se započítá jen za kombinace *druh operace × rok × měsíc*, ve kterých už existuje skutečná platba. Neporovnává se tak plán budoucích měsíců (9–12/2026) ani měsíců bez dat.
- **Datum agregace se liší podle oblasti:**
  - cash flow a mzdy podle data platby;
  - pohledávky podle data splatnosti;
  - spokojenost podle data hodnocení;
  - kontrakty a slevy podle data začátku kontraktu.
- **Žádná pevně zadaná data v measures.** „Data aktuální k“ se počítá jako datum poslední skutečné platby.
- **Nespokojené hodnocení** je hodnocení 0–6 z 10. Hodnocení 7–8 je neutrální, 9–10 spokojené.

### Barvy (technické measures s prefixem „Barva –“)

Barevné measures vracejí kód barvy pro podmíněné formátování. Barvy jsou stejné v celém reportu:

| Barva | Význam |
|---|---|
| zelená `#2E7D4F` | v pořádku / v plánu |
| červená `#C0392B` | nepříznivé (pod plánem příjmů, nad plánem nákladů, vysoká nespokojenost) |
| šedá `#6B7280` | na hranici (např. nespokojenost 15–30 %, spokojenost 7–8) |
| oranžová `#E8892B` | skutečnost ve sloupcových grafech |
| světle šedá `#CFD4DC` | plán ve sloupcových grafech |
| světle oranžová `#F6CFA5` | nesoulad kategorie v matici |

## 7. Vypočítané sloupce v Power BI

| Tabulka | Sloupec | K čemu slouží |
|---|---|---|
| D_DEN | Úplná data | příznak měsíců s úplnými daty (filtr výpadku) |
| F_KONTRAKT | Stav úhrady | Zaplaceno včas / Zaplaceno pozdě / Nezaplaceno / Nevyfakturováno |
| D_ZAKAZNIK | ABC podle tržeb | aktuální ABC kategorie (A/B/C podle tržeb za posledních 12 měsíců); noví zákazníci bez kategorie = „Nový – bez ABC“ |
| D_ZAKAZNIK | Doporučená kategorie | cenová kategorie, která odpovídá ABC (A = Velkozákazník, B = Malozákazník, C = Normal) |
| D_ZDROJ | Hodnocení zdroje celkem | průměrné hodnocení zdroje za celé období |
| D_ZDROJ | Skupina zdroje | „10 nejhůře hodnocených zdrojů“ vs. „Ostatní zdroje“ |

DAX všech sloupců a measures je v business glossary.

## 8. Známá omezení dat

- **Výpadek dat 4/2024–1/2025.**
  - V tomto období chybí platby, úhrady faktur i hodnocení.
  - Rok 2024 proto obsahuje jen leden–březen a rok 2025 začíná únorem.
  - Kontrakty v datech jsou, proto je graf kontraktů na Přehledu počítá.
- **Ceníková cena** je z aktuálního ceníku. Slevy jsou spolehlivé jen pro poslední roky.
- **Data končí 31. 8. 2026.** Plánované položky za 9–12/2026 se se skutečností nesrovnávají.

## 9. Související výstupy

| Výstup | Soubor / místo |
|---|---|
| 2a – Dimenze, ukazatele, faktové tabulky | `dimenzie_fakty_FINAL.xlsx` |
| 2b – Logické modely | Silver (snowflake) a Gold (star) modely |
| 3 – Datový sklad | BigQuery `fis4it562-team25`: `bronze_matastav`, `silver_matastav`, `gold_matastav` |
| 4 – Business glossary | Dawiso, space Team 25 → Business Glossary (`Business_glossary_Dawiso_FINAL.xlsx`) |
| 5 – Report | `Matastav_25_5.pbix` |
| 6 – Prezentace | Prezentace zjištění a doporučení (10 min) |
