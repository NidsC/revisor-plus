from django import template

from catalog.figures import render_figure

register = template.Library()


@register.simple_tag
def question_figure(question):
    """Render a question's figure (its own, or its parent's shared one).

    Markup is generated at render time from the stored numeric parameters — see
    catalog/figures.py for why nothing draws from stored markup.
    """
    if question is None:
        return ""
    return render_figure(question.context_figure)
