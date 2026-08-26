"""
The measurement primitive every figure is built out of.

The bug this exists to prevent: before this package, each figure function wrote
its own `viewBox` literal, guessed from the content it thought it had drawn. The
guesses were wrong, and the fix each time was a magic constant — the old
`_nvr_frame` carried `height = 2 * PANEL + 90` with a comment explaining that
`+74` had clipped the labels' descenders. Every new figure kind was one more
chance to guess wrong.

So nothing here writes a size down. A `Box` carries markup *and* the extent that
markup actually occupies; containers add their children's extents up; and the
viewBox is whatever the outermost Box measured. A figure that draws outside its
box is then a test failure rather than something a pupil notices.
"""

_ESCAPES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;"),
            ("'", "&#39;"))


def escape(value):
    """Stdlib `django.utils.html.escape`.

    This package deliberately does not import Django. It is the single
    implementation of the drawing, shared by the app and by the contributor
    preview tool (`elevenplus_data/preview_questions.py`), which runs on plain
    Python with no settings module and no installed apps. A second
    implementation is the thing to avoid: the preview tool already carried one
    reimplementation that drifted from the app (`WRAP_WIDTH = 90` against the
    app's 100), and it showed authors line numbers the live site disagreed with.

    The Django layer adds `mark_safe` at the template tag, which is where the
    trust boundary belongs.
    """
    out = str(value)
    for char, entity in _ESCAPES:
        out = out.replace(char, entity)
    return out


class Box:
    """Markup plus the space it occupies, in user units, origin at its top left.

    `width`/`height` are the *ink* extent — including half a stroke either side,
    because a 2-unit stroke on a rectangle paints one unit outside the geometry
    and that unit is what gets clipped at the viewBox edge.
    """

    __slots__ = ("markup", "width", "height")

    def __init__(self, markup, width, height):
        self.markup = markup
        self.width = float(width)
        self.height = float(height)

    def at(self, dx, dy):
        """The same drawing, moved. Extent is unchanged — a translate does not
        resize anything, and pretending otherwise is how the old code drifted."""
        if not dx and not dy:
            return self
        return Box(f'<g transform="translate({dx:.1f},{dy:.1f})">{self.markup}</g>',
                   self.width, self.height)


EMPTY = Box("", 0, 0)


def stack(boxes, gap=0, align="start"):
    """Boxes one under another. Measured, not assumed."""
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return EMPTY
    width = max(b.width for b in boxes)
    parts, y = [], 0.0
    for box in boxes:
        if align == "center":
            dx = (width - box.width) / 2
        elif align == "end":
            dx = width - box.width
        else:
            dx = 0.0
        parts.append(box.at(dx, y).markup)
        y += box.height + gap
    return Box("".join(parts), width, y - gap if boxes else 0.0)


def row(boxes, gap=0, align="center"):
    """Boxes side by side. Measured, not assumed."""
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return EMPTY
    height = max(b.height for b in boxes)
    parts, x = [], 0.0
    for box in boxes:
        if align == "center":
            dy = (height - box.height) / 2
        elif align == "end":
            dy = height - box.height
        else:
            dy = 0.0
        parts.append(box.at(x, dy).markup)
        x += box.width + gap
    return Box("".join(parts), x - gap if boxes else 0.0, height)


def svg(box, label, pad=0, scalable=False, paper=True):
    """Wrap a measured Box as a finished SVG element.

    The size rule of this package lives in this function and nowhere else.
    `width`/`height` are written in **pixels equal to the box's user units**, so
    one user unit is one CSS pixel. There is no `width:100%` and no per-kind
    `max-width`: a per-kind `max-width` is exactly what let a five-net figure
    render its labels at 7.5px beside a four-panel one rendering at 13px.

    `scalable` figures are additionally sized through `--fig-scale`, a single
    variable set once per viewport in base.html. The invariant that matters is
    not that a panel is always 64 physical pixels — it is that **every figure on
    a page is at the same scale as every other**, so the hexagon in the stem and
    the hexagon in the option tile beside it are the same picture. One shared
    variable keeps that true at every viewport while still letting a five-panel
    series fit a phone.

    Only non-verbal figures set it. Maths figures carry their edge measurements
    as `<text>` inside the drawing, and shrinking those is the very bug this
    package exists to remove — so they stay at 1:1 and scroll instead.
    """
    width, height = box.width + 2 * pad, box.height + 2 * pad
    sizing = (f'width:calc({width:.0f}px * var(--fig-scale,1));'
              f'height:calc({height:.0f}px * var(--fig-scale,1));'
              if scalable else "")
    # An explicit panel behind the figure, kept from the module this replaced.
    # Its reason is unchanged for the figures that still need it: without one the
    # SVG is transparent and anything drawn in near-black inherits whatever the
    # page background is, and a diagram whose measurements have vanished is not
    # merely ugly, it is unanswerable.
    #
    # Non-verbal figures pass `paper=False`, because they no longer need it and
    # it costs them something. They contain no text at all, and every glyph is
    # explicitly filled, so nothing in one depends on the page behind it. What
    # the rectangle does do is paint a hard white edge inside each answer tile,
    # which shows as a seam wherever the tile is not exactly the same white.
    backdrop = (f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" '
                f'rx="10" fill="#FFFFFF"/>') if paper else ""
    return (f'<svg viewBox="0 0 {width:.0f} {height:.0f}" '
            f'width="{width:.0f}" height="{height:.0f}" '
            f'role="img" aria-label="{escape(label)}" '
            f'style="display:block;flex:none;{sizing}">'
            f'{backdrop}{box.at(pad, pad).markup}</svg>')
