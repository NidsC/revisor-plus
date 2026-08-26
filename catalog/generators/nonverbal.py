"""
Non-verbal reasoning generators.

Follows the standard 11+ NVR types found in the research: series, rotation and
reflection, and nets/cubes.

The transformation is applied in code and the distractors are the specific wrong
transformations — rotated the wrong way, rotated by the wrong step, reflected
instead of rotated. So every distractor is a reason a pupil could be wrong,
rather than a shape that merely looks different.

**Each answer now carries its own picture.** These generators used to draw the
lettered answer panels *inside* the stem figure and hand back options holding the
bare letters "A".."D", because `AnswerOption` was text-only and a visual multiple
choice would have needed per-option images. That worked, but it made the drawing
and the answer key two lists held in the same order by hand — which is why
`_lettered()` existed, and why its docstring had to promise they "can never
disagree". `AnswerOption.figure` removes the promise by removing the second list.

`text` is still set on every option, and carries the panel in words. For this
section that is a best-effort description rather than a true equivalent: a
non-verbal question asks a pupil to see a relationship between shapes, and no
sentence makes that available to someone who cannot see them. It is worth
setting anyway — it is what the review screens print, what a pupil gets if a
figure fails to draw, and what tells an author at review time that two options
are the same picture.
"""
from . import Generator, Item, register

SIDED_SHAPES = {3: "triangle", 4: "square", 5: "pentagon", 6: "hexagon"}

# Rotation questions use outlines with no mirror symmetry. That is not a style
# choice: reflecting a mirror-symmetric shape gives the same picture as some
# rotation of it, so a reflection distractor there is one of the rotation answers
# with a different letter on it. An asymmetric outline is what makes "reflected"
# and "turned" tell apart — and the subtopic is called Rotation & Reflection.
from catalog.figures.glyphs import CHIRAL as ASYMMETRIC  # noqa: E402


def _cell(shape, rot=0, fill="none", dots=0, marker=False, flip=None):
    """One panel's contents in the vocabulary of catalog/figures/glyphs.py."""
    head = {"shape": shape, "rot": rot % 360, "fill": fill, "size": "medium"}
    if marker:
        head["marker"] = 1
    if flip:
        head["flip"] = flip
    if not dots:
        return head
    # The count of small circles along the bottom of the panel — the second rule
    # a harder series question layers on top of the rotation. `repeat` rather
    # than one glyph per position: the fixed three-position version silently drew
    # a 4-dot panel as 3 dots, which made two different answers the same picture.
    #
    # The shape moves to the top of the panel to make room. Left centred it
    # overlapped the dot row, and a rotating shape crossing the marks the pupil
    # is meant to count is a question about two rules made harder to read for no
    # reason.
    head["at"] = "top"
    return {"items": [head, {"shape": "circle", "size": "tiny", "fill": "solid",
                             "at": "bottom", "repeat": dots}]}


def _describe(cell):
    """The panel in words, precisely enough that two different pictures never
    describe the same. `generate_bank` rejects a question whose options repeat a
    description, so this is also the last line of defence against shipping four
    answers of which two are identical."""
    items = cell.get("items", [cell])
    head = items[0]
    parts = [head.get("shape", "shape").replace("_", " ")]
    if head.get("flip"):
        parts.append(f"reflected {head['flip']}ly")
    rotation = head.get("rot", 0) % 360
    if rotation:
        parts.append(f"turned {rotation}°")
    if head.get("fill", "none") != "none":
        parts.append(f"{head['fill'].replace('_', ' ')} shading")
    for extra in items[1:]:
        count = extra.get("repeat", 1)
        parts.append(f"{count} dot{'s' if count > 1 else ''}")
    if head.get("marker"):
        parts.append("with a corner mark")
    return ", ".join(parts)


def _describe_net(squares):
    """A net in words, row by row.

    Dry, deliberately. A pupil has to fold this in their head, so an evocative
    description ("a cross shape") would be less useful than an exact one, and
    two nets that differ by a single square must not describe the same.
    """
    rows = {}
    for row, column in squares:
        rows.setdefault(row, []).append(column)
    lines = []
    for row in sorted(rows):
        columns = sorted(rows[row])
        where = ", ".join(str(c + 1) for c in columns)
        lines.append(f"{len(columns)} at position{'s' if len(columns) > 1 else ''} {where}")
    return "; ".join(lines)


