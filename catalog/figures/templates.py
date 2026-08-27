"""
Named diagram templates for non-verbal reasoning questions.

`catalog/figures/nvr.py` gives three kinds a question's `figure` can be —
`nvr_grid`, `nvr_panel`, `nvr_net` — and every question fills in that kind's
`data` from scratch: which cells, which one is blank, which squares make a net.
That is precise, but it is also everything a `/questions` session had no
guidance for, because nothing here named the shapes NVR questions actually
come in.

A template is that name. `nvr.rotating_series` is "a row of one shape turning
by a fixed step, last panel blank" — an author gives a shape and a step, not a
hand-built `cells` list — and `resolve()` turns the two into the concrete
`kind`/`data` a question or option already knows how to store. Nothing about
`nvr_grid`/`nvr_panel`/`nvr_net` changes: a template is resolved once, when a
pack is imported (`import_pack.py`, the same seam that already resolves a
pack's `table_ref` into a figure), and the database only ever holds the
resolved shape.

Three of NVR's six subtopics — Analogies, Codes, Odd One Out — have no
generator and no questions (see pending_issues.md). All three are already
drawable with the existing kinds; what was missing was a name for the
arrangement, not a new kind. `nvr.simple_analogy`, `nvr.corner_code` and
`nvr.odd_one_out` are exactly the shapes worked out by hand in
`_EXAMPLE.nvr_figures.json`, given a name so the next question does not start
from a blank cell either.

The three subtopics WITH a generator (`catalog/generators/nonverbal.py`) share
their cell-building code with the matching templates here, via `cell()` and
`strip_net()` below — so a rotated cell means the same thing whether a rule
built it or a person did, and there is exactly one place that knows how.
"""
from dataclasses import dataclass, field
from typing import Callable

TEMPLATES = {}


@dataclass(frozen=True)
class Template:
    id: str
    subtopic: str          # must match a taxonomy.json NVR subtopic name
    summary: str            # one line, for an author choosing between templates
    required: frozenset
    build: Callable[[dict], dict]
    optional: frozenset = field(default_factory=frozenset)


def register(template):
    TEMPLATES[template.id] = template
    return template


def resolve(template_id, data):
    """The concrete `{"kind": ..., "data": {...}}` a template and its slot data
    produce — what `import_pack.py` stores in place of a pack's `template_id`
    form, and what a generator gets in place of hand-building the same shape.

    Raises `KeyError` for an unknown id. Every pack reaching this should already
    have passed `validate_questions.py`'s `_check_template`, which checks the id
    and the slot data first — so this is a caller's bug reaching this
    unvalidated, not an authoring mistake, and it should fail loudly rather than
    store a blank figure.
    """
    return TEMPLATES[template_id].build(dict(data) if isinstance(data, dict) else {})


def _alt(data, fallback):
    given = data.get("alt")
    return given if isinstance(given, str) and given.strip() else fallback


# --------------------------------------------------------------------------
# Shared cell/net builders.
#
# Moved here from `catalog/generators/nonverbal.py`, which now imports them,
# so the generator and an author's `template_id` both go through the same
# construction — the alternative was two copies of "what a rotated cell looks
# like" drifting apart the first time one of them changed.

def cell(shape, rot=0, fill="none", dots=0, marker=False, flip=None):
    """One panel's contents, in the vocabulary `catalog/figures/glyphs.py` draws.

    `dots` adds the second rule a harder series question layers on top of the
    rotation — a row of small circles along the bottom of the panel, counted
    rather than compared. The shape moves to the top of the panel to make room:
    centred, it overlaps the dot row.
    """
    head = {"shape": shape, "rot": rot % 360, "fill": fill}
    if marker:
        head["marker"] = True
    if flip:
        head["flip"] = flip
    if not dots:
        return head
    head["at"] = "top"
    return {"items": [head, {"shape": "circle", "size": "tiny", "fill": "solid",
                             "at": "bottom", "repeat": dots}]}


def strip_net(above_col, below_col):
    """A 1-4-1 cube net: a strip of four faces with one above and one below.

    That shape always folds into a cube wherever the two flaps sit, so this is
    how a generator or an author gets a guaranteed-valid net without running a
    folding simulation. `above_col`/`below_col` are 0-3, the column the flap
    attaches at along the strip.
    """
    return [(1, 0), (1, 1), (1, 2), (1, 3), (0, above_col), (2, below_col)]


_NET_TRANSFORMS = {
    "rotate90": lambda r, c: (c, -r),
    "rotate180": lambda r, c: (-r, -c),
    "rotate270": lambda r, c: (-c, r),
    "flip_h": lambda r, c: (r, -c),
    "flip_v": lambda r, c: (-r, c),
}


# --------------------------------------------------------------------------
# Series & Sequences

