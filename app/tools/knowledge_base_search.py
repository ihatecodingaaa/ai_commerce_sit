from app.logging_setup import log_event
from app.rag.retrieval import search_articles


def knowledge_base_search(query: str, allow_internal: bool = False):
    """Search the support knowledge base.

    *** THIS IS THE LAB'S DELIBERATE VULNERABILITY (CWE-863: Incorrect
    Authorization). ***

    Every other customer-facing tool in this package scopes its query to the
    calling customer's own user_id. This one does not have a per-customer
    concept of authorization -- instead, whether internal-only articles
    (visibility='internal' -- runbooks, credential-rotation notes, incident
    tickets) are reachable at all is gated by `allow_internal`.

    `allow_internal` is NOT part of this tool's schema (see
    app/tools/__init__.py::TOOL_SCHEMAS) and the model can never set it --
    app/chatbot/agent.py computes it server-side, true only once this
    conversation has already ingested a knowledge_base_search result whose
    `source` is 'review' (untrusted, customer-submitted content -- see
    app/rag/retrieval.py::index_content_as_kb). That is what makes internal
    disclosure reachable ONLY via indirect prompt injection: a directly
    typed customer question, however phrased, never ingests untrusted
    content first, so it always gets the public-only default, regardless of
    what terms the model decides to search for. Only after the model has
    retrieved and followed instructions embedded in a planted review does a
    *second* search get to see internal content -- see
    docs/attack-timeline.md Stage 4/5 for the full chain.
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
