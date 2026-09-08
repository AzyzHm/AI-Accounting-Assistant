from typing import TypedDict


class HistoryTurn(TypedDict):
    role: str
    content: str


class TokenUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GraphState(TypedDict):
    query: str
    """The raw question exactly as the user typed it. Never mutated."""

    search_query: str
    """The (possibly refined) query actually sent to retrieval/web search.
    Starts as `query`, gets rewritten by the refine node, and can be
    swapped for the validator's `optimized_query` when retrying retrieval."""

    history: list[HistoryTurn]
    intent: str
    """One of "general_knowledge", "web_search", "retrieve". Decides which
    path through the graph this turn takes."""

    category: str
    """Subject category ("ifrs", "tax_code", "accounting_standards"), only
    meaningful when intent == "retrieve"."""

    context: str
    answer: str
    is_valid: bool
    retrieval_attempts: int
    """How many times the retrieve node has run for this turn. Used to cap
    the retrieve -> validate retry loop at MAX_RETRIEVAL_ATTEMPTS."""

    token_usage: TokenUsage
