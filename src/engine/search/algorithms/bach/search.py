import chess
from engine.search.interface import BaseSearch

PIECE_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

class SimpleSearcher(BaseSearch):
    def __init__(self, evaluator, logger):
        super().__init__(evaluator, logger)

    def _order_moves(self, board,  moves: list):
        def score(move):
            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)

                if victim is None or attacker is None:
                    return 0

                return PIECE_VALUE[victim.piece_type] - PIECE_VALUE[attacker.piece_type]

            return 0

        return sorted(moves, key=score, reverse=True)

    def minimax(self, board: chess.Board, depth: int, alpha: float, beta: float, isMax: bool):
        if depth == 0 or board.is_game_over():
            return self.evaluator.evaluate(board)
        
        if isMax:
            best = -float("inf")

            moves = self._order_moves(board, list(board.legal_moves))

            for move in moves:
                board.push(move)

                score = self.minimax(board, depth - 1, alpha, beta, False) # False to switch turn

                board.pop()

                best = max(best, score)
                alpha = max(alpha, best) # get the best so far
                if alpha >= beta:
                    break

            return best
        else:
            best = float("inf")

            moves = self._order_moves(board, list(board.legal_moves))

            for move in moves:
                board.push(move)

                score = self.minimax(board, depth - 1, alpha, beta, True)

                board.pop()

                best = min(best, score)
                beta = min(beta, best)
                if alpha >= beta:
                    break

            return best

    def search(self, board, depth, time_limit = None):
        best_move = None

        for curr_depth in range(1, depth + 1):
            best_score = -float("inf")

            alpha = -float("inf")
            beta = float("inf")

            for move in self._order_moves(board, board.legal_moves):
                board.push(move)

                score = self.minimax(board, curr_depth - 1, alpha, beta, False)

                board.pop()

                if score > best_score:
                    best_score = score
                    best_move = move

                alpha = max(alpha, best_score) # the last node (the root node is a maxi so redo this)

                self.logger.log_search(best_score, best_move, curr_depth, 0)

        return best_score, best_move