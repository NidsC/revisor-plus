"""
The non-verbal reasoning shape vocabulary.

Everything an NVR figure can contain is enumerated in this module, and a spec
naming anything not enumerated here is an error rather than a default. That is
the whole point of it being closed: `validate_questions.py` imports these sets,
so an author who writes `"shape": "octogon"` is told at author time, instead of
the app quietly drawing a square and the question becoming unanswerable on the
live site.

Being closed is affordable because real GL non-verbal papers use a small,
repetitive visual vocabulary — a shape, a size, a fill, a rotation, a count, and
where in the cell it sits. The interesting part of an NVR question is the *rule*
relating the cells, not the drawing.

No ids, no `<defs>`, no `<pattern>`, no `<clipPath>`. Shading is computed here as
real geometry (`_clip_halfplane`, `_hatch_lines`, `_dot_centres`) rather than
referenced through a document id. Ids would have to be unique across every
figure on a page — and the contributor preview puts a whole pack on one page —
so an id scheme is a collision waiting to happen. Geometry has no such problem.
"""
import math

from .box import Box

# --------------------------------------------------------------------- tokens
#
# Each of these is a closed set. Adding to one is a deliberate extension of the
# contract: the authoring docs are written from these names, and the validator
# rejects anything outside them.

# `tiny` exists for marks that get counted. A row of `small` circles does not fit
# a panel past two of them, so it has to compress — and a counting rule whose
# marks shrink as the count rises reads as a size rule as well, which is not what
# the question asks. At `tiny`, a row of five fits at full size and no
# compression happens.
SIZES = {"tiny": 0.15, "small": 0.34, "medium": 0.52, "large": 0.72}

FILLS = {"none", "solid", "half", "quarter", "hatch", "cross_hatch", "dots"}

STROKES = {"solid", "dashed", "bold"}

# Reflection. The `Rotation & Reflection` subtopic is named for both, but nothing
# could draw the second half of it until this existed — every question the
# generator made was a rotation. It is also what makes a usable distractor for a
# half turn: `base - 180` and `base + 180` are the same picture, so a
# rotate-the-wrong-way distractor for a 180 degree turn is the correct answer
# with a different letter on it.
#
# Only meaningful on a shape that is not mirror-symmetric. A regular polygon with
# a corner marker is NOT: reflecting it always gives the same picture as some
# rotation of it, so a reflection distractor there is indistinguishable from a
# rotation one. Use an asymmetric outline, or a `half`/`quarter` fill, which is
# what makes a symmetric shape chiral.
FLIPS = {"horizontal", "vertical"}

# How many copies of a glyph are drawn, spread evenly across its position band.
# Counting is one of the handful of rules real non-verbal papers are built on
# ("each panel gains a dot"), and it needs to hold more than the three the first
# version of this module could place.
#
# Five, because five `tiny` glyphs are what fits a panel at their declared size.
# Past that the row compresses and the marks shrink, and a pupil counting six
# marks against five is being asked to count things that are also changing size.
MAX_REPEAT = 5


def fits_without_compressing(size_name, repeat):
    """Whether a row of `repeat` glyphs fits at its declared size.

    Exposed for `validate_questions.py`, so an author is warned that their
    counting row will be squashed rather than finding out from the page.
    """
    fraction = SIZES.get(size_name, SIZES["medium"])
    return repeat * (fraction * 1.12) <= 0.88

# Where in its cell a glyph sits. A cell may hold several glyphs at different
# positions — "a small circle in the top-right corner" is a rule NVR papers use
# constantly, and it needs to mean the same corner in every question.
POSITIONS = {
    "center": (0.0, 0.0),
    "top": (0.0, -1.0), "bottom": (0.0, 1.0),
    "left": (-1.0, 0.0), "right": (1.0, 0.0),
    "top_left": (-1.0, -1.0), "top_right": (1.0, -1.0),
    "bottom_left": (-1.0, 1.0), "bottom_right": (1.0, 1.0),
}

# Rotation is quantised. A pupil cannot distinguish 20° from 25° on a 46px
# glyph, so allowing arbitrary angles only creates questions whose answer is not
# readable — and distractors that differ from the key by an invisible amount.
ROTATION_STEP = 15

STROKE_COLOUR = "#334155"
FILL_COLOUR = "#DBEAFE"
PAPER = "#FFFFFF"


# ------------------------------------------------------------------- outlines
#
# Every shape is a polygon in a unit space whose bounding box is 2x2, centred on
# the origin. One representation for everything — including the circle, as a
# 48-gon — means shading, rotation and scaling have a single code path each,
# rather than one per shape. At the sizes these render (22-46px) a 48-gon and a
# circle are the same picture.

