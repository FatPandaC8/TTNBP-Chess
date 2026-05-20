import os
import stat
import subprocess
from pathlib import Path

from engine.utils.config_loader import load_config
from engine.utils.date_time import timestamp


ROOT = Path(__file__).resolve().parent.parent
LOGS_PGN_DIR = ROOT / "logs" / "pgn"

LOGS_PGN_DIR.mkdir(exist_ok=True)


# =========================
# HELPERS
# =========================

def make_executable(path: Path):
    if os.name != "nt" and path.exists():
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IEXEC)


def resolve_engine_path(cmd: str) -> Path:
    path = ROOT / cmd

    if not path.exists():
        raise FileNotFoundError(
            f"Engine binary not found: {path}"
        )

    make_executable(path)

    return path


# =========================
# ENGINE ARGS
# =========================

def build_engine_args(engine_cfg):
    engine_path = resolve_engine_path(engine_cfg["cmd"])

    args = [
        "-engine",
        f"name={engine_cfg['name']}",
        f"cmd={engine_path}",
        "proto=uci",
    ]

    options = engine_cfg.get("options", {})

    for key, value in options.items():
        args.append(f"option.{key}={value}")

    return args


# =========================
# BUILD COMMAND
# =========================

def build_cutechess_command(config):
    tournament_cfg = config["tournament"]
    engines_cfg = config["engines"]

    cutechess = resolve_engine_path("bin/cutechess-cli")

    cmd = [str(cutechess)]

    # Engines
    for engine_cfg in engines_cfg:
        cmd.extend(build_engine_args(engine_cfg))

    # Openings
    opening = tournament_cfg.get("opening")

    if opening:
        cmd.extend([
            "-openings",
            f"file={ROOT / opening['file']}",
            f"format={opening.get('format', 'pgn')}",
            f"order={opening.get('order', 'random')}",
            f"plies={opening.get('plies', 8)}",
        ])

    # Tournament settings
    cmd.extend([
        "-each",
        f"tc={tournament_cfg['tc']}",

        "-games",
        str(tournament_cfg["games"]),

        "-repeat",

        "-concurrency",
        str(tournament_cfg["concurrency"]),

        "-pgnout",
        str(LOGS_PGN_DIR / f"game_{timestamp()}.pgn"),
    ])

    return cmd


# =========================
# RUN
# =========================

def run_tournament(config):
    cmd = build_cutechess_command(config)

    print("\n[TOURNAMENT] Running:\n")
    print(" ".join(map(str, cmd)))
    print()

    subprocess.run(
        cmd,
        cwd=ROOT,
        check=True,
    )


# =========================
# MAIN
# =========================

def main():
    config = load_config("tournament.yml")
    run_tournament(config)


if __name__ == "__main__":
    main()
