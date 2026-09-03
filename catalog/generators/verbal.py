"""
Verbal Reasoning generators.

VR is more algorithmic than it looks: codes, letter sequences and hidden words are
pure string manipulation, and analogies and odd-one-out need only a curated set of
word groups plus combinatorics. The word data below is ordinary English vocabulary
chosen for this purpose — nothing is lifted from a published paper.

Each generator names one canonical VR subtopic from elevenplus_data/taxonomy.json.
Eight of the taxonomy's 24 are covered here; the rest are pack territory. Question
forms that used to share a subtopic — codes with letter sequences, hidden words
with compound words — are now filed separately, because the taxonomy separates
them and a pupil weak on one is not necessarily weak on the other.

HIDDEN and NumberSequence's rule shapes were checked against 10 real VR papers
(Owl Tutors, GL Assessment, CGP, Bond/OUP) as working notes in plans.md's VR
generator coverage entry before being built/reworked. The wording and numbers
below are still original: only the *shape* (always a 4-letter word spanning a
two-word join; the sequence rule types that recur across publishers) came from
that check, never specific sentences or number lines.
"""
import string

from . import Generator, Item, register, shuffled_options

ALPHABET = string.ascii_uppercase

# Semantic groups for odd-one-out. Each entry: (category, members, foils) where a
# foil is a plausible near-member from a neighbouring category — "ivy" among trees
# rather than "hammer", so the question needs a reason and not just a glance.
GROUPS = [
    ("trees", ["oak", "birch", "willow", "beech", "sycamore", "rowan"],
     ["ivy", "bracken", "moss"]),
    ("mammals", ["otter", "badger", "hare", "fox", "stoat", "hedgehog"],
     ["heron", "adder", "newt"]),
    ("instruments", ["violin", "cello", "viola", "harp"], ["trumpet", "flute", "drum"]),
    ("cutlery", ["fork", "spoon", "knife", "ladle"], ["saucer", "kettle", "jug"]),
    ("weather", ["drizzle", "sleet", "hail", "downpour"], ["breeze", "frost", "haze"]),
    ("buildings", ["cottage", "bungalow", "chalet", "cabin"], ["barn", "chapel", "kiosk"]),
    ("fruit", ["plum", "damson", "greengage", "apricot"], ["walnut", "marrow", "swede"]),
    ("boats", ["canoe", "kayak", "punt", "dinghy"], ["sledge", "carriage", "glider"]),
]

# Analogy pairs by relation type. Difficulty rises as the relation gets less
# concrete: worn-on and part-of are visible, whereas degree and function are not.
ANALOGIES = [
    ("worn on", [("foot", "shoe"), ("hand", "glove"), ("head", "hat"), ("neck", "scarf")]),
    ("young of", [("dog", "puppy"), ("cat", "kitten"), ("horse", "foal"), ("sheep", "lamb")]),
    ("home of", [("bee", "hive"), ("bird", "nest"), ("fox", "earth"), ("rabbit", "burrow")]),
    ("part of", [("petal", "flower"), ("page", "book"), ("spoke", "wheel"), ("rung", "ladder")]),
    ("tool of", [("brush", "painter"), ("chisel", "sculptor"), ("baton", "conductor"),
                 ("trowel", "gardener")]),
    ("greater degree", [("warm", "scorching"), ("cool", "freezing"), ("damp", "sodden"),
                        ("large", "colossal")]),
    ("opposite", [("ancient", "modern"), ("scarce", "plentiful"), ("reluctant", "eager"),
                  ("shallow", "profound")]),
]

