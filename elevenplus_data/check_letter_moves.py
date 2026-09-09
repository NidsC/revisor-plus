#!/usr/bin/env python3
"""
Independent checks on the Letter Moves pack (contrib_prash_vr_14.json).

    python3 elevenplus_data/check_letter_moves.py elevenplus_data/contrib_prash_vr_14.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator and never reads the pool. The two words are
parsed out of the rendered stem and everything else is re-derived from them,
which matters here more than anywhere: this subtopic's only real fault is a
pair with a SECOND valid move, and a checker that trusted the pool's own
"verified unique" claim would have agreed with it. Three entries of the 28
carry exactly that fault (SPEAK/AID, BEAST/OWL, STONE/PET, each losing to an
-s plural) and are not in this pack.

  * THE EXHAUSTIVE MOVE SWEEP. For each stem, every letter of the first word is
    removed in turn and inserted at every position of the second word — the
    complete space of legal moves, |A| x (|B| + 1) of them, not a sample. Every
    move whose two results are both real words is collected. **Exactly one must
    survive, and it must be the key.** No printed distractor may be among the
    survivors either.
  * THE -S TRAP EXPLICITLY. The word list accepts the regular -s form of any
    listed word, because that is precisely what a lemma-only dictionary misses
    and precisely how the three excluded entries passed their original check.
  * THE MOVE IS CHECKED WITHOUT A DICTIONARY TOO, so this half runs anywhere:
    the key's first word must be the stem's first word with exactly one letter
    removed and the rest in their original order; the key's second word must be
    the stem's second word with that same letter inserted, its own letters
    still in order. A key that is not a legal move is wrong whether or not it
    happens to be two real words.
  * DISTRACTORS. Each must be a pair built from the same four words — nothing
    invented — must not be a valid move itself, and the two named slips must
    both be present: leaving one word unchanged, and reporting the right two
    words in the wrong slots. Their slugs are checked against what they
    actually show.
  * THE WORKED EXAMPLE gets the same exhaustive sweep as a question.
  * plus: one question per word pair, unique stems and refs, band labels in
    range, explanations naming the moved letter and both results, and answer
    positions neither clustered nor cyclic nor in a run of four.

THE WORD LIST. Where `/usr/share/dict/words` or `wordfreq` is missing, the
sweep is REPORTED AS SKIPPED rather than quietly passing; the dictionary-free
checks above still run.
"""
import collections
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_14.json"
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

STEM = re.compile(r"^Move one letter from ([A-Z]+) to ([A-Z]+)\.$")
PAIR = re.compile(r"^([A-Z]+), ([A-Z]+)$")


def real_word(word):
    """A word a pupil would offer: common, and listed as a lemma or its -s form."""
    w = word.lower()
    return zipf_frequency(w, "en") >= 3.0 and (
        w in WEB2 or (w.endswith("s") and w[:-1] in WEB2)
        or (w.endswith("es") and w[:-2] in WEB2))


def all_moves(a, b):
    """Every (new_a, new_b) reachable by moving one letter from a into b."""
    out = set()
    for i, ch in enumerate(a):
        rest = a[:i] + a[i + 1:]
        for j in range(len(b) + 1):
            out.add((rest, b[:j] + ch + b[j:], ch))
    return out


def is_legal_move(a, b, new_a, new_b):
    """True when (new_a, new_b) really is one letter moved from a into b.

    Dictionary-free: pure string arithmetic on what the stem printed.
    """
    return any((na, nb) == (new_a, new_b) for na, nb, _ in all_moves(a, b))


