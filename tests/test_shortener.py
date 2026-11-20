import unittest

from src.shortener import Shortener


class ShortenerTests(unittest.TestCase):
    def test_shortens_and_expands_urls(self):
        shortener = Shortener()
        code = shortener.shorten("https://example.com/a")

        self.assertEqual(code, "0")
        self.assertEqual(shortener.expand(code), "https://example.com/a")
        next_code = shortener.shorten("http://example.org/")
        self.assertEqual(shortener.expand(next_code), "http://example.org/")

    def test_same_url_gets_same_code_and_trims_outer_whitespace(self):
        shortener = Shortener()
        code = shortener.shorten("  https://example.com/path  ")

        self.assertEqual(shortener.shorten("https://example.com/path"), code)
        self.assertEqual(shortener.expand(code), "https://example.com/path")

    def test_encodes_ids_beyond_single_base62_digit(self):
        shortener = Shortener()
        for index in range(63):
            code = shortener.shorten(f"https://example.com/{index}")

        self.assertEqual(code, "10")
        self.assertEqual(shortener.expand(code), "https://example.com/62")

    def test_rejects_malformed_urls_and_unknown_codes(self):
        shortener = Shortener()
        for url in (
            "ftp://example.com/file",
            "https:///missing-host",
            "https://",
            "not a URL",
            42,
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                shortener.shorten(url)

        with self.assertRaises(KeyError):
            shortener.expand("unknown")


if __name__ == "__main__":
    unittest.main()
