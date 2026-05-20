"""
spsa_tuner.py — SPSA Parameter Tuner
=====================================

THIẾT KẾ:
  - Đọc engine_cmd và opponent_cmd từ tournament.yml (cùng format bạn đang dùng)
  - theta+ vs theta-  → đánh với NHAU  (gradient signal thuần)
  - Cả hai đồng thời đánh với OPPONENT cố định → đo absolute strength
  - Kết hợp hai signal theo tỉ lệ để cập nhật theta

OPPONENT có thể là:
  1. Stockfish với skill level / depth giới hạn  (khuyến nghị)
  2. Một bản frozen của chính engine (build cũ)
  3. Bất kỳ UCI engine nào mạnh hơn

Cách chạy:
  python spsa_tuner.py                         # đọc tournament.yml
  python spsa_tuner.py --config my.yml         # yml khác
  python spsa_tuner.py --resume                # tiếp từ checkpoint
  python spsa_tuner.py --check                 # chỉ kiểm tra engine
  python spsa_tuner.py --params LMR_FULL_DEPTH_MOVES NULL_MOVE_REDUCTION
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import stat
import sys
import time
import threading
from pathlib import Path
from typing import Optional
from engine.utils.config_loader import load_config
import chess
import chess.engine

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
    "all": None,  # None = toàn bộ
}

# ── Đường dẫn gốc (cùng logic với tournament.py) ───────────────────────────
ROOT      = Path(__file__).resolve().parent.parent   # lên 1 cấp so với scripts/
LOGS      = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
CHECKPOINT = LOGS / "spsa_checkpoint.json"
LOG_FILE   = LOGS / "spsa_tuner.log"

# ── Import TUNABLE_PARAMS từ engine ────────────────────────────────────────
sys.path.insert(0, str(ROOT))
try:
    from engine.search.algorithms.search import TUNABLE_PARAMS
except ImportError as e:
    print(f"[ERROR] Không import được TUNABLE_PARAMS: {e}")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# ĐỌC CONFIG — dùng lại tournament.yml
# ══════════════════════════════════════════════════════════════════════════════



def resolve_cmd(cmd_str: str) -> list[str]:
    """
    Giống resolve_engine_path trong tournament.py.
    cmd_str có thể là:
      - "bin/my_engine"          → binary
      - "bin/my_engine.py"       → python script  (thêm sys.executable)
      - "stockfish"              → PATH system binary
    """
    path = ROOT / cmd_str
    if path.exists():
        if os.name != "nt":
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        if path.suffix == ".py":
            return [sys.executable, str(path)] 
        return [str(path)]

    # fallback: thử tìm trong PATH (ví dụ "stockfish")
    import shutil
    found = shutil.which(cmd_str)
    if found:
        return [found]

    raise FileNotFoundError(
        f"Không tìm thấy engine: '{cmd_str}'\n"
        f"  Đã thử: {path}\n"
        f"  Đã thử PATH: {cmd_str}"
    )


def extract_engine_info(config: dict) -> tuple[list[str], dict, list[str], dict]:
    """
    Trả về (engine_cmd, engine_options, opponent_cmd, opponent_options).

    tournament.yml phải có:
      engines:
        - name: my_engine
          cmd: bin/my_engine         ← engine cần tune
          options: {}

        - name: opponent              ← đối thủ cố định (Stockfish, frozen build...)
          cmd: bin/stockfish
          options:
            Skill Level: 15          ← giới hạn sức mạnh Stockfish
            UCI_LimitStrength: true
            UCI_Elo: 1800
    """
    engines = config["engines"]
    if len(engines) < 2:
        raise ValueError(
            "tournament.yml cần ít nhất 2 engine:\n"
            "  engines[0] = engine cần tune\n"
            "  engines[1] = opponent cố định"
        )

    e0 = engines[0]
    e1 = engines[1]

    engine_cmd  = resolve_cmd(e0["cmd"])
    engine_opts = e0.get("options", {}) or {}

    opp_cmd  = resolve_cmd(e1["cmd"])
    opp_opts = e1.get("options", {}) or {}

    return engine_cmd, engine_opts, opp_cmd, opp_opts


# ══════════════════════════════════════════════════════════════════════════════
# LOGGER
# ══════════════════════════════════════════════════════════════════════════════

class TunerLogger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f    = open(path, "a", encoding="utf-8")
        self._lock = threading.Lock()

    def log(self, msg: str):
        ts   = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with self._lock:
            self._f.write(line + "\n")
            self._f.flush()

    def close(self):
        self._f.close()


# ══════════════════════════════════════════════════════════════════════════════
# OPENING BOOK (đa dạng ván cờ, tránh lặp)
# ══════════════════════════════════════════════════════════════════════════════

OPENING_FENS = [
    chess.STARTING_FEN,
    # e4 openings
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "rnbqkb1r/ppp2ppp/3p1n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4",
    # d4 openings
    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
    "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2",
    "rnbqkb1r/ppp1pppp/5n2/3p4/3P4/5N2/PPP1PPPP/RNBQKB1R w KQkq - 2 3",
    # Sicilian
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
    # French
    "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    # Caro-Kann
    "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    # English
    "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq - 0 1",
    # London / Colle
    "rnbqkb1r/ppp1pppp/5n2/3p4/3P4/2N2N2/PPP1PPPP/R1BQKB1R b KQkq - 3 3",
    # King's Indian
    "rnbqkb1r/pppppp1p/5np1/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 3",
]

WIN  = 1.0
DRAW = 0.5
LOSS = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE GAME
# ══════════════════════════════════════════════════════════════════════════════

def play_game(
    white_cmd:  list[str],
    white_opts: dict,
    black_cmd:  list[str],
    black_opts: dict,
    tc:         chess.engine.Limit,
    fen:        str,
    max_moves:  int = 200,
) -> float:
    """
    Chạy 1 ván. Trả về score của WHITE: 1=thắng, 0.5=hòa, 0=thua.
    Spawn và destroy engine mỗi ván để tránh state leak.
    """
    print(f"  [GAME] spawning engines...", flush=True)
    try:
        white = chess.engine.SimpleEngine.popen_uci(white_cmd, timeout=20)
        black = chess.engine.SimpleEngine.popen_uci(black_cmd, timeout=20)
    except Exception as e:
        print(f"  [WARN] spawn engine thất bại: {e}")
        return DRAW

    try:
        # Inject options
        for k, v in white_opts.items():
            try: white.configure({k: v})
            except Exception: pass
        for k, v in black_opts.items():
            try: black.configure({k: v})
            except Exception: pass

        board = chess.Board(fen)
        print(f"  [GAME] engines ready, starting game", flush=True)
        for _ in range(max_moves):
            if board.is_game_over(claim_draw=True):
                break
            engine = white if board.turn == chess.WHITE else black
            print(f"  [GAME] move {_} - calling engine.play()", flush=True)
            try:
                result = engine.play(board, tc)
                print(f"  [GAME] move {_} - got {result.move}", flush=True)
                if result.move not in board.legal_moves:
                    return LOSS if board.turn == chess.WHITE else WIN
                board.push(result.move)
            except Exception:
                return LOSS if board.turn == chess.WHITE else WIN

        outcome = board.outcome(claim_draw=True)
        if outcome is None:
            return DRAW
        if outcome.winner is None:
            return DRAW
        return WIN if outcome.winner == chess.WHITE else LOSS

    finally:
        try: white.quit()
        except Exception: pass
        try: black.quit()
        except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
# MATCH RUNNER — 3 loại match
# ══════════════════════════════════════════════════════════════════════════════

def run_spsa_match(
    engine_cmd:    list[str],
    params_plus:   dict,
    params_minus:  dict,
    opp_cmd:       list[str],
    opp_opts:      dict,
    tc:            chess.engine.Limit,
    games:         int,          # phải chia hết cho 4
    logger:        TunerLogger,
) -> tuple[float, float]:
    """
    Chạy 2 loại match xen kẽ:

    [A] theta+  vs  theta-   (gradient match — đo hướng cải thiện)
    [B] theta+  vs  opponent (absolute match — đo sức mạnh tuyệt đối)
        theta-  vs  opponent

    Trả về (wr_gradient, wr_vs_opponent):
      wr_gradient   : win-rate của theta+ so với theta-
      wr_vs_opponent: win-rate trung bình của (theta+ + theta-) so với opponent
    """
    assert games % 4 == 0, "games phải chia hết cho 4"
    pairs = games // 4  # số pair mỗi loại match

    fens = random.choices(OPENING_FENS, k=pairs)

    grad_scores = []      # theta+ vs theta-
    abs_scores  = []      # engine vs opponent

    for fen in fens:
        # ── [A] gradient match ──────────────────────────────────────────────
        # pair 1: plus=W, minus=B
        s = play_game(
            engine_cmd, params_plus,
            engine_cmd, params_minus,
            tc, fen
        )
        grad_scores.append(s)

        # pair 2: minus=W, plus=B  (swap màu)
        s = play_game(
            engine_cmd, params_minus,
            engine_cmd, params_plus,
            tc, fen
        )
        grad_scores.append(1.0 - s)  # đảo về góc nhìn của plus

        # ── [B] absolute match ──────────────────────────────────────────────
        # theta+ vs opponent
        s = play_game(
            engine_cmd, params_plus,
            opp_cmd,    opp_opts,
            tc, fen
        )
        abs_scores.append(s)

        # theta- vs opponent
        s = play_game(
            engine_cmd, params_minus,
            opp_cmd,    opp_opts,
            tc, fen
        )
        abs_scores.append(s)

    wr_grad = sum(grad_scores) / len(grad_scores)
    wr_abs  = sum(abs_scores)  / len(abs_scores)

    g_w = sum(s == WIN  for s in grad_scores)
    g_d = sum(s == DRAW for s in grad_scores)
    g_l = sum(s == LOSS for s in grad_scores)

    a_w = sum(s == WIN  for s in abs_scores)
    a_d = sum(s == DRAW for s in abs_scores)
    a_l = sum(s == LOSS for s in abs_scores)

    logger.log(
        f"  gradient (+vs-) : {g_w}W {g_d}D {g_l}L  wr={wr_grad:.3f}  |  "
        f"absolute (vs opp): {a_w}W {a_d}D {a_l}L  wr={wr_abs:.3f}"
    )
    return wr_grad, wr_abs


# ══════════════════════════════════════════════════════════════════════════════
# SPSA TUNER
# ══════════════════════════════════════════════════════════════════════════════

class SPSATuner:
    """
    Cập nhật theta theo công thức SPSA tiêu chuẩn kết hợp signal tuyệt đối:

        gradient SPSA : g_hat = (wr_grad - 0.5) / (c_k * delta)
        absolute term : g_abs = (wr_abs  - target_wr)          ← kéo về target
        g_combined    = alpha_g * g_hat + alpha_a * g_abs * delta
        theta        += a_k * g_combined
    """

    def __init__(
        self,
        engine_cmd:  list[str],
        engine_opts: dict,
        opp_cmd:     list[str],
        opp_opts:    dict,
        tc:          chess.engine.Limit,
        games:       int,
        max_iters:   int,
        target_wr:   float,   # win-rate mục tiêu vs opponent (0.5 = ngang sức)
        logger:      TunerLogger,
        params_subset: Optional[list[str]] = None,
    ):
        self.engine_cmd  = engine_cmd
        self.engine_opts = engine_opts
        self.opp_cmd     = opp_cmd
        self.opp_opts    = opp_opts
        self.tc          = tc
        self.games       = games
        self.max_iters   = max_iters
        self.target_wr   = target_wr
        self.logger      = logger

        # Chọn subset tham số nếu cần
        self.active_params = (
            {k: v for k, v in TUNABLE_PARAMS.items() if k in params_subset}
            if params_subset
            else dict(TUNABLE_PARAMS)
        )

        # Trạng thái float (SPSA cập nhật trơn tru, round khi inject)
        self.theta: dict[str, float] = {
            k: float(v[0]) for k, v in self.active_params.items()
        }
        self.iteration = 0

        # SPSA hyperparams
        self.A     = max(1, int(0.1 * max_iters))
        self.a0    = 0.1 * (self.A + 1) ** 0.602
        self.alpha = 0.602
        self.gamma = 0.101
        self.c_ratio  = 0.2   # c_k = c_ratio * param_step
        self.w_grad   = 0.7   # weight của gradient signal
        self.w_abs    = 0.3   # weight của absolute signal

    # ── helpers ───────────────────────────────────────────────────────────────

    def _clip(self, name: str, val: float) -> float:
        _, lo, hi, _ = self.active_params[name]
        return max(float(lo), min(float(hi), val))

    def _round_params(self, theta: dict[str, float]) -> dict[str, int]:
        out = {}
        for name, val in theta.items():
            _, lo, hi, _ = self.active_params[name]
            out[name] = int(max(lo, min(hi, round(val))))
        # Giữ nguyên options cố định của engine (hash, threads, v.v.)
        merged = dict(self.engine_opts)
        merged.update(out)
        return merged

    # ── checkpoint ────────────────────────────────────────────────────────────

    def save(self):
        CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT.write_text(json.dumps(
            {"iteration": self.iteration, "theta": self.theta}, indent=2
        ))
        self.logger.log(f"  checkpoint → {CHECKPOINT.name}")

    def load(self) -> bool:
        if not CHECKPOINT.exists():
            return False
        text = CHECKPOINT.read_text().strip()
        if not text:                          # ← thêm dòng này
            return False
        data = json.loads(text)
        # Chỉ load các param đang active
        for k in self.theta:
            if k in data["theta"]:
                self.theta[k] = data["theta"][k]
        self.iteration = data["iteration"]
        self.logger.log(f"  resumed from iteration {self.iteration}")
        return True

    # ── one SPSA step ─────────────────────────────────────────────────────────

    def step(self):
        k   = self.iteration + 1
        a_k = self.a0 / (k + self.A) ** self.alpha
        c_k = {name: self.c_ratio * step
               for name, (_, _, _, step) in self.active_params.items()}

        # Perturbation Rademacher ±1
        delta = {name: random.choice([-1, 1]) for name in self.theta}

        theta_plus  = {
            name: self._clip(name, self.theta[name] + c_k[name] * delta[name])
            for name in self.theta
        }
        theta_minus = {
            name: self._clip(name, self.theta[name] - c_k[name] * delta[name])
            for name in self.theta
        }

        self.logger.log(
            f"\nIter {k}/{self.max_iters}  "
            f"a_k={a_k:.5f}  "
            f"target_wr={self.target_wr:.2f}"
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

        # ── cập nhật theta ────────────────────────────────────────────────────
        #
        # Signal 1 (gradient): nếu wr_grad > 0.5  → theta+ tốt hơn → đi theo delta
        # Signal 2 (absolute): nếu wr_abs < target → cả hai còn yếu → tìm hướng mạnh hơn
        #
        grad_signal = wr_grad - 0.5          # ∈ [-0.5, 0.5]
        abs_signal  = wr_abs  - self.target_wr  # âm = yếu hơn mục tiêu

        for name in self.theta:
            ck  = c_k[name]
            dk  = delta[name]

            g_spsa = grad_signal / (ck * dk)           # gradient SPSA thuần
            g_abs  = abs_signal  * dk                   # absolute push theo delta
            g_combined = self.w_grad * g_spsa + self.w_abs * g_abs

            self.theta[name] = self._clip(
                name,
                self.theta[name] + a_k * g_combined
            )

        self.iteration = k

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self, resume: bool = False):
        if resume:
            self.load()

        self.logger.log("=" * 64)
        self.logger.log("SPSA TUNER")
        self.logger.log(f"  engine      : {' '.join(self.engine_cmd)}")
        self.logger.log(f"  opponent    : {' '.join(self.opp_cmd)}")
        self.logger.log(f"  opp options : {self.opp_opts}")
        self.logger.log(f"  params      : {len(self.active_params)}")
        self.logger.log(f"  iters       : {self.max_iters}")
        self.logger.log(f"  games/iter  : {self.games}  ({self.games//2} gradient + {self.games//2} absolute)")
        self.logger.log(f"  target_wr   : {self.target_wr}")
        self.logger.log("=" * 64)
        self._print_state("Initial values")

        try:
            while self.iteration < self.max_iters:
                self.step()
                if self.iteration % 10 == 0:
                    self._print_state(f"After iter {self.iteration}")
                    self.save()
        except KeyboardInterrupt:
            self.logger.log("\n[STOPPED] Ctrl+C")
        finally:
            self.save()
            self._print_final()

    def _print_state(self, label: str):
        self.logger.log(f"\n── {label} " + "─" * (48 - len(label)))
        for name, fval in self.theta.items():
            default = self.active_params[name][0]
            ival    = round(fval)
            diff    = ival - default
            sign    = "+" if diff >= 0 else ""
            self.logger.log(f"  {name:<28} {ival:>7}  (default {default:>6}  {sign}{diff})")
        self.logger.log("")

    def _print_final(self):
        self.logger.log("\n" + "=" * 64)
        self.logger.log("KẾT QUẢ — paste vào TUNABLE_PARAMS:")
        self.logger.log("=" * 64)
        for name, fval in self.theta.items():
            _, lo, hi, step = self.active_params[name]
            val = int(max(lo, min(hi, round(fval))))
            self.logger.log(f'    "{name}": ({val}, {lo}, {hi}, {step}),')

        self.logger.log("\nUCI setoption:")
        for name, fval in self.theta.items():
            _, lo, hi, _ = self.active_params[name]
            val = int(max(lo, min(hi, round(fval))))
            self.logger.log(f"  setoption name {name} value {val}")


# ══════════════════════════════════════════════════════════════════════════════
# SANITY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def check_engines(engine_cmd: list[str], engine_opts: dict,
                  opp_cmd: list[str], opp_opts: dict):
    print("[CHECK] Kiểm tra engine cần tune...")
    try:
        e = chess.engine.SimpleEngine.popen_uci(engine_cmd, timeout=15)
        for k, v in engine_opts.items():
            try: e.configure({k: v})
            except Exception: pass
        r = e.play(chess.Board(), chess.engine.Limit(time=0.1))
        e.quit()
        print(f"  OK — engine đi: {r.move}")
    except Exception as ex:
        print(f"  FAILED: {ex}")
        return False

    print("[CHECK] Kiểm tra opponent...")
    try:
        o = chess.engine.SimpleEngine.popen_uci(opp_cmd, timeout=15)
        for k, v in opp_opts.items():
            try: o.configure({k: v})
            except Exception: pass
        r = o.play(chess.Board(), chess.engine.Limit(time=0.1))
        o.quit()
        print(f"  OK — opponent đi: {r.move}")
    except Exception as ex:
        print(f"  FAILED: {ex}")
        return False

    return True


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="SPSA tuner — đọc config từ tournament.yml"
    )
    p.add_argument("--config",    default="tournament.yml",
                   help="Path tới config file (default: tournament.yml)")
    p.add_argument("--games",     type=int,   default=8,
                   help="Ván/iter, phải chia hết cho 4 (default=8)")
    p.add_argument("--iters",     type=int,   default=500,
                   help="Số iteration (default=500)")
    p.add_argument("--tc",        type=float, default=5.0,
                   help="Giây mỗi ván (default=5.0)")
    p.add_argument("--inc",       type=float, default=0.05,
                   help="Increment giây (default=0.05)")
    p.add_argument("--target-wr", type=float, default=0.35,
                   help="Win-rate mục tiêu vs opponent (default=0.35, tức opponent mạnh hơn)")
    p.add_argument("--resume",    action="store_true",
                   help="Tiếp từ checkpoint")
    p.add_argument("--check",     action="store_true",
                   help="Chỉ kiểm tra engine rồi thoát")
    p.add_argument("--params",    nargs="*", metavar="NAME",
                   help="Chỉ tune các param này")
    
    p.add_argument(
        "--group",
        choices=list(PARAM_GROUPS.keys()),
        default="all",
        help="Nhóm tham số cần tune (default: all)"
    )
    return p.parse_args()


def main():
    args = parse_args()

    config = load_config("tournament.yml")

    try:
        engine_cmd, engine_opts, opp_cmd, opp_opts = extract_engine_info(config)
    except (ValueError, FileNotFoundError) as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print(f"[INFO] engine  : {' '.join(engine_cmd)}")
    print(f"[INFO] opponent: {' '.join(opp_cmd)}")
    print(f"[INFO] opp opts: {opp_opts}")

    if args.check:
        ok = check_engines(engine_cmd, engine_opts, opp_cmd, opp_opts)
        sys.exit(0 if ok else 1)

    if args.games % 4 != 0:
        print("[ERROR] --games phải chia hết cho 4")
        sys.exit(1)

    if args.params:
        unknown = set(args.params) - set(TUNABLE_PARAMS)
        if unknown:
            print(f"[ERROR] Tham số không tồn tại: {unknown}")
            print(f"        Hợp lệ: {list(TUNABLE_PARAMS.keys())}")
            sys.exit(1)

    tc     = chess.engine.Limit(time=args.tc)
    logger = TunerLogger(LOG_FILE)

    groups = (
        [PARAM_GROUPS[args.group]] if args.group != "all"
        else [v for v in PARAM_GROUPS.values() if v is not None] + [None]
    )

    try:
        for i, group_params in enumerate(groups):
            logger.log(f"\n{'='*64}")
            logger.log(f"NHÓM: {group_params or 'ALL'}")
            logger.log(f"{'='*64}")

            tuner = SPSATuner(
                engine_cmd    = engine_cmd,
                engine_opts   = engine_opts,
                opp_cmd       = opp_cmd,
                opp_opts      = opp_opts,
                tc            = tc,
                games         = args.games,
                max_iters     = args.iters,
                target_wr     = args.target_wr,
                logger        = logger,
                params_subset = group_params,
            )

            # Group đầu tiên: không load (checkpoint có thể rỗng)
            # Group 2 trở đi: load theta đã tune từ group trước
            if i > 0:
                tuner.load()

            tuner.run(resume=False)
            tuner.save()

    finally:
        logger.close()


if __name__ == "__main__":
    main()