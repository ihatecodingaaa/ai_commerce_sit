import os, re, secrets, time, uuid
from html import escape
from typing import Optional

import httpx
import psycopg
from fastapi import FastAPI, Form, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.context import CryptContext

app = FastAPI(title="AI Commerce Security Lab")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB = os.environ["DATABASE_URL"]
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "lab_service_token_only_8f3d2a7c")
IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://image-service:8000")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
SESSIONS: dict[str, int] = {}

PUBLIC_DOCS = {
    "shipping-policy.md": "Standard shipping takes 3-5 business days. Express shipping takes 1-2 business days.",
    "refund-policy.md": "Refunds may be requested within 14 days for unused products.",
    "returns.md": "Open a support ticket before returning an item.",
    "product-support.md": "Support can look up orders, tickets and product-image issues.",
    "image-upload-guide.md": "Product image issues are handled by an internal image-management service. Customers do not access that service directly.",
}

# INTERNAL / SHOULD NOT BE CUSTOMER-RETRIEVABLE.
# VULNERABILITY: document-level authorization is intentionally omitted in vulnerable_document_filter().
def internal_runbook() -> str:
    return (
        "Internal Image Service\n"
        "Service account: support-image-service\n"
        f"Authentication: {SERVICE_TOKEN}\n"
        "Endpoint: http://image-service:8000\n"
        "Permissions: image metadata, image upload\n"
    )


def db():
    return psycopg.connect(DB, autocommit=True)


def log(event: str, detail: str = ""):
    safe = detail.replace(SERVICE_TOKEN, SERVICE_TOKEN[:4] + "...redacted")
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} request={uuid.uuid4()} event={event} {safe}", flush=True)


