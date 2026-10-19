"""Small client for the OpenFoodFacts API.

Docs: https://openfoodfacts.github.io/openfoodfacts-server/api/
"""

import requests

BASE_URL = "https://world.openfoodfacts.org"
# OpenFoodFacts asks API users to send a descriptive User-Agent.
HEADERS = {"User-Agent": "InventoryApp/1.0 (student project)"}
FIELDS = "code,product_name,brands,ingredients_text,nutriscore_grade"
TIMEOUT = 10


class OpenFoodFactsError(Exception):
    """Raised when the OpenFoodFacts API fails or returns something unusable."""


class ProductNotFound(OpenFoodFactsError):
    """Raised when OpenFoodFacts has no matching product."""


def _get_json(url, params=None):
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout as exc:
        raise OpenFoodFactsError("OpenFoodFacts request timed out") from exc
    except requests.exceptions.RequestException as exc:
        raise OpenFoodFactsError(f"OpenFoodFacts request failed: {exc}") from exc
    except ValueError as exc:
        raise OpenFoodFactsError("OpenFoodFacts returned invalid JSON") from exc


def _clean_product(product):
    """Keep only the fields we store, with safe defaults."""
    return {
        "code": str(product.get("code", "")),
        "product_name": product.get("product_name") or "Unknown product",
        "brands": product.get("brands") or "",
        "ingredients_text": product.get("ingredients_text") or "",
        "nutriscore_grade": product.get("nutriscore_grade") or "",
    }


def fetch_by_barcode(barcode):
    """Look up one product by barcode. Returns a cleaned product dict."""
    barcode = str(barcode).strip()
    if not barcode.isdigit():
        raise ValueError("Barcode must contain digits only")

    data = _get_json(f"{BASE_URL}/api/v2/product/{barcode}.json", {"fields": FIELDS})
    if data.get("status") != 1 or "product" not in data:
        raise ProductNotFound(f"No product found for barcode {barcode}")

    product = data["product"]
    product.setdefault("code", barcode)
    return _clean_product(product)


def search_by_name(name, limit=5):
    """Search products by name. Returns a list of cleaned product dicts."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Product name must not be empty")

    data = _get_json(
        f"{BASE_URL}/cgi/search.pl",
        {
            "search_terms": name,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": limit,
            "fields": FIELDS,
        },
    )
    products = data.get("products") or []
    if not products:
        raise ProductNotFound(f"No products found matching '{name}'")
    return [_clean_product(p) for p in products]