# Sentences with a word hidden across a word boundary. Built by hand because the
# join has to read naturally — an automated search produces sentences no one would
# write. (sentence, hidden word)
#
# Every entry is verified programmatically (not just read by eye) against the
# shape real papers use: the hidden word is always exactly 4 letters, always a
# real dictionary word, and always spans the join of two adjacent words rather
# than sitting inside one — see elevenplus_data-adjacent working notes. Split
# into three difficulty tiers by sentence length/vocabulary, since the papers'
# difficulty axis is the sentence, not the hidden-word mechanism itself, which
# stays constant across all three tiers.
# Every entry below is checked programmatically against three things: the
# hidden word is a real word spanning a two-word join (not sitting inside one
# word), and — the check the first draft of this pool missed — no OTHER real,
# everyday 4-letter word also spans some join in the same sentence. Several
# early drafts here failed that third check (e.g. a "crop"/"early" join that
# spelled both the intended PEAR and an equally valid ROPE at a different
# offset) and were rewritten until they passed. See plans.md's VR generator
# coverage entry for the verification script.
HIDDEN_D3 = [
    ("Everyone admired her dance during assembly.", "HERD"),
    ("Every attic lamp flickered throughout the storm.", "CLAM"),
    ("The chef made a superb owl-shaped cake.", "BOWL"),
    ("Our teacher often shared stories about brave knights.", "HERO"),
    ("Priya told us a riddle about the desert.", "ARID"),
    ("Some very tall trees grew beside the lake.", "EVER"),
    ("The buses carried children into school every morning.", "SCAR"),
    ("The old cottage dance took place every autumn.", "AGED"),
    ("We stable our horses every evening before dark.", "WEST"),
    ("Every autumn, the apple orchard was full of visitors.", "HEAP"),
    ("She kept the winning ribbon ever since that day.", "BONE"),
    ("Sit beside Skip, the class hamster, during story time.", "DESK"),
    ("The cat sat beside a warm fire every evening.", "IDEA"),
    ("The cellar kite collection had never once been used.", "LARK"),
    ("The lambs took a meadow nap by the stream.", "DOWN"),
]
HIDDEN_D4 = [
    ("During the game, always pass the ball to a teammate.", "MEAL"),
    ("Everyone made the same choice about their project this term.", "ECHO"),
    ("Its fur was red, gentle underneath, yet warm in winter.", "EDGE"),
    ("The brave stable boy saved every horse from the fire.", "VEST"),
    ("The dog began to chase at the ball rolling downhill.", "SEAT"),
    ("There wasn't much food or drink left after the party.", "ODOR"),
    ("They found an old bench and chair inside their attic.", "HAND"),
    ("He put several pencils in the desk inside his classroom cupboard.", "SKIN"),
    ("Her friends and family gathered for a picnic by the lake.", "SAND"),
    ("Scouts who camp early get the best spot by the lake.", "PEAR"),
    ("She was one of the first arrived guests at the party.", "STAR"),
    ("The chef added a pea, sea salt, and pepper to taste.", "EASE"),
    ("The cottage was one story tall, with roses by the door.", "NEST"),
    ("The flowers can bloom twice a year if conditions stay warm.", "SCAN"),
    ("The stage had a cello, green lights, plus a red curtain.", "OGRE"),
    ("They followed the path an old man had used for years.", "THAN"),
]
HIDDEN_D5 = [
    ("Every spring, our village holds a tree dance to greet fresh leaves.", "REED"),
    ("In the old fable, the ant, hen, and fox all worked together.", "THEN"),
    ("Some geese eat early each day and still find plenty of food.", "TEAR"),
    ("The class made a photo advert to support their charity bake sale.", "TOAD"),
    ("The old goat, happy with his meal, wandered off into the field.", "OATH"),
    ("At the fair, the pie race was the funniest event of the day.", "PIER"),
    ("He sat on the bench in the school hall waiting for his turn.", "CHIN"),
    ("The girl often climbed the ladder and reached the top of the barn.", "LOFT"),
    ("When you finish editing your story, read it aloud to check it makes sense.", "SHED"),
]
HIDDEN = HIDDEN_D3 + HIDDEN_D4 + HIDDEN_D5

COMPOUNDS = [
    ("rain", ["bow", "coat", "fall", "drop"]),
    ("foot", ["path", "ball", "print", "step"]),
    ("day", ["light", "break", "dream", "time"]),
    ("night", ["fall", "mare", "gown", "time"]),
    ("book", ["case", "mark", "shelf", "worm"]),
    ("sun", ["flower", "rise", "shine", "set"]),
]