def _regular(sides, phase=-90.0, radius=1.0):
    return [(radius * math.cos(math.radians(phase + i * 360.0 / sides)),
             radius * math.sin(math.radians(phase + i * 360.0 / sides)))
            for i in range(sides)]


def _star(points=5, inner=0.45):
    out = []
    for i in range(points * 2):
        r = 1.0 if i % 2 == 0 else inner
        a = math.radians(-90 + i * 180.0 / points)
        out.append((r * math.cos(a), r * math.sin(a)))
    return out


def _cross(arm=0.36):
    a = arm
    return [(-a, -1), (a, -1), (a, -a), (1, -a), (1, a), (a, a),
            (a, 1), (-a, 1), (-a, a), (-1, a), (-1, -a), (-a, -a)]


def _arrow():
    return [(0, -1), (0.85, -0.05), (0.34, -0.05), (0.34, 1),
            (-0.34, 1), (-0.34, -0.05), (-0.85, -0.05)]


def _l_shape():
    return [(-1, -1), (0.05, -1), (0.05, 0.1), (1, 0.1), (1, 1), (-1, 1)]


# Outlines with no mirror symmetry. These are what a reflection question needs:
# reflecting a shape that IS mirror-symmetric gives back a picture some rotation
# of it also gives, so on a symmetric outline "reflected" and "turned" are not
# two different answers. `trapezium`, `arrow` and `semicircle` all look
# asymmetric and are not — each is symmetric about its vertical axis.
def _right_trapezium():
    return [(-1, -1), (0.3, -1), (1, 1), (-1, 1)]


def _flag():
    return [(-0.72, -1), (0.95, -0.62), (-0.72, -0.24), (-0.72, 1), (-0.95, 1),
            (-0.95, -1)]


def _semicircle():
    # Step 6, not 8: 180 degrees divides by 6, so the arc ends exactly on 360 and
    # the outline closes along the flat edge. At step 8 the last point was 356
    # and the shape closed on a slant, giving a dome with a tilted base.
    points = [(math.cos(math.radians(a)), math.sin(math.radians(a)))
              for a in range(180, 361, 6)]
    return [(x, y * 2 + 1) for x, y in points]


SHAPES = {
    "circle": _regular(48, -90),
    "ellipse": [(x, y * 0.62) for x, y in _regular(48, -90)],
    "square": [(-1, -1), (1, -1), (1, 1), (-1, 1)],
    "rectangle": [(-1, -0.55), (1, -0.55), (1, 0.55), (-1, 0.55)],
    "triangle": [(0, -1), (1, 0.82), (-1, 0.82)],
    "right_triangle": [(-1, -1), (1, 1), (-1, 1)],
    "diamond": [(0, -1), (1, 0), (0, 1), (-1, 0)],
    "trapezium": [(-0.55, -1), (0.55, -1), (1, 1), (-1, 1)],
    "pentagon": _regular(5),
    "hexagon": _regular(6),
    "octagon": _regular(8, -112.5),
    "star": _star(5),
    "star6": _star(6, 0.58),
    "cross": _cross(),
    "arrow": _arrow(),
    "l_shape": _l_shape(),
    "semicircle": _semicircle(),
    "right_trapezium": _right_trapezium(),
    "flag": _flag(),
}

# The subset with no mirror symmetry, for questions that turn on telling a
# reflection from a rotation. Named here rather than in the generator so the
# authoring contract and the validator can quote one list.
CHIRAL = ("right_triangle", "l_shape", "right_trapezium", "flag")


# ------------------------------------------------------------------- geometry

def _transform(points, scale, rotation, cx, cy, flip=None):
    # Flip before rotating, so "reflected, then turned 90 degrees" means what it
    # says. Order matters: the two do not commute, and a distractor built as one
    # order and described as the other is a wrong answer that is arguably right.
    if flip == "horizontal":
        points = [(-x, y) for x, y in points]
    elif flip == "vertical":
        points = [(x, -y) for x, y in points]
    rad = math.radians(rotation)
    cos, sin = math.cos(rad), math.sin(rad)
    return [(cx + (x * cos - y * sin) * scale, cy + (x * sin + y * cos) * scale)
            for x, y in points]


def _clip_halfplane(points, keep):
    """Sutherland-Hodgman against one half-plane. `keep(point)` says which side
    survives, and edges crossing the boundary are cut at the crossing.

    Used for `half` and `quarter` shading: the shaded region is the shape itself
    clipped to the left half (and then the top half), so the shading follows the
    outline exactly. A circle shaded `half` gives a true semicircle, not a
    rectangle sitting on top of a circle.
    """
    if not points:
        return []
    out = []
    for i, current in enumerate(points):
        previous = points[i - 1]
        cur_in, prev_in = keep(current), keep(previous)
        if cur_in != prev_in:
            out.append(_crossing(previous, current, keep))
        if cur_in:
            out.append(current)
    return out


