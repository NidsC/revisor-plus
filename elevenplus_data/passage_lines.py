"""
Where a passage's lines break, and therefore what `line_ref` means.

Stdlib only, and deliberately so. This is imported by BOTH
`catalog/passages.py`, which renders passages for pupils, and
`elevenplus_data/validate_questions.py`, which checks packs before they merge
and must run for a contributor with nothing but Python 3 — no Django, no pip
install. Anything that imports Django cannot live here.

It exists as its own module because those two have to agree exactly. A
comprehension question cites the passage by line ("another way of saying
'lulled' (line 1)"), so the number the author counts to and the number the
pupil reads have to be the same number. Printed papers get that for free —
typesetting fixes where lines break. HTML does not, because text reflows with
the window, so the break points are fixed here instead and the width is part of
the authoring contract rather than a styling choice.

If the validator wrapped passages even slightly differently from the renderer,
it would approve a `line_ref` that points at the wrong line, which is worse
than not checking at all: the author gets told they are right.
"""
import textwrap

# Characters per line, and part of the authoring contract rather than a styling
# choice — documented in elevenplus_data/CLAUDE.md because authors count against
# it. 100 is not arbitrary: the one line_ref written so far ("line 7", pointing
# at "like herds of grey horses" in The Lighthouse Keeper's Daughter) lands on
# line 7 at widths 100 and 105, and on line 8 or later at anything narrower. So
# this is the measure that pack was written against.
#
# Change it and every line_ref already written shifts.
PASSAGE_LINE_WIDTH = 100

# Number every Nth line, as printed papers do, rather than every line.
NUMBER_EVERY = 5


def passage_lines(text, width=PASSAGE_LINE_WIDTH):
    """Split a passage into numbered lines.

    Returns a list of (line_number, text) pairs. Paragraphs are separated by a
    blank line in the source and keep their break; the blank line itself is
    returned as (None, "") so the caller can render the gap without consuming a
    line number — a number that moved when a paragraph was added would
    invalidate every reference after it.
    """
    if not text:
        return []
    out = []
    n = 0
    paragraphs = str(text).replace("\r\n", "\n").split("\n\n")
    for i, para in enumerate(paragraphs):
        if i:
            out.append((None, ""))
        para = " ".join(para.split())
        if not para:
            continue
        for line in textwrap.wrap(para, width=width) or [""]:
            n += 1
            out.append((n, line))
    return out


def last_line_number(text, width=PASSAGE_LINE_WIDTH):
    """The highest line number in a passage — 0 when there is no text.

    What a `line_ref` has to fit inside. Blank paragraph separators carry no
    number, so this is not simply len(passage_lines(...)).
    """
    numbers = [n for n, _ in passage_lines(text, width=width) if n is not None]
    return numbers[-1] if numbers else 0
