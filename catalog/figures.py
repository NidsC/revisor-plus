"""
Question figures, generated server-side from numeric parameters.

The papers we import specify their diagrams rather than shipping them: a question
carries `"svg": "l_shape"` plus `"dimensions": {...}`, or a `"table": {...}`. So
the figure is fully determined by the data, and we can draw it.

NOTHING HERE STORES OR ECHOES MARKUP. The database keeps only
`{"kind": ..., "data": {numbers}}` and this module turns that into SVG or a table
at render time, coercing every value it interpolates. That is deliberate: storing
generated markup in a JSONField and printing it with `|safe` would turn the admin
question editor into an XSS hole, and stashing generated files under static/
would need them written before `collectstatic` runs in build.sh.
"""
from django.utils.html import escape
from django.utils.safestring import mark_safe

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


def _l_shape(data):
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

    pad, scale = 34, min(300 / top, 190 / left)
    w, h = top * scale, left * scale

    def px(ux, uy):
        return pad + ux * scale, pad + uy * scale

    pts = [(0, 0), (top, 0), (top, right), (bottom_left, right),
           (bottom_left, left), (0, left)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in (px(a, b) for a, b in pts))

    parts = [
        f'<svg viewBox="0 0 {w + 2 * pad:.0f} {h + 2 * pad:.0f}" '
        f'role="img" aria-label="L-shaped figure with labelled edges" '
        f'style="max-width:420px;width:100%;height:auto">',
        f'<polygon points="{path}" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>',
    ]
    # Edge labels, each just outside its own edge.
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)  # noqa: E731
    x, y = mid(px(0, 0), px(top, 0)); parts.append(_txt(x, y - 10, top))
    x, y = mid(px(top, 0), px(top, right)); parts.append(_txt(x + 16, y + 4, right))
    x, y = mid(px(bottom_left, right), px(top, right)); parts.append(_txt(x, y - 8, inner_h))
    x, y = mid(px(bottom_left, right), px(bottom_left, left))
    parts.append(_txt(x + 16, y + 4, inner_v))
    x, y = mid(px(0, left), px(bottom_left, left)); parts.append(_txt(x, y + 20, bottom_left))
    x, y = mid(px(0, 0), px(0, left)); parts.append(_txt(x - 16, y + 4, left))
    parts.append("</svg>")
    return "".join(parts)


def _angles_on_line(data):
    """Straight line AOB with a ray OC. Deliberately schematic — the papers say
    'not drawn to scale' and the actual angle is given in the question text, so
    drawing a specific value would risk contradicting the stem."""
    return (
        '<svg viewBox="0 0 360 170" role="img" '
        'aria-label="Straight line A O B with ray O C, angle x between OC and OB" '
        'style="max-width:360px;width:100%;height:auto">'
        f'<line x1="30" y1="130" x2="330" y2="130" stroke="{STROKE}" stroke-width="2"/>'
        f'<line x1="180" y1="130" x2="285" y2="40" stroke="{STROKE}" stroke-width="2"/>'
        f'<circle cx="180" cy="130" r="4" fill="{STROKE}"/>'
        f'<path d="M 130 130 A 50 50 0 0 1 145 95" fill="none" stroke="{STROKE}"/>'
        f'<path d="M 232 130 A 52 52 0 0 0 218 96" fill="none" stroke="{STROKE}"/>'
        + _txt(24, 148, "A") + _txt(180, 150, "O") + _txt(336, 148, "B")
        + _txt(295, 34, "C") + _txt(120, 104, "AOC") + _txt(243, 112, "x")
        + "</svg>"
    )


def _venn(data):
    """Two overlapping sets. Counts live in the question text, not the diagram —
    the whole task is working out the overlap, so labelling it would answer it."""
    a = escape(str(data.get("left_label", "A")))
    b = escape(str(data.get("right_label", "B")))
    return (
        '<svg viewBox="0 0 380 210" role="img" '
        'aria-label="Two overlapping circles inside a rectangle" '
        'style="max-width:380px;width:100%;height:auto">'
        f'<rect x="8" y="8" width="364" height="194" fill="none" '
        f'stroke="{STROKE}" stroke-dasharray="4 3"/>'
        f'<circle cx="150" cy="105" r="72" fill="{FILL}" fill-opacity=".7" stroke="{STROKE}"/>'
        f'<circle cx="230" cy="105" r="72" fill="{FILL}" fill-opacity=".7" stroke="{STROKE}"/>'
        + _txt(108, 46, a) + _txt(272, 46, b) + "</svg>"
    )


_SVG = {"l_shape": _l_shape, "angles_on_line": _angles_on_line, "venn": _venn}


def _table(data):
    headers = data.get("headers") or []
    rows = data.get("rows") or []
    out = ['<div class="table-responsive"><table class="table table-sm table-bordered '
           'align-middle mb-0" style="width:auto">']
    if headers:
        out.append("<thead><tr>")
        out += [f"<th>{escape('' if h is None else str(h))}</th>" for h in headers]
        out.append("</tr></thead>")
    out.append("<tbody>")
    for row in rows:
        out.append("<tr>")
        # A null cell is the value the pupil has to supply, so it renders as a
        # blank box rather than the word "None".
        out += [f'<td>{escape(str(c)) if c is not None else "&nbsp;"}</td>'
                if c is not None else '<td class="bg-light">&nbsp;</td>' for c in row]
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _number_box(data):
    numbers = data.get("numbers") or []
    chips = "".join(
        f'<span class="badge bg-light text-dark border fs-6 me-2 mb-2">{escape(str(n))}</span>'
        for n in numbers
    )
    return f'<div class="p-3 border rounded bg-white d-inline-block">{chips}</div>'


