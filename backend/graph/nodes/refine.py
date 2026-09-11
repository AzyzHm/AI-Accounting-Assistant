import json

from config.llm_providers import getResponseFromLLM
from config.prompts import refine_prompt
from core.logger import get_logger
from graph.nodes.history_utils import format_history
from graph.state import GraphState, HistoryTurn

logger = get_logger(__name__)


def refine_query(user_query: str, history: list[HistoryTurn] | None = None) -> str:
    """
    Rewrites `user_query` into a self-contained search query, resolving vague
    references (e.g. "what is that?", "who was it") using the conversation
    history when possible. Falls back to the original query on any error.
    """
    history_block = format_history(history or []) or "(no prior turns)"
    user_prompt = f"CONVERSATION HISTORY:\n{history_block}\n\nUSER QUERY: {user_query}"

    try:
        response = getResponseFromLLM(refine_prompt, user_prompt, 0.0)
        if response.text is None:
            raise ValueError("LLM response is empty")

        result = json.loads(response.text)
        refined = result.get("refined_query")
        if not refined or not isinstance(refined, str):
            raise ValueError("LLM response missing 'refined_query'")

        return refined

    except Exception as e:
        logger.error("Refine Error: %s", e)
        return user_query


def refine_node(state: GraphState):
    search_query = refine_query(state["query"], state.get("history"))
    logger.info("Refined query: %r -> %r", state["query"], search_query)
    return {"search_query": search_query}
