from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = ROOT / "config"


def load_config(file_name):
    file_path = CONFIG_DIR / file_name

    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")

    with open(file_path, "r", encoding='utf-8') as f:
        return yaml.safe_load(f)