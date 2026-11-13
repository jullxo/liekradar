"""LiekRadar – Streamlit aplikácia.

Spustenie lokálne (z priečinka liekradar):
    streamlit run app.py

Čísla počítajú funkcie z pipeline/analytika.py nad dátami v data/processed.
Záložka „Opýtaj sa LiekRadaru“ volá agentov z agents/graph.py (funkcia spusti), keď budú hotoví.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="LiekRadar", page_icon="💊", layout="wide")

DATA = Path("data/processed")
METODIKA = Path("vault/metodika")
MANIFEST = Path("vault/manifest_zdrojov.csv")

if not (DATA / "lieky.parquet").exists():
    st.title("LiekRadar")
    st.error("Chýbajú dáta v `data/processed`. Spusti najprv `python -m pipeline.run_pipeline`.")
    st.stop()

from pipeline import analytika as an  # noqa: E402  (až po kontrole dát)
from pipeline.kiq2_posun import ATC_SKUPINY  # noqa: E402

KRAJINY = {"CZ": "Česko", "SK": "Slovensko"}
PERSONY = {"Nákupca lekárenskej siete": "lekaren", "Výrobca generík / distribútor": "vyrobca"}
UPOZORNENIE = ("Skóre rizika nie je pravdepodobnosť. LiekRadar nie je lekárske odporúčanie; "
               "zámenu inej účinnej látky môže urobiť len lekár.")
MODRA, SVETLA = "#24578f", "#8fb3dc"

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1280px;}
h1, h2, h3, h4 {color: #24578f !important;}
.lr-hero {position: relative; overflow: hidden; border: 1px solid #dce8f4; border-radius: 22px;
          padding: 24px 36px; margin-bottom: 16px; background: #ffffff;}
.lr-hero::before {content: ""; position: absolute; width: 340px; height: 340px; border-radius: 50%;
                  background: #dce8f4; right: -90px; top: -150px;}
.lr-hero::after {content: ""; position: absolute; width: 150px; height: 150px; border-radius: 50%;
                 background: #dce8f4; right: 230px; bottom: -110px; opacity: .7;}
.lr-hero > * {position: relative; z-index: 1;}
.lr-kicker {font-size: .78rem; letter-spacing: .12em; text-transform: uppercase; color: #24578f;
            font-weight: 600; margin-bottom: .2rem;}
.lr-title {font-size: 2.6rem; font-weight: 700; color: #24578f; line-height: 1.1; margin: .15rem 0;}
.lr-sub {font-size: 1.05rem; font-style: italic; color: #24578f; margin: .3rem 0 0;}
.lr-cards {display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: 4px 0 22px;}
.lr-card {background: #f3f6fa; border: 1px solid #dce8f4; border-radius: 16px; padding: 16px 18px;}
.lr-card .v {font-size: 1.9rem; font-weight: 700; color: #24578f; line-height: 1.1;}
.lr-card .l {font-size: .8rem; color: #4a5b72; margin-top: 4px;}
.lr-sec {margin: .4rem 0 .6rem;}
.lr-sec h3 {margin: 0 0 .2rem; font-size: 1.45rem;}
.lr-sec p {color: #4a5b72; font-size: .92rem; margin: 0;}
.lr-sec.maly {margin-top: 1.2rem;}
.lr-sec.maly h3 {font-size: 1.12rem;}
.lr-mini {display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 6px;}
.lr-mini > div {background: #f3f6fa; border: 1px solid #dce8f4; border-radius: 12px; padding: 10px 12px;}
.lr-mini .v {font-size: 1.45rem; font-weight: 700; color: #24578f; line-height: 1.15;}
.lr-mini .l {font-size: .72rem; color: #4a5b72;}
.lr-pill {display: inline-block; background: #24578f; color: #fff; font-size: .72rem; font-weight: 700;
          border-radius: 999px; padding: 2px 10px; margin-right: 8px; vertical-align: middle;}
.lr-country {font-size: 1.15rem; font-weight: 700; color: #24578f; margin: .6rem 0 .3rem;}
.lr-note {font-size: .8rem; color: #6b7a90; border-top: 1px solid #dce8f4; padding-top: .6rem; margin-top: 1rem;}
.stTabs [data-baseweb="tab-list"] {gap: 6px; border-bottom: 1px solid #dce8f4;}
.stTabs [data-baseweb="tab"] {font-weight: 600; padding: 8px 16px; border-radius: 10px 10px 0 0;}
.stTabs [aria-selected="true"] {background: #eef4fa;}
[data-testid="stMetric"] {background: #f3f6fa; border: 1px solid #dce8f4; border-radius: 14px; padding: 12px 14px;}
[data-testid="stMetricValue"] {color: #24578f; font-weight: 700;}
[data-testid="stSidebar"] .lr-brand {font-size: 1.7rem; font-weight: 700; color: #fff; margin-bottom: 0;}
[data-testid="stSidebar"] .lr-brand-sub {font-style: italic; color: #dce8f4; font-size: .9rem;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color: #dce8f4;}
</style>
""", unsafe_allow_html=True)


