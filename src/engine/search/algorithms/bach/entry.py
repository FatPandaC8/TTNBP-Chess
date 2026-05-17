from dataclasses import dataclass, field

EXACT = 0
LOWER = 1
UPPER = 2

@dataclass
class TTEntry:
    key: int
    depth: int
    score: float
    flag: int
    move: object = field(default=None)  # best move found at this node