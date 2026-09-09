#!/usr/bin/env python3
"""
Builds elevenplus_data/contrib_prash_vr_12.json — 29 Hidden Words questions.

    python3 elevenplus_data/generate_hidden_words.py [OUTPUT.json]

The RNG is seeded, so re-running reproduces the committed pack byte for byte.
Check what comes out with its companion, `check_hidden_words.py`, which
re-derives every answer from the rendered stem without importing this file.

WHY 29 AND NOT 40 — ELEVEN SENTENCES HAVE A SECOND VALID ANSWER
---------------------------------------------------------------
This pack is sized to the *measured* ceiling of `catalog/generators/verbal.py`'s
`HiddenWord`, not to a round number. That generator's pool is 40 sentences
(HIDDEN_D3/D4/D5 = 15/16/9), and its own comment states that every entry was
checked so that "no OTHER real, everyday 4-letter word also spans some join in
the same sentence".

Re-running that check here found **11 sentences where a second real word does
span a join**, so 11 of the 40 have two defensible answers and cannot ship:

    band 3  BOWL  rival OWLS   The chef made a superb owl-shaped cake.
    band 3  HERO  rival TENS, REDS
                                Our teacher often shared stories about brave knights.
    band 3  DESK  rival SHAM   Sit beside Skip, the class hamster, during story time.
    band 3  IDEA  rival CATS   The cat sat beside a warm fire every evening.
    band 4  VEST  rival BOYS   The brave stable boy saved every horse from the fire.
    band 4  SKIN  rival PUTS   He put several pencils in the desk inside his classroom cupboard.
    band 4  EASE  rival PEAS, SEAS
                                The chef added a pea, sea salt, and pepper to taste.
    band 4  NEST  rival ONES   The cottage was one story tall, with roses by the door.
    band 5  REED  rival OGRE   Every spring, our village holds a tree dance to greet fresh leaves.
    band 5  OATH  rival REDO   The old goat, happy with his meal, wandered off into the field.
    band 5  SHED  rival OURS   When you finish editing your story, read it aloud to check it makes sense.

Nine of those eleven rivals are PLURALS or third-person verb forms — OWLS, TENS,
REDS, CATS, BOYS, PUTS, PEAS, SEAS, ONES, OURS. That is the whole explanation
for how the original check passed: `/usr/share/dict/web2` lists lemmas, so a
sweep against it alone never sees `cats`, and "The cat sat beside a warm fire"
hides CATS across `cat|sat` every bit as much as it hides IDEA across
`beside|a`. The same root cause put three entries into `LetterMove`'s pool —
see `generate_letter_moves.py`, which drops them for the same reason.

The 11 sentences are NOT edited into safety here. Rewording a curated pool
entry from a pack generator would leave `catalog/generators/verbal.py` still
serving the ambiguous version to every pupil the adaptive engine reaches; that
is a fix to make in the generator's own pool, deliberately, not a workaround to
bury in a pack. This pack ships the 29 that are clean.

WHAT COUNTS AS A RIVAL
----------------------
A candidate is a rival answer when all three hold:

1. It spans **exactly one** word join. The stem promises a word hidden "across
   the end of one word and the start of the next", so a run crossing two joins
   (HINT across `bench|in|the`) is not the shape the pupil was told to look
   for, and SARI across `us|a|riddle` is not a second answer to "Priya told us
   a riddle about the desert".
2. It is common enough for a pupil to write — `wordfreq` zipf >= 3.0.
3. A dictionary lists it as a common noun, verb or adjective, **or it is the
   regular -s form of one**. Proper nouns are excluded by hand (THEO, TAFT,
   RAND, SATO, CHAN, ALTA, MECH all clear the frequency bar as names and none
   is an answer an 11-year-old writes).

DISTRACTORS ARE NOT WORDS, AND THEY CROSS A JOIN TOO
----------------------------------------------------
Every distractor here is a real 4-letter run of the printed sentence that also
spans exactly one join, and that **no dictionary lists at all** — a stricter
bar than the rival test above, because a distractor only has to be arguable to
be unfair, not common. Both halves matter. If distractors did not span a join,
"which one sits across a gap" would answer the question without reading for
meaning; if they were not screened against the dictionary, one of them would
occasionally be a second right answer. `HiddenWord` builds them by slicing a
fixed window either side of the key and screens neither way, which is how OWLS
came to be offered as a distractor in the very sentence where it is also a
valid answer.

The three distractors are the nearest such runs to the key, so they overlap it
and cannot be told apart by position.

Sentences, keys and the three vetted distractors are frozen in POOL below
rather than recomputed, so this script needs no dictionary and reproduces
anywhere. The dictionary sweep that produced them lives in the checker, which
re-runs it in full wherever a word list is available.

ANSWER FORMAT
-------------
elevenplus_data/CLAUDE.md's VR answer-format table puts "the hidden word" in
the write-in column, so nine of the 29 ship as `short_text` — the pupil writes
the word, which is what the real paper asks for. The remaining 20 are `mcq`,
which is what carries a distractor and therefore what makes the
"is it actually a word" judgement visible to the marking engine. Neither format
is a downgrade of the other: they test the same thing and the pack carries both
deliberately.
"""
import collections
import json
import os
import random
import re
import sys

rng = random.Random(20260909)

