from langgraph.graph import END, StateGraph

from config.llm_providers import warm_up_embedding_model
from core.logger import get_logger
from graph.nodes.generate import generate_answer_node
from graph.nodes.refine import refine_node
from graph.nodes.retrieve import retrieval_node
from graph.nodes.router import router_node
from graph.nodes.validate import validate_node
from graph.nodes.web_search import web_search_node
from graph.state import GraphState

logger = get_logger(__name__)

MAX_RETRIEVAL_ATTEMPTS = 3
"""Max number of retrieve -> validate round trips for a single turn, before
giving up on the local sources and falling back to a web search."""

NODE_LABELS = {
    "router": "Understanding your question",
    "refine": "Refining your query",
    "web_search": "Searching the web",
    "retrieve": "Searching sources",
    "validate": "Checking the sources",
    "generate": "Writing answer",
}
"""Human-friendly labels for each node, used to stream real-time progress
updates to the frontend as the agent moves through the graph."""


def route_after_router(state: GraphState):
    """After the router decides the intent, general knowledge questions go
    straight to generation, everything else first goes through the refine
    step to make sure the query is well-formed for searching."""
    if state["intent"] == "general_knowledge":
        return "generate"
    return "refine"


def route_after_refine(state: GraphState):
    """After refining the query, send it to whichever search the router
    picked."""
    if state["intent"] == "web_search":
        return "web_search"
    return "retrieve"


def post_val_routing(state: GraphState):
    """
    After validating the retrieved context: proceed to generation if it is
    enough, retry retrieval with the validator's optimized query if there
    are attempts left, or fall back to a web search once
    MAX_RETRIEVAL_ATTEMPTS is reached.
    """
    if state["is_valid"]:
        return "generate"

    attempts = state.get("retrieval_attempts", 0)
    if attempts < MAX_RETRIEVAL_ATTEMPTS:
        logger.info("Context insufficient, retrying retrieval (attempt %d)", attempts + 1)
        return "retrieve"

    logger.info("Max retrieval attempts (%d) reached, falling back to web search", attempts)
    return "web_search"


workflow = StateGraph(GraphState)

workflow.add_node("router", router_node)
workflow.add_node("refine", refine_node)
workflow.add_node("retrieve", retrieval_node)
workflow.add_node("validate", validate_node)
workflow.add_node("web_search", web_search_node)
workflow.add_node("generate", generate_answer_node)

workflow.set_entry_point("router")

workflow.add_conditional_edges(
    "router", route_after_router, {"refine": "refine", "generate": "generate"}
)

workflow.add_conditional_edges(
    "refine", route_after_refine, {"web_search": "web_search", "retrieve": "retrieve"}
)

workflow.add_edge("retrieve", "validate")

workflow.add_conditional_edges(
    "validate",
    post_val_routing,
    {"generate": "generate", "retrieve": "retrieve", "web_search": "web_search"},
)

workflow.add_edge("web_search", "generate")
workflow.add_edge("generate", END)

app = workflow.compile()

if __name__ == "__main__":
    warm_up_embedding_model()
    test_input = {
        "query": "Under IFRS, what criteria must be met for an asset to be recognized on the statement of financial position?"
    }

    try:
        final_state = app.invoke(test_input)  # type: ignore
        print("Answer:", final_state["answer"])
    except Exception as e:
        print(f"Execution Error: {e}")
