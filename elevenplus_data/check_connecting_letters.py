#!/usr/bin/env python3
"""
Independent checks on the Connecting Letters pack (contrib_prash_vr_16.json).

    python3 elevenplus_data/check_connecting_letters.py elevenplus_data/contrib_prash_vr_16.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator and never reads the pool. The two fragment pairs
are parsed out of the *rendered stem* and every question is re-solved from
them, because uniqueness IS the puzzle here: "the same letter goes in both
gaps" is only a question if exactly one letter does, and with just 26
candidates a near-miss is ordinary rather than exotic.

  * THE EXHAUSTIVE CONNECTOR SWEEP. All 26 letters are tried for a
    single-connector question and all 676 ordered pairs for a two-connector
    one — the entire answer space, not a sample. A candidate survives only if
    it makes a real word out of ALL FOUR fragments. **Exactly one must survive
    and it must be the key**, and no printed distractor may be among the
    survivors.
  * PLURALS ARE IN THE WORD LIST. `/usr/share/dict/web2` lists lemmas, so a
    sweep against it alone never sees BANS — which is exactly how the pool's
    BA(_)AG / BAN(_)ET entry kept a second solution (S: BAS/SAG, BANS/SET)
    through its original check. That entry is not in this pack.
  * THE EXPLANATION IS RECOMPUTED. It names four words; each must be the
    corresponding fragment with the key actually spliced in, so an explanation
    cannot drift from the stem it explains. This half needs no dictionary.
  * THE WORKED EXAMPLES get the same sweep as a question, and must not be built
    on a frame that is also a question in the pack.
  * plus: one question per frame, unique stems and refs, gap width matching the
    connector length, band 5 being the two-letter type and bands 2-4 the
    one-letter type, write-in questions carrying an answer and no options, and
    answer positions neither clustered nor cyclic nor in a run of four.

THE WORD LIST. Where `/usr/share/dict/words` or `wordfreq` is missing, the
sweep is REPORTED AS SKIPPED rather than quietly passing; the splice check and
every structural check still run.
"""
import collections
import json
import re
import string
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_16.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

try:
    from wordfreq import zipf_frequency
    WEB2 = {w.strip().lower() for w in open("/usr/share/dict/words") if w.strip()}
except Exception as exc:
    WEB2, zipf_frequency, WHY_SKIPPED = None, None, str(exc)
else:
    WHY_SKIPPED = None

STEM = re.compile(r"^([A-Z]+)\((_+)\)([A-Z]+)\s+([A-Z]+)\(\2\)([A-Z]+)$")
EXPLAIN = re.compile(r"^([A-Z]+) gives ([A-Z]+) and ([A-Z]+) from the first pair, "
                     r"and ([A-Z]+) and ([A-Z]+) from the second\.$")


def real_word(word):
    """Common enough to count, listed as a lemma or its regular -s form."""
    w = word.lower()
    return zipf_frequency(w, "en") >= 3.0 and (
        w in WEB2 or (w.endswith("s") and w[:-1] in WEB2)
        or (w.endswith("es") and w[:-2] in WEB2))


def solutions(p1, s1, p2, s2, width):
    """Every connector of `width` letters that makes all four fragments words."""
    space = (string.ascii_uppercase if width == 1 else
             [a + b for a in string.ascii_uppercase for b in string.ascii_uppercase])
    return [c for c in space
            if real_word(p1 + c) and real_word(c + s1)
            and real_word(p2 + c) and real_word(c + s2)]


