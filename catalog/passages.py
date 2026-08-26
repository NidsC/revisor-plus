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
from django.utils.html import escape
from django.utils.safestring import mark_safe

# Where the lines break lives in elevenplus_data/passage_lines.py, not here.
# validate_questions.py has to wrap passages exactly as this module does in
# order to check a `line_ref` against the passage it points at, and it is
# stdlib-only — it runs for a contributor with no Django and no pip install.
# One module both can import is the only way the two cannot drift apart.
from elevenplus_data.passage_lines import (  # noqa: F401  (re-exported)
    NUMBER_EVERY, PASSAGE_LINE_WIDTH, passage_lines,
)


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
