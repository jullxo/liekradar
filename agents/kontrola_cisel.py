"""Kontrola čísel v správe proti výsledkom nástrojov (časť kritika, bez modelu).

Overuje tri druhy údajov, pri ktorých model najčastejšie zamieňa čísla:
1. skóre rizika – každé „skóre N“ sa musí zhodovať so skóre lieku z top_rizikove, ku ktorému patrí
   (liek spomenutý naposledy pred skóre v tom istom riadku, podľa kódu alebo názvu);
2. kódy liekov – každý kód v správe musí byť vo výsledkoch nástrojov a balenie pri ňom
   (napr. „20x80 ml/240 mg“) sa musí zhodovať s názvom a doplnkom lieku v dátach;
3. časový posun – počty vĺn v ČR a SR, dni posunu a počty prípadov pri látke musia sedieť
   s výsledkom posun_latky.

Každý problém je jedna veta v tvare „… v správe X, v dátach Y“, aby ju reportér vedel opraviť.
"""

from __future__ import annotations

import re
import unicodedata

# Kód lieku: SK napr. 76566 alebo 3334D, CZ 7 číslic. Čisto číselný kód berieme len v kontexte
# (v `...`, po slove kód, na začiatku zátvorky), aby sa za kód nepovažovali počty balení.
_KOD_ALNUM = r"\d{3,6}[A-Z]"
_KOD = rf"(?:\d{{5,7}}|{_KOD_ALNUM})"
_KOD_VZORY = [
    re.compile(rf"`({_KOD})`"),
    re.compile(rf"\bk[óo]d\w*\s*:?\s*`?({_KOD})\b`?", re.IGNORECASE),
    re.compile(rf"\(\s*({_KOD})\s*[,)]"),
    re.compile(rf"(?<![\w/.,-])({_KOD_ALNUM})(?![\w/.,-])"),
]
_KOD_POKRACOVANIE = re.compile(rf"\s*(?:,|a|alebo)\s*`?({_KOD})\b`?")

_BALENIE = re.compile(
    r"\d+(?:[,.]\d+)?\s*x\s*\d+(?:[,.]\d+)?(?:\s*x\s*\d+(?:[,.]\d+)?)?\s*(?:ml|mg|g|cm|ks|l)\b"
    r"(?:\s*/\s*\d+(?:[,.]\d+)?\s*(?:mg|g|ml|m?l?d|iu|mcg|µg)\b)?", re.IGNORECASE)

_SKORE = re.compile(
    r"skór\w*(?:\s+(?:rizika|výpadku|modelu|je|na|úrovni|hodnotou|bodov|v[0-2]))*\s*[:=]?\s*"
    r"(\d+(?:[,.]\d+)?)(?!\s*[–-]\s*\d)(\s*(?:mg|ml|g|mcg|%)\b)?", re.IGNORECASE)

_POSUN_KONTEXT = re.compile(r"posun|neskôr|skôr|súbe|súčasn|predchádz|vĺn|vln|vlny|vlna", re.IGNORECASE)
_VLNY = re.compile(r"(\d+)\s+(?:vĺn\w*\s+|vln\w*\s+)?(?:výpadkov\s+)?(?:v|na)\s+(ČR|SR|CZ|SK|Česk\w*|Slovensk\w*)")
_DNI = re.compile(r"(\d+)\s*(?:[–-]|až)\s*(\d+)\s*d[nň]\w*|(\d+)\s*d[nň]\w*", re.IGNORECASE)
_PRIPADY = re.compile(r"(\d+)\s+(?:prípad\w*|dvojic\w*)", re.IGNORECASE)


def _bez_diakritiky(text: str) -> str:
    """Malé písmená bez diakritiky; dĺžka textu sa nemení, aby sedeli pozície v pôvodnom riadku."""
    return "".join((unicodedata.normalize("NFKD", c)[:1] or c).lower() for c in str(text))


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).lower().replace(",", ".")


def _cislo(text: str) -> float:
    return float(text.replace(",", "."))


# ---------------------------------------------------------------------------
# Index faktov z výsledkov nástrojov
# ---------------------------------------------------------------------------

