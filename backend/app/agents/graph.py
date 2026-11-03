from langgraph.graph import END, StateGraph

from app.agents.consent_agent import consent_node
from app.agents.intake_agent import intake_node
from app.agents.kim_agent import kim_node
from app.agents.scheduling_agent import scheduling_node
from app.agents.state import IntakeState

NODES = {
    "IntakeAgent": "intake",
    "ConsentAgent": "consent",
    "SchedulingAgent": "scheduling",
    "KIMAgent": "kim",
}


def route_next_step(state: IntakeState) -> str:
    """Maps the `next_agent` decision of the last agent to the next graph node."""
    target = state.get("next_agent", "END")
    # ConsentAgent pointing at itself means: waiting for IAM approval -> end this run
    if state.get("iam_required"):
        return END
    return NODES.get(target, END)


def _entry(state: IntakeState) -> str:
    """Resumed run: intake already done and consent now granted -> skip straight ahead."""
    if state.get("triage_score") and state.get("consent_granted"):
        return "scheduling"
    return "intake"


def build_graph():
    g = StateGraph(IntakeState)
    g.add_node("intake", intake_node)
    g.add_node("consent", consent_node)
    g.add_node("scheduling", scheduling_node)
    g.add_node("kim", kim_node)

    targets = {*NODES.values(), END}
    g.set_conditional_entry_point(_entry, {"intake": "intake", "scheduling": "scheduling"})
    for name in ("intake", "consent"):
        g.add_conditional_edges(name, route_next_step, {t: t for t in targets})
    g.add_edge("scheduling", "kim")
    g.add_edge("kim", END)
    return g.compile()


intake_graph = build_graph()
