import http.client
import threading
import unittest
from urllib.parse import urlencode

from src.server import ShortenerServer
from src.shortener import Shortener


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.shortener = Shortener(table_capacity=1)
        self.server = ShortenerServer(("127.0.0.1", 0), self.shortener)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read().decode("utf-8")
        connection.close()
        return result

    def test_home_form_and_shortening_result(self):
        status, _, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn('action="/shorten"', page)

        status, _, page = self.request(
            "POST",
            "/shorten",
            urlencode({"url": "https://example.com/a?x=<tag>&y=2"}),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(status, 200)
        self.assertIn('id="short-link" href="/0"', page)
        status, _, table = self.request("GET", "/table")
        self.assertEqual(status, 200)
        self.assertIn("https://example.com/a?x=&lt;tag&gt;&amp;y=2", table)

    def test_short_link_redirects_and_unknown_code_is_not_found(self):
        self.shortener.shorten("https://example.com/original")

        status, headers, _ = self.request("GET", "/0")
        self.assertEqual(status, 302)
        self.assertEqual(dict(headers)["Location"], "https://example.com/original")

        status, _, _ = self.request("GET", "/unknown")
        self.assertEqual(status, 404)

    def test_invalid_form_returns_bad_request(self):
        status, _, page = self.request(
            "POST",
            "/shorten",
            urlencode({"url": "javascript:alert(1)"}),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(status, 400)
        self.assertIn("HTTP(S)", page)

    def test_table_shows_chained_nodes_and_horner_steps(self):
        self.shortener.shorten("https://example.com/first")
        self.shortener.shorten("https://example.com/second")

        status, _, page = self.request("GET", "/table")
        self.assertEqual(status, 200)
        self.assertIn('scope="col">버킷</th>', page)
        self.assertIn("&rarr;", page)
        self.assertIn("https://example.com/first", page)
        self.assertIn("Horner 해시 계산 보기", page)
        self.assertIn("ord(", page)
        self.assertIn("버킷 인덱스", page)


if __name__ == "__main__":
    unittest.main()
