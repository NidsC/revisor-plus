"""
Checks that every figure this build can draw obeys the same size contract.

Run:  python3 test_figures.py

No Django and no database — `catalog/figures` is deliberately stdlib-only, and a
test that needed a settings module could not prove that.

**What this is defending against.** Before the figures package existed, each
figure function wrote its own `viewBox` and its own `style="max-width:Npx"`, and
the two were unrelated. Measured on the old module:

    nvr_series 3 seq / 4 opts   viewBox 336x238   max-width 336   1.00 px/unit
    nvr_net    4 nets           viewBox 472x126   max-width 472   1.00 px/unit
    nvr_net    5 nets           viewBox 590x126   max-width 520   0.88 px/unit
    l_shape                     viewBox 368x235   max-width 420   1.14 px/unit

The 1.00s were a coincidence — they held only where a function happened to set
`max-width` equal to its own viewBox width. Where it did not, the whole drawing
scaled, text included: a five-net figure rendered its A-D labels at 11.5px on a
desktop and 7.5px on a phone, beside radio buttons that stayed the same size. So
these are the four things a figure must never do again:

  1. render at anything other than one CSS pixel per user unit
  2. draw chrome text inside a non-verbal figure, where it would scale
  3. draw outside its own measured box (the old `_nvr_frame` carried
     `height = 2 * PANEL + 90` because `+74` clipped the labels' descenders)
  4. draw a shape nobody asked for when the spec names one this build cannot draw

Every check below is one of those four.
"""
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, ".")

from catalog.figures import (OPTION_KINDS, SUPPORTED, intrinsic_width,  # noqa: E402
                             render_figure, render_option_figure)
from catalog.figures.glyphs import FILLS, SHAPES, SIZES  # noqa: E402
from catalog.figures.layout import CELL, MAX_INTRINSIC  # noqa: E402

FAILURES = []


def check(condition, message):
    if condition:
        return True
    FAILURES.append(message)
    return False


def cell(shape, **attrs):
    spec = {"shape": shape}
    spec.update(attrs)
    return spec


# Every non-verbal figure this build can draw, at the sizes a real paper uses.
# The counts matter: 5 and 6 panels are where the old renderer's hardcoded
# `min(width, 520)` cap started shrinking things.
def nvr_cases():
    cases = []
    for count in (2, 3, 4, 5, 6):
        cases.append((f"nvr_grid series of {count}", "nvr_grid", {
            "cells": [cell("hexagon", rot=i * 45, marker=1) for i in range(count)] + [None],
            "blank": count}))
    cases.append(("nvr_grid 3x3 matrix", "nvr_grid", {
        "cells": [cell("square", fill=f) for f in sorted(FILLS)] + [None],
        "cols": 3, "blank": len(FILLS)}))
    cases.append(("nvr_grid 2x4 matrix", "nvr_grid", {
        "cells": [cell("triangle", rot=i * 30) for i in range(7)] + [None],
        "cols": 4, "blank": 7}))
    cases.append(("nvr_grid analogy", "nvr_grid", {
        "cells": [cell("triangle"), cell("triangle", rot=180), cell("star"), None],
        "blank": 3, "separator_after": 1}))
    for size in sorted(SIZES):
        cases.append((f"nvr_panel {size}", "nvr_panel", {
            "cell": cell("pentagon", fill="hatch", size=size)}))
    cases.append(("nvr_panel multi-glyph", "nvr_panel", {"cell": {"items": [
        cell("square", size="large"), cell("circle", size="small", at="top_right"),
        cell("star", size="small", at="bottom_left", fill="solid")]}}))
    cases.append(("nvr_net 1-4-1", "nvr_net", {
        "squares": [[1, 0], [1, 1], [1, 2], [1, 3], [0, 1], [2, 2]]}))
    cases.append(("nvr_net 2x3", "nvr_net", {
        "squares": [[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2]]}))
    return cases


def mat_cases():
    return [
        ("l_shape", "l_shape", {"top": 18, "left": 10, "bottom_left": 11, "right": 4}),
        ("l_shape small", "l_shape", {"top": 7, "left": 5, "bottom_left": 4, "right": 2}),
        ("angles_on_line", "angles_on_line", {}),
        ("venn", "venn", {"left_label": "Cats", "right_label": "Dogs"}),
    ]


# ---------------------------------------------------------------- extents
#
# Walks the emitted SVG and works out how far the ink actually reaches,
# accumulating the `translate` on each nested <g>. This is what makes check 3 a
# real check rather than a restatement of what the renderer already believes.

def _numbers(element, *names):
    return [float(element.get(name, 0) or 0) for name in names]


