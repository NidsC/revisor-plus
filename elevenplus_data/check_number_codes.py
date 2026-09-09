#!/usr/bin/env python3
"""
Independent checks on the Number Codes pack (contrib_prash_vr_09.json).

    python3 elevenplus_data/check_number_codes.py elevenplus_data/contrib_prash_vr_09.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator. If it did, a wrong template would be checked
against itself and pass. Everything below is derived from the *rendered stem
text*: the printed "WORD = CODE" pairs are parsed back out of the stem and
every letter's value is re-derived from them.

  * the exhaustive two-answer sweep. `all_mappings` enumerates EVERY injective
    letter -> value map consistent with the printed pairs — it assigns letters
    one at a time and rejects on the first pair that disagrees, so nothing
    consistent is skipped — and exactly one must survive. If two did, the pupil
    was shown a puzzle with two defensible readings. The question is then
    solved under that one map, the answer must be the key, and no printed
    distractor may be an answer under it either. For a decode item that means
    encoding every option word and checking only the keyed one produces the
    printed code; for a letter clue, that exactly one letter in the whole
    puzzle takes the printed value.
  * distractor liveness: every encode distractor must be a code of the right
    length over the values the puzzle actually shows, and must not repeat a
    value — no word in this pack repeats a letter, so a code with a repeated
    digit is impossible and a pupil could rule it out without decoding. Decode
    distractors must be spelled from letters the puzzle has already shown, for
    the same reason; the count that are not is reported rather than hidden.
  * bands 1 and 2 must be absent, band 5's letter clues must genuinely appear
    in only one given word, answer positions neither clustered nor cyclic nor
    in a run of four, no duplicate stems or refs, typed questions carrying an
    answer and no options, and every explanation stating its own answer.
"""
import collections
import re
import json
import sys

PACK = sys.argv[1]
pack = json.load(open(PACK))
qs = pack["questions"]
fail, notes = [], []

PAIR = re.compile(r"^([A-Z]+) = (.+)$")
ASK_ENCODE = re.compile(r"^What is the code for ([A-Z]+)\?$")
ASK_WORD = re.compile(r"^Which word has the code (\S+)\?$")
ASK_LETTER = re.compile(r"^Which letter does (\S+) stand for\?$")


def parse(stem):
    """(pairs, question) from the rendered stem, or None if it isn't the shape
    this pack prints. pairs is [(WORD, [unit, ...]), ...]."""
    if not stem.startswith("In a code, "):
        return None
    body, _, question = stem[len("In a code, "):].partition(". ")
    pairs = []
    for chunk in body.split("; "):
        m = PAIR.match(chunk)
        if not m:
            return None
        word, code = m.group(1), m.group(2)
        units = code.split(" ") if " " in code else list(code)
        pairs.append((word, units))
    return pairs, question


def all_mappings(pairs, cap=2):
    """Every injective letter -> value map consistent with every printed pair.

    Exhaustive by construction: letters are assigned one at a time from the
    values the stem actually prints, and a partial assignment is kept only
    while it still agrees with every pair position it has filled in. Nothing
    consistent is pruned, so a second solution would be found if one existed.
    """
    letters = sorted({c for w, _ in pairs for c in w})
    values = sorted({u for _, units in pairs for u in units})
    sols = []

    def agrees(m):
        for word, units in pairs:
            if len(word) != len(units):
                return False
            for c, u in zip(word, units):
                if c in m and m[c] != u:
                    return False
        return True

    def rec(i, m, used):
        if len(sols) >= cap:
            return
        if i == len(letters):
            sols.append(dict(m))
            return
        c = letters[i]
        for v in values:
            if v in used:
                continue
            m[c] = v
            if agrees(m):
                rec(i + 1, m, used | {v})
            del m[c]

    rec(0, {}, frozenset())
    return sols


