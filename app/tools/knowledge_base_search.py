from app.logging_setup import log_event
from app.rag.retrieval import search_articles


def knowledge_base_search(query: str):
    """Search the support knowledge base.

    *** THIS IS THE LAB'S DELIBERATE VULNERABILITY (CWE-863: Incorrect
    Authorization). ***

    Every other customer-facing tool in this package scopes its query to the
    calling customer's own user_id. This one does not: it searches
    kb_articles with no `visibility` filter, so internal-only articles
    (visibility='internal' -- runbooks, credential-rotation notes, incident
    tickets) are just as retrievable as public FAQ content. There is no
    per-customer authorization concept for "knowledge" the way there is for
    "your orders" or "your tickets", so the article that should have read
    `WHERE visibility = 'public'` was written without it.

    The query string itself is whatever the *model* decided to search for.
    Normally that mirrors the customer's question. But if attacker-controlled
    text reached the model's context (e.g. via a product review that was
    auto-indexed into the knowledge base -- see app/rag/retrieval.py) and
    that text instructs the model to search for something else, the model
    may call this tool with attacker-chosen terms, and this function will
    dutifully return internal content into the conversation. See
    docs/attack-timeline.md Stage 4/5 for the full chain.
    """
    results = search_articles(query, visibility_filter=None)  # <-- no filter: the bug
    log_event(
        "kb_retrieval",
        query=query,
        retrieved_ids=[r["id"] for r in results],
        retrieved_visibilities=[r["visibility"] for r in results],
    )
    return {
        "results": [
            {"id": r["id"], "title": r["title"], "body": r["body"]} for r in results
        ]
    }
