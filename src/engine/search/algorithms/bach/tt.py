from engine.search.algorithms.bach.entry import EXACT, LOWER, UPPER


class TranspositionTable:
    def __init__(self, size=1_000_000):
        self.size = size
        self.table = [None] * size

        self.hits = 0
        self.misses = 0

    def index(self, key):
        return key % self.size

    # def probe(self, key, req_depth): old version (without flags)
    #     idx = self.index(key)

    #     entry = self.table[idx]

    #     # if the req_depth < depth -> meaning the higher depth uses the result from lower depth is kinda useless
    #     # so only allow the reverse to happen
    #     if (
    #         entry is not None
    #         and entry.key == key
    #         and entry.depth >= req_depth
    #     ):
    #         return entry
        
    #     return None
    
    def lookup(self, key, req_depth, alpha, beta):

        idx = self.index(key)

        entry = self.table[idx]

        if (
            entry is None
            or entry.key != key
            or entry.depth < req_depth
        ):
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
    
    def store(self, entry):
        idx = self.index(entry.key)

        old = self.table[idx]

        if (
            old is None
            or entry.depth >= old.depth
        ):
            self.table[idx] = entry

    def export_entries(self, min_depth=3):
        return {
            entry.key: entry
            for entry in self.table
            if entry is not None and entry.depth >= min_depth
        }

    # should only merge if depth is like above 6 for less noise in the main thread
    def merge_tt(self, incoming):
        for key, entry in incoming.items():

            idx = self.index(key)
            old = self.table[idx]

            if old is None or entry.depth > old.depth:
                self.table[idx] = entry