def index_dat(data: dict) -> dict:
    """Z výsledkov nástrojov vytiahne skóre, kódy liekov s balením a výsledky posun_latky."""
    skore_kod: dict[str, int] = {}          # kód -> skóre (top_rizikove)
    skore_nazov: dict[str, set] = {}        # prvé slovo názvu -> skóre (top_rizikove)
    nazov_kod: dict[str, str] = {}          # kód -> názov
    lieky: dict[str, str | None] = {}       # kód -> „názov + doplnok“ (None = balenie nepoznáme)
    posun: list[dict] = []
    for z in data.values():
        v = z.get("vysledok")
        if not isinstance(v, dict):
            continue
        nastroj = z.get("nastroj")
        zaznamy = v.get("zaznamy", [])
        if nastroj == "top_rizikove":
            for r in zaznamy:
                kod = str(r.get("kod"))
                skore_kod[kod] = r.get("skore")
                nazov_kod[kod] = r.get("nazov") or ""
                lieky[kod] = f"{r.get('nazov') or ''} {r.get('doplnok') or ''}"
                slovo = _prve_slovo(r.get("nazov"))
                if slovo:
                    skore_nazov.setdefault(slovo, set()).add(r.get("skore"))
                for dalsi in re.findall(_KOD, str(r.get("dalsie_kody") or "")):
                    lieky.setdefault(dalsi, None)
        elif nastroj == "nahrady":
            for r in zaznamy:
                kod = str(r.get("kod"))
                lieky[kod] = f"{r.get('nazov') or ''} {r.get('doplnok') or ''}"
                nazov_kod.setdefault(kod, r.get("nazov") or "")
            p = v.get("povodny_liek")
            if p:
                lieky.setdefault(str(p["kod"]), f"{p.get('nazov') or ''} {p.get('doplnok') or ''}")
        elif nastroj == "detail_latky":
            for info in (v.get("krajiny") or {}).values():
                for r in (info.get("teraz_vo_vypadku") or []) + (info.get("ohlasene_vypadky") or []):
                    lieky.setdefault(str(r.get("kod")), None)
        elif nastroj == "posun_latky":
            posun.append(v)
    return {"skore_kod": skore_kod, "skore_nazov": skore_nazov, "nazov_kod": nazov_kod,
            "lieky": lieky, "posun": posun}


def _prve_slovo(nazov) -> str:
    slova = re.findall(r"[^\W\d_]{4,}", _bez_diakritiky(nazov or ""))
    return slova[0] if slova else ""


def _kody_v_riadku(riadok: str) -> list[tuple[int, str]]:
    """Pozície a kódy liekov v riadku (aj zoznam po „kódy `0943F`, `0940F`“)."""
    najdene: dict[int, str] = {}
    for vzor in _KOD_VZORY:
        for m in vzor.finditer(riadok):
            najdene.setdefault(m.start(1), m.group(1))
            if vzor is _KOD_VZORY[1]:
                koniec = m.end()
                while (p := _KOD_POKRACOVANIE.match(riadok, koniec)):
                    najdene.setdefault(p.start(1), p.group(1))
                    koniec = p.end()
    return sorted(najdene.items())


def _zatvorka(riadok: str, pozicia: int) -> tuple[int, int] | None:
    """Rozsah najvnútornejšej okrúhlej zátvorky, v ktorej je pozícia (alebo None)."""
    zasobnik, rozsahy = [], []
    for i, c in enumerate(riadok):
        if c == "(":
            zasobnik.append(i)
        elif c == ")" and zasobnik:
            rozsahy.append((zasobnik.pop(), i))
    vnutri = [r for r in rozsahy if r[0] < pozicia < r[1]]
    return min(vnutri, key=lambda r: r[1] - r[0]) if vnutri else None


# ---------------------------------------------------------------------------
# Kontroly
# ---------------------------------------------------------------------------

def _kontrola_skore(riadok: str, idx: dict) -> list[str]:
    problemy = []
    if not idx["skore_kod"]:
        return problemy
    zmienky = [(p, ("kod", k)) for p, k in _kody_v_riadku(riadok) if k in idx["skore_kod"]]
    bez = _bez_diakritiky(riadok)
    for slovo in idx["skore_nazov"]:
        for m in re.finditer(rf"\b{re.escape(slovo)}", bez):
            zmienky.append((m.start(), ("nazov", slovo)))
    zmienky.sort()
    vsetky_skore = {s for s in idx["skore_kod"].values()}
    for m in _SKORE.finditer(riadok):
        hodnota, jednotka = m.group(1), (m.group(2) or "").strip()
        pred = [z for z in zmienky if z[0] < m.start()]
        druh, kluc = pred[-1][1] if pred else (None, None)
        if druh == "kod":
            ocakavane, komu = {idx["skore_kod"][kluc]}, f"{idx['nazov_kod'].get(kluc, '')} ({kluc})"
        elif druh == "nazov":
            ocakavane, komu = idx["skore_nazov"][kluc], kluc.upper()
        else:
            ocakavane, komu = vsetky_skore, None
        v_sprave = f"skóre {hodnota}{' ' + jednotka if jednotka else ''}"
        if jednotka and jednotka != "%":  # percentá rieši pravidlo o skóre v percentách
            dalej = f"pri {komu} " if komu else ""
            problemy.append(f"Skóre {dalej}nemá jednotku: v správe „{v_sprave}“, v dátach skóre "
                            f"{', '.join(map(str, sorted(ocakavane)))} (body 0–100).")
        elif _cislo(hodnota) not in {float(s) for s in ocakavane if s is not None}:
            if komu:
                problemy.append(f"Skóre pri {komu}: v správe {hodnota}, v dátach "
                                f"{', '.join(map(str, sorted(ocakavane)))} (top_rizikove).")
            else:
                problemy.append(f"Skóre {hodnota} nepatrí žiadnemu lieku z top_rizikove "
                                f"(v dátach: {', '.join(map(str, sorted(vsetky_skore)))}).")
    return problemy


