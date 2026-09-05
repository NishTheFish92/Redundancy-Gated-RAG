"""Corpus loading, cleaning and chunking.

Reads the frozen Wikipedia text in data/raw, cuts the noise sections, and cuts what is
left into fixed-size word windows. Nothing here touches the embedding model.

The two decisions this file implements, both recorded in docs/IMPLEMENTATION_PLAN.md
section 2:

  Cleaning. The sections named in config are removed before chunking. Measured on the
  frozen corpus this removes about 2 percent of each article, not the large cut the
  original reasoning assumed: the Wikipedia plaintext export already discards citation
  text, so References arrives as a heading with nothing under it. The step still earns
  its place, since those orphan heading words would otherwise land inside a chunk as
  body text, but do not oversell it.

  Chunking. Fixed-size word windows with zero overlap. Fixed size keeps chunk lengths
  comparable, which is what lets a single global tau and delta mean the same thing for
  every pair. Zero overlap matters more: overlapping windows are near-duplicates by
  construction, so overlap would manufacture the exact redundancy this project claims
  to discover in the data.
"""

import re
from dataclasses import dataclass
from pathlib import Path

# A wikipedia plaintext extract marks sections like "== Causes ==" and subsections like
# "=== Type 1 ===". Group 1 is the run of '=' signs, which gives the heading depth.
HEADING_RE = re.compile(r"^(=+)\s*(.*?)\s*\1$")


@dataclass(frozen=True)
class Chunk:
    """One retrievable unit. `chunk_id` is the row index into the similarity matrix, so
    it is assigned once here and never reordered afterwards."""

    chunk_id: int
    page: str
    text: str
    n_words: int


def slugify(title: str) -> str:
    """'Type 1 diabetes' -> 'type_1_diabetes'. Used for raw text filenames so the page
    title in config.yaml is the single source of truth for what gets loaded."""
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def clean_text(text: str, strip_sections: list[str], keep_headings: bool = True) -> str:
    """Drop the sections named in `strip_sections` and tidy the heading markup.

    A stripped section takes its subsections with it, so removing "References" also
    removes anything nested underneath it. Matching on the heading name is
    case-insensitive because article headings are not perfectly consistent.

    With `keep_headings` on, a heading line becomes its plain words ("== Causes ==" is
    kept as "Causes"). The words are genuine topic signal and fixed-size windows absorb
    them mid-chunk, which is the point: a splitter that respected line structure could
    emit "Causes" as its own tiny chunk, and those match across all three articles at
    very high similarity, inflating the duplicate rate with a real but uninteresting
    artifact.
    """
    strip_lower = {s.lower() for s in strip_sections}
    kept_lines: list[str] = []
    in_stripped_section = False

    for line in text.splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            depth, heading = len(match.group(1)), match.group(2)
            # Only top level sections (==) open or close a stripped region. A deeper
            # heading inherits whatever region it is sitting inside.
            if depth == 2:
                in_stripped_section = heading.lower() in strip_lower
            if in_stripped_section:
                continue
            if keep_headings:
                kept_lines.append(heading)
            continue

        if not in_stripped_section:
            kept_lines.append(line)

    # Collapse the runs of blank lines left behind by the removals.
    cleaned = "\n".join(kept_lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def load_pages(
    raw_dir: str | Path,
    pages: list[str],
    strip_sections: list[str],
    keep_headings: bool = True,
) -> dict[str, str]:
    """Read the frozen raw text for each page in `pages` and clean it.

    `pages` comes from config rather than from listing the directory, because the order
    of this dict decides the order chunk ids are assigned in, and chunk id is the
    project's tie-break key. Directory listing order is not guaranteed, config order is.
    """
    raw_dir = Path(raw_dir)
    loaded: dict[str, str] = {}
    for title in pages:
        path = raw_dir / f"{slugify(title)}.txt"
        if not path.exists():
            raise FileNotFoundError(
                f"missing raw text for '{title}' at {path}. "
                f"Run: uv run python scripts/fetch_corpus.py"
            )
        raw = path.read_text(encoding="utf-8")
        loaded[title] = clean_text(raw, strip_sections, keep_headings)
    return loaded


def chunk_pages(
    pages: dict[str, str],
    chunk_size_words: int,
    overlap_words: int,
    min_chunk_words: int,
) -> list[Chunk]:
    """Cut each page into fixed-size word windows. Windows never cross a page boundary.

    Chunk ids run 0..n-1 in page order, then in position order within a page, which
    makes the "break ties by chunk id ascending" rule reproducible across runs.
    """
    if overlap_words >= chunk_size_words:
        raise ValueError(
            f"overlap_words ({overlap_words}) must be smaller than chunk_size_words "
            f"({chunk_size_words}), otherwise the window never advances"
        )

    step = chunk_size_words - overlap_words
    chunks: list[Chunk] = []

    for title, text in pages.items():
        words = text.split()
        for start in range(0, len(words), step):
            window = words[start : start + chunk_size_words]
            # Only the trailing window of a page can fall under the floor. DECIDED:
            # drop it rather than merging it into the previous chunk. Measured on the
            # frozen corpus this discards 18 words out of 20,304, the tail of the
            # Diabetes article, and it keeps every chunk at or under chunk_size_words.
            if len(window) < min_chunk_words:
                continue
            chunks.append(
                Chunk(
                    chunk_id=len(chunks),
                    page=title,
                    text=" ".join(window),
                    n_words=len(window),
                )
            )

    return chunks
