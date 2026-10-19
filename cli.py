"""Command-line interface for the inventory API.

Start the server first (python app.py), then run:  python cli.py
"""

import argparse

import requests

DEFAULT_URL = "http://127.0.0.1:5000"
TIMEOUT = 15


class ApiError(Exception):
    """Raised when the API is unreachable or returns an error."""


class InventoryClient:
    """Thin wrapper around the Flask API that turns failures into ApiError."""

    def __init__(self, base_url=DEFAULT_URL):
        self.base_url = base_url.rstrip("/")

    def request(self, method, path, **kwargs):
        try:
            response = requests.request(
                method, f"{self.base_url}{path}", timeout=TIMEOUT, **kwargs
            )
        except requests.exceptions.ConnectionError as exc:
            raise ApiError(
                f"Could not reach the server at {self.base_url}. Is 'python app.py' running?"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise ApiError("The server took too long to respond.") from exc
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"Request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError(f"Server sent an unreadable response ({response.status_code}).") from exc

        if not response.ok:
            message = data.get("error", "Unknown error") if isinstance(data, dict) else "Unknown error"
            raise ApiError(f"{message} (HTTP {response.status_code})")
        return data

    def list_items(self):
        return self.request("GET", "/inventory")

    def get_item(self, item_id):
        return self.request("GET", f"/inventory/{item_id}")

    def create_item(self, payload):
        return self.request("POST", "/inventory", json=payload)

    def update_item(self, item_id, payload):
        return self.request("PATCH", f"/inventory/{item_id}", json=payload)

    def delete_item(self, item_id):
        return self.request("DELETE", f"/inventory/{item_id}")

    def search_api(self, barcode=None, name=None):
        params = {"barcode": barcode} if barcode else {"name": name}
        return self.request("GET", "/openfoodfacts/search", params=params)

    def add_from_api(self, payload):
        return self.request("POST", "/inventory/from-api", json=payload)


# ---------- Input helpers (re-prompt until valid) ----------

def ask_text(prompt, required=True):
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("  This field is required.")


def ask_int(prompt, minimum=0, default=None):
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if value < minimum:
            print(f"  Please enter a number that is at least {minimum}.")
            continue
        return value


def ask_float(prompt, minimum=0.0, default=None):
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a number (for example 2.99).")
            continue
        if value < minimum:
            print(f"  Please enter a number that is at least {minimum}.")
            continue
        return value


# ---------- Display helpers ----------

def format_item(item):
    product = item["product"]
    return (
        f"[{item['id']}] {product['product_name']}"
        f" ({product['brands'] or 'no brand'}) - ${item['price']:.2f}, stock: {item['stock']}"
    )


def print_item_details(item):
    product = item["product"]
    print(f"\nItem {item['id']}")
    print(f"  Name:         {product['product_name']}")
    print(f"  Brand:        {product['brands'] or '-'}")
    print(f"  Barcode:      {product['code'] or '-'}")
    print(f"  Nutri-Score:  {(product['nutriscore_grade'] or '-').upper()}")
    print(f"  Ingredients:  {product['ingredients_text'] or '-'}")
    print(f"  Price:        ${item['price']:.2f}")
    print(f"  Stock:        {item['stock']}")


# ---------- Menu actions ----------

def add_item(client):
    payload = {
        "product_name": ask_text("Product name: "),
        "brands": ask_text("Brand (optional): ", required=False),
        "ingredients_text": ask_text("Ingredients (optional): ", required=False),
        "price": ask_float("Price: "),
        "stock": ask_int("Stock: "),
    }
    item = client.create_item(payload)
    print(f"Added: {format_item(item)}")


def view_all(client):
    items = client.list_items()
    if not items:
        print("Inventory is empty.")
        return
    for item in items:
        print(format_item(item))


def view_details(client):
    item = client.get_item(ask_int("Item ID: ", minimum=1))
    print_item_details(item)


def update_item(client):
    item_id = ask_int("Item ID: ", minimum=1)
    current = client.get_item(item_id)
    print(f"Current: {format_item(current)}")
    print("Press Enter to keep a value.")
    price = ask_float("New price: ", default=current["price"])
    stock = ask_int("New stock: ", default=current["stock"])
    updated = client.update_item(item_id, {"price": price, "stock": stock})
    print(f"Updated: {format_item(updated)}")


def delete_item(client):
    item_id = ask_int("Item ID: ", minimum=1)
    item = client.get_item(item_id)
    confirm = ask_text(f"Delete '{item['product']['product_name']}'? (y/n): ").lower()
    if confirm != "y":
        print("Cancelled.")
        return
    client.delete_item(item_id)
    print(f"Deleted item {item_id}.")


def ask_search_term():
    """Ask whether to search by barcode or name. Returns (barcode, name)."""
    while True:
        choice = ask_text("Search by (b)arcode or (n)ame? ").lower()
        if choice in ("b", "barcode"):
            return ask_text("Barcode: "), None
        if choice in ("n", "name"):
            return None, ask_text("Product name: ")
        print("  Please type 'b' or 'n'.")


def find_on_api(client):
    barcode, name = ask_search_term()
    results = client.search_api(barcode=barcode, name=name)
    print(f"Found {len(results)} result(s):")
    for product in results:
        print(f"  {product['code']}: {product['product_name']} ({product['brands'] or 'no brand'})")


def add_from_api(client):
    barcode, name = ask_search_term()
    payload = {"barcode": barcode} if barcode else {"name": name}
    payload["price"] = ask_float("Price: ")
    payload["stock"] = ask_int("Stock: ")
    item = client.add_from_api(payload)
    print(f"Added from OpenFoodFacts: {format_item(item)}")


MENU = {
    "1": ("Add a new inventory item", add_item),
    "2": ("View all items", view_all),
    "3": ("View item details", view_details),
    "4": ("Update item price / stock", update_item),
    "5": ("Delete an item", delete_item),
    "6": ("Find a product on OpenFoodFacts", find_on_api),
    "7": ("Add an item from OpenFoodFacts", add_from_api),
    "0": ("Quit", None),
}


def print_menu():
    print("\n=== Inventory Manager ===")
    for key, (label, _) in MENU.items():
        print(f"  {key}. {label}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inventory manager CLI")
    parser.add_argument("--url", default=DEFAULT_URL, help="Base URL of the Flask API")
    args = parser.parse_args(argv)
    client = InventoryClient(args.url)

    while True:
        print_menu()
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye!")
            return
        if choice not in MENU:
            print("Invalid option, please try again.")
            continue
        _, action = MENU[choice]
        try:
            action(client)
        except ApiError as exc:
            print(f"Error: {exc}")
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")


if __name__ == "__main__":
    main()
