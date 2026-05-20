import multiprocessing as mp
import chess

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2


class SharedTranspositionTable:
    def __init__(self, size=1 << 20):
        self.size = size
        self.table = mp.Array('l', size * 4, lock=False)
        # each entry: [key, score, depth, move]

    def _index(self, key):
        return key % self.size

    def store(self, key, score, move, depth, flag):
        idx = self._index(key) * 4

        self.table[idx] = key
        self.table[idx + 1] = score
        self.table[idx + 2] = depth
        self.table[idx + 3] = move.to_square if move else -1

    def retrieve(self, key):
        idx = self._index(key) * 4

        stored_key = self.table[idx]
        if stored_key != key:
            return None

        score = self.table[idx + 1]
        depth = self.table[idx + 2]
        move_square = self.table[idx + 3]

        move = None
        if move_square != -1:
            move = chess.Move(0, move_square)

        return {
            "score": score,
            "depth": depth,
            "move": move
        }