#!/usr/bin/env python3
"""
analyze-debate-files-commented.py

The same program as analyze-debate-files.py, with a comment on every line explaining
what it does and why. If you want to audit the numbers on
https://burdenofproof.education/audience-adaptation.html but do not write Python, read
this version. If you do write Python, read the other one; the comments here will annoy you.

Run it like this:

    python3 analyze-debate-files-commented.py team-affirmative-02-fisheries-2025.cmir

There is nothing to install. A .cmir file is a JSON document that has been gzipped, and
Python reads both formats out of the box.

WHAT A .cmir FILE ACTUALLY IS
-----------------------------
Unzip one and you get a tree of nested boxes. Each box is a dict with a "type" telling you
what kind of thing it is, and usually a "content" list holding the boxes inside it:

    {"type": "card", "content": [
        {"type": "tag",            "content": [{"type": "text", "text": "Canada agrees."}]},
        {"type": "cite_paragraph", "content": [{"type": "text", "text": "Huebert 25 ..."}]},
        {"type": "card_body",      "content": [{"type": "text", "text": "The long-standing ..."}]}
    ]}

The actual words only ever live in "text" boxes at the very bottom. A text box can also
carry "marks", which is how highlighting and underlining are stored:

    {"type": "text", "text": "cause extinction",
     "marks": [{"type": "highlight"}, {"type": "underline_mark"}]}

So almost every function below is some version of the same move: walk down through the
tree until you hit the text boxes, then count something about them.
"""

# ---------------------------------------------------------------------------
# IMPORTS - the standard-library tools this script borrows.
# ---------------------------------------------------------------------------

import gzip                          # unzips the .cmir file (it is gzip-compressed)
import json                          # turns the unzipped text into Python dicts and lists
import statistics as st              # gives us median() and mean(); "as st" is just a nickname
import sys                           # lets us read the filenames typed on the command line
from collections import OrderedDict  # a dict that remembers insertion order, for the outline
from pathlib import Path             # tidy way to pull a filename out of a full path

# A tuple of the three node types CardMirror uses for headings. A "hat" is a top-level
# heading, a "pocket" groups a set of blocks, a "block" is a single section such as
# "1AC-Canada". Keeping them in one place means the rest of the script can just ask
# "is this node one of the heading types?" without repeating all three names.
SECTION_TYPES = ('hat', 'pocket', 'block')


# ---------------------------------------------------------------------------
# READING THE FILE
# ---------------------------------------------------------------------------

def load(path):
    """Open a .cmir file and hand back the list of top-level nodes inside it."""
    # gzip.open with 'rt' means "read this gzipped file as text, not raw bytes".
    # The `with` block closes the file automatically when we are done with it.
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        # json.load turns the file's text into Python objects: dicts, lists, strings.
        # The result has some wrapper keys; ['doc']['content'] reaches past them to the
        # actual list of nodes, which is what every other function here expects.
        return json.load(fh)['doc']['content']


# ---------------------------------------------------------------------------
# THREE WAYS OF WALKING THE TREE
#
# Each of these calls itself on its own children. That is called recursion, and it is the
# natural shape for a tree: "handle this node, then do the same to everything inside it."
# ---------------------------------------------------------------------------

def text_of(node):
    """Return all the text inside a node, with its formatting thrown away."""
    # Base case: if this node IS a text box, hand back its words and stop descending.
    # .get('text', '') means "give me the text key, or an empty string if there isn't one",
    # which avoids a crash on a malformed node.
    if node.get('type') == 'text':
        return node.get('text', '')
    # Otherwise this node is a container, so ask each child for its text and glue the
    # answers together. `or []` covers nodes with no 'content' key at all - without it,
    # the loop would try to iterate over None and crash.
    return ''.join(text_of(c) for c in node.get('content', []) or [])


def contains(node, node_type):
    """True if a node of this type is anywhere inside (used to spot cite_paragraph)."""
    # Check the node itself first. A node counts as containing its own type.
    if node.get('type') == node_type:
        return True
    # any() stops at the first True, so this quits early once it finds a match instead of
    # walking the rest of the tree for no reason.
    return any(contains(c, node_type) for c in node.get('content', []) or [])


def count_words(node, mark=None):
    """Count words under a node. Pass a mark name to count only marked words."""
    total = 0                                  # running tally for this branch of the tree
    if node.get('type') == 'text':             # only text boxes contain actual words
        # Collect this text box's mark names into a set: {'highlight', 'underline_mark'}.
        # A set is used because we only care whether a mark is present, not how many times.
        marks = {m.get('type') for m in node.get('marks', []) or []}
        # Two cases count: no mark was requested (so count everything), or the requested
        # mark is on this text. Anything else is skipped.
        if mark is None or mark in marks:
            # .split() with no argument splits on any whitespace and discards the blanks,
            # so "the  fish " becomes ['the', 'fish'] and len() gives 2. This is the same
            # tokenizer used for every count in the script, which is the point: totals and
            # highlighted counts come from one traversal and one definition of "a word",
            # so the percentages cannot drift apart.
            total += len(node.get('text', '').split())
    # Whether or not this node held text, recurse into its children and add their totals.
    for child in node.get('content', []) or []:
        total += count_words(child, mark)
    return total


# ---------------------------------------------------------------------------
# TELLING CARDS APART FROM ANALYTICS
#
# This is the part that reading .docx got wrong. In Word, a card tag and an analytic are
# both just bold text, so the old script had to guess from formatting. Here the file
# labels its own parts, so we can simply look.
# ---------------------------------------------------------------------------

