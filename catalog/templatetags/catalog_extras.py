from django import template

from catalog.figures import render_figure
from catalog.passages import format_line_ref, render_passage

register = template.Library()


@register.simple_tag
def question_passage(question):
    """Render a question's passage (its own, or its parent's shared one).

    Numbered, because comprehension questions cite lines. See catalog/passages.py
    for why the line breaks are fixed server-side.
    """
    if question is None:
        return ""
    return render_passage(question.context_passage)


@register.filter
def line_ref_label(question):
    """"line 7" / "lines 20-21" for a question that cites the passage."""
    if question is None:
        return ""
    return format_line_ref(getattr(question, "line_ref", ""))


@register.simple_tag
def question_figure(question):
    """Render a question's figure (its own, or its parent's shared one).

    Markup is generated at render time from the stored numeric parameters — see
    catalog/figures.py for why nothing draws from stored markup.
    """
    if question is None:
        return ""
    return render_figure(question.context_figure)
