# Inventory Manager (Flask + OpenFoodFacts + CLI)

A small inventory system:

- **Flask API** with RESTful CRUD routes and helper routes
- **Simulated database**: an in-memory Python list (`storage.py`) shaped like OpenFoodFacts data
- **OpenFoodFacts integration** (`off_client.py`): look up products by barcode or name
- **CLI** (`cli.py`): menu-driven interface that calls the API
- **Tests** (`tests/`): 74 unit tests, no internet needed (the external API is mocked)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Terminal 1 (server):

```bash
python app.py
```

Terminal 2 (CLI):

```bash
python cli.py                    # optional: --url http://127.0.0.1:5000
```

## Run the tests

```bash
python -m unittest discover -s tests -t . -v
```

(pytest also works if you have it installed: `pytest`)

## Route plan

| Route | Inputs | Output | What it changes | Triggered from the CLI by |
|---|---|---|---|---|
| `GET /inventory` | none | JSON list of all items | nothing | **2. View all items** |
| `GET /inventory/<id>` | `id` in URL | one item, or 404 | nothing | **3. View item details**; also used by Update and Delete to load/confirm the item |
| `POST /inventory` | JSON: `product_name` (required), `brands`, `ingredients_text`, `nutriscore_grade`, `code`, `price`, `stock` | the new item (201), or 400 | appends a new item to the array with a new ID | **1. Add a new inventory item** |
| `PATCH /inventory/<id>` | `id` in URL; JSON with any of `price`, `stock`, `product_name`, `brands`, `ingredients_text`, `nutriscore_grade`, `code` | the updated item, 404, or 400 | edits fields of one item; nothing changes if any value is invalid | **4. Update item price / stock** |
| `DELETE /inventory/<id>` | `id` in URL | confirmation + deleted item, or 404 | removes the item from the array | **5. Delete an item** (asks y/n first) |
| `GET /openfoodfacts/search` | query: `barcode` **or** `name` | list of matching products, 404 if none, 502 if OpenFoodFacts is down | nothing (read-only lookup) | **6. Find a product on OpenFoodFacts** |
| `POST /inventory/from-api` | JSON: `barcode` **or** `name`, plus optional `price`, `stock` | the new item (201); 404 not found, 409 already in inventory, 502 API failure | looks the product up on OpenFoodFacts and appends it to the array | **7. Add an item from OpenFoodFacts** |

## Data shape

Each item in the array looks like an OpenFoodFacts response plus our own fields:

```json
{
  "id": 3,
  "status": 1,
  "product": {
    "code": "0000000000001",
    "product_name": "Organic Almond Milk",
    "brands": "Silk",
    "ingredients_text": "Filtered water, almonds, cane sugar, ...",
    "nutriscore_grade": "b"
  },
  "price": 3.25,
  "stock": 30
}
```

`id` is assigned by the server (highest existing ID + 1, so IDs are never reused after a delete).
Because storage is just a list, **data resets every time the server restarts**.

## Error handling

- Invalid input (missing name, negative or non-numeric price/stock, bad JSON, unknown fields) returns `400` with `{"error": "..."}`.
- Unknown IDs return `404`.
- OpenFoodFacts failures (timeout, no connection, bad response) return `502`, and the CLI shows a readable message instead of crashing.
- The CLI re-prompts on invalid typed input and reports when the server is not running.

## Git workflow (for the Git Management part of the rubric)

```bash
git init
git add .
git commit -m "Initial project setup"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Then build each feature on its own branch, open a pull request on GitHub, merge it, and delete the branch:

```bash
git checkout -b feature/crud-routes
# ...make changes...
git add . && git commit -m "Add CRUD routes"
git push -u origin feature/crud-routes
# open a Pull Request on GitHub, merge it, then:
git checkout main && git pull
git branch -d feature/crud-routes
git push origin --delete feature/crud-routes     # or click "Delete branch" on GitHub
```

Suggested branches: `feature/storage-and-crud`, `feature/openfoodfacts-client`, `feature/cli`, `feature/tests`.
