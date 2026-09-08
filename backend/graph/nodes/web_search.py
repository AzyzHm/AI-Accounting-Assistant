from core.logger import get_logger
from graph.state import GraphState
from services.search_service import search_web

logger = get_logger(__name__)


def web_search_node(state: GraphState):
    """uses the web search service"""
    search_query = state.get("search_query") or state["query"]
    logger.info("Searching the web: %r", search_query)
    context = search_web(search_query)
    return {"context": context}
