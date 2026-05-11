import chess
class HistoryTable:

    def __init__(self):
        self.scores = [0] * 8192

    def record_cutoff(self, board : chess.Board, move : chess.Move, depth: int):

        color_offset = int(board.turn) << 12
        idx = color_offset | (move.from_square << 6) | move.to_square
        
        self.scores[idx] += depth * depth
        
        # Ngưỡng an toàn để tránh số quá lớn làm chậm so sánh trong Python
        if self.scores[idx] > 2000000:
            self.age()

    def get_score(self, board : chess.Board, move : chess.Move) -> int:
        """Lấy điểm số để sắp xếp nước đi."""
        idx = (int(board.turn) << 12) | (move.from_square << 6) | move.to_square
        return self.scores[idx]

    def age(self):
        """Làm giảm bảng điểm bằng phép dịch bit."""
        self.scores = [s >> 1 for s in self.scores]

    def clear(self):
        self.scores = [0] * 8192