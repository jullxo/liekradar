"""Jednorazový prieskum portálu ŠÚKL s hláseniami o prerušení dodávok.

Nič nemení, len stiahne jednu stránku, uloží ju a vypíše, ako je postavená.
Spustenie:  python -m pipeline._prieskum_portalu
"""

import re
from pathlib import Path

import requests

HEADERS = {"User-Agent": "LiekRadar (studentsky projekt VSE, 4IT529)"}
BASE = "https://portal.sukl.sk/PreruseniePublic/"
LIST_URL = BASE + "?act=PrerusenieOznList&lang=sk&mid=2"
OUT = Path("data/raw/sk/portal_ukazka.html")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    robots = requests.get("https://portal.sukl.sk/robots.txt", headers=HEADERS, timeout=30)
    print("=== robots.txt ===")
    print(robots.status_code, robots.text[:500] if robots.ok else "(nie je)")

    response = requests.get(LIST_URL, headers=HEADERS, timeout=60)
    print("\n=== Stránka so zoznamom ===")
    print("Status:", response.status_code, "| Kódovanie:", response.encoding,
          "| Veľkosť:", len(response.text), "znakov")
    OUT.write_text(response.text, encoding="utf-8")
    print("Uložené do", OUT)

    html = response.text
    print("Počet riadkov tabuľky <tr>:", len(re.findall(r"<tr", html, flags=re.I)))

    print("\n=== Formuláre ===")
    for form in re.findall(r"<form[^>]*>", html, flags=re.I):
        print(form[:200])
    inputs = re.findall(r"<input[^>]*>", html, flags=re.I)
    print("Počet polí <input>:", len(inputs))
    for field in inputs[:25]:
        print("  ", field[:160])

    print("\n=== Odkazy, ktoré vyzerajú ako stránkovanie ===")
    links = sorted(set(re.findall(r'href="([^"]*act=[^"]*)"', html, flags=re.I)))
    for link in links[:40]:
        print("  ", link.replace("&amp;", "&"))

    print("\n=== Text okolo slov strana / page / ďalšia ===")
    for match in re.finditer(r"(strana|page|ďalš|dalsi|next|>>|&gt;&gt;)", html, flags=re.I):
        start = max(match.start() - 120, 0)
        print("  …", re.sub(r"\s+", " ", html[start:match.end() + 120]), "…")
        break

    print("\n=== Prvý riadok tabuľky s dátami (HTML) ===")
    rows = re.findall(r"<tr.*?</tr>", html, flags=re.I | re.S)
    for row in rows:
        if re.search(r"\d{1,2}\.\d{1,2}\.\d{4}", row):
            print(re.sub(r"\s+", " ", row)[:800])
            break


if __name__ == "__main__":
    main()
