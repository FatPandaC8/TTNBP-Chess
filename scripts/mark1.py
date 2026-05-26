import time
import chess
from statistics import mean

from engine.evaluation import Evaluator, StockfishLikeEvaluator
from engine.search.algorithms.search import Searcher
from engine.utils.logger import Logger

EVALUATORS = {
    "Evaluator": Evaluator,
    "StockfishLike": StockfishLikeEvaluator,
}

DEPTHS = [1, 2, 3, 4]
REPEATS = 10   # 10 lần trắng + 10 lần đen
TIME_LIMIT = 0.25

FENS = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
    "r2q1rk1/pp2bppp/2n1pn2/2bp4/2B5/2N2NP1/PP2PPBP/R1BQ1RK1 w - - 2 9",
]

def toggle_turn_fen(fen: str) -> str:
    parts = fen.split(" ")
    if len(parts) >= 2:
        parts[1] = "b" if parts[1] == "w" else "w"
    return " ".join(parts)

def run_search(evaluator, board, depth):
    logger = Logger()
    searcher = Searcher(evaluator=evaluator, logger=logger)
    t0 = time.perf_counter()
    score, move = searcher.search(board, depth=depth, time_limit=TIME_LIMIT)
    dt = time.perf_counter() - t0
    return score, move, dt

def benchmark():
    # lưu tổng kết chung
    summary = {name: {"scores": [], "times": []} for name in EVALUATORS}

    for fen in FENS:
        for fen_variant in [fen, toggle_turn_fen(fen)]:
            print("=" * 80)
            print(f"FEN: {fen_variant}")

            for name, cls in EVALUATORS.items():
                print(f"\n--- {name} ---")
                evaluator = cls()

                for depth in DEPTHS:
                    scores, times = [], []
                    best_move = None

                    for i in range(REPEATS):
                        board = chess.Board(fen_variant)
                        score, move, dt = run_search(evaluator, board, depth)
                        scores.append(score)
                        times.append(dt)
                        if i == 0:
                            best_move = move

                    avg_s = mean(scores)
                    avg_t = mean(times)
                    summary[name]["scores"].append(avg_s)
                    summary[name]["times"].append(avg_t)

                    print(
                        f"depth={depth}  "
                        f"avg_score={avg_s:>7.2f}  "
                        f"best_move={best_move}  "
                        f"avg_time={avg_t:.4f}s"
                    )

            print()

    # tổng kết cuối
    print("=" * 80)
    print("SUMMARY (overall avg across all FEN + sides + depths)")
    for name in EVALUATORS:
        avg_score = mean(summary[name]["scores"])
        avg_time = mean(summary[name]["times"])
        print(f"{name:12s}  avg_score={avg_score:>7.2f}  avg_time={avg_time:.4f}s")

if __name__ == "__main__":
    benchmark()