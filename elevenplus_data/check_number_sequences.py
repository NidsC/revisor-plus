#!/usr/bin/env python3
"""
Independent checks on the Number Sequences pack (contrib_prash_vr_17.json).

    python3 elevenplus_data/check_number_sequences.py elevenplus_data/contrib_prash_vr_17.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator. Every answer is re-derived from the numbers
printed in the stem, by fitting rules to them from scratch — which is the only
way to catch the fault that matters here, a row of numbers that two different
rules both explain and then disagree about.

  * ALL FIVE FAMILIES ARE RE-FITTED to every stem: constant difference,
    changing difference, multiplicative (including division), two-step
    (multiply then subtract), and two interleaved sequences. Each is fitted
    from the printed terms alone, under the parameter limits the subtopic
    actually uses, and every family that fits ALL the shown terms then predicts
    the next one.
      - At least one family must fit, or the row is not a sequence question.
      - **Every family that fits must predict the SAME next number.** Two
        fitting families that disagree means two defensible answers, and the
        question fails. Strictly, any number continues some rule; this is what
        turns "the simplest reading" from an assertion into a test.
      - The key must be that agreed number.
  * THE BAND LABEL IS CHECKED AGAINST THE RULE, not trusted: band 1 and 2 are
    constant differences (1 with small positive steps, 2 with larger or
    negative ones), band 3 a changing difference, band 4 multiplicative or
    two-step, band 5 two interleaved sequences. A rule in the wrong band is a
    mislabelled difficulty, which the adaptive engine reads as fact.
  * NOTHING GOES BELOW ZERO. A descending row is a real paper shape only while
    it stops at zero — the one real example seen runs 100, 90, _, 40, 0. Every
    printed term and the answer are re-checked against that here rather than
    being assumed from the generator's own guard.
  * DISTRACTORS: all numeric, none equal to the key, and the one misconception
    slug this pack uses is verified to sit exactly on the options that repeat
    the last number shown — no more, no fewer.
  * plus: unique stems and refs, `numeric` questions carrying an integer answer
    and no options, explanations stating the answer, and answer positions
    neither clustered nor cyclic nor in a run of four.

No dictionary and no third-party module: this checker runs anywhere.
"""
import collections
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_17.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

STEM = re.compile(r"^(-?\d+(?:, -?\d+)+), ___$")
BAND_RULE = {1: {"constant"}, 2: {"constant"}, 3: {"changing"},
             4: {"multiplicative", "two-step"}, 5: {"alternating"}}
TYPE_OF = {"constant": "constant-difference", "changing": "changing-difference",
           "multiplicative": "multiplicative", "two-step": "two-step-rule",
           "alternating": "alternating"}


def fit_constant(t):
    """A fixed step, fitted to every printed term."""
    step = t[1] - t[0]
    if all(b - a == step for a, b in zip(t, t[1:])):
        return t[-1] + step
    return None


def fit_changing(t):
    """A step that itself changes by a fixed amount each time."""
    if len(t) < 4:
        return None
    diffs = [b - a for a, b in zip(t, t[1:])]
    dstep = diffs[1] - diffs[0]
    if dstep == 0 or not all(b - a == dstep for a, b in zip(diffs, diffs[1:])):
        return None
    return t[-1] + diffs[-1] + dstep


def fit_multiplicative(t):
    """Multiply or divide by a fixed whole number each time."""
    if any(x == 0 for x in t):
        return None
    if all(b % a == 0 for a, b in zip(t, t[1:])):
        ratio = t[1] // t[0]
        if ratio > 1 and all(b == a * ratio for a, b in zip(t, t[1:])):
            return t[-1] * ratio
    if all(a % b == 0 for a, b in zip(t, t[1:])):
        ratio = t[0] // t[1]
        if ratio > 1 and all(b * ratio == a for a, b in zip(t, t[1:])):
            return t[-1] // ratio
    return None


def fit_two_step(t):
    """Multiply by m then subtract s, both fixed. Solved, not searched blindly."""
    out = set()
    for m in (2, 3, 4, 5):
        s = t[0] * m - t[1]
        if s <= 0:
            continue
        if all(b == a * m - s for a, b in zip(t, t[1:])):
            out.add(t[-1] * m - s)
    return out.pop() if len(out) == 1 else None


def fit_alternating(t):
    """Two sequences taking turns, each with its own constant step."""
    if len(t) < 6:
        return None
    a, b = t[0::2], t[1::2]
    if len(a) < 3 or len(b) < 2:
        return None
    for half in (a, b):
        if len({y - x for x, y in zip(half, half[1:])}) != 1:
            return None
    # The blank continues whichever half comes next after the last shown term.
    nxt = b if len(t) % 2 else a
    return nxt[-1] + (nxt[1] - nxt[0])


FITTERS = {"constant": fit_constant, "changing": fit_changing,
           "multiplicative": fit_multiplicative, "two-step": fit_two_step,
           "alternating": fit_alternating}