def _kontrola_kodov(riadok: str, idx: dict) -> list[str]:
    problemy = []
    kody = _kody_v_riadku(riadok)
    for _, kod in kody:
        if kod not in idx["lieky"]:
            problemy.append(f"Kód lieku {kod}: v správe je, vo výsledkoch nástrojov nie je.")
    znamych = [(p, k) for p, k in kody if idx["lieky"].get(k)]
    if not znamych:
        return problemy
    for m in _BALENIE.finditer(riadok):
        zatvorka = _zatvorka(riadok, m.start())
        v_zatvorke = [(p, k) for p, k in znamych if zatvorka and zatvorka[0] < p < zatvorka[1]]
        kandidati = v_zatvorke or [(p, k) for p, k in znamych if abs(p - m.start()) <= 80]
        if not kandidati:
            continue
        _, kod = min(kandidati, key=lambda pk: abs(pk[0] - m.start()))
        if _norm(m.group(0)) in _norm(idx["lieky"][kod]):
            continue
        ine = [k for k, t in idx["lieky"].items() if t and k != kod and _norm(m.group(0)) in _norm(t)]
        dovetok = f" ({m.group(0)} je balenie kódu {', '.join(ine)})" if ine else ""
        v_datach = re.sub(r"\s+", " ", idx["lieky"][kod]).strip()
        problemy.append(f"Balenie pri kóde {kod}: v správe „{m.group(0)}“, v dátach „{v_datach}“{dovetok}.")
    return problemy


def _kontrola_posunu(riadok: str, idx: dict) -> list[str]:
    problemy = []
    if not idx["posun"] or not _POSUN_KONTEXT.search(riadok):
        return problemy
    bez = _bez_diakritiky(riadok)
    zmienky = []
    for p in idx["posun"]:
        kmen = _bez_diakritiky(p.get("nazov") or "")[:6].replace("y", "i")
        for vzor in {p.get("atc", "").lower(), kmen}:
            if vzor:
                zmienky += [(m.start(), p) for m in re.finditer(re.escape(vzor), bez.replace("y", "i"))]
    zmienky.sort(key=lambda z: z[0])
    for i, (zaciatok, p) in enumerate(zmienky):
        koniec = next((z[0] for z in zmienky[i + 1:] if z[1] is not p), len(riadok))
        usek = riadok[zaciatok:koniec]
        if not _POSUN_KONTEXT.search(usek):
            continue
        meno = f"{p.get('nazov')} ({p.get('atc')})"
        if re.search(r"vĺn|vln|vlny", usek, re.IGNORECASE):
            for m in _VLNY.finditer(usek):
                krajina = "CZ" if m.group(2).lower().startswith(("č", "c")) else "SK"
                ocakavane = p.get("vlny_cz" if krajina == "CZ" else "vlny_sk")
                if ocakavane is not None and int(m.group(1)) != ocakavane:
                    problemy.append(f"Vlny výpadkov {meno} v {'ČR' if krajina == 'CZ' else 'SR'}: v správe "
                                    f"{m.group(1)}, v dátach {ocakavane} (posun_latky).")
        rozdiely = sorted({abs(d["rozdiel_dni_sk_minus_cz"]) for d in p.get("dvojice_do_60_dni") or []})
        povolene_dni = set(rozdiely) | {7, 8, 60}
        for m in _DNI.finditer(usek):
            cisla = [int(c) for c in m.groups() if c]
            zle = [c for c in cisla if c not in povolene_dni]
            if zle:
                problemy.append(f"Posun {meno}: v správe {m.group(0).strip()}, v dátach rozdiely "
                                f"{', '.join(map(str, rozdiely)) or 'žiadne'} dní (posun_latky).")
        povolene_pripady = {p.get("sucasne_do_7_dni"), p.get("cr_skor_8_60_dni"), p.get("sr_skor_8_60_dni"),
                            len(p.get("dvojice_do_60_dni") or [])}
        for m in _PRIPADY.finditer(usek):
            if int(m.group(1)) not in povolene_pripady:
                problemy.append(f"Počet prípadov pri {meno}: v správe {m.group(1)}, v dátach súčasne do 7 dní "
                                f"{p.get('sucasne_do_7_dni')}, ČR skôr {p.get('cr_skor_8_60_dni')}, SR skôr "
                                f"{p.get('sr_skor_8_60_dni')} (posun_latky).")
    return problemy


def kontrola_cisel(brief: str, data: dict) -> list[str]:
    """Všetky nezhody čísel v správe s výsledkami nástrojov (bez duplicít, v poradí výskytu)."""
    idx = index_dat(data)
    problemy: list[str] = []
    for riadok in brief.splitlines():
        if riadok.lstrip().startswith("#"):
            continue
        for p in _kontrola_skore(riadok, idx) + _kontrola_kodov(riadok, idx) + _kontrola_posunu(riadok, idx):
            if p not in problemy:
                problemy.append(p)
    return problemy
