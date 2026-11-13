"""Prístup k modelu Gemini pre agentov LiekRadaru.

- Kľúč a názov modelu sa čítajú zo st.secrets (GEMINI_API_KEY, GEMINI_MODEL), inak z premenných
  prostredia. Kľúč sa nikdy nevypisuje, nezapisuje do logov ani do Case Logu.
- Bezplatná úroveň Gemini: 15 požiadaviek za minútu a 500 za deň. Obmedzovač drží najviac
  15 volaní za 60 s v rámci procesu a najviac MAX_VOLANI_NA_OTAZKU volaní na jednu otázku.
- Pri chybe 429 počká (podľa odpovede servera, najviac 60 s) a skúsi to raz znova.
  Pri 503 (model dočasne preťažený) počká 15 s a tiež skúsi raz znova. Ak aj potom vráti 503,
  prepne sa na záložný model GEMINI_MODEL_FALLBACK (predvolene gemini-3.1-flash-lite) a ten
  používa až do konca otázky. Ktorý model krok spravil, je v `posledny_model`.
- LIEKRADAR_FAKE_LLM=1: namiesto Gemini vráti pevné odpovede, ktoré pripraví každý agent sám.
  Graf sa tak dá otestovať bez kľúča a bez míňania limitu. LIEKRADAR_FAKE_503=n navyše simuluje,
  že od n-tého volania je hlavný model preťažený (test záložného modelu).
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import deque

from pydantic import BaseModel

MAX_VOLANI_NA_OTAZKU = 6
LIMIT_ZA_MINUTU = 15
CAKANIE_PRI_429_MAX_S = 60
CAKANIE_PRI_503_S = 15
PREDVOLENY_MODEL = "gemini-3.5-flash-lite"
PREDVOLENY_ZALOZNY_MODEL = "gemini-3.1-flash-lite"

_casy_volani: deque = deque()  # časy volaní za poslednú minútu (spoločné pre všetky otázky v procese)
_zamok = threading.Lock()


class LLMChyba(RuntimeError):
    """Chyba pri volaní modelu so správou, ktorú môže aplikácia ukázať používateľovi."""


def _nastavenie(nazov: str) -> str | None:
    """Hodnota zo st.secrets, inak z premennej prostredia. Hodnotu nikdy nevypisujeme."""
    try:
        import streamlit as st

        hodnota = st.secrets.get(nazov)
        if hodnota:
            return str(hodnota)
    except Exception:  # mimo Streamlitu alebo bez secrets.toml
        pass
    hodnota = os.environ.get(nazov)
    return hodnota or None


def je_fake() -> bool:
    return os.environ.get("LIEKRADAR_FAKE_LLM", "").strip() in {"1", "true", "True", "ano"}


def nazov_modelu() -> str:
    if je_fake():
        return "fake-llm (LIEKRADAR_FAKE_LLM=1)"
    return _nastavenie("GEMINI_MODEL") or PREDVOLENY_MODEL


def nazov_zalozneho_modelu() -> str:
    if je_fake():
        return "fake-llm-zalozny"
    return _nastavenie("GEMINI_MODEL_FALLBACK") or PREDVOLENY_ZALOZNY_MODEL


def _pockaj_na_slot() -> None:
    """Najviac LIMIT_ZA_MINUTU volaní za posledných 60 sekúnd."""
    while True:
        with _zamok:
            teraz = time.monotonic()
            while _casy_volani and teraz - _casy_volani[0] > 60:
                _casy_volani.popleft()
            if len(_casy_volani) < LIMIT_ZA_MINUTU:
                _casy_volani.append(teraz)
                return
            cakaj = 60 - (teraz - _casy_volani[0]) + 0.5
        time.sleep(max(cakaj, 0.5))


def _je_429(chyba: Exception) -> bool:
    text = f"{type(chyba).__name__} {chyba}"
    return "RateLimit" in type(chyba).__name__ or "429" in text or "RESOURCE_EXHAUSTED" in text


def _je_pretazeny(chyba: Exception) -> bool:
    text = str(chyba)
    return "503" in text or "UNAVAILABLE" in text or "overloaded" in text.lower()


def _cakanie_z_chyby(chyba: Exception) -> float:
    """Koľko sekúnd čakať podľa odpovede servera (retryDelay / 'retry in Xs'), najviac 60 s."""
    text = str(chyba)
    nalez = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", text) or re.search(
        r"retry in (\d+(?:\.\d+)?)\s*s", text, re.IGNORECASE)
    sekundy = float(nalez.group(1)) if nalez else 30.0
    return min(max(sekundy, 2.0), CAKANIE_PRI_429_MAX_S)


class LLM:
    """Jeden objekt na jednu otázku: počíta volania a drží rozpočet MAX_VOLANI_NA_OTAZKU."""

    def __init__(self) -> None:
        self.fake = je_fake()
        self.model = nazov_modelu()                 # hlavný model
        self.zalozny_model = nazov_zalozneho_modelu()
        self.aktivny_model = self.model             # po 503 sa prepne na záložný (do konca otázky)
        self.posledny_model = self.model            # model, ktorý spravil (alebo skúšal) posledné volanie
        self.pouzite_modely: list[str] = []         # modely, ktoré úspešne odpovedali, v poradí
        self.pocet_volani = 0    # úspešné volania (rozpočet MAX_VOLANI_NA_OTAZKU)
        self.pocet_pokusov = 0   # všetky požiadavky na Gemini vrátane opakovaní po 429/503
        self._fake_503_od = int(os.environ.get("LIEKRADAR_FAKE_503", "0") or 0) if self.fake else 0
        self._klienti: dict = {}
        self._kluc: str | None = None
        if not self.fake:
            self._kluc = _nastavenie("GEMINI_API_KEY")
            if not self._kluc:
                raise LLMChyba("Chýba GEMINI_API_KEY (v .streamlit/secrets.toml alebo v premennej prostredia). "
                               "Na test bez kľúča nastavte LIEKRADAR_FAKE_LLM=1.")

    # -- verejné metódy -----------------------------------------------------------------

    def _fake_volanie(self):
        """Režim LIEKRADAR_FAKE_LLM: započíta volanie, prípadne simuluje 503 a prepnutie na záložný model."""
        if self._fake_503_od and self.pocet_volani + 1 >= self._fake_503_od and self.aktivny_model == self.model:
            self.pocet_pokusov += 2  # hlavný model: pokus + opakovanie, oba 503
            self.aktivny_model = self.zalozny_model
        self.pocet_volani += 1
        self.pocet_pokusov += 1
        self._zaznamenaj_model(self.aktivny_model)

    def _zaznamenaj_model(self, model: str) -> None:
        self.posledny_model = model
        if model not in self.pouzite_modely:
            self.pouzite_modely.append(model)

    def text(self, system: str, vstup: str, fake: str) -> str:
        """Voľný text (markdown). `fake` je odpoveď pre režim LIEKRADAR_FAKE_LLM."""
        if self.fake:
            self._fake_volanie()
            return fake
        odpoved = self._zavolaj(lambda klient: klient.invoke(self._spravy(system, vstup)))
        return (odpoved.text or "").strip()

    def strukturovane(self, system: str, vstup: str, schema: type[BaseModel], fake: BaseModel) -> BaseModel:
        """Štruktúrovaný výstup podľa Pydantic schémy."""
        if self.fake:
            self._fake_volanie()
            return fake
        odpoved = self._zavolaj(
            lambda klient: klient.with_structured_output(schema).invoke(self._spravy(system, vstup)))
        if odpoved is None:
            raise LLMChyba("Model nevrátil výstup v požadovanej štruktúre.")
        return odpoved if isinstance(odpoved, schema) else schema.model_validate(odpoved)

    # -- interné ----------------------------------------------------------------------

    @staticmethod
    def _spravy(system: str, vstup: str):
        from langchain_core.messages import HumanMessage, SystemMessage

        return [SystemMessage(content=system), HumanMessage(content=vstup)]

    def _klient_gemini(self, model: str):
        if model not in self._klienti:
            from langchain_google_genai import ChatGoogleGenerativeAI

            # max_retries=1 = jeden pokus; opakovanie pri 429/503 riadime sami, aby sa limit neminul potichu
            self._klienti[model] = ChatGoogleGenerativeAI(model=model, google_api_key=self._kluc,
                                                          max_retries=1, timeout=120)
        return self._klienti[model]

    def _bez_kluca(self, text: str) -> str:
        if self._kluc:
            text = text.replace(self._kluc, "***")
        return re.sub(r"key=[A-Za-z0-9_\-]+", "key=***", text)

    def _zavolaj(self, volanie):
        if self.pocet_volani >= MAX_VOLANI_NA_OTAZKU:
            raise LLMChyba(f"Prekročený rozpočet {MAX_VOLANI_NA_OTAZKU} volaní modelu na jednu otázku.")
        while True:
            model = self.aktivny_model
            try:
                odpoved = self._skus_model(model, volanie)
            except _Pretazeny:
                if model != self.zalozny_model:  # hlavný model je preťažený -> záložný do konca otázky
                    self.aktivny_model = self.zalozny_model
                    continue
                raise LLMChyba(f"Modely {self.model} aj {self.zalozny_model} sú teraz preťažené (Google vrátil "
                               "503). Skúste to o niekoľko minút.") from None
            self.pocet_volani += 1  # rozpočet otázky počíta úspešné volania, opakovania po 429/503 navyše
            self._zaznamenaj_model(model)
            return odpoved

    def _skus_model(self, model: str, volanie):
        """Jeden model: pokus a pri 429/503 jedno opakovanie. Pri trvalom 503 vyhodí _Pretazeny."""
        klient = self._klient_gemini(model)
        for pokus in (1, 2):
            _pockaj_na_slot()
            self.pocet_pokusov += 1
            self.posledny_model = model
            try:
                return volanie(klient)
            except Exception as chyba:  # noqa: BLE001 – chybu prekladáme na zrozumiteľnú správu
                if _je_429(chyba) and pokus == 1:
                    time.sleep(_cakanie_z_chyby(chyba))
                    continue
                if _je_pretazeny(chyba) and pokus == 1:  # 503: model je dočasne preťažený
                    time.sleep(CAKANIE_PRI_503_S)
                    continue
                if _je_429(chyba):
                    raise LLMChyba("Gemini odmietol požiadavku pre limit bezplatnej úrovne (15 požiadaviek za "
                                   "minútu, 500 za deň). Skúste to o minútu, prípadne zajtra.") from None
                if _je_pretazeny(chyba):
                    raise _Pretazeny() from None
                popis = self._bez_kluca(str(chyba))[:300]
                raise LLMChyba(f"Volanie modelu {model} zlyhalo ({type(chyba).__name__}): {popis}") from None
        raise LLMChyba(f"Volanie modelu {model} zlyhalo.")


class _Pretazeny(Exception):
    """Model vrátil 503 aj po opakovaní."""
