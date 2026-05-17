from dataclasses import dataclass

EXACT = 0
LOWER = 1
UPPER = 2

@dataclass(slots=True)
class TTEntry:
    key: int
    depth: int
    score: float
    flag: int
    move: object = None