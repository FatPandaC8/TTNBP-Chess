import chess
import chess.polyglot
import os
import time
from multiprocessing import Manager
from concurrent.futures import ProcessPoolExecutor, as_completed
from engine.search.algorithms.bach.entry import EXACT, LOWER, UPPER, TTEntry
from engine.search.algorithms.bach.tt import TranspositionTable
from engine.search.interface import BaseSearch

# fmt: off
PIECE_VALUE = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN:  900, chess.KING:  20000,
}

MATE_SCORE         = 100_000
PARALLEL_THRESHOLD = 4      
INF                = float("inf")

_S_TT   = 10_000_000
_S_CAP  =  1_000_000
_S_PROM =    750_000
# fmt: on

_zobrist_hash = chess.polyglot.zobrist_hash

# Global Process pool prevents process spawning overhead crashes
GLOBAL_POOL = ProcessPoolExecutor(max_workers=max(1, os.cpu_count() or 4))

# FIX 1: Persistent global Manager and Shared Dictionary memory footprint
# This ensures your engine retains its brain memory across consecutive turns!
GLOBAL_MANAGER = Manager()
GLOBAL_SHARED_TT_DICT = GLOBAL_MANAGER.dict()


class _ParallelWorkerTimer:
    def __init__(self, end_time):
        self.end_time = end_time
        self.nodes = 0

    def should_stop(self):
        if self.end_time is None: return False
        return time.time() >= self.end_time


def _worker(args):
    """Evaluates a unique root move with full historical shared memory caching."""
    evaluator, fen, depth, move_uci, end_time = args
    board = chess.Board(fen)
    
    local_tt = TranspositionTable()
    if hasattr(local_tt, '_dict'):
        # Re-attach directly to the persistent global brain mapping
        local_tt._dict = GLOBAL_SHARED_TT_DICT
        
    searcher = SimpleSearcher(evaluator=evaluator, logger=None, tt=local_tt)
    searcher.timer = _ParallelWorkerTimer(end_time)
    searcher._root_ply = len(board.move_stack)

    move = chess.Move.from_uci(move_uci)
    board.push(move)
    try:
        # Full open window prevents false beta cuts across tasks
        score = -searcher.negamax(board, depth - 1, -INF, INF)
    except TimeoutError:
        score = None
    board.pop()
    
    return move_uci, score


