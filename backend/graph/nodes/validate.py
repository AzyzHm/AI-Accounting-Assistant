import json

from config.llm_providers import getResponseFromLLM
from config.prompts import validator_prompt
from core.logger import get_logger
from graph.state import GraphState

logger = get_logger(__name__)


def validate_node(state: GraphState):
    """Validate the context before augmenting the final answer.

    When the context is not enough to answer the query, this also asks the
    LLM for an "optimized query" targeting the missing information, which
    the workflow can send back to the retriever for another attempt (up to
    MAX_RETRIEVAL_ATTEMPTS, see graph/workflow.py).
    """

    if state.get("intent") == "general_knowledge":
        return {"is_valid": True}

    user_input = f"USER QUERY: {state['query']}\n\nRETRIEVED CONTEXT: {state['context']}"

    try:
        response = getResponseFromLLM(validator_prompt, user_input, 0.0)
        if response.text is None:
            raise ValueError("LLM Response is empty")
        result = json.loads(response.text)

        is_valid = result.get("is_valid", False)
        optimized_query = result.get("optimized_query")

        logger.info("Validation result: is_valid=%s optimized_query=%r", is_valid, optimized_query)

        update: dict = {"is_valid": is_valid}
        if not is_valid and optimized_query:
            update["search_query"] = optimized_query
        return update
    except Exception as e:
        logger.error("Validation Error: %s", e)
        return {"is_valid": False}
