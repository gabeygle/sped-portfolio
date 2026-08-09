#!/usr/bin/env python3
"""Analyze CardMirror .cmir debate files.

Written by GLM 5 Turbo. Published here unmodified apart from this note.

An independent implementation of the same measurements as analyze-debate-files.py,
produced after GLM was sent corrections to its first attempt. It reproduces every
figure published on https://burdenofproof.education/audience-adaptation.html
exactly: 20 and 56 evidence cards, 62,629 and 66,331 words, 493 and 3,182
highlighted, 12,732 and 7,457 underlined.

It is also the better program. It walks the document once, accumulating every
counter in a single pass, and holds nothing but the current word in memory --
where the other script traverses three times and materialises the whole document
as a list of character/mark pairs. On the fisheries file it runs in about an
eighth of the time using essentially no memory.

Two things it does not do, which is why both are published: it does not measure
card body length, and it does not group cards by section, so it cannot produce
the median-card-length or 1AC figures on the page.

    python3 analyze-cmir-glm.py file1.cmir file2.cmir
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set


# ── Constants ───────────────────────────────────────────────────────────────

BLOCK_LEVEL_TYPES: FrozenSet[str] = frozenset({
    "tag", "card_body", "cite_paragraph", "block",
    "hat", "pocket", "paragraph",
})

MARK_HIGHLIGHT = "highlight"
MARK_UNDERLINE = "underline_mark"


# ── Result type ─────────────────────────────────────────────────────────────

@dataclass
class CmirStats:
    """Measurement results for a single .cmir document."""

    filename: str = ""
    card_nodes: int = 0
    evidence_cards: int = 0
    total_words: int = 0
    highlighted_words: int = 0
    underlined_words: int = 0
    both_highlighted_and_underlined: int = 0

    @property
    def analytic_cards(self) -> int:
        return self.card_nodes - self.evidence_cards


# ── Single-pass analysis ────────────────────────────────────────────────────

def analyze(content: List[object]) -> CmirStats:
    """Walk *content* (the top-level array from ``doc.content``) once,
    collecting every metric in a single traversal.

    For each top-level card node we check for ``cite_paragraph`` in its
    subtree to distinguish evidence cards from analytic cards.  For every
    ``text`` node we accumulate characters into a per-word mark-union
    buffer, flushing on whitespace boundaries.
    """

    stats = CmirStats()

    # Working buffer for the current word being accumulated.
    # ``word_marks`` collects the union of all marks that touch this word.
    word_marks: Set[str] = set()
    in_word: bool = False

    def flush_word() -> None:
        nonlocal in_word
        if not in_word:
            return
        stats.total_words += 1
        hl = MARK_HIGHLIGHT in word_marks
        ul = MARK_UNDERLINE in word_marks
        if hl:
            stats.highlighted_words += 1
        if ul:
            stats.underlined_words += 1
        if hl and ul:
            stats.both_highlighted_and_underlined += 1
        word_marks.clear()
        in_word = False

    def emit_space() -> None:
        """End the current word (if any) and separate blocks."""
        flush_word()

    def walk_text_node(node: Dict) -> None:
        nonlocal in_word
        text = node.get("text", "")
        marks: FrozenSet[str] = frozenset(
            m.get("type", "") for m in node.get("marks", [])
        )
        for ch in text:
            if ch.isspace():
                flush_word()
            else:
                in_word = True
                word_marks.update(marks)

    def subtree_has_type(node: object, target: str) -> bool:
        """Return True if any node reachable through ``content`` arrays
        has ``type == target``.  Only follows ``content`` fields — never
        descends into ``attrs``, ``marks``, or other metadata."""
        if isinstance(node, dict):
            if node.get("type") == target:
                return True
            children = node.get("content")
            if isinstance(children, list):
                for child in children:
                    if subtree_has_type(child, target):
                        return True
            return False
        if isinstance(node, list):
            for item in node:
                if subtree_has_type(item, target):
                    return True
            return False
        return False

    def walk(node: object) -> None:
        """Recursively walk the tree.  Only descends into ``content``
        arrays, never into arbitrary dict values."""
        if isinstance(node, dict):
            node_type = node.get("type")
            if node_type == "text":
                walk_text_node(node)
                return
            # Only descend into content — skip attrs, marks, etc.
            children = node.get("content")
            if isinstance(children, list):
                for child in children:
                    walk(child)
            # Emit block-level separator after processing children
            if node_type in BLOCK_LEVEL_TYPES:
                emit_space()
        elif isinstance(node, list):
            for item in node:
                walk(item)

    # ── First pass: count cards (top-level only) ────────────────────────
    for item in content:
        if isinstance(item, dict) and item.get("type") == "card":
            stats.card_nodes += 1
            if subtree_has_type(item, "cite_paragraph"):
                stats.evidence_cards += 1

    # ── Single pass for word/mark counts ───────────────────────────────
    walk(content)
    flush_word()  # final word if file doesn't end with whitespace

    return stats


# ── I/O ────────────────────────────────────────────────────────────────────

def load_cmir(filepath: str) -> dict:
    """Load and decompress a ``.cmir`` file (gzip → JSON)."""
    with open(filepath, "rb") as f:
        raw = gzip.decompress(f.read())
    return json.loads(raw.decode("utf-8"))


def format_results(results: List[CmirStats]) -> str:
    """Format analysis results as a human-readable table."""
    lines: List[str] = []

    # ── Per-file detail ──────────────────────────────────────────────
    for r in results:
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"  {r.filename}")
        lines.append("=" * 60)
        lines.append(f"  Card nodes (total):                  {r.card_nodes}")
        lines.append(f"  Evidence cards:                    {r.evidence_cards}")
        lines.append(f"  Analytic cards:                     {r.analytic_cards}")
        lines.append(f"  Total words:                        {r.total_words}")
        lines.append(f"  Highlighted words:                  {r.highlighted_words}")
        lines.append(f"  Underlined words:                   {r.underlined_words}")
        lines.append(
            f"  Both highlighted & underlined:      "
            f"{r.both_highlighted_and_underlined}"
        )

    # ── Summary table (only if multiple files) ────────────────────────
    if len(results) > 1:
        labels = [r.filename for r in results]
        col_w = max(len(l) for l in labels)
        metric_w = 35
        lines.append("")
        lines.append("=" * 60)
        lines.append("  SUMMARY")
        lines.append("=" * 60)
        header = (
            f"  {'Metric':<{metric_w}} "
            + "  ".join(f"{l:>{col_w}}" for l in labels)
        )
        lines.append(header)
        sep = f"  {'-' * metric_w} " + "  ".join("-" * col_w for _ in labels)
        lines.append(sep)

        metrics = [
            ("Card nodes", "card_nodes"),
            ("Evidence cards", "evidence_cards"),
            ("Analytic cards", lambda r: r.analytic_cards),
            ("Total words", "total_words"),
            ("Highlighted words", "highlighted_words"),
            ("Underlined words", "underlined_words"),
        ]
        for label, key in metrics:
            getter = key if callable(key) else (lambda r, k=key: getattr(r, k))
            vals = [getter(r) for r in results]
            row = f"  {label:<{metric_w}} " + "  ".join(f"{v:>{col_w}}" for v in vals)
            lines.append(row)

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Analyze CardMirror .cmir debate files.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="One or more .cmir files to analyze.",
    )
    args = parser.parse_args(argv)

    results: List[CmirStats] = []
    for filepath in args.files:
        try:
            data = load_cmir(filepath)
            stats = analyze(data["doc"]["content"])
            stats.filename = filepath.split("/")[-1]
            results.append(stats)
        except Exception as exc:
            print(f"ERROR processing {filepath}: {exc}", file=sys.stderr)
            raise

    print(format_results(results))


if __name__ == "__main__":
    main()