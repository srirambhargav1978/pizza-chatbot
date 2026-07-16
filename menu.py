"""Menu catalog for the pizza ordering demo."""

PIZZAS = [
    {"id": "margherita", "name": "Margherita", "description": "Tomato, mozzarella, basil", "prices": {"small": 11, "medium": 15, "large": 19}},
    {"id": "pepperoni", "name": "Pepperoni", "description": "Tomato, mozzarella, pepperoni", "prices": {"small": 12, "medium": 16, "large": 20}},
    {"id": "bbq_chicken", "name": "BBQ Chicken", "description": "BBQ base, chicken, red onion, mozzarella", "prices": {"small": 13, "medium": 17, "large": 21}},
    {"id": "veggie_supreme", "name": "Veggie Supreme", "description": "Capsicum, mushroom, olives, onion, mozzarella", "prices": {"small": 12, "medium": 16, "large": 20}},
    {"id": "hawaiian", "name": "Hawaiian", "description": "Tomato, mozzarella, ham, pineapple", "prices": {"small": 12, "medium": 16, "large": 20}},
    {"id": "meat_lovers", "name": "Meat Lovers", "description": "Pepperoni, ham, beef, bacon, mozzarella", "prices": {"small": 14, "medium": 18, "large": 23}},
]

TOPPINGS = [
    {"id": "extra_cheese", "name": "Extra Cheese", "price": 2},
    {"id": "mushroom", "name": "Mushroom", "price": 1.5},
    {"id": "olives", "name": "Olives", "price": 1.5},
    {"id": "jalapeno", "name": "Jalapeno", "price": 1.5},
    {"id": "bacon", "name": "Bacon", "price": 2.5},
]

SIDES = [
    {"id": "garlic_bread", "name": "Garlic Bread", "price": 6},
    {"id": "wedges", "name": "Potato Wedges", "price": 7},
    {"id": "chicken_wings", "name": "Chicken Wings (6pc)", "price": 9},
]

DRINKS = [
    {"id": "cola", "name": "Cola (500ml)", "price": 4},
    {"id": "sparkling_water", "name": "Sparkling Water", "price": 3},
    {"id": "orange_juice", "name": "Orange Juice", "price": 4},
]

SIZES = ["small", "medium", "large"]


def find_pizza(pizza_id: str):
    return next((p for p in PIZZAS if p["id"] == pizza_id or p["name"].lower() == str(pizza_id).lower()), None)


def find_side_or_drink(item_id: str):
    for item in SIDES + DRINKS:
        if item["id"] == item_id or item["name"].lower() == str(item_id).lower():
            return item
    return None


def menu_summary_text() -> str:
    """A compact text form of the whole menu, handed to the model so it
    knows exactly what's available (and doesn't invent items)."""
    lines = ["PIZZAS (small/medium/large prices):"]
    for p in PIZZAS:
        lines.append(f"- {p['name']} ({p['id']}): {p['description']} — ${p['prices']['small']}/${p['prices']['medium']}/${p['prices']['large']}")
    lines.append("\nEXTRA TOPPINGS:")
    for t in TOPPINGS:
        lines.append(f"- {t['name']} ({t['id']}): +${t['price']}")
    lines.append("\nSIDES:")
    for s in SIDES:
        lines.append(f"- {s['name']} ({s['id']}): ${s['price']}")
    lines.append("\nDRINKS:")
    for d in DRINKS:
        lines.append(f"- {d['name']} ({d['id']}): ${d['price']}")
    return "\n".join(lines)
