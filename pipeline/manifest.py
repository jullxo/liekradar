"""Manifest zdrojov (evidence log) podľa pravidla kurzu "Log everything".

Ku každému stiahnutému súboru zapíše do vault/manifest_zdrojov.csv:
evidenčné ID zdroja, URL, čas stiahnutia v UTC, SHA-256 a hodnotenie Admiralty.
Agenti potom v správach citujú zdroje ako [E001, A2].

Spustenie (doplní manifest pre súbory, ktoré už máš stiahnuté):
    python -m pipeline.manifest

Pri ďalších sťahovaniach ho dopĺňajú skripty sources_cz a sources_sk automaticky.
"""

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_FILE = Path("vault/manifest_zdrojov.csv")
STLPCE = ["id", "zdroj", "subor", "url", "stiahnute_utc", "sha256", "velkost_bajtov", "admiralty", "metoda"]

# Evidenčné ID a hodnotenie zdrojov. Hodnotenie Admiralty musí sedieť s poznámkami
# Source Assessment vo vault/zdroje/ (A = spoľahlivý zdroj, 1 = potvrdená, 2 = pravdepodobne pravdivá informácia).
ZDROJE = {
    "cz_hlasenia": {
        "id": "E001", "admiralty": "A2",
        "zdroj": "SÚKL – hlásenia o uvedení, prerušení, ukončení a obnovení dodávok",
        "url": "https://opendata.sukl.gov.cz/katalog-otevrenych-dat/"
               "hlaseni-o-uvedeni-preruseni-ukonceni-obnoveni-dodavek-leciveho-pripravku-na-trh",
        "metoda": "otvorené dáta, ZIP s CSV",
    },
    "cz_dlp": {
        "id": "E002", "admiralty": "A1",
        "zdroj": "SÚKL – databáza liekov DLP",
        "url": "https://opendata.sukl.gov.cz/katalog-otevrenych-dat/databaze-lecivych-pripravku-dlp",
        "metoda": "otvorené dáta, ZIP s CSV",
    },
    "cz_dis13": {
        "id": "E003", "admiralty": "A2",
        "zdroj": "SÚKL – DIS-13 dodávky distribútorov",
        "url": "https://opendata.sukl.gov.cz/katalog-otevrenych-dat/dis-13",
        "metoda": "otvorené dáta, mesačné CSV a ročné ZIP",
    },
    "sk_register": {
        "id": "E004", "admiralty": "A1",
        "zdroj": "ŠÚKL – register liekov (API)",
        "url": "https://api.sukl.sk/json/lieky_ui42.php",
        "metoda": "API po stránkach, uložené vybrané stĺpce ako Parquet",
    },
    "sk_hlasenia": {
        "id": "E005", "admiralty": "A2",
        "zdroj": "ŠÚKL – oznámenia o prvom uvedení, prerušení, zrušení a obnovení dodávok",
        "url": "https://portal.sukl.sk/PreruseniePublic/",
        "metoda": "CSV export z verejného portálu",
    },
}


def sha256_suboru(cesta: Path) -> str:
    """SHA-256 súboru, čítané po kúskoch, aby to zvládlo aj veľké súbory."""
    h = hashlib.sha256()
    with open(cesta, "rb") as f:
        for kus in iter(lambda: f.read(1024 * 1024), b""):
            h.update(kus)
    return h.hexdigest()


def _nacitaj() -> list[dict]:
    if not MANIFEST_FILE.exists():
        return []
    with open(MANIFEST_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def zaznamenaj(kluc: str, subor: Path, url: str | None = None, cas: datetime | None = None) -> dict | None:
    """Zapíše súbor do manifestu. Ten istý súbor s tým istým obsahom nezapíše dvakrát."""
    subor = Path(subor)
    if not subor.exists():
        return None
    info = ZDROJE[kluc]
    sha = sha256_suboru(subor)
    cesta = subor.as_posix()
    riadky = _nacitaj()
    if any(r["subor"] == cesta and r["sha256"] == sha for r in riadky):
        return None

    cas = cas or datetime.now(timezone.utc)
    riadok = {
        "id": info["id"],
        "zdroj": info["zdroj"],
        "subor": cesta,
        "url": url or info["url"],
        "stiahnute_utc": cas.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha,
        "velkost_bajtov": subor.stat().st_size,
        "admiralty": info["admiralty"],
        "metoda": info["metoda"],
    }
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    novy = not MANIFEST_FILE.exists()
    with open(MANIFEST_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=STLPCE)
        if novy:
            writer.writeheader()
        writer.writerow(riadok)
    return riadok


def doplnit_existujuce() -> None:
    """Zapíše do manifestu súbory, ktoré už sú stiahnuté.

    Ako čas stiahnutia použije čas, keď bol súbor uložený na disk (posledná zmena).
    """
    raw = Path("data/raw")
    subory = {
        "cz_hlasenia": list((raw / "cz" / "hlasenia").glob("mr_hlaseni.csv")),
        "cz_dlp": [p for p in (raw / "cz" / "dlp").rglob("*.csv") if p.name.lower().startswith("dlp_lecivepripravky")],
        "cz_dis13": sorted(p for p in (raw / "cz" / "dis13").glob("*") if p.suffix.lower() in (".csv", ".zip")),
        "sk_register": [raw / "sk" / "register.parquet"],
        "sk_hlasenia": [raw / "sk" / "hlasenia_export.csv"],
    }
    pridane = 0
    for kluc, zoznam in subory.items():
        for subor in zoznam:
            if subor.exists():
                cas = datetime.fromtimestamp(subor.stat().st_mtime, tz=timezone.utc)
                if zaznamenaj(kluc, subor, cas=cas):
                    pridane += 1
    print(f"Pridaných záznamov: {pridane}")


def vypis() -> None:
    riadky = _nacitaj()
    print(f"\n=== Manifest zdrojov ({MANIFEST_FILE}) ===")
    for r in riadky:
        print(f"{r['id']}  {r['admiralty']}  {r['stiahnute_utc']}  {r['sha256'][:12]}  {r['subor']}")


if __name__ == "__main__":
    doplnit_existujuce()
    vypis()