def _extent(element, dx, dy, found):
    tag = element.tag.split("}")[-1]
    if tag == "g":
        transform = element.get("transform", "")
        match = re.search(r"translate\(([-\d.]+),([-\d.]+)\)", transform)
        if match:
            dx += float(match.group(1))
            dy += float(match.group(2))
    elif tag == "rect":
        x, y, w, h = _numbers(element, "x", "y", "width", "height")
        stroke = float(element.get("stroke-width", 0) or 0) / 2
        found.append((dx + x - stroke, dy + y - stroke,
                      dx + x + w + stroke, dy + y + h + stroke))
    elif tag == "circle":
        cx, cy, r = _numbers(element, "cx", "cy", "r")
        found.append((dx + cx - r, dy + cy - r, dx + cx + r, dy + cy + r))
    elif tag == "line":
        x1, y1, x2, y2 = _numbers(element, "x1", "y1", "x2", "y2")
        stroke = float(element.get("stroke-width", 0) or 0) / 2
        found.append((dx + min(x1, x2) - stroke, dy + min(y1, y2) - stroke,
                      dx + max(x1, x2) + stroke, dy + max(y1, y2) + stroke))
    elif tag == "polygon":
        points = [tuple(float(v) for v in pair.split(","))
                  for pair in element.get("points", "").split() if "," in pair]
        if points:
            stroke = float(element.get("stroke-width", 0) or 0) / 2
            found.append((dx + min(p[0] for p in points) - stroke,
                          dy + min(p[1] for p in points) - stroke,
                          dx + max(p[0] for p in points) + stroke,
                          dy + max(p[1] for p in points) + stroke))
    elif tag == "text":
        # Approximate metrics, which is all that is needed: the failure this
        # catches is a label sitting near the edge of the box with its
        # descenders hanging over it, and that is a whole-character overrun.
        x, y = _numbers(element, "x", "y")
        size = float(element.get("font-size", 13) or 13)
        width = 0.62 * size * len(element.text or "")
        anchor = element.get("text-anchor", "start")
        left = x - width / 2 if anchor == "middle" else (x - width if anchor == "end" else x)
        found.append((dx + left, dy + y - 0.8 * size,
                      dx + left + width, dy + y + 0.26 * size))
    for child in element:
        _extent(child, dx, dy, found)


def ink_extent(markup):
    root = ET.fromstring(markup)
    found = []
    for child in root:
        _extent(child, 0.0, 0.0, found)
    if not found:
        return None
    return (min(b[0] for b in found), min(b[1] for b in found),
            max(b[2] for b in found), max(b[3] for b in found))


def svg_of(markup):
    """The <svg> element out of whatever render_figure wrapped it in."""
    start = markup.find("<svg")
    return markup[start:markup.rfind("</svg>") + 6] if start >= 0 else ""


# ------------------------------------------------------------------- checks

def check_figure(label, markup, is_nvr):
    element = svg_of(markup)
    if not check(element, f"{label}: produced no SVG"):
        return
    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', element)
    attrs = re.search(r'width="([\d.]+)" height="([\d.]+)"', element)
    if not check(box and attrs, f"{label}: missing viewBox or width/height"):
        return
    view_w, view_h = float(box.group(1)), float(box.group(2))
    px_w, px_h = float(attrs.group(1)), float(attrs.group(2))

    # 1. one user unit is one CSS pixel, in every kind, at every size
    check(abs(px_w - view_w) < 1e-6 and abs(px_h - view_h) < 1e-6,
          f"{label}: renders at {px_w / view_w:.3f} px per user unit, not 1.000")
    check("max-width" not in element,
          f"{label}: sets its own max-width, which is what let kinds disagree")
    check("width:100%" not in element,
          f"{label}: uses width:100%, so it scales with the container")

    # Responsive sizing goes through one page-wide variable, never a per-kind
    # constant. That is the difference between "every figure is at the same
    # scale as every other" and the old behaviour, where each kind picked its
    # own and two questions in one paper drew the same square at two sizes.
    if is_nvr:
        check("var(--fig-scale,1)" in element,
              f"{label}: does not size through --fig-scale, so it will not stay "
              f"in step with the other figures on the page")
    else:
        check("var(--fig-scale" not in element,
              f"{label}: a Maths figure carries its labels as <text>; scaling it "
              f"shrinks them, which is the bug this package removes")

    # 2. no chrome text inside a non-verbal figure
    if is_nvr:
        check("<text" not in element,
              f"{label}: draws text inside the SVG, where it will scale with "
              f"the figure instead of staying at the page's font size")

    # 3. everything drawn is inside the box that was measured for it
    extent = ink_extent(element)
    if extent:
        left, top, right, bottom = extent
        check(left >= -0.51 and top >= -0.51,
              f"{label}: draws above/left of its box (ink starts at "
              f"{left:.1f},{top:.1f})")
        check(right <= view_w + 0.51 and bottom <= view_h + 0.51,
              f"{label}: draws outside its box — ink reaches {right:.1f}x"
              f"{bottom:.1f} in a {view_w:.0f}x{view_h:.0f} box. This is the "
              f"clipping the old renderer patched with a magic +90.")
    return view_w, view_h


