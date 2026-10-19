import unittest
from unittest.mock import MagicMock, patch

import requests

import off_client


def fake_response(json_data=None, raise_http=None, bad_json=False):
    response = MagicMock()
    if raise_http:
        response.raise_for_status.side_effect = raise_http
    if bad_json:
        response.json.side_effect = ValueError("bad json")
    else:
        response.json.return_value = json_data
    return response


class FetchByBarcodeTests(unittest.TestCase):
    @patch("off_client.requests.get")
    def test_success_returns_cleaned_product(self, mock_get):
        mock_get.return_value = fake_response(
            {
                "status": 1,
                "product": {
                    "product_name": "Organic Almond Milk",
                    "brands": "Silk",
                    "ingredients_text": "Filtered water, almonds",
                    "extra_field": "dropped",
                },
            }
        )
        product = off_client.fetch_by_barcode("0000000000001")
        self.assertEqual(product["product_name"], "Organic Almond Milk")
        self.assertEqual(product["code"], "0000000000001")
        self.assertEqual(product["nutriscore_grade"], "")
        self.assertNotIn("extra_field", product)

    @patch("off_client.requests.get")
    def test_missing_name_gets_default(self, mock_get):
        mock_get.return_value = fake_response({"status": 1, "product": {"code": "1"}})
        self.assertEqual(off_client.fetch_by_barcode("1")["product_name"], "Unknown product")

    @patch("off_client.requests.get")
    def test_not_found_status_zero(self, mock_get):
        mock_get.return_value = fake_response({"status": 0})
        with self.assertRaises(off_client.ProductNotFound):
            off_client.fetch_by_barcode("999")

    def test_non_numeric_barcode_rejected_without_request(self):
        with patch("off_client.requests.get") as mock_get:
            with self.assertRaises(ValueError):
                off_client.fetch_by_barcode("abc")
            mock_get.assert_not_called()

    @patch("off_client.requests.get", side_effect=requests.exceptions.Timeout)
    def test_timeout(self, _):
        with self.assertRaises(off_client.OpenFoodFactsError):
            off_client.fetch_by_barcode("1")

    @patch("off_client.requests.get", side_effect=requests.exceptions.ConnectionError)
    def test_connection_error(self, _):
        with self.assertRaises(off_client.OpenFoodFactsError):
            off_client.fetch_by_barcode("1")

    @patch("off_client.requests.get")
    def test_http_error(self, mock_get):
        mock_get.return_value = fake_response(raise_http=requests.exceptions.HTTPError("500"))
        with self.assertRaises(off_client.OpenFoodFactsError):
            off_client.fetch_by_barcode("1")

    @patch("off_client.requests.get")
    def test_invalid_json(self, mock_get):
        mock_get.return_value = fake_response(bad_json=True)
        with self.assertRaises(off_client.OpenFoodFactsError):
            off_client.fetch_by_barcode("1")


class SearchByNameTests(unittest.TestCase):
    @patch("off_client.requests.get")
    def test_success(self, mock_get):
        mock_get.return_value = fake_response(
            {"products": [{"code": "1", "product_name": "A"}, {"code": "2", "product_name": "B"}]}
        )
        results = off_client.search_by_name("milk")
        self.assertEqual([p["product_name"] for p in results], ["A", "B"])

    @patch("off_client.requests.get")
    def test_no_results(self, mock_get):
        mock_get.return_value = fake_response({"products": []})
        with self.assertRaises(off_client.ProductNotFound):
            off_client.search_by_name("zzzzzz")

    def test_empty_name_rejected(self):
        for name in ("", "   ", None):
            with self.assertRaises(ValueError):
                off_client.search_by_name(name)

    @patch("off_client.requests.get", side_effect=requests.exceptions.ConnectionError)
    def test_connection_error(self, _):
        with self.assertRaises(off_client.OpenFoodFactsError):
            off_client.search_by_name("milk")


if __name__ == "__main__":
    unittest.main()
