"""Load config.yaml.

The only job here is reading the file and refusing to hand back a value that the team
has not decided yet. Undecided knobs are null in config.yaml, and `require` turns a
null into a loud error naming the knob, so an unmade decision can never silently
become a default buried in logic.
"""

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
    """Fetch a config value, erroring out if it is still undecided.

    Example: require(config, "gate.tau") raises while tau is null in config.yaml.
    """
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"config key not found: {dotted_key}")
        node = node[part]
    if node is None:
        raise ValueError(
            f"config value '{dotted_key}' is still undecided (null in config.yaml). "
            f"See docs/CHECKLIST.md, it is on the 'Still open' list. Decide it and "
            f"write the reasoning into the docs before using it."
        )
    return node


def resolve_path(relative: str) -> Path:
    """Turn a repo-relative config path like 'data/raw' into an absolute path, so
    scripts and notebooks work regardless of the directory they are run from."""
    return REPO_ROOT / relative
