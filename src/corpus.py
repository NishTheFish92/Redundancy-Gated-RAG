"""Corpus loading, cleaning and chunking."""

import re
from dataclasses import dataclass
from pathlib import Path

HEADING_RE = re.compile(r"^(=+)\s*(.*?)\s*\1$")


@dataclass(frozen=True)
class Chunk:
    """One retrievable unit."""

    chunk_id: int
    page: str
    text: str
    n_words: int


def slugify(title: str) -> str:
    """Convert title to filename slug."""
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def clean_text(text: str, strip_sections: list[str], keep_headings: bool = True) -> str:
    """Remove specified sections and clean heading markup."""
    strip_lower = {s.lower() for s in strip_sections}
    kept_lines: list[str] = []
    in_stripped_section = False

    for line in text.splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            depth, heading = len(match.group(1)), match.group(2)
            if depth == 2:
                in_stripped_section = heading.lower() in strip_lower
            if in_stripped_section:
                continue
            if keep_headings:
                kept_lines.append(heading)
            continue

        if not in_stripped_section:
            kept_lines.append(line)

    cleaned = "\n".join(kept_lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def load_pages(
    raw_dir: str | Path,
    pages: list[str],
    strip_sections: list[str],
    keep_headings: bool = True,
) -> dict[str, str]:
    """Load and clean raw text for each page."""
    raw_dir = Path(raw_dir)
    loaded: dict[str, str] = {}
    for title in pages:
        path = raw_dir / f"{slugify(title)}.txt"
        if not path.exists():
            raise FileNotFoundError(f"missing raw text: {path}")
        raw = path.read_text(encoding="utf-8")
        loaded[title] = clean_text(raw, strip_sections, keep_headings)
    return loaded


def chunk_pages(
    pages: dict[str, str],
    chunk_size_words: int,
    overlap_words: int,
    min_chunk_words: int,
) -> list[Chunk]:
    """Cut each page into fixed-size word windows."""
    if overlap_words >= chunk_size_words:
        raise ValueError(
            f"overlap_words ({overlap_words}) must be < chunk_size_words ({chunk_size_words})"
        )

    step = chunk_size_words - overlap_words
    chunks: list[Chunk] = []

    for title, text in pages.items():
        words = text.split()
        for start in range(0, len(words), step):
            window = words[start : start + chunk_size_words]
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
