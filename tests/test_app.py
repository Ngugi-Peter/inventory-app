import unittest
from unittest.mock import patch

import off_client
import storage
from app import create_app

FAKE_PRODUCT = {
    "code": "123456",
    "product_name": "Test Oats",
    "brands": "OatCo",
    "ingredients_text": "Oats",
    "nutriscore_grade": "a",
}


class AppTestCase(unittest.TestCase):
    def setUp(self):
        storage.reset()
        self.client = create_app().test_client()


class ReadTests(AppTestCase):
    def test_get_all(self):
        res = self.client.get("/inventory")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), 3)

    def test_get_one(self):
        res = self.client.get("/inventory/2")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["product"]["product_name"], "Nutella")

    def test_get_one_missing(self):
        res = self.client.get("/inventory/999")
        self.assertEqual(res.status_code, 404)
        self.assertIn("error", res.get_json())

    def test_non_integer_id_is_404(self):
        self.assertEqual(self.client.get("/inventory/abc").status_code, 404)

    def test_unknown_route_returns_json_404(self):
        res = self.client.get("/nope")
        self.assertEqual(res.status_code, 404)
        self.assertIn("error", res.get_json())

    def test_wrong_method_returns_405(self):
        self.assertEqual(self.client.put("/inventory").status_code, 405)


class CreateTests(AppTestCase):
    def test_create_success(self):
        res = self.client.post(
            "/inventory",
            json={"product_name": " Tea ", "brands": "Brew", "price": 2.5, "stock": 7},
        )
        self.assertEqual(res.status_code, 201)
        body = res.get_json()
        self.assertEqual(body["id"], 4)
        self.assertEqual(body["product"]["product_name"], "Tea")
        self.assertEqual(body["stock"], 7)
        self.assertEqual(len(storage.get_all()), 4)

    def test_create_defaults_price_and_stock(self):
        body = self.client.post("/inventory", json={"product_name": "Water"}).get_json()
        self.assertEqual(body["price"], 0.0)
        self.assertEqual(body["stock"], 0)

    def test_create_requires_name(self):
        for payload in ({}, {"product_name": ""}, {"product_name": "   "}):
            res = self.client.post("/inventory", json=payload)
            self.assertEqual(res.status_code, 400, payload)
        self.assertEqual(len(storage.get_all()), 3)

    def test_create_rejects_bad_numbers(self):
        bad = [
            {"price": -1},
            {"price": "free"},
            {"price": True},
            {"stock": -5},
            {"stock": 1.5},
            {"stock": "10"},
        ]
        for extra in bad:
            res = self.client.post("/inventory", json={"product_name": "X", **extra})
            self.assertEqual(res.status_code, 400, extra)
        self.assertEqual(len(storage.get_all()), 3)

    def test_create_rejects_non_json_body(self):
        res = self.client.post("/inventory", data="not json")
        self.assertEqual(res.status_code, 400)

    def test_create_rejects_non_string_name(self):
        res = self.client.post("/inventory", json={"product_name": 123})
        self.assertEqual(res.status_code, 400)


class UpdateTests(AppTestCase):
    def test_patch_price_and_stock(self):
        res = self.client.patch("/inventory/1", json={"price": 2.25, "stock": 5})
        self.assertEqual(res.status_code, 200)
        item = storage.get_one(1)
        self.assertEqual(item["price"], 2.25)
        self.assertEqual(item["stock"], 5)

    def test_patch_product_field(self):
        res = self.client.patch("/inventory/1", json={"brands": "New Brand"})
        self.assertEqual(res.get_json()["product"]["brands"], "New Brand")

    def test_patch_leaves_other_fields_alone(self):
        self.client.patch("/inventory/1", json={"stock": 1})
        self.assertEqual(storage.get_one(1)["price"], 1.99)

    def test_patch_missing_item(self):
        res = self.client.patch("/inventory/999", json={"stock": 1})
        self.assertEqual(res.status_code, 404)

    def test_patch_cannot_change_id(self):
        res = self.client.patch("/inventory/1", json={"id": 50})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(storage.get_one(1)["id"], 1)

    def test_patch_empty_body(self):
        self.assertEqual(self.client.patch("/inventory/1", json={}).status_code, 400)

    def test_patch_invalid_value_changes_nothing(self):
        res = self.client.patch("/inventory/1", json={"price": 9.99, "stock": -1})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(storage.get_one(1)["price"], 1.99)

    def test_patch_empty_name_rejected(self):
        res = self.client.patch("/inventory/1", json={"product_name": " "})
        self.assertEqual(res.status_code, 400)