def is_evidence_card(node):
    """True for a card backed by a source; False for an analytic."""
    # Two conditions, and both must hold. First, the node must be a card at all. Second,
    # it must contain a cite_paragraph - the citation line naming the author and date.
    # A card with a citation is quoted evidence. A card without one is an analytic: an
    # argument the debater makes in their own voice. That single distinction is what
    # reproduces the hand count of 20 and 56 exactly, with no thresholds or special cases.
    return node.get('type') == 'card' and contains(node, 'cite_paragraph')


def card_body_words(card):
    """Length of a card's quoted body, excluding its tag and citation line."""
    # Only count children of type 'card_body'. The tag is the debater's own summary and
    # the citation is bibliographic, so neither belongs in "how long is this card".
    # A card can hold several card_body paragraphs, hence the sum.
    return sum(count_words(c) for c in card.get('content', []) or []
               if c.get('type') == 'card_body')


def sections(top):
    """Group the evidence cards under whichever heading they appear beneath."""
    # OrderedDict keeps sections in the order they appear in the document. `current` holds
    # the heading we are underneath right now; it starts as None because the file might
    # open with something before any heading.
    grouped, current = OrderedDict(), None
    # The top level of a .cmir is a flat list: heading, card, card, heading, card...
    # so walking it in order and remembering the last heading seen rebuilds the nesting.
    for node in top:
        if node['type'] in SECTION_TYPES:
            # A heading. Remember its text, stripped of stray spaces, as the current section.
            current = text_of(node).strip()
            # setdefault creates an empty list for this heading if we have not seen it
            # before, and leaves any existing list alone if we have.
            grouped.setdefault(current, [])
        elif is_evidence_card(node) and current is not None:
            # A card, and we know which section we are in, so file it there.
            grouped[current].append(node)
    return grouped
    # This is how the 1AC gets counted separately. The 2025 file's 1AC is the sections
    # "1AC-Canada" and "1AC-CAOFA", 12 cards plus 18, which is the 30 published on the page.


# ---------------------------------------------------------------------------
# PRINTING THE RESULTS
# ---------------------------------------------------------------------------

def report(path):
    """Run every measurement on one file and print it."""
    top = load(path)                      # the list of top-level nodes
    doc = {'type': 'doc', 'content': top}  # wrap that list back into a single node, because
                                           # count_words expects one node rather than a list

    # Three whole-file numbers, each one a full walk of the tree. Same traversal, same
    # tokenizer, so the percentages below are exact rather than approximate.
    total = count_words(doc)                        # every word in the document
    highlighted = count_words(doc, 'highlight')     # words a student reads aloud
    underlined = count_words(doc, 'underline_mark')  # words marking the reasoning

    # Now the card-level numbers.
    all_cards = [n for n in top if n['type'] == 'card']      # every card-shaped node
    cards = [n for n in all_cards if is_evidence_card(n)]    # only those with a citation
    body = [card_body_words(c) for c in cards]               # each card's body length
    # Each card's tag is its first child, so content[0] is the tag and text_of reads it.
    # The `if c.get('content')` guard skips any empty card rather than crashing on it.
    tags = [len(text_of(c.get('content', [])[0]).split())
            for c in cards if c.get('content')]

    # Everything from here down is formatting. The f-strings hold small instructions:
    # {total:>7,} means "pad to 7 characters, right-aligned, with thousands separators",
    # and :5.1f means "five characters wide, one decimal place".
    print('=' * 74)                       # a rule made of 74 equals signs
    print(Path(path).name)                # just the filename, not the whole path
    print('=' * 74)
    print(f"  words, whole file  : {total:>7,}")
    print(f"  highlighted words  : {highlighted:>7,}   {100 * highlighted / total:5.1f}%   (read aloud)")
    print(f"  underlined words   : {underlined:>7,}   {100 * underlined / total:5.1f}%   (the warrant)")
    print()
    print(f"  card nodes         : {len(all_cards)}")
    print(f"  evidence cards     : {len(cards)}"
          f"   ({len(all_cards) - len(cards)} analytics, no citation)")
    # median is the middle value once sorted. It is used here instead of the average
    # because a handful of very long cards would drag an average upward and misdescribe
    # what a typical card looks like - which is the thing the page is actually claiming.
    print(f"  tag length, words  : median {st.median(tags):.0f}  mean {st.mean(tags):.1f}"
          f"  range {min(tags)}-{max(tags)}")
    print(f"  card body, words   : median {st.median(body):.0f}  mean {st.mean(body):.0f}"
          f"  range {min(body)}-{max(body)}")
    # sum() over a list of True/False counts the Trues, because Python treats True as 1.
    print(f"  cards over 1,000 w : {sum(b > 1000 for b in body)}/{len(cards)}"
          f" = {100 * sum(b > 1000 for b in body) / len(cards):.0f}%")
    print()
    print("  evidence cards by section:")
    for name, group in sections(top).items():
        if group:                          # skip headings that hold no evidence cards
            words = sum(card_body_words(c) for c in group)
            print(f"      {len(group):3d} cards  {words:>6,} words   {name[:52]}")
    print()


def main():
    """Read filenames off the command line and report on each."""
    # sys.argv is everything typed at the prompt; [0] is the script's own name, so [1:]
    # is the list of files the user asked for.
    paths = sys.argv[1:]
    if not paths:                # nothing specified, so explain the script and stop
        print(__doc__)           # __doc__ is the long triple-quoted text at the top
        sys.exit(1)              # exit code 1 conventionally means "did not do the job"
    for path in paths:           # allows several files in one command
        report(path)


# Only run main() when this file is executed directly, not when another script imports it
# to borrow a function. Standard Python boilerplate.
if __name__ == '__main__':
    main()
