"""Flask API for the inventory app.

CRUD routes
    GET    /inventory          fetch all items
    GET    /inventory/<id>     fetch one item
    POST   /inventory          add an item
    PATCH  /inventory/<id>     update an item
    DELETE /inventory/<id>     remove an item

Helper routes
    GET    /openfoodfacts/search?barcode=...  (or ?name=...)   look up a product, no saving
    POST   /inventory/from-api                                 look up a product and add it
"""

from flask import Flask, jsonify, request

import off_client
import storage


def error(message, status):
    return jsonify({"error": message}), status


def validate_price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("price must be a number")
    if value < 0:
        raise ValueError("price must not be negative")
    return round(float(value), 2)


def validate_stock(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("stock must be a whole number")
    if value < 0:
        raise ValueError("stock must not be negative")
    return value


def validate_text(field, value):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value.strip()


def get_json_body():
    """Return the JSON body as a dict, or raise ValueError."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body


def build_item(product, price=0.0, stock=0):
    return {
        "id": storage.next_id(),
        "status": 1,
        "product": product,
        "price": validate_price(price),
        "stock": validate_stock(stock),
    }


def create_app():
    app = Flask(__name__)

    # ---------- CRUD ----------

    @app.get("/inventory")
    def list_items():
        return jsonify(storage.get_all())

    @app.get("/inventory/<int:item_id>")
    def get_item(item_id):
        item = storage.get_one(item_id)
        if item is None:
            return error(f"Item {item_id} not found", 404)
        return jsonify(item)

    @app.post("/inventory")
    def create_item():
        try:
            body = get_json_body()
            name = validate_text("product_name", body.get("product_name", ""))
            if not name:
                raise ValueError("product_name is required")

            product = {
                "code": validate_text("code", body.get("code", "")),
                "product_name": name,
                "brands": validate_text("brands", body.get("brands", "")),
                "ingredients_text": validate_text(
                    "ingredients_text", body.get("ingredients_text", "")
                ),
                "nutriscore_grade": validate_text(
                    "nutriscore_grade", body.get("nutriscore_grade", "")
                ),
            }
            item = build_item(product, body.get("price", 0), body.get("stock", 0))
        except ValueError as exc:
            return error(str(exc), 400)

        storage.add(item)
        return jsonify(item), 201

    @app.patch("/inventory/<int:item_id>")
    def update_item(item_id):
        item = storage.get_one(item_id)
        if item is None:
            return error(f"Item {item_id} not found", 404)

        try:
            body = get_json_body()
            unknown = set(body) - storage.TOP_LEVEL_EDITABLE - storage.PRODUCT_EDITABLE
            if unknown:
                raise ValueError(f"Cannot update field(s): {', '.join(sorted(unknown))}")
            if not body:
                raise ValueError("No fields to update")

            changes = {}
            product_changes = {}
            for field, value in body.items():
                if field == "price":
                    changes["price"] = validate_price(value)
                elif field == "stock":
                    changes["stock"] = validate_stock(value)
                else:
                    product_changes[field] = validate_text(field, value)
            if "product_name" in product_changes and not product_changes["product_name"]:
                raise ValueError("product_name must not be empty")
        except ValueError as exc:
            return error(str(exc), 400)

        # Apply only after everything validated, so a bad request changes nothing.
        item.update(changes)
        item["product"].update(product_changes)
        return jsonify(item)

    @app.delete("/inventory/<int:item_id>")
    def delete_item(item_id):
        item = storage.remove(item_id)
        if item is None:
            return error(f"Item {item_id} not found", 404)
        return jsonify({"message": f"Item {item_id} deleted", "item": item})

    # ---------- Helper routes (OpenFoodFacts) ----------

    @app.get("/openfoodfacts/search")
    def search_openfoodfacts():
        barcode = request.args.get("barcode")
        name = request.args.get("name")
        if not barcode and not name:
            return error("Provide a 'barcode' or 'name' query parameter", 400)

        try:
            if barcode:
                results = [off_client.fetch_by_barcode(barcode)]
            else:
                results = off_client.search_by_name(name)
        except ValueError as exc:
            return error(str(exc), 400)
        except off_client.ProductNotFound as exc:
            return error(str(exc), 404)
        except off_client.OpenFoodFactsError as exc:
            return error(str(exc), 502)

        return jsonify(results)

    @app.post("/inventory/from-api")
    def add_from_api():
        try:
            body = get_json_body()
            barcode = body.get("barcode")
            name = body.get("name")
            if not barcode and not name:
                raise ValueError("Provide a 'barcode' or 'name'")

            if barcode:
                product = off_client.fetch_by_barcode(barcode)
            else:
                product = off_client.search_by_name(name, limit=1)[0]

            if product["code"] and any(
                i["product"]["code"] == product["code"] for i in storage.get_all()
            ):
                return error(f"Product {product['code']} is already in inventory", 409)

            item = build_item(product, body.get("price", 0), body.get("stock", 0))
        except ValueError as exc:
            return error(str(exc), 400)
        except off_client.ProductNotFound as exc:
            return error(str(exc), 404)
        except off_client.OpenFoodFactsError as exc:
            return error(str(exc), 502)

        storage.add(item)
        return jsonify(item), 201

    # ---------- Error handlers ----------

    @app.errorhandler(404)
    def not_found(_):
        return error("Route not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_):
        return error("Method not allowed", 405)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
