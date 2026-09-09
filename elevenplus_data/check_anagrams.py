#!/usr/bin/env python3
"""
Independent checks on the Anagrams pack (contrib_prash_vr_15.json).

    python3 elevenplus_data/check_anagrams.py elevenplus_data/contrib_prash_vr_15.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator and never reads the pool. The scrambled letters
are taken from the *rendered stem* — the capitalised token the pupil actually
sees — and every answer is re-derived from those letters alone.

  * THE LETTERS MUST MATCH EXACTLY. The key must be a permutation of the
    scrambled token, same multiset, and must not BE the token: a "jumble" that
    left the word unjumbled is not a question. This half needs no dictionary.
  * THE RIVAL-ANAGRAM SWEEP. Every word in the list that is a permutation of
    the same letters is collected — the whole dictionary indexed by sorted
    letters, so the search is exhaustive rather than a sample of orderings —
    and any rival common enough for a pupil to write (zipf >= 3.0) fails the
    question. This is the ambiguity that matters for this subtopic: an anagram
    with two real solutions has two right answers.
  * DISTRACTORS ARE NOT ANAGRAMS. A distractor that rearranged to the same
    letters would reintroduce exactly that ambiguity. Every distractor must
    also be the same length as the key, so length never gives the answer away,
    and be a real word, so none is eliminable for not looking like one.
  * THE BAND LABEL IS RECOUNTED, not trusted. Difficulty here is word length:
    4 letters is band 2, 5 is band 3, 6 is band 4, 7 is band 5. The checker
    counts the letters in the printed stem and fails a mislabelled question.
  * THE WORKED EXAMPLES are checked as anagrams AND checked not to give away a
    shipped answer — an example naming a word that is also a question hands
    that question over before the pupil reads it.
  * plus: one question per answer word, unique stems and refs, `plain-anagram`
    stems carrying a sentence and `anagram-with-clue` stems a dash and a clue,
    write-in questions with an answer and no options, explanations stating the
    answer, and answer positions neither clustered nor cyclic nor in a run of
    four.

THE WORD LIST. Where `/usr/share/dict/words` or `wordfreq` is missing, the
rival sweep and the real-word check are REPORTED AS SKIPPED rather than quietly
passing; the letter-multiset and band-label checks still run.
"""
import collections
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_15.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

LETTERS = {2: 4, 3: 5, 4: 6, 5: 7}          # band -> answer length

try:
    from wordfreq import zipf_frequency
    WORDS = {w.strip().lower() for w in open("/usr/share/dict/words") if w.strip()}
    WORDS |= {w + "s" for w in list(WORDS)}   # web2 lists lemmas; plurals are answers too
    BY_LETTERS = collections.defaultdict(set)
    for w in WORDS:
        if 3 <= len(w) <= 8:
            BY_LETTERS["".join(sorted(w))].add(w)
except Exception as exc:
    WORDS, zipf_frequency, WHY_SKIPPED = None, None, str(exc)
else:
    WHY_SKIPPED = None

CAPS = re.compile(r"\b([A-Z]{3,})\b")


# Two bars, because they measure two different things. A RIVAL has to be a word
# the pupil produces unprompted from a jumble, so it is held at zipf >= 3.0. A
# DISTRACTOR only has to be recognisable as a word when it is printed in front
# of them, which is an easier task, so it is held at 2.8. The gap is not
# hypothetical: ERASER (zipf 2.94) is an ordinary school word that fails the
# production bar and should not fail the recognition one.
RIVAL_BAR, PRINTED_BAR = 3.0, 2.8


def real_word(word, bar=RIVAL_BAR):
    return zipf_frequency(word.lower(), "en") >= bar and word.lower() in WORDS


def scrambled_of(stem):
    """The capitalised jumble printed in the stem, and nothing else."""
    caps = CAPS.findall(stem)
    return caps[0] if len(caps) == 1 else None


positions, refs, stems, answers = [], [], collections.Counter(), collections.Counter()
swept = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Anagrams":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    qtype = q.get("question_type")
    if qtype not in ("plain-anagram", "anagram-with-clue"):
        fail.append(f"{tag}: wrong question_type {qtype!r}")
    band = q.get("difficulty")
    if band not in LETTERS:
        fail.append(f"{tag}: band {band!r}; this pack is bands 2-5")
        continue

    scrambled = scrambled_of(stem)
    if not scrambled:
        fail.append(f"{tag}: stem does not print exactly one capitalised jumble: {stem!r}")
        continue
    if qtype == "anagram-with-clue" and " — " not in stem:
        fail.append(f"{tag}: a clue question must print its clue after a dash")
    if qtype == "plain-anagram" and (" — " in stem or len(stem.split()) < 5):
        fail.append(f"{tag}: a sentence question must print a sentence")

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

    if not key:
        fail.append(f"{tag}: no answer")
        continue
    answers[key] += 1

    if sorted(key) != sorted(scrambled):
        fail.append(f"{tag}: key {key!r} is not a rearrangement of {scrambled!r}")
    if key == scrambled:
        fail.append(f"{tag}: the jumble {scrambled!r} is already the answer")
    if len(key) != LETTERS[band]:
        fail.append(f"{tag}: {key!r} is {len(key)} letters but is labelled band {band}, "
                    f"which is {LETTERS[band]}")

    for w in wrong:
        if len(w) != len(key):
            fail.append(f"{tag}: distractor {w!r} is not the same length as the key")
        if sorted(w) == sorted(key):
            fail.append(f"{tag}: distractor {w!r} is another arrangement of the same "
                        f"letters, so it is a second answer")

    if WORDS is not None:
        swept += 1
        rivals = sorted(w.upper() for w in BY_LETTERS.get("".join(sorted(key.lower())), set())
                        if w.upper() != key and zipf_frequency(w, "en") >= 3.0)
        if rivals:
            fail.append(f"{tag}: {scrambled} also rearranges to {', '.join(rivals)}")
        if not real_word(key):
            fail.append(f"{tag}: key {key!r} is not a common real word")
        for w in wrong:
            if not real_word(w, PRINTED_BAR):
                fail.append(f"{tag}: distractor {w!r} is not a common real word")

    if key not in q.get("explanation", "") or scrambled not in q.get("explanation", ""):
        fail.append(f"{tag}: explanation does not state both {scrambled} and {key}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for a, n in answers.items():
    if n > 1:
        fail.append(f"answer {a} used in {n} questions")
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
    caps = CAPS.findall(ex)
    if len(caps) < 2:
        fail.append(f"{g.get('group_ref')}: example does not show a jumble and its answer")
        continue
    jumble, shown = caps[0], caps[-1]
    if sorted(jumble) != sorted(shown):
        fail.append(f"example: {shown} is not a rearrangement of {jumble}")
    if shown in answers:
        fail.append(f"example gives away {shown}, which is also a question in this pack")

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
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}"
      f"   (band = answer length: {LETTERS})")
print(f"unique stems: {len(stems)} / {len(qs)}   distinct answers: {len(answers)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
if WORDS is None:
    print(f"rival-anagram sweep: SKIPPED — no word list ({WHY_SKIPPED})")
else:
    print(f"rival-anagram sweep: ran over all {swept} stems")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
