from engine.evaluation.eval import Evaluator
from engine.search.heuristic.manager import HeuristicManager
from engine.utils.logger import Logger


class SearchContext:

    def __init__(
        self,
        evaluator: Evaluator,
        logger: Logger,
        heuristic_manager: HeuristicManager,
    ):
        self.evaluator = evaluator
        self.logger = logger
        self.heuristic_manager = heuristic_manager