def _answers(rng, correct, pool, describe, figure_of, drawn):
    """Shuffle the correct answer among three distractors that are genuinely
    different pictures from it and from each other.

    `pool` is candidate distractors in priority order, and the first three that
    draw differently are used. Distinctness is decided by **what the option
    actually draws**, not by the parameters it was built from — those are not the
    same test. Two examples this build hit, both of which produced four answers
    of which two were the same picture and only one was marked right:

      * a half turn. `base - 180` and `base + 180` are the same angle, so the
        turned-the-wrong-way distractor was the correct answer.
      * a series whose rule adds a dot, where the panel could hold only three.
        A 4-dot answer and a 3-dot answer drew the same panel.

    Neither was visible before, because these generators used to hand back
    options holding the bare letters "A".."D". Letters are always distinct, so
    `generate_bank`'s duplicate-option check could not fire however identical the
    pictures were. Returns None if the pool cannot supply three, which drops the
    question rather than shipping an unanswerable one.
    """
    chosen, seen = [], {drawn(correct)}
    for candidate in pool:
        mark = drawn(candidate)
        if mark in seen:
            continue
        seen.add(mark)
        chosen.append(candidate)
        if len(chosen) == 3:
            break
    if len(chosen) < 3:
        return None, None
    candidates = [correct] + chosen
    order = list(range(len(candidates)))
    rng.shuffle(order)
    options = [(describe(candidates[i]), i == 0, figure_of(candidates[i]))
               for i in order]
    return options, describe(correct)


def _panel_figure(cell):
    return {"kind": "nvr_panel", "data": {"cell": cell}}


def _net_figure(squares):
    return {"kind": "nvr_net", "data": {"squares": [list(s) for s in squares]}}


def _drawn_cell(cell):
    """What this cell actually draws, as a string, for comparing two options.

    The drawing itself is the identity, which is the only comparison that
    answers the question being asked — "would a pupil see two identical
    panels?". Comparing the specs would not: `rot: 180` and `rot: -180` are
    different specs and the same picture.
    """
    from catalog.figures.glyphs import cell_markup
    from catalog.figures.layout import CELL
    return cell_markup(cell, CELL)


def _drawn_net(squares):
    """The same test for nets: two nets are the same answer if, once each is
    shifted to the origin, they occupy the same squares. A net translated by one
    column is the same net and must not appear twice."""
    rows = [int(r) for r, _ in squares]
    columns = [int(c) for _, c in squares]
    top, left = min(rows), min(columns)
    return repr(sorted((int(r) - top, int(c) - left) for r, c in squares))


@register
class ShapeSeries(Generator):
    slug = "nvr.series"
    section, subtopic = "NVR", "Series & Sequences"
    template_id = "rotating-series"

    def build(self, rng, difficulty):
        # DIFFICULTY: a single changing attribute first (rotation), then two at
        # once (rotation plus a dot count), then a larger step that is harder to
        # read off. Two simultaneous rules is the real jump.
        sides = rng.choice([3, 4, 5, 6])
        step = {1: 90, 2: 45, 3: 90, 4: 60, 5: 135}[difficulty]
        direction = 1 if difficulty <= 2 or rng.random() < 0.5 else -1
        step *= direction
        dots_change = difficulty >= 3
        start_rot = rng.choice([0, 30, 45])
        # Starts at one. The series runs four panels and a distractor goes one
        # step further, so a start of two would ask for six marks — past what a
        # panel holds at a constant size (glyphs.MAX_REPEAT).
        start_dots = 1

        shape = SIDED_SHAPES[sides]
        other = SIDED_SHAPES[sides + 1 if sides < 6 else sides - 1]

        def at(index, dots_offset=0, override_shape=None):
            return _cell(override_shape or shape,
                         rot=start_rot + index * step, marker=True,
                         dots=start_dots + index + dots_offset if dots_change else 0)

        sequence = [at(i) for i in range(3)]
        correct = at(3)
        # Candidates in priority order; `_answers` takes the first three that
        # draw differently from the key and from each other. Offering more than
        # three is what lets it stay correct at every difficulty: at a 180-degree
        # step, "turned the wrong way" IS the answer, and the pool moves on.
        pool = [
            at(2, dots_offset=1),            # repeated the last panel's turn
            _cell(shape, rot=start_rot - 3 * step, marker=True,
                  dots=start_dots + 3 if dots_change else 0),  # turned the wrong way
            at(3, dots_offset=-1),           # right turn, forgot the dot rule
            at(3, override_shape=other),     # right turn, wrong shape
            at(4),                           # one step too far
        ]
        options, correct_text = _answers(rng, correct, pool, _describe,
                                         _panel_figure, _drawn_cell)
        if options is None:
            return None
        rule = (f"the shape turns {abs(step)}° "
                f"{'clockwise' if step > 0 else 'anticlockwise'} each time"
                + (", and gains a dot" if dots_change else ""))
        return Item(
            stem="Which option comes next in the series?",
            options=options,
            difficulty=difficulty,
            params={"sides": sides, "step": step, "dots": dots_change,
                    "start": start_rot, "sd": start_dots},
            # The stem is the sequence with the blank the pupil fills. The
            # answer panels are no longer part of it.
            figure={"kind": "nvr_grid",
                    "data": {"cells": sequence + [None], "blank": len(sequence),
                             "alt": "A series of shapes with the last one missing"}},
            explanation=f"Reading the series, {rule}. That gives {correct_text}.",
        )