positions, refs, stems = [], [], collections.Counter()
families = collections.Counter()

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Number Sequences":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    band = q.get("difficulty")
    if band not in BAND_RULE:
        fail.append(f"{tag}: band {band!r}")
        continue

    m = STEM.match(stem)
    if not m:
        fail.append(f"{tag}: stem is not a row of numbers ending in a blank: {stem!r}")
        continue
    terms = [int(x) for x in m.group(1).split(", ")]

    kind = q.get("kind")
    if kind == "numeric":
        if q.get("options"):
            fail.append(f"{tag}: a write-in question must not carry options")
        if not isinstance(q.get("answer"), int):
            fail.append(f"{tag}: numeric answer {q.get('answer')!r} is not an integer")
            continue
        key, wrong = q["answer"], []
    elif kind == "mcq":
        opts = q.get("options") or []
        texts = [o["text"] for o in opts]
        if len(set(texts)) != len(texts):
            fail.append(f"{tag}: repeated option text")
        correct = [o for o in opts if o.get("correct")]
        if len(correct) != 1:
            fail.append(f"{tag}: {len(correct)} options marked correct")
            continue
        if any(not re.fullmatch(r"-?\d+", t) for t in texts):
            fail.append(f"{tag}: an option is not a number")
            continue
        key = int(correct[0]["text"])
        positions.append(texts.index(correct[0]["text"]))
        wrong = [int(o["text"]) for o in opts if not o.get("correct")]
        # The one slug this pack uses must sit exactly on the repeat-the-last-term
        # options and nowhere else.
        for o in opts:
            slug = o.get("misconception")
            repeats = o["text"] == str(terms[-1])
            if o.get("correct") and slug:
                fail.append(f"{tag}: the key carries a misconception slug")
            elif not o.get("correct") and repeats and slug != \
                    "copied-a-given-number-instead-of-solving":
                fail.append(f"{tag}: option {o['text']} repeats the last number shown but "
                            f"is tagged {slug!r}")
            elif not o.get("correct") and not repeats and slug:
                fail.append(f"{tag}: option {o['text']} carries slug {slug!r} that this "
                            f"pack cannot verify from the printed numbers")
    else:
        fail.append(f"{tag}: kind {kind!r}; this pack is mcq and numeric only")
        continue

    # Re-fit every family to the printed terms.
    fits = {name: f(terms) for name, f in FITTERS.items()}
    fits = {name: v for name, v in fits.items() if v is not None}
    if not fits:
        fail.append(f"{tag}: no rule family fits {terms}")
        continue
    predictions = set(fits.values())
    if len(predictions) > 1:
        fail.append(f"{tag}: {terms} is fitted by {sorted(fits)} which disagree "
                    f"({sorted(predictions)}), so it has more than one defensible answer")
        continue
    answer = predictions.pop()
    if key != answer:
        fail.append(f"{tag}: key {key} but the rule gives {answer} for {terms}")
    for w in wrong:
        if w == answer:
            fail.append(f"{tag}: distractor {w} is also the answer")

    for name in fits:
        families[name] += 1
    if not (set(fits) & BAND_RULE[band]):
        fail.append(f"{tag}: band {band} should be {sorted(BAND_RULE[band])} but the row "
                    f"fits {sorted(fits)}")
    if q.get("question_type") not in {TYPE_OF[n] for n in fits}:
        fail.append(f"{tag}: filed as {q.get('question_type')!r} but the row fits "
                    f"{sorted(TYPE_OF[n] for n in fits)}")

    if any(x < 0 for x in terms) or answer < 0:
        fail.append(f"{tag}: the row runs below zero ({terms} -> {answer})")
    if str(answer) not in q.get("explanation", ""):
        fail.append(f"{tag}: explanation does not state the answer {answer}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")
for g in pack.get("groups", []):
    if not g.get("instruction") or not g.get("example"):
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")
    else:
        ex = re.search(r"(-?\d+(?:, -?\d+)+), ___ .*?next number is (-?\d+)", g["example"])
        if not ex:
            fail.append(f"{g.get('group_ref')}: example does not show a row and its answer")
        else:
            t = [int(x) for x in ex.group(1).split(", ")]
            got = {v for v in (f(t) for f in FITTERS.values()) if v is not None}
            if got != {int(ex.group(2))}:
                fail.append(f"example row {t} gives {sorted(got)}, not {ex.group(2)}")

dist = collections.Counter(positions)
run = longest = 1
for a, b in zip(positions, positions[1:]):
    run = run + 1 if a == b else 1
    longest = max(longest, run)
cyclic = next((p for p in (2, 3, 4, 5)
               if positions and all(positions[i] == positions[i % p]
                                    for i in range(len(positions)))), 0)
expected = len(positions) / 4
if longest >= 4:
    fail.append(f"answer position: run of {longest} identical positions")
if cyclic:
    fail.append(f"answer position: cyclic with period {cyclic}")
for pos, c in dist.items():
    if c > expected * 1.6 or c < expected * 0.55:
        fail.append(f"answer position {pos}: {c} of {len(positions)} (expected ~{expected:.0f})")

print(f"pack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"kinds: {dict(collections.Counter(q['kind'] for q in qs))}")
print(f"question types: {dict(collections.Counter(q['question_type'] for q in qs))}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"rule families re-fitted from the printed numbers: {dict(families)}")
print(f"unique stems: {len(stems)} / {len(qs)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
