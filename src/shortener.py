"""In-memory URL shortener backed by a configurable hash table."""

from urllib.parse import urlsplit

from src.base62 import encode
from src.hash_table import HashTable


class Shortener:
    def __init__(
        self,
        table_type: type[HashTable] = HashTable,
        table_capacity: int = 1024,
    ):
        self.table = table_type(capacity=table_capacity)
        self._codes = table_type(capacity=table_capacity)
        self._next_id = 0

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not isinstance(url, str):
            raise ValueError("URL must be a string")
        normalized = url.strip()
        if not normalized or any(character.isspace() for character in normalized):
            raise ValueError("URL must not be empty or contain whitespace")
        try:
            parsed = urlsplit(normalized)
            hostname = parsed.hostname
            parsed.port
        except ValueError as error:
            raise ValueError("URL is malformed") from error
        if parsed.scheme not in ("http", "https") or not parsed.netloc or not hostname:
            raise ValueError("URL must have an HTTP(S) scheme and host")
        return normalized

    def shorten(self, url: str) -> str:
        normalized = self._normalize_url(url)
        if normalized in self.table:
            return self.table[normalized]

        code = encode(self._next_id)
        self.table[normalized] = code
        self._codes[code] = normalized
        self._next_id += 1
        return code

    def expand(self, code: str) -> str:
        return self._codes[code]
