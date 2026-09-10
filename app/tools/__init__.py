"""Backend tools exposed to the support chatbot.

Design principle (see docs/defensive-controls.md): the LLM is never trusted
as an authorization boundary. Every tool that touches customer-specific data
takes the *server-side session user id* (bound by app/chatbot/agent.py, not
supplied by the model) and enforces scoping itself, independent of anything
the model asks for.

The one deliberate exception is knowledge_base_search, which has no concept
of "whose data is this" -- it is a flat search over a knowledge base that
mixes public support articles with internal engineering notes. That single
missing scope check is the lab's core trust-boundary vulnerability. See
vulnerable/upload/README.md and docs/attack-timeline.md Stage 4/5.
"""
from app.tools.customer_lookup import customer_lookup
from app.tools.knowledge_base_search import knowledge_base_search
from app.tools.order_lookup import order_lookup
from app.tools.refund_request import refund_request
from app.tools.ticket_search import ticket_search

# Tools that require the authenticated customer's user_id to be bound
# server-side before the function is invoked (see agent.py).
SCOPED_TOOLS = {"order_lookup", "customer_lookup", "ticket_search", "refund_request"}

TOOL_FUNCTIONS = {
    "order_lookup": order_lookup,
    "customer_lookup": customer_lookup,
    "ticket_search": ticket_search,
    "knowledge_base_search": knowledge_base_search,
    "refund_request": refund_request,
}

# Ollama / OpenAI-style tool schemas advertised to the model.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "order_lookup",
            "description": "Look up the logged-in customer's own orders. Optionally filter by an order id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "Specific order id to look up (optional)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "customer_lookup",
            "description": "Look up the logged-in customer's own account/profile information.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ticket_search",
            "description": "Search the logged-in customer's own support tickets by keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword(s) to search for"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_base_search",
            "description": "Search the support knowledge base / help articles for information relevant to a customer question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refund_request",
            "description": "File a refund request for one of the logged-in customer's own orders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "The order id to refund"},
                    "reason": {"type": "string", "description": "Reason for the refund"},
                },
                "required": ["order_id", "reason"],
            },
        },
    },
]
