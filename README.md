# Pizza Chatbot

A conversational ordering agent built with LangGraph — takes an order
naturally over chat, supports guest checkout or recognizing a returning
customer by phone number, and persists completed orders to SQLite.

Live demo: https://api-pizza.sbm78.au

## How it works

A 3-node LangGraph agent runs on every message:

1. **`parse_intent`** — reads the menu, current cart, and the new message,
   and decides exactly one structured action: add an item, remove an item,
   record the customer's phone/name, check out, or just answer a question
   (chitchat) without changing the order.
2. **`apply_action`** — plain Python. Prices the item against the menu
   catalog (including per-topping pricing), mutates the cart, looks up or
   saves the customer in SQLite, or finalizes the order. No LLM call here.
3. **`generate_reply`** — asks the model to write a natural confirmation
   or answer based on what just happened, including the running total.

The "guest vs returning customer" flow: giving a phone number doesn't
require a password — it's just enough to recognize you next time and offer
"the usual?" based on your last order, stored in SQLite. First-time numbers
get a neutral acknowledgment; numbers that already exist in the customers
table get recognized with their last order pulled up.

All model calls go through the shared LiteLLM proxy, so this app is
protected by the same moderation guardrail as every other app on the
platform and traces to the same Langfuse project automatically.

## Stack

- **FastAPI** — HTTP API + serves its own chat UI at `/`
- **LangGraph** — the agent graph described above
- **SQLite** — customers + completed orders (`db.py`)
- **LiteLLM** — model gateway (not called directly)
- **Langfuse** — tracing (wired via LiteLLM's callback)

## Running locally

```bash
pip install -r requirements.txt
export LITELLM_BASE_URL=http://localhost:4000
export LITELLM_MASTER_KEY=your-key
uvicorn main:app --reload
```

Requires a LiteLLM proxy running separately — see the
[infrastructure repo](https://github.com/srirambhargav1978/sbm78-infrastructure).

## API

- `GET /` — chat UI
- `POST /chat` — `{"session_id": "optional", "message": "..."}` → reply + current cart
- `GET /health` — health check