def _rotating_series(data):
    shape = data["shape"]
    step = data["step"]
    start_rot = data.get("start_rot", 0)
    count = data.get("count", 3)
    marker = data.get("marker", True)
    fill = data.get("fill", "none")
    dots_start = data.get("dots_start", 0)
    dots_step = data.get("dots_step", 1)
    cells = [
        cell(shape, rot=start_rot + i * step, fill=fill, marker=marker,
             dots=(dots_start + i * dots_step) if dots_start else 0)
        for i in range(count)
    ]
    cells.append(None)
    direction = "clockwise" if step >= 0 else "anticlockwise"
    return {"kind": "nvr_grid", "data": {
        "cells": cells, "blank": count,
        "alt": _alt(data, f"A {shape.replace('_', ' ')} turning {abs(step)}° "
                          f"{direction} each time, with the last one missing"),
    }}


register(Template(
    id="nvr.rotating_series", subtopic="Series & Sequences",
    summary="A row of one shape turning by a fixed step each panel, last one blank.",
    required=frozenset({"shape", "step"}),
    optional=frozenset({"start_rot", "count", "marker", "fill", "dots_start",
                        "dots_step", "alt"}),
    build=_rotating_series,
))


def _size_progression(data):
    shape = data["shape"]
    sizes = data["sizes"]
    cells = [{"shape": shape, "size": s} for s in sizes]
    cells.append(None)
    return {"kind": "nvr_grid", "data": {
        "cells": cells, "blank": len(sizes),
        "alt": _alt(data, f"A {shape.replace('_', ' ')} growing in size each "
                          f"time, with the last one missing"),
    }}


register(Template(
    id="nvr.size_progression", subtopic="Series & Sequences",
    summary="A row of one shape stepping through named sizes, last one blank.",
    required=frozenset({"shape", "sizes"}),
    optional=frozenset({"alt"}),
    build=_size_progression,
))


def _count_progression(data):
    shape = data["shape"]
    start_count = data["start_count"]
    step = data.get("step", 1)
    count = data.get("count", 3)
    cells = [
        {"shape": shape, "size": "tiny", "fill": "solid",
         "repeat": start_count + i * step}
        for i in range(count)
    ]
    cells.append(None)
    return {"kind": "nvr_grid", "data": {
        "cells": cells, "blank": count,
        "alt": _alt(data, f"A row of {shape.replace('_', ' ')} marks increasing "
                          f"by {step} each time, with the last one missing"),
    }}


register(Template(
    id="nvr.count_progression", subtopic="Series & Sequences",
    summary="A row counting up by a fixed step each panel, last one blank.",
    required=frozenset({"shape", "start_count"}),
    optional=frozenset({"step", "count", "alt"}),
    build=_count_progression,
))


# --------------------------------------------------------------------------
# Rotation & Reflection

def _rotate_reflect(data):
    shape = data["shape"]
    base_rot = data.get("base_rot", 0)
    marker = data.get("marker", True)
    fill = data.get("fill", "none")
    flip = data.get("flip")
    return {"kind": "nvr_grid", "data": {
        "cells": [cell(shape, rot=base_rot, fill=fill, marker=marker, flip=flip)],
        "alt": _alt(data, "The shape before the transformation"),
    }}


register(Template(
    id="nvr.rotate_reflect", subtopic="Rotation & Reflection",
    summary="A single shape, shown before a rotation or reflection is applied.",
    required=frozenset({"shape"}),
    optional=frozenset({"base_rot", "marker", "fill", "flip", "alt"}),
    build=_rotate_reflect,
))


# --------------------------------------------------------------------------
# 3D Shapes & Nets

def _which_net_folds(data):
    above_col, below_col = data["above_col"], data["below_col"]
    for name, value in (("above_col", above_col), ("below_col", below_col)):
        if not isinstance(value, int) or not 0 <= value <= 3:
            raise ValueError(f"{name} must be a whole number from 0 to 3, "
                             f"got {value!r}")
    squares = strip_net(above_col, below_col)
    return {"kind": "nvr_net", "data": {
        "squares": [list(s) for s in squares],
        "alt": _alt(data, "A strip of four squares with one above and one below"),
    }}


register(Template(
    id="nvr.which_net_folds", subtopic="3D Shapes & Nets",
    summary="A guaranteed-valid 1-4-1 cube net (a strip of four, one above, one below).",
    required=frozenset({"above_col", "below_col"}),
    optional=frozenset({"alt"}),
    build=_which_net_folds,
))


