from engine.search.algorithms.bach.entry import EXACT, LOWER, UPPER


class TranspositionTable:
    def __init__(self, size=1_000_000):
        self.size = size
        self.table = [None] * size
        self.index_map = {}  # key -> idx, for O(1) export without full scan

        self.hits = 0
        self.misses = 0

    def _index(self, key):
        return key % self.size

    def lookup(self, key, req_depth, alpha, beta):
        idx = self._index(key)
        entry = self.table[idx]

        if entry is None or entry.key != key or entry.depth < req_depth:
            self.misses += 1
            return None, alpha, beta

        self.hits += 1

        if entry.flag == EXACT:
            return entry.score, alpha, beta
        elif entry.flag == LOWER:
            alpha = max(alpha, entry.score)
        elif entry.flag == UPPER:
            beta = min(beta, entry.score)

        if alpha >= beta:
            return entry.score, alpha, beta

        return None, alpha, beta

    def get_move(self, key):
        """Return the best move stored for this key, or None."""
        idx = self._index(key)
        entry = self.table[idx]
        if entry is not None and entry.key == key:
            return getattr(entry, 'move', None)
        return None

    def store(self, entry):
        idx = self._index(entry.key)
        old = self.table[idx]

        # Two-tier replacement:
        # Always replace if same key (fresh info), or if new entry searched deeper
        if old is None or old.key == entry.key or entry.depth >= old.depth:
            self.table[idx] = entry
            self.index_map[entry.key] = idx

    def export_entries(self, min_depth=3):
        """O(1) per entry via index_map instead of scanning the full table."""
        result = {}
        for key, idx in self.index_map.items():
            entry = self.table[idx]
            if entry is not None and entry.key == key and entry.depth >= min_depth:
                result[key] = entry
        return result

    def merge_tt(self, incoming):
        for key, entry in incoming.items():
            idx = self._index(key)
            old = self.table[idx]
            if old is None or entry.depth > old.depth:
                self.table[idx] = entry
                self.index_map[entry.key] = idx