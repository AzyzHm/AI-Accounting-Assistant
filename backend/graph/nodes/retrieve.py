import ollama

from core.logger import get_logger
from graph.state import GraphState
from services.chroma_service import collection

logger = get_logger(__name__)


def retrieve_context(query: str, category: str, n_results: int = 5):
    """
    Retrieves relevant chunks from ChromaDB filtered by category.
    """
    query_embedding = ollama.embed(model="embeddinggemma", input=query)["embeddings"][0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"category": {"$eq": category}},  # type: ignore[dict-item]
    )

    documents = results.get("documents", [[]])
    context_list = documents[0] if documents and len(documents) > 0 else []
    if not context_list or not isinstance(context_list, list):
        return "No local documents found."
    return "\n\n".join(context_list)


def retrieval_node(state: GraphState):
    attempts = state.get("retrieval_attempts", 0) + 1
    search_query = state.get("search_query") or state["query"]

    logger.info(
        "Retrieving (attempt %d) query=%r category=%s", attempts, search_query, state["category"]
    )
    context = retrieve_context(search_query, state["category"], 5)
    return {"context": context, "retrieval_attempts": attempts}
