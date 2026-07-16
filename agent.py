"""
Pizza Chatbot's LangGraph agent.

Three nodes per incoming message:

  1. parse_intent   — asks the model to read the message (plus cart state
     and conversation so far) and return ONE structured action: add an
     item, remove an item, record the customer's phone/name (the "guest
     vs returning customer" flow), check out, or just answer a question
     about the menu.
  2. apply_action    — plain Python: mutates the cart, looks up returning
     customers in SQLite, or saves a completed order. No LLM call here.
  3. generate_reply  — asks the model to write a natural confirmation/
     answer based on what apply_action just did.

Model calls go through the shared LiteLLM proxy (not directly to a
provider), so this app inherits the same guardrail and Langfuse tracing
as every other app on the platform automatically.
"""

import json
import os
from typing import Any, Dict, List, Optional, TypedDict

from openai import OpenAI
from langgraph.graph import StateGraph, END

import db
import menu

MODEL_NAME = os.environ.get("PIZZA_MODEL", "gpt-4o-mini")


def _client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("LITELLM_BASE_URL", "http://litellm:4000"),
        api_key=os.environ.get("LITELLM_MASTER_KEY", "sk-not-set"),
    )


class PizzaState(TypedDict):
    session_id: str
    message: str
    history: List[Dict[str, str]]
    cart: List[Dict[str, Any]]
    customer_phone: Optional[str]
    customer_name: Optional[str]
    status: str
    action: Dict[str, Any]
    action_result: Dict[str, Any]
    reply: str


INTENT_SYSTEM_PROMPT = """You are the ordering brain for a pizza shop's chat agent.
Given the menu, the current cart, and the newest customer message, decide ONE action.
Respond with ONLY a JSON object (no markdown fences, no commentary) shaped like:

{"action": "add_item", "item_id": "pepperoni", "size": "medium", "toppings": ["bacon"], "qty": 1}
{"action": "remove_item", "item_id": "pepperoni"}
{"action": "set_customer_info", "phone": "0400111222", "name": "Alex"}
{"action": "checkout"}
{"action": "chitchat", "note": "answering a menu question, no cart change"}

Rules:
- item_id must be one of the ids/names from the menu provided.
- "size" only applies to pizzas (small/medium/large); omit for sides/drinks.
- If the message doesn't clearly map to add/remove/checkout/customer-info, use "chitchat".
- Only ever return ONE action per message.
"""

REPLY_SYSTEM_PROMPT = """You are a friendly pizza shop ordering assistant.
You'll be given: the menu, what action was just taken (if any), the resulting cart,
and whether this is a known returning customer with a past order. Write a short,
warm reply (2-4 sentences): confirm what changed, mention the running total if there's
anything in the cart, and prompt the next natural step (add more, or check out).
If it's a checkout confirmation, clearly state the order is placed and the total.
If the customer is recognized and has a past order, you may offer to repeat it.
Never invent menu items that weren't provided."""


def _extract_json(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def parse_intent(state: PizzaState) -> PizzaState:
    try:
        resp = _client().chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({
                    "menu": menu.menu_summary_text(),
                    "cart": state.get("cart", []),
                    "message": state["message"],
                })},
            ],
            temperature=0,
        )
        state["action"] = _extract_json(resp.choices[0].message.content)
    except Exception:
        state["action"] = {"action": "chitchat", "note": "couldn't parse intent"}
    return state


def _price_item(item_id: str, size: Optional[str], toppings: Optional[List[str]]):
    pizza = menu.find_pizza(item_id)
    if pizza:
        size = size if size in menu.SIZES else "medium"
        base = pizza["prices"][size]
        topping_objs = []
        topping_total = 0.0
        for t_id in (toppings or []):
            t = next((t for t in menu.TOPPINGS if t["id"] == t_id or t["name"].lower() == str(t_id).lower()), None)
            if t:
                topping_objs.append(t["name"])
                topping_total += t["price"]
        return {
            "type": "pizza", "id": pizza["id"], "name": pizza["name"], "size": size,
            "toppings": topping_objs, "price": round(base + topping_total, 2),
        }
    other = menu.find_side_or_drink(item_id)
    if other:
        return {"type": "item", "id": other["id"], "name": other["name"], "price": other["price"]}
    return None


def apply_action(state: PizzaState) -> PizzaState:
    action = state.get("action", {})
    kind = action.get("action")
    result: Dict[str, Any] = {"kind": kind}
    cart = state.get("cart", [])

    if kind == "add_item":
        priced = _price_item(action.get("item_id"), action.get("size"), action.get("toppings"))
        if priced:
            priced["qty"] = action.get("qty", 1) or 1
            cart.append(priced)
            result["added"] = priced
        else:
            result["error"] = "item_not_found"

    elif kind == "remove_item":
        target = str(action.get("item_id", "")).lower()
        for i, item in enumerate(cart):
            if item["id"].lower() == target or item["name"].lower() == target:
                result["removed"] = cart.pop(i)
                break
        else:
            result["error"] = "item_not_in_cart"

    elif kind == "set_customer_info":
        phone = action.get("phone")
        name = action.get("name")
        if phone:
            existing = db.get_customer(phone)
            db.upsert_customer(phone, name)
            state["customer_phone"] = phone
            state["customer_name"] = name or (existing["name"] if existing else None)
            result["known_customer"] = bool(existing)
            if existing:
                result["last_order"] = db.get_last_order(phone)

    elif kind == "checkout":
        total = round(sum(i["price"] * i.get("qty", 1) for i in cart), 2)
        if cart:
            order_id = db.save_order(cart, total, state.get("customer_phone"))
            result["order_id"] = order_id
            result["total"] = total
            state["status"] = "checked_out"
            cart = []  # clear the local reference too, or the line below re-fills it
        else:
            result["error"] = "empty_cart"

    state["cart"] = cart
    state["action_result"] = result
    return state


def generate_reply(state: PizzaState) -> PizzaState:
    try:
        resp = _client().chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({
                    "menu": menu.menu_summary_text(),
                    "action_taken": state.get("action", {}),
                    "action_result": state.get("action_result", {}),
                    "cart": state.get("cart", []),
                    "customer_name": state.get("customer_name"),
                    "latest_message": state["message"],
                })},
            ],
            temperature=0.6,
        )
        state["reply"] = resp.choices[0].message.content.strip()
    except Exception as exc:
        state["reply"] = (
            "Sorry, I'm having trouble reaching the kitchen system right now "
            f"({exc.__class__.__name__}). Please try again in a moment."
        )
    return state


def build_graph():
    graph = StateGraph(PizzaState)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("apply_action", apply_action)
    graph.add_node("generate_reply", generate_reply)

    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "apply_action")
    graph.add_edge("apply_action", "generate_reply")
    graph.add_edge("generate_reply", END)

    return graph.compile()


PIZZA_GRAPH = build_graph()
