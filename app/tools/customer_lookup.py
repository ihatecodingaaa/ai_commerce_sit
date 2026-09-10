from app.models.db import query_one


def customer_lookup(user_id: int):
    """Return the calling customer's own profile only. There is no argument
    that lets the caller (model) target a different customer id -- this
    tool's signature intentionally has no such parameter.
    """
    row = query_one(
        "SELECT id, username, email, full_name, created_at FROM users WHERE id = ?",
        (user_id,),
    )
    return {"customer": row}
