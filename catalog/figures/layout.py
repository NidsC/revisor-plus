"""
Panels and grids — the only things that decide how big an NVR figure is.

One constant, `CELL`, sizes every panel in every kind. That is the invariant the
old module lacked: `_nvr_frame` used a 74-unit panel and `_nvr_net` a 20-unit
grid square, each with its own `max-width`, so the same drawing rendered at a
different physical size depending on which kind it belonged to and how many
panels were beside it. Measured before this change, a five-net figure rendered
at 0.88 CSS pixels per user unit while a four-panel series rendered at 1.00.

Nothing in this module or `nvr.py` writes a pixel size. `box.svg()` does that,
once, from the measurement.
"""
from .box import Box, row, stack
from .glyphs import STROKE_COLOUR, cell_markup

CELL = 64            # every panel, every grid square, every option tile
GAP = 12             # between panels in a row
RULE = 1.5           # panel outline

# Widest a stem figure may be before it scrolls on the narrowest card we
# support (a 340px phone viewport, less the card and container padding). Not a
# clamp — nothing is ever scaled to meet it. It is the threshold the validator
# warns an author about, so "this will scroll on a phone" is something they are
# told at author time rather than something a pupil discovers.
MAX_INTRINSIC = 292


def panel(cell_spec, blank=False):
    """One bordered panel. `blank` is the cell the pupil has to supply.

    A blank is drawn as a dashed empty panel, which is what the papers print and
    which — unlike the question mark the old renderer drew — needs no text
    inside the SVG. See `nvr.py` for why that matters.
    """
    inset = RULE / 2
    dash = ' stroke-dasharray="6 4"' if blank else ""
    outline = (f'<rect x="{inset}" y="{inset}" width="{CELL - RULE}" '
               f'height="{CELL - RULE}" rx="6" fill="none" '
               f'stroke="{STROKE_COLOUR}" stroke-width="{RULE}"{dash}/>')
    body = "" if blank else cell_markup(cell_spec, CELL)
    return Box(outline + body, CELL, CELL)


def separator():
    """The break between the two halves of an analogy ("A is to B as C is to ?").

    Two dots, the printed convention, rather than the characters "::" — a glyph
    is a glyph at any size, and text inside the figure is what this package is
    built to avoid.
    """
    x = GAP / 2
    dots = "".join(f'<circle cx="{x}" cy="{CELL / 2 + dy}" r="2.2" '
                   f'fill="{STROKE_COLOUR}"/>' for dy in (-7, 7))
    return Box(dots, GAP, CELL)


def panel_row(cell_specs, blank_index=None, separator_after=None):
    """A row of panels, measured."""
    boxes = []
    for index, spec in enumerate(cell_specs):
        boxes.append(panel(spec, blank=(index == blank_index)))
        if separator_after is not None and index == separator_after:
            boxes.append(separator())
    return row(boxes, gap=GAP)


def panel_grid(cell_specs, cols, blank_index=None):
    """`cell_specs` laid out `cols` wide, in reading order."""
    rows = []
    for start in range(0, len(cell_specs), cols):
        chunk = cell_specs[start:start + cols]
        blank = None
        if blank_index is not None and start <= blank_index < start + cols:
            blank = blank_index - start
        rows.append(panel_row(chunk, blank_index=blank))
    return stack(rows, gap=GAP, align="start")


def net_box(squares):
    """A cube net: unit squares on a grid, given as (row, column) pairs.

    Drawn on the same `CELL` as everything else — a net square is a quarter of a
    panel — so a net and a shape panel in the same paper are visibly the same
    scale. The old renderer used a 20-unit square here against a 74-unit panel
    elsewhere, with no relationship between them.
    """
    pairs = [(int(r), int(c)) for r, c in squares
             if isinstance(r, (int, float)) and isinstance(c, (int, float))]
    if not pairs:
        return Box("", CELL, CELL)
    side = CELL / 2
    min_r = min(r for r, _ in pairs)
    min_c = min(c for _, c in pairs)
    rows = max(r for r, _ in pairs) - min_r + 1
    cols = max(c for _, c in pairs) - min_c + 1
    inset = RULE / 2
    parts = []
    for r, c in pairs:
        x, y = (c - min_c) * side + inset, (r - min_r) * side + inset
        parts.append(f'<rect x="{x}" y="{y}" width="{side - RULE}" '
                     f'height="{side - RULE}" fill="#DBEAFE" '
                     f'stroke="{STROKE_COLOUR}" stroke-width="{RULE}"/>')
    return Box("".join(parts), cols * side, rows * side)
