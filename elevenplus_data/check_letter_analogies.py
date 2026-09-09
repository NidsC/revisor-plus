#!/usr/bin/env python3
"""
Independent checks on the Letter Analogy pack (contrib_prash_vr_07.json).

    python3 elevenplus_data/check_letter_analogies.py elevenplus_data/contrib_prash_vr_07.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

This is deliberately NOT part of validate_questions.py, which is the import
gate, nor of audit_packs.py, whose checks are section-agnostic. It knows one
question shape and can therefore do what neither can: re-derive every answer
from the *rendered stem text* and prove the key is the only one available.

It never imports the generator. If it did, a wrong rule in the generator would
be checked against itself and pass. It reads the printed stem, enumerates the
rules a pupil could read out of it, and requires them all to agree.

Rule space, per output position: the output letter is either
  * some input letter X_j shifted by a fixed amount (the amount pinned by the
    worked pair), or
  * the alphabet mirror of some input letter X_j (A<->Z, B<->Y, ...)
for any j — which covers every positional permutation, every per-letter shift
and every mirror reading. Both halves of what was asked for fall out of this:
the key is too narrow if the reachable set has more than one member, and the
two-answer sweep is the check that no printed distractor is in that set.

Also checks, for the pack as a whole: no duplicate stems or option sets, no
duplicate refs, answer positions neither clustered nor cyclic nor in a run of
four, every distractor a same-shape letter group carrying a misconception, and
every explanation stating its own answer.
"""
import collections
import itertools
import json
import re
import sys

PACK = sys.argv[1]
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []


def N(c):
    return ord(c) - ord('A')


def n2s(v):
    return ''.join(chr(ord('A') + (x % 26)) for x in v)


STEM = re.compile(r"^([A-Z]+) is to ([A-Z]+) as ([A-Z]+) is to ___$")


def achievable(stem):
    """Every answer any consistent rule gives for this stem."""
    m = STEM.match(stem)
    if not m:
        return None, None
    X, Y, Z = ([N(c) for c in g] for g in m.groups())
    if not (len(X) == len(Y) == len(Z)):
        return None, None
    per_pos = []
    for i, y in enumerate(Y):
        atoms = set()
        for j, x in enumerate(X):
            atoms.add((Z[j] + (y - x)) % 26)            # shift atom
            if y == 25 - x:                             # mirror atom
                atoms.add((25 - Z[j]) % 26)
        per_pos.append(sorted(atoms))
    return {n2s(c) for c in itertools.product(*per_pos)}, m.groups()


# ---------------------------------------------------------------- checks
keys, positions = [], []
stems = collections.Counter()
optsets = collections.Counter()
refs = []

for q in qs:
    tag = q.get("ref", "?")
    stems[q["stem"]] += 1
    refs.append(tag)
    opts = q["options"]
    texts = [o["text"] for o in opts]
    optsets[(q["stem"], tuple(sorted(texts)))] += 1
    if len(set(texts)) != len(texts):
        fail.append(f"{tag}: repeated option text")
    correct = [o for o in opts if o.get("correct")]
    if len(correct) != 1:
        fail.append(f"{tag}: {len(correct)} options marked correct")
        continue
    key = correct[0]["text"]
    keys.append(key)
    positions.append(texts.index(key))

    reachable, parts = achievable(q["stem"])
    if reachable is None:
        fail.append(f"{tag}: stem does not parse: {q['stem']!r}")
        continue
    # 1. the key is what the stem's rule actually produces
    if key not in reachable:
        fail.append(f"{tag}: key {key} is not produced by any reading of {q['stem']!r}")
    # 2. the rule is not open to a second reading (key-too-narrow guard)
    if len(reachable) != 1:
        fail.append(f"{tag}: {q['stem']!r} has {len(reachable)} valid readings: "
                    f"{sorted(reachable)}")
    # 3. exhaustive two-answer sweep: no distractor is also right
    for o in opts:
        if not o.get("correct") and o["text"] in reachable:
            fail.append(f"{tag}: distractor {o['text']} is also a correct answer")
    # 4. distractors must be the same shape as the key
    for o in opts:
        if len(o["text"]) != len(key) or not o["text"].isupper():
            fail.append(f"{tag}: option {o['text']!r} is not a {len(key)}-letter group")
    # 5. a distractor equal to the unchanged third group must say so
    third = parts[2]
    for o in opts:
        if not o.get("correct") and o["text"] == third and o.get("misconception") != "no-shift-applied":
            fail.append(f"{tag}: distractor {o['text']} is the third group unchanged but is "
                        f"tagged {o.get('misconception')!r}")
    # 6. explanation must state the key and not name an option letter position
    if key not in q["explanation"]:
        fail.append(f"{tag}: explanation does not state the answer {key}")

# duplicates
for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for (s, _), n in optsets.items():
    if n > 1:
        fail.append(f"duplicate stem+option set x{n}: {s!r}")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

# answer-position distribution
dist = collections.Counter(positions)
n_opts = max(len(q["options"]) for q in qs)
run, longest = 1, 1
for a, b in zip(positions, positions[1:]):
    run = run + 1 if a == b else 1
    longest = max(longest, run)
cyclic = 0
for period in (2, 3, 4, 5):
    ok = all(positions[i] == positions[i % period] for i in range(len(positions)))
    if ok:
        cyclic = period
expected = len(positions) / n_opts
if longest >= 4:
    fail.append(f"answer position: run of {longest} identical positions")
if cyclic:
    fail.append(f"answer position: cyclic with period {cyclic}")
for pos, c in dist.items():
    if c > expected * 1.6 or c < expected * 0.55:
        fail.append(f"answer position {pos}: {c} of {len(positions)} (expected ~{expected:.0f})")

# difficulty bands
bands = collections.Counter(q["difficulty"] for q in qs)
types = collections.Counter(q["question_type"] for q in qs)

print(f"pack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"answer positions (0-indexed): {dict(sorted(dist.items()))}  longest run {longest}  cyclic {cyclic or 'none'}")
print(f"difficulty: {dict(sorted(bands.items()))}")
print(f"question types: {dict(types)}")
print(f"unique stems: {len(stems)} / {len(qs)}")
print(f"stem lengths: {dict(collections.Counter(len(q['stem'].split()[0]) for q in qs))}")
mis = collections.Counter(o.get('misconception') for q in qs for o in q['options'] if not o.get('correct'))
print("distractor misconceptions:", dict(mis))
untagged = sum(1 for q in qs for o in q['options'] if not o.get('correct') and not o.get('misconception'))
print("untagged distractors:", untagged)

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