def _crossing(a, b, keep, depth=22):
    """Where the segment a-b crosses the boundary, by bisection.

    Bisection rather than solving the line equation because it works for any
    `keep` predicate — a vertical cut, a horizontal one, or both — without this
    function needing to know which. 22 halvings resolves a 64-unit cell to well
    under a thousandth of a unit.
    """
    inside, outside = (a, b) if keep(a) else (b, a)
    for _ in range(depth):
        mid = ((inside[0] + outside[0]) / 2, (inside[1] + outside[1]) / 2)
        if keep(mid):
            inside = mid
        else:
            outside = mid
    return inside


def _edges(points):
    return [(points[i - 1], points[i]) for i in range(len(points))]


def _scanline(points, x0, y0, dx, dy):
    """Where the infinite line through (x0,y0) with direction (dx,dy) enters and
    leaves the polygon, as parameter values along that direction, sorted.

    Even-odd pairing of the sorted crossings gives the inside segments, which is
    correct for concave shapes too — a hatched star has five separate spans on
    some lines, and pairing sorted crossings finds all of them.
    """
    hits = []
    for (ax, ay), (bx, by) in _edges(points):
        # Cross product of the edge with the ray direction; zero means parallel.
        denominator = (bx - ax) * dy - (by - ay) * dx
        if abs(denominator) < 1e-12:
            continue
        t = ((x0 - ax) * dy - (y0 - ay) * dx) / denominator
        if 0 <= t < 1:
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            hits.append((px - x0) * dx + (py - y0) * dy)
    hits.sort()
    return hits


def _hatch_lines(points, spacing, angle, cx, cy, extent):
    """Parallel line segments filling the polygon, at `angle` degrees."""
    rad = math.radians(angle)
    dx, dy = math.cos(rad), math.sin(rad)
    nx, ny = -dy, dx           # unit normal, the direction we step along
    segments = []
    steps = int(extent / spacing) + 1
    for step in range(-steps, steps + 1):
        ox, oy = cx + nx * step * spacing, cy + ny * step * spacing
        hits = _scanline(points, ox, oy, dx, dy)
        for i in range(0, len(hits) - 1, 2):
            start, end = hits[i], hits[i + 1]
            if end - start < 0.6:      # skip slivers at the tips of a star
                continue
            segments.append(((ox + dx * start, oy + dy * start),
                             (ox + dx * end, oy + dy * end)))
    return segments


def _contains(points, x, y):
    """Even-odd point-in-polygon, for placing dots inside any outline."""
    inside = False
    for (ax, ay), (bx, by) in _edges(points):
        if (ay > y) != (by > y):
            crossing = ax + (y - ay) / (by - ay) * (bx - ax)
            if crossing > x:
                inside = not inside
    return inside


def _dot_centres(points, spacing, cx, cy, extent):
    steps = int(extent / spacing) + 1
    return [(cx + i * spacing, cy + j * spacing)
            for i in range(-steps, steps + 1)
            for j in range(-steps, steps + 1)
            if _contains(points, cx + i * spacing, cy + j * spacing)]


# -------------------------------------------------------------------- drawing

def _path(points):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def _stroke_attrs(stroke):
    width = 2.6 if stroke == "bold" else 1.8
    dash = ' stroke-dasharray="5 3.5"' if stroke == "dashed" else ""
    return f'stroke="{STROKE_COLOUR}" stroke-width="{width}"{dash}'


def _shading(points, fill, cx, cy, extent):
    """The marks inside an outline, as geometry. Never a pattern fill."""
    if fill in ("none", "solid"):
        return ""
    if fill == "half":
        clipped = _clip_halfplane(points, lambda p: p[0] <= cx)
        return (f'<polygon points="{_path(clipped)}" fill="{FILL_COLOUR}"/>'
                if len(clipped) > 2 else "")
    if fill == "quarter":
        clipped = _clip_halfplane(points, lambda p: p[0] <= cx)
        clipped = _clip_halfplane(clipped, lambda p: p[1] <= cy)
        return (f'<polygon points="{_path(clipped)}" fill="{FILL_COLOUR}"/>'
                if len(clipped) > 2 else "")
    if fill in ("hatch", "cross_hatch"):
        angles = (45,) if fill == "hatch" else (45, -45)
        out = []
        for angle in angles:
            for (ax, ay), (bx, by) in _hatch_lines(points, 4.5, angle, cx, cy, extent):
                out.append(f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" '
                           f'y2="{by:.2f}" stroke="{STROKE_COLOUR}" stroke-width="1"/>')
        return "".join(out)
    if fill == "dots":
        return "".join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.5" '
                       f'fill="{STROKE_COLOUR}"/>'
                       for x, y in _dot_centres(points, 6.0, cx, cy, extent))
    return ""


