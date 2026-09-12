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

    uid: str
    """The caller's Firebase uid, used by the web_search node to enforce
    their per-user search credit limit. Absent for graph runs that do not
    need quota enforcement, such as the module's own __main__ smoke test."""

    search_blocked: bool
    """True when the web_search node skipped an actual search because the
    caller had already reached their daily or monthly search credit limit."""

    search_block_message: str
    """Set alongside `search_blocked`: a ready-to-display explanation of
    why the web search was skipped and the exact date it becomes available
    again. The generate node returns this verbatim instead of calling the
    LLM."""
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
