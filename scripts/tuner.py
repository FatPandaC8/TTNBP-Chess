from __future__ import annotations

import json
import os
import random
import stat
import sys
import threading
import time

from pathlib import Path
from typing import Optional

import chess
import chess.engine

from engine.utils.config_loader import load_config


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_GAMES = 32
DEFAULT_ITERS = 300
DEFAULT_TC = 3.0
DEFAULT_TARGET_WR = 0.45

PARAM_GROUPS = {
    "lmr": [
        "LMR_FULL_DEPTH_MOVES",
        "LMR_REDUCTION_LIMIT",
        "LMR_REDUCTION_BASE",
        "LMR_REDUCTION_DEEP",
    ],

    "pruning": [
        "RAZOR_MARGIN_D1",
        "RAZOR_MARGIN_D2",
        "RAZOR_MARGIN_D3",
        "FUTILITY_MARGIN_D1",
        "FUTILITY_MARGIN_D2",
    ],

    "threshold": [
        "NULL_MOVE_MIN_DEPTH",
        "NULL_MOVE_REDUCTION",
        "ASPIRATION_DELTA",
        "RAZOR_DEPTH",
        "FUTILITY_DEPTH",
        "ASPIRATION_MIN_DEPTH",
    ],

    "ordering": [
        "MO_KILLER1_SCORE",
        "MO_KILLER2_SCORE",
        "HISTORY_MAX_BONUS",
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parent.parent

LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

CHECKPOINT = LOGS / "spsa_checkpoint.json"
LOG_FILE = LOGS / "spsa_tuner.log"

sys.path.insert(0, str(ROOT))

try:
    from engine.search.algorithms.search import TUNABLE_PARAMS

except ImportError as e:
    print(f"[ERROR] Cannot import TUNABLE_PARAMS: {e}")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# OPENINGS
# ══════════════════════════════════════════════════════════════════════════════

OPENING_FENS = [
    chess.STARTING_FEN,

    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "rnbqkb1r/ppp2ppp/3p1n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4",

    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
    "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2",

    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",

    "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",

    "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",

    "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq - 0 1",
]

WIN = 1.0
DRAW = 0.5
LOSS = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def resolve_cmd(cmd_str: str) -> list[str]:

    path = ROOT / cmd_str

    if path.exists():

        if os.name != "nt":
            path.chmod(path.stat().st_mode | stat.S_IEXEC)

        if path.suffix == ".py":
            return [sys.executable, str(path)]

        return [str(path)]

    import shutil

    found = shutil.which(cmd_str)

    if found:
        return [found]

    raise FileNotFoundError(
        f"Engine not found: {cmd_str}"
    )


def extract_engine_info(config):

    engines = config["engines"]

    if len(engines) < 2:
        raise ValueError(
            "Need at least 2 engines in config"
        )

    tune_engine = engines[0]
    opponent = engines[1]

    engine_cmd = resolve_cmd(
        tune_engine["cmd"]
    )

    opp_cmd = resolve_cmd(
        opponent["cmd"]
    )

    return (
        engine_cmd,
        tune_engine.get("options", {}),
        opp_cmd,
        opponent.get("options", {}),
    )


# ══════════════════════════════════════════════════════════════════════════════
# LOGGER
# ══════════════════════════════════════════════════════════════════════════════

class TunerLogger:

    def __init__(self, path: Path):

        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self._f = open(
            path,
            "a",
            encoding="utf-8"
        )

        self._lock = threading.Lock()

    def log(self, msg: str):

        ts = time.strftime("%H:%M:%S")

        line = f"[{ts}] {msg}"

        print(line, flush=True)

        with self._lock:
            self._f.write(line + "\n")
            self._f.flush()

    def close(self):
        self._f.close()


# ══════════════════════════════════════════════════════════════════════════════
# PLAY GAME
# ══════════════════════════════════════════════════════════════════════════════

def play_game(
    white_cmd,
    white_opts,
    black_cmd,
    black_opts,
    tc,
    fen,
    max_moves=200,
):

    try:

        white = chess.engine.SimpleEngine.popen_uci(
            white_cmd,
            timeout=20
        )

        black = chess.engine.SimpleEngine.popen_uci(
            black_cmd,
            timeout=20
        )

    except Exception:
        return DRAW

    try:

        for k, v in white_opts.items():
            try:
                white.configure({k: v})
            except Exception:
                pass

        for k, v in black_opts.items():
            try:
                black.configure({k: v})
            except Exception:
                pass

        board = chess.Board(fen)

        for _ in range(max_moves):

            if board.is_game_over(claim_draw=True):
                break

            engine = (
                white
                if board.turn == chess.WHITE
                else black
            )

            try:

                result = engine.play(
                    board,
                    tc
                )

                if result.move not in board.legal_moves:
                    return LOSS if board.turn else WIN

                board.push(result.move)

            except Exception:
                return LOSS if board.turn else WIN

        outcome = board.outcome(claim_draw=True)

        if outcome is None:
            return DRAW

        if outcome.winner is None:
            return DRAW

        return WIN if outcome.winner else LOSS

    finally:

        try:
            white.quit()
        except Exception:
            pass

        try:
            black.quit()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# MATCH
# ══════════════════════════════════════════════════════════════════════════════

def run_spsa_match(
    engine_cmd,
    params_plus,
    params_minus,
    opp_cmd,
    opp_opts,
    tc,
    games,
    logger,
):

    pairs = games // 4

    fens = random.choices(
        OPENING_FENS,
        k=pairs
    )

    grad_scores = []
    abs_scores = []

    for fen in fens:

        # plus vs minus

        s = play_game(
            engine_cmd,
            params_plus,
            engine_cmd,
            params_minus,
            tc,
            fen
        )

        grad_scores.append(s)

        s = play_game(
            engine_cmd,
            params_minus,
            engine_cmd,
            params_plus,
            tc,
            fen
        )

        grad_scores.append(1.0 - s)

        # plus vs opponent

        s = play_game(
            engine_cmd,
            params_plus,
            opp_cmd,
            opp_opts,
            tc,
            fen
        )

        abs_scores.append(s)

        # minus vs opponent

        s = play_game(
            engine_cmd,
            params_minus,
            opp_cmd,
            opp_opts,
            tc,
            fen
        )

        abs_scores.append(s)

    wr_grad = sum(grad_scores) / len(grad_scores)
    wr_abs = sum(abs_scores) / len(abs_scores)

    logger.log(
        f"gradient={wr_grad:.3f} "
        f"absolute={wr_abs:.3f}"
    )

    return wr_grad, wr_abs


# ══════════════════════════════════════════════════════════════════════════════
# SPSA
# ══════════════════════════════════════════════════════════════════════════════

class SPSATuner:

    def __init__(
        self,
        engine_cmd,
        engine_opts,
        opp_cmd,
        opp_opts,
        tc,
        games,
        max_iters,
        target_wr,
        logger,
        params_subset: Optional[list[str]] = None,
    ):

        self.engine_cmd = engine_cmd
        self.engine_opts = engine_opts

        self.opp_cmd = opp_cmd
        self.opp_opts = opp_opts

        self.tc = tc
        self.games = games

        self.max_iters = max_iters
        self.target_wr = target_wr

        self.logger = logger

        self.active_params = (
            {
                k: v
                for k, v in TUNABLE_PARAMS.items()
                if k in params_subset
            }
            if params_subset
            else dict(TUNABLE_PARAMS)
        )

        self.theta = {
            k: float(v[0])
            for k, v in self.active_params.items()
        }

        self.iteration = 0

        # SPSA hyperparams

        self.A = max(
            1,
            int(0.15 * max_iters)
        )

        self.alpha = 0.602
        self.gamma = 0.101

        self.a0 = (
            0.02
            * (self.A + 1) ** self.alpha
        )

        self.c_ratio = 0.10

        self.w_grad = 0.85
        self.w_abs = 0.15

        self.momentum = 0.85
        self.max_update = 2.0

        self.velocity = {
            k: 0.0
            for k in self.theta
        }

        self.best_wr = float("-inf")
        self.best_theta = dict(self.theta)

    # ─────────────────────────

    def _clip(self, name, val):

        _, lo, hi, _ = self.active_params[name]

        return max(
            float(lo),
            min(float(hi), val)
        )

    def _round_params(self, theta):

        out = {}

        for name, val in theta.items():

            _, lo, hi, _ = self.active_params[name]

            out[name] = int(
                max(lo, min(hi, round(val)))
            )

        merged = dict(self.engine_opts)

        merged.update(out)

        return merged

    # ─────────────────────────

    def save(self):

        CHECKPOINT.write_text(json.dumps({
            "iteration": self.iteration,
            "theta": self.theta,
            "best_theta": self.best_theta,
            "best_wr": self.best_wr,
        }, indent=2))

        self.logger.log(
            "checkpoint saved"
        )

    def load(self):

        if not CHECKPOINT.exists():
            return False

        text = CHECKPOINT.read_text().strip()

        if not text:
            return False

        data = json.loads(text)

        for k in self.theta:

            if k in data["theta"]:
                self.theta[k] = data["theta"][k]

        self.iteration = data["iteration"]

        if "best_theta" in data:
            self.best_theta = data["best_theta"]

        if "best_wr" in data:
            self.best_wr = data["best_wr"]

        self.logger.log(
            f"resumed iter {self.iteration}"
        )

        return True

    # ─────────────────────────

    def step(self):

        k = self.iteration + 1

        a_k = (
            self.a0
            / (k + self.A) ** self.alpha
        )

        c_k = {
            name: self.c_ratio * step
            for name, (_, _, _, step)
            in self.active_params.items()
        }

        delta = {
            name: random.choice([-1, 1])
            for name in self.theta
        }

        theta_plus = {
            name: self._clip(
                name,
                self.theta[name]
                + c_k[name] * delta[name]
            )
            for name in self.theta
        }

        theta_minus = {
            name: self._clip(
                name,
                self.theta[name]
                - c_k[name] * delta[name]
            )
            for name in self.theta
        }

        self.logger.log(
            f"\nIter {k}/{self.max_iters}"
        )

        wr_grad, wr_abs = run_spsa_match(
            self.engine_cmd,
            self._round_params(theta_plus),
            self._round_params(theta_minus),
            self.opp_cmd,
            self.opp_opts,
            self.tc,
            self.games,
            self.logger,
        )

        grad_signal = wr_grad - 0.5
        abs_signal = wr_abs - self.target_wr

        # noise filter

        if abs(grad_signal) < 0.03:

            self.logger.log(
                "weak gradient -> skip"
            )

            self.iteration = k
            return

        # update

        for name in self.theta:

            ck = c_k[name]
            dk = delta[name]

            g_spsa = (
                grad_signal
                / (ck * dk)
            )

            g_abs = abs_signal * dk

            g_combined = (
                self.w_grad * g_spsa
                + self.w_abs * g_abs
            )

            update = a_k * g_combined

            update = max(
                -self.max_update,
                min(self.max_update, update)
            )

            self.velocity[name] = (
                self.momentum
                * self.velocity[name]
                + (1.0 - self.momentum)
                * update
            )

            self.theta[name] = self._clip(
                name,
                self.theta[name]
                + self.velocity[name]
            )

        # best

        if wr_abs > self.best_wr:

            self.best_wr = wr_abs
            self.best_theta = dict(self.theta)

            self.logger.log(
                f"NEW BEST wr={wr_abs:.3f}"
            )

        self.iteration = k

    # ─────────────────────────

    def run(self, resume=False):

        if resume:
            self.load()

        self.logger.log("=" * 64)

        self.logger.log(
            "SPSA TUNER"
        )

        self.logger.log(
            f"iters={self.max_iters} "
            f"games={self.games}"
        )

        self.logger.log("=" * 64)

        try:

            while self.iteration < self.max_iters:

                self.step()

                if self.iteration % 10 == 0:
                    self.save()

        except KeyboardInterrupt:

            self.logger.log(
                "STOPPED"
            )

        finally:

            self.save()
            self._print_final()

    # ─────────────────────────

    def _print_final(self):

        self.logger.log("\n" + "=" * 64)

        self.logger.log(
            f"BEST WR = {self.best_wr:.3f}"
        )

        self.logger.log("=" * 64)

        for name, fval in self.best_theta.items():

            _, lo, hi, step = (
                self.active_params[name]
            )

            val = int(
                max(lo, min(hi, round(fval)))
            )

            self.logger.log(
                f'"{name}": ({val}, {lo}, {hi}, {step}),'
            )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():

    config = load_config(
        "tournament_old.yml"
    )

    try:

        (
            engine_cmd,
            engine_opts,
            opp_cmd,
            opp_opts,
        ) = extract_engine_info(config)

    except Exception as e:

        print(f"[ERROR] {e}")
        return

    logger = TunerLogger(LOG_FILE)

    tc = chess.engine.Limit(
        time=DEFAULT_TC
    )

    try:

        tuner = SPSATuner(
            engine_cmd=engine_cmd,
            engine_opts=engine_opts,
            opp_cmd=opp_cmd,
            opp_opts=opp_opts,
            tc=tc,
            games=DEFAULT_GAMES,
            max_iters=DEFAULT_ITERS,
            target_wr=DEFAULT_TARGET_WR,
            logger=logger,
            params_subset=None,
        )

        tuner.run(resume=True)

    finally:
        logger.close()


if __name__ == "__main__":
    main()