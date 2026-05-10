import chess

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2


class TTEntry:
    __slots__ = ('hash_key', 'score', 'best_move', 'depth', 'flag')

    def __init__(self, hash_key: int, score: int, best_move: chess.Move, depth: int, flag: int):
        self.hash_key = hash_key    # 64-bit Zobrist key
        self.score = score          # Giá trị lượng giá (int)
        self.best_move = best_move  # chess.Move object hoặc None
        self.depth = depth          # Độ sâu tìm kiếm còn lại (int)
        self.flag = flag            # EXACT, LOWER, hoặc UPPER


class TranspositionTable:
    """
    Bảng hoán vị dùng mảng cố định (Fixed-size list).
    Sử dụng bitmasking để tìm index thay vì dùng Dictionary.
    """
    def __init__(self, size_exponent=20):
        # size_exponent=20 tương đương với 2^20 entries (khoảng 1 triệu entries)
        self.size = 1 << size_exponent
        self.mask = self.size - 1
        self.table = [None] * self.size

    def store(self, hash_key: int, score: int, best_move: chess.Move, depth: int, flag: int):
        index = hash_key & self.mask
        entry = self.table[index]

        # Chiến lược thay thế (Replacement Scheme): 
        # Ghi đè nếu vị trí trống HOẶC vị trí cũ có độ sâu thấp hơn (Depth-preferred)
        if entry is None or entry.depth <= depth:
            self.table[index] = TTEntry(hash_key, score, best_move, depth, flag)

    def retrieve(self, hash_key: int):
        index = hash_key & self.mask
        entry = self.table[index]

        # Phải kiểm tra hash_key vì nhiều thế cờ khác nhau có thể trùng index (Collision)
        if entry is not None and entry.hash_key == hash_key:
            return entry
        return None

    def clear(self):
        self.table = [None] * self.size