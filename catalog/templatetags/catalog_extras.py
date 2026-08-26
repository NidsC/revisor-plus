from django import template
from django.utils.safestring import mark_safe

from catalog.figures import render_figure, render_option_figure
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
    catalog/figures/__init__.py for why nothing draws from stored markup.

    This module is the trust boundary. `catalog.figures` is plain stdlib Python
    with no Django import, so that the contributor preview tool can share the
    one implementation of the drawing; `mark_safe` is applied here, at the point
    the markup actually reaches a template, rather than inside a package that
    also runs outside Django.
    """
    if question is None:
        return ""
    return mark_safe(render_figure(question.context_figure))


@register.simple_tag
def option_figure(option):
    """Render one answer option's panel, for a question answered with pictures."""
    if option is None:
        return ""
    return mark_safe(render_option_figure(getattr(option, "figure", None)))
