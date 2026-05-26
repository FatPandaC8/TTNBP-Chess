import chess
import chess.polyglot
import os
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

MAX_KILLERS   = 2
HISTORY_MAX   = 10_000
NULL_MOVE_R   = 3
LMR_MIN_DEPTH = 3
LMR_MIN_MOVE  = 3

INF = float("inf")

_MAX_DEPTH = 64
_MAX_MOVES = 128
LMR_TABLE = [
    [
        max(1, min(
            int(0.5 + math.log(max(d, 1)) * math.log(max(i + 1, 1)) / 2.25),
            d - 2
        )) if (d >= LMR_MIN_DEPTH and i >= LMR_MIN_MOVE) else 0
        for i in range(_MAX_MOVES)
    ]
    for d in range(_MAX_DEPTH)
]

_SCORE_TT      = 10_000_000
_SCORE_CAPTURE =  1_000_000
_SCORE_KILLER  =    500_000


def _board_key(board: chess.Board) -> int:
    return chess.polyglot.zobrist_hash(board)


def split_moves(moves, k):
    moves = list(moves)
    chunk_size = math.ceil(len(moves) / k)
    return [moves[i * chunk_size: (i + 1) * chunk_size] for i in range(k)]


def helper_worker(args):
    """
    Plain alpha-beta, no LMR, no null-move — keeps TT entries clean.
    We only want move ordering hints, not pruned-score bounds.
    """
    evaluator, board_fen, depth, root_moves = args
    board    = chess.Board(board_fen)
    local_tt = TranspositionTable()
    searcher = SimpleSearcher(evaluator=evaluator, logger=Logger(), tt=local_tt)
    searcher.helper_search(board, depth, root_moves)
    # Only export deep entries so shallow noise doesn't pollute main TT
    return local_tt.export_entries(min_depth=4)


