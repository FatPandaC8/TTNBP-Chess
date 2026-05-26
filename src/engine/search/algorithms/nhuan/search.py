import chess
from engine.evaluation.eval import Evaluator

INFINITY = 10**9

def minimax(board: chess.Board, depth: int, alpha: int, beta: int, is_max: bool, evaluator: Evaluator) -> int:
    """Minimax + alpha-beta pruning."""
    if depth == 0 or board.is_game_over():
        return evaluator.evaluate(board)

    if is_max:
        best = -INFINITY
        for move in board.legal_moves:
            board.push(move)
            score = minimax(board, depth - 1, alpha, beta, False, evaluator)
            board.pop()

            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break  # prune
        return best
    else:
        best = INFINITY
        for move in board.legal_moves:
            board.push(move)
            score = minimax(board, depth - 1, alpha, beta, True, evaluator)
            board.pop()

            if score < best:
                best = score
            if best < beta:
                beta = best
            if alpha >= beta:
                break  # prune
        return best


def find_best_move(board: chess.Board, depth: int, evaluator: Evaluator) -> chess.Move:
    """Chọn nước đi tốt nhất cho phía đang đi."""
    best_move = None

    if board.turn == chess.WHITE:
        best_score = -INFINITY
        for move in board.legal_moves:
            board.push(move)
            score = minimax(board, depth - 1, -INFINITY, INFINITY, False, evaluator)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = move
    else:
        best_score = INFINITY
        for move in board.legal_moves:
            board.push(move)
            score = minimax(board, depth - 1, -INFINITY, INFINITY, True, evaluator)
            board.pop()
            if score < best_score:
                best_score = score
                best_move = move

    return best_move