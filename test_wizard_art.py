"""
Checks the Word Wizard character in vocab/wizard_art.py.

Run:  python3 test_wizard_art.py

The point of the nine looks is that a child can SEE they have progressed, so
this checks that each rank really does look different, that the staff and
beard arrive in order, that every sprite has the named parts wizard.css
animates, and that a sprite stays small enough to be cheap on an iPad.

Stdlib only: wizard_art.py has no Django in it.
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocab"))

import wizard_art as w  # noqa: E402

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


SVG = "{http://www.w3.org/2000/svg}"
LEVELS = range(1, len(w.LOOKS) + 1)
PARTS = ["wc-all", "wc-staff", "wc-body", "wc-head", "wc-face", "wc-beard", "wc-eyes",
         "wc-eyes-sad", "wc-smile", "wc-frown", "wc-hat", "wc-arm", "wc-fx"]


def parse(level):
    return ET.fromstring(w.render(level).replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1))


def group(root, cls):
    return next((g for g in root.iter(f"{SVG}g") if g.get("class") == cls), None)


def fills(g):
    return {r.get("fill") for r in g.iter(f"{SVG}rect")} if g is not None else set()


print("== every look renders ==")
ck("nine looks, Apprentice to Grand Wizard",
   [l["rank"] for l in w.LOOKS] == ["Apprentice", "Spell Reader", "Charm Weaver", "Conjurer", "Enchanter",
                                    "Sorcerer", "Mage", "Archmage", "Grand Wizard"])
import re  # noqa: E402
_svc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocab", "services.py")).read()
_ranks = re.findall(r'"([A-Z][a-z]+(?: [A-Z][a-z]+)?)"', _svc[_svc.index("RANKS = ["):_svc.index("]", _svc.index("RANKS = ["))])
ck("the ranks match vocab.services.RANKS", _ranks == [l["rank"] for l in w.LOOKS], str(_ranks))
for level in LEVELS:
    root = parse(level)
    missing = [p for p in PARTS if group(root, p) is None]
    ck(f"level {level}: valid SVG with every animated part", not missing, str(missing))
    rects = list(root.iter(f"{SVG}rect"))
    ck(f"level {level}: under 600 squares (cheap to draw)", len(rects) < 600, str(len(rects)))
    out = [r for r in rects if not (0 <= int(r.get("x")) and int(r.get("x")) + int(r.get("width")) <= w.W
                                    and 0 <= int(r.get("y")) < w.H)]
    ck(f"level {level}: every square inside the grid", not out)
ck("levels past nine stay the Grand Wizard", w.render(12) == w.render(9))
ck("crisp pixels, not smoothed", 'shape-rendering="crispEdges"' in w.render(1))

print("\n== a child can see the progress ==")
robes = [l["robe"][0] for l in w.LOOKS]
ck("every rank has its own robe colour", len(set(robes)) == len(robes), str(robes))
ck("every rank looks different from the one before",
   all(w.render(n) != w.render(n + 1) for n in range(1, 9)))
staffs = [l["staff"] for l in w.LOOKS]
ck("Apprentice is empty-handed, Spell Reader gets a wand, then a staff",
   staffs[0] is None and staffs[1] == "wand" and all(s not in (None, "wand") for s in staffs[2:]), str(staffs))
order = ["wood", "gem", "orb", "star"]
tops = [order.index(s) for s in staffs[2:]]
ck("the staff only ever gets grander: wood, gem, orb, star", tops == sorted(tops) and tops[-1] == 3, str(staffs))
beards = [l["beard"][0] if l["beard"] else 0 for l in w.LOOKS]
ck("no beard at first, then it only grows", beards[0] == 0 and beards == sorted(beards) and beards[-1] > 10,
   str(beards))
heights = [l["hat_h"] for l in w.LOOKS]
ck("the hat only gets taller (after the Apprentice's cap)", heights[1:] == sorted(heights[1:]), str(heights))
ck("the staff group is empty for the Apprentice only",
   not fills(group(parse(1), "wc-staff")) and all(fills(group(parse(n), "wc-staff")) for n in range(2, 10)))
ck("every level but the first says what it unlocks",
   w.LOOKS[0]["new"] is None and all(l["new"] for l in w.LOOKS[1:]))

print("\n== the wrapper ==")
f = w.figure(3, pose="cast", size="lg")
ck("figure carries its pose and size classes", 'wiz-char--cast' in f and 'wiz-char--lg' in f)
ck("...and an accessible label naming the rank", 'role="img"' in f and 'a Charm Weaver' in f)
ck("the Grand Wizard glows", "wiz-char--grand" in w.figure(9) and "wiz-char--grand" not in w.figure(8))
ck("a locked look is a silhouette, without the glow",
   "wiz-char--locked" in w.figure(9, pose="locked") and "wiz-char--grand" not in w.figure(9, pose="locked"))
ck("a label is escaped", "&lt;b&gt;" in w.figure(1, label="<b>"))

if fails:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
print("\nRESULT: all checks passed.")
