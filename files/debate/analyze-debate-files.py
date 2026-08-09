#!/usr/bin/env python3
"""
analyze-debate-files.py
Reproduces every figure published on https://burdenofproof.education/audience-adaptation.html

Usage:
    python3 analyze-debate-files.py team-affirmative-02-fisheries-2025.cmir
    python3 analyze-debate-files.py *.cmir

No dependencies. A .cmir file is gzipped JSON; the standard library reads it.

---------------------------------------------------------------------------
WHY .cmir AND NOT .docx
---------------------------------------------------------------------------
The first version of this script read the .docx files, and it got the card count wrong.

A .docx stores appearance, not meaning. It knows a paragraph is styled "Heading 4"; it does
not know whether that paragraph is a card tag, an analytic the debater argues in their own
voice, or a heading in a documentation section. All three are formatted alike, because all
three look alike on paper. So the script had to guess -- does the body contain underlining?
is the tag phrased as a question? -- and guessing produced 63 cards in the fisheries file
where a hand count found 56.

CardMirror's .cmir format stores the document model instead:

    hat / pocket / block   the file's outline, so a section like "1AC—Canada" is addressable
    card                   an actual card, typed as such
    tag / card_body        the parts of a card
    cite_paragraph         the citation line, typed as such
    marks: highlight, underline_mark, emphasis_mark, cite_mark

Which makes the analysis a matter of reading fields rather than inferring them. A card is an
evidence card when it contains a cite_paragraph -- there are exactly 56 of those in the
fisheries file and 20 in the cognitive warfare file, matching the hand counts with no
heuristics, no thresholds, and no special cases. Roughly sixty lines of guesswork deleted.

The .docx files remain published alongside these, because Word is what most people have.
They are the same documents. This script reads the .cmir versions because they are the ones
that can be read honestly.

---------------------------------------------------------------------------
COUNTING WORDS
---------------------------------------------------------------------------
Every word is counted once, from the text nodes of the document tree, and each text node
carries its own marks. So a highlighted word and a total word come from the same traversal
and the same tokenizer.

This resolves a problem the .docx version could not avoid. There, formatting boundaries
split runs mid-word -- highlighting the "deter" in "deterrence" produced two runs -- so
counting run by run inflated the total by about 2%, and the published percentages and the
published totals had to use two different denominators. That footnote is now obsolete: one
traversal, one denominator, and the marked-word counts below are exact rather than
approximate.

---------------------------------------------------------------------------
WHAT IS DELIBERATELY NOT HERE
---------------------------------------------------------------------------
An earlier version compared tag vocabulary against English word-frequency bands using the
`wordfreq` package. Those figures are not published and not computed here: the mapping from
Zipf frequency to a difficulty level such as CEFR was an approximation with no source behind
it. The analysis is on the roadmap pending a defensible mapping.
"""

import gzip
import json
import statistics as st
import sys
from collections import OrderedDict
from pathlib import Path

SECTION_TYPES = ('hat', 'pocket', 'block')


def load(path):
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        return json.load(fh)['doc']['content']


def text_of(node):
    if node.get('type') == 'text':
        return node.get('text', '')
    return ''.join(text_of(c) for c in node.get('content', []) or [])


def contains(node, node_type):
    if node.get('type') == node_type:
        return True
    return any(contains(c, node_type) for c in node.get('content', []) or [])


def count_words(node, mark=None):
    """Words under this node. With `mark`, only words carrying that mark."""
    total = 0
    if node.get('type') == 'text':
        marks = {m.get('type') for m in node.get('marks', []) or []}
        if mark is None or mark in marks:
            total += len(node.get('text', '').split())
    for child in node.get('content', []) or []:
        total += count_words(child, mark)
    return total


def is_evidence_card(node):
    """A card with a citation is evidence. A card without one is an analytic."""
    return node.get('type') == 'card' and contains(node, 'cite_paragraph')


def card_body_words(card):
    """Words in the card body, which excludes the tag and the citation line."""
    return sum(count_words(c) for c in card.get('content', []) or []
               if c.get('type') == 'card_body')


def sections(top):
    """Map each section heading to the evidence cards beneath it, in document order."""
    grouped, current = OrderedDict(), None
    for node in top:
        if node['type'] in SECTION_TYPES:
            current = text_of(node).strip()
            grouped.setdefault(current, [])
        elif is_evidence_card(node) and current is not None:
            grouped[current].append(node)
    return grouped


def report(path):
    top = load(path)
    doc = {'type': 'doc', 'content': top}

    total = count_words(doc)
    highlighted = count_words(doc, 'highlight')
    underlined = count_words(doc, 'underline_mark')

    all_cards = [n for n in top if n['type'] == 'card']
    cards = [n for n in all_cards if is_evidence_card(n)]
    body = [card_body_words(c) for c in cards]
    tags = [len(text_of(c.get('content', [])[0]).split())
            for c in cards if c.get('content')]

    print('=' * 74)
    print(Path(path).name)
    print('=' * 74)
    print(f"  words, whole file  : {total:>7,}")
    print(f"  highlighted words  : {highlighted:>7,}   {100 * highlighted / total:5.1f}%   (read aloud)")
    print(f"  underlined words   : {underlined:>7,}   {100 * underlined / total:5.1f}%   (the warrant)")
    print()
    print(f"  card nodes         : {len(all_cards)}")
    print(f"  evidence cards     : {len(cards)}"
          f"   ({len(all_cards) - len(cards)} analytics, no citation)")
    print(f"  tag length, words  : median {st.median(tags):.0f}  mean {st.mean(tags):.1f}"
          f"  range {min(tags)}-{max(tags)}")
    print(f"  card body, words   : median {st.median(body):.0f}  mean {st.mean(body):.0f}"
          f"  range {min(body)}-{max(body)}")
    print(f"  cards over 1,000 w : {sum(b > 1000 for b in body)}/{len(cards)}"
          f" = {100 * sum(b > 1000 for b in body) / len(cards):.0f}%")
    print()
    print("  evidence cards by section:")
    for name, group in sections(top).items():
        if group:
            words = sum(card_body_words(c) for c in group)
            print(f"      {len(group):3d} cards  {words:>6,} words   {name[:52]}")
    print()


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        sys.exit(1)
    for path in paths:
        report(path)


if __name__ == '__main__':
    main()
