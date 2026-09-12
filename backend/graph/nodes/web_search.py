from core.logger import get_logger
from graph.state import GraphState
from services import limits_service, stats_service
from services.search_service import search_web

logger = get_logger(__name__)


def web_search_node(state: GraphState):
    """Searches the web via the search service, unless the caller has
    already reached their daily or monthly search credit limit, in which
    case the search is skipped entirely and a ready-to-display explanation
    (with the exact reset date) is returned instead. ADMIN and SUPER_ADMIN
    are exempt, they always get the actual search."""
    uid = state.get("uid")
    role = state.get("role")

    if uid:
        block_message = limits_service.search_limit_message(uid, role)
        if block_message:
            logger.info("Web search blocked for %s: search credit limit reached", uid)
            return {"context": "", "search_blocked": True, "search_block_message": block_message}

    search_query = state.get("search_query") or state["query"]
    logger.info("Searching the web: %r", search_query)
    context = search_web(search_query)

    if uid:
        limits_service.record_search_usage(uid, role)
        stats_service.record_search_credit(uid)

    return {"context": context}
