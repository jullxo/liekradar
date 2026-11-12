"""Multiagentný systém LiekRadar (LangGraph).

Graf kopíruje cyklus competitive intelligence:
    orchestrátor (plánovanie) -> zber -> analytik (analýza) -> reportér (šírenie)

Zatiaľ kostra bez volania modelu: každý agent len zapíše, čo by robil.
Gemini doplníme, keď budú hotové nástroje v agents/tools.py.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class LiekRadarState(TypedDict, total=False):
    otazka: str          # otázka používateľa
    persona: str         # "vyrobca" alebo "lekaren"
    plan: list[str]      # kroky od orchestrátora
    data: dict           # čo zozbierali zberné agenty
    analyza: dict        # výsledky analytika
    brief: str           # výstup reportéra
    priebeh: list[str]   # záznam komunikácie agentov (zobrazíme v aplikácii)


def orchestrator(state: LiekRadarState) -> LiekRadarState:
    plan = ["zber CZ", "zber SK", "analýza rizika"]
    return {"plan": plan, "priebeh": [f"Orchestrátor: plán {plan}"]}


def zber(state: LiekRadarState) -> LiekRadarState:
    return {"data": {}, "priebeh": state["priebeh"] + ["Zberné agenty: dáta CZ a SK načítané"]}


def analytik(state: LiekRadarState) -> LiekRadarState:
    return {"analyza": {}, "priebeh": state["priebeh"] + ["Analytik: skóre rizika vyhodnotené"]}


def reporter(state: LiekRadarState) -> LiekRadarState:
    brief = f"Brief pre: {state.get('persona', '?')} (zatiaľ prázdny)"
    return {"brief": brief, "priebeh": state["priebeh"] + ["Reportér: brief pripravený"]}


def build_graph():
    g = StateGraph(LiekRadarState)
    g.add_node("orchestrator", orchestrator)
    g.add_node("zber", zber)
    g.add_node("analytik", analytik)
    g.add_node("reporter", reporter)
    g.add_edge(START, "orchestrator")
    g.add_edge("orchestrator", "zber")
    g.add_edge("zber", "analytik")
    g.add_edge("analytik", "reporter")
    g.add_edge("reporter", END)
    return g.compile()


if __name__ == "__main__":
    vysledok = build_graph().invoke({"otazka": "Ktoré antibiotiká sú ohrozené?", "persona": "lekaren"})
    for krok in vysledok["priebeh"]:
        print(krok)
    print(vysledok["brief"])