def main():
    print("Figure size contract\n" + "=" * 74)
    print(f"{'figure':<28}{'box':<13}{'rendered':<13}{'px/unit':>9}{'text':>6}{'scrolls':>9}")

    for label, kind, data in nvr_cases():
        markup = render_figure({"kind": kind, "data": data})
        result = check_figure(label, markup, is_nvr=True)
        if not result:
            continue
        view_w, view_h = result
        element = svg_of(markup)
        # `intrinsic_width` is what validate_questions.py warns authors from, so
        # it has to agree with what is actually emitted.
        check(intrinsic_width(kind, data) == int(view_w),
              f"{label}: intrinsic_width says {intrinsic_width(kind, data)}, "
              f"emitted {int(view_w)} — the author warning would be wrong")
        print(f"{label:<28}{f'{view_w:.0f}x{view_h:.0f}':<13}"
              f"{f'{view_w:.0f}x{view_h:.0f}px':<13}{1.0:>9.3f}"
              f"{element.count('<text'):>6}"
              f"{('yes' if view_w > MAX_INTRINSIC else ''):>9}")

    for label, kind, data in mat_cases():
        markup = render_figure({"kind": kind, "data": data})
        result = check_figure(label, markup, is_nvr=False)
        if not result:
            continue
        view_w, view_h = result
        element = svg_of(markup)
        print(f"{label:<28}{f'{view_w:.0f}x{view_h:.0f}':<13}"
              f"{f'{view_w:.0f}x{view_h:.0f}px':<13}{1.0:>9.3f}"
              f"{element.count('<text'):>6}"
              f"{('yes' if view_w > MAX_INTRINSIC else ''):>9}")

    print("-" * 74)

    # 4. one panel size everywhere. A hexagon in the stem and the hexagon in the
    # option tile the pupil compares it against must be the same picture.
    stem = svg_of(render_figure({"kind": "nvr_grid", "data": {
        "cells": [cell("hexagon")], "blank": None}}))
    tile = render_option_figure({"kind": "nvr_panel", "data": {"cell": cell("hexagon")}})
    stem_w = float(re.search(r'width="([\d.]+)"', stem).group(1))
    tile_w = float(re.search(r'width="([\d.]+)"', tile).group(1))
    check(stem_w == tile_w == CELL,
          f"a stem panel is {stem_w:.0f}px and an option tile {tile_w:.0f}px; "
          f"both must be CELL ({CELL})")
    print(f"panel size: stem {stem_w:.0f}px, option tile {tile_w:.0f}px, CELL {CELL}")

    # A net square is exactly half a panel, so nets and shapes share one scale.
    net = render_option_figure({"kind": "nvr_net", "data": {"squares": [[0, 0]]}})
    net_w = float(re.search(r'width="([\d.]+)"', net).group(1))
    check(net_w == CELL / 2,
          f"a single net square is {net_w:.0f}px, expected {CELL / 2:.0f}px")
    print(f"net square: {net_w:.0f}px (half a panel)")

    # A counted row keeps one glyph size. Sizing the marks by dividing the
    # available width by the count makes a panel of two draw visibly bigger marks
    # than a panel of four, and in a series whose rule is "one more each time"
    # that reads as a second rule about size which nobody intended.
    widths = []
    for count in range(1, 6):
        markup = render_option_figure({"kind": "nvr_panel", "data": {"cell": {
            "items": [{"shape": "square", "size": "large"},
                      {"shape": "circle", "size": "tiny", "fill": "solid",
                       "at": "bottom", "repeat": count}]}}})
        marks = re.findall(r'<polygon points="([^"]+)"', markup)
        spans = []
        for points in marks:
            xs = [float(pair.split(",")[0]) for pair in points.split()]
            spans.append(round(max(xs) - min(xs), 1))
        widths.append(min(spans))
    check(len(set(widths)) == 1,
          f"a counted row of 'tiny' glyphs draws them at {sorted(set(widths))} "
          f"across counts 1-5; a counting rule must not also change the size")
    print(f"counted marks: {widths[0]}px wide at every count from 1 to 5")

    # 5. the vocabulary is closed — an unknown token draws nothing rather than
    # quietly substituting a default the author did not ask for.
    unknown = render_option_figure(
        {"kind": "nvr_panel", "data": {"cell": cell("octogon")}})
    check("<polygon" not in unknown,
          "an unknown shape name drew something anyway; the validator's promise "
          "that a pack can only ask for drawable pictures depends on it not")
    check(render_figure({"kind": "nvr_totally_made_up", "data": {}}) == "",
          "an unknown figure kind produced markup")
    print(f"vocabulary: {len(SHAPES)} shapes, {len(FILLS)} fills, "
          f"{len(SIZES)} sizes; unknown tokens draw nothing")
    print(f"kinds: {len(SUPPORTED)} supported, {len(OPTION_KINDS)} usable on an option")

    print("=" * 74)
    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL  {failure}")
        print(f"\nRESULT: {len(FAILURES)} FAILED")
        return 1
    print("\nRESULT: ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