class SimpleSearcher(BaseSearch):

    def __init__(self, evaluator, logger, tt):
        super().__init__(evaluator, logger)
        self.tt           = tt
        self.killer_moves = {}
        self.history      = {}
        # When True, minimax skips LMR and null-move (used in pre-search)
        self._plain_search = False

    #  Heuristic tables

    def _store_killer(self, depth, move):
        killers = self.killer_moves.setdefault(depth, [])
        if move not in killers:
            killers.insert(0, move)
            if len(killers) > MAX_KILLERS:
                killers.pop()

    def _update_history(self, move, depth):
        k = (move.from_square, move.to_square)
        self.history[k] = min(self.history.get(k, 0) + depth * depth, HISTORY_MAX)

    def _order_moves(self, board, moves, tt_move=None, depth=0):
        killers = self.killer_moves.get(depth, ())
        history = self.history
        pv      = PIECE_VALUE
        scored  = []

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
                s = _SCORE_KILLER - killers.index(move)
            else:
                s = history.get((move.from_square, move.to_square), 0)

            scored.append((s, move))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    @staticmethod
    def _lmr(depth, move_idx, is_quiet, in_check):
        if not is_quiet or in_check:
            return 0
        d = min(depth,    _MAX_DEPTH - 1)
        i = min(move_idx, _MAX_MOVES - 1)
        return LMR_TABLE[d][i]

    #  Core alpha-beta

    def minimax(self, board: chess.Board, depth: int, alpha: float, beta: float, isMax: bool):
        self.timer.nodes += 1
        if self.timer.should_stop():
            raise TimeoutError

        alpha_orig = alpha
        key        = _board_key(board)

        tt_score, alpha, beta = self.tt.lookup(key, depth, alpha, beta)
        if tt_score is not None:
            return tt_score
        if alpha >= beta:
            return alpha

        in_check = board.is_check()

        if in_check and depth == 0:
            depth = 1

        if depth == 0 or board.is_game_over():
            score = self.evaluator.evaluate(board)
            self.tt.store(TTEntry(key=key, depth=0, score=score, flag=EXACT))
            return score

        # Null-move pruning — disabled during pre-search to avoid storing
        # aggressive LOWER bounds that the main search would trust blindly.
        if (not self._plain_search
                and not in_check
                and depth >= NULL_MOVE_R + 1
                and not board.is_variant_end()):
            board.push(chess.Move.null())
            null_score = self.minimax(board, depth - 1 - NULL_MOVE_R, alpha, beta, not isMax)
            board.pop()

            if isMax and null_score >= beta:
                return null_score
            if not isMax and null_score <= alpha:
                return null_score

        tt_move = self.tt.get_move(key)
        moves   = self._order_moves(board, board.legal_moves, tt_move=tt_move, depth=depth)

        best      = -INF if isMax else INF
        best_move = None

        for i, move in enumerate(moves):
            is_quiet = not board.is_capture(move) and move.promotion is None

            board.push(move)
            in_check_after = board.is_check()

            # LMR - disabled during pre-search for same reason as null-move
            reduction = (0 if self._plain_search
                         else self._lmr(depth, i, is_quiet, in_check_after))

            if reduction:
                if isMax:
                    score = self.minimax(board, depth - 1 - reduction, alpha, alpha + 1, False)
                    if score > alpha:
                        score = self.minimax(board, depth - 1, alpha, beta, False)
                else:
                    score = self.minimax(board, depth - 1 - reduction, beta - 1, beta, True)
                    if score < beta:
                        score = self.minimax(board, depth - 1, alpha, beta, True)
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
                if best_move and is_quiet:
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

    #  Helper / pre-search (plain alpha-beta, no LMR, no null-move)

    def helper_search(self, board, depth, root_moves=None):
        self._plain_search = True
        is_max = board.turn == chess.WHITE
        best   = -INF if is_max else INF

        for move in root_moves:
            board.push(move)
            score = self.minimax(board, depth - 1, -INF, INF, not is_max)
            board.pop()

            if is_max:
                best = max(best, score)
            else:
                best = min(best, score)

        self._plain_search = False
        return best

    #  Root search with iterative deepening

    def search(self, board, depth, time_limit=None):
        moves = list(board.legal_moves)
        if not moves:
            return 0, None

        cpu_count   = os.cpu_count() or 1
        num_workers = max(1, (cpu_count * 3) // 4)

        helper_depths = list(range(1, depth // 2 + 1))
        num_workers   = min(num_workers, len(helper_depths))

        move_groups = split_moves(moves, num_workers)
        tasks = [
            (self.evaluator, board.fen(), d, move_groups[i])
            for i, d in enumerate(helper_depths[:num_workers])
        ]

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            for helper_tt in executor.map(helper_worker, tasks):
                self.tt.merge_tt(helper_tt)

        self.timer.start(time_limit)

        best_score = None
        best_move  = moves[0]
        is_max     = board.turn == chess.WHITE

        for curr_depth in range(1, depth + 1):
            if self.timer.should_stop():
                break

            current_best_score = None
            current_best_move  = None

            root_key = _board_key(board)
            ordered  = self._order_moves(
                board, moves,
                tt_move=self.tt.get_move(root_key),
                depth=0
            )

            try:
                for move in ordered:
                    # Full window per root move - so no root move is pruned
                    # before it gets a fair evaluation.
                    board.push(move)
                    score = self.minimax(
                        board, curr_depth - 1, -INF, INF,
                        board.turn == chess.WHITE
                    )
                    board.pop()

                    if is_max:
                        if current_best_move is None or score > current_best_score:
                            current_best_score = score
                            current_best_move  = move
                    else:
                        if current_best_move is None or score < current_best_score:
                            current_best_score = score
                            current_best_move  = move

                    self.logger.log_search(best_score, best_move, curr_depth, 0)

            except TimeoutError:
                # Depth incomplete - keep last fully-searched depth's result
                break

            if current_best_move is not None:
                best_score = current_best_score
                best_move  = current_best_move

        return best_score if best_score is not None else 0, best_move