@register
class LetterCode(Generator):
    slug = "vr.code"
    section, subtopic = "VR", "Letter Codes"
    template_id = "letter-shift-code"

    def build(self, rng, difficulty):
        # DIFFICULTY: a +1 shift is spotted instantly; larger shifts, backwards
        # shifts and alternating shifts each add a step of reasoning.
        words = ["CAT", "DOG", "TREE", "LAMP", "BIRD", "STONE", "RIVER", "CANDLE"]
        word = rng.choice([w for w in words if len(w) <= 3 + difficulty])
        shift = {1: 1, 2: 2, 3: -1, 4: 3, 5: -2}[difficulty]
        alternating = difficulty == 5

        def encode(w):
            out = []
            for i, ch in enumerate(w):
                s = shift * (1 if not alternating or i % 2 == 0 else -1)
                out.append(ALPHABET[(ALPHABET.index(ch) + s) % 26])
            return "".join(out)

        example = rng.choice([w for w in words if w != word and len(w) <= 4])
        correct = encode(word)
        return Item(
            stem=(f"If {example} is written in code as {encode(example)}, "
                  f"how is {word} written in the same code?"),
            options=shuffled_options(rng, correct, [
                "".join(ALPHABET[(ALPHABET.index(c) - shift) % 26] for c in word),
                "".join(ALPHABET[(ALPHABET.index(c) + shift + 1) % 26] for c in word),
                word[::-1],
            ]),
            difficulty=difficulty,
            params={"word": word, "shift": shift, "alt": alternating},
            explanation=(f"Each letter moves {abs(shift)} place"
                         f"{'s' if abs(shift) != 1 else ''} "
                         f"{'forward' if shift > 0 else 'back'} in the alphabet"
                         f"{', alternating direction' if alternating else ''}, "
                         f"giving {correct}."),
            misconceptions={
                "".join(ALPHABET[(ALPHABET.index(c) - shift) % 26] for c in word):
                    "shifted-the-wrong-way",
            },
        )


@register
class LetterSequence(Generator):
    slug = "vr.letterseq"
    section, subtopic = "VR", "Letter Sequences"
    template_id = "letter-sequence"

    def build(self, rng, difficulty):
        # DIFFICULTY: a constant step, then a larger one, then two interleaved
        # sequences — the last is the standard 11+ "letter pairs" item.
        step = {1: 1, 2: 2, 3: 3, 4: -2, 5: 2}[difficulty]
        start = rng.randrange(0, 14)
        if difficulty == 5:
            second = rng.randrange(0, 14)
            pairs = [f"{ALPHABET[(start + i * step) % 26]}{ALPHABET[(second + i * 3) % 26]}"
                     for i in range(4)]
            correct = f"{ALPHABET[(start + 4 * step) % 26]}{ALPHABET[(second + 12) % 26]}"
            shown = ", ".join(pairs)
            wrong = [f"{ALPHABET[(start + 4 * step) % 26]}{ALPHABET[(second + 9) % 26]}",
                     f"{ALPHABET[(start + 5 * step) % 26]}{ALPHABET[(second + 12) % 26]}",
                     pairs[0]]
        else:
            start = max(start, 6) if step < 0 else start
            letters = [ALPHABET[(start + i * step) % 26] for i in range(5)]
            correct = ALPHABET[(start + 5 * step) % 26]
            shown = ", ".join(letters)
            wrong = [ALPHABET[(start + 5 * step + 1) % 26],
                     ALPHABET[(start + 4 * step) % 26],
                     ALPHABET[(start - step) % 26]]
        return Item(
            stem=f"What comes next in this sequence?  {shown}, ___",
            options=shuffled_options(rng, correct, wrong),
            difficulty=difficulty,
            params={"start": start, "step": step, "d": difficulty},
            explanation=(f"The letters move {abs(step)} place"
                         f"{'s' if abs(step) != 1 else ''} "
                         f"{'forward' if step > 0 else 'back'} each time"
                         + (", with the second letter following its own pattern."
                            if difficulty == 5 else ".")),
        )


@register
class OddOneOut(Generator):
    slug = "vr.oddoneout"
    section, subtopic = "VR", "Odd One Out"
    template_id = "odd-one-out"
    difficulties = (1, 2, 3, 4)

    def build(self, rng, difficulty):
        category, members, foils = rng.choice(GROUPS)
        # DIFFICULTY: more members to hold in mind, and at the top end the odd one
        # is a near-neighbour rather than obviously unrelated.
        n = {1: 3, 2: 3, 3: 4, 4: 4}[difficulty]
        if len(members) < n:
            return None
        chosen = rng.sample(members, n)
        odd = rng.choice(foils if difficulty >= 3 else foils[:1])
        words = chosen + [odd]
        rng.shuffle(words)
        return Item(
            stem=f"Which is the odd one out?  {', '.join(words)}",
            options=shuffled_options(rng, odd, chosen[:3]),
            difficulty=difficulty,
            params={"category": category, "words": sorted(words)},
            explanation=(f"{', '.join(chosen)} are all {category}. "
                         f"{odd.capitalize()} is not."),
        )


