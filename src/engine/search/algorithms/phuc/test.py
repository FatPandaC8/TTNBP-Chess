import time
from chess import Board

from .alpha_beta import AlphaBetaSearcher
from ...context import SearchContext
from ...heuristic.manager import HeuristicManager
from ...heuristic.phuc import *
from ....utils.logger import Logger
from ....evaluation.eval import Evaluator

board = Board()
searcher = AlphaBetaSearcher(
    context=SearchContext(
        evaluator=Evaluator(),
        logger=Logger(),
        heuristic_manager=HeuristicManager([
            CaptureHeuristic(),
            CheckHeuristic(),
        ])
    )
)

score, move = searcher.search(board, depth=1)

start = time.time()

score, move = searcher.search(board, depth=4)

print(time.time() - start)