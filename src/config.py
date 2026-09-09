"""Load config.yaml and enforce decided parameters."""

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Read config.yaml into a plain nested dict."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def require(config: dict[str, Any], dotted_key: str) -> Any:
    """Fetch config value, error if null or missing."""
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"config key not found: {dotted_key}")
        node = node[part]
    if node is None:
        raise ValueError(f"config '{dotted_key}' is undecided (null)")
    return node


def resolve_path(relative: str) -> Path:
    """Convert repo-relative path to absolute path."""
    return REPO_ROOT / relative
