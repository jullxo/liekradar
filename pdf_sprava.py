"""PDF so správou AI analytika v dizajne LiekRadaru (písmo Montserrat, farby z aplikácie).

Používa ho app.py pri tlačidle „Stiahnuť správu (PDF)“. Písmo je v assets/fonts (licencia SIL OFL).
"""

from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from fpdf import FPDF

FONTY = Path(__file__).parent / "assets" / "fonts"
MODRA = (36, 87, 143)
SVETLA = (220, 232, 244)
TEXT = (29, 43, 63)
SIVA = (107, 122, 144)
ZELENA = (30, 120, 70)
ORANZOVA = (170, 105, 0)


@lru_cache(maxsize=1)
def _znaky_pisma() -> frozenset:
    """Znaky, ktoré písmo obsahuje (ostatné z textu vynecháme, aby v PDF neboli prázdne štvorčeky)."""
    try:
        from fontTools.ttLib import TTFont
        return frozenset(TTFont(FONTY / "Montserrat-Regular.ttf").getBestCmap())
    except Exception:
        return frozenset()


def _cisty(text: str) -> str:
    znaky = _znaky_pisma()
    if znaky:
        text = "".join(ch for ch in text if ord(ch) in znaky or ch in "\n\t ")
    return text


def _markdown(text: str) -> str:
    """Markdown od modelu do tvaru, ktorý vie fpdf2: **tučné**, __kurzíva__, odrážky ako •."""
    text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)      # [[odkaz]] -> odkaz
    text = text.replace("`", "")
    text = re.sub(r"(?<!\*)\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\*)", r"__\1__", text)  # *kurzíva*
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.M)
    text = text.replace("--", "–")  # fpdf2 by "--" bral ako podčiarknutie
    return _cisty(text)


class _Pdf(FPDF):
    def __init__(self, pata: str, strana: str):
        super().__init__(format="A4")
        self.pata, self.strana = pata, strana
        for styl, subor in (("", "Regular"), ("B", "Bold"), ("I", "Italic"), ("BI", "Bold")):
            self.add_font("Montserrat", styl, str(FONTY / f"Montserrat-{subor}.ttf"))
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(True, margin=22)

    def footer(self):
        self.set_y(-16)
        self.set_draw_color(*SVETLA)
        self.line(18, self.get_y(), self.w - 18, self.get_y())
        self.set_font("Montserrat", "", 7)
        self.set_text_color(*SIVA)
        self.multi_cell(self.w - 36 - 20, 3.6, _cisty(self.pata), new_x="RIGHT", new_y="TOP")
        self.cell(20, 3.6, f"{self.strana} {self.page_no()}", align="R")


def vytvor_pdf(nadpis: str, casti: dict, *, otazka: str, kontrola: str, schvalene: bool,
               nazvy: dict, pata: str, podtitul: str, popis_otazky: str, strana: str) -> bytes:
    """nadpis + časti správy (bluf, zistenia, podklady, …) -> PDF ako bajty.

    nazvy: {kľúč časti: nadpis v zvolenom jazyku}; poradie slovníka určuje poradie v PDF.
    """
    pdf = _Pdf(pata, strana)
    pdf.add_page()
    sirka = pdf.w - 36

    # hlavička: modrý pás so značkou
    pdf.set_fill_color(*MODRA)
    pdf.rect(0, 0, pdf.w, 26, style="F")
    pdf.set_fill_color(*SVETLA)
    pdf.ellipse(pdf.w - 46, -22, 60, 60, style="F")
    pdf.set_xy(18, 7)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Montserrat", "B", 18)
    pdf.cell(0, 8, "LiekRadar", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Montserrat", "I", 8.5)
    pdf.cell(0, 5, _cisty(podtitul), new_x="LMARGIN", new_y="NEXT")

    # nadpis a otázka
    pdf.set_y(34)
    pdf.set_text_color(*MODRA)
    pdf.set_font("Montserrat", "B", 15)
    pdf.multi_cell(sirka, 7, _cisty(nadpis or otazka), align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_text_color(*SIVA)
    pdf.set_font("Montserrat", "", 8.5)
    pdf.multi_cell(sirka, 4.5, _cisty(f"{popis_otazky}: {otazka}  ·  {datetime.now():%d. %m. %Y}"),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # stručná odpoveď v rámčeku
    if casti.get("bluf"):
        y = pdf.get_y()
        pdf.set_x(22)
        pdf.set_font("Montserrat", "B", 7.5)
        pdf.set_text_color(*MODRA)
        pdf.cell(0, 6, _cisty(nazvy.get("bluf", "").upper()), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(22)
        pdf.set_font("Montserrat", "", 10)
        pdf.set_text_color(*TEXT)
        pdf.multi_cell(sirka - 6, 5.4, _markdown(casti["bluf"]), markdown=True, align="L", new_x="LMARGIN", new_y="NEXT")
        vyska = pdf.get_y() - y + 3
        if pdf.get_y() > y:  # rámček len ak sa odpoveď zmestila na jednu stranu
            pdf.set_draw_color(*SVETLA)
            pdf.set_line_width(0.2)
            pdf.rect(18, y - 2, sirka, vyska, style="D")
            pdf.set_fill_color(*MODRA)
            pdf.rect(18, y - 2, 1.2, vyska, style="F")
        pdf.ln(5)

    # výsledok kontroly faktov
    pdf.set_font("Montserrat", "B", 9)
    pdf.set_text_color(*(ZELENA if schvalene else ORANZOVA))
    pdf.multi_cell(sirka, 4.8, _cisty(kontrola), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ostatné časti
    for kluc, nazov in nazvy.items():
        if kluc == "bluf" or not casti.get(kluc):
            continue
        if pdf.get_y() > pdf.h - 45:
            pdf.add_page()
        pdf.set_font("Montserrat", "B", 11.5)
        pdf.set_text_color(*MODRA)
        pdf.cell(0, 7, _cisty(nazov), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*SVETLA)
        pdf.line(18, pdf.get_y(), 18 + sirka, pdf.get_y())
        pdf.ln(2)
        pdf.set_font("Montserrat", "", 9)
        pdf.set_text_color(*TEXT)
        for odsek in [o for o in casti[kluc].split("\n") if o.strip()]:
            pdf.multi_cell(sirka, 4.7, _markdown(odsek), markdown=True, align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        pdf.ln(3)

    return bytes(pdf.output())