@register
class RotationReflection(Generator):
    slug = "nvr.rotation"
    section, subtopic = "NVR", "Rotation & Reflection"
    template_id = "apply-transformation"

    def build(self, rng, difficulty):
        # DIFFICULTY: a quarter turn is read off directly; a half turn and a
        # reflection are the ones pupils confuse, because for a symmetric shape
        # they can look the same — which is why every shape carries a marker.
        outline = rng.choice(ASYMMETRIC)
        base_rot = rng.choice([0, 15, 30, 45])
        turn, label = {
            1: (90, "a quarter turn clockwise"),
            2: (180, "a half turn"),
            3: (-90, "a quarter turn anticlockwise"),
            4: (180, "a half turn"),
            5: (-90, "a quarter turn anticlockwise"),
        }[difficulty]
        fill = "half" if difficulty >= 4 else "none"

        def cell(rot, flip=None):
            return _cell(outline, rot=rot, marker=True, fill=fill, flip=flip)

        shape = cell(base_rot)
        correct = cell(base_rot + turn)
        # Reflections are in the pool because they are the mistake this subtopic
        # is named for, and because they are what remains distinguishable when
        # the turn is 180 degrees and turning the wrong way gives the answer.
        pool = [
            cell(base_rot - turn),                        # turned the wrong way
            cell(base_rot, flip="horizontal"),            # reflected, not turned
            cell(base_rot),                               # did not turn at all
            cell(base_rot + turn, flip="horizontal"),     # turned and reflected
            cell(base_rot + turn + 45),                   # over-turned
            cell(base_rot + turn - 45),                   # under-turned
        ]
        options, correct_text = _answers(rng, correct, pool, _describe,
                                         _panel_figure, _drawn_cell)
        if options is None:
            return None
        return Item(
            stem=f"The shape on the left is given {label}. Which option shows the result?",
            options=options,
            difficulty=difficulty,
            params={"outline": outline, "base": base_rot, "turn": turn,
                    "fill": fill},
            figure={"kind": "nvr_grid",
                    "data": {"cells": [shape],
                             "alt": "The shape before the transformation"}},
            explanation=(f"Follow the corner mark: after {label} it lands where "
                         f"{correct_text} shows it."),
            misconceptions={correct_text: ""},
        )


# Cube nets. The 1-4-1 family is used for the valid cases: a strip of four with
# one square attached above and one below folds into a cube wherever those two
# flaps sit, so every generated "valid" net is verifiably valid without needing a
# folding simulation. The invalid cases are well-known non-nets.
def _strip_net(above_col, below_col):
    return [(1, 0), (1, 1), (1, 2), (1, 3), (0, above_col), (2, below_col)]


INVALID_NETS = [
    [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)],           # 2x3 rectangle
    [(1, 0), (1, 1), (1, 2), (1, 3), (0, 1), (0, 2)],           # 4 in a row + 2 adjacent above
    [(0, 1), (1, 1), (2, 1), (3, 1), (0, 0), (0, 2)],           # T with both flaps at the top
    [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (1, 1)],           # 4+2 stacked on one side
    [(0, 0), (0, 1), (1, 1), (1, 2), (2, 2), (2, 3)],           # staircase
]


@register
class CubeNets(Generator):
    slug = "nvr.nets"
    section, subtopic = "NVR", "3D Shapes & Nets"
    template_id = "which-net-folds"

    def build(self, rng, difficulty):
        # DIFFICULTY: how near-miss the wrong nets are. At the easy end the
        # distractors are obviously wrong (a 2x3 block); at the hard end they are
        # 1-4-1-like arrangements that only fail on closer inspection.
        valid = _strip_net(rng.randrange(4), rng.randrange(4))
        pool = INVALID_NETS[:2] if difficulty <= 2 else INVALID_NETS[1:]
        if len(pool) < 3:
            pool = INVALID_NETS
        wrong = rng.sample(pool, min(3, len(pool))) + [n for n in INVALID_NETS
                                                       if n not in pool]
        options, correct_text = _answers(rng, valid, wrong, _describe_net,
                                         _net_figure, _drawn_net)
        if options is None:
            return None
        return Item(
            stem="Which of these nets folds up to make a cube?",
            options=options,
            difficulty=difficulty,
            params={"valid": valid, "wrong": [tuple(map(tuple, w)) for w in wrong]},
            # No stem figure: the four nets ARE the question, and each one is now
            # its own option rather than a lettered panel inside a shared drawing.
            figure=None,
            explanation=("The one that folds is a strip of four faces with one "
                         "face above and one below — that always makes a cube. "
                         "The others leave a face missing or overlapping."),
        )
