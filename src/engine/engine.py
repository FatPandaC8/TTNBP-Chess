import chess
from engine.utils.logger import Logger
from engine.agents.interface import Agent
from engine.game.match import Match
from engine.game.runner import MatchRunner
from engine.evaluation.eval import Evaluator
from engine.search.algorithms.random import RandomSearch
# from engine.search.algorithms.search import Searcher
from engine.utils.decorators import timer_decorator

class Engine:
    def __init__(self):
        logger = Logger()

        evaluator = Evaluator()

        time_limit: float = 0.0

        white_agent = (
            Agent("#1", time_limit)
            .with_search(RandomSearch(evaluator=evaluator, logger=logger))
            .with_depth(1_000_000)
        )

        black_agent = (
            Agent("#2", time_limit)
            .with_search(RandomSearch(evaluator=evaluator, logger=logger))
            .with_depth(1_000_000)
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