"""Odd-one-out category data.

Membership is irreducible knowledge -- no dictionary says a rowan is a tree and
a foxglove is not -- so CATEGORIES is hand-authored. What is NOT hand-authored,
and is the point of this module, is the FOILS.

The previous version listed three foils per category by hand, which capped the
subtopic at 8 x 3 = 24 facts and meant adding a category bought exactly three
questions. Here a foil is COMPUTED: any member of a neighbouring category that
is not a member of this one. Adding one category therefore yields foils for
every category it neighbours, and the yield grows with the square of the data
rather than with the length of a hand-typed list.

ADJACENT is what makes a foil good. The generator's original comment had it
right -- "ivy among trees rather than hammer" -- but encoded it by hand. A near
foil comes from a neighbouring category and needs a reason to reject; a far foil
comes from anywhere else and is obvious. That distinction is the difficulty axis
in verbal.py, and it is why ADJACENT is a graph rather than a flat list.
"""

# THE LABEL RULE. The explanation the pupil reads is "<members> are all <label>.
# <Foil> is not." -- so a category's label must read FALSE of every foil that
# category can draw. This is not a membership question and no assertion catches
# it; it is caught by reading the generated prose. `garments` was labelled
# "things worn on the body", which produced "anorak, blazer, cloak, shawl are
# all things worn on the body. Turban is not." A turban IS worn on the body, so
# the explanation asserted something untrue. Adjacent categories are exactly
# where this bites, because that is where the labels are closest.
#
# slug -> (display label, six members). Six so the generator can vary how many
# words it shows from 3 to 6 and get five genuinely different bands; the old
# data had four members in six of its eight categories and could not.
CATEGORIES = {
    "trees":        ("trees", ["oak", "birch", "willow", "beech", "sycamore", "rowan"]),
    "flowers":      ("garden flowers", ["daffodil", "tulip", "bluebell", "primrose", "foxglove", "snowdrop"]),
    "vegetables":   ("vegetables", ["carrot", "parsnip", "turnip", "cabbage", "leek", "swede"]),
    "fruit":        ("fruit", ["plum", "damson", "greengage", "apricot", "peach", "nectarine"]),
    "mammals":      ("mammals", ["otter", "badger", "hare", "fox", "stoat", "hedgehog"]),
    "birds":        ("birds", ["heron", "robin", "swallow", "kestrel", "wren", "curlew"]),
    "fish":         ("fish", ["trout", "salmon", "pike", "perch", "herring", "mackerel"]),
    "insects":      ("insects", ["beetle", "cricket", "moth", "wasp", "aphid", "earwig"]),
    "amphibians":   ("reptiles and amphibians", ["adder", "newt", "toad", "lizard", "frog", "slowworm"]),
    "cutlery":      ("cutlery", ["fork", "spoon", "knife", "ladle", "skewer", "tongs"]),
    "crockery":     ("crockery", ["saucer", "plate", "bowl", "mug", "teacup", "jug"]),
    "furniture":    ("furniture", ["wardrobe", "dresser", "bookcase", "stool", "bench", "sideboard"]),
    "dwellings":    ("places people live", ["cottage", "bungalow", "chalet", "cabin", "villa", "flat"]),
    "publicbuild":  ("public buildings", ["library", "museum", "chapel", "cinema", "hospital", "theatre"]),
    "farmbuild":    ("farm buildings", ["barn", "stable", "granary", "sty", "henhouse", "silo"]),
    "boats":        ("boats", ["canoe", "kayak", "punt", "dinghy", "yacht", "barge"]),
    "roadvehicles": ("road vehicles", ["lorry", "coach", "van", "tractor", "motorbike", "taxi"]),
    "aircraft":     ("aircraft", ["glider", "helicopter", "biplane", "airship", "jet", "seaplane"]),
    "precip":       ("kinds of rain and snow", ["drizzle", "sleet", "hail", "downpour", "shower", "snowfall"]),
    "winds":        ("kinds of wind", ["breeze", "gale", "gust", "squall", "draught", "whirlwind"]),
    "strings":      ("stringed instruments", ["violin", "cello", "viola", "harp", "guitar", "banjo"]),
    "windinst":     ("wind instruments", ["trumpet", "flute", "clarinet", "oboe", "bugle", "recorder"]),
    "percussion":   ("percussion instruments", ["drum", "cymbal", "tambourine", "triangle", "xylophone", "gong"]),
    "footwear":     ("footwear", ["sandal", "boot", "slipper", "clog", "plimsoll", "wellington"]),
    "headwear":     ("headwear", ["bonnet", "beret", "helmet", "turban", "cap", "balaclava"]),
    "garments":     ("clothes worn on the body rather than the head or feet", ["cloak", "anorak", "blazer", "cardigan", "jumper", "shawl"]),
    "handtools":    ("tools used at a workbench", ["hammer", "chisel", "spanner", "mallet", "pliers", "screwdriver"]),
    "gardentools":  ("garden tools", ["trowel", "rake", "hoe", "spade", "secateurs", "shears"]),
    "metals":       ("metals", ["copper", "bronze", "pewter", "zinc", "brass", "tin"]),
    "fabrics":      ("fabrics", ["velvet", "linen", "corduroy", "denim", "tweed", "satin"]),
}

