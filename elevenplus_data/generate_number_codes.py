#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_09.json — 100 Number Codes.

    python3 elevenplus_data/generate_number_codes.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
That is the point of keeping this file: the pack is checkable rather than
merely reviewable. Check what comes out with its companion,
`check_number_codes.py`, which re-derives every letter's value from the
rendered stem — parsing the printed WORD = CODE pairs, not calling anything in
here — and then solves each question from that.

BANDS 1 AND 2 ARE NOT GENERATED
-------------------------------
`catalog/generators/verbal.py`'s NumberCode splits difficulty by target-word
length, but its `_TARGET_LEN` gives bands 1 and 2 the same 4-letter target, so
the two labels do not name two different levels of work — the only difference
is that band 2 may also ask for a decode. A pupil's weakness report treats a
band as a claim about how hard the question was, so this pack starts at band 3
rather than ship two bands whose labels are not carrying information.

What the three bands here do mean:

  band 3 — a 4-letter target, whole code asked for. One pass through the given
           words pins every letter, and the answer is read straight off.
  band 4 — a 5-letter target, and the decode direction appears: given a code,
           which word is it? That needs the mapping inverted, not just read.
  band 5 — a 6-letter target, and the single-letter clue ("which letter does 7
           stand for?"). There is no whole code to assemble and check against,
           and the clue letter is guaranteed to appear in exactly ONE of the
           three given words, so it has to be hunted for rather than met on the
           way past.

WHY EVERY QUESTION HAS EXACTLY ONE ANSWER
-----------------------------------------
Every word in the pool is spelled from the nine letters A D E I N O R S T and
never repeats a letter. Two consequences, and the whole guarantee rests on
them:

  * no repeated letter in a given word means its code can be read off position
    by position, so each given word pins one value per letter it contains;
  * the puzzle is only kept if every letter of the target already appears in
    the three given words. Once that holds, every letter the question needs is
    pinned by what the pupil was shown — there is no second mapping consistent
    with the same three pairs, so no second defensible answer.

Nine letters also means nine values are enough, so digits are drawn from 1-9
and 0 is never used: a code starting 0 invites a pupil to read it as a number
with a dropped leading zero rather than as a string of letter-values.

HOW DISTRACTORS STAY LIVE
-------------------------
Encode items get their distractors from named slips a pupil actually makes —
swapping two of the code's digits, reading the code backwards, or copying one
of the given words' codes — and those carry the matching misconception slug,
because the slug is the sentence the child reads. The fourth shape, giving one
letter another letter's value, is a real slip with no slug in taxonomy.json, so
it ships untagged rather than borrow one that does not describe it.

Decode items (which word? which letter?) are not tagged at all. Their
distractors are other real words of the same length, or other letters from the
same puzzle; picking one of those is not a named mistake, it is being wrong,
and a slug claiming otherwise would be a lie to the child. Where it can, the
generator prefers distractor words spelled only from letters the puzzle has
already shown, so the question cannot be answered by noticing that a word
contains a letter that never appeared.
"""
import json
import os
import random
import sys

rng = random.Random(20260912)

# Every word below is spelled from these nine letters and repeats none of them.
# See the module docstring: both properties are load-bearing, not tidiness.
ALPHABET = set("ADEINORST")

WORDS = {
    4: ["TEAR", "TIRE", "RIDE", "NOTE", "ROSE", "STAR", "RAID", "DATE", "SEAT",
        "OATS", "DIET", "DINE", "EARN", "IRON", "NEAR", "RAIN", "REST", "SAID",
        "SAND", "SENT", "SIDE", "SORT", "TIDE", "TONE", "TORN", "TRIO", "DOES",
        "DOTS", "ENDS", "NEST", "NODS", "OARS", "ONES", "RATS", "RODS", "SITE",
        "STIR", "TANS", "TEAS", "TIES", "TINS", "TOAD", "TOES", "DEAR", "DIRT",
        "EAST", "EDIT", "NOSE", "RIOT", "ROAD"],
    5: ["ARISE", "NOISE", "STAIN", "STONE", "STARE", "TRADE", "RESIN", "SEDAN",
        "RATIO", "ADORN", "DINER", "DRAIN", "IRONS", "NOTES", "ORATE", "RAISE",
        "RATES", "RIDES", "RINSE", "ROADS", "SAINT", "SNORE", "STAND", "STEAD",
        "STORE", "TEARS", "TIRES", "TONES", "TRAIN", "TREND", "TRIED", "TRIES",
        "ANTES", "ASIDE", "DATES", "DINES", "DOERS", "EARNS", "IDEAS", "NEARS",
        "ROAST", "SNORT"],
    6: ["STRAND", "RATION", "DONATE", "ORIENT", "ARDENT", "DETAIN", "ORNATE",
        "ATONES", "SENIOR", "STONED", "STRAIN", "TRAINS", "SORTED", "STORED",
        "ADORNS", "RETAIN", "RETINA", "RAISED", "RADIOS", "ADROIT", "SNORED",
        "SOARED"],
}

# One symbol per letter (nine letters -> nine symbols). "=" and ";" are
# excluded deliberately: the stem prints "WORD = code" and separates pairs with
# ";", so either would sit inside the puzzle's own punctuation.
SYMBOLS = ["#", "@", "%", "&", "*", "+", "!", "~", "^"]
DIGITS = [str(d) for d in range(1, 10)]

GROUPS = [
    {
        "group_ref": "G-NC-ENCODE",
        "instruction": (
            "In each question, some words are shown with their codes. The same letter "
            "always stands for the same number, in every word. Work out the code for "
            "the word you are asked about."
        ),
        "example": (
            "TEAR = 5832 and RIDE = 2498, so T = 5, E = 8, A = 3, R = 2, I = 4 and "
            "D = 9. Reading DATE letter by letter gives 9358."
        ),
    },
    {
        "group_ref": "G-NC-DECODE",
        "instruction": (
            "In each question, some words are shown with their codes. The same letter "
            "always stands for the same number, in every word. Work out which word, or "
            "which letter, the code you are asked about stands for."
        ),
        "example": (
            "TEAR = 5832 and RIDE = 2498, so 8 stands for E, and the code 9358 spells "
            "DATE."
        ),
    },
    {
        "group_ref": "G-NC-SYMBOL",
        "instruction": (
            "In each question, some words are shown with their codes. The same letter "
            "always stands for the same symbol, in every word. Work out the code for "
            "the word you are asked about."
        ),
        "example": (
            "TEAR = * ! % @ and RIDE = @ ~ ^ !, so T = *, E = !, A = %, R = @, I = ~ "
            "and D = ^. Reading DATE letter by letter gives ^ % * !."
        ),
    },
]


def join(units, is_symbol):
    return " ".join(units) if is_symbol else "".join(units)


def make_puzzle(length, is_symbol, clue_in_one_given=False):
    """Three given words and a target, all `length` letters, plus a mapping.

    Kept only if every letter of the target already appears in the three given
    words — see the module docstring. Returns None if this draw did not work,
    and the caller redraws.
    """
    pool = WORDS[length]
    target = rng.choice(pool)
    givens = rng.sample([w for w in pool if w != target], 3)
    covered = set("".join(givens))
    if not set(target) <= covered:
        return None
    letters = sorted(covered)
    values = rng.sample(SYMBOLS if is_symbol else DIGITS, len(letters))
    mapping = dict(zip(letters, values))
    if clue_in_one_given:
        # Band 5's letter clue: the letter asked about must appear in exactly
        # one of the three given words, so it has to be hunted for.
        singles = [c for c in letters if sum(c in w for w in givens) == 1]
        if not singles:
            return None
    return target, givens, mapping, letters


def code_of(word, mapping, is_symbol):
    return join([mapping[c] for c in word], is_symbol)


def pairs_text(givens, mapping, is_symbol):
    return "; ".join(f"{w} = {code_of(w, mapping, is_symbol)}" for w in givens)


def mapping_text(word, mapping):
    return ", ".join(f"{c} = {mapping[c]}" for c in word)


def encode_distractors(correct, target, givens, mapping, is_symbol):
    """Candidate (text, slug) pairs for an encode item, best first.

    Each is a value one named slip actually produces. The mis-mapped shape is
    real but has no slug in taxonomy.json, so it ships untagged.
    """
    units = correct.split(" ") if is_symbol else list(correct)
    cands = []

    swap_first = units[:]
    swap_first[0], swap_first[1] = swap_first[1], swap_first[0]
    cands.append((join(swap_first, is_symbol), "swapped-two-symbols-in-the-code"))

    swap_last = units[:]
    swap_last[-1], swap_last[-2] = swap_last[-2], swap_last[-1]
    cands.append((join(swap_last, is_symbol), "swapped-two-symbols-in-the-code"))

    cands.append((join(units[::-1], is_symbol), "read-the-code-in-reverse"))

    # One copied given, not three: all three are the same slip, and offering
    # them all would let that one misconception crowd out the others in the
    # shuffle below.
    cands.append((code_of(rng.choice(givens), mapping, is_symbol),
                  "copied-a-given-number-instead-of-solving"))

    # Give one letter another letter's value. The replacement must not already
    # be in the code: no letter repeats in these words, so a code with a
    # repeated digit is impossible and a pupil could rule it out without ever
    # decoding anything.
    for i in range(len(units)):
        others = [v for v in mapping.values() if v not in units]
        if not others:
            continue
        m = units[:]
        m[i] = rng.choice(others)
        cands.append((join(m, is_symbol), None))

    rng.shuffle(cands)
    out, seen = [], {correct}
    for text, slug in cands:
        if text in seen:
            continue
        seen.add(text)
        out.append((text, slug))
        if len(out) == 3:
            break
    return out if len(out) == 3 else None


def word_distractors(target, givens, letters, length):
    """Three other real words of the same length, preferring ones spelled only
    from letters the puzzle has already shown — otherwise a pupil could rule a
    word out for containing a letter that never appeared, without decoding."""
    pool = [w for w in WORDS[length] if w != target and w not in givens]
    inside = [w for w in pool if set(w) <= set(letters)]
    picks = rng.sample(inside, 3) if len(inside) >= 3 else None
    if picks is None:
        picks = rng.sample(pool, 3)
    return picks


def build_encode(target, givens, mapping, letters, is_symbol, difficulty, typed):
    correct = code_of(target, mapping, is_symbol)
    noun = "symbols" if is_symbol else "numbers"
    stem = (f"In a code, {pairs_text(givens, mapping, is_symbol)}. "
            f"What is the code for {target}?")
    explanation = (f"Each letter always stands for the same {noun[:-1]}: "
                   f"{mapping_text(target, mapping)}. Reading {target} letter by "
                   f"letter gives {correct}.")
    q = {
        "subtopic": "Number Codes",
        "question_type": "symbol-substitution" if is_symbol else "number-to-code",
        "group_ref": "G-NC-SYMBOL" if is_symbol else "G-NC-ENCODE",
        "stem": stem,
        "difficulty": difficulty,
        "explanation": explanation,
    }
    if typed:
        q["kind"] = "short_text"
        q["answer"] = correct
        q["accepted_alternatives"] = [" ".join(correct)] if not is_symbol else []
        return q
    wrong = encode_distractors(correct, target, givens, mapping, is_symbol)
    if wrong is None:
        return None
    q["kind"] = "mcq"
    q["_key"] = correct
    q["_wrong"] = wrong
    return q


def build_decode_word(target, givens, mapping, letters, difficulty):
    correct_code = code_of(target, mapping, False)
    stem = (f"In a code, {pairs_text(givens, mapping, False)}. "
            f"Which word has the code {correct_code}?")
    explanation = (f"Each letter always stands for the same number: "
                   f"{mapping_text(target, mapping)}. Reading {correct_code} back one "
                   f"number at a time spells {target}.")
    return {
        "subtopic": "Number Codes",
        "question_type": "code-to-number",
        "group_ref": "G-NC-DECODE",
        "stem": stem,
        "difficulty": difficulty,
        "explanation": explanation,
        "kind": "mcq",
        "_key": target,
        "_wrong": [(w, None) for w in word_distractors(target, givens, letters, len(target))],
    }


def build_letter_clue(target, givens, mapping, letters, difficulty, typed):
    singles = [c for c in letters if sum(c in w for w in givens) == 1]
    clue_letter = rng.choice(singles)
    clue_value = mapping[clue_letter]
    home = next(w for w in givens if clue_letter in w)
    stem = (f"In a code, {pairs_text(givens, mapping, False)}. "
            f"Which letter does {clue_value} stand for?")
    explanation = (f"{clue_value} appears in the code for {home}, in the same place as "
                   f"the letter {clue_letter}, so {clue_value} stands for {clue_letter}.")
    q = {
        "subtopic": "Number Codes",
        "question_type": "code-to-number",
        "group_ref": "G-NC-DECODE",
        "stem": stem,
        "difficulty": difficulty,
        "explanation": explanation,
    }
    if typed:
        q["kind"] = "short_text"
        q["answer"] = clue_letter
        q["accepted_alternatives"] = []
        return q
    others = [c for c in letters if c != clue_letter]
    q["kind"] = "mcq"
    q["_key"] = clue_letter
    q["_wrong"] = [(c, None) for c in rng.sample(others, 3)]
    return q


# The batch: (count, difficulty, builder tag, typed).
PLAN = [
    (12, 3, "encode-digit", False),
    (8, 3, "encode-digit", True),
    (15, 3, "encode-symbol", False),
    (6, 4, "encode-digit", False),
    (4, 4, "encode-digit", True),
    (12, 4, "encode-symbol", False),
    (13, 4, "decode-word", False),
    (10, 5, "encode-symbol", False),
    (10, 5, "decode-word", False),
    (2, 5, "letter-clue", False),
    (8, 5, "letter-clue", True),
]
LENGTH = {3: 4, 4: 5, 5: 6}


def draw(tag, difficulty, typed):
    length = LENGTH[difficulty]
    is_symbol = tag == "encode-symbol"
    for _ in range(4000):
        puzzle = make_puzzle(length, is_symbol, clue_in_one_given=(tag == "letter-clue"))
        if puzzle is None:
            continue
        target, givens, mapping, letters = puzzle
        if tag in ("encode-digit", "encode-symbol"):
            q = build_encode(target, givens, mapping, letters, is_symbol, difficulty, typed)
        elif tag == "decode-word":
            q = build_decode_word(target, givens, mapping, letters, difficulty)
        else:
            q = build_letter_clue(target, givens, mapping, letters, difficulty, typed)
        if q is not None:
            return q
    raise SystemExit(f"could not draw a {tag} at band {difficulty}")


def key_positions(n):
    """An even spread of key positions with no long run and no cycle.

    rebalance_keys.py would fix a bad spread after the fact; doing it here
    means the committed pack is right the first time and that step has nothing
    to do.
    """
    base = [0, 1, 2, 3] * (n // 4) + list(range(n % 4))
    while True:
        rng.shuffle(base)
        if all(base[i] != base[i + 1] or base[i + 1] != base[i + 2]
               for i in range(len(base) - 2)):
            return base


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_09.json")

    questions, seen_stems = [], set()
    for count, difficulty, tag, typed in PLAN:
        made = 0
        while made < count:
            q = draw(tag, difficulty, typed)
            if q["stem"] in seen_stems:
                continue
            seen_stems.add(q["stem"])
            questions.append(q)
            made += 1

    rng.shuffle(questions)

    mcqs = [q for q in questions if q["kind"] == "mcq"]
    for q, pos in zip(mcqs, key_positions(len(mcqs))):
        wrong = list(q.pop("_wrong"))
        key = q.pop("_key")
        opts = [{"text": t, "correct": False, **({"misconception": s} if s else {})}
                for t, s in wrong]
        opts.insert(pos, {"text": key, "correct": True})
        q["options"] = opts

    for i, q in enumerate(questions, start=1):
        q_ordered = {"number": str(i), "ref": f"PRASH-VR-{800 + i:04d}"}
        q_ordered.update(q)
        questions[i - 1] = q_ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-09",
            "is_placeholder": False,
        },
        "groups": GROUPS,
        "questions": questions,
    }
    with open(out_path, "w") as fh:
        json.dump(pack, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {out_path}: {len(questions)} questions")


if __name__ == "__main__":
    main()
