# test_eval.py

from engine.board.board import ChessBoard
from engine.evaluation.eval import Evaluator

def test_eval():
    board = ChessBoard()
    evaluator = Evaluator("config/evaluation/eval.yaml")
    score = evaluator.evaluate(board)

    print("Score:", score)

    assert isinstance(score, int)