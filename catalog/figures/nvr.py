"""
The non-verbal reasoning figure kinds.

Three kinds cover the section, because nearly every GL non-verbal stem is a row
or grid of panels and nearly every answer is one panel:

    nvr_grid    a grid of cells, optionally with one blank — series, matrices,
                analogies, odd-one-out and code questions are all this shape
    nvr_panel   a single cell, which is what an answer option is
    nvr_net     a cube net, the one shape that is not a panel of glyphs

**No text is drawn inside any of them.** Letters, captions and instructions are
HTML, rendered around the figure by `templates/practice/question.html`. Two
things follow. Chrome text can no longer shrink with the drawing — before this,
an option letter rendered at 13.0px beside a four-panel figure and 7.5px beside a
five-net one, while the radio buttons it labelled stayed the same size in both.
And the clipping bug class disappears: the old `_nvr_frame` carried
`height = 2 * PANEL + 90` with a comment recording that `+74` had cut the
descenders off the A-D labels. With no glyphs in the box there is nothing to clip.

Answer panels are no longer drawn inside the stem figure either. Each option
carries its own `nvr_panel` figure on `AnswerOption.figure`, so the picture a
pupil clicks and the row that marks their answer are the same object. The old
arrangement kept them in step by list position, which is why
`generators/nonverbal.py` needed `_lettered()` to build both halves at once.
"""
from .box import Box, svg
from .layout import CELL, MAX_INTRINSIC, net_box, panel, panel_grid

DEFAULT_ALT = "Non-verbal reasoning figure"


def _alt(data, fallback):
    alt = data.get("alt")
    return alt if isinstance(alt, str) and alt.strip() else fallback


def nvr_grid(data):
    """A grid of cells, optionally with one blank and one analogy separator."""
    cells = data.get("cells")
    if not isinstance(cells, list) or not cells:
        return ""
    cols = data.get("cols") or len(cells)
    try:
        cols = max(1, int(cols))
    except (TypeError, ValueError):
        cols = len(cells)
    blank = data.get("blank")
    blank = blank if isinstance(blank, int) and 0 <= blank < len(cells) else None
    separator_after = data.get("separator_after")

    if cols >= len(cells) and isinstance(separator_after, int):
        from .layout import panel_row
        box = panel_row(cells, blank_index=blank, separator_after=separator_after)
    else:
        box = panel_grid(cells, cols, blank_index=blank)
    return svg(box, _alt(data, f"A grid of {len(cells)} panels"), scalable=True, paper=False)


def nvr_panel(data):
    """A single cell. The shape of an answer option."""
    cell = data.get("cell")
    if not isinstance(cell, dict):
        return ""
    return svg(panel(cell), _alt(data, "One answer panel"), scalable=True, paper=False)


def nvr_net(data):
    """A cube net drawn as squares on a grid."""
    squares = data.get("squares")
    if not isinstance(squares, list) or not squares:
        return ""
    try:
        box = net_box(squares)
    except (TypeError, ValueError):
        return ""
    return svg(box, _alt(data, "A net of squares"), scalable=True, paper=False)


KINDS = {"nvr_grid": nvr_grid, "nvr_panel": nvr_panel, "nvr_net": nvr_net}


def intrinsic_width(kind, data):
    """The width this figure will render at, in CSS pixels.

    Exposed so `validate_questions.py` can warn an author that their figure is
    wider than a phone card before it is merged, rather than the author finding
    out from a pupil. Returns 0 for anything that does not draw.
    """
    markup = KINDS.get(kind, lambda _: "")(data if isinstance(data, dict) else {})
    if not markup:
        return 0
    start = markup.find('width="') + 7
    return int(markup[start:markup.find('"', start)])


__all__ = ["KINDS", "intrinsic_width", "CELL", "MAX_INTRINSIC", "Box"]
