#!/usr/bin/env python3
"""
Independent checks on the Hidden Words pack (contrib_prash_vr_12.json).

    python3 elevenplus_data/check_hidden_words.py elevenplus_data/contrib_prash_vr_12.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator. Everything below is re-derived from the
*rendered stem* — the sentence the pupil actually reads — because this
subtopic's one real fault is a sentence that hides a second word nobody
noticed, and a checker reading the generator's own pool would simply agree with
whatever the pool asserts.

  * THE EXHAUSTIVE SWEEP. For every question, every 4-letter run of the
    sentence that spans exactly one word join is enumerated — the complete
    candidate space, not a sample — and each is tested against a word list.
    Exactly one must be a word a pupil could offer, and it must be the key.
    This is the check that found eleven of the upstream generator's forty
    sentences to have two valid answers; nine of the eleven rivals were plurals
    or -s verb forms, which is precisely what a lemma-only dictionary misses,
    so the sweep here accepts the regular -s form of any listed word.
  * DISTRACTORS. Every distractor must be a run of the printed sentence (not an
    invented string), must span exactly one join like the key does — otherwise
    "which one crosses a gap" answers the question without reading for
    meaning — and must not be listed in the dictionary at all, a stricter bar
    than the rival test, because a distractor only has to be arguable to be
    unfair.
  * THE WORKED EXAMPLE in the group block is swept too. It teaches the notation,
    so an example with two answers teaches the wrong lesson before question 1.
  * plus: every stem really is a sentence hiding its key across one join, keys
    and refs unique, `short_text` answers carrying no options and `mcq` ones
    exactly one correct option, every explanation naming the two words that
    genuinely straddle the join, band labels present and in range, and answer
    positions neither clustered nor cyclic nor in a run of four.

THE WORD LIST. The sweep needs one, and `/usr/share/dict/words` does not exist
on every machine (the production deploy has none — see
`catalog/generators/_build_compound_data.py`). Where it is missing, or where
`wordfreq` is not installed, the sweep is REPORTED AS SKIPPED rather than
quietly passing, and every other check still runs. Run it at least once
somewhere that has both before trusting a pack.
"""
import collections
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_12.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

# Proper nouns that clear a frequency bar as names but are not answers an
# 11-year-old writes. Hand-adjudicated; kept in the checker so the judgement is
# reviewable next to the check that uses it rather than buried in the generator.
PROPER = {"THEO", "TAFT", "RAND", "SATO", "CHAN", "ALTA", "MECH"}

try:
    from wordfreq import zipf_frequency
    WEB2 = {w.strip().lower() for w in open("/usr/share/dict/words") if w.strip()}
except Exception as exc:                      # no dictionary, or no wordfreq
    WEB2, zipf_frequency, SWEEP_SKIPPED = None, None, str(exc)
else:
    SWEEP_SKIPPED = None


def listed(word):
    """In the dictionary at all, as a lemma or its regular -s form."""
    w = word.lower()
    return (word in PROPER or w in WEB2
            or (w.endswith("s") and w[:-1] in WEB2)
            or (w.endswith("es") and w[:-2] in WEB2))


def claimable(word):
    """A word a pupil could defensibly offer as the answer."""
    if word in PROPER:
        return False
    return zipf_frequency(word.lower(), "en") >= 3.0 and listed(word)


def runs(sentence):
    """Every 4-letter run spanning exactly ONE word join: {run: [start, ...]}.

    One join, not "at least one": the stem promises a word across the end of
    one word and the start of the next, so a run crossing two joins is not the
    shape the pupil was told to look for.
    """
    words = re.findall(r"[A-Za-z]+", sentence)
    letters, ends, pos = "", [], 0
    for w in words:
        letters += w.upper()
        pos += len(w)
        ends.append(pos)
    inner = set(ends[:-1])
    out = collections.defaultdict(list)
    for i in range(len(letters) - 3):
        if len([e for e in inner if i < e < i + 4]) == 1:
            out[letters[i:i + 4]].append(i)
    return out, words, ends


def straddle_words(sentence, word):
    """The two words `word` runs across, from the sentence text alone."""
    found, words, ends = runs(sentence)
    if word not in found:
        return None
    i = found[word][0]
    join = [e for e in ends[:-1] if i < e < i + 4][0]
    at = ends.index(join)
    return words[at], words[at + 1]


positions, refs, stems = [], [], collections.Counter()
swept = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Hidden Words":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    if q.get("question_type") != "across-two-words":
        fail.append(f"{tag}: wrong question_type {q.get('question_type')!r}")
    if q.get("difficulty") not in (3, 4, 5):
        fail.append(f"{tag}: band {q.get('difficulty')!r}; this pack is bands 3-5")

    kind = q.get("kind")
    if kind == "short_text":
        if q.get("options"):
            fail.append(f"{tag}: a write-in question must not carry options")
        key = q.get("answer")
        if not key:
            fail.append(f"{tag}: write-in question with no answer")
            continue
        wrong = []
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

    if len(key) != 4 or not key.isalpha() or key != key.upper():
        fail.append(f"{tag}: key {key!r} is not a four-letter capitalised word")
        continue

    found, _, _ = runs(stem)
    if key not in found:
        fail.append(f"{tag}: the key {key} does not span exactly one join in the stem")
        continue

    for w in wrong:
        if len(w) != 4 or not w.isalpha():
            fail.append(f"{tag}: distractor {w!r} is not a four-letter run")
        elif w not in found:
            fail.append(f"{tag}: distractor {w!r} does not span exactly one join of the "
                        f"stem, so the key can be picked out by position alone")

    if WEB2 is not None:
        swept += 1
        rivals = sorted(w for w in found if w != key and claimable(w))
        if rivals:
            fail.append(f"{tag}: {stem!r} also hides {', '.join(rivals)} across a join, "
                        f"so {key} is not the only answer")
        for w in wrong:
            if listed(w):
                fail.append(f"{tag}: distractor {w!r} is a dictionary word")

    pair = straddle_words(stem, key)
    if pair and not all(f"“{w}”" in q.get("explanation", "") for w in pair):
        fail.append(f"{tag}: explanation does not name the two words {pair} that straddle "
                    f"the join")
    if key not in q.get("explanation", ""):
        fail.append(f"{tag}: explanation does not state the answer {key}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")

# The worked example teaches the notation, so it gets the same sweep.
for g in pack.get("groups", []):
    ex = g.get("example", "")
    m = re.search(r"“([^”]+)”", ex)
    claimed = re.search(r"hides ([A-Z]{4})", ex)
    if not g.get("instruction") or not ex:
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")
    elif m and claimed and WEB2 is not None:
        found, _, _ = runs(m.group(1))
        rivals = sorted(w for w in found if w != claimed.group(1) and claimable(w))
        if claimed.group(1) not in found:
            fail.append(f"example: {claimed.group(1)} does not span one join of {m.group(1)!r}")
        if rivals:
            fail.append(f"example sentence {m.group(1)!r} also hides {', '.join(rivals)}")

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
print(f"unique stems: {len(stems)} / {len(qs)}   unique keys: "
      f"{len({q.get('answer') or next(o['text'] for o in q['options'] if o['correct']) for q in qs})}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
if WEB2 is None:
    print(f"two-answer sweep: SKIPPED — no word list ({SWEEP_SKIPPED})")
else:
    print(f"two-answer sweep: ran over all {swept} stems and the worked example")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
