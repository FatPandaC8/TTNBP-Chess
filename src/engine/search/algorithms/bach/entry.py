from dataclasses import dataclass

EXACT = 0
LOWER = 1
UPPER = 2

@dataclass
class TTEntry:
    key: int # zobrist hashing
    depth: int
    score: int
    flag: int
    best_move: object = None