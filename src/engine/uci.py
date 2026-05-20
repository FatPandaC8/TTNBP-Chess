from engine.agents.interface import Agent
from engine.evaluation.eval import Evaluator
from engine.protocols.uci import UCIProtocol
from engine.search.algorithms.phuc.alpha_beta import AlphaBetaSearcher
from engine.search.algorithms.search import Searcher
from engine.search.heuristic.manager import HeuristicManager
from engine.search.heuristic.phuc.capture import CaptureHeuristic
from engine.search.heuristic.phuc.check import CheckHeuristic
from engine.utils.logger import Logger


def build_agent() -> Agent:

    logger = Logger()

    evaluator = Evaluator()

    heuristics=HeuristicManager([
        CaptureHeuristic(),
        CheckHeuristic(),
    ])

    return (
        Agent("#uci", 2)
        .with_search(
            AlphaBetaSearcher(
                evaluator=evaluator,
                logger=logger,
                heuristics=heuristics,
            )
        )
        .with_depth(2)
    )


def main():
    agent = build_agent()
    protocol = UCIProtocol(agent)
    protocol.loop()

if __name__ == "__main__":
    main()
