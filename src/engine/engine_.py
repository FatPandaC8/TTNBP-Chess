import chess
from engine.search.algorithms.bach.tt import TranspositionTable
from engine.ui.pygame.game import Game
from engine.ui.pygame.human_agent import HumanAgent
from engine.ui.pygame.input_handler import InputHandler
from engine.utils.logger import Logger
from engine.agents.ai_agent import AIAgent
from engine.game.match import Match
from engine.game.runner import MatchRunner
from engine.evaluation.eval import Evaluator
from engine.evaluation.eval_stockfish_like import StockfishLikeEvaluator
from engine.evaluation.eval_pst_only import PSTOnlyEvaluator
from engine.search.algorithms.bach.search import SimpleSearcher
from engine.utils.decorators import timer_decorator
from engine.search.algorithms.thanh.search import BasicSearcher

class Engine:
    def __init__(self):
        self.logger = Logger()

        # Agent #1 (White): Stockfish-like PST + positional terms
        evaluator_stockfish_like = StockfishLikeEvaluator()

        # Agent #2 (Black): PST + Material
        evaluator_full = Evaluator()

        # Kept for quick A/B testing if needed.
        evaluator_pst_only = PSTOnlyEvaluator()

        time_limit: float = 0.5

        main_tt = TranspositionTable(size=1_000_000)
        
        self.white_agent = (
            AIAgent("#1", time_limit)
            .with_search(
                SimpleSearcher(
                    evaluator=evaluator_stockfish_like,
                    logger=self.logger,
                    tt=main_tt
                )
            )
            .with_depth(8)
        )

        self.black_agent = (
            AIAgent("#2", time_limit)
            .with_search(BasicSearcher(evaluator=evaluator_full, logger=self.logger))
            .with_depth(2)
        )

    def _make_match(self) -> Match:
        return Match(
            board=chess.Board(),
            # white_agent=HumanAgent(),
            white_agent=self.white_agent,
            black_agent=self.black_agent,
        )

    @timer_decorator
    def run_headless(self):
        runner = MatchRunner(
            match=self._make_match(),
            logger=self.logger,
        )
        runner.run()

    @timer_decorator
    def run_gui(self):
        game = Game(match=self._make_match())
        game.start_game()
