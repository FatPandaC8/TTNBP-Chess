import time
import chess
import math
from engine.search.algorithms.bach.entry import EXACT, LOWER, UPPER, TTEntry
from engine.search.algorithms.bach.tt import TranspositionTable
from engine.search.interface import BaseSearch
from concurrent.futures import ProcessPoolExecutor
from engine.utils.logger import Logger

PIECE_VALUE = {
    chess.PAWN:   100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:   20000,
}

MAX_KILLERS    = 2
HISTORY_MAX    = 10_000
NULL_MOVE_R    = 3
LMR_MIN_DEPTH  = 3
LMR_MIN_MOVE   = 3      # first N moves (0-indexed) are never reduced

INF = float("inf")      # construct once, reuse everywhere

# Pre-compute LMR table [depth][move_index] at import time so _lmr_reduction
# never calls math.log() at runtime.  Table is large enough for any sane depth.
_MAX_DEPTH = 64
_MAX_MOVES = 128
LMR_TABLE = [
    [
        max(1, min(
            int(0.5 + math.log(max(d, 1)) * math.log(max(i + 1, 1)) / 2.25),
            d - 2          # never reduce so far that depth goes <= 0
        )) if (d >= LMR_MIN_DEPTH and i >= LMR_MIN_MOVE) else 0
        for i in range(_MAX_MOVES)
    ]
    for d in range(_MAX_DEPTH)
]

# Move-ordering score buckets (kept as module-level ints to avoid rebuilding)
_SCORE_TT       = 10_000_000
_SCORE_CAPTURE  =  1_000_000
_SCORE_KILLER   =    500_000
# history scores fill in below killer naturally


def split_moves(moves, k):
    moves = list(moves)
    chunk_size = math.ceil(len(moves) / k)
    return [moves[i * chunk_size: (i + 1) * chunk_size] for i in range(k)]


def helper_worker(args):
    evaluator, board_fen, depth, root_moves = args
    board = chess.Board(board_fen)
    local_tt = TranspositionTable()
    searcher = SimpleSearcher(evaluator=evaluator, logger=Logger(), tt=local_tt)
    
    # Run the pre-search
    searcher.helper_search(board, depth, root_moves)
    
    # OPTIMIZATION: Return raw tuples. 
    # This is significantly faster for ProcessPoolExecutor to handle.
    return local_tt.export_entries(min_depth=6)


