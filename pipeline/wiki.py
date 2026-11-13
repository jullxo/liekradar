"""Generátor wiki pre Obsidian (LLM Wiki Pattern, upravené podľa pravidiel kurzu).

Vytvára Entity Notes podľa šablóny kurzu do vault/wiki/:
    vault/wiki/latky/<ATC>.md         jedna poznámka na účinnú látku
    vault/wiki/firmy/<Firma>.md       jedna poznámka na držiteľa registrácie
    vault/wiki/00 Mapa látok.md       rozcestník (Map of Content)
    vault/wiki/00 Mapa firiem.md

Sekcie Identifiers, Facts, Relations a Timeline píše vždy tento skript priamo z dát.
Sekciu "Analyst notes" dopĺňajú agenti alebo človek a skript ju pri ďalšom behu NIKDY
neprepíše. Rovnako zachová príznak `verified` v hlavičke (prepína ho len človek).

Spustenie (po pipeline.normalize, match_cz_sk a kiq2_posun):
    python -m pipeline.wiki         # všetky látky s výpadkom a firmy s aspoň 3 výpadkami
    python -m pipeline.wiki J01     # len látky so zadaným začiatkom ATC (rýchla ukážka)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline import analytika as an
from pipeline.kiq2_posun import ATC_SKUPINY

VAULT = Path("vault")
WIKI = VAULT / "wiki"
LATKY_DIR = WIKI / "latky"
FIRMY_DIR = WIKI / "firmy"

MIN_VYPADKOV_FIRMY = 3
TIMELINE_RIADKOV = 15

ANALYST_NADPIS = "## Analyst notes"
ANALYST_PRAZDNE = (
    "## Analyst notes (inference, clearly marked)\n"
    "<!-- Sem píšu agenti a analytik. Generátor túto sekciu nikdy neprepíše.\n"
    "     Každý záznam: dátum (UTC), autor (agent / meno), text, citované zdroje [E00x, známka].\n"
    "     Úsudky agentov majú vždy verified: false, kým ich nepotvrdí človek. -->\n"
)


# ---------------------------------------------------------------------------
# Pomocné funkcie
# ---------------------------------------------------------------------------

def _nazov_suboru(text: str) -> str:
    """Názov súboru bez znakov, ktoré Windows alebo Obsidian nepovoľujú."""
    return re.sub(r'[<>:"/\\|?*#^\[\]]', "", str(text)).strip().rstrip(".") or "bez nazvu"


def _zachovane(cesta: Path) -> tuple[str, str]:
    """Z existujúcej poznámky vytiahne sekciu Analyst notes a hodnotu verified."""
    if not cesta.exists():
        return ANALYST_PRAZDNE, "false"
    text = cesta.read_text(encoding="utf-8")
    verified = re.search(r"^verified:\s*(true|false)\s*$", text, flags=re.M)
    zaciatok = text.find(ANALYST_NADPIS)
    poznamky = text[zaciatok:] if zaciatok >= 0 else ANALYST_PRAZDNE
    return poznamky, verified.group(1) if verified else "false"


def _frontmatter(polia: dict) -> str:
    riadky = ["---"]
    for kluc, hodnota in polia.items():
        if isinstance(hodnota, bool):
            hodnota = "true" if hodnota else "false"
        elif isinstance(hodnota, (list, dict, str)):
            hodnota = json.dumps(hodnota, ensure_ascii=False)
        elif hodnota is None or (isinstance(hodnota, float) and pd.isna(hodnota)):
            hodnota = "null"
        riadky.append(f"{kluc}: {hodnota}")
    riadky.append("---")
    return "\n".join(riadky)


def _zapis(cesta: Path, frontmatter: dict, telo: str) -> None:
    poznamky, verified = _zachovane(cesta)
    frontmatter["verified"] = verified == "true"
    cesta.parent.mkdir(parents=True, exist_ok=True)
    cesta.write_text(_frontmatter(frontmatter) + "\n" + telo.rstrip() + "\n\n" + poznamky.rstrip() + "\n",
                     encoding="utf-8")


def _cislo(x) -> str:
    return "—" if x is None or (isinstance(x, float) and pd.isna(x)) else f"{int(round(x)):,}".replace(",", " ")


def _percento(x) -> str:
    return "—" if x is None else f"{x:+.0%}"


# ---------------------------------------------------------------------------
# Látky
# ---------------------------------------------------------------------------

def _timeline_latky(atc: str) -> list[str]:
    ep = an._podla_atc("epizody").get(atc)
    if ep is None:
        return []
    ep = ep[(ep["zaciatok"] >= an.SPOLOCNE_OD) & ~ep["planovany"]]
    udalosti = []
    for r in ep.itertuples():
        zdroj = an.ZDROJ[(r.krajina, "hlasenia")]
        udalosti.append((r.zaciatok, r.krajina, f"začiatok výpadku: {r.nazov} ({r.kod})", zdroj))
        if pd.notna(r.koniec):
            co = "zrušenie dodávok" if r.ako_skoncil == "zrusenie" else "obnovenie dodávok"
            udalosti.append((r.koniec, r.krajina, f"{co}: {r.nazov} ({r.kod})", zdroj))
    udalosti.sort(key=lambda u: u[0], reverse=True)
    return [f"| {an._datum(d)} | {k} | {u} | {z} |" for d, k, u, z in udalosti[:TIMELINE_RIADKOV]]


def poznamka_latky(atc: str, firmy_s_poznamkou: dict, latky_s_poznamkou: set, generovane: str) -> Path:
    d = an.detail_latky(atc)
    p = an.posun_latky(atc)
    cz, sk = d["krajiny"]["CZ"], d["krajiny"]["SK"]

    riadky = [f"# {atc} {d['nazov']}".rstrip(), ""]
    riadky += ["⬆ [[00 Mapa látok]]", ""]

    riadky += ["## Identifiers",
               f"- ATC: `{atc}`, skupina {atc[0]} – {d['skupina']}",
               f"- Názov látky: {d['nazov'] or '—'}",
               f"- Registrované balenia: ČR {cz['registrovane_balenia']} {an.ZDROJ[('CZ', 'lieky')]}, "
               f"SR {sk['registrovane_balenia']} {an.ZDROJ[('SK', 'lieky')]}", ""]

    riadky += ["## Facts (with sources)"]
    for krajina, info in (("ČR", cz), ("SR", sk)):
        kod = "CZ" if krajina == "ČR" else "SK"
        zdroj = an.ZDROJ[(kod, "hlasenia")]
        median = "—" if info["median_dlzky_dni"] is None else f"{info['median_dlzky_dni']:.0f} dní"
        riadky.append(f"- {krajina}: od 15. 4. 2019 {info['vypadky_od_2019']} výpadkov balení, "
                      f"z toho {info['vypadky_12m']} za posledných 12 mesiacov; medián dĺžky ukončených {median} {zdroj}")
        riadky.append(f"- {krajina}: počet balení teraz vo výpadku {info['pocet_teraz_vo_vypadku']}, "
                      f"ohlásených budúcich výpadkov {len(info['ohlasene_vypadky'])} {zdroj}")
    dod = cz.get("dodavky")
    if dod:
        riadky.append(f"- ČR dodávky do lekární {dod['obdobie']}: {_cislo(dod['baleni_lekarne_3m'])} balení "
                      f"({_percento(dod['zmena_oproti_predch_3m'])} oproti predchádzajúcim 3 mesiacom); "
                      f"vývoz {_cislo(dod['baleni_vyvoz_3m'])} balení {an.ZDROJ[('CZ', 'dodavky')]}")
    riadky.append(f"- Vlny výpadkov (KIQ2): ČR {p['vlny_cz']}, SR {p['vlny_sk']}; súčasne do 7 dní {p['sucasne_do_7_dni']}×, "
                  f"ČR skôr o 8–60 dní {p['cr_skor_8_60_dni']}×, SR skôr o 8–60 dní {p['sr_skor_8_60_dni']}× "
                  f"{an.ZDROJ[('CZ', 'hlasenia')]} {an.ZDROJ[('SK', 'hlasenia')]}")
    riadky.append("")

    riadky += ["## Relations"]
    vyrobcovia = {}
    for info in (cz, sk):
        for nazov, pocet in info["vyrobcovia"].items():
            kluc = an.firma_kluc(nazov)
            vyrobcovia[kluc] = vyrobcovia.get(kluc, 0) + pocet
    odkazy = [f"[[{firmy_s_poznamkou[k]}]]" if k in firmy_s_poznamkou else an.nazov_firmy(k)
              for k, _ in sorted(vyrobcovia.items(), key=lambda x: -x[1])[:12]]
    riadky.append(f"- drží registráciu: {', '.join(odkazy) if odkazy else '—'}")
    surodenci = sorted(a for a in latky_s_poznamkou if a[:5] == atc[:5] and a != atc)
    riadky.append(f"- iné látky v skupine {atc[:5]}: {', '.join(f'[[{a}]]' for a in surodenci) if surodenci else '—'}")
    riadky.append("")

    riadky += ["## Timeline", "| Dátum | Krajina | Udalosť | Zdroj |", "|---|---|---|---|"]
    riadky += _timeline_latky(atc) or ["| — | — | žiadne výpadky od 15. 4. 2019 | — |"]
    riadky.append("")

    frontmatter = {
        "typ": "latka", "atc": atc, "nazov": d["nazov"], "aliases": [d["nazov"]] if d["nazov"] else [],
        "skupina": atc[0],
        "vypadky_cz_od_2019": cz["vypadky_od_2019"], "vypadky_sk_od_2019": sk["vypadky_od_2019"],
        "teraz_vo_vypadku_cz": cz["pocet_teraz_vo_vypadku"], "teraz_vo_vypadku_sk": sk["pocet_teraz_vo_vypadku"],
        "zdroje": ["E001", "E002", "E003", "E004", "E005"], "generovane_utc": generovane,
    }
    cesta = LATKY_DIR / f"{_nazov_suboru(atc)}.md"
    _zapis(cesta, frontmatter, "\n".join(riadky))
    return cesta


# ---------------------------------------------------------------------------
# Firmy
# ---------------------------------------------------------------------------

def poznamka_firmy(kluc: str, nazov_suboru: str, ep: pd.DataFrame, lieky: pd.DataFrame,
                   latky_s_poznamkou: set, generovane: str) -> Path:
    dnes = an._dnes()
    e = ep[ep["firma"] == kluc]
    l = lieky[lieky["firma"] == kluc]
    nazvy = sorted(set(l["drzitel"].dropna()) | set(e["drzitel"].dropna()))

    riadky = [f"# {nazov_suboru}", "", "⬆ [[00 Mapa firiem]]", ""]
    riadky += ["## Identifiers", f"- Názvy v registroch: {', '.join(nazvy[:8])}",
               f"- Registrované balenia: ČR {int((l['krajina'] == 'CZ').sum())} {an.ZDROJ[('CZ', 'lieky')]}, "
               f"SR {int((l['krajina'] == 'SK').sum())} {an.ZDROJ[('SK', 'lieky')]}", ""]

    riadky += ["## Facts (with sources)"]
    for krajina, nazov_kr in (("CZ", "ČR"), ("SK", "SR")):
        ek = e[e["krajina"] == krajina]
        balenia = max(int((l["krajina"] == krajina).sum()), 1)
        za_rok = int((ek["zaciatok"] > dnes - pd.Timedelta(days=365)).sum())
        riadky.append(f"- {nazov_kr}: od 15. 4. 2019 {len(ek)} výpadkov balení, za posledných 12 mesiacov {za_rok} "
                      f"(to je {za_rok / balenia:.1%} registrovaných balení), teraz trvá {int(ek['trva'].sum())} "
                      f"{an.ZDROJ[(krajina, 'hlasenia')]}")
    riadky.append("")

    top = e.groupby("atc").size().sort_values(ascending=False).head(25)
    odkazy = [f"[[{a}]] ({n}×)" if a in latky_s_poznamkou else f"{a} ({n}×)" for a, n in top.items()]
    riadky += ["## Relations", f"- drží registráciu látok s výpadkami: {', '.join(odkazy) if odkazy else '—'}", ""]

    riadky += ["## Timeline", "| Dátum | Krajina | Udalosť | Zdroj |", "|---|---|---|---|"]
    for r in e.sort_values("zaciatok", ascending=False).head(TIMELINE_RIADKOV).itertuples():
        riadky.append(f"| {an._datum(r.zaciatok)} | {r.krajina} | začiatok výpadku: {r.nazov} ({r.kod}, [[{r.atc}]]) "
                      f"| {an.ZDROJ[(r.krajina, 'hlasenia')]} |")
    riadky.append("")

    frontmatter = {
        "typ": "firma", "firma": kluc, "aliases": nazvy[:8],
        "vypadky_cz_od_2019": int((e["krajina"] == "CZ").sum()), "vypadky_sk_od_2019": int((e["krajina"] == "SK").sum()),
        "zdroje": ["E001", "E002", "E004", "E005"], "generovane_utc": generovane,
    }
    cesta = FIRMY_DIR / f"{nazov_suboru}.md"
    _zapis(cesta, frontmatter, "\n".join(riadky))
    return cesta


# ---------------------------------------------------------------------------
# Rozcestníky a hlavný beh
# ---------------------------------------------------------------------------

def _mapa_latok(latky: list, pocty: pd.DataFrame) -> None:
    riadky = ["# 00 Mapa látok", "", "Rozcestník všetkých látok s výpadkom od 15. 4. 2019. Generované z dát, neupravovať ručne.", ""]
    for skupina in sorted({a[0] for a in latky}):
        riadky += [f"## {skupina} – {ATC_SKUPINY.get(skupina, '')}", ""]
        for atc in sorted(a for a in latky if a[0] == skupina):
            cz = int(pocty.at[atc, "CZ"]) if atc in pocty.index and "CZ" in pocty else 0
            sk = int(pocty.at[atc, "SK"]) if atc in pocty.index and "SK" in pocty else 0
            riadky.append(f"- [[{atc}]] {an.nazov_atc(atc)} – výpadky ČR {cz}, SR {sk}")
        riadky.append("")
    (WIKI / "00 Mapa látok.md").write_text("\n".join(riadky), encoding="utf-8")


def _mapa_firiem(firmy: dict, pocty: pd.Series) -> None:
    riadky = ["# 00 Mapa firiem", "", f"Držitelia registrácie s aspoň {MIN_VYPADKOV_FIRMY} výpadkami od 15. 4. 2019, "
              "zoradení podľa počtu výpadkov. Generované z dát, neupravovať ručne.", ""]
    for kluc in pocty.sort_values(ascending=False).index:
        if kluc in firmy:
            riadky.append(f"- [[{firmy[kluc]}]] – {int(pocty[kluc])} výpadkov")
    (WIKI / "00 Mapa firiem.md").write_text("\n".join(riadky) + "\n", encoding="utf-8")


def run(atc_prefix: str | None = None) -> None:
    generovane = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ep = an._tab("epizody")
    ep = ep[(ep["zaciatok"] >= an.SPOLOCNE_OD) & ~ep["planovany"] & (ep["atc"].fillna("").str.len() == 7)].copy()
    ep["firma"] = ep["drzitel"].map(an.firma_kluc)
    lieky = an._tab("lieky").copy()
    lieky["firma"] = lieky["drzitel"].map(an.firma_kluc)

    latky = sorted(ep["atc"].unique())
    if atc_prefix:
        latky = [a for a in latky if a.startswith(atc_prefix.upper())]
    latky_set = set(latky)

    pocty_firiem = ep.groupby("firma").size()
    pocty_firiem = pocty_firiem[(pocty_firiem >= MIN_VYPADKOV_FIRMY) & (pocty_firiem.index != "")]
    if atc_prefix:
        pocty_firiem = pocty_firiem[pocty_firiem.index.isin(ep[ep["atc"].isin(latky_set)]["firma"])]
    firmy = {}
    pouzite = set()
    for kluc in pocty_firiem.index:
        nazov = _nazov_suboru(an.nazov_firmy(kluc))
        if nazov.lower() in pouzite:  # dve firmy s rovnakým názvom súboru
            nazov = f"{nazov} ({kluc})"
        pouzite.add(nazov.lower())
        firmy[kluc] = nazov

    print(f"Píšem {len(latky)} poznámok o látkach…")
    for i, atc in enumerate(latky, 1):
        poznamka_latky(atc, firmy, latky_set, generovane)
        if i % 200 == 0:
            print(f"  {i}/{len(latky)}")

    print(f"Píšem {len(firmy)} poznámok o firmách…")
    for kluc, nazov in firmy.items():
        poznamka_firmy(kluc, nazov, ep, lieky, latky_set, generovane)

    _mapa_latok(latky, ep.groupby(["atc", "krajina"]).size().unstack(fill_value=0))
    _mapa_firiem(firmy, pocty_firiem)
    for priecinok in ("cases", "reports"):
        (VAULT / priecinok).mkdir(parents=True, exist_ok=True)
        (VAULT / priecinok / ".gitkeep").touch()
    print(f"Hotovo: {WIKI}  (látky {len(latky)}, firmy {len(firmy)})")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
