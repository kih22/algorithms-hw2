import unittest

from src.base62 import decode, encode


class Base62Tests(unittest.TestCase):
    def test_zero_encodes_as_zero(self):
        self.assertEqual(encode(0), "0")

    def test_round_trip(self):
        for number in (1, 61, 62, 3844, 2**128):
            with self.subTest(number=number):
                self.assertEqual(decode(encode(number)), number)

    def test_rejects_negative_and_non_integer_inputs(self):
        with self.assertRaises(ValueError):
            encode(-1)
        for value in (True, 1.5, "12"):
            with self.subTest(value=value), self.assertRaises(TypeError):
                encode(value)

    def test_rejects_empty_or_invalid_codes(self):
        for code in ("", "!", "a-"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                decode(code)
        with self.assertRaises(TypeError):
            decode(12)

    def test_leading_zeroes_decode(self):
        self.assertEqual(decode("000a"), 10)


if __name__ == "__main__":
    unittest.main()