class SimpleSearcher(BaseSearch):

    def __init__(self, evaluator, logger, tt):
        super().__init__(evaluator, logger)
        self.tt = tt
        # Sync main thread's local TT object to the same global backing dict
        if hasattr(self.tt, '_dict'):
            self.tt._dict = GLOBAL_SHARED_TT_DICT
        self._root_ply = 0

    def _eval(self, board):
        raw = self.evaluator.evaluate(board)
        return raw if board.turn == chess.WHITE else -raw

    def _terminal(self, board):
        if board.is_checkmate():
            return -(MATE_SCORE - (len(board.move_stack) - self._root_ply))
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        if board.is_repetition(2) or board.is_fifty_moves():
            return 0
        return None

    def _move_score(self, board, move, tt_move):
        if move == tt_move:  return _S_TT
        if board.is_capture(move):
            v  = board.piece_at(move.to_square)
            a  = board.piece_at(move.from_square)
            vt = v.piece_type if v else chess.PAWN
            at = a.piece_type if a else chess.PAWN
            return _S_CAP + PIECE_VALUE[vt] - PIECE_VALUE[at]
        if move.promotion:
            return _S_PROM + PIECE_VALUE.get(move.promotion, 0)
        return 0

    def _order(self, board, moves, tt_move=None):
        return sorted(moves, key=lambda m: self._move_score(board, m, tt_move), reverse=True)

    def quiescence(self, board, alpha, beta):
        if self.timer.should_stop(): raise TimeoutError
        self.timer.nodes += 1

        t = self._terminal(board)
        if t is not None: return t

        stand_pat = self._eval(board)
        if stand_pat >= beta: return stand_pat
        alpha = max(alpha, stand_pat)
        best = stand_pat

        # Generate moves: captures + checks + promotions
        moves = []
        for move in board.legal_moves:
            if (board.is_capture(move) or
                move.promotion or
                board.gives_check(move)):
                moves.append(move)

        for move in self._order(board, moves):
            board.push(move)
            score = -self.quiescence(board, -beta, -alpha)
            board.pop()
            if score > best:
                best = score
                alpha = max(alpha, score)
                if alpha >= beta: break
        return best

    def negamax(self, board, depth, alpha, beta):
        if self.timer.should_stop(): raise TimeoutError
        self.timer.nodes += 1

        alpha_orig, beta_orig = alpha, beta
        key = _zobrist_hash(board)

        tt_score, alpha, beta = self.tt.lookup(key, depth, alpha, beta)
        if tt_score is not None: return tt_score
        if alpha >= beta: return tt_score

        if depth >= 3 and not board.is_check():
            board.push(chess.Move.null())
            score = -self.negamax(board, depth - 1 - 2, -beta, -beta + 1)
            board.pop()
            if score >= beta:
                return beta

        if board.is_check() and depth == 0: depth = 1
        t = self._terminal(board)
        if t is not None: return t
        if depth == 0: return self.quiescence(board, alpha, beta)

        tt_move = self.tt.get_move(key)
        best, best_move = -INF, None

        for move in self._order(board, board.legal_moves, tt_move=tt_move):
            board.push(move)
            score = -self.negamax(board, depth - 1, -beta, -alpha)
            board.pop()

            if score > best:
                best = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta: break

        flag = UPPER if best <= alpha_orig else (LOWER if best >= beta_orig else EXACT)
        self.tt.store(TTEntry(key=key, depth=depth, score=best, flag=flag, move=best_move))
        return best

    def _search_serial(self, board, moves, depth):
        best_score, best_move = None, moves[0]
        try:
            for curr_depth in range(1, depth + 1):
                if self.timer.should_stop(): break
                iter_score, iter_move = None, None
                root_key = _zobrist_hash(board)
                ordered  = self._order(board, moves, tt_move=self.tt.get_move(root_key))

                for move in ordered:
                    if self.timer.should_stop(): raise TimeoutError
                    board.push(move)
                    score = -self.negamax(board, curr_depth - 1, -INF, INF)
                    board.pop()

                    if iter_move is None or score > iter_score:
                        iter_score, iter_move = score, move

                if iter_move is not None:
                    best_score, best_move = iter_score, iter_move
                    
        except TimeoutError:
            pass
        return best_score or 0, best_move

    def _search_parallel(self, board, moves, depth):
        root_key = _zobrist_hash(board)
        best_score, best_move = None, moves[0]

        for curr_depth in range(1, depth + 1):
            if self.timer.should_stop():
                break

            ordered = self._order(board, moves,
                                tt_move=self.tt.get_move(root_key))
            fen = board.fen()
            time_limit = getattr(self.timer, 'time_limit', None)
            start_time = time.time()
            end_time = (start_time + time_limit) if time_limit else None

            futures = {}
            for m in ordered:
                args = (self.evaluator, fen, curr_depth, m.uci(), end_time)
                futures[GLOBAL_POOL.submit(_worker, args)] = m

            # Collect results for this depth
            best_this_depth, best_move_this = None, None
            while futures:
                timeout = (end_time - time.time()) if end_time else None
                if timeout is not None and timeout <= 0:
                    break
                try:
                    for future in as_completed(futures.keys(), timeout=timeout):
                        move = futures.pop(future)
                        try:
                            _, score = future.result()
                            if score is not None:
                                if best_this_depth is None or score > best_this_depth:
                                    best_this_depth, best_move_this = score, move
                        except Exception:
                            pass
                except TimeoutError:
                    break

            for f in futures:
                f.cancel()

            if best_move_this is not None:
                best_score, best_move = best_this_depth, best_move_this
                # Store in TT for move ordering at next depth
                self.tt.store(TTEntry(key=root_key, depth=curr_depth,
                                    score=best_score, flag=EXACT,
                                    move=best_move))

        return best_score or 0, best_move

    def search(self, board, depth, time_limit=None):
        moves = list(board.legal_moves)
        if not moves: return 0, None

        self.timer.start(time_limit)
        self._root_ply = len(board.move_stack)

        if depth < PARALLEL_THRESHOLD:
            return self._search_serial(board, moves, depth)
        else:
            return self._search_parallel(board, moves, depth)