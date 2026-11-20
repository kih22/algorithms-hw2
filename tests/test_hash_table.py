import unittest

from src.hash_table import HashTable


class HashTableTests(unittest.TestCase):
    def test_empty_table_and_empty_string_key(self):
        table = HashTable()
        self.assertEqual(len(table), 0)
        self.assertEqual(table.items(), [])
        self.assertNotIn("", table)

        table[""] = "empty key"
        self.assertEqual(table[""], "empty key")
        self.assertIn("", table)
        self.assertEqual(len(table), 1)

    def test_insert_lookup_update_and_items(self):
        table = HashTable()
        table["first"] = 1
        table["second"] = 2
        table["first"] = 3

        self.assertEqual(table["first"], 3)
        self.assertEqual(table["second"], 2)
        self.assertEqual(len(table), 2)
        self.assertEqual(table.items(), [("first", 3), ("second", 2)])

    def test_collisions_survive_deletion_of_another_key(self):
        table = HashTable(capacity=1)
        table["first"] = "one"
        table["second"] = "two"
        table["third"] = "three"

        del table["first"]
        self.assertEqual(table["second"], "two")
        self.assertEqual(table["third"], "three")
        self.assertNotIn("first", table)
        self.assertEqual(len(table), 2)

    def test_missing_keys_raise_key_error(self):
        table = HashTable()
        with self.assertRaises(KeyError):
            _ = table["missing"]
        with self.assertRaises(KeyError):
            del table["missing"]

    def test_empty_values_are_still_members(self):
        table = HashTable()
        table["none"] = None

        self.assertIn("none", table)
        self.assertIsNone(table["none"])

    def test_probe_count_matches_chain_position_or_full_failed_scan(self):
        table = HashTable(capacity=1)
        table["first"] = 1
        table["second"] = 2
        table["third"] = 3

        self.assertEqual(table.probe_count("third"), 1)
        self.assertEqual(table.probe_count("first"), 3)
        self.assertEqual(table.probe_count("missing"), 3)

    def test_delete_last_item_and_invalid_inputs(self):
        table = HashTable()
        table["only"] = 1
        del table["only"]
        self.assertEqual(len(table), 0)
        self.assertEqual(table.items(), [])

        with self.assertRaises(TypeError):
            table[1] = "not a string key"
        with self.assertRaises(TypeError):
            _ = table[1]
        with self.assertRaises(TypeError):
            del table[1]
        with self.assertRaises(TypeError):
            _ = 1 in table
        for capacity in (0, -1, True, 1.5, "1"):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                HashTable(capacity=capacity)


if __name__ == "__main__":
    unittest.main()
