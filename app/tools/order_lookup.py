from app.models.db import query_all, query_one


def order_lookup(user_id: int, order_id: int | None = None):
    """Return the calling customer's own orders. Always scoped to user_id,
    which is bound server-side from the session -- never from model input.
    """
    if order_id is not None:
        row = query_one(
            "SELECT o.id, o.quantity, o.total_cents, o.status, o.created_at, p.name AS product_name "
            "FROM orders o JOIN products p ON p.id = o.product_id "
            "WHERE o.id = ? AND o.user_id = ?",
            (order_id, user_id),
        )
        return {"orders": [row] if row else []}

    rows = query_all(
        "SELECT o.id, o.quantity, o.total_cents, o.status, o.created_at, p.name AS product_name "
        "FROM orders o JOIN products p ON p.id = o.product_id "
        "WHERE o.user_id = ? ORDER BY o.created_at DESC",
        (user_id,),
    )
    return {"orders": rows}
