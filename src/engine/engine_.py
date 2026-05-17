import chess
from engine.search.algorithms.bach.tt import TranspositionTable
from engine.utils.logger import Logger
from engine.agents.interface import Agent
from engine.game.match import Match
from engine.game.runner import MatchRunner
from engine.evaluation.eval import Evaluator
# from engine.search.algorithms.random import RandomSearch
from engine.search.algorithms.bach.search import SimpleSearcher
from engine.search.algorithms.search import Searcher
from engine.utils.decorators import timer_decorator

class Engine:
    def __init__(self):
        logger = Logger()

        evaluator = Evaluator()

        time_limit: float = 0.5

        # Current: depth 5 takes 263.171743s, depth 2 takes 2.29s

        main_tt = TranspositionTable(size=1_000_000)
        
        white_agent = (
            Agent("#1", time_limit)
            .with_search(
                SimpleSearcher(
                    evaluator=evaluator,
                    logger=logger,
                    tt=main_tt
                )
            )
            .with_depth(12)
        )

        black_agent = (
            Agent("#2", time_limit)
            .with_search(Searcher(evaluator=evaluator, logger=logger))
            .with_depth(12)
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