"""
Question figures, generated server-side from numeric parameters.

The papers we import specify their diagrams rather than shipping them: a question
carries `"svg": "l_shape"` plus `"dimensions": {...}`, or a `"table": {...}`, and
a non-verbal question carries a grid of shape specs. So the figure is fully
determined by the data, and we can draw it.

NOTHING HERE STORES OR ECHOES MARKUP. The database keeps only
`{"kind": ..., "data": {...}}` and this package turns that into SVG or a table at
render time, coercing or rejecting every value it interpolates. That is
deliberate: storing generated markup in a JSONField and printing it with `|safe`
would turn the admin question editor into an XSS hole, and stashing generated
files under static/ would need them written before `collectstatic` runs in
build.sh.

It is also why an authored pack declares a figure as *data* rather than pasting
SVG. The vocabulary in `glyphs.py` is closed, so a pack can only ask for pictures
this build can actually draw — checked by `validate_questions.py` at author time.

**This package does not import Django.** The Django-facing half is
`catalog/templatetags/catalog_extras.py`, which is where `mark_safe` is applied
and therefore where the trust boundary sits. Everything here is plain stdlib
Python so that the contributor preview tool can import the *same* drawing code
instead of reimplementing it in JavaScript. That is not tidiness: the preview
already carried one reimplementation that drifted from the app, and it spent
weeks showing authors passage line numbers the live site disagreed with.

    render_figure(figure)          -> markup for a question's own figure
    render_option_figure(option)   -> markup for one answer option's panel
    SUPPORTED                      -> the kinds this build can draw
"""
from . import mat, nvr
from .layout import CELL, MAX_INTRINSIC
from .nvr import intrinsic_width

# Kinds that draw an SVG. Wrapped in a scroll container by `render_figure`,
# because a figure is never scaled down to fit — see `box.svg`.
_SVG = {}
_SVG.update(mat.SVG_KINDS)
_SVG.update(nvr.KINDS)

# Kinds that are already HTML and lay themselves out.
_HTML = dict(mat.HTML_KINDS)

# Figure kinds this build can actually draw. `import_paper` warns on anything a
# paper asks for that is not in here, rather than silently dropping the diagram
# and leaving a question that cannot be answered; `validate_questions.py` makes
# the same check against a pack before it is merged.
SUPPORTED = set(_SVG) | set(_HTML)

# The kinds that belong to an answer option rather than to a question stem.
OPTION_KINDS = {"nvr_panel", "nvr_net"}


def _parts(figure):
    if not isinstance(figure, dict):
        return None, {}
    data = figure.get("data")
    return figure.get("kind"), data if isinstance(data, dict) else {}


def render_figure(figure):
    """figure -> markup. `figure` is {"kind": str, "data": {...}} or None.

    An SVG comes back inside a horizontal scroll container. A figure wider than
    the card scrolls; it is never scaled to fit, because scaling to fit is what
    made two questions in the same paper draw the same square at two different
    sizes and their labels at 13px and 7.5px.
    """
    kind, data = _parts(figure)
    if kind in _SVG:
        markup = _SVG[kind](data)
        return f'<div class="figure-scroll">{markup}</div>' if markup else ""
    if kind in _HTML:
        return _HTML[kind](data)
    return ""


def render_option_figure(option_figure):
    """One answer option's panel, unwrapped.

    Bare because the option tile around it is already an HTML control that owns
    its own spacing, letter and radio input — see the `.nvr-option` block in
    templates/base.html. The letter is HTML precisely so that it cannot scale
    with the drawing the way an in-figure `<text>` label did.
    """
    kind, data = _parts(option_figure)
    if kind in _SVG:
        return _SVG[kind](data)
    return ""


__all__ = ["render_figure", "render_option_figure", "SUPPORTED", "OPTION_KINDS",
           "intrinsic_width", "CELL", "MAX_INTRINSIC"]
