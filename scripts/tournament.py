import os
import sys
import stat
import shutil
import platform
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT / "bin"


def make_executable(path: Path):
    if os.name != "nt":
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IEXEC)


def detect_platform():
    system = platform.system().lower()

    if system == "windows":
        return "windows"

    if system == "darwin":
        return "macos"

    return "linux"


def expected_binaries():
    current = detect_platform()

    if current == "windows":
        return {
            "cutechess": BIN_DIR / "cutechess-cli.exe",
            "stockfish": BIN_DIR / "stockfish.exe",
            "my_engine": BIN_DIR / "my_engine.exe",
        }

    return {
        "cutechess": BIN_DIR / "cutechess-cli",
        "stockfish": BIN_DIR / "stockfish",
        "my_engine": BIN_DIR / "uci",
    }


def print_missing_binary_help(name: str):
    current = detect_platform()

    print(f"\n[ERROR] Missing binary: {name}\n")

    if name == "cutechess":
        print("Download CuteChess CLI:")
        print("https://github.com/cutechess/cutechess/releases")

        if current == "windows":
            print("\nExpected file:")
            print("bin/cutechess-cli.exe")

        else:
            print("\nExpected file:")
            print("bin/cutechess-cli")

    elif name == "stockfish":
        print("Download Stockfish:")
        print("https://stockfishchess.org/download/")

        if current == "windows":
            print("\nExpected file:")
            print("bin/stockfish.exe")

        else:
            print("\nExpected file:")
            print("bin/stockfish")

    print()


def check_binaries():
    bins = expected_binaries()

    missing = False

    for name, path in bins.items():
        if not path.exists():
            missing = True
            print_missing_binary_help(name)
        else:
            make_executable(path)

    return not missing


def run_tournament(games=20, concurrency=1, tc="1+0.1"):
    bins = expected_binaries()

    cutechess = bins["cutechess"]
    stockfish = bins["stockfish"]
    my_engine = bins["my_engine"]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    cmd = [
        str(cutechess),

        "-engine",
        "name=MyEngine",
        f"cmd={my_engine}",
        f"dir={ROOT}",

        "-engine",
        "name=Stockfish",
        f"cmd={stockfish}",

        "-each",
        "proto=uci",
        f"tc={tc}",

        "-games",
        str(games),

        "-repeat",

        "-concurrency",
        str(concurrency),
    ]

    print("\n[TOURNAMENT] Running:\n")
    print(" ".join(cmd))
    print()

    subprocess.run(
        cmd,
        cwd=ROOT,
        env=env
    )


def main():

    if not check_binaries():
        return

    run_tournament()


if __name__ == "__main__":
    main()
