"""Simulated data storage: a plain in-memory list of inventory items.

Each item mimics the shape of an OpenFoodFacts API response, plus a few
fields of our own (id, price, stock):

    {
        "id": 1,
        "status": 1,
        "product": {
            "code": "5449000000996",
            "product_name": "Coca-Cola",
            "brands": "Coca-Cola",
            "ingredients_text": "Carbonated water, sugar, ...",
            "nutriscore_grade": "e",
        },
        "price": 1.99,
        "stock": 24,
    }
"""

import copy

# Fields a client is allowed to change with PATCH.
TOP_LEVEL_EDITABLE = {"price", "stock"}
PRODUCT_EDITABLE = {
    "product_name",
    "brands",
    "ingredients_text",
    "nutriscore_grade",
    "code",
}

SEED_DATA = [
    {
        "id": 1,
        "status": 1,
        "product": {
            "code": "5449000000996",
            "product_name": "Coca-Cola",
            "brands": "Coca-Cola",
            "ingredients_text": "Carbonated water, sugar, colour (caramel E150d), "
            "acid (phosphoric acid), natural flavourings including caffeine",
            "nutriscore_grade": "e",
        },
        "price": 1.99,
        "stock": 24,
    },
    {
        "id": 2,
        "status": 1,
        "product": {
            "code": "3017620422003",
            "product_name": "Nutella",
            "brands": "Ferrero",
            "ingredients_text": "Sugar, palm oil, hazelnuts 13%, skimmed milk "
            "powder 8.7%, cocoa powder 7.4%, emulsifier: lecithins (soy), vanillin",
            "nutriscore_grade": "e",
        },
        "price": 4.5,
        "stock": 12,
    },
    {
        "id": 3,
        "status": 1,
        "product": {
            "code": "0000000000001",
            "product_name": "Organic Almond Milk",
            "brands": "Silk",
            "ingredients_text": "Filtered water, almonds, cane sugar, sea salt, "
            "sunflower lecithin",
            "nutriscore_grade": "b",
        },
        "price": 3.25,
        "stock": 30,
    },
]

# The "database": a module-level array.
inventory = copy.deepcopy(SEED_DATA)


def reset():
    """Restore the seed data (used by tests)."""
    inventory.clear()
    inventory.extend(copy.deepcopy(SEED_DATA))


def next_id():
    """Return the next unused integer ID."""
    return max((item["id"] for item in inventory), default=0) + 1


def get_all():
    return inventory


def get_one(item_id):
    for item in inventory:
        if item["id"] == item_id:
            return item
    return None


def add(item):
    inventory.append(item)
    return item


def remove(item_id):
    item = get_one(item_id)
    if item is None:
        return None
    inventory.remove(item)
    return item
