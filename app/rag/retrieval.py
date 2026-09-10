"""Lightweight keyword-relevance retrieval.

This intentionally is NOT a vector/embedding pipeline -- a 4 GiB, GPU-less
EC2 instance running Ollama alongside the app has little room for an
embedding model too. A simple term-overlap scorer demonstrates exactly the
same security property a "real" RAG pipeline would have: whatever content
scores highest for a query gets inserted into the LLM's context, verbatim,
with no distinction between "written by support staff" and "written by a
customer".
"""
import re

from app.models.db import execute, query_all

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "or",
    "for", "in", "on", "with", "my", "me", "i", "it", "this", "that", "do",
    "does", "how", "what", "can", "you", "please", "help", "about", "your",
}

_WORD_RE = re.compile(r"[a-zA-Z0-9\-]{2,}")


def _tokens(text: str):
    return [t.lower() for t in _WORD_RE.findall(text or "") if t.lower() not in _STOPWORDS]


def index_content_as_kb(title: str, body: str, source: str, source_id: int, visibility: str = "public"):
    """Persist a piece of content into the searchable knowledge base.

    Used for seed FAQ/runbook articles AND for auto-indexing customer
    reviews (the attacker-controlled content injection surface). Nothing
    here sanitizes or inspects `body` for embedded instructions -- it is
    stored and later retrieved exactly as submitted.
    """
    return execute(
        "INSERT INTO kb_articles (title, body, visibility, source, source_id) VALUES (?, ?, ?, ?, ?)",
        (title, body, visibility, source, source_id),
    )


def update_kb_content(source: str, source_id: int, title: str = None, body: str = None):
    """Update the KB article mirroring a piece of source content (e.g. an
    edited review) so retrieval always reflects current content -- same
    trust-boundary property as index_content_as_kb: nothing here sanitizes
    the new body either.
    """
    if title is not None:
        execute(
            "UPDATE kb_articles SET title = ? WHERE source = ? AND source_id = ?",
            (title, source, source_id),
        )
    if body is not None:
        execute(
            "UPDATE kb_articles SET body = ? WHERE source = ? AND source_id = ?",
            (body, source, source_id),
        )


def delete_kb_content(source: str, source_id: int):
    """Remove the KB article(s) mirroring a piece of deleted source content."""
    execute("DELETE FROM kb_articles WHERE source = ? AND source_id = ?", (source, source_id))


def search_articles(query: str, visibility_filter: str | None = "public", limit: int = 5):
    """Score every kb_articles row against `query` by term overlap.

    visibility_filter='public'  -> only customer-facing articles (correct
                                    behavior for any *customer-scoped* use).
    visibility_filter=None      -> no filter at all (used by
                                    knowledge_base_search -- the bug).
    """
    q_tokens = set(_tokens(query))
    if not q_tokens:
        return []

    if visibility_filter:
        rows = query_all(
            "SELECT id, title, body, visibility FROM kb_articles WHERE visibility = ?",
            (visibility_filter,),
        )
    else:
        rows = query_all("SELECT id, title, body, visibility FROM kb_articles")

    scored = []
    for row in rows:
        hay_tokens = _tokens(row["title"]) + _tokens(row["body"])
        hay_counts = {}
        for t in hay_tokens:
            hay_counts[t] = hay_counts.get(t, 0) + 1
        score = sum(hay_counts.get(t, 0) for t in q_tokens)
        # small title-match boost so precise queries surface the right doc
        title_tokens = set(_tokens(row["title"]))
        score += 2 * len(q_tokens & title_tokens)
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in scored[:limit]]
