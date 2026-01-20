from __future__ import annotations

import re
from typing import List, NamedTuple, Sequence

__all__ = ["TextChunk", "heading_split"]


class TextChunk(NamedTuple):
    text: str
    start: int
    end: int
    heading: str


# ────────────────────────────────────────────────────────────────────
# 1.  Heading regexes
# ────────────────────────────────────────────────────────────────────
# 1.A  ATX‑style Markdown:      ## Results and Discussion
_MD_ATX_RE = re.compile(r"^\s*#{1,6}\s+(?P<text>.+?)\s*$")

# 1.B  Setext‑style Markdown:
#       Results and Discussion
#       ----------------------
_MD_SETEXT_RE = re.compile(r"^\s*(?P<text>[^=\-].+?)\s*\n[=\-]{2,}\s*$", re.MULTILINE)

# 1.C  Numeric or ALL‑CAP journal headings
_JOURNAL_RE = re.compile(
    r"""
    ^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?          # optional numbering
    (?P<text>
        (?:[A-Z][A-Z\s\-]{2,60})            # ALL‑CAPS   e.g.  MATERIALS AND METHODS
        |
        (?:[A-Z][A-Za-z0-9\- ]{2,60})       # Title Case e.g.  Solid‑Surface Vitrification
    )\s*$
    """,
    re.VERBOSE,
)

# Fallback chunk length (characters) when no headings are found
_FALLBACK_SIZE = 10_000


# ────────────────────────────────────────────────────────────────────
# 2.  Helper functions
# ────────────────────────────────────────────────────────────────────
def _strip_hashes(s: str) -> str:
    """Remove leading Markdown hashes and surrounding whitespace."""
    return s.lstrip("#").strip()


def _iter_heading_matches(text: str):
    """
    Yield tuples (start_pos, end_pos, heading_text) for every heading
    found *outside* fenced code blocks.
    """
    code_block = False
    pos = 0  # running character offset
    lines = text.splitlines(keepends=True)

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            code_block = not code_block
            pos += len(line)
            i += 1
            continue

        if not code_block:
            # 2.a ATX‑style
            m = _MD_ATX_RE.match(line)
            if m:
                yield pos, pos + len(line), _strip_hashes(m.group("text"))
                pos += len(line)
                i += 1
                continue

            # 2.b Setext‑style (needs look‑ahead)
            if i + 1 < len(lines) and _MD_SETEXT_RE.match("".join(lines[i : i + 2])):
                m = _MD_SETEXT_RE.match("".join(lines[i : i + 2]))
                assert m is not None
                combined_len = len(lines[i]) + len(lines[i + 1])
                yield pos, pos + combined_len, m.group("text").strip()
                pos += combined_len
                i += 2
                continue

            # 2.c Journal‑style
            m = _JOURNAL_RE.match(line)
            if m:
                yield pos, pos + len(line), m.group("text").strip()
                pos += len(line)
                i += 1
                continue

        # Default: not a heading
        pos += len(line)
        i += 1


def _fallback_slices(text: str, size: int) -> Sequence[TextChunk]:
    slices = []
    for i in range(0, len(text), size):
        start, end = i, min(i + size, len(text))
        slices.append(TextChunk(text=text[start:end], start=start, end=end, heading="(fallback)"))
    return slices


# ────────────────────────────────────────────────────────────────────
# 3.  Public API
# ────────────────────────────────────────────────────────────────────
def heading_split(
    text: str,
    *,
    window_prev: int = 0,
    window_next: int = 0,
    fallback_size: int = _FALLBACK_SIZE,
) -> List[TextChunk]:
    """
    Parameters
    ----------
    text : str
        Full Markdown / plain‑text content of the article.

    window_prev / window_next : int, default 0
        How many *adjacent* heading blocks to prepend/append so the LLM
        sees a bit of context.  Example: with `window_prev=1` each chunk
        begins one heading *earlier* than its logical section.

    fallback_size : int
        If no headings are detected, chunk by fixed character size.

    Returns
    -------
    List[TextChunk]
    """

    matches = list(_iter_heading_matches(text))
    if not matches:
        return list(_fallback_slices(text, fallback_size))

    # Build list of boundary offsets
    boundaries = [start for start, _, _ in matches] + [len(text)]
    chunks: List[TextChunk] = []

    for idx, (head_start, head_end, head_text) in enumerate(matches):
        # True [start, end) of this logical section
        true_start = head_start
        true_end = boundaries[idx + 1]

        # Expand with window
        win_start = boundaries[max(0, idx - window_prev)]
        win_end = boundaries[min(len(matches), idx + 1 + window_next)]

        chunks.append(
            TextChunk(
                text=text[win_start:win_end],
                start=win_start,
                end=win_end,
                heading=head_text,
            )
        )

    return chunks