# Categories grouped by domain. A FAR foil -- the obvious, low-band kind -- must
# come from a DIFFERENT domain. Two categories in the same domain that are not
# adjacent are simply never paired, which is what stops `plum` (fruit) being
# offered as the odd one out among trees: a plum is a tree. That whole class of
# defect is excluded by the structure rather than caught pair by pair.
DOMAINS = {
    "plants":     ["trees", "flowers", "vegetables", "fruit"],
    "animals":    ["mammals", "birds", "fish", "insects", "amphibians"],
    "household":  ["cutlery", "crockery", "furniture"],
    "buildings":  ["dwellings", "publicbuild", "farmbuild"],
    "transport":  ["boats", "roadvehicles", "aircraft"],
    "weather":    ["precip", "winds"],
    "music":      ["strings", "windinst", "percussion"],
    "clothing":   ["footwear", "headwear", "garments"],
    "tools":      ["handtools", "gardentools"],
    "materials":  ["metals", "fabrics"],
}

# Neighbouring categories: close enough that a member of one is a PLAUSIBLE but
# wrong answer for the other. Declared one way round and symmetrised on load.
ADJACENT = {
    "trees":       ["flowers", "vegetables"],
    "flowers":     ["vegetables"],
    "vegetables":  ["fruit"],
    "fruit":       ["flowers"],
    "mammals":     ["birds", "amphibians"],
    "birds":       ["insects", "amphibians"],
    "fish":        ["amphibians", "mammals"],
    "insects":     ["amphibians"],
    "cutlery":     ["crockery"],
    "crockery":    ["furniture"],
    "dwellings":   ["publicbuild", "farmbuild"],
    "publicbuild": ["farmbuild"],
    "boats":       ["roadvehicles", "aircraft"],
    "roadvehicles":["aircraft"],
    "precip":      ["winds"],
    "strings":     ["windinst", "percussion"],
    "windinst":    ["percussion"],
    "footwear":    ["headwear", "garments"],
    "headwear":    ["garments"],
    "handtools":   ["gardentools"],
    "metals":      ["fabrics"],
}

# (category, word) pairs where the word could be argued INTO the category, so it
# must never be that category's odd one out. This is the conservative direction:
# a pair listed here costs one fact; a pair MISSING from here ships a question
# with two defensible answers -- the `nightlight` class.
#
# An entry must name a word that is NOT already a member of the category, or it
# blocks nothing. `_build` asserts that, because the first draft of this list was
# almost entirely such no-ops: it recorded "this member is debatable" when the
# field means "this foil is unsafe".
#
# The `walnut` defect in the old data -- a walnut is botanically a drupe, so a
# fruit -- is excluded a second way too: no nut appears anywhere in CATEGORIES,
# so the pairing cannot arise.
AMBIGUOUS = {
    ("precip", "squall"),        # a squall brings rain, so it is arguably precipitation
    ("windinst", "brass"),       # brass IS a family of wind instruments
    ("handtools", "knife"),      # a craft knife is a workbench tool
    ("handtools", "skewer"),
    ("gardentools", "fork"),     # a garden fork
    ("gardentools", "knife"),    # a pruning knife
}

def _build():
    adj = {c: set() for c in CATEGORIES}
    for a, bs in ADJACENT.items():
        for b in bs:
            adj[a].add(b)
            adj[b].add(a)
    member_of = {}
    for slug, (_label, ms) in CATEGORIES.items():
        for w in ms:
            if w in member_of:
                raise AssertionError(f"{w!r} is in both {member_of[w]} and {slug}")
            member_of[w] = slug
    domain_of = {c: d for d, cs in DOMAINS.items() for c in cs}
    assert set(domain_of) == set(CATEGORIES), "every category needs a domain"
    for cat, word in AMBIGUOUS:
        assert cat in CATEGORIES, f"AMBIGUOUS names unknown category {cat!r}"
        if word in CATEGORIES[cat][1]:
            raise AssertionError(
                f"AMBIGUOUS ({cat!r}, {word!r}) is a no-op: {word!r} is already a "
                f"member of {cat!r}, so it could never be that category's foil")
    near, far = {}, {}
    for slug, (_label, ms) in CATEGORIES.items():
        own = set(ms)
        near[slug] = sorted(w for n in adj[slug] for w in CATEGORIES[n][1]
                            if w not in own and (slug, w) not in AMBIGUOUS)
        far[slug] = sorted(w for other, (_l, ws) in CATEGORIES.items()
                           if domain_of[other] != domain_of[slug]
                           for w in ws
                           if w not in own and (slug, w) not in AMBIGUOUS)
    return adj, member_of, near, far


ADJACENCY, MEMBER_OF, NEAR_FOILS, FAR_FOILS = _build()
