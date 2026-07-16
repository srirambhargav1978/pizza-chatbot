import os
import uuid
from typing import Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import PIZZA_GRAPH

app = FastAPI(title="Pizza Chatbot")

# In-memory session store (cart + conversation) — resets on container
# restart. Completed orders and known customers persist in SQLite (db.py)
# regardless, since that's the part that actually needs to survive.
SESSIONS: Dict[str, dict] = {}

LANGFUSE_ENABLED = bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))


def _get_langfuse_handler():
    if not LANGFUSE_ENABLED:
        return None
    try:
        from langfuse.callback import CallbackHandler
        return CallbackHandler()
    except Exception:
        return None


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    cart: list
    status: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "pizza-chatbot"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    session = SESSIONS.setdefault(session_id, {
        "history": [], "cart": [], "customer_phone": None, "customer_name": None, "status": "ordering",
    })

    state = {
        "session_id": session_id,
        "message": req.message,
        "history": session["history"],
        "cart": session["cart"],
        "customer_phone": session["customer_phone"],
        "customer_name": session["customer_name"],
        "status": session["status"],
        "action": {},
        "action_result": {},
        "reply": "",
    }

    config = {}
    handler = _get_langfuse_handler()
    if handler:
        config["callbacks"] = [handler]

    result = PIZZA_GRAPH.invoke(state, config=config)

    session["history"].append({"role": "user", "content": req.message})
    session["history"].append({"role": "assistant", "content": result["reply"]})
    session["cart"] = result["cart"]
    session["customer_phone"] = result.get("customer_phone")
    session["customer_name"] = result.get("customer_name")
    session["status"] = result.get("status", "ordering")

    return ChatResponse(
        session_id=session_id,
        reply=result["reply"],
        cart=result["cart"],
        status=session["status"],
    )


@app.get("/", response_class=HTMLResponse)
def chat_ui():
    return CHAT_UI_HTML


CHAT_UI_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pizza Chatbot — Order Online</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Inter',sans-serif;background:#060B14;color:#E2EAF4;height:100vh;display:flex;flex-direction:column}
  header{padding:20px 5%;border-bottom:1px solid #1A2E4A;display:flex;align-items:center;gap:10px}
  .mark{width:32px;height:32px;background:linear-gradient(135deg,#F59E0B,#EF4444);border-radius:7px;display:flex;align-items:center;justify-content:center;font-weight:800;color:#060B14;font-size:13px}
  header span{font-weight:700;font-size:15px}
  header small{color:#6B84A3;margin-left:8px}
  #log{flex:1;overflow-y:auto;padding:24px 5%;display:flex;flex-direction:column;gap:14px;max-width:760px;margin:0 auto;width:100%}
  .msg{max-width:75%;padding:12px 16px;border-radius:14px;font-size:14px;line-height:1.6}
  .user{align-self:flex-end;background:#F59E0B;color:#060B14;font-weight:500}
  .bot{align-self:flex-start;background:#0D1B35;border:1px solid #1A2E4A}
  .cart{align-self:flex-start;background:#0D1B35;border:1px solid #1A2E4A;border-radius:10px;padding:12px 14px;font-size:12px;max-width:85%}
  .cart b{display:block;color:#fff;margin-bottom:6px;font-size:12.5px}
  .cart-item{display:flex;justify-content:space-between;color:#9fb0c8;padding:3px 0}
  form{border-top:1px solid #1A2E4A;padding:16px 5%;display:flex;gap:10px;max-width:760px;margin:0 auto;width:100%}
  input{flex:1;background:#0D1B35;border:1px solid #1A2E4A;border-radius:8px;padding:12px 14px;color:#fff;font-size:14px}
  input:focus{outline:none;border-color:#F59E0B}
  button{background:#F59E0B;color:#060B14;border:none;border-radius:8px;padding:0 22px;font-weight:700;cursor:pointer;font-size:14px}
  button:disabled{opacity:.5;cursor:default}
  .hint{color:#6B84A3;font-size:12px;text-align:center;padding:6px 0 14px}
</style>
</head>
<body>

<header>
  <div class="mark">SB</div>
  <span>Pizza Chatbot</span>
  <small>Ordering Agent &middot; LangGraph + LiteLLM + SQLite</small>
</header>

<div id="log">
  <div class="msg bot">Hey! What can I get started for you? You can order straight away as a guest, or give me your phone number if you've ordered before and I'll pull up your usual.</div>
</div>
<div class="hint">Try: "I'll have a large pepperoni with extra cheese" or "my number is 0400111222"</div>

<form id="chat-form">
  <input id="input" type="text" placeholder="Order something, or ask about the menu..." autocomplete="off">
  <button type="submit" id="send-btn">Send</button>
</form>

<script>
let sessionId = null;
const log = document.getElementById('log');
const form = document.getElementById('chat-form');
const input = document.getElementById('input');
const btn = document.getElementById('send-btn');

function addMsg(text, cls) {
  const d = document.createElement('div');
  d.className = 'msg ' + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function addCart(cart) {
  const existing = document.getElementById('cart-box');
  if (existing) existing.remove();
  if (!cart || !cart.length) return;
  const wrap = document.createElement('div');
  wrap.className = 'cart';
  wrap.id = 'cart-box';
  let total = 0;
  let html = '<b>Current order</b>';
  cart.forEach(i => {
    const lineTotal = i.price * (i.qty || 1);
    total += lineTotal;
    const label = i.size ? (i.name + ' (' + i.size + ')') : i.name;
    html += '<div class="cart-item"><span>' + (i.qty || 1) + '&times; ' + label + '</span><span>$' + lineTotal.toFixed(2) + '</span></div>';
  });
  html += '<div class="cart-item" style="border-top:1px solid #1A2E4A;margin-top:6px;padding-top:6px;color:#fff"><span>Total</span><span>$' + total.toFixed(2) + '</span></div>';
  wrap.innerHTML = html;
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  addMsg(message, 'user');
  input.value = '';
  btn.disabled = true;

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({session_id: sessionId, message})
    });
    const data = await res.json();
    sessionId = data.session_id;
    addMsg(data.reply, 'bot');
    addCart(data.cart);
  } catch (err) {
    addMsg('Something went wrong placing that. Please try again.', 'bot');
  } finally {
    btn.disabled = false;
    input.focus();
  }
});
</script>

</body>
</html>"""
