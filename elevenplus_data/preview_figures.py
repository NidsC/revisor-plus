#!/usr/bin/env python3
"""
Render every figure this build can draw onto one page, at three screen widths.

Usage:
    python3 elevenplus_data/preview_figures.py            # writes figures-preview.html
    python3 elevenplus_data/preview_figures.py out.html

Two audiences.

For whoever is **authoring** non-verbal questions: this is the vocabulary. Every
shape, fill, size and position a `figure` spec may name is on the page with the
spec that drew it, so choosing between `hatch` and `cross_hatch` is looking
rather than guessing, and asking for something that is not there is obvious
before a pack is written.

For whoever is **changing the renderer**: the three width columns are the check
that the size contract holds. The failure this replaced was not that any one
figure looked wrong on its own — it was that two figures in the same paper drew
the same square at different sizes, and only a side-by-side showed it. A panel
must be the same size in every row of a column.

Stdlib only, and it imports `catalog.figures` rather than reimplementing any of
the drawing. That is deliberate: a preview that draws its own version of the
figures is a preview that can disagree with the live site, which has happened
here before.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog.figures import render_figure, render_option_figure  # noqa: E402
from catalog.figures.glyphs import (CHIRAL, FILLS, MAX_REPEAT,  # noqa: E402
                                    POSITIONS, SHAPES, SIZES, STROKES,
                                    fits_without_compressing)
from catalog.figures.layout import CELL, MAX_INTRINSIC  # noqa: E402

# The widths that matter: a small phone, a large phone/small tablet, and a
# desktop. --fig-scale steps at 400 and 576, so these straddle both steps.
WIDTHS = [("360px — phone", 360, 0.70), ("576px — large phone", 576, 0.82),
          ("1100px — desktop", 1100, 1.0)]


def panel(cell):
    return render_option_figure({"kind": "nvr_panel", "data": {"cell": cell}})


def swatch(label, markup, note=""):
    return (f'<figure class="sw"><div class="sw-art">{markup}</div>'
            f'<figcaption>{label}'
            f'{f"<span>{note}</span>" if note else ""}</figcaption></figure>')


def vocabulary():
    out = []

    out.append("<h2>Shapes</h2><p>Every outline a spec may name. The four marked "
               "<b>chiral</b> have no mirror symmetry, which is what a question "
               "about reflection needs — reflecting any of the others gives a "
               "picture some rotation of it also gives.</p><div class='grid'>")
    for name in sorted(SHAPES):
        note = "chiral" if name in CHIRAL else ""
        out.append(swatch(name, panel({"shape": name}), note))
    out.append("</div>")

    out.append("<h2>Fills</h2><p>Shading is computed as geometry, not a pattern "
               "fill, so it follows the outline exactly — a circle shaded "
               "<code>half</code> is a true semicircle.</p><div class='grid'>")
    for name in sorted(FILLS):
        out.append(swatch(name, panel({"shape": "pentagon", "fill": name})))
    out.append("</div>")

    out.append("<h2>Sizes</h2><div class='grid'>")
    for name, fraction in sorted(SIZES.items(), key=lambda kv: kv[1]):
        out.append(swatch(name, panel({"shape": "hexagon", "size": name}),
                          f"{fraction:.2f} of the panel"))
    out.append("</div>")

    out.append("<h2>Strokes</h2><div class='grid'>")
    for name in sorted(STROKES):
        out.append(swatch(name, panel({"shape": "square", "stroke": name})))
    out.append("</div>")

    out.append("<h2>Positions</h2><p>Where a glyph sits in its panel. A panel may "
               "hold several glyphs at different positions.</p><div class='grid'>")
    for name in sorted(POSITIONS):
        out.append(swatch(name, panel({"items": [
            {"shape": "square", "size": "large"},
            {"shape": "circle", "size": "small", "fill": "solid", "at": name}]})))
    out.append("</div>")

    out.append("<h2>Rotation and reflection</h2><p>A reflection is applied before "
               "the rotation. The corner mark reflects with the shape — without "
               "it a rotation is invisible on a symmetric outline.</p>"
               "<div class='grid'>")
    for rotation in (0, 45, 90, 180, 270):
        out.append(swatch(f"rot {rotation}",
                          panel({"shape": "flag", "rot": rotation, "marker": 1})))
    out.append(swatch("flip horizontal",
                      panel({"shape": "flag", "flip": "horizontal", "marker": 1})))
    out.append(swatch("flip vertical",
                      panel({"shape": "flag", "flip": "vertical", "marker": 1})))
    out.append("</div>")

    out.append("<h2>Repeat</h2><p>Counting is one of the rules real papers are "
               "built on. Copies are never dropped — a count that drew fewer "
               "than it claimed would make the rule the question turns on "
               "invisible.</p>"
               "<p><b>Use <code>tiny</code> for anything counted.</b> A row keeps "
               "the size it was given for as long as it fits and is compressed "
               "only when it will not, so marks that are too big to fit shrink as "
               "the count rises — and a counting rule whose marks change size "
               "reads as a size rule too. Compare the two rows.</p>"
               "<div class='grid'>")
    for count in range(1, MAX_REPEAT + 1):
        out.append(swatch(f"tiny × {count}", panel({"items": [
            {"shape": "square", "size": "large"},
            {"shape": "circle", "size": "tiny", "fill": "solid",
             "at": "bottom", "repeat": count}]}), "same size"))
    out.append("</div><div class='grid'>")
    for count in range(1, MAX_REPEAT + 1):
        note = "" if fits_without_compressing("small", count) else "squashed"
        out.append(swatch(f"small × {count}", panel({"items": [
            {"shape": "square", "size": "large"},
            {"shape": "circle", "size": "small", "fill": "solid",
             "at": "bottom", "repeat": count}]}), note))
    out.append("</div>")
    return "".join(out)


def kinds():
    def cell(shape, **attrs):
        spec = {"shape": shape}
        spec.update(attrs)
        return spec

    examples = [
        ("nvr_grid — series", {"kind": "nvr_grid", "data": {
            "cells": [cell("flag", rot=i * 90, marker=1) for i in range(3)] + [None],
            "blank": 3}}),
        ("nvr_grid — long series (scrolls on a phone)", {"kind": "nvr_grid", "data": {
            "cells": [cell("hexagon", rot=i * 45, marker=1) for i in range(5)] + [None],
            "blank": 5}}),
        ("nvr_grid — 3x3 matrix", {"kind": "nvr_grid", "data": {
            "cells": [cell("square", fill=f) for f in
                      ("none", "half", "solid", "hatch", "dots", "cross_hatch",
                       "quarter", "none")] + [None],
            "cols": 3, "blank": 8}}),
        ("nvr_grid — analogy", {"kind": "nvr_grid", "data": {
            "cells": [cell("l_shape"), cell("l_shape", rot=180), cell("star"), None],
            "blank": 3, "separator_after": 1}}),
        ("nvr_net", {"kind": "nvr_net", "data": {
            "squares": [[1, 0], [1, 1], [1, 2], [1, 3], [0, 1], [2, 2]]}}),
        ("l_shape (Maths — keeps its labels, so it never scales)",
         {"kind": "l_shape", "data": {"top": 18, "left": 10, "bottom_left": 11,
                                      "right": 4}}),
        ("venn (Maths)", {"kind": "venn", "data": {"left_label": "Cats",
                                                   "right_label": "Dogs"}}),
    ]
    out = ["<h2>Figure kinds</h2>"]
    for label, figure in examples:
        out.append(f"<h3>{label}</h3>{render_figure(figure)}")

    out.append("<h3>An answer, as the pupil meets it</h3><p>Each option is a tile "
               "carrying its own panel, its letter and a real radio input. The "
               "letter is HTML, so it stays the page's font size whatever the "
               "figure does.</p>")
    out.append(render_figure({"kind": "nvr_grid", "data": {
        "cells": [cell("right_triangle", rot=i * 90, marker=1) for i in range(3)]
        + [None], "blank": 3}}))
    out.append("<div class='nvr-options'>")
    for index, rotation in enumerate((270, 90, 0, 180)):
        letter = "ABCD"[index]
        out.append(
            f'<label class="nvr-option{" is-correct" if rotation == 270 else ""}">'
            f'<span class="nvr-option-figure">'
            f'{panel(cell("right_triangle", rot=rotation, marker=1))}</span>'
            f'<span class="nvr-option-letter">{letter}</span></label>')
    out.append("</div>")
    return "".join(out)


CSS = """
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 system-ui,-apple-system,'Segoe UI',sans-serif;
     color:#0F172A;background:#F6F8FC}
