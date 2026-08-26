"""
Maths figures: diagrams generated from the numbers a paper gives.

Moved here unchanged in substance from the old single-module `catalog/figures.py`
and put on the package's size contract. The drawings are the same; what changed
is that they no longer each pick their own `max-width`. Measured before the
change, `l_shape` rendered at 1.14 CSS pixels per user unit — so its edge labels
came out at 14.8px while every other figure's came out at 13px, for no reason
other than that its `max-width` (420) and its viewBox (368) were written by hand
at different times.

Text *is* allowed in here, unlike in `nvr.py`. The distinction is what the text
is for: an edge measurement on an L-shape is part of the diagram and cannot live
anywhere else, whereas an option letter is chrome and belongs in HTML. What both
now share is that a 13-unit label renders at 13 pixels, always.
"""
from .box import Box, escape, svg

STROKE = "#334155"
FILL = "#DBEAFE"
LABEL = "#0F172A"


def _n(value, default=0.0):
    """Coerce to float. Anything non-numeric becomes the default, so a malformed
    figure spec produces a plain diagram rather than broken markup."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _txt(x, y, text, anchor="middle", size=13):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'font-size="{size}" fill="{LABEL}" '
            f'font-family="system-ui,sans-serif">{escape(str(text))}</text>')


def l_shape(data):
    """An L, drawn to the four given edge lengths.

    The other two edges are derived, which is also the bit the pupil has to work
    out: with top 18, bottom-left 11, left 10 and right 4, the inner edges are
    18-11=7 across and 10-4=6 down.
    """
    top = _n(data.get("top"), 10)
    left = _n(data.get("left"), 10)
    bottom_left = _n(data.get("bottom_left"), 6)
    right = _n(data.get("right"), 4)
    inner_h = top - bottom_left
    inner_v = left - right
    if top <= 0 or left <= 0:
        return ""

    scale = min(300 / top, 190 / left)
    width, height = top * scale, left * scale

    def px(ux, uy):
        return ux * scale, uy * scale

    corners = [(0, 0), (top, 0), (top, right), (bottom_left, right),
               (bottom_left, left), (0, left)]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in (px(a, b) for a, b in corners))

    parts = [f'<polygon points="{points}" fill="{FILL}" stroke="{STROKE}" '
             f'stroke-width="2"/>']

    def mid(a, b):
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    x, y = mid(px(0, 0), px(top, 0)); parts.append(_txt(x, y - 10, top))
    x, y = mid(px(top, 0), px(top, right)); parts.append(_txt(x + 16, y + 4, right))
    x, y = mid(px(bottom_left, right), px(top, right))
    parts.append(_txt(x, y - 8, inner_h))
    x, y = mid(px(bottom_left, right), px(bottom_left, left))
    parts.append(_txt(x + 16, y + 4, inner_v))
    x, y = mid(px(0, left), px(bottom_left, left))
    parts.append(_txt(x, y + 20, bottom_left))
    x, y = mid(px(0, 0), px(0, left)); parts.append(_txt(x - 16, y + 4, left))
    # Padding is what the labels sit in: they are drawn outside the polygon, so
    # the box is the shape plus room for them on every side.
    return svg(Box("".join(parts), width, height),
               "L-shaped figure with labelled edges", pad=34)


def angles_on_line(data):
    """Straight line AOB with a ray OC. Deliberately schematic — the papers say
    'not drawn to scale' and the actual angle is given in the question text, so
    drawing a specific value would risk contradicting the stem."""
    markup = (
        f'<line x1="30" y1="130" x2="330" y2="130" stroke="{STROKE}" stroke-width="2"/>'
        f'<line x1="180" y1="130" x2="285" y2="40" stroke="{STROKE}" stroke-width="2"/>'
        f'<circle cx="180" cy="130" r="4" fill="{STROKE}"/>'
        f'<path d="M 130 130 A 50 50 0 0 1 145 95" fill="none" stroke="{STROKE}"/>'
        f'<path d="M 232 130 A 52 52 0 0 0 218 96" fill="none" stroke="{STROKE}"/>'
        + _txt(24, 148, "A") + _txt(180, 150, "O") + _txt(336, 148, "B")
        + _txt(295, 34, "C") + _txt(120, 104, "AOC") + _txt(243, 112, "x")
    )
    return svg(Box(markup, 360, 170),
               "Straight line A O B with ray O C, angle x between OC and OB")


def venn(data):
    """Two overlapping sets. Counts live in the question text, not the diagram —
    the whole task is working out the overlap, so labelling it would answer it."""
    a = escape(str(data.get("left_label", "A")))
    b = escape(str(data.get("right_label", "B")))
    markup = (
        f'<rect x="8" y="8" width="364" height="194" fill="none" '
        f'stroke="{STROKE}" stroke-dasharray="4 3"/>'
        f'<circle cx="150" cy="105" r="72" fill="{FILL}" fill-opacity=".7" stroke="{STROKE}"/>'
        f'<circle cx="230" cy="105" r="72" fill="{FILL}" fill-opacity=".7" stroke="{STROKE}"/>'
        + _txt(108, 46, a) + _txt(272, 46, b)
    )
    return svg(Box(markup, 380, 210),
               "Two overlapping circles inside a rectangle")


def table(data):
    headers = data.get("headers") or []
    rows = data.get("rows") or []
    out = ['<div class="table-responsive"><table class="table table-sm table-bordered '
           'align-middle mb-0" style="width:auto">']
    if headers:
        out.append("<thead><tr>")
        out += [f"<th>{escape('' if h is None else str(h))}</th>" for h in headers]
        out.append("</tr></thead>")
    out.append("<tbody>")
    for line in rows:
        out.append("<tr>")
        # A null cell is the value the pupil has to supply, so it renders as a
        # blank box rather than the word "None".
        out += [f"<td>{escape(str(c))}</td>" if c is not None
                else '<td class="bg-light">&nbsp;</td>' for c in line]
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def number_box(data):
    numbers = data.get("numbers") or []
    chips = "".join(
        f'<span class="badge bg-light text-dark border fs-6 me-2 mb-2">{escape(str(n))}</span>'
        for n in numbers
    )
    return f'<div class="p-3 border rounded bg-white d-inline-block">{chips}</div>'


SVG_KINDS = {"l_shape": l_shape, "angles_on_line": angles_on_line, "venn": venn}
HTML_KINDS = {"table": table, "number_box": number_box}