class DeleteTests(AppTestCase):
    def test_delete_success(self):
        res = self.client.delete("/inventory/1")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(storage.get_one(1))
        self.assertEqual(self.client.get("/inventory/1").status_code, 404)

    def test_delete_missing(self):
        self.assertEqual(self.client.delete("/inventory/999").status_code, 404)

    def test_ids_not_reused_after_deleting_lower_id(self):
        self.client.delete("/inventory/1")
        body = self.client.post("/inventory", json={"product_name": "New"}).get_json()
        self.assertEqual(body["id"], 4)


class OpenFoodFactsRouteTests(AppTestCase):
    def test_search_requires_a_term(self):
        self.assertEqual(self.client.get("/openfoodfacts/search").status_code, 400)

    @patch("app.off_client.fetch_by_barcode", return_value=FAKE_PRODUCT)
    def test_search_by_barcode(self, mock_fetch):
        res = self.client.get("/openfoodfacts/search?barcode=123456")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()[0]["product_name"], "Test Oats")
        mock_fetch.assert_called_once_with("123456")

    @patch("app.off_client.search_by_name", return_value=[FAKE_PRODUCT])
    def test_search_by_name(self, _):
        res = self.client.get("/openfoodfacts/search?name=oats")
        self.assertEqual(res.status_code, 200)

    @patch("app.off_client.fetch_by_barcode", side_effect=off_client.ProductNotFound("nope"))
    def test_search_not_found(self, _):
        self.assertEqual(self.client.get("/openfoodfacts/search?barcode=1").status_code, 404)

    @patch("app.off_client.fetch_by_barcode", side_effect=ValueError("Barcode must contain digits only"))
    def test_search_bad_barcode(self, _):
        self.assertEqual(self.client.get("/openfoodfacts/search?barcode=abc").status_code, 400)

    @patch("app.off_client.fetch_by_barcode", side_effect=off_client.OpenFoodFactsError("down"))
    def test_search_api_failure_is_502(self, _):
        self.assertEqual(self.client.get("/openfoodfacts/search?barcode=1").status_code, 502)

    @patch("app.off_client.fetch_by_barcode", return_value=FAKE_PRODUCT)
    def test_add_from_api_by_barcode(self, _):
        res = self.client.post(
            "/inventory/from-api", json={"barcode": "123456", "price": 3, "stock": 10}
        )
        self.assertEqual(res.status_code, 201)
        body = res.get_json()
        self.assertEqual(body["id"], 4)
        self.assertEqual(body["product"]["brands"], "OatCo")
        self.assertEqual(body["stock"], 10)
        self.assertIsNotNone(storage.get_one(4))

    @patch("app.off_client.search_by_name", return_value=[FAKE_PRODUCT])
    def test_add_from_api_by_name(self, _):
        res = self.client.post("/inventory/from-api", json={"name": "oats"})
        self.assertEqual(res.status_code, 201)

    @patch("app.off_client.fetch_by_barcode", return_value=FAKE_PRODUCT)
    def test_add_from_api_duplicate_is_409(self, _):
        self.client.post("/inventory/from-api", json={"barcode": "123456"})
        res = self.client.post("/inventory/from-api", json={"barcode": "123456"})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(len(storage.get_all()), 4)

    def test_add_from_api_requires_term(self):
        self.assertEqual(self.client.post("/inventory/from-api", json={}).status_code, 400)

    @patch("app.off_client.fetch_by_barcode", return_value=FAKE_PRODUCT)
    def test_add_from_api_bad_price_not_saved(self, _):
        res = self.client.post("/inventory/from-api", json={"barcode": "123456", "price": -2})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(len(storage.get_all()), 3)

    @patch("app.off_client.fetch_by_barcode", side_effect=off_client.OpenFoodFactsError("down"))
    def test_add_from_api_failure_is_502(self, _):
        res = self.client.post("/inventory/from-api", json={"barcode": "1"})
        self.assertEqual(res.status_code, 502)
        self.assertEqual(len(storage.get_all()), 3)


if __name__ == "__main__":
    unittest.main()
