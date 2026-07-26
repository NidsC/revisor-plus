"""
Non-verbal reasoning generators.

Follows the standard 11+ NVR types found in the research: series, rotation and
reflection, and nets/cubes. The figure carries both the question and the lettered
answer panels, exactly as a real paper does, so AnswerOption stays text ("A"–"D")
and no per-option images are needed.

The transformation is applied in code and the distractors are the specific wrong
transformations — rotated the wrong way, rotated by the wrong step, reflected
instead of rotated. So every distractor is a reason a pupil could be wrong,
rather than a shape that merely looks different.
"""
from . import Generator, Item, register

LETTERS = "ABCD"


def _lettered(rng, correct_spec, wrong_specs):
    """Place the correct panel among distractors, return (options, figure_options).

    Returns MCQ options as letters plus the panel specs in display order, so the
    figure and the answer key can never disagree.
    """
    panels = [correct_spec] + list(wrong_specs)[:3]
    order = list(range(len(panels)))
    rng.shuffle(order)
    shuffled = [panels[i] for i in order]
    correct_letter = LETTERS[order.index(0)]
    options = [(LETTERS[i], LETTERS[i] == correct_letter) for i in range(len(shuffled))]
    return options, shuffled, correct_letter


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
        start_dots = rng.randint(1, 2)

        def panel(i):
            spec = {"sides": sides, "rot": start_rot + i * step, "marker": 1}
            if dots_change:
                spec["dots"] = start_dots + i
            return spec

        sequence = [panel(i) for i in range(3)]
        correct = panel(3)
        wrong = [
            {**correct, "rot": start_rot + 2 * step},                   # repeated the last
            {**correct, "rot": start_rot + 3 * -step},                  # turned the wrong way
            {**correct, "sides": sides + 1 if sides < 6 else sides - 1},  # changed the shape
        ]
        if dots_change:
            wrong[0] = {**correct, "dots": start_dots + 2}              # forgot the second rule
        options, panels, letter = _lettered(rng, correct, wrong)
        rule = (f"the shape turns {abs(step)}° "
                f"{'clockwise' if step > 0 else 'anticlockwise'} each time"
                + (", and gains a dot" if dots_change else ""))
        return Item(
            stem="Which option comes next in the series?",
            options=options,
            difficulty=difficulty,
            params={"sides": sides, "step": step, "dots": dots_change,
                    "start": start_rot, "sd": start_dots},
            figure={"kind": "nvr_series", "data": {"sequence": sequence, "options": panels}},
            explanation=f"Reading the series, {rule}. That gives option {letter}.",
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
        sides = rng.choice([3, 4, 5, 6])
        base_rot = rng.choice([0, 15, 30, 45])
        turn, label = {
            1: (90, "a quarter turn clockwise"),
            2: (180, "a half turn"),
            3: (-90, "a quarter turn anticlockwise"),
            4: (180, "a half turn"),
            5: (-90, "a quarter turn anticlockwise"),
        }[difficulty]
        shape = {"sides": sides, "rot": base_rot, "marker": 1,
                 "shaded": difficulty >= 4}
        correct = {**shape, "rot": base_rot + turn}
        wrong = [
            {**shape, "rot": base_rot - turn},          # turned the wrong way
            {**shape, "rot": base_rot},                 # did not turn at all
            {**shape, "rot": base_rot + turn + 45},     # over-turned
        ]
        options, panels, letter = _lettered(rng, correct, wrong)
        return Item(
            stem=f"The shape on the left is given {label}. Which option shows the result?",
            options=options,
            difficulty=difficulty,
            params={"sides": sides, "base": base_rot, "turn": turn},
            figure={"kind": "nvr_rotation", "data": {"shape": shape, "options": panels}},
            explanation=(f"Follow the dot: after {label} it moves to the position "
                         f"shown in option {letter}."),
            misconceptions={letter: ""},
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
        wrong = rng.sample(pool, 3)
        options, panels, letter = _lettered(rng, valid, wrong)
        return Item(
            stem="Which of these nets folds up to make a cube?",
            options=options,
            difficulty=difficulty,
            params={"valid": valid, "wrong": [tuple(map(tuple, w)) for w in wrong]},
            figure={"kind": "nvr_net", "data": {"nets": panels}},
            explanation=(f"Option {letter} is a strip of four faces with one face "
                         f"above and one below — that always folds into a cube. The "
                         f"others leave a face missing or overlapping."),
        )
