
"""
tuner.py — Bayesian Optimization tuner dùng Optuna + cutechess-cli
===================================================================

Cài đặt:
  pip install optuna

Cách chạy:
  python scripts/tuner.py                        # tune tất cả, 100 trials
  python scripts/tuner.py --group lmr            # chỉ tune nhóm LMR
  python scripts/tuner.py --trials 200           # số lần thử
  python scripts/tuner.py --resume               # tiếp từ study đã lưu
  python scripts/tuner.py --check                # kiểm tra engine
"""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import chess.pgn
import optuna
from optuna.samplers import TPESampler

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent.parent
LOGS     = ROOT / "logs"
LOGS_PGN = LOGS / "spsa_pgn"
LOGS_PGN.mkdir(parents=True, exist_ok=True)
DB_PATH  = LOGS / "optuna_study.db"   # lưu study để resume

# ── Import config từ engine ──────────────────────────────────────────────────
sys.path.insert(0, str(ROOT / "src"))
try:
    from engine.search.algorithms.search import TUNABLE_PARAMS
    from engine.utils.config_loader import load_config
except ImportError as e:
    print(f"[ERROR] {e}")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# PARAM GROUPS
# ══════════════════════════════════════════════════════════════════════════════

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
        "ASPIRATION_MIN_DEPTH",
        "RAZOR_DEPTH",
        "FUTILITY_DEPTH",
    ],
    "ordering": [
        "MO_KILLER1_SCORE",
        "MO_KILLER2_SCORE",
        "HISTORY_MAX_BONUS",
    ],
    "all": None,  # None = toàn bộ
}

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

WIN  = 1.0
DRAW = 0.5
LOSS = 0.0


def make_executable(path: Path):
    if os.name != "nt" and path.exists():
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


def resolve_engine_path(cmd: str) -> Path:
    path = ROOT / cmd
    if not path.exists():
        raise FileNotFoundError(f"Engine không tìm thấy: {path}")
    make_executable(path)
    return path


def build_engine_args(cmd: str, name: str, options: dict) -> list[str]:
    path = resolve_engine_path(cmd)
    args = [
        "-engine",
        f"name={name}",
        f"cmd={path}",
        "proto=uci",
    ]
    for k, v in options.items():
        args.append(f"option.{k}={v}")
    return args


def parse_pgn_results(pgn_path: Path, n_games: int) -> list[float]:
    """Parse PGN file, trả về list score của WHITE."""
    scores = []
    try:
        with open(pgn_path) as f:
            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                result = game.headers.get("Result", "*")
                if result == "1-0":
                    scores.append(WIN)
                elif result == "0-1":
                    scores.append(LOSS)
                elif result == "1/2-1/2":
                    scores.append(DRAW)
    except Exception as e:
        print(f"  [WARN] PGN parse lỗi: {e}")

    while len(scores) < n_games:
        scores.append(DRAW)

    return scores


# ══════════════════════════════════════════════════════════════════════════════
# CUTECHESS RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_cutechess(
    config:   dict,
    name_w:   str,
    cmd_w:    str,
    opts_w:   dict,
    name_b:   str,
    cmd_b:    str,
    opts_b:   dict,
    n_games:  int,
    trial_id: int,
) -> list[float]:
    """
    Chạy n_games ván qua cutechess-cli.
    Trả về list score của WHITE (1=thắng, 0.5=hòa, 0=thua).
    """
    tournament_cfg = config["tournament"]
    opening        = tournament_cfg.get("opening", {})
    pgn_path       = LOGS_PGN / f"trial_{trial_id}_{name_w}_vs_{name_b}_{int(time.time())}.pgn"
    cutechess      = resolve_engine_path("bin/cutechess-cli")

    cmd = [str(cutechess)]
    cmd += build_engine_args(cmd_w, name_w, opts_w)
    cmd += build_engine_args(cmd_b, name_b, opts_b)

    if opening:
        cmd += [
            "-openings",
            f"file={ROOT / opening['file']}",
            f"format={opening.get('format', 'pgn')}",
            f"order={opening.get('order', 'random')}",
            f"plies={opening.get('plies', 8)}",
        ]

    cmd += [
        "-each", f"tc={tournament_cfg['tc']}",
        "-games",       str(n_games),
        "-repeat",
        "-concurrency", str(tournament_cfg.get("concurrency", 1)),
        "-pgnout",      str(pgn_path),
        "-resign",      "movecount=3", "score=400",
        "-draw",        "movenumber=40", "movecount=8", "score=10",
    ]

    try:
        subprocess.run(
            cmd, cwd=ROOT, check=True,
            capture_output=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        print(f"  [WARN] cutechess timeout trial {trial_id}")
        return [DRAW] * n_games
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] cutechess lỗi: {e.stderr.decode()[:300]}")
        return [DRAW] * n_games

    return parse_pgn_results(pgn_path, n_games)