@register
class Analogy(Generator):
    slug = "vr.analogy"
    section, subtopic = "VR", "Word Analogies"
    template_id = "word-analogy"

    def build(self, rng, difficulty):
        # DIFFICULTY: concrete relations first (worn-on, young-of), abstract last
        # (degree, opposite) — the relation type IS the difficulty.
        pool = {1: ANALOGIES[:2], 2: ANALOGIES[:3], 3: ANALOGIES[2:5],
                4: ANALOGIES[4:6], 5: ANALOGIES[5:]}[difficulty]
        relation, pairs = rng.choice(pool)
        if len(pairs) < 2:
            return None
        (a1, b1), (a2, b2) = rng.sample(pairs, 2)
        others = [p for r, ps in ANALOGIES if r != relation for p in ps]
        distractors = [w for _, w in rng.sample(others, 3)]
        return Item(
            stem=f"{a1.capitalize()} is to {b1} as {a2} is to ______?",
            options=shuffled_options(rng, b2, distractors),
            difficulty=difficulty,
            params={"relation": relation, "pair": [a2, b2]},
            explanation=(f"The relationship is “{relation}”: a {b1} is {relation} "
                         f"a {a1}, so the answer is {b2}."),
        )


@register
class CompoundWord(Generator):
    slug = "vr.compound"
    section, subtopic = "VR", "Compound Words"
    template_id = "compound-word"
    difficulties = (1, 2, 3)

    def build(self, rng, difficulty):
        head, tails = rng.choice(COMPOUNDS)
        correct = rng.choice(tails)
        others = [t for h, ts in COMPOUNDS if h != head for t in ts]
        return Item(
            stem=(f"Which word makes a new word when placed after “{head}”?  "
                  f"({head}____)"),
            options=shuffled_options(rng, correct, rng.sample(others, 3)),
            difficulty=difficulty,
            params={"head": head, "tail": correct},
            explanation=f"“{head}{correct}” is a word; the others do not join to “{head}”.",
        )


@register
class HiddenWord(Generator):
    slug = "vr.hidden"
    section, subtopic = "VR", "Hidden Words"
    template_id = "hidden-word"
    difficulties = (3, 4, 5)

    def build(self, rng, difficulty):
        # DIFFICULTY: the hidden-word mechanism never changes — real papers vary
        # sentence length and vocabulary instead, so that's what the three tiers
        # below track (see HIDDEN_D3/D4/D5).
        pool = {3: HIDDEN_D3, 4: HIDDEN_D4, 5: HIDDEN_D5}[difficulty]
        sentence, hidden = rng.choice(pool)
        letters = "".join(c for c in sentence.upper() if c.isalpha())
        # Distractors are real substrings of the sentence that are NOT words, so
        # the pupil has to check meaning rather than just spot a run of letters.
        idx = letters.find(hidden)

        def window(offset):
            # Always a full 4-character slice, clamped to stay in bounds —
            # a plain idx-N slice near the start of the sentence (idx==0, the
            # first two words) used to truncate to 1-2 characters and could
            # produce a distractor shorter than the "4-letter word" the stem
            # itself promises.
            start = max(0, min(idx + offset, len(letters) - 4))
            return letters[start:start + 4]

        near = [window(-4), window(-2), window(1), window(3), window(5)]
        return Item(
            stem=(f"A {len(hidden)}-letter word is hidden across the end of one word "
                  f"and the start of the next. Find it:  “{sentence}”"),
            options=shuffled_options(rng, hidden, [n for n in near if n and n != hidden]),
            difficulty=difficulty,
            params={"sentence": sentence},
            question_type="across-two-words",
            explanation=f"The letters run together to give {hidden}.",
        )


@register
class LogicOrdering(Generator):
    slug = "vr.logic"
    section, subtopic = "VR", "Scenario Deduction"
    template_id = "ordering-puzzle"

    def build(self, rng, difficulty):
        # DIFFICULTY: the number of people to order. Clues are generated FROM a
        # known ordering and then shuffled, so the puzzle is always solvable and
        # always has exactly one answer — the failure mode of hand-written logic
        # puzzles is an under-constrained one with two valid solutions.
        n = {1: 3, 2: 4, 3: 4, 4: 5, 5: 5}[difficulty]
        people = rng.sample(
            ["Priya", "Jack", "Nia", "Omar", "Leo", "Zara", "Ben", "Mia"], n)
        order = people[:]          # index 0 finishes first
        clues = [f"{order[i]} finishes ahead of {order[i + 1]}" for i in range(n - 1)]
        clues.append(f"{order[-1]} finishes last")
        rng.shuffle(clues)
        place = rng.randrange(n)
        ordinal = ["first", "second", "third", "fourth", "fifth"][place]
        return Item(
            stem=(f"{n} friends run a race. " + ". ".join(clues) + ". "
                  f"Who finishes {ordinal}?"),
            options=shuffled_options(rng, order[place],
                                     [p for p in people if p != order[place]][:3]),
            difficulty=difficulty,
            params={"order": order, "place": place},
            explanation=(f"Putting the clues together the order is "
                         f"{', '.join(order)} — so {order[place]} is {ordinal}."),
        )


