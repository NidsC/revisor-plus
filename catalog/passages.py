"""
Reading passages, rendered with line numbers.

Comprehension questions cite the passage by line — "another way of saying
'lulled' (line 1)" — so a passage has to be numbered, and the number has to mean
the same thing to the author writing `line_ref` and to the pupil reading it.

Printed papers get that for free: the typesetting fixes where lines break. HTML
does not, because the text reflows with the window. So lines are fixed here
instead, by wrapping the passage at PASSAGE_LINE_WIDTH characters before it ever
reaches the browser. The width is part of the authoring contract rather than a
rendering detail — change it and every `line_ref` already written shifts.

Like catalog/figures.py, this stores no markup and escapes everything it
interpolates.
"""
import textwrap

from django.utils.html import escape
from django.utils.safestring import mark_safe

# Characters per line, and part of the authoring contract rather than a styling
# choice — documented in elevenplus_data/CLAUDE.md because authors count against
# it. 100 is not arbitrary: the one line_ref written so far ("line 7", pointing
# at "like herds of grey horses" in The Lighthouse Keeper's Daughter) lands on
# line 7 at widths 100 and 105, and on line 8 or later at anything narrower. So
# this is the measure that pack was written against.
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


def render_passage(text, width=PASSAGE_LINE_WIDTH, every=NUMBER_EVERY):
    """The passage as an HTML block with a number beside every Nth line."""
    lines = passage_lines(text, width=width)
    if not lines:
        return ""
    rows = []
    for number, line in lines:
        if number is None:
            rows.append('<span class="passage-gap" aria-hidden="true"></span>')
            continue
        label = str(number) if number % every == 0 else ""
        rows.append(
            f'<span class="passage-num" aria-hidden="true">{escape(label)}</span>'
            f'<span class="passage-line">{escape(line)}</span>'
        )
    return mark_safe(f'<div class="passage-numbered">{"".join(rows)}</div>')


def format_line_ref(line_ref):
    """A question's line reference, as a short label. "" when there is none."""
    ref = (line_ref or "").strip()
    if not ref:
        return ""
    return f"lines {ref}" if "-" in ref else f"line {ref}"