def glyph_markup(spec, cell, cx, cy):
    """One glyph, drawn centred on (cx, cy) within a cell of edge `cell`.

    Returns markup only — the caller owns the extent, because a glyph is always
    drawn inside a panel whose size is fixed by the layout, never the other way
    round. That is what keeps a hexagon in a series exactly the same size as the
    hexagon in the option tile the pupil compares it against.
    """
    shape = spec.get("shape", "square")
    outline = SHAPES.get(shape)
    if outline is None:
        return ""
    size = SIZES.get(spec.get("size", "medium"), SIZES["medium"])
    fill = spec.get("fill", "none")
    fill = fill if fill in FILLS else "none"
    stroke = spec.get("stroke", "solid")
    stroke = stroke if stroke in STROKES else "solid"
    rotation = spec.get("rot", 0) or 0

    flip = spec.get("flip")
    flip = flip if flip in FLIPS else None
    try:
        repeat = max(1, min(MAX_REPEAT, int(spec.get("repeat", 1) or 1)))
    except (TypeError, ValueError):
        repeat = 1

    offset_x, offset_y = POSITIONS.get(spec.get("at", "center"), (0.0, 0.0))
    # Half the room left over once the glyph is placed, so a corner glyph sits
    # in the corner and still keeps clear of the panel's own outline.
    room = (cell * (1 - size) / 2) * 0.82
    base_x, base_y = cx + offset_x * room, cy + offset_y * room

    scale = size * cell / 2
    # Repeated glyphs sit in a row centred on the position the spec asked for.
    #
    # They keep the size they were given for as long as they fit, and shrink
    # only once the row would not. Sizing them by dividing the available width
    # by the count — the obvious implementation, and the first one here — makes
    # the glyph shrink as the count rises, so a panel of two draws visibly
    # bigger marks than a panel of four. In a series whose rule is "one more dot
    # each time", that reads as a second rule about size that nobody intended,
    # and the distractor built by breaking the real rule no longer looks wrong
    # in the way it should.
    #
    # They are never dropped, either: a `repeat` of 5 that drew 3 would make the
    # rule the question turns on invisible, and the question unanswerable.
    if repeat > 1:
        diameter = size * cell
        step = diameter * 1.12
        available = cell * 0.88
        if repeat * step > available:
            step = available / repeat
            scale = step * 0.44
        start = base_x - step * (repeat - 1) / 2
        centres = [(start + index * step, base_y) for index in range(repeat)]
    else:
        centres = [(base_x, base_y)]

    parts = []
    body_colour = FILL_COLOUR if fill == "solid" else PAPER
    for centre_x, centre_y in centres:
        points = _transform(outline, scale, rotation, centre_x, centre_y, flip)
        parts.append(f'<polygon points="{_path(points)}" fill="{body_colour}" '
                     f'{_stroke_attrs(stroke)}/>')
        parts.append(_shading(points, fill, centre_x, centre_y, scale * 1.45))
        # A rotation marker. A square looks identical every 90 degrees and a
        # circle at every angle, so a question about rotation is unanswerable
        # without one. Opt-in: `marker` is a rule the author states, not a
        # decoration. It reflects with the shape, or the reflection would be
        # invisible on a symmetric outline.
        if spec.get("marker"):
            marker_angle = -(rotation) if flip == "horizontal" else rotation
            if flip == "vertical":
                marker_angle = 180 - rotation
            angle = math.radians(marker_angle - 90)
            parts.append(
                f'<circle cx="{centre_x + scale * 0.58 * math.cos(angle):.2f}" '
                f'cy="{centre_y + scale * 0.58 * math.sin(angle):.2f}" r="2.6" '
                f'fill="{STROKE_COLOUR}"/>')
    return "".join(parts)


def cell_markup(cell_spec, cell):
    """A whole cell's contents: one glyph, or several at declared positions."""
    if not isinstance(cell_spec, dict):
        return ""
    items = cell_spec.get("items")
    if not isinstance(items, list):
        items = [cell_spec]
    half = cell / 2
    return "".join(glyph_markup(item, cell, half, half)
                   for item in items if isinstance(item, dict))


def cell_box(cell_spec, cell):
    return Box(cell_markup(cell_spec, cell), cell, cell)
