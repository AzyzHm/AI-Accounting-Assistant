import json

from config.models import getResponseFromLLM
from config.prompts import router_prompt
from core.logger import get_logger
from graph.nodes.history_utils import format_history
from graph.state import GraphState, HistoryTurn

logger = get_logger(__name__)

VALID_INTENTS = {"general_knowledge", "web_search", "retrieve"}


def route_query(
    user_query: str, history: list[HistoryTurn] | None = None
) -> tuple[str, str | None]:
    """
    Routes the user query using an LLM to decide the intent (general_knowledge,
    web_search, or retrieve) and, when relevant, the subject category used to
    filter the local knowledge base.
    """
    history_block = format_history(history or []) or "(no prior turns)"
    user_prompt = f"CONVERSATION HISTORY:\n{history_block}\n\nUSER QUERY: {user_query}"

    try:
        response = getResponseFromLLM(router_prompt, user_prompt, 0.0)
        if response.text is None:
            raise ValueError("LLM response is empty")

        result = json.loads(response.text)
        intent = result.get("intent", "general_knowledge")
        if intent not in VALID_INTENTS:
            intent = "general_knowledge"

        category = result.get("category") if intent == "retrieve" else None
        return intent, category

    except Exception as e:
        logger.error("Router Error: %s", e)
        return "general_knowledge", None


def router_node(state: GraphState):
    intent, category = route_query(state["query"], state.get("history"))
    logger.info("Router decided intent=%s category=%s", intent, category)
    return {"intent": intent, "category": category}