class SimpleSearcher(BaseSearch):

    def __init__(self, evaluator, logger, tt):
        super().__init__(evaluator, logger)
        self.tt           = tt
        self.killer_moves = {}   # depth -> [move, ...]
        self.history      = {}   # (from_sq, to_sq) -> int

    def _store_killer(self, depth, move):
        killers = self.killer_moves.setdefault(depth, [])
        if move not in killers:
            killers.insert(0, move)
            if len(killers) > MAX_KILLERS:
                killers.pop()

    def _update_history(self, move, depth):
        k = (move.from_square, move.to_square)
        self.history[k] = min(self.history.get(k, 0) + depth * depth, HISTORY_MAX)

    # Move ordering
    # Inlined all sub-calls; single pass over moves builds score list,
    # then sorted() runs on plain ints, no closure attribute lookups.

    def _order_moves(self, board, moves, tt_move=None, depth=0):
        killers  = self.killer_moves.get(depth, ())
        history  = self.history
        pv       = PIECE_VALUE
        scored   = []

        for move in moves:
            if move == tt_move:
                s = _SCORE_TT

            elif board.is_capture(move):
                victim   = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                mvv_lva  = (pv[victim.piece_type] - pv[attacker.piece_type]
                            if victim and attacker else 0)
                s = _SCORE_CAPTURE + mvv_lva

            elif move in killers:
                # killers[0] is more recent, slightly higher score
                s = _SCORE_KILLER - killers.index(move)

            else:
                s = history.get((move.from_square, move.to_square), 0)

            scored.append((s, move))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    # LMR table lookup (zero Python overhead at search time)

    @staticmethod
    def _lmr(depth, move_idx, is_quiet, in_check):
        """Return reduction from pre-built table, 0 if conditions not met."""
        if not is_quiet or in_check:
            return 0
        d = min(depth,    _MAX_DEPTH - 1)
        i = min(move_idx, _MAX_MOVES - 1)
        return LMR_TABLE[d][i]   # already 0 for d < LMR_MIN_DEPTH or i < LMR_MIN_MOVE

    # Core search

    def minimax(self, board: chess.Board, depth: int, alpha: float, beta: float, isMax: bool):
        alpha_orig = alpha

        # Cache the key — used in TT lookup, store, and get_move
        key = hash(board._transposition_key())

        tt_score, alpha, beta = self.tt.lookup(key, depth, alpha, beta)
        if tt_score is not None:
            return tt_score
        if alpha >= beta:          # window collapsed by TT bound tightening
            return alpha

        in_check = board.is_check()

        # Check extension: never evaluate under check at the horizon
        if in_check and depth == 0:
            depth = 1

        if depth == 0 or board.is_game_over():
            score = self.evaluator.evaluate(board)
            self.tt.store(TTEntry(key=key, depth=0, score=score, flag=EXACT))
            return score

        # Null-move pruning
        if not in_check and depth >= NULL_MOVE_R + 1 and not board.is_variant_end():
            board.push(chess.Move.null())
            null_score = self.minimax(board, depth - 1 - NULL_MOVE_R, alpha, beta, not isMax)
            board.pop()

            if isMax and null_score >= beta:
                return beta
            if not isMax and null_score <= alpha:
                return alpha

        # Move loop
        tt_move = self.tt.get_move(key)
        moves   = self._order_moves(board, board.legal_moves, tt_move=tt_move, depth=depth)

        best      = -INF if isMax else INF
        best_move = None

        for i, move in enumerate(moves):
            board.push(move)

            is_quiet       = not board.is_capture(move) and move.promotion is None
            in_check_after = board.is_check()

            reduction = self._lmr(depth, i, is_quiet, in_check_after)

            if reduction:
                # Null-window probe at reduced depth
                score = self.minimax(board, depth - 1 - reduction, alpha, alpha + 1, not isMax)
                # Re-search at full depth only if the reduced search beat alpha
                if (isMax and score > alpha) or (not isMax and score < beta):
                    score = self.minimax(board, depth - 1, alpha, beta, not isMax)
            else:
                score = self.minimax(board, depth - 1, alpha, beta, not isMax)

            board.pop()

            if isMax:
                if score > best:
                    best      = score
                    best_move = move
                if score > alpha:
                    alpha = score
            else:
                if score < best:
                    best      = score
                    best_move = move
                if score < beta:
                    beta = score

            if alpha >= beta:
                if best_move and is_quiet:   # reuse flag computed above
                    self._store_killer(depth, best_move)
                    self._update_history(best_move, depth)
                break

        if best <= alpha_orig:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        else:
            flag = EXACT

        self.tt.store(TTEntry(key=key, depth=depth, score=best, flag=flag, move=best_move))
        return best

    # Helper search (parallel pre-search)
    def helper_search(self, board, depth, root_moves=None):
        is_max = board.turn == chess.WHITE
        alpha  = -INF
        beta   =  INF
        best   = -INF if is_max else INF

        for move in root_moves:
            board.push(move)
            score = self.minimax(board, depth - 1, alpha, beta, not is_max)
            board.pop()

            if is_max:
                if score > best:  best  = score
                if score > alpha: alpha = score
            else:
                if score < best:  best = score
                if score < beta:  beta = score

        return best

    # Root search with iterative deepening
    def search(self, board, depth, time_limit=None):
        start = time.time()

        moves = list(board.legal_moves)
        if not moves:
            return 0, None

        # parallel pre-search to warm the TT
        helper_depths = list(range(1, depth // 2 + 1))
        num_workers   = len(helper_depths)
        move_groups   = split_moves(moves, num_workers)

        tasks = [
            (self.evaluator, board.fen(), d, move_groups[i])
            for i, d in enumerate(helper_depths)
        ]

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            for helper_tt in executor.map(helper_worker, tasks):
                self.tt.merge_tt(helper_tt)   # merge as results arrive

        # iterative deepening
        best_score = None
        best_move  = moves[0]          # always-valid fallback
        root_key   = chess.polyglot.zobrist_hash(board)

        for curr_depth in range(1, depth + 1):
            if time_limit is not None and time.time() - start > time_limit:
                break

            current_best_score = None
            current_best_move  = None
            alpha = -INF
            beta  =  INF

            ordered = self._order_moves(
                board, moves,
                tt_move=self.tt.get_move(root_key),
                depth=0
            )

            for move in ordered:
                board.push(move)
                score = self.minimax(
                    board, curr_depth - 1, alpha, beta,
                    board.turn == chess.WHITE   # side to move after push
                )
                board.pop()

                if current_best_score is None or score > current_best_score:
                    current_best_score = score
                    current_best_move  = move

                if score > alpha:
                    alpha = score

                self.logger.log_search(best_score, best_move, curr_depth, 0)

            if current_best_move is not None:
                best_score = current_best_score
                best_move  = current_best_move

        return best_score if best_score is not None else 0, best_move