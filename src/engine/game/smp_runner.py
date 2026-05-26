# smp_runner.py
import chess
import random
import multiprocessing as mp
from multiprocessing import shared_memory


def _worker_search(args):
    fen, depth, tt_name, evaluator, seed, time_limit = args
    from engine.search.algorithms.bach.search import LazySMP

    shm = shared_memory.SharedMemory(name=tt_name)
    board = chess.Board(fen)
    random.seed(seed)
    engine = LazySMP(evaluator=evaluator, logger=None, tt_buffer=shm.buf)
    score, move = engine.search(board, depth, time_limit)
    shm.close()

    # fallback: if search timed out before finding anything, pick first legal move
    if move is None:
        move = next(iter(board.legal_moves), None)

    return score, move


class SMPRunner:
    def __init__(self, evaluator, logger, tt_shm, workers=4):
        self.evaluator = evaluator
        self.logger = logger
        self.tt_shm = tt_shm
        self.workers = workers
        self.pool = mp.Pool(processes=self.workers)  # create once

    def search(self, board: chess.Board, depth: int, time_limit: float = None):
        tasks = [
            (board.fen(), depth, self.tt_shm.name, self.evaluator,
             random.randint(0, 10_000_000), time_limit)
            for _ in range(self.workers)
        ]
        results = self.pool.map(_worker_search, tasks)
        results = [(s, m) for s, m in results if m is not None]
        if not results:
            return 0, None
        return max(results, key=lambda x: x[0])

    def close(self):
        self.pool.terminate()
        self.pool.join()