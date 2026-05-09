# test_eval.py

from engine.board.board import ChessBoard
from engine.evaluation.eval import Evaluator

def main():
    board = ChessBoard()
    evaluator = Evaluator()

    score = evaluator.evaluate(board)

    print("Score:", score)

if __name__ == "__main__":
    main()