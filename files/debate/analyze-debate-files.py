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
COUNTING WORDS  (an earlier version of this script got this wrong)
---------------------------------------------------------------------------
Text nodes split at every formatting boundary, in .cmir exactly as runs do in .docx.
Highlighting the "deter" in "deterrence" produces two adjacent text nodes, and counting
each node separately then reports two words where the document contains one.

An earlier version of this script counted node by node and inflated every total by about
1.9%: 63,837 words for the 2022 file instead of 62,629. Switching formats did not fix
this, and a claim that it had was published for a few hours before a reader compared the
output against another tool and the totals did not agree.

What actually fixes it is tokenising once. The functions below flatten the document to a
stream of characters, each carrying the marks that were active on it, insert a space at
paragraph boundaries so the last word of one block cannot fuse with the first of the next,
and only then split on whitespace. A word crossing a formatting boundary is one word that
carries both sets of marks.

The check that this is right: counting this way gives 62,629 and 66,331, which is exactly
what counting the .docx versions paragraph by paragraph gives. Two unrelated parsers over
two file formats agreeing to the word is the strongest evidence available here.

---------------------------------------------------------------------------
WHICH MARKS ARE COUNTED, AND WHY THE OTHERS ARE NOT
---------------------------------------------------------------------------
These files carry more formatting marks than the two this script reports:

    highlight         counted -- the words a debater says out loud
    underline_mark    counted -- the warrant, underlined inside quoted evidence
    underline_direct  NOT counted -- see below
    emphasis_mark, cite_mark, bold, italic, font_size, font_family, link,
    superscript       not counted; they are typography, not argument marking

`underline_direct` deserves the explanation, because it looks like it should count.
It is underlining applied directly rather than through the evidence-marking system, and
in both of these files it appears **only inside tags** -- 62 text nodes in the 2022 file
and 75 in the 2025 file, none of them in a card body. The words carrying it are the
debater's own emphasis on their own tagline: "stalled", "poisons", "collapses", "invites".

That is a different act from underlining the reasoning inside a piece of quoted evidence,
which is what the published figure measures, so it is excluded on purpose. Including it
would add 80 words to the 2022 file (+0.6%) and 100 to the 2025 file (+1.3%).

If you are adapting this script to other files, check that assumption before trusting it.
A file where underline_direct appears inside card bodies would mean something different,
and this script would then undercount. Print the mark inventory first:

    marks = collections.Counter()
    def scan(n):
        for m in n.get('marks', []) or []: marks[m.get('type')] += 1
        for c in n.get('content', []) or []: scan(c)

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


# Node types that end a paragraph. A space is emitted after each so the last word of one
# block cannot fuse with the first word of the next.
BREAK_TYPES = {'tag', 'card_body', 'cite_paragraph', 'block', 'hat', 'pocket', 'paragraph'}


def _flatten(node, out):
    """Flatten to (character, marks) pairs so the text can be tokenised once."""
    if node.get('type') == 'text':
        marks = frozenset(m.get('type') for m in node.get('marks', []) or [])
        for ch in node.get('text', ''):
            out.append((ch, marks))
    for child in node.get('content', []) or []:
        _flatten(child, out)
    if node.get('type') in BREAK_TYPES:
        out.append((' ', frozenset()))


def count_words(node, mark=None):
    """Words under this node. With `mark`, only words carrying that mark.

    Tokenises the flattened character stream once, so a word split across formatting
    boundaries counts as one word carrying every mark that touched it. See the docstring.
    """
    stream = []
    _flatten(node, stream)
    total, in_word, word_marks = 0, False, set()
    for ch, marks in stream:
        if ch.isspace():
            if in_word and (mark is None or mark in word_marks):
                total += 1
            in_word, word_marks = False, set()
        else:
            in_word = True
            word_marks |= marks
    if in_word and (mark is None or mark in word_marks):
        total += 1
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
