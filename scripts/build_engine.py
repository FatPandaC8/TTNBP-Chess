import shutil
import subprocess
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
BIN = ROOT / "bin"

IS_WINDOWS = os.name == "nt"
ENGINE_NAME = "my_engine.exe" if IS_WINDOWS else "my_engine"
ENGINE = BIN / ENGINE_NAME

MAIN_FILE = SRC / "engine" / "uci.py"


def needs_rebuild() -> bool:
    if not ENGINE.exists():
        return True

    engine_time = ENGINE.stat().st_mtime
    source_time = MAIN_FILE.stat().st_mtime

    return source_time > engine_time


def clean_pyinstaller_artifacts():
    """Xóa toàn bộ file rác PyInstaller để chỉ giữ bin/my_engine"""

    dist_dir = ROOT / "dist"
    build_dir = ROOT / "build"
    spec_file = ROOT / "my_engine.spec"

    if dist_dir.exists():
        shutil.rmtree(dist_dir, ignore_errors=True)

    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    if spec_file.exists():
        spec_file.unlink()


def build_engine():
    print("\n[BUILD] Building engine...\n")

    BIN.mkdir(exist_ok=True)

    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "my_engine",
        "--distpath",
        str(BIN),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT),
        "--clean",
        str(MAIN_FILE),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    result = subprocess.run(cmd, cwd=ROOT, env=env)

    if result.returncode != 0:
        raise RuntimeError("Build failed")
    
    clean_pyinstaller_artifacts()

    print("\n[BUILD] Done\n")


if __name__ == "__main__":
    if needs_rebuild():
        build_engine()
    else:
        print("\n[ALREADY BUILT] Engine is up to date")
