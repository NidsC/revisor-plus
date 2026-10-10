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
    """The passage as an ordered list, one item per numbered line, with a gutter
    number beside every Nth."""
    lines = passage_lines(text, width=width)
    if not lines:
        return ""
    rows = []
    gap_before = False
    for number, line in lines:
        if number is None:
            # A paragraph gap is a class on the next item, never a list item, so
            # item N is always line N. Consecutive gaps still set it once.
            gap_before = True
            continue
        label = str(number) if number % every == 0 else ""
        cls = "passage-row passage-row--gap" if gap_before else "passage-row"
        gap_before = False
        rows.append(
            f'<li class="{cls}">'
            f'<span class="passage-num" aria-hidden="true">{escape(label)}</span>'
            f'<span class="passage-line">{escape(line)}</span>'
            f'</li>'
        )
    # role="list": WebKit/VoiceOver drops list semantics from a list-style:none list.
    return mark_safe(f'<ol class="passage-numbered" role="list">{"".join(rows)}</ol>')


def format_line_ref(line_ref):
    """A question's line reference, as a short label. "" when there is none."""
    ref = (line_ref or "").strip()
    if not ref:
        return ""
    return f"lines {ref}" if "-" in ref else f"line {ref}"
