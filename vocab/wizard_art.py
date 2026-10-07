"""
The Word Wizard himself: a flat pixel-art character, drawn in code as inline SVG.

One drawing, nine looks. Each level (rank) changes what a child can see:
robe colour, hat (a soft cap, then a pointed hat that grows taller and
gathers a band, stars and a moon), beard (none, then brown, grey and white,
growing longer) and what he carries (nothing, a wand, then a staff topped
with wood, a gem, a crystal orb and finally a gold star). LOOKS below is the
whole table, and `new` says in words what each level adds.

The SVG is solid 1x1 squares on a 32x40 grid (merged into runs, so a sprite
is a couple of hundred <rect>s), outlined automatically. It is split into
named groups so that CSS alone can animate him — static/vocab/wizard.css
moves .wc-arm to cast, .wc-head to slump, .wc-eyes to blink, swaps
.wc-smile/.wc-frown and .wc-eyes/.wc-eyes-sad, and lights .wc-fx. Every
transform there uses the view box as its frame, so the pivots below are in
grid units.

No image files and no library: render(level) returns markup, cached, and the
templates put it in the page with {% wizard %} (vocab/templatetags).
"""
from functools import lru_cache
from html import escape

W, H = 32, 40

INK = "#1d1633"
SKIN, BLUSH = "#f4c7a1", "#ef9a9a"
MOUTH = "#8e3b46"
BOOT = "#3a2a22"
BELT = "#3a2a22"
WOOD, WOOD_SH = "#9a6a3a", "#6e4824"
GOLD, GOLD_SH = "#f5b623", "#c98a0c"
SILVER = "#d6dcea"
WHITE = "#ffffff"

BROWN_BEARD = ("#7a4e2d", "#5b3920")
GREY_BEARD = ("#bdb7ad", "#9a948a")
WHITE_BEARD = ("#f3f0ea", "#cfc9bd")

# One look per level. Level 9 and beyond are the Grand Wizard.
#   robe: (main, shade)   hat: "cap" | "cone"   hat_h: cone height in pixels
#   band: hat band colour or None   hat_stars: gold stars on the hat
#   trim: robe hem and front colour or None   robe_stars: stars on the robe
#   beard: (rows, (colour, shade)) or None   staff: what he carries
LOOKS = [
    dict(rank="Apprentice", robe=("#8d6e52", "#6d543d"), hat="cap", hat_h=0, band=None,
         hat_stars=0, moon=False, big_star=False, trim=None, robe_stars=False, beard=None,
         staff=None, gem=None, new=None),
    dict(rank="Spell Reader", robe=("#3f9d5a", "#2f7a45"), hat="cone", hat_h=8, band="#2f7a45",
         hat_stars=0, moon=False, big_star=False, trim=None, robe_stars=False, beard=None,
         staff="wand", gem=None, new="a pointed hat, a green robe and a wand"),
    dict(rank="Charm Weaver", robe=("#2b9aa0", "#1f767b"), hat="cone", hat_h=9, band=WOOD,
         hat_stars=0, moon=False, big_star=False, trim=None, robe_stars=False, beard=None,
         staff="wood", gem=None, new="a teal robe, a taller hat and a wooden staff"),
    dict(rank="Conjurer", robe=("#3b6fd8", "#2c54a8"), hat="cone", hat_h=10, band=GOLD,
         hat_stars=2, moon=False, big_star=False, trim=None, robe_stars=False,
         beard=(3, BROWN_BEARD), staff="wood", gem=None,
         new="a blue robe, a starry hat and a beard"),
    dict(rank="Enchanter", robe=("#7c4ddb", "#5f36b0"), hat="cone", hat_h=10, band=GOLD,
         hat_stars=2, moon=False, big_star=False, trim=GOLD, robe_stars=False,
         beard=(4, BROWN_BEARD), staff="gem", gem=("#3fd0e0", "#bdf4fa"),
         new="a purple robe with a gold hem, and a staff with a gem"),
    dict(rank="Sorcerer", robe=("#c8414b", "#9c2f37"), hat="cone", hat_h=11, band=GOLD,
         hat_stars=3, moon=False, big_star=False, trim=GOLD, robe_stars=False,
         beard=(6, GREY_BEARD), staff="gem", gem=("#e0315a", "#ffb3c4"),
         new="a crimson robe, a grey beard and a ruby staff"),
    dict(rank="Mage", robe=("#3d3a9e", "#2c2a78"), hat="cone", hat_h=11, band=GOLD,
         hat_stars=3, moon=False, big_star=False, trim=GOLD, robe_stars=True,
         beard=(7, GREY_BEARD), staff="orb", gem=("#7fd8ff", "#e6f8ff"),
         new="an indigo robe covered in stars, and a crystal orb staff"),
    dict(rank="Archmage", robe=("#252a5c", "#181c42"), hat="cone", hat_h=12, band=SILVER,
         hat_stars=3, moon=True, big_star=False, trim=SILVER, robe_stars=True,
         beard=(10, WHITE_BEARD), staff="orb", gem=("#b48cff", "#efe4ff"),
         new="a midnight robe with silver trim, a moon on your hat and a long white beard"),
    dict(rank="Grand Wizard", robe=("#5b2a86", "#43206a"), hat="cone", hat_h=12, band=GOLD,
         hat_stars=2, moon=False, big_star=True, trim=GOLD, robe_stars=True,
         beard=(13, WHITE_BEARD), staff="star", gem=None,
         new="royal robes, the tallest hat of all and the golden star staff"),
]


