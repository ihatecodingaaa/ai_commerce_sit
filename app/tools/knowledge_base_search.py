from app.logging_setup import log_event
from app.rag.retrieval import search_articles


def knowledge_base_search(query: str, allow_internal: bool = False):
    """Search the support knowledge base and return matching articles.

    `allow_internal` controls whether internal-visibility articles are
    included in the results; it is set by the caller, not by tool arguments.
    """
    results = search_articles(query, visibility_filter=None if allow_internal else "public")
    log_event(
        "kb_retrieval",
        query=query,
        allow_internal=allow_internal,
        retrieved_ids=[r["id"] for r in results],
        retrieved_visibilities=[r["visibility"] for r in results],
    )
    return {
        "results": [
            {"id": r["id"], "title": r["title"], "body": r["body"], "source": r["source"]}
            for r in results
        ]
    }