positions, refs, stems, frames = [], [], collections.Counter(), collections.Counter()
swept = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Connecting Letters":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    band = q.get("difficulty")
    if band not in (2, 3, 4, 5):
        fail.append(f"{tag}: band {band!r}; this pack is bands 2-5")

    m = STEM.match(stem)
    if not m:
        fail.append(f"{tag}: stem is not two gapped fragment pairs: {stem!r}")
        continue
    p1, gap, s1, p2, s2 = m.groups()
    width = len(gap)
    frames[(p1, s1, p2, s2)] += 1

    qtype = q.get("question_type")
    if width == 1 and qtype != "single-connector":
        fail.append(f"{tag}: one-letter gap filed as {qtype!r}")
    if width == 2 and qtype != "two-connectors":
        fail.append(f"{tag}: two-letter gap filed as {qtype!r}")
    if (width == 2) != (band == 5):
        fail.append(f"{tag}: band {band} with a {width}-letter gap; band 5 is the "
                    f"two-letter type and bands 2-4 the one-letter type")

    kind = q.get("kind")
    if kind == "short_text":
        if q.get("options"):
            fail.append(f"{tag}: a write-in question must not carry options")
        key, wrong = q.get("answer"), []
    elif kind == "mcq":
        opts = q.get("options") or []
        texts = [o["text"] for o in opts]
        if len(set(texts)) != len(texts):
            fail.append(f"{tag}: repeated option text")
        correct = [o for o in opts if o.get("correct")]
        if len(correct) != 1:
            fail.append(f"{tag}: {len(correct)} options marked correct")
            continue
        key = correct[0]["text"]
        positions.append(texts.index(key))
        wrong = [o["text"] for o in opts if not o.get("correct")]
    else:
        fail.append(f"{tag}: kind {kind!r}; this pack is mcq and short_text only")
        continue

    if not key or len(key) != width:
        fail.append(f"{tag}: key {key!r} does not fill a {width}-letter gap")
        continue
    for w in wrong:
        if len(w) != width:
            fail.append(f"{tag}: distractor {w!r} does not fill a {width}-letter gap")

    # The explanation must be the stem with the key spliced in — no dictionary.
    em = EXPLAIN.match(q.get("explanation", ""))
    if not em:
        fail.append(f"{tag}: explanation is not in this pack's shape")
    else:
        shown_key, w1, w2, w3, w4 = em.groups()
        if shown_key != key:
            fail.append(f"{tag}: explanation explains {shown_key}, not the key {key}")
        if (w1, w2, w3, w4) != (p1 + key, key + s1, p2 + key, key + s2):
            fail.append(f"{tag}: explanation words {(w1, w2, w3, w4)} are not the stem's "
                        f"fragments with {key} spliced in")

    if WEB2 is not None:
        swept += 1
        sols = solutions(p1, s1, p2, s2, width)
        if sols != [key]:
            fail.append(f"{tag}: {stem!r} is solved by {sols or 'nothing'}, not by {key} "
                        f"alone")
        for w in wrong:
            if w in sols:
                fail.append(f"{tag}: distractor {w!r} also solves both pairs")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for f, n in frames.items():
    if n > 1:
        fail.append(f"frame {f} used in {n} questions")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")

for g in pack.get("groups", []):
    ex = g.get("example", "")
    if not g.get("instruction") or not ex:
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")
        continue
    m = re.search(r"([A-Z]+)\((_+)\)([A-Z]+)\s+([A-Z]+)\(_+\)([A-Z]+)", ex)
    claimed = re.search(r"the letters? ([A-Z]+) gives?", ex)
    if not m or not claimed:
        fail.append(f"{g.get('group_ref')}: example does not show a frame and its answer")
        continue
    p1, gap, s1, p2, s2 = m.groups()
    if m.group(0).split("     ")[0] and f"{p1}({gap}){s1}     {p2}({gap}){s2}" in stems:
        fail.append(f"example frame is also a question in this pack")
    if WEB2 is not None:
        sols = solutions(p1, s1, p2, s2, len(gap))
        if sols != [claimed.group(1)]:
            fail.append(f"example {p1}({gap}){s1} {p2}({gap}){s2} is solved by "
                        f"{sols or 'nothing'}, not by {claimed.group(1)} alone")

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
    if c > expected * 1.7 or c < expected * 0.5:
        fail.append(f"answer position {pos}: {c} of {len(positions)} (expected ~{expected:.0f})")

print(f"pack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"kinds: {dict(collections.Counter(q['kind'] for q in qs))}")
print(f"question types: {dict(collections.Counter(q['question_type'] for q in qs))}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"unique stems: {len(stems)} / {len(qs)}   distinct frames: {len(frames)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
if WEB2 is None:
    print(f"connector sweep: SKIPPED — no word list ({WHY_SKIPPED})")
else:
    print(f"connector sweep: ran over all {swept} stems and both worked examples")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
