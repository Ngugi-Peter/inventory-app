import unittest

import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        storage.reset()

    def test_seed_items_have_unique_ids(self):
        ids = [item["id"] for item in storage.get_all()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_next_id_is_one_more_than_max(self):
        self.assertEqual(storage.next_id(), 4)

    def test_next_id_on_empty_inventory(self):
        storage.inventory.clear()
        self.assertEqual(storage.next_id(), 1)

    def test_next_id_never_reuses_deleted_max_gap(self):
        storage.remove(2)
        self.assertEqual(storage.next_id(), 4)

    def test_get_one_found_and_missing(self):
        self.assertEqual(storage.get_one(1)["product"]["product_name"], "Coca-Cola")
        self.assertIsNone(storage.get_one(999))

    def test_add_and_remove(self):
        storage.add({"id": 10, "product": {}, "price": 1, "stock": 1})
        self.assertIsNotNone(storage.get_one(10))
        removed = storage.remove(10)
        self.assertEqual(removed["id"], 10)
        self.assertIsNone(storage.get_one(10))

    def test_remove_missing_returns_none(self):
        self.assertIsNone(storage.remove(999))


if __name__ == "__main__":
    unittest.main()