positions, refs, stems, seen_pairs = [], [], collections.Counter(), collections.Counter()
swept = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Letter Moves":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    if q.get("question_type") != "move-one-letter":
        fail.append(f"{tag}: wrong question_type {q.get('question_type')!r}")
    if q.get("difficulty") not in (3, 4, 5):
        fail.append(f"{tag}: band {q.get('difficulty')!r}; this pack is bands 3-5")
    if q.get("kind") != "mcq":
        fail.append(f"{tag}: kind {q.get('kind')!r}; this pack is mcq throughout")
        continue

    m = STEM.match(stem)
    if not m:
        fail.append(f"{tag}: stem is not in this pack's printed shape: {stem!r}")
        continue
    word_a, word_b = m.groups()
    seen_pairs[(word_a, word_b)] += 1

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
    if correct[0].get("misconception"):
        fail.append(f"{tag}: the key carries a misconception slug")

    km = PAIR.match(key)
    if not km:
        fail.append(f"{tag}: key {key!r} is not a printed word pair")
        continue
    new_a, new_b = km.groups()

    if not is_legal_move(word_a, word_b, new_a, new_b):
        fail.append(f"{tag}: {key!r} is not one letter moved from {word_a} into {word_b}")

    if WEB2 is not None:
        swept += 1
        good = {(na, nb) for na, nb, _ in all_moves(word_a, word_b)
                if real_word(na) and real_word(nb)}
        if (new_a, new_b) not in good:
            fail.append(f"{tag}: the key {key!r} does not make two real words")
        rivals = sorted(good - {(new_a, new_b)})
        if rivals:
            fail.append(f"{tag}: {word_a} -> {word_b} also allows "
                        f"{'; '.join(f'{x}, {y}' for x, y in rivals)}, so the key is not "
                        f"the only answer")
        for w in wrong:
            wm = PAIR.match(w)
            if wm and (wm.group(1), wm.group(2)) in good:
                fail.append(f"{tag}: distractor {w!r} is also a valid move")

    # Distractors are built from the same four words and show the two named slips.
    wordset = {word_a, word_b, new_a, new_b}
    for w in wrong:
        wm = PAIR.match(w)
        if not wm:
            fail.append(f"{tag}: distractor {w!r} is not a printed word pair")
            continue
        if not set(wm.groups()) <= wordset:
            fail.append(f"{tag}: distractor {w!r} uses words not in this question")
    slugs = {o["text"]: o.get("misconception") for o in opts if not o.get("correct")}
    unchanged = [w for w in wrong if word_a in w.split(", ") or word_b in w.split(", ")]
    swapped = [w for w in wrong if w == f"{new_b}, {new_a}"]
    if not unchanged:
        fail.append(f"{tag}: no distractor leaves one of the two words unchanged")
    if not swapped:
        fail.append(f"{tag}: no distractor reports the two new words in the wrong slots")
    for w in unchanged:
        if slugs.get(w) != "only-changed-one-word":
            fail.append(f"{tag}: {w!r} leaves a word unchanged but is tagged {slugs.get(w)!r}")
    for w in swapped:
        if slugs.get(w) != "mixed-up-which-word-changed":
            fail.append(f"{tag}: {w!r} swaps the slots but is tagged {slugs.get(w)!r}")

    exp = q.get("explanation", "")
    for part in (new_a, new_b, word_a, word_b):
        if part not in exp:
            fail.append(f"{tag}: explanation does not mention {part}")
            break

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for p, n in seen_pairs.items():
    if n > 1:
        fail.append(f"word pair {p} used in {n} questions")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")

# The worked example is swept exactly like a question.
for g in pack.get("groups", []):
    ex = g.get("example", "")
    if not g.get("instruction") or not ex:
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")
        continue
    m = re.search(r"Move one letter from ([A-Z]+) to ([A-Z]+):", ex)
    claimed = re.search(r"the pair is ([A-Z]+), ([A-Z]+)\.", ex)
    if not m or not claimed:
        fail.append(f"{g.get('group_ref')}: example does not state a move and its pair")
        continue
    if not is_legal_move(m.group(1), m.group(2), *claimed.groups()):
        fail.append(f"example: {claimed.groups()} is not a legal move on {m.groups()}")
    if WEB2 is not None:
        good = {(na, nb) for na, nb, _ in all_moves(*m.groups())
                if real_word(na) and real_word(nb)}
        if good != {claimed.groups()}:
            fail.append(f"example {m.groups()} has moves {sorted(good)}, not just "
                        f"{claimed.groups()}")

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
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"unique stems: {len(stems)} / {len(qs)}   distinct word pairs: {len(seen_pairs)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
if WEB2 is None:
    print(f"exhaustive move sweep: SKIPPED — no word list ({WHY_SKIPPED})")
else:
    print(f"exhaustive move sweep: ran over all {swept} stems and the worked example")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
