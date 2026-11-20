import unittest

from experiments.compare_hash_tables import measure_load_factors


class CompareHashTablesTests(unittest.TestCase):
    def test_measurements_are_reproducible_across_requested_load_factors(self):
        load_factors = (0.1, 0.5, 0.9)
        first_run = measure_load_factors(
            target_load_factors=load_factors,
            capacity=101,
            trials=2,
            seed=17,
        )
        second_run = measure_load_factors(
            target_load_factors=load_factors,
            capacity=101,
            trials=2,
            seed=17,
        )

        self.assertEqual(first_run, second_run)
        self.assertEqual(
            [row.target_load_factor for row in first_run],
            list(load_factors),
        )
        self.assertEqual([row.capacity for row in first_run], [101] * 3)
        for row in first_run:
            with self.subTest(load=row.target_load_factor):
                self.assertGreaterEqual(row.item_count, 1)
                self.assertGreaterEqual(row.chaining_successful, 1)
                self.assertGreaterEqual(row.linear_successful, 1)
                self.assertGreaterEqual(row.chaining_unsuccessful, 0)
                self.assertGreaterEqual(row.linear_unsuccessful, 1)


if __name__ == "__main__":
    unittest.main()