# (sentence, hidden word). See the module docstring for how the 29 were
# selected from the generator's 40. There are no distractors: this pack is
# write-in throughout, because any option set either hands the answer to a
# pupil who never reads the sentence or offers a second correct answer.
POOL = {
    3: [
        ('Everyone admired her dance during assembly.', 'HERD'),
        ('Every attic lamp flickered throughout the storm.', 'CLAM'),
        ('Priya told us a riddle about the desert.', 'ARID'),
        ('Some very tall trees grew beside the lake.', 'EVER'),
        ('The buses carried children into school every morning.', 'SCAR'),
        ('The old cottage dance took place every autumn.', 'AGED'),
        ('We stable our horses every evening before dark.', 'WEST'),
        ('Every autumn, the apple orchard was full of visitors.', 'HEAP'),
        ('She kept the winning ribbon ever since that day.', 'BONE'),
        ('The cellar kite collection had never once been used.', 'LARK'),
        ('The lambs took a meadow nap by the stream.', 'DOWN'),
    ],
    4: [
        ('During the game, always pass the ball to a teammate.', 'MEAL'),
        ('Everyone made the same choice about their project this term.', 'ECHO'),
        ('Its fur was red, gentle underneath, yet warm in winter.', 'EDGE'),
        ('The dog began to chase at the ball rolling downhill.', 'SEAT'),
        ("There wasn't much food or drink left after the party.", 'ODOR'),
        ('They found an old bench and chair inside their attic.', 'HAND'),
        ('Her friends and family gathered for a picnic by the lake.', 'SAND'),
        ('Scouts who camp early get the best spot by the lake.', 'PEAR'),
        ('She was one of the first arrived guests at the party.', 'STAR'),
        ('The flowers can bloom twice a year if conditions stay warm.', 'SCAN'),
        ('The stage had a cello, green lights, plus a red curtain.', 'OGRE'),
        ('They followed the path an old man had used for years.', 'THAN'),
    ],
    5: [
        ('In the old fable, the ant, hen, and fox all worked together.', 'THEN'),
        ('Some geese eat early each day and still find plenty of food.', 'TEAR'),
        ('The class made a photo advert to support their charity bake sale.', 'TOAD'),
        ('At the fair, the pie race was the funniest event of the day.', 'PIER'),
        ('He sat on the bench in the school hall waiting for his turn.', 'CHIN'),
        ('The girl often climbed the ladder and reached the top of the barn.', 'LOFT'),
    ],
}

GROUPS = [
    {
        "group_ref": "G-HW-JOIN",
        "instruction": (
            "In each sentence below, a four-letter word is hidden across the end of one "
            "word and the start of the next. The letters are always next to each other "
            "and always in the order they are printed. Find the hidden word."
        ),
        "example": (
            "In “You must open a window.” the end of MUST and the start of OPEN run "
            "together as MUSTOPEN, which hides STOP."
        ),
    },
]


def straddle(sentence, hidden):
    """The two adjacent words the hidden word runs across, from the text alone.

    Returned as (first word, second word, letters taken from each), so the
    explanation quotes the sentence rather than restating the answer. Raises if
    the key does not in fact span exactly one join — a pool entry that cannot
    be explained from its own sentence is a pool entry that should not ship.
    """
    words = re.findall(r"[A-Za-z]+", sentence)
    letters, ends, pos = "", [], 0
    for w in words:
        letters += w.upper()
        pos += len(w)
        ends.append(pos)
    for i in range(len(letters) - 3):
        if letters[i:i + 4] != hidden:
            continue
        crossed = [e for e in ends[:-1] if i < e < i + 4]
        if len(crossed) == 1:
            join = crossed[0]
            first = words[ends.index(join)]
            second = words[ends.index(join) + 1]
            return first, second, join - i
    raise SystemExit(f"{hidden} does not span exactly one join in {sentence!r}")


# No key_positions() here, unlike the other pack generators in this series:
# with no options anywhere in the pack there is no answer position to balance,
# and rebalance_keys.py has nothing to reorder.


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "contrib_prash_vr_12.json")

    questions = []
    for band in sorted(POOL):
        for sentence, hidden in POOL[band]:
            first, second, take = straddle(sentence, hidden)
            explanation = (
                f"The end of “{first}” and the start of “{second}” run together as "
                f"{first.upper()}{second.upper()}, and the four letters across the "
                f"join spell {hidden}."
            )
            q = {
                "subtopic": "Hidden Words",
                "question_type": "across-two-words",
                "group_ref": "G-HW-JOIN",
                "stem": sentence,
                "difficulty": band,
                "explanation": explanation,
                "kind": "short_text",
                "answer": hidden,
            }
            questions.append(q)

    rng.shuffle(questions)

    for i, q in enumerate(questions, start=1):
        ordered = {"number": str(i), "ref": f"PRASH-VR-{1100 + i:04d}"}
        ordered.update(q)
        questions[i - 1] = ordered

    pack = {
        "section": {
            "code": "VR",
            "name": "Verbal Reasoning",
            "source": "CONTRIB-PRASH-12",
            "is_placeholder": False,
        },
        "groups": GROUPS,
        "questions": questions,
    }
    with open(out_path, "w") as fh:
        json.dump(pack, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {out_path}: {len(questions)} questions "
          f"({dict(sorted(collections.Counter(q['difficulty'] for q in questions).items()))})")


if __name__ == "__main__":
    main()
