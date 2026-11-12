"""LiekRadar – Streamlit aplikácia.

Zatiaľ len kostra: tri časti, ktoré budeme postupne napĺňať.
"""

import streamlit as st

st.set_page_config(page_title="LiekRadar", page_icon="💊", layout="wide")

st.title("LiekRadar")
st.caption("Včasné varovanie pred výpadkami liekov v ČR a SR")

with st.sidebar:
    st.header("Pre koho")
    persona = st.radio(
        "Vyber pohľad",
        ["Výrobca generík / distribútor", "Nákupca lekárenskej siete"],
    )
    try:
        has_key = bool(st.secrets.get("GEMINI_API_KEY"))
    except Exception:  # secrets.toml vôbec neexistuje
        has_key = False
    if not has_key:
        st.warning("Chýba GEMINI_API_KEY v secrets. Agenti zatiaľ nepobežia.")

tab_prehlad, tab_detail, tab_otazky = st.tabs(
    ["Prehľad rizík ČR vs SR", "Detail lieku", "Opýtaj sa LiekRadaru"]
)

with tab_prehlad:
    st.info("Sem príde zoznam liekov s najvyšším rizikom výpadku, vedľa seba ČR a SR.")

with tab_detail:
    st.info("Sem príde časová os výpadkov v oboch krajinách, náhrady a konkurenti.")

with tab_otazky:
    st.info(f"Sem príde okno na otázky pre pohľad: {persona}. Ukážeme aj, ako si agenti odovzdávajú prácu.")