def init_db():
    for _ in range(30):
        try:
            with db() as c, c.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer');
                    CREATE TABLE IF NOT EXISTS reviews(id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id), product_id INT NOT NULL, body TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS orders(id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id), order_no TEXT UNIQUE NOT NULL, status TEXT NOT NULL);
                """)
                seeds = [("alice@example.test","ORD-10001","Shipped"),("bob@example.test","ORD-10002","Processing"),("charlie@example.test","ORD-10003","Delivered")]
                for email, order_no, status in seeds:
                    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                    row = cur.fetchone()
                    if not row:
                        cur.execute("INSERT INTO users(email,password_hash) VALUES(%s,%s) RETURNING id", (email,pwd.hash("Customer123!")))
                        uid = cur.fetchone()[0]
                    else:
                        uid = row[0]
                    cur.execute("INSERT INTO orders(user_id,order_no,status) VALUES(%s,%s,%s) ON CONFLICT(order_no) DO NOTHING", (uid,order_no,status))
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("database unavailable")


@app.on_event("startup")
def startup():
    init_db()


def page(title: str, body: str) -> str:
    nav = '<nav><a href="/">Home</a> | <a href="/products">Products</a> | <a href="/account">Account</a> | <a href="/orders">Orders</a> | <a href="/support">Support</a> | <a href="/about">About</a></nav><hr>'
    return f"<!doctype html><html><head><title>{escape(title)}</title><style>body{{font-family:Arial;max-width:900px;margin:40px auto;line-height:1.5}}textarea,input{{width:100%;padding:8px;margin:5px 0}}button{{padding:8px 16px}}pre{{white-space:pre-wrap;background:#eee;padding:12px}}</style></head><body>{nav}<h1>{escape(title)}</h1>{body}</body></html>"


def current_user(request: Request) -> Optional[tuple[int,str,str]]:
    sid = request.cookies.get("sid")
    uid = SESSIONS.get(sid or "")
    if not uid: return None
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT id,email,role FROM users WHERE id=%s", (uid,))
        return cur.fetchone()


def require_user(request: Request):
    u = current_user(request)
    if not u: raise HTTPException(401, "login required")
    return u


@app.get("/", response_class=HTMLResponse)
def home():
    return page("AI Commerce", "<p>Welcome to a synthetic training storefront.</p><p>Try the support chatbot, browse products, or create a customer account.</p>")

@app.get("/products", response_class=HTMLResponse)
def products():
    cards = ''.join(f'<li><a href="/product/{i}">Product {i}</a> — synthetic demo item</li>' for i in range(1,4))
    return page("Products", f"<ul>{cards}</ul>")

@app.get("/product/{product_id}", response_class=HTMLResponse)
def product(product_id: int):
    return page(f"Product {product_id}", f'<p>Demo product {product_id}. Customers may submit reviews after login.</p><form method="post" action="/api/reviews"><input type="hidden" name="product_id" value="{product_id}"><textarea name="body"></textarea><button>Submit review</button></form>')

@app.get("/register", response_class=HTMLResponse)
def register_form():
    return page("Register", '<form method="post"><input name="email" type="email" required><input name="password" type="password" required><button>Create account</button></form>')

@app.post("/register")
def register(email: str = Form(...), password: str = Form(...)):
    with db() as c, c.cursor() as cur:
        try: cur.execute("INSERT INTO users(email,password_hash) VALUES(%s,%s)", (email,pwd.hash(password)))
        except psycopg.errors.UniqueViolation: raise HTTPException(409,"email exists")
    log("customer_registered", email)
    return RedirectResponse("/login",303)

@app.get("/login", response_class=HTMLResponse)
def login_form():
    return page("Login", '<form method="post"><input name="email" type="email"><input name="password" type="password"><button>Login</button></form>')

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT id,password_hash FROM users WHERE email=%s", (email,)); row=cur.fetchone()
    if not row or not pwd.verify(password,row[1]): raise HTTPException(401,"invalid credentials")
    sid=secrets.token_urlsafe(24); SESSIONS[sid]=row[0]
    r=RedirectResponse("/account",303); r.set_cookie("sid",sid,httponly=True,samesite="lax"); return r

@app.get("/logout")
def logout(request: Request):
    sid=request.cookies.get("sid"); SESSIONS.pop(sid or "",None); r=RedirectResponse("/",303); r.delete_cookie("sid"); return r

@app.get("/account", response_class=HTMLResponse)
def account(request: Request):
    u=require_user(request); return page("Account",f"<p>{escape(u[1])}</p><p>Role: {escape(u[2])}</p><a href='/logout'>Logout</a>")

@app.get("/orders", response_class=HTMLResponse)
def orders(request: Request):
    u=require_user(request)
    with db() as c,c.cursor() as cur:
        cur.execute("SELECT order_no,status FROM orders WHERE user_id=%s",(u[0],)); rows=cur.fetchall()
    return page("Orders","<ul>"+''.join(f"<li>{escape(a)} — {escape(b)}</li>" for a,b in rows)+"</ul>")

@app.get("/about", response_class=HTMLResponse)
def about():
    return page("About","<p>AI Commerce is a synthetic retailer.</p><h3>Customer Operations</h3><p>Alice Tan — Head of Customer Operations</p><p>Our teams handle support, orders, returns, and product image quality.</p>")

@app.post("/api/reviews")
def review(request: Request, product_id: int=Form(...), body: str=Form(...)):
    u=require_user(request)
    with db() as c,c.cursor() as cur: cur.execute("INSERT INTO reviews(user_id,product_id,body) VALUES(%s,%s,%s)",(u[0],product_id,body))
    return RedirectResponse(f"/product/{product_id}",303)


def vulnerable_document_filter(query: str):
    # INTENTIONAL FLAW: internal documents are not filtered by caller role.
    docs=list(PUBLIC_DOCS.items())
    with db() as c,c.cursor() as cur:
        cur.execute("SELECT 'customer-review-'||id, body FROM reviews ORDER BY id DESC LIMIT 20")
        docs += cur.fetchall()
    terms=set(re.findall(r"[a-z]{4,}",query.lower()))
    scored=[]
    for name,text in docs:
        score=sum(1 for t in terms if t in text.lower() or t in str(name).lower())
        if score: scored.append((score,str(name),text))
    return sorted(scored,reverse=True)[:5]


def injection_influences_agent(retrieved) -> bool:
    # Deterministic mock behavior: several semantically similar injections work.
    text=" ".join(str(x[2]).lower() for x in retrieved)
    imperative=any(w in text for w in ["reveal","show","return","print","include","disclose"])
    target=any(p in text for p in ["internal image","image service","service configuration","support configuration"])
    authority=any(p in text for p in ["support agent","assistant","system instruction","priority instruction"])
    return imperative and target and authority


def vulnerable_tool_authorization(tool: str, user_role: str) -> bool:
    # INTENTIONAL FLAW: LLM-selected internal support_configuration is not independently authorized.
    if tool == "support_configuration": return True
    return tool in {"order_lookup","knowledge_base_search"}


def secure_tool_authorization(tool: str, user_role: str) -> bool:
    return tool != "support_configuration" or user_role in {"support","admin"}


def mock_agent(message: str, role: str) -> str:
    retrieved=vulnerable_document_filter(message)
    for _,name,_ in retrieved: log("document_retrieved",name)
    if injection_influences_agent(retrieved) and any(k in message.lower() for k in ["image","internal","configuration","support"]):
        tool="support_configuration"; log("tool_invoked",tool)
        if vulnerable_tool_authorization(tool,role):
            log("internal_document_retrieved","internal-image-service-runbook.md")
            log("service_token_accessed",SERVICE_TOKEN)
            return internal_runbook()+"\nFLAG{internal_information_disclosed}\nFLAG{service_token_obtained}"
    if "refund" in message.lower(): return PUBLIC_DOCS["refund-policy.md"]
    if "shipping" in message.lower(): return PUBLIC_DOCS["shipping-policy.md"]
    if "image" in message.lower(): return PUBLIC_DOCS["image-upload-guide.md"]
    return "I can help with orders, refunds, returns, support tickets, product issues and image-related support."


async def local_agent(message: str) -> str:
    # Real model mode has NO shell/exec tools. Retrieved text is explicitly marked untrusted.
    base=os.getenv("LOCAL_LLM_BASE_URL","http://host.docker.internal:11434/v1")
    model=os.getenv("LOCAL_LLM_MODEL","qwen2.5:3b")
    retrieved=vulnerable_document_filter(message)
    context="\n".join(f"[UNTRUSTED RAG {name}] {text}" for _,name,text in retrieved)
    payload={"model":model,"messages":[{"role":"system","content":"You are a customer support assistant. LLM output is untrusted; backend must authorize tools."},{"role":"user","content":message+"\n"+context}],"temperature":0}
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.post(base.rstrip("/")+"/chat/completions",json=payload); r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]

@app.get("/support", response_class=HTMLResponse)
def support():
    return page("Support",'<p>Ask about orders, refunds, tickets, or product image issues.</p><form method="post"><textarea name="message"></textarea><button>Ask</button></form>')

@app.post("/support", response_class=HTMLResponse)
async def support_post(request: Request, message: str=Form(...)):
    u=require_user(request); log("chatbot_request",message[:120])
    answer = await local_agent(message) if LLM_PROVIDER=="local" else mock_agent(message,u[2])
    return page("Support",f"<p><b>You:</b> {escape(message)}</p><pre>{escape(answer)}</pre><a href='/support'>Ask another</a>")

@app.get("/api/image-service/info")
def image_info(request: Request):
    require_user(request)
    return {"name":"image-management","access":"internal support service","auth":"Bearer service credential required"}

@app.get("/api/admin")
def admin(request: Request):
    u=require_user(request)
    if u[2] != "admin": raise HTTPException(403,"admin required")
    return {"ok":True}
