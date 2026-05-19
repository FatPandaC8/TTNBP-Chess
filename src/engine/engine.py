import chess
from engine.utils.logger import Logger
from engine.agents.interface import Agent
from engine.game.match import Match
from engine.game.runner import MatchRunner
from engine.evaluation.eval import Evaluator
from engine.evaluation.eval_stockfish_like import StockfishLikeEvaluator
from engine.evaluation.eval_pst_only import PSTOnlyEvaluator
from engine.search.algorithms.random import RandomSearch
from engine.search.algorithms.search import Searcher
from engine.utils.decorators import timer_decorator

class Engine:
    def __init__(self):
        logger = Logger()

        # Agent #1 (White): Stockfish-like PST + positional terms
        evaluator_stockfish_like = StockfishLikeEvaluator()

        # Agent #2 (Black): PST + Material
        evaluator_full = Evaluator()

        # Kept for quick A/B testing if needed.
        evaluator_pst_only = PSTOnlyEvaluator()

        time_limit: float = 0.5

        # Current: depth 5 takes 263.171743s, depth 2 takes 2.29s
        white_agent = (
            Agent("#1", time_limit)
            .with_search(Searcher(evaluator=evaluator_full, logger=logger))
            .with_depth(2)
        )

        black_agent = (
            Agent("#2", time_limit)
            .with_search(Searcher(evaluator=evaluator_full, logger=logger))
            .with_depth(2)
        )

        match = Match(
            board=chess.Board(),
            white_agent=white_agent,
            black_agent=black_agent,
        )

        self.runner = MatchRunner(
            match=match,
            logger=logger,
        )

    @timer_decorator
    def run(self):
        self.runner.run()