_HTML = {"table": _table, "number_box": _number_box}


def render_figure(figure):
    """figure -> safe HTML. `figure` is {"kind": str, "data": {...}} or None."""
    if not isinstance(figure, dict):
        return ""
    kind = figure.get("kind")
    data = figure.get("data") if isinstance(figure.get("data"), dict) else {}
    if kind in _SVG:
        return mark_safe(_SVG[kind](data))
    if kind in _HTML:
        return mark_safe(_HTML[kind](data))
    return ""


# Figure kinds this module can actually draw. The importer warns on anything a
# paper asks for that is not in here, rather than silently dropping the diagram
# and leaving a question that cannot be answered.
SUPPORTED = set(_SVG) | set(_HTML)


# ---------------------------------------------------------------- Non-verbal reasoning
#
# Real NVR papers put the candidate answers INSIDE the figure as lettered panels,
# and the pupil writes A/B/C/D. That convention is what makes these generatable
# here: AnswerOption is text-only, so a visual multiple choice would otherwise
# need per-option images. The stem figure carries everything; the options are
# letters.

PANEL = 74          # panel edge in user units
GAP = 10
LETTERS = "ABCDE"


def _poly_points(cx, cy, r, sides, rotation_deg):
    import math
    pts = []
    for i in range(sides):
        a = math.radians(rotation_deg - 90 + i * 360 / sides)
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


def _shape_svg(spec, cx, cy):
    """One shape: n-sided polygon, rotated, optionally shaded, with dots."""
    sides = int(spec.get("sides", 4) or 4)
    rot = _n(spec.get("rot"), 0)
    shaded = bool(spec.get("shaded"))
    dots = int(spec.get("dots", 0) or 0)
    fill = FILL if shaded else "#ffffff"
    out = [f'<polygon points="{_poly_points(cx, cy, 22, max(3, sides), rot)}" '
           f'fill="{fill}" stroke="{STROKE}" stroke-width="2"/>']
    # A marker so a rotation is actually visible — a plain square looks identical
    # at every 90 degrees, which would make the question unanswerable.
    if spec.get("marker"):
        import math
        a = math.radians(rot - 90)
        out.append(f'<circle cx="{cx + 13 * math.cos(a):.1f}" '
                   f'cy="{cy + 13 * math.sin(a):.1f}" r="4" fill="{STROKE}"/>')
    for i in range(dots):
        out.append(f'<circle cx="{cx - 9 + i * 9:.1f}" cy="{cy + 30:.1f}" r="3" '
                   f'fill="{STROKE}"/>')
    return "".join(out)


def _panel(x, y, inner, label=None, dashed=False):
    box = (f'<rect x="{x}" y="{y}" width="{PANEL}" height="{PANEL}" rx="6" '
           f'fill="none" stroke="{STROKE}" stroke-width="1.5"'
           f'{" stroke-dasharray=\"5 4\"" if dashed else ""}/>')
    lab = _txt(x + PANEL / 2, y + PANEL + 16, label) if label else ""
    return box + inner + lab


def _row(specs, y, labels=None, dashed_last=False):
    out = []
    for i, spec in enumerate(specs):
        x = i * (PANEL + GAP)
        inner = "" if spec is None else _shape_svg(spec, x + PANEL / 2, y + PANEL / 2)
        if spec is None:
            inner = _txt(x + PANEL / 2, y + PANEL / 2 + 8, "?", size=26)
        out.append(_panel(x, y, inner, labels[i] if labels else None,
                          dashed=dashed_last and i == len(specs) - 1))
    return "".join(out)


def _nvr_frame(sequence, options, title):
    """Sequence row above, lettered option row below."""
    width = max(len(sequence), len(options)) * (PANEL + GAP)
    height = 2 * PANEL + 74
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}" '
             f'style="max-width:{min(width, 520)}px;width:100%;height:auto">']
    parts.append(_row(sequence, 0, dashed_last=True))
    parts.append(_txt(width / 2, PANEL + 40, "Choose from:", size=12))
    parts.append(_row(options, PANEL + 52, labels=list(LETTERS[:len(options)])))
    parts.append("</svg>")
    return "".join(parts)


def _nvr_series(data):
    return _nvr_frame(list(data.get("sequence") or []) + [None],
                      data.get("options") or [], "Which shape comes next?")


def _nvr_rotation(data):
    return _nvr_frame([data.get("shape") or {}], data.get("options") or [],
                      "Which option is the shape after the transformation?")


def _nvr_net(data):
    """Candidate cube nets on a grid — which folds into a cube."""
    nets = data.get("nets") or []
    cell = 20
    cols, rows = 5, 4
    w_each = cols * cell + 18
    width, height = len(nets) * w_each, rows * cell + 40
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Four candidate nets" '
             f'style="max-width:{min(width, 520)}px;width:100%;height:auto">']
    for i, net in enumerate(nets):
        ox = i * w_each
        for (r, c) in net:
            parts.append(
                f'<rect x="{ox + c * cell}" y="{r * cell}" width="{cell}" '
                f'height="{cell}" fill="{FILL}" stroke="{STROKE}" stroke-width="1.5"/>')
        parts.append(_txt(ox + (cols * cell) / 2, rows * cell + 26, LETTERS[i]))
    parts.append("</svg>")
    return "".join(parts)


_SVG.update({"nvr_series": _nvr_series, "nvr_rotation": _nvr_rotation,
             "nvr_net": _nvr_net})
SUPPORTED = set(_SVG) | set(_HTML)
