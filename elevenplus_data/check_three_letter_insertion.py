#!/usr/bin/env python3
"""
Independent checks on the Three-Letter Insertion pack (contrib_prash_vr_21.json).

    python3 elevenplus_data/check_three_letter_insertion.py elevenplus_data/contrib_prash_vr_21.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator and never reads the pool. The mutilated word is
taken from the *rendered stem* — the capitalised token the pupil actually sees —
and every answer is re-derived from it.

  * THE EXHAUSTIVE SWEEP. For each stem, every one of the **17,576** three-letter
    strings is tried at every insertion point of the printed token: the complete
    space, not a sample. A candidate counts when the string is itself a real
    word AND inserting it makes a real word, which is exactly what the stem
    promises. The key must be one of them.
  * WHERE MORE THAN ONE CANDIDATE SURVIVES, THE SENTENCE IS THE ONLY GUARD, and
    the checker says so per question rather than passing quietly. It cannot read
    the sentence, so it reports the rivals and leaves that judgement to a human —
    the honest division of labour for this subtopic, and the one thing
    `_TLI_ALL_FRAGMENTS`' own comment gets wrong when it credits the word list.
  * EVERY OPTION MUST BE A REAL WORD, and this is the check that matters most
    here: the stem tells the pupil the answer is itself a word, so an option
    that is not one is eliminable without reading the sentence — and a KEY that
    is not one punishes the pupil who follows the instruction. The four
    fragments this pack excludes (HAN, ALA, ALT, PHI) all clear a bare
    frequency bar and are all listed in web2; they are rejected here by a
    hand-adjudicated list, because that judgement is not one a word list makes.
  * NO DISTRACTOR MAY ALSO FIT the printed gap as a word.
  * plus: the key really does rebuild a real word from the printed token, one
    question per token, unique stems and refs, band labels in range (there is no
    band 5 in this subtopic), write-in questions carrying an answer and no
    options, explanations naming the rebuilt word, and answer positions neither
    clustered nor cyclic nor in a run of four.

THE WORD LIST. Where `/usr/share/dict/words` or `wordfreq` is missing, the
sweep and the real-word checks are REPORTED AS SKIPPED rather than quietly
passing; the structural checks still run.
"""
import collections
import json
import re
import string
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_21.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

# Hand-adjudicated: listed in web2 and frequent enough to pass a bare bar, but
# not words a pupil would call words. The frequency comes from proper nouns
# (Han, Phi as a name, Ala. as an abbreviation) and from `alt` as a key name.
NOT_WORDS = {"HAN", "ALA", "ALT", "PHI", "ORA", "ITA", "ETA", "OSA"}

try:
    from wordfreq import zipf_frequency
    WORDS = {w.strip().lower() for w in open("/usr/share/dict/words") if w.strip()}
except Exception as exc:
    WORDS, zipf_frequency, WHY_SKIPPED = None, None, str(exc)
else:
    WHY_SKIPPED = None

CAPS = re.compile(r"\b([A-Z]{2,})\b")


def real_word(word):
    w = word.lower()
    if word.upper() in NOT_WORDS:
        return False
    return zipf_frequency(w, "en") >= 2.5 and (
        w in WORDS or (w.endswith("s") and w[:-1] in WORDS))


TRIPLES = ["".join(t) for t in
           __import__("itertools").product(string.ascii_uppercase, repeat=3)]


def candidates(token):
    """Every (fragment, position) that satisfies what the stem promises."""
    out = []
    for frag in TRIPLES:
        if not real_word(frag):
            continue
        for i in range(len(token) + 1):
            if real_word(token[:i] + frag + token[i:]):
                out.append((frag, i, token[:i] + frag + token[i:]))
    return out


positions, refs, stems, tokens = [], [], collections.Counter(), collections.Counter()
sentence_guarded = swept = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Three-Letter Insertion":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    if q.get("question_type") != "insert-to-complete":
        fail.append(f"{tag}: wrong question_type {q.get('question_type')!r}")
    if q.get("difficulty") not in (2, 3, 4):
        fail.append(f"{tag}: band {q.get('difficulty')!r}; this subtopic has bands 2-4 "
                    f"only — there is no band 5")

    caps = CAPS.findall(stem)
    if len(caps) != 1:
        fail.append(f"{tag}: stem does not print exactly one capitalised word: {stem!r}")
        continue
    token = caps[0]
    tokens[token] += 1

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

    if not key or len(key) != 3 or not key.isalpha():
        fail.append(f"{tag}: key {key!r} is not three letters")
        continue
    for w in wrong:
        if len(w) != 3 or not w.isalpha():
            fail.append(f"{tag}: distractor {w!r} is not three letters")

    if WORDS is None:
        continue
    swept += 1
    if not real_word(key):
        fail.append(f"{tag}: the key {key!r} is not a word a pupil would recognise, but "
                    f"the stem tells them the answer is one")
    for w in wrong:
        if not real_word(w):
            fail.append(f"{tag}: distractor {w!r} is not a real word, so it can be struck "
                        f"out without reading the sentence")

    fits = candidates(token)
    if key not in {f for f, _, _ in fits}:
        fail.append(f"{tag}: {key} does not rebuild a real word from {token}")
        continue
    rebuilt = next(w for f, _, w in fits if f == key)
    for w in wrong:
        if w in {f for f, _, _ in fits}:
            fail.append(f"{tag}: distractor {w!r} also rebuilds a real word from {token}")
    others = sorted({(f, w) for f, _, w in fits if f != key})
    if others:
        sentence_guarded += 1
        print(f"  note {tag}: {token} also takes "
              f"{', '.join(f'{f} -> {w}' for f, w in others[:4])}"
              f"{' ...' if len(others) > 4 else ''}; only the sentence rules these out")
    if rebuilt not in q.get("explanation", ""):
        fail.append(f"{tag}: explanation does not name the rebuilt word {rebuilt}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for t, n in tokens.items():
    if n > 1:
        fail.append(f"token {t} used in {n} questions")
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
    m = re.search(r"putting ([A-Z]{3}) back gives ([A-Z]+)", ex)
    quoted = re.search(r"“([^”]+)”", ex)
    tok = CAPS.search(quoted.group(1)) if quoted else None
    if not m or not tok:
        fail.append(f"{g.get('group_ref')}: example does not show a token and its answer")
    elif WORDS is not None:
        if m.group(1) not in {f for f, _, _ in candidates(tok.group(1))}:
            fail.append(f"example: {m.group(1)} does not rebuild a word from {tok.group(1)}")
        if tok.group(1) in tokens:
            fail.append("example reuses a token that is also a question")

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
    if c > expected * 1.8 or c < expected * 0.45:
        fail.append(f"answer position {pos}: {c} of {len(positions)} (expected ~{expected:.0f})")

print(f"\npack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"kinds: {dict(collections.Counter(q['kind'] for q in qs))}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"unique stems: {len(stems)} / {len(qs)}   distinct tokens: {len(tokens)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
if WORDS is None:
    print(f"17,576-string sweep: SKIPPED — no word list ({WHY_SKIPPED})")
else:
    print(f"17,576-string sweep: ran over all {swept} stems; {sentence_guarded} of them "
          f"have a rival the sentence alone rules out")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
