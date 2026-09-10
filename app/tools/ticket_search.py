from app.models.db import query_all


def ticket_search(user_id: int, query: str = ""):
    """Search the calling customer's OWN customer-visibility tickets.

    Correctly scoped: user_id = calling customer AND visibility = 'customer'.
    Internal engineering tickets are never returned here -- contrast with
    knowledge_base_search, which has no such filter (the lab's bug).
    """
    like = f"%{query}%" if query else "%"
    rows = query_all(
        "SELECT ticket_ref, subject, body, status, created_at FROM tickets "
        "WHERE user_id = ? AND visibility = 'customer' "
        "AND (subject LIKE ? OR body LIKE ?) ORDER BY created_at DESC",
        (user_id, like, like),
    )
    return {"tickets": rows}
