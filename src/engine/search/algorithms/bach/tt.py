import chess

from engine.search.algorithms.bach.entry import EXACT, LOWER, UPPER, TTEntry


class TranspositionTable:
    def __init__(self, size=1_000_000):
        self.size = size
        self.table = [None] * size
        # REMOVED: self.index_map (Too slow to update during minimax)

    def _index(self, key):
        return key % self.size

    def lookup(self, key, req_depth, alpha, beta):
        idx = key % self.size
        entry = self.table[idx]

        if entry is None or entry.key != key or entry.depth < req_depth:
            return None, alpha, beta

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
        """
        Fetches only the best move for a given key.
        Used at the start of the move loop to improve move ordering.
        """
        idx = key % self.size
        entry = self.table[idx]
        
        # Verify entry exists and the key matches (to handle hash collisions)
        if entry is not None and entry.key == key:
            return entry.move
        return None

    def store(self, entry):
        idx = entry.key % self.size
        old = self.table[idx]
        # Always replace if same key or if new entry is deeper
        if old is None or old.key == entry.key or entry.depth >= old.depth:
            self.table[idx] = entry

    def export_entries(self, min_depth=6):
        """
        Scan the table once at the end. 
        Export as tuples to maximize multiprocessing speed.
        """
        # (key, depth, score, flag, move_uci)
        return [
            (e.key, e.depth, e.score, e.flag, e.move.uci() if e.move else None)
            for e in self.table 
            if e is not None and e.depth >= min_depth
        ]

    def merge_tt(self, incoming_tuples):
        """Merges raw tuples back into TTEntry objects."""
        for key, depth, score, flag, move_uci in incoming_tuples:
            idx = key % self.size
            old = self.table[idx]
            if old is None or depth > old.depth:
                move = chess.Move.from_uci(move_uci) if move_uci else None
                self.table[idx] = TTEntry(key, depth, score, flag, move)