"""Fetch the three Wikipedia articles once and freeze them on disk.

Run manually, never as part of the pipeline:

    uv run python scripts/fetch_corpus.py

Wikipedia articles change. docs/IMPLEMENTATION_PLAN.md section 2 decided to fetch once
into data/raw and commit those files, so a rerun at writeup time gives the same numbers
as a run today and a teammate's results cannot silently drift from yours.

Alongside the text this writes data/raw/MANIFEST.json recording the revision id and
fetch date of each article. That is what makes "frozen" checkable rather than a claim:
the revision id pins the exact version of the article the results were built on.

This script is the only thing in the project that touches the network, which is why
`requests` is a dev dependency and not a project dependency.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# Make `src` importable when this file is run directly from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, resolve_path  # noqa: E402
from src.corpus import slugify  # noqa: E402

API_URL = "https://en.wikipedia.org/w/api.php"

# Wikipedia asks that automated requests identify themselves.
USER_AGENT = "RedundancyGatedRAG/0.1 (student project; one-off corpus fetch)"

TIMEOUT_SECONDS = 30


def fetch_page(title: str) -> dict:
    """Fetch one article as plain text, plus the revision id that identifies it.

    One request per title. The extracts API truncates when several titles are asked for
    at once, and a truncated article would be a silent corpus bug.
    """
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "titles": title,
        "prop": "extracts|revisions",
        "explaintext": "1",      # plain text, not HTML or wikitext
        "redirects": "1",        # follow a redirect rather than returning an empty page
        "rvprop": "ids|timestamp",
    }
    response = requests.get(
        API_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()
    payload = response.json()

    pages = payload.get("query", {}).get("pages", [])
    if not pages:
        raise RuntimeError(f"no page returned for '{title}'")
    page = pages[0]
    if page.get("missing"):
        raise RuntimeError(f"wikipedia has no article titled '{title}'")

    revision = page.get("revisions", [{}])[0]
    return {
        "requested_title": title,
        "resolved_title": page["title"],
        "revision_id": revision.get("revid"),
        "revision_timestamp": revision.get("timestamp"),
        "text": page["extract"],
    }


def main() -> None:
    config = load_config()
    titles = config["corpus"]["pages"]
    raw_dir = resolve_path(config["corpus"]["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": API_URL,
        "pages": [],
    }

    for title in titles:
        print(f"fetching: {title}")
        page = fetch_page(title)

        if page["resolved_title"] != page["requested_title"]:
            # Worth seeing. It means config.yaml names a redirect, so the article that
            # actually landed on disk is not the one the config appears to ask for.
            print(
                f"  note: '{page['requested_title']}' redirected to "
                f"'{page['resolved_title']}'"
            )

        out_path = raw_dir / f"{slugify(title)}.txt"
        out_path.write_text(page["text"], encoding="utf-8")

        word_count = len(page["text"].split())
        manifest["pages"].append(
            {
                "requested_title": page["requested_title"],
                "resolved_title": page["resolved_title"],
                "revision_id": page["revision_id"],
                "revision_timestamp": page["revision_timestamp"],
                "file": out_path.name,
                "raw_word_count": word_count,
            }
        )
        print(f"  wrote {out_path.relative_to(resolve_path('.'))}  ({word_count} words, revision {page['revision_id']})")

    manifest_path = raw_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {manifest_path.relative_to(resolve_path('.'))}")
    print("commit data/raw so the corpus stays frozen for everyone.")


if __name__ == "__main__":
    main()
