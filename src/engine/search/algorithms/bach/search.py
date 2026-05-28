import chess
import chess.polyglot
import time
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from engine.search.algorithms.bach.entry import EXACT, LOWER, UPPER, TTEntry
from engine.search.algorithms.bach.tt import TranspositionTable
from engine.search.interface import BaseSearch

MATE_SCORE = 100_000
INF        = float("inf")

_zobrist_hash = chess.polyglot.zobrist_hash


def _evaluate_move(
    fen:      str,
    move_uci: str,
    depth:    int,
    end_time: float | None,
    evaluator,
) -> tuple[str, float | None]:
    board = chess.Board(fen)
    move  = chess.Move.from_uci(move_uci)
    board.push(move)
    root_ply = len(board.move_stack) - 1

    worker = _WorkerSearcher(evaluator, end_time, root_ply)
    try:
        score = worker.minimax(board, depth - 1, -INF, INF, maximizing=board.turn == chess.WHITE)
        return move_uci, score
    except TimeoutError:
        return move_uci, None


class _WorkerSearcher:
    def __init__(self, evaluator, end_time: float | None, root_ply: int):
        self.evaluator = evaluator
        self.end_time  = end_time
        self.root_ply  = root_ply
        self.tt        = TranspositionTable()

    def _tick(self):
        if self.end_time and time.time() >= self.end_time:
            raise TimeoutError

    def _eval(self, board: chess.Board) -> float:
        return self.evaluator.evaluate(board)

    def _terminal(self, board: chess.Board) -> float | None:
        if board.is_checkmate():
            score = MATE_SCORE - (len(board.move_stack) - self.root_ply)
            return -score if board.turn == chess.WHITE else score
        if (board.is_stalemate()
                or board.is_insufficient_material()
                or board.is_repetition(2)
                or board.is_fifty_moves()):
            return 0
        return None

    def minimax(self, board: chess.Board, depth: int,
                alpha: float, beta: float, maximizing: bool) -> float:
        self._tick()

        alpha_orig = alpha
        key = _zobrist_hash(board)

        tt_score, alpha, beta = self.tt.lookup(key, depth, alpha, beta)
        if tt_score is not None:
            return tt_score
        if alpha >= beta:
            return alpha

        t = self._terminal(board)
        if t is not None:
            return t
        if depth == 0:
            return self._eval(board)

        best_move = None

        if maximizing:
            best = -INF
            for move in board.legal_moves:
                board.push(move)
                score = self.minimax(board, depth - 1, alpha, beta, False)
                board.pop()
                if score > best:
                    best      = score
                    best_move = move
                alpha = max(alpha, best)
                if alpha >= beta:
                    break
        else:
            best = INF
            for move in board.legal_moves:
                board.push(move)
                score = self.minimax(board, depth - 1, alpha, beta, True)
                board.pop()
                if score < best:
                    best      = score
                    best_move = move
                beta = min(beta, best)
                if alpha >= beta:
                    break

        flag = (EXACT if alpha_orig < best < beta
                else LOWER if best >= beta
                else UPPER)
        self.tt.store(TTEntry(key=key, depth=depth, score=best,
                              flag=flag, move=best_move))
        return best


class SimpleSearcher(BaseSearch):

    def __init__(self, evaluator, logger, tt: TranspositionTable):
        super().__init__(evaluator, logger)
        self.tt = tt

    def search(self, board: chess.Board, depth: int,
               time_limit: float | None = None) -> tuple[float, chess.Move]:
        moves = list(board.legal_moves)
        if not moves:
            return 0, None

        self.timer.start(time_limit)
        fen      = board.fen()
        root_key = _zobrist_hash(board)

        best_score: float      = -INF
        best_move:  chess.Move = moves[0]

        max_workers = min(len(moves), 8)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for curr_depth in range(1, depth + 1):
                if self.timer.should_stop():
                    break

                end_time = getattr(self.timer, 'end_time', None)

                future_to_move = {
                    pool.submit(_evaluate_move,
                                fen, m.uci(), curr_depth,
                                end_time, self.evaluator): m
                    for m in moves
                }

                remaining = (end_time - time.time()) if end_time else None
                done, pending = wait(
                    future_to_move.keys(),
                    timeout=remaining,
                    return_when=ALL_COMPLETED,
                )

                for f in pending:
                    f.cancel()

                iter_best_score: float            = -INF
                iter_best_move:  chess.Move | None = None

                for future in done:
                    move = future_to_move[future]
                    try:
                        _, score = future.result(timeout=0)
                    except Exception:
                        continue
                    if score is not None and score > iter_best_score:
                        iter_best_score = score
                        iter_best_move  = move

                if iter_best_move is not None:
                    best_score = iter_best_score
                    best_move  = iter_best_move
                    self.tt.store(TTEntry(
                        key=root_key, depth=curr_depth,
                        score=best_score, flag=EXACT, move=best_move,
                    ))

        return best_score, best_move