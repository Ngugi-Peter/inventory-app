import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import requests

import cli


def run_with_inputs(action, client, inputs):
    out = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(out):
        action(client)
    return out.getvalue()


ITEM = {
    "id": 1,
    "status": 1,
    "product": {
        "code": "123",
        "product_name": "Oats",
        "brands": "OatCo",
        "ingredients_text": "Oats",
        "nutriscore_grade": "a",
    },
    "price": 2.5,
    "stock": 4,
}


class InputHelperTests(unittest.TestCase):
    def test_ask_int_retries_until_valid(self):
        out = io.StringIO()
        with patch("builtins.input", side_effect=["abc", "-3", "7"]), redirect_stdout(out):
            self.assertEqual(cli.ask_int("n: "), 7)
        self.assertIn("whole number", out.getvalue())

    def test_ask_int_default_on_enter(self):
        with patch("builtins.input", side_effect=[""]):
            self.assertEqual(cli.ask_int("n: ", default=9), 9)

    def test_ask_float_retries_until_valid(self):
        with patch("builtins.input", side_effect=["x", "-1", "2.5"]), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.ask_float("p: "), 2.5)

    def test_ask_text_required_retries(self):
        with patch("builtins.input", side_effect=["", "  ", "hi"]), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.ask_text("t: "), "hi")

    def test_ask_text_optional_allows_empty(self):
        with patch("builtins.input", side_effect=[""]):
            self.assertEqual(cli.ask_text("t: ", required=False), "")


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = cli.InventoryClient("http://test")

    @patch("cli.requests.request", side_effect=requests.exceptions.ConnectionError)
    def test_server_down_gives_friendly_error(self, _):
        with self.assertRaises(cli.ApiError) as ctx:
            self.client.list_items()
        self.assertIn("python app.py", str(ctx.exception))

    @patch("cli.requests.request", side_effect=requests.exceptions.Timeout)
    def test_timeout(self, _):
        with self.assertRaises(cli.ApiError):
            self.client.list_items()

    @patch("cli.requests.request")
    def test_http_error_uses_server_message(self, mock_request):
        response = MagicMock(ok=False, status_code=404)
        response.json.return_value = {"error": "Item 9 not found"}
        mock_request.return_value = response
        with self.assertRaises(cli.ApiError) as ctx:
            self.client.get_item(9)
        self.assertIn("Item 9 not found", str(ctx.exception))

    @patch("cli.requests.request")
    def test_unreadable_response(self, mock_request):
        response = MagicMock(ok=True, status_code=200)
        response.json.side_effect = ValueError
        mock_request.return_value = response
        with self.assertRaises(cli.ApiError):
            self.client.list_items()


class ActionTests(unittest.TestCase):
    def test_view_all_empty(self):
        client = MagicMock()
        client.list_items.return_value = []
        self.assertIn("empty", run_with_inputs(cli.view_all, client, []))

    def test_view_all_lists_items(self):
        client = MagicMock()
        client.list_items.return_value = [ITEM]
        self.assertIn("Oats", run_with_inputs(cli.view_all, client, []))

    def test_add_item_sends_payload(self):
        client = MagicMock()
        client.create_item.return_value = ITEM
        run_with_inputs(cli.add_item, client, ["Oats", "OatCo", "", "2.5", "4"])
        payload = client.create_item.call_args[0][0]
        self.assertEqual(payload["product_name"], "Oats")
        self.assertEqual(payload["price"], 2.5)
        self.assertEqual(payload["stock"], 4)

    def test_update_keeps_values_on_enter(self):
        client = MagicMock()
        client.get_item.return_value = ITEM
        client.update_item.return_value = ITEM
        run_with_inputs(cli.update_item, client, ["1", "", "10"])
        client.update_item.assert_called_once_with(1, {"price": 2.5, "stock": 10})

    def test_delete_requires_confirmation(self):
        client = MagicMock()
        client.get_item.return_value = ITEM
        out = run_with_inputs(cli.delete_item, client, ["1", "n"])
        client.delete_item.assert_not_called()
        self.assertIn("Cancelled", out)

    def test_delete_confirmed(self):
        client = MagicMock()
        client.get_item.return_value = ITEM
        run_with_inputs(cli.delete_item, client, ["1", "y"])
        client.delete_item.assert_called_once_with(1)

    def test_find_on_api_by_barcode(self):
        client = MagicMock()
        client.search_api.return_value = [ITEM["product"]]
        out = run_with_inputs(cli.find_on_api, client, ["b", "123"])
        client.search_api.assert_called_once_with(barcode="123", name=None)
        self.assertIn("Oats", out)

    def test_add_from_api_by_name(self):
        client = MagicMock()
        client.add_from_api.return_value = ITEM
        run_with_inputs(cli.add_from_api, client, ["n", "oats", "3", "5"])
        client.add_from_api.assert_called_once_with({"name": "oats", "price": 3.0, "stock": 5})

    def test_search_term_reprompts_on_bad_choice(self):
        with patch("builtins.input", side_effect=["x", "b", "42"]), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.ask_search_term(), ("42", None))


class MainLoopTests(unittest.TestCase):
    def test_api_error_does_not_crash_loop(self):
        out = io.StringIO()
        with patch("cli.requests.request", side_effect=requests.exceptions.ConnectionError), \
                patch("builtins.input", side_effect=["2", "0"]), redirect_stdout(out):
            cli.main([])
        text = out.getvalue()
        self.assertIn("Error:", text)
        self.assertIn("Goodbye", text)

    def test_invalid_menu_option(self):
        out = io.StringIO()
        with patch("builtins.input", side_effect=["99", "0"]), redirect_stdout(out):
            cli.main([])
        self.assertIn("Invalid option", out.getvalue())


if __name__ == "__main__":
    unittest.main()