header{padding:1.5rem 1.25rem;background:#fff;border-bottom:1px solid #E6EBF2}
h1{margin:0 0 .35rem;font-size:1.3rem}
header p{margin:0;color:#64748B;max-width:70ch}
.cols{display:flex;gap:1.25rem;align-items:flex-start;padding:1.25rem;
      overflow-x:auto}
.col{background:#fff;border:1px solid #E6EBF2;border-radius:.85rem;flex:none;
     box-shadow:0 1px 3px rgba(15,23,42,.06)}
.col-head{padding:.6rem .9rem;border-bottom:1px solid #E6EBF2;font-weight:700;
          font-size:.85rem;position:sticky;top:0;background:#fff;border-radius:.85rem .85rem 0 0}
.col-head span{font-weight:400;color:#64748B}
.col-body{padding:.9rem}
h2{font-size:1rem;margin:1.4rem 0 .3rem;padding-top:.9rem;
   border-top:1px solid #E6EBF2}
h2:first-child{border-top:0;padding-top:0;margin-top:0}
h3{font-size:.85rem;margin:1rem 0 .4rem;color:#3F4C5F}
p{margin:.2rem 0 .7rem;color:#64748B;font-size:.8rem}
code{background:#F1F5F9;padding:.05rem .25rem;border-radius:.25rem;font-size:.9em}
.grid{display:flex;flex-wrap:wrap;gap:.5rem}
.sw{margin:0;text-align:center}
.sw-art{line-height:0}
.sw figcaption{font-size:.62rem;color:#64748B;margin-top:.15rem;max-width:80px}
.sw figcaption span{display:block;color:#2563EB;font-weight:700}
.figure-scroll{overflow-x:auto;max-width:100%;padding-bottom:.15rem}
.nvr-options{display:flex;flex-wrap:wrap;gap:.75rem;margin-top:.6rem}
.nvr-option{display:flex;flex-direction:column;align-items:center;gap:.35rem;
  padding:.55rem .55rem .4rem;background:#fff;border:1px solid #E6EBF2;
  border-radius:.85rem}
.nvr-option-figure{display:block;line-height:0}
.nvr-option-letter{font-size:.8rem;font-weight:700;color:#64748B}
.nvr-option.is-correct{background:#F0FDF4;border-color:#16A34A}
.nvr-option.is-correct .nvr-option-letter{color:#16A34A}
"""


def build():
    body = vocabulary() + kinds()
    columns = []
    for label, width, scale in WIDTHS:
        columns.append(
            f'<div class="col" style="width:{width}px;--fig-scale:{scale}">'
            f'<div class="col-head">{label} '
            f'<span>&mdash; --fig-scale: {scale}</span></div>'
            f'<div class="col-body">{body}</div></div>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Figure vocabulary &mdash; RevisorPlus</title><style>{CSS}</style></head>
<body>
<header>
  <h1>Every figure this build can draw</h1>
  <p>The same page rendered at three widths. A panel is
  <b>{CELL}px</b> at full size and every figure on a page shares one
  <code>--fig-scale</code>, so within a column a panel is the same size in every
  row &mdash; that is the property to check. A stem figure wider than
  <b>{MAX_INTRINSIC}px</b> scrolls rather than shrinking, and
  <code>validate_questions.py</code> warns the author it will.</p>
</header>
<div class="cols">{"".join(columns)}</div>
</body></html>"""


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "figures-preview.html")
    target.write_text(build(), encoding="utf-8")
    print(f"Wrote {target} ({target.stat().st_size // 1024} KB)")