def sekcia(stitok: str, nadpis: str, popis: str = "", maly: bool = False) -> None:
    """Nadpis sekcie v štýle prezentácie: malý štítok, nadpis, jednoriadkový popis."""
    trieda = "lr-sec maly" if maly else "lr-sec"
    st.markdown(f'<div class="{trieda}"><div class="lr-kicker">{stitok}</div><h3>{nadpis}</h3>'
                f'{f"<p>{popis}</p>" if popis else ""}</div>', unsafe_allow_html=True)


def karticky(polozky: list) -> None:
    """Malé karty s číslami vedľa seba: [(hodnota, popis), ...]."""
    obsah = "".join(f'<div><div class="v">{v}</div><div class="l">{l}</div></div>' for v, l in polozky)
    st.markdown(f'<div class="lr-mini">{obsah}</div>', unsafe_allow_html=True)


def krajina_nadpis(krajina: str) -> None:
    st.markdown(f'<div class="lr-country"><span class="lr-pill">{krajina}</span>{KRAJINY[krajina]}</div>',
                unsafe_allow_html=True)


def poznamka(text: str) -> None:
    st.markdown(f'<div class="lr-note">{text}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Načítanie (výsledky sa pamätajú hodinu, aby appka bola rýchla)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Počítam riziká…")
def rizikove(krajina: str, prefix: str | None, n: int) -> pd.DataFrame:
    return an.top_rizikove(krajina, prefix, n)


@st.cache_data(ttl=3600, show_spinner=False)
def detail(atc: str) -> dict:
    return an.detail_latky(atc)


@st.cache_data(ttl=3600, show_spinner=False)
def posun(atc: str) -> dict:
    return an.posun_latky(atc)


@st.cache_data(ttl=3600, show_spinner="Hľadám náhrady…")
def nahrady(krajina: str, kod: str) -> pd.DataFrame:
    return an.nahrady(krajina, kod)


@st.cache_data(ttl=3600, show_spinner="Počítam konkurentov…")
def konkurenti(prefix: str, krajina: str) -> pd.DataFrame:
    return an.konkurenti(prefix, krajina)


@st.cache_data(ttl=3600, show_spinner="Hľadám medzery na trhu…")
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
def vypadky_mesacne(atc: str) -> pd.DataFrame:
    ep = an._tab("epizody")
    ep = ep[(ep["atc"] == atc) & (ep["zaciatok"] >= an.SPOLOCNE_OD) & ~ep["planovany"]]
    if ep.empty:
        return pd.DataFrame()
    stvrtrok = ep["zaciatok"].dt.to_period("Q")
    tab = ep.groupby([stvrtrok, "krajina"]).size().unstack(fill_value=0)
    vsetky = pd.period_range(pd.Period(an.SPOLOCNE_OD, "Q"), pd.Period(an._dnes(), "Q"), freq="Q")
    tab = tab.reindex(vsetky, fill_value=0).rename(columns=KRAJINY).reindex(columns=list(KRAJINY.values()), fill_value=0)
    tab.index = [f"{p.year} Q{p.quarter}" for p in tab.index]
    tab.index.name = "štvrťrok"
    return tab


@st.cache_data(ttl=3600, show_spinner=False)
def presnost_modelu() -> dict:
    """Presnosť top 100 zo spätného testu pre každú krajinu (podľa modelu, ktorý appka používa)."""
    vysledok = {}
    for krajina in KRAJINY:
        try:
            from pipeline import kiq1_ml
            balik = kiq1_ml.nacitaj_model(krajina)
            if balik:
                vysledok[krajina] = balik["metriky"]["presnost_top"]
                continue
        except Exception:
            pass
        try:
            import json
            vysledok[krajina] = json.loads(an.VAHY_SUBOR.read_text(encoding="utf-8"))[krajina]["presnost_top"]
        except Exception:
            vysledok[krajina] = None
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
    return {
        "teraz_cz": int(vo_vypadku.get("CZ", 0)), "teraz_sk": int(vo_vypadku.get("SK", 0)),
        "rok_cz": int((rok["krajina"] == "CZ").sum()), "rok_sk": int((rok["krajina"] == "SK").sum()),
        "latky_oboch": latky_oboch,
    }


def cislo(x) -> str:
    return "—" if x is None else f"{int(x):,}".replace(",", " ")


def datum_dat() -> str:
    try:
        m = pd.read_csv(MANIFEST)
        return pd.to_datetime(m["stiahnute_utc"]).max().strftime("%d. %m. %Y")
    except Exception:
        return "?"


def percento(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{x * 100:.1f} %".replace(".", ",")


def kod_text(df: pd.DataFrame) -> pd.DataFrame:
    """Kódy liekov ako text, aby Streamlit nezmazal nuly na začiatku."""
    if "kod" in df:
        df = df.assign(kod=df["kod"].astype(str))
    return df


# ---------------------------------------------------------------------------
# Bočný panel
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<div class="lr-brand">LiekRadar</div>'
                '<div class="lr-brand-sub">Radar výpadkov liekov v ČR a SR</div>', unsafe_allow_html=True)
    st.write("")
    persona_nazov = st.radio("Pohľad", list(PERSONY))
    persona = PERSONY[persona_nazov]
    st.divider()
    st.caption(f"Dáta SÚKL a ŠÚKL stiahnuté {datum_dat()}")
    st.caption("Zdroje: [E001–E003] SÚKL, [E004–E005] ŠÚKL. Podrobnosti v záložke Metodika.")
    try:
        ma_kluc = bool(st.secrets.get("GEMINI_API_KEY"))
    except Exception:  # secrets.toml vôbec neexistuje
        ma_kluc = False

st.markdown("""
<div class="lr-hero">
  <div class="lr-kicker">4IT529 Competitive Intelligence · Team 12</div>
  <div class="lr-title">LiekRadar</div>
  <div class="lr-sub">Systém, ktorý predvída výpadky liekov v Česku a na Slovensku</div>
</div>
""", unsafe_allow_html=True)

_p, _m = prehlad(), presnost_modelu()
st.markdown(f"""
<div class="lr-cards">
  <div class="lr-card"><div class="v">{cislo(_p['teraz_cz'])}</div><div class="l">liekov teraz vo výpadku v ČR</div></div>
  <div class="lr-card"><div class="v">{cislo(_p['teraz_sk'])}</div><div class="l">liekov teraz vo výpadku v SR</div></div>
  <div class="lr-card"><div class="v">{cislo(_p['rok_cz'] + _p['rok_sk'])}</div><div class="l">nových výpadkov za 12 mesiacov (ČR + SR)</div></div>
  <div class="lr-card"><div class="v">{cislo(_p['latky_oboch'])}</div><div class="l">účinných látok sledovaných v oboch krajinách</div></div>
  <div class="lr-card"><div class="v">{percento(_m.get('CZ'))}</div><div class="l">presnosť top 100 v spätnom teste (ČR)</div></div>
</div>
""", unsafe_allow_html=True)

latky = zoznam_latok()
if "atc" not in st.session_state:
    st.session_state["atc"] = "J01CR02" if "J01CR02" in latky else next(iter(latky))


# ---------------------------------------------------------------------------
# Záložky
# ---------------------------------------------------------------------------

def zalozka_rizika() -> None:
    sekcia("KIQ1 · Včasné varovanie", "Lieky s najvyšším rizikom výpadku",
           "Lieky, ktoré dnes nie sú vo výpadku ani ho nemajú ohlásený, zoradené podľa rizika na najbližších "
           "8 týždňov. Jeden riadok = výrobca a látka.")
    c1, c2 = st.columns([3, 1])
    skupiny = {"": "Všetky skupiny"} | {k: f"{k} – {v}" for k, v in ATC_SKUPINY.items()}
    skupina = c1.selectbox("Skupina ATC", list(skupiny), format_func=skupiny.get)
    n = c2.slider("Počet liekov", 10, 50, 20, step=10)

    presnost = presnost_modelu()
    for krajina in KRAJINY:  # ČR a pod ňou SR, aby boli tabuľky široké a prehľadné
        krajina_nadpis(krajina)
        tab = rizikove(krajina, skupina or None, n)
        if tab.empty:
            st.info("Žiadne lieky so signálom rizika.")
            continue
        popis = f"Model: {tab['verzia_modelu'].iloc[0]}"
        if presnost.get(krajina):
            popis += (f" · V spätnom teste malo výpadok do 8 týždňov {percento(presnost[krajina])} "
                      "zo 100 liekov s najvyšším skóre.")
        st.caption(popis)
        tab = tab.reset_index(drop=True)
        tab.insert(0, "poradie", range(1, len(tab) + 1))
        st.dataframe(
            kod_text(tab[["poradie", "skore", "nazov", "doplnok", "latka", "drzitel", "kod"]]),
            hide_index=True, width="stretch", height=35 * (len(tab) + 1) + 3,  # celá tabuľka bez posúvania
            column_config={
                "poradie": st.column_config.NumberColumn("#", width="small"),
                "skore": st.column_config.ProgressColumn("Skóre", min_value=0, max_value=100, format="%d"),
                "nazov": "Liek", "doplnok": "Balenie", "latka": "Látka", "drzitel": "Držiteľ", "kod": "Kód",
            },
        )
        with st.expander(f"Prečo majú tieto lieky vysoké skóre? ({KRAJINY[krajina]})"):
            for r in tab.itertuples():
                st.markdown(f"**{r.poradie}. {r.nazov}** ({r.skore}): {r.dovody}")
        st.write("")
    poznamka(UPOZORNENIE)


def zalozka_latka() -> None:
    sekcia("KIQ2 · KIQ3", "Účinná látka v ČR a SR", "Výpadky v oboch krajinách, či prichádzajú spolu a čím nahradiť liek, ktorý chýba.")
    atc = st.selectbox("Účinná látka (napíš kód alebo názov)", list(latky), format_func=lambda a: latky.get(a, a), key="atc")
    d, p = detail(atc), posun(atc)
    st.markdown(f"**{atc} {d['nazov']}** · skupina {atc[0]} – {d['skupina']}")

    stlpce = st.columns(2)
    for stlpec, (krajina, nazov) in zip(stlpce, KRAJINY.items()):
        info = d["krajiny"][krajina]
        with stlpec:
            krajina_nadpis(krajina)
            karticky([(info["registrovane_balenia"], "registrovaných balení"),
                      (info["vypadky_od_2019"], "výpadkov od 2019"),
                      (info["vypadky_12m"], "za 12 mesiacov"),
                      (info["pocet_teraz_vo_vypadku"], "teraz vo výpadku")])
            median = info["median_dlzky_dni"]
            st.caption((f"Typický výpadok trvá {median:.0f} dní. " if median else "") + " ".join(info["zdroje"]))
            if info.get("dodavky"):
                dod = info["dodavky"]
                zmena = dod.get("zmena_oproti_predch_3m")
                st.caption(f"Dodávky do lekární {dod['obdobie']}: {int(dod['baleni_lekarne_3m']):,} balení".replace(",", " ")
                           + (f" ({zmena:+.0%} oproti predch. 3 mesiacom)" if zmena is not None else ""))

    graf = vypadky_mesacne(atc)
    if not graf.empty:
        sekcia("Vývoj", "Začiatky výpadkov po štvrťrokoch", maly=True)
        st.bar_chart(graf, height=240, stack=False, x_label="štvrťrok", y_label="počet výpadkov", color=[MODRA, SVETLA])

    sekcia("KIQ2", "Prichádzajú výpadky v ČR a SR spolu?", maly=True)
    text = (f"Vlny výpadkov: ČR {p['vlny_cz']}, SR {p['vlny_sk']}. Súčasne (do 7 dní) {p['sucasne_do_7_dni']}×, "
            f"ČR skôr o 8–60 dní {p['cr_skor_8_60_dni']}×, SR skôr o 8–60 dní {p['sr_skor_8_60_dni']}×.")
    lift = (p.get("skupina_atc") or {}).get("lift_sucasne")
    if lift:
        text += (f" V celej skupine {atc[0]} sú súčasné výpadky {lift:.1f}× častejšie, "
                 "než by zodpovedalo náhode.").replace(".", ",", 1)
    st.write(text)

    st.write("")
    sekcia("KIQ3", "Čo je teraz vo výpadku a čím to nahradiť", maly=True)
    stlpce = st.columns(2)
    for stlpec, (krajina, nazov) in zip(stlpce, KRAJINY.items()):
        info = d["krajiny"][krajina]
        with stlpec:
            krajina_nadpis(krajina)
            if info["ohlasene_vypadky"]:
                st.warning("Ohlásené budúce výpadky: " + "; ".join(
                    f"{o['nazov']} ({o['kod']}) od {o['od']}" for o in info["ohlasene_vypadky"]))
            if not info["teraz_vo_vypadku"]:
                st.success("Žiadny liek s touto látkou nie je vo výpadku.")
                continue
            moznosti = {o["kod"]: f"{o['nazov']} ({o['kod']}), od {o['od']}" for o in info["teraz_vo_vypadku"]}
            kod = st.selectbox("Liek vo výpadku", list(moznosti), format_func=lambda k: moznosti.get(k, k),
                               key=f"vypadok_{krajina}_{atc}")  # nový výber pri každej látke
            nah = nahrady(krajina, kod)
            if nah.empty:
                st.error("Nenašli sme náhradu s rovnakou látkou ani v rovnakej skupine.")
                continue
            if nah["typ"].iloc[0] != "rovnaká látka":
                st.warning("Liek s rovnakou látkou nie je dostupný. Ponúkame lieky z rovnakej skupiny – "
                           "zámenu môže urobiť len lekár.")
            stlpce_nah = ["nazov", "doplnok", "drzitel", "odporucil_sukl", "rovnaka_sila", "dalsie_balenia"]
            stlpce_nah += ["baleni_lekarne_3m"] if "baleni_lekarne_3m" in nah else []
            st.dataframe(nah[stlpce_nah], hide_index=True, width="stretch", column_config={
                "nazov": "Liek", "doplnok": "Balenie", "drzitel": "Držiteľ",
                "odporucil_sukl": st.column_config.CheckboxColumn("Odporučil SÚKL"),
                "rovnaka_sila": st.column_config.CheckboxColumn("Rovnaká sila"),
                "dalsie_balenia": "Ďalšie balenia", "baleni_lekarne_3m": "Dodané za 3 mes.",
            })
            st.caption(nah["zdroj"].iloc[0])
    poznamka(UPOZORNENIE)


def zalozka_trh() -> None:
    sekcia("KIQ4 · KIQ5", "Trh a konkurencia", "Kde vznikajú medzery na trhu a ako sú na tom jednotliví výrobcovia.")
    c1, c2 = st.columns([1, 2])
    krajina = c1.radio("Krajina", list(KRAJINY), format_func=KRAJINY.get, horizontal=True)
    prefix = c2.text_input("Skupina ATC pre konkurentov (napr. J01, J01CR)",
                           value=st.session_state["atc"][:5]).strip().upper()

    sekcia("KIQ5", "Trhové medzery", "Výpadok trvá aspoň 8 týždňov a látku dodávajú najviac 2 iní výrobcovia. "
           "Príležitosť pre výrobcu, riziko pre lekáreň.", maly=True)
    med = medzery(krajina, 15)
    if med.empty:
        st.info("Žiadne trhové medzery podľa prahov.")
    else:
        st.dataframe(med.drop(columns=["zdroj"]), hide_index=True, width="stretch", column_config={
            "atc": "ATC", "nazov": "Látka", "balenia_vo_vypadku": "Balení vo výpadku",
            "najdlhsi_vypadok_dni": "Najdlhší výpadok (dni)", "median_vypadku_dni": "Medián (dni)",
            "dodavatelia_dostupni": "Iní dodávatelia", "trh_baleni_mesacne": "Trh (balení/mesiac)",
        })
        st.caption(med["zdroj"].iloc[0])

    sekcia("KIQ4", f"Konkurenti v skupine {prefix}", maly=True)
    if len(prefix) < 3:
        st.info("Zadaj aspoň 3 znaky ATC kódu.")
        return
    kon = konkurenti(prefix, krajina)
    if kon.empty:
        st.info("V tejto skupine nie sú registrované lieky.")
        return
    stlpce = [c for c in ["nazov", "registrovane_balenia", "vypadky_od_2019", "vypadky_12m", "teraz_vo_vypadku",
                          "median_dlzky_dni", "podiel_dodavok_12m", "zmena_podielu_pb", "vypadkov_konkurencie"] if c in kon]
    st.dataframe(kon[stlpce].head(20), hide_index=True, width="stretch", column_config={
        "nazov": "Výrobca (skupina)", "registrovane_balenia": "Balenia", "vypadky_od_2019": "Výpadky od 2019",
        "vypadky_12m": "Za 12 mes.", "teraz_vo_vypadku": "Teraz", "median_dlzky_dni": "Medián dĺžky (dni)",
        "podiel_dodavok_12m": st.column_config.NumberColumn("Podiel na dodávkach", format="percent"),
        "zmena_podielu_pb": st.column_config.NumberColumn("Zmena podielu počas výpadkov iných (p. b.)", format="%+.1f"),
        "vypadkov_konkurencie": "Z koľkých výpadkov",
    })
    st.caption(kon["zdroj"].iloc[0] + ". Firmy sú zlúčené podľa skupiny (napr. Sandoz ČR a Sandoz SI).")


def zalozka_otazky() -> None:
    sekcia("Multiagentný systém", "Opýtaj sa LiekRadaru",
           "Orchestrátor naplánuje kroky, zberné agenty zistia fakty z dát, analytik ich vyhodnotí, "
           "reportér napíše správu vo formáte BLUF a kritik skontroluje citácie.")
    try:
        from agents.graph import spusti
    except ImportError:
        spusti = None
    if spusti is None:
        st.info("Agenti sa ešte pripravujú. Zatiaľ použi ostatné záložky – počítajú rovnaké čísla, "
                "ktoré budú agenti používať.")
        return
    if not ma_kluc:
        st.warning("Chýba GEMINI_API_KEY v secrets, agenti nepobežia.")
        return
    priklad = ("Ktoré antibiotiká na Slovensku hrozí, že budú v najbližších týždňoch chýbať, a čím ich nahradiť?"
               if persona == "lekaren" else "Kde v ČR vzniká po výpadkoch konkurencie príležitosť pre generikum?")
    otazka = st.text_area("Otázka", value=priklad, height=80)
    if st.button("Spustiť analýzu", type="primary"):
        with st.spinner("Agenti pracujú…"):
            vysledok = spusti(otazka, persona)
        st.markdown(vysledok.get("brief", ""))
        with st.expander("Ako si agenti odovzdávali prácu"):
            for krok in vysledok.get("priebeh", []):
                if isinstance(krok, dict):
                    st.markdown(f"**{krok.get('agent', '')}**: {krok.get('text', '')}")
                else:
                    st.markdown(f"- {krok}")
        st.caption("Správu vytvoril jazykový model nad číslami z nástrojov LiekRadaru. Nie je overená, "
                   "kým ju neskontroluje človek. " + UPOZORNENIE)


def zalozka_metodika() -> None:
    sekcia("Metodika", "Zdroje dát a overenie modelov")
    try:
        m = pd.read_csv(MANIFEST).sort_values("stiahnute_utc").drop_duplicates("zdroj", keep="last")
        st.markdown("**Zdroje dát** (posledné stiahnutie, hodnotenie podľa Admiralty kódu)")
        st.dataframe(m[["id", "zdroj", "admiralty", "stiahnute_utc", "url", "sha256"]].sort_values("id"),
                     hide_index=True, width="stretch")
    except Exception:
        st.info("Manifest zdrojov nie je k dispozícii.")
    for nazov in ["KIQ1 model ML.md", "KIQ1 spätný test.md", "Kontrola párovania.md"]:
        cesta = METODIKA / nazov
        if cesta.exists():
            with st.expander(nazov.removesuffix(".md")):
                st.markdown(cesta.read_text(encoding="utf-8"))


ZALOZKY = {
    "Riziká výpadkov": zalozka_rizika,
    "Látka a náhrady": zalozka_latka,
    "Trh a konkurencia": zalozka_trh,
    "Opýtaj sa LiekRadaru": zalozka_otazky,
    "Metodika": zalozka_metodika,
}
poradie = list(ZALOZKY)
if persona == "vyrobca":  # výrobcu zaujíma najprv trh, lekáreň riziká a náhrady
    poradie = ["Trh a konkurencia", "Riziká výpadkov", "Látka a náhrady", "Opýtaj sa LiekRadaru", "Metodika"]

for zalozka, nazov in zip(st.tabs(poradie), poradie):
    with zalozka:
        ZALOZKY[nazov]()
