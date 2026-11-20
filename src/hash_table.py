"""A fixed-capacity hash table using separate chaining."""

from typing import Generic, TypeVar

Value = TypeVar("Value")


class _Node(Generic[Value]):
    def __init__(self, key: str, value: Value, next_node: "_Node[Value] | None" = None):
        self.key = key
        self.value = value
        self.next = next_node


class HashTable(Generic[Value]):
    """Store string keys in buckets selected by a Horner hash."""

    def __init__(self, capacity: int = 8):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._buckets: list[_Node[Value] | None] = [None] * capacity
        self._keys: list[str] = []
        self._size = 0

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str):
            raise TypeError("key must be a string")

    def hash_calculation(self, key: str) -> tuple[list[int], int]:
        """Return each Horner accumulator and the resulting bucket index."""
        self._validate_key(key)
        values = []
        accumulator = 0
        for character in key:
            accumulator = accumulator * 31 + ord(character)
            values.append(accumulator)
        return values, accumulator % self.capacity

    def _bucket_index(self, key: str) -> int:
        return self.hash_calculation(key)[1]

    def __setitem__(self, key: str, value: Value) -> None:
        self._validate_key(key)
        index = self._bucket_index(key)
        node = self._buckets[index]
        while node is not None:
            if node.key == key:
                node.value = value
                return
            node = node.next
        self._buckets[index] = _Node(key, value, self._buckets[index])
        self._keys.append(key)
        self._size += 1

    def __getitem__(self, key: str) -> Value:
        self._validate_key(key)
        node = self._buckets[self._bucket_index(key)]
        while node is not None:
            if node.key == key:
                return node.value
            node = node.next
        raise KeyError(key)

    def __delitem__(self, key: str) -> None:
        self._validate_key(key)
        index = self._bucket_index(key)
        previous = None
        node = self._buckets[index]
        while node is not None:
            if node.key == key:
                if previous is None:
                    self._buckets[index] = node.next
                else:
                    previous.next = node.next
                self._keys.remove(key)
                self._size -= 1
                return
            previous, node = node, node.next
        raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        self._validate_key(key)
        try:
            self[key]
        except KeyError:
            return False
        return True

    def __len__(self) -> int:
        return self._size

    def items(self) -> list[tuple[str, Value]]:
        """Return key/value pairs in insertion order."""
        return [(key, self[key]) for key in self._keys]

    def buckets(self) -> list[list[tuple[str, Value]]]:
        """Return a snapshot of the keys and values grouped by bucket."""
        result = []
        for head in self._buckets:
            bucket = []
            node = head
            while node is not None:
                bucket.append((node.key, node.value))
                node = node.next
            result.append(bucket)
        return result
