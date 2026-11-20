"""A fixed-capacity hash table using linear probing."""

from typing import Generic, TypeVar

from src.hash_table import _horner_hash, _validate_key

Value = TypeVar("Value")


class _Entry(Generic[Value]):
    def __init__(self, key: str, value: Value):
        self.key = key
        self.value = value


class LinearProbingHashTable(Generic[Value]):
    """Store string keys in slots selected by Horner hashing and linear probing."""

    def __init__(self, capacity: int = 8):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._slots: list[_Entry[Value] | None] = [None] * capacity
        self._keys: list[str] = []
        self._size = 0

    @staticmethod
    def _validate_key(key: str) -> None:
        _validate_key(key)

    def hash_calculation(self, key: str) -> tuple[list[int], int]:
        """Return each Horner accumulator and the initial slot index."""
        return _horner_hash(key, self.capacity)

    def probe_trace(self, key: str) -> list[int]:
        """Return slots inspected to find a key or the first available slot."""
        _, start = self.hash_calculation(key)
        inspected = []
        for offset in range(self.capacity):
            index = (start + offset) % self.capacity
            inspected.append(index)
            entry = self._slots[index]
            if entry is None or entry.key == key:
                return inspected
        return inspected

    def probe_count(self, key: str) -> int:
        """Count inspected slots, including the matching or first empty slot."""
        return len(self.probe_trace(key))

    def __setitem__(self, key: str, value: Value) -> None:
        self._validate_key(key)
        for index in self.probe_trace(key):
            entry = self._slots[index]
            if entry is not None:
                if entry.key == key:
                    entry.value = value
                    return
                continue
            self._slots[index] = _Entry(key, value)
            self._keys.append(key)
            self._size += 1
            return
        raise OverflowError("hash table is full")

    def __getitem__(self, key: str) -> Value:
        self._validate_key(key)
        for index in self.probe_trace(key):
            entry = self._slots[index]
            if entry is None:
                break
            if entry.key == key:
                return entry.value
        raise KeyError(key)

    def __delitem__(self, key: str) -> None:
        self._validate_key(key)
        for index in self.probe_trace(key):
            entry = self._slots[index]
            if entry is None:
                break
            if entry.key == key:
                self._slots[index] = None
                self._keys.remove(key)
                self._size -= 1

                displaced = []
                next_index = (index + 1) % self.capacity
                while self._slots[next_index] is not None:
                    displaced.append(self._slots[next_index])
                    self._slots[next_index] = None
                    self._size -= 1
                    next_index = (next_index + 1) % self.capacity
                for displaced_entry in displaced:
                    self._place_existing(displaced_entry)
                return
        raise KeyError(key)

    def _place_existing(self, entry: _Entry[Value]) -> None:
        _, start = self.hash_calculation(entry.key)
        for offset in range(self.capacity):
            index = (start + offset) % self.capacity
            if self._slots[index] is None:
                self._slots[index] = entry
                self._size += 1
                return
        raise RuntimeError("no empty slot while restoring a probe cluster")

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
        """Return each slot as an empty list or a single key/value pair."""
        return [
            [] if entry is None else [(entry.key, entry.value)]
            for entry in self._slots
        ]
