import unittest

from src.hash_table import HashTable
from src.linear_probing import LinearProbingHashTable


class HashTableContractTests:
    table_type = HashTable

    def make_table(self, capacity=8):
        return self.table_type(capacity=capacity)

    def test_empty_table_and_empty_string_key(self):
        table = self.make_table()
        self.assertEqual(len(table), 0)
        self.assertEqual(table.items(), [])
        self.assertNotIn("", table)

        table[""] = "empty key"
        self.assertEqual(table[""], "empty key")
        self.assertIn("", table)
        self.assertEqual(len(table), 1)

    def test_insert_lookup_update_and_items(self):
        table = self.make_table()
        table["first"] = 1
        table["second"] = 2
        table["first"] = 3

        self.assertEqual(table["first"], 3)
        self.assertEqual(table["second"], 2)
        self.assertEqual(len(table), 2)
        self.assertEqual(table.items(), [("first", 3), ("second", 2)])

    def test_delete_preserves_the_rest_of_a_collision_cluster(self):
        table = self.make_table(capacity=3)
        table["a"] = "one"
        table["d"] = "two"
        table["g"] = "three"

        del table["d"]
        self.assertEqual(table["a"], "one")
        self.assertEqual(table["g"], "three")
        self.assertNotIn("d", table)
        self.assertEqual(table.items(), [("a", "one"), ("g", "three")])

    def test_missing_keys_raise_key_error(self):
        table = self.make_table()
        with self.assertRaises(KeyError):
            _ = table["missing"]
        with self.assertRaises(KeyError):
            del table["missing"]

    def test_empty_values_are_still_members(self):
        table = self.make_table()
        table["none"] = None

        self.assertIn("none", table)
        self.assertIsNone(table["none"])

    def test_probe_count_checks_a_bounded_number_of_slots_or_nodes(self):
        table = self.make_table(capacity=3)
        table["a"] = 1
        table["d"] = 2

        self.assertGreaterEqual(table.probe_count("d"), 1)
        self.assertGreaterEqual(table.probe_count("missing"), 0)
        self.assertLessEqual(table.probe_count("missing"), table.capacity)
        self.assertEqual(len(table), 2)

    def test_horner_hash_has_the_same_steps(self):
        table = self.make_table(capacity=7)
        accumulators, index = table.hash_calculation("abc")

        self.assertEqual(accumulators, [97, 3105, 96354])
        self.assertEqual(index, 96354 % 7)

    def test_delete_last_item_and_invalid_inputs(self):
        table = self.make_table()
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
                self.table_type(capacity=capacity)


class ChainingHashTableTests(HashTableContractTests, unittest.TestCase):
    table_type = HashTable

    def test_probe_count_matches_chain_position_or_full_failed_scan(self):
        table = self.make_table(capacity=1)
        table["first"] = 1
        table["second"] = 2
        table["third"] = 3

        self.assertEqual(table.probe_count("third"), 1)
        self.assertEqual(table.probe_count("first"), 3)
        self.assertEqual(table.probe_count("missing"), 3)


class LinearProbingHashTableTests(HashTableContractTests, unittest.TestCase):
    table_type = LinearProbingHashTable

    def test_probe_wraps_from_last_slot_to_zero(self):
        table = self.make_table(capacity=5)
        table["c"] = "last"
        table["h"] = "wrapped"

        self.assertEqual(table.probe_trace("h"), [4, 0])
        self.assertEqual(table.buckets()[4], [("c", "last")])
        self.assertEqual(table.buckets()[0], [("h", "wrapped")])

    def test_full_table_updates_existing_keys_and_rejects_new_ones(self):
        table = self.make_table(capacity=4)
        for key in ("first", "second", "third", "fourth"):
            table[key] = key

        self.assertEqual(len(table), table.capacity)
        table["first"] = "updated"
        self.assertEqual(table["first"], "updated")
        with self.assertRaises(OverflowError):
            table["fifth"] = "fifth"
        self.assertEqual(table.probe_count("missing"), table.capacity)

    def test_delete_from_full_wrapped_cluster_allows_reinsertion(self):
        table = self.make_table(capacity=3)
        table["b"] = 1
        table["e"] = 2
        table["h"] = 3
        self.assertEqual(len(table), 3)

        del table["e"]
        self.assertEqual(table["b"], 1)
        self.assertEqual(table["h"], 3)
        table["k"] = 4
        self.assertEqual(table["k"], 4)
        self.assertEqual(len(table), 3)


if __name__ == "__main__":
    unittest.main()
