from app.models.db import execute, query_one


def refund_request(user_id: int, order_id: int, reason: str):
    """File a refund request for one of the calling customer's own orders.
    Verifies ownership before doing anything -- a model-supplied order_id
    for someone else's order is rejected.
    """
    order = query_one(
        "SELECT id, status FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id)
    )
    if not order:
        return {"error": "order not found for this customer"}

    execute(
        "UPDATE orders SET status = 'refund_requested' WHERE id = ?", (order_id,)
    )
    return {
        "status": "refund_requested",
        "order_id": order_id,
        "reason": reason,
        "note": "A support agent will review this request within 2 business days.",
    }