# ══════════════════════════════════════════════════════════════════════════════
# OBJECTIVE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def make_objective(
    config:        dict,
    engine_cmd:    str,
    engine_opts:   dict,
    opp_cmd:       str,
    opp_opts:      dict,
    games:         int,
    active_params: dict,
):
    """
    Trả về hàm objective cho Optuna.

    Mỗi trial:
      1. Optuna suggest một bộ params mới (thông minh dựa trên lịch sử)
      2. Chạy match: engine(params_new) vs opponent  → wr_vs_opp
      3. Chạy match: engine(params_new) vs engine(default) → wr_vs_default
      4. Objective = 0.6 * wr_vs_opp + 0.4 * wr_vs_default
         (tối đa hóa cả hai: mạnh hơn opponent VÀ mạnh hơn default)
    """

    # Lấy default params để làm baseline so sánh
    default_opts = {k: str(v[0]) for k, v in active_params.items()}

    def objective(trial: optuna.Trial) -> float:
        # Optuna suggest params mới
        suggested = {}
        for name, (default, lo, hi, step) in active_params.items():
            suggested[name] = trial.suggest_int(name, lo, hi, step=step)

        trial_opts = {**engine_opts, **{k: str(v) for k, v in suggested.items()}}
        default_engine_opts = {**engine_opts, **default_opts}

        print(f"\n[Trial {trial.number}] Params: {suggested}")

        half = max(2, games // 2)

        # ── Match 1: engine(suggested) vs opponent ───────────────────────────
        scores_vs_opp = run_cutechess(
            config,
            name_w="engine", cmd_w=engine_cmd, opts_w=trial_opts,
            name_b="opp",    cmd_b=opp_cmd,    opts_b=opp_opts,
            n_games=half, trial_id=trial.number,
        )
        # swap màu
        scores_vs_opp_swap = run_cutechess(
            config,
            name_w="opp",    cmd_w=opp_cmd,    opts_w=opp_opts,
            name_b="engine", cmd_b=engine_cmd, opts_b=trial_opts,
            n_games=half, trial_id=trial.number,
        )
        wr_vs_opp = (
            sum(scores_vs_opp) + sum(1.0 - s for s in scores_vs_opp_swap)
        ) / (len(scores_vs_opp) + len(scores_vs_opp_swap))

        # ── Match 2: engine(suggested) vs engine(default) ────────────────────
        scores_vs_default = run_cutechess(
            config,
            name_w="new",     cmd_w=engine_cmd, opts_w=trial_opts,
            name_b="default", cmd_b=engine_cmd, opts_b=default_engine_opts,
            n_games=half, trial_id=trial.number,
        )
        scores_vs_default_swap = run_cutechess(
            config,
            name_w="default", cmd_w=engine_cmd, opts_w=default_engine_opts,
            name_b="new",     cmd_b=engine_cmd, opts_b=trial_opts,
            n_games=half, trial_id=trial.number,
        )
        wr_vs_default = (
            sum(scores_vs_default) + sum(1.0 - s for s in scores_vs_default_swap)
        ) / (len(scores_vs_default) + len(scores_vs_default_swap))

        # ── Objective tổng hợp ───────────────────────────────────────────────
        objective_value = 0.6 * wr_vs_opp + 0.4 * wr_vs_default

        print(
            f"[Trial {trial.number}] "
            f"wr_vs_opp={wr_vs_opp:.3f}  "
            f"wr_vs_default={wr_vs_default:.3f}  "
            f"→ objective={objective_value:.3f}"
        )
        return objective_value

    return objective


# ══════════════════════════════════════════════════════════════════════════════
# SANITY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def check_engines(engine_cmd: str, opp_cmd: str):
    import chess.engine
    print("[CHECK] Kiểm tra engine...")
    for label, cmd_str in [("engine", engine_cmd), ("opponent", opp_cmd)]:
        path = resolve_engine_path(cmd_str)
        cmd  = [str(path)]
        try:
            e = chess.engine.SimpleEngine.popen_uci(cmd, timeout=15)
            r = e.play(chess.Board(), chess.engine.Limit(time=0.1))
            e.quit()
            print(f"  [{label}] OK — đi: {r.move}")
        except Exception as ex:
            print(f"  [{label}] FAILED: {ex}")
            return False
    return True


# ══════════════════════════════════════════════════════════════════════════════
# PRINT RESULTS
# ══════════════════════════════════════════════════════════════════════════════

def print_results(study: optuna.Study, active_params: dict):
    best = study.best_trial
    print("\n" + "=" * 64)
    print(f"KẾT QUẢ TỐT NHẤT (trial #{best.number}, objective={best.value:.4f})")
    print("=" * 64)
    print("\nPaste vào TUNABLE_PARAMS:")
    for name, val in best.params.items():
        _, lo, hi, step = active_params[name]
        print(f'    "{name}": ({val}, {lo}, {hi}, {step}),')

    print("\nUCI setoption:")
    for name, val in best.params.items():
        print(f"  setoption name {name} value {val}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(description="Bayesian tuner dùng Optuna + cutechess")
    p.add_argument("--config",  default="tournament.yml")
    p.add_argument("--group",   choices=list(PARAM_GROUPS.keys()), default="all")
    p.add_argument("--trials",  type=int,   default=100,
                   help="Số trial Optuna (default=100)")
    p.add_argument("--games",   type=int,   default=8,
                   help="Ván mỗi trial, phải chẵn (default=8)")
    p.add_argument("--resume",  action="store_true",
                   help="Tiếp từ study đã lưu")
    p.add_argument("--check",   action="store_true")
    return p.parse_args()


def main():
    args   = parse_args()
    config = load_config(args.config)

    engines    = config["engines"]
    engine_cfg = engines[0]
    opp_cfg    = engines[1]

    engine_cmd  = engine_cfg["cmd"]
    engine_opts = engine_cfg.get("options", {}) or {}
    opp_cmd     = opp_cfg["cmd"]
    opp_opts    = opp_cfg.get("options", {}) or {}

    print(f"[INFO] engine  : {engine_cmd}")
    print(f"[INFO] opponent: {opp_cmd}  opts={opp_opts}")

    if args.check:
        sys.exit(0 if check_engines(engine_cmd, opp_cmd) else 1)

    # Chọn nhóm params active
    group_keys = PARAM_GROUPS[args.group]
    active_params = (
        {k: v for k, v in TUNABLE_PARAMS.items() if k in group_keys}
        if group_keys
        else dict(TUNABLE_PARAMS)
    )
    print(f"[INFO] Tuning {len(active_params)} params: {list(active_params.keys())}")

    # Tạo hoặc load Optuna study
    # Lưu vào SQLite để resume được
    study_name = f"chess_tuner_{args.group}"
    storage    = f"sqlite:///{DB_PATH}"

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    if args.resume:
        study = optuna.load_study(
            study_name=study_name,
            storage=storage,
            sampler=TPESampler(seed=42),
        )
        print(f"[INFO] Resume study '{study_name}' ({len(study.trials)} trials đã chạy)")
    else:
        study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            direction="maximize",
            sampler=TPESampler(
                seed=42,
                n_startup_trials=10,  # 10 trial đầu random để khám phá
            ),
            load_if_exists=True,
        )

    objective = make_objective(
        config        = config,
        engine_cmd    = engine_cmd,
        engine_opts   = engine_opts,
        opp_cmd       = opp_cmd,
        opp_opts      = opp_opts,
        games         = args.games,
        active_params = active_params,
    )

    try:
        study.optimize(
            objective,
            n_trials=args.trials,
            show_progress_bar=True,
        )
    except KeyboardInterrupt:
        print("\n[STOPPED] Ctrl+C")
    finally:
        print_results(study, active_params)


if __name__ == "__main__":
    main()