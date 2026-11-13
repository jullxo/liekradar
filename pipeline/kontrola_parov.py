"""Vzorka párov ČR–SR na ručnú kontrolu.

Párujeme na úrovni účinnej látky (ATC, 7 znakov) a výrobcov spájame podľa začiatku názvu
(analytika.firma_kluc). Obe veci treba overiť očami: vyberieme 50 látok a ku každej
jeden český a jeden slovenský liek, podľa možnosti od toho istého výrobcu.

Spustenie (po pipeline.normalize a pipeline.match_cz_sk):
    python -m pipeline.kontrola_parov               # vytvorí súbor na vyplnenie
    python -m pipeline.kontrola_parov --vyhodnot    # spočíta výsledok z vyplneného súboru

Súbor: vault/metodika/kontrola_parov.csv (otvára sa v Exceli, oddeľovač ;)
Vyplníš stĺpce ta_ista_latka a ten_isty_vyrobca hodnotou A (áno) alebo N (nie), prípadne poznámku.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from pipeline import analytika as an
from pipeline.match_cz_sk import PARY_FILE

SUBOR = Path("vault/metodika/kontrola_parov.csv")
SPRAVA = Path("vault/metodika/Kontrola párovania.md")
POCET = 50


def _vyber_latky(pary: pd.DataFrame) -> list:
    """Polovica látok s najviac výpadkami (na tých stoja výsledky), polovica náhodných."""
    pary = pary.assign(vypadky=pary["vypadky_CZ"] + pary["vypadky_SK"])
    top = pary.sort_values("vypadky", ascending=False).head(POCET // 2)["atc"].tolist()
    ostatne = pary[~pary["atc"].isin(top)]
    nahodne = ostatne.sample(min(len(ostatne), POCET - len(top)), random_state=42)["atc"].tolist()
    return top + nahodne


def vytvor() -> None:
    pary = pd.read_parquet(PARY_FILE)
    lieky = an._tab("lieky")
    lieky = lieky[lieky["atc"].isin(_vyber_latky(pary))].copy()
    lieky["firma"] = lieky["drzitel"].map(an.firma_kluc)

    riadky = []
    for atc, skupina in lieky.groupby("atc", sort=False):
        cz, sk = skupina[skupina["krajina"] == "CZ"], skupina[skupina["krajina"] == "SK"]
        if cz.empty or sk.empty:
            continue
        spolocne = (set(cz["firma"]) & set(sk["firma"])) - {""}
        if spolocne:  # výrobca, ktorý má látku v oboch krajinách: overíme aj spájanie firiem
            firma = max(spolocne, key=lambda f: (cz["firma"] == f).sum() + (sk["firma"] == f).sum())
            c, s = cz[cz["firma"] == firma].iloc[0], sk[sk["firma"] == firma].iloc[0]
        else:
            c, s = cz.iloc[0], sk.iloc[0]
        riadky.append({
            "atc": atc, "latka": an.nazov_atc(atc),
            "cz_kod": c["kod"], "cz_nazov": f"{c['nazov']} {c['doplnok'] or ''}".strip(),
            "cz_drzitel": c["drzitel"],
            "sk_kod": s["kod"], "sk_nazov": f"{s['nazov']} {s['doplnok'] or ''}".strip(),
            "sk_drzitel": s["drzitel"],
            "system_spojil_vyrobcu": "áno" if c["firma"] and c["firma"] == s["firma"] else "nie",
            "ta_ista_latka": "", "ten_isty_vyrobca": "", "poznamka": "",
        })
    tab = pd.DataFrame(riadky).sort_values("atc")
    SUBOR.parent.mkdir(parents=True, exist_ok=True)
    tab.to_csv(SUBOR, sep=";", index=False, encoding="utf-8-sig")
    print(f"Vytvorené: {SUBOR}  ({len(tab)} párov)")
    print("Otvor v Exceli a do stĺpcov ta_ista_latka a ten_isty_vyrobca napíš A alebo N.")
    print("Ulož ako CSV (oddeľovač bodkočiarka) pod rovnakým názvom.")


def vyhodnot() -> None:
    try:
        tab = pd.read_csv(SUBOR, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    except UnicodeDecodeError:  # Excel niekedy uloží CSV v kódovaní Windows
        tab = pd.read_csv(SUBOR, sep=";", dtype=str, encoding="cp1250").fillna("")
    for stlpec in ("ta_ista_latka", "ten_isty_vyrobca"):
        tab[stlpec] = tab[stlpec].str.strip().str.upper().str[:1]
    latka = tab[tab["ta_ista_latka"].isin(["A", "N"])]
    spojene = tab[(tab["system_spojil_vyrobcu"] == "áno") & tab["ten_isty_vyrobca"].isin(["A", "N"])]
    nespojene = tab[(tab["system_spojil_vyrobcu"] == "nie") & tab["ten_isty_vyrobca"].isin(["A", "N"])]

    ok_latka = (latka["ta_ista_latka"] == "A").sum()
    ok_spojene = (spojene["ten_isty_vyrobca"] == "A").sum()
    zle_nespojene = (nespojene["ten_isty_vyrobca"] == "A").sum()

    riadky = ["# Ručná kontrola párovania ČR–SR", "",
              f"Vzorka {len(tab)} účinných látok (polovica s najviac výpadkami, polovica náhodne). Ku každej "
              "jeden liek z ČR a jeden zo SR, podľa možnosti od toho istého výrobcu. Kontroloval človek "
              f"podľa názvu, sily a držiteľa registrácie. Podklad: `{SUBOR.name}`.", "",
              "| Kontrola | Výsledok |", "|---|---|",
              f"| Rovnaká účinná látka pod rovnakým ATC kódom | {ok_latka} z {len(latka)} |",
              f"| Systém spojil výrobcu a je to naozaj ten istý výrobca (skupina) | {ok_spojene} z {len(spojene)} |",
              f"| Systém výrobcu nespojil, hoci je to ten istý | {zle_nespojene} z {len(nespojene)} |", ""]
    chyby = tab[(tab["ta_ista_latka"] == "N") | ((tab["system_spojil_vyrobcu"] == "áno") & (tab["ten_isty_vyrobca"] == "N"))
                | ((tab["system_spojil_vyrobcu"] == "nie") & (tab["ten_isty_vyrobca"] == "A"))]
    if not chyby.empty:
        riadky += ["Nájdené chyby:", ""]
        for r in chyby.itertuples():
            riadky.append(f"- {r.atc} {r.latka}: {r.cz_nazov} ({r.cz_drzitel}) × {r.sk_nazov} ({r.sk_drzitel})"
                          + (f" – {r.poznamka}" if r.poznamka else ""))
        riadky.append("")
    SPRAVA.write_text("\n".join(riadky), encoding="utf-8")
    print("\n".join(riadky))
    print(f"\nUložené: {SPRAVA}")


if __name__ == "__main__":
    vyhodnot() if "--vyhodnot" in sys.argv else vytvor()