def _matching_net(data):
    squares = data["squares"]
    transform_name = data["transform"]
    transform = _NET_TRANSFORMS.get(transform_name)
    if transform is None:
        raise ValueError(f"transform must be one of {sorted(_NET_TRANSFORMS)}, "
                         f"got {transform_name!r}")
    pairs = [(int(r), int(c)) for r, c in squares]
    transformed = [transform(r, c) for r, c in pairs]
    min_r = min(r for r, _ in transformed)
    min_c = min(c for _, c in transformed)
    return {"kind": "nvr_net", "data": {
        "squares": [[r - min_r, c - min_c] for r, c in transformed],
        "alt": _alt(data, f"The given net, {transform_name.replace('_', ' ')}"),
    }}


register(Template(
    id="nvr.matching_net", subtopic="3D Shapes & Nets",
    summary="A given net, rotated or reflected — for \"which net is the same net turned?\"",
    required=frozenset({"squares", "transform"}),
    optional=frozenset({"alt"}),
    build=_matching_net,
))


# --------------------------------------------------------------------------
# Analogies

def _simple_analogy(data):
    return {"kind": "nvr_grid", "data": {
        "cells": [data["from_a"], data["to_a"], data["from_c"], None],
        "blank": 3, "separator_after": 1,
        "alt": _alt(data, "The first shape changes into the second; the third "
                          "shape's pair is missing"),
    }}


register(Template(
    id="nvr.simple_analogy", subtopic="Analogies",
    summary="A is to B as C is to ? — the classic four-cell analogy with one separator.",
    required=frozenset({"from_a", "to_a", "from_c"}),
    optional=frozenset({"alt"}),
    build=_simple_analogy,
))


# --------------------------------------------------------------------------
# Codes

def _corner_code(data):
    entries = data["entries"]
    marker_shape = data.get("marker_shape", "circle")
    marker_size = data.get("marker_size", "small")
    marker_fill = data.get("marker_fill", "solid")
    base_size = data.get("base_size", "large")
    cells = [
        {"items": [{"shape": entry["shape"], "size": base_size},
                  {"shape": marker_shape, "size": marker_size,
                   "fill": marker_fill, "at": entry["position"]}]}
        for entry in entries
    ]
    return {"kind": "nvr_grid", "data": {
        "cols": data.get("cols", len(entries)), "cells": cells,
        "alt": _alt(data, "Shapes, each with a mark in one corner"),
    }}


register(Template(
    id="nvr.corner_code", subtopic="Codes",
    summary="A grid of shapes, each carrying a small mark at a named corner as its code.",
    required=frozenset({"entries"}),
    optional=frozenset({"cols", "marker_shape", "marker_size", "marker_fill",
                        "base_size", "alt"}),
    build=_corner_code,
))


def _shape_to_symbol_grid(data):
    row_values, col_values = data["row_values"], data["col_values"]
    cells = []
    for row in row_values:
        for col in col_values:
            merged = dict(row)
            merged.update(col)
            cells.append(merged)
    blank = data.get("blank", len(cells) - 1)
    cells[blank] = None
    return {"kind": "nvr_grid", "data": {
        "cols": len(col_values), "cells": cells, "blank": blank,
        "alt": _alt(data, "A grid where shape and shading each follow their "
                          "own rule, with one cell missing"),
    }}


register(Template(
    id="nvr.shape_to_symbol_grid", subtopic="Codes",
    summary="A matrix crossing a row rule with a column rule, one cell blank.",
    required=frozenset({"row_values", "col_values"}),
    optional=frozenset({"blank", "alt"}),
    build=_shape_to_symbol_grid,
))


# --------------------------------------------------------------------------
# Odd One Out
#
# There is no stem — the options ARE the question — so, unlike every template
# above, these two build one OPTION at a time: `common` is the cell every
# option shares, and `field`/`value` is the one thing this option changes. An
# author still writes each option's `text`/`correct` by hand and repeats the
# same `common` into each one; what the template guarantees is that only the
# one named field actually differs, which is the one thing an odd-one-out
# question depends on.

def _odd_one_out(data):
    cell_spec = dict(data["common"])
    cell_spec[data["field"]] = data["value"]
    return {"kind": "nvr_panel", "data": {
        "cell": cell_spec, "alt": _alt(data, "One answer panel"),
    }}


register(Template(
    id="nvr.odd_one_out", subtopic="Odd One Out",
    summary="One option: a shared base cell with one named field overridden.",
    required=frozenset({"common", "field", "value"}),
    optional=frozenset({"alt"}),
    build=_odd_one_out,
))


def _odd_one_out_grid(data):
    items = [dict(item) for item in data["items"]]
    items[data["vary_index"]][data["field"]] = data["value"]
    return {"kind": "nvr_panel", "data": {
        "cell": {"items": items}, "alt": _alt(data, "One answer panel"),
    }}


register(Template(
    id="nvr.odd_one_out_grid", subtopic="Odd One Out",
    summary="One option: a shared multi-glyph cell with one item's field overridden.",
    required=frozenset({"items", "vary_index", "field", "value"}),
    optional=frozenset({"alt"}),
    build=_odd_one_out_grid,
))
