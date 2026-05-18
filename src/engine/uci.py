from engine.agents.interface import Agent
from engine.evaluation.eval import Evaluator
from engine.protocols.uci import UCIProtocol
from engine.search.algorithms.search import Searcher
from engine.utils.logger import Logger


def build_agent() -> Agent:

    logger = Logger()

    evaluator = Evaluator()

    return (
        Agent("#uci", 0.5)
        .with_search(
            Searcher(
                evaluator=evaluator,
                logger=logger
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
