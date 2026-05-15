import subprocess
import sys
from pathlib import Path
import shutil
import os

# =========================
# PATHS
# =========================

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
BIN = ROOT / "bin"
BUILD = ROOT / "build"

ENGINE_NAME = "my_engine"
MAIN_FILE = SRC / "engine" / "uci.py"

ENGINE_BIN = BIN / ENGINE_NAME


# =========================
# HELPERS
# =========================

def run(cmd, check=True):
    print(f"> {cmd}")
    return subprocess.run(cmd, shell=True, check=check)


def has(cmd):
    return subprocess.call(f"which {cmd}", shell=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


# =========================
# DEPENDENCIES (IDEMPOTENT)
# =========================

def ensure_binutils():
    if not has("objdump"):
        print("[DEP] Installing binutils...")
        run("apt update && apt install -y binutils")


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa
        print("[DEP] PyInstaller already installed")
    except ImportError:
        print("[DEP] Installing PyInstaller...")
        run(f"{sys.executable} -m pip install pyinstaller")


# =========================
# CLEAN
# =========================

def clean():
    print("[CLEAN] Removing unused artifacts...")

    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)

    spec_file = ROOT / f"{ENGINE_NAME}.spec"
    if spec_file.exists():
        spec_file.unlink()

    BUILD.mkdir(exist_ok=True)
    BIN.mkdir(exist_ok=True)


# =========================
# REBUILD CHECK
# =========================

def needs_rebuild():
    if not ENGINE_BIN.exists():
        return True

    engine_time = ENGINE_BIN.stat().st_mtime

    for py_file in SRC.rglob("*.py"):
        if py_file.stat().st_mtime > engine_time:
            return True

    return False


# =========================
# BUILD
# =========================

def build():
    print("\n[BUILD] Starting build...\n")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        ENGINE_NAME,
        "--distpath",
        str(BIN),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        "--clean",
        str(MAIN_FILE),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)

    result = subprocess.run(cmd, cwd=ROOT, env=env)

    if result.returncode != 0:
        raise RuntimeError("Build failed")

    clean()

    print(f"\n[OK] Built → {ENGINE_BIN}\n")


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    ensure_binutils()
    ensure_pyinstaller()

    if needs_rebuild():
        build()
    else:
        print(f"\n[SKIP] Up-to-date → {ENGINE_BIN}\n")