positions, mcq_count = [], 0
stems = collections.Counter()
refs = []
kinds = collections.Counter()
variants = collections.Counter()
outside_letters = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)
    kinds[q["kind"]] += 1

    parsed = parse(stem)
    if parsed is None:
        fail.append(f"{tag}: stem is not in this pack's printed shape: {stem!r}")
        continue
    pairs, question = parsed

    maps = all_mappings(pairs)
    if len(maps) != 1:
        fail.append(f"{tag}: the printed pairs admit {len(maps)} letter->value maps")
        continue
    mapping = maps[0]
    is_symbol = not all(u.isdigit() for _, units in pairs for u in units)

    def encode(word):
        if not set(word) <= set(mapping):
            return None
        units = [mapping[c] for c in word]
        return " ".join(units) if is_symbol else "".join(units)

    if q["kind"] in ("short_text", "numeric"):
        if "options" in q:
            fail.append(f"{tag}: typed question carries options")
        key = q.get("answer")
        if not key:
            fail.append(f"{tag}: typed question has no answer")
            continue
        opts, texts = [], []
    else:
        opts = q["options"]
        texts = [o["text"] for o in opts]
        if len(set(texts)) != len(texts):
            fail.append(f"{tag}: repeated option text")
        correct = [o for o in opts if o.get("correct")]
        if len(correct) != 1:
            fail.append(f"{tag}: {len(correct)} options marked correct")
            continue
        key = correct[0]["text"]
        positions.append(texts.index(key))
        mcq_count += 1
    wrong_texts = [o["text"] for o in opts if not o.get("correct")]

    m = ASK_ENCODE.match(question)
    if m:
        variants["encode"] += 1
        target = m.group(1)
        if not set(target) <= set(mapping):
            fail.append(f"{tag}: {target} uses a letter the given words never show")
            continue
        answer = encode(target)
        if key != answer:
            fail.append(f"{tag}: key {key!r} but the code for {target} is {answer!r}")
        # exhaustive two-answer sweep across the printed options
        for w in wrong_texts:
            if w == answer:
                fail.append(f"{tag}: distractor {w!r} is also the code for {target}")
        # distractor liveness
        n = len(target)
        for w in wrong_texts:
            units = w.split(" ") if is_symbol else list(w)
            if len(units) != n:
                fail.append(f"{tag}: distractor {w!r} is not {n} units long")
            elif len(set(units)) != len(units):
                fail.append(f"{tag}: distractor {w!r} repeats a value, so it is not a "
                            f"possible code in this pack")
            elif not set(units) <= set(mapping.values()):
                fail.append(f"{tag}: distractor {w!r} uses a value the puzzle never shows")
    elif ASK_WORD.match(question):
        variants["decode-word"] += 1
        code = ASK_WORD.match(question).group(1)
        if encode(key) != code:
            fail.append(f"{tag}: key {key!r} encodes to {encode(key)!r}, not {code!r}")
        # exhaustive two-answer sweep: every option word, encoded
        for w in wrong_texts:
            if encode(w) == code:
                fail.append(f"{tag}: distractor {w!r} also has the code {code}")
            if w == key:
                fail.append(f"{tag}: distractor repeats the key")
            if not set(w) <= set(mapping):
                outside_letters += 1
        shown = {w for w, _ in pairs}
        if key in shown:
            fail.append(f"{tag}: the answer {key!r} is one of the given words")
    elif ASK_LETTER.match(question):
        variants["letter-clue"] += 1
        value = ASK_LETTER.match(question).group(1)
        owners = [c for c, v in mapping.items() if v == value]
        if len(owners) != 1:
            fail.append(f"{tag}: {value} is taken by {len(owners)} letters: {owners}")
            continue
        if key != owners[0]:
            fail.append(f"{tag}: key {key!r} but {value} stands for {owners[0]!r}")
        for w in wrong_texts:
            if w == owners[0]:
                fail.append(f"{tag}: distractor {w!r} is also the answer")
            if w not in mapping:
                fail.append(f"{tag}: distractor {w!r} is not a letter in this puzzle")
        # band 5's claim: the clue letter is in exactly one given word
        homes = sum(owners[0] in w for w, _ in pairs)
        if homes != 1:
            fail.append(f"{tag}: clue letter {owners[0]} appears in {homes} given words, "
                        f"so it is not the band-5 shape this pack claims")
    else:
        fail.append(f"{tag}: unrecognised question sentence {question!r}")
        continue

    if str(key) not in q["explanation"]:
        fail.append(f"{tag}: explanation does not state the answer {key}")
    if q["difficulty"] in (1, 2):
        fail.append(f"{tag}: bands 1 and 2 are excluded from this pack")
    if q["subtopic"] != "Number Codes":
        fail.append(f"{tag}: wrong subtopic {q['subtopic']!r}")

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")

dist = collections.Counter(positions)
run, longest = 1, 1
for a, b in zip(positions, positions[1:]):
    run = run + 1 if a == b else 1
    longest = max(longest, run)
cyclic = next((p for p in (2, 3, 4, 5)
               if all(positions[i] == positions[i % p] for i in range(len(positions)))), 0)
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
print(f"kinds: {dict(kinds)}")
print(f"variants solved from the stem: {dict(variants)}")
print(f"answer positions (0-indexed, {mcq_count} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"question types: {dict(collections.Counter(q['question_type'] for q in qs))}")
print(f"unique stems: {len(stems)} / {len(qs)}")
print(f"decode distractors using a letter the puzzle never showed: {outside_letters}")
mis = collections.Counter(o.get("misconception") for q in qs
                          for o in q.get("options", []) if not o.get("correct"))
print("distractor misconceptions:", dict(mis))

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