@register
class NumberSequence(Generator):
    slug = "vr.numseq"
    section, subtopic = "VR", "Number Sequences"
    template_id = "number-sequence"

    def build(self, rng, difficulty):
        # DIFFICULTY: a fixed step, then a bigger/negative one, then a step that
        # itself changes, then multiply/divide (or two operations per step), then
        # two interleaved sequences — the same shape as vr.letterseq, and it maps
        # onto the five Number Sequences question types already named in
        # taxonomy.json (constant-difference / changing-difference /
        # multiplicative / two-step-rule / alternating). Real papers show several
        # rule types this doesn't cover yet (Fibonacci-like recurrence, special
        # number families) — those have no taxonomy slot yet, so they're left for
        # when that gap is addressed rather than forced in here without one.
        if difficulty == 1:
            return self._constant(rng, difficulty, step_range=(1, 4),
                                   start_range=(1, 20), allow_negative=False)
        if difficulty == 2:
            return self._constant(rng, difficulty, step_range=(5, 12),
                                   start_range=(20, 120), allow_negative=True)
        if difficulty == 3:
            return self._changing(rng, difficulty)
        if difficulty == 4:
            build = rng.choice([self._multiplicative, self._two_step])
            return build(rng, difficulty)
        return self._alternating(rng, difficulty)

    def _constant(self, rng, difficulty, step_range, start_range, allow_negative):
        step = rng.randint(*step_range)
        start = rng.randint(*start_range)
        if allow_negative and rng.random() < 0.5:
            step = -step
            # Same real-papers constraint as _changing(): descending sequences
            # never run past zero. A start drawn from start_range wasn't
            # guaranteed to survive 5 steps of descent (it wasn't sized with
            # this branch in mind), so give it enough headroom instead.
            start = 5 * abs(step) + rng.randint(0, 20)
        terms = [start + i * step for i in range(5)]
        correct = start + 5 * step
        # Candidates, not all distinct: overshoot/undershoot by a step, double
        # the step, and repeat the last shown term (terms[-1] == correct - step,
        # so it's a guaranteed duplicate of one candidate below — that's fine,
        # shuffled_options dedupes and there's margin left over).
        wrong = [correct + step, correct - step, correct + 2 * step, terms[-1]]
        return Item(
            stem=f"What comes next in this sequence?  {', '.join(map(str, terms))}, ___",
            options=shuffled_options(rng, correct, wrong),
            difficulty=difficulty,
            params={"kind": "constant", "start": start, "step": step},
            question_type="constant-difference",
            explanation=(f"Each number is {abs(step)} more than the last"
                         if step > 0 else
                         f"Each number is {abs(step)} less than the last") + f", giving {correct}.",
        )

    def _changing(self, rng, difficulty):
        d0 = rng.randint(1, 5)
        dstep = rng.randint(1, 3)
        if rng.random() < 0.4:
            d0, dstep = -d0, -dstep
            # The one real descending example seen (VR3 Q5: 100, 90, _, 40, 0)
            # runs down to exactly zero and no further — never negative. Pick a
            # start with just enough headroom that every term, including the
            # one being asked for, stays at or above zero.
            drop = 5 * d0 + 10 * dstep      # negative: total fall over 5 steps
            start = -drop + rng.randint(0, 20)
        else:
            start = rng.randint(1, 30)
        terms = [start]
        diff = d0
        for _ in range(4):
            terms.append(terms[-1] + diff)
            diff += dstep
        correct = terms[-1] + diff
        wrong = [terms[-1] + (diff - dstep), correct + dstep, terms[-1]]
        return Item(
            stem=f"What comes next in this sequence?  {', '.join(map(str, terms))}, ___",
            options=shuffled_options(rng, correct, wrong),
            difficulty=difficulty,
            params={"kind": "changing", "start": start, "d0": d0, "dstep": dstep},
            question_type="changing-difference",
            explanation=(f"The gap between each number changes by {abs(dstep)} "
                         f"each time, so the last gap of {abs(diff - dstep)} becomes "
                         f"{abs(diff)}, giving {correct}."),
        )

    def _multiplicative(self, rng, difficulty):
        ratio = rng.choice([2, 3])
        divide = rng.random() < 0.5
        if divide:
            start = ratio ** 5 * rng.randint(1, 3)
            terms = [start]
            for _ in range(4):
                terms.append(terms[-1] // ratio)
            correct = terms[-1] // ratio
        else:
            start = rng.randint(1, 5)
            terms = [start]
            for _ in range(4):
                terms.append(terms[-1] * ratio)
            correct = terms[-1] * ratio
        op = "divided by" if divide else "multiplied by"
        other_ratio = 5 - ratio  # the only other ratio this generator uses
        # Distractors from real mistakes, not arbitrary offsets: repeating the
        # last term (forgot to act at all), and using the other common ratio
        # instead of the right one — either as the sole operation or as an
        # extra +/-ratio slip on top of the correct answer. `correct + 1` is
        # kept only as a last-resort filler for the rare case (small numbers
        # after several divisions) where the others collide with each other.
        if divide:
            wrong = [terms[-1], terms[-1] // other_ratio, correct + ratio,
                     max(1, correct - ratio), correct + 1]
        else:
            wrong = [terms[-1], terms[-1] * other_ratio, correct + ratio,
                     max(1, correct - ratio), correct + 1]
        return Item(
            stem=f"What comes next in this sequence?  {', '.join(map(str, terms))}, ___",
            options=shuffled_options(rng, correct, wrong),
            difficulty=difficulty,
            params={"kind": "multiplicative", "start": start, "ratio": ratio, "divide": divide},
            question_type="multiplicative",
            explanation=f"Each number is {op} {ratio} to get the next, giving {correct}.",
        )

    def _two_step(self, rng, difficulty):
        mult = rng.choice([2, 3])
        # start > sub guarantees (mult - 1) * start > sub, so mult*x - sub > x
        # at every step and the sequence only ever grows — matching the one
        # real example seen (VR7 Q28: 2, 5, 14, 41, 122), which never dips.
        # sub anywhere near start (or larger, as an unconstrained 1-5 range
        # allowed) sends a small start negative within a couple of terms.
        start = rng.randint(3, 6)
        sub = rng.randint(1, start - 1)
        terms = [start]
        for _ in range(4):
            terms.append(terms[-1] * mult - sub)
        correct = terms[-1] * mult - sub
        # NOT `terms[-1] * mult` as a candidate: that's algebraically identical
        # to `correct + sub` (multiply, forget to subtract), always a duplicate.
        wrong = [correct + sub, correct + mult, correct - mult, correct + sub + mult]
        return Item(
            stem=f"What comes next in this sequence?  {', '.join(map(str, terms))}, ___",
            options=shuffled_options(rng, correct, wrong),
            difficulty=difficulty,
            params={"kind": "two-step", "start": start, "mult": mult, "sub": sub},
            question_type="two-step-rule",
            explanation=(f"Each number is multiplied by {mult}, then {sub} is "
                         f"taken away, giving {correct}."),
        )

    def _alternating(self, rng, difficulty):
        # Two interleaved rules: odd positions follow one rule, even positions
        # follow another, exactly the shape GL Assessment's own solution text
        # describes ("the 1st, 3rd, 5th... and the 2nd, 4th, 6th...").
        step_a = rng.randint(2, 8)
        step_b = rng.randint(2, 8)
        start_a = rng.randint(1, 15)
        start_b = rng.randint(1, 15)
        a = [start_a + i * step_a for i in range(4)]
        b = [start_b + i * step_b for i in range(4)]
        shown = [a[0], b[0], a[1], b[1], a[2], b[2], a[3]]
        correct = b[3]
        # Margin candidates: continuing the OTHER sequence instead, one step
        # over/under, and repeating an already-shown term of the B sequence.
        wrong = [a[3] + step_a, correct + step_b, correct - step_b,
                 correct + 2 * step_b, b[2]]
        return Item(
            stem=f"What comes next in this sequence?  {', '.join(map(str, shown))}, ___",
            options=shuffled_options(rng, correct, wrong),
            difficulty=difficulty,
            params={"kind": "alternating", "start_a": start_a, "step_a": step_a,
                    "start_b": start_b, "step_b": step_b},
            question_type="alternating",
            explanation=(f"There are two sequences running together: every other "
                         f"number goes up by {step_a}, and the ones in between go "
                         f"up by {step_b}. The next number continues the second "
                         f"sequence, giving {correct}."),
        )
