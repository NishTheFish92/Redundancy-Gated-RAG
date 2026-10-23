"""Load config.yaml and resolve the repo-relative paths in it."""

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Read config.yaml into a plain nested dict."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(relative: str) -> Path:
    """Turn a repo-relative config path like 'data/raw' into an absolute path, so
    scripts and notebooks work regardless of the directory they are run from."""
    return REPO_ROOT / relative
