from config.llm_providers import getResponseFromLLM
from config.prompts import expert_prompt_v1, expert_prompt_v2
from core.logger import get_logger
from graph.nodes.history_utils import format_history
from graph.state import GraphState

logger = get_logger(__name__)

_EMPTY_TOKEN_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _extract_token_usage(response) -> dict:
    """Pulls prompt/completion/total token counts off an LLM response's
    usage_metadata, defaulting every field to 0 when it is absent."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return dict(_EMPTY_TOKEN_USAGE)

    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", None) or 0,
        "completion_tokens": getattr(usage, "candidates_token_count", None) or 0,
        "total_tokens": getattr(usage, "total_token_count", None) or 0,
    }


def generate_answer_node(state: GraphState):
    """Generate a final answer for the query, grounded in retrieved/web
    context (when available) and the recent conversation history (when
    available).

    When the web_search node skipped an actual search because the caller's
    search credit limit was reached, the LLM is never called: the node's
    ready-to-display explanation is returned verbatim as the answer, so the
    exact reset date it names is never paraphrased or dropped by the LLM.
    """
    if state.get("search_blocked"):
        return {
            "answer": state.get("search_block_message", ""),
            "token_usage": dict(_EMPTY_TOKEN_USAGE),
        }

    context = state.get("context", "")
    query = state.get("query", "")
    intent = state.get("intent", "general_knowledge")
    history = state.get("history") or []

    history_block = f"CONVERSATION SO FAR:\n{format_history(history)}\n\n" if history else ""

    if not context or intent == "general_knowledge":
        expert_prompt = expert_prompt_v1
        user_msg = f"{history_block}QUESTION: {query}"
    else:
        expert_prompt = expert_prompt_v2
        user_msg = f"{history_block}CONTEXT: {context}\n\nQUESTION: {query}"

    logger.info("Generating answer (intent=%s, has_context=%s)", intent, bool(context))

    response = getResponseFromLLM(
        system_prompt=expert_prompt, user_prompt=user_msg, model_temp=0.5, format="text"
    )

    return {"answer": response.text, "token_usage": _extract_token_usage(response)}