def look_for(level):
    """The look for a level: 1 is the first entry, 9 and beyond the last."""
    return LOOKS[max(1, min(level, len(LOOKS))) - 1]


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------

class Sprite:
    """Named layers of pixels, drawn in order."""

    ORDER = ["staff", "body", "face", "beard", "eyes", "eyes_sad", "smile", "frown", "hat", "arm", "fx"]

    def __init__(self):
        self.layers = {name: {} for name in self.ORDER}

    def put(self, layer, x, y, colour):
        if 0 <= x < W and 0 <= y < H:
            self.layers[layer][(x, y)] = colour

    def outline(self, layer, colour=INK):
        """Ink every empty pixel that touches the layer's shape."""
        filled = set(self.layers[layer])
        for (x, y) in list(filled):
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in filled:
                    self.put(layer, nx, ny, colour)

    def block(self, layer, x0, y0, rows, palette):
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch != ".":
                    self.put(layer, x0 + dx, y0 + dy, palette[ch])


def _body(s, look):
    main, shade = look["robe"]
    trim = look["trim"]
    for y in range(19, 36):
        half = 3 + int((y - 19) * 0.45)
        left, right = 16 - half, 15 + half
        for x in range(left, right + 1):
            colour = shade if x > right - max(2, half // 3) else main
            if trim and (y >= 34 or (y >= 23 and x in (15, 16))):
                colour = trim
            if y == 24:
                colour = GOLD if trim else BELT
            s.put("body", x, y, colour)
    if look["robe_stars"]:
        for x, y in ((10, 30), (19, 28), (13, 33), (21, 32), (12, 26)):
            s.put("body", x, y, GOLD)
    for x0 in (10, 17):                                   # boots
        for y in (36, 37):
            for x in range(x0, x0 + 5):
                s.put("body", x, y, BOOT)
    for y in range(20, 25):                               # right sleeve, reaching out
        for x in range(19 + (y - 20) // 2, 23 + (y - 20) // 2):
            s.put("body", x, y, shade)
    s.outline("body")
    for x, y in ((25, 23), (26, 23), (25, 24), (26, 24)):  # right hand, over the outline
        s.put("body", x, y, SKIN)


def _arm(s, look):
    """The casting arm: hangs at his side, rotated up by CSS to cast."""
    main, _ = look["robe"]
    for y in range(20, 27):
        for x in range(10 - (y - 20) // 2, 13 - (y - 20) // 2):
            s.put("arm", x, y, main)
    for x, y in ((7, 27), (8, 27), (7, 28), (8, 28)):
        s.put("arm", x, y, SKIN)
    s.outline("arm")


FACE = [
    ".KKKKKKKK.",
    "KSSSSSSSSK",
    "KSSSSSSSSK",
    "KSSSSSSSSK",
    "KPSSSSSSPK",
    ".KSSSSSSK.",
    "..KKKKKK..",
]


def _face(s):
    s.block("face", 11, 13, FACE, {"K": INK, "S": SKIN, "P": BLUSH})
    for x in (14, 17):
        s.put("eyes", x, 15, INK)
        s.put("eyes", x, 16, INK)
    for x in (13, 14, 17, 18):                            # closed, downcast
        s.put("eyes_sad", x, 16, INK)
    for x, y in ((14, 17), (17, 17), (15, 18), (16, 18)):
        s.put("smile", x, y, MOUTH)
    for x, y in ((15, 17), (16, 17), (14, 18), (17, 18)):
        s.put("frown", x, y, MOUTH)


def _beard(s, look):
    if not look["beard"]:
        return
    rows, (colour, shade) = look["beard"]
    for y in range(17, 18 + rows):
        half = max(1, 4 - (y - 18) // 2) if rows > 4 else max(1, 4 - (y - 17))
        for x in range(16 - half, 16 + half):
            s.put("beard", x, y, shade if x == 15 + half else colour)
    s.outline("beard", shade)


def _hat(s, look):
    main, shade = look["robe"]
    band = look["band"] or shade
    if look["hat"] == "cap":
        for y, (left, right) in zip(range(7, 13), ((14, 17), (12, 19), (11, 20), (10, 21), (10, 21), (10, 21))):
            for x in range(left, right + 1):
                s.put("hat", x, y, shade if x > right - 2 else main)
        for x in range(9, 23):
            s.put("hat", x, 13, shade)
        s.put("hat", 15, 6, GOLD)                         # a pom-pom
        s.put("hat", 16, 6, GOLD)
    else:
        tip = 12 - look["hat_h"]
        for y in range(tip, 12):
            frac = (y - tip) / max(1, 11 - tip)
            half = 0.5 + frac * 5.5
            lean = round((1 - frac) ** 2 * 3)
            left, right = round(15.5 - half) + lean, round(15.5 + half) - 1 + lean
            for x in range(left, right + 1):
                s.put("hat", x, y, shade if x >= right - max(0, int(half) // 2) else main)
        for x in range(10, 22):
            s.put("hat", x, 12, band)
        for x in range(8, 24):
            s.put("hat", x, 13, shade)
        cone = {p for p, c in s.layers["hat"].items() if p[1] < 12}
        spots = [(14, 9), (16, 7), (13, 10), (17, 10)]
        for x, y in spots[: look["hat_stars"]]:
            if (x, y) in cone:
                s.put("hat", x, y, GOLD)
        if look["moon"]:
            for x, y in ((15, 8), (14, 9), (14, 10), (15, 11)):
                if (x, y) in cone:
                    s.put("hat", x, y, SILVER)
        if look["big_star"]:
            for x, y in ((15, 7), (14, 8), (15, 8), (16, 8), (15, 9)):
                if (x, y) in cone:
                    s.put("hat", x, y, GOLD)
    s.outline("hat")


def _staff(s, look):
    kind = look["staff"]
    if kind is None:
        return
    if kind == "wand":
        for y in range(17, 25):
            s.put("staff", 27, y, WOOD)
        s.put("staff", 27, 16, GOLD)
        s.outline("staff")
        return
    top = {"wood": 10, "gem": 9, "orb": 9, "star": 9}[kind]
    for y in range(top, 38):
        s.put("staff", 26, y, WOOD)
        s.put("staff", 27, y, WOOD_SH)
    if kind == "wood":
        for x, y in ((25, 8), (26, 8), (27, 8), (28, 8), (25, 9), (28, 9), (25, 10)):
            s.put("staff", x, y, WOOD)
    elif kind == "gem":
        gem, light = look["gem"]
        for x in (25, 28):
            s.put("staff", x, 8, GOLD)
        for y, xs in ((4, (26, 27)), (5, (25, 26, 27, 28)), (6, (25, 26, 27, 28)), (7, (26, 27))):
            for x in xs:
                s.put("staff", x, y, gem)
        s.put("staff", 26, 5, light)
    elif kind == "orb":
        gem, light = look["gem"]
        for x in range(25, 29):
            s.put("staff", x, 9, GOLD)
        for y, (a, b) in ((3, (26, 27)), (4, (25, 28)), (5, (24, 29)), (6, (24, 29)), (7, (25, 28)), (8, (26, 27))):
            for x in range(a, b + 1):
                s.put("staff", x, y, gem)
        s.put("staff", 25, 4, light)
        s.put("staff", 25, 5, light)
    elif kind == "star":
        for y, xs in ((2, (26, 27)), (3, (26, 27)), (4, range(23, 31)), (5, range(24, 30)),
                      (6, range(25, 29)), (7, (24, 25, 28, 29)), (8, (23, 24, 29, 30))):
            for x in xs:
                s.put("staff", x, y, GOLD)
        for x in range(25, 29):
            s.put("staff", x, 9, GOLD_SH)
    s.outline("staff")


def _fx(look):
    """Sparkle centres: round the raised hand, and the staff's tip if he has one."""
    spots = [(5, 10), (9, 7), (3, 14)]
    if look["staff"] in ("wood", "gem", "orb", "star"):
        spots += [(23, 2), (30, 5), (29, 0)]
    elif look["staff"] == "wand":
        spots += [(29, 14), (25, 13)]
    return spots


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------

def _rects(pixels):
    """Pixels as <rect>s, merged into horizontal runs of one colour."""
    out = []
    rows = {}
    for (x, y), c in pixels.items():
        rows.setdefault(y, []).append((x, c))
    for y in sorted(rows):
        run_x, run_c, run_n = None, None, 0
        for x, c in sorted(rows[y]) + [(None, None)]:
            if run_c is not None and x == run_x + run_n and c == run_c:
                run_n += 1
                continue
            if run_c is not None:
                out.append(f'<rect x="{run_x}" y="{y}" width="{run_n}" height="1" fill="{run_c}"/>')
            run_x, run_c, run_n = x, c, 1
    return "".join(out)


def _spark(x, y, i):
    """A four-point sparkle centred on (x, y)."""
    px = [(x, y, WHITE), (x - 1, y, GOLD), (x + 1, y, GOLD), (x, y - 1, GOLD), (x, y + 1, GOLD)]
    rects = "".join(f'<rect x="{a}" y="{b}" width="1" height="1" fill="{c}"/>'
                    for a, b, c in px if 0 <= a < W and 0 <= b < H)
    return f'<g class="wc-spark" style="--i:{i}">{rects}</g>'


@lru_cache(maxsize=None)
def render(level):
    """The wizard's SVG for a level, as a markup string."""
    look = look_for(level)
    s = Sprite()
    _staff(s, look)
    _body(s, look)
    _face(s)
    _beard(s, look)
    _hat(s, look)
    _arm(s, look)
    g = {name: _rects(px) for name, px in s.layers.items()}
    sparks = "".join(_spark(x, y, i) for i, (x, y) in enumerate(_fx(look)))
    lvl = max(1, min(level, len(LOOKS)))
    return (
        f'<svg class="wc wc--lv{lvl}" viewBox="-2 -2 {W + 4} {H + 3}" shape-rendering="crispEdges" '
        f'aria-hidden="true" focusable="false"><g class="wc-all">'
        f'<g class="wc-staff">{g["staff"]}</g><g class="wc-body">{g["body"]}</g>'
        f'<g class="wc-head"><g class="wc-face">{g["face"]}</g><g class="wc-beard">{g["beard"]}</g>'
        f'<g class="wc-eyes">{g["eyes"]}</g><g class="wc-eyes-sad">{g["eyes_sad"]}</g>'
        f'<g class="wc-smile">{g["smile"]}</g><g class="wc-frown">{g["frown"]}</g>'
        f'<g class="wc-hat">{g["hat"]}</g></g>'
        f'<g class="wc-arm">{g["arm"]}</g><g class="wc-fx">{sparks}</g>'
        f'</g></svg>'
    )


def figure(level, pose="idle", size="md", label=None):
    """render(level) wrapped in its pose and size, labelled for screen readers."""
    look = look_for(level)
    text = escape(label or f"Your wizard, a {look['rank']}")
    grand = " wiz-char--grand" if look is LOOKS[-1] and pose != "locked" else ""
    if pose == "locked":            # a dark silhouette: the next look, not yet earned
        pose = "idle wiz-char--locked"
    return (f'<span class="wiz-char wiz-char--{pose} wiz-char--{size}{grand}" role="img" '
            f'aria-label="{text}">{render(level)}</span>')
