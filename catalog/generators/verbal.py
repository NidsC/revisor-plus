"""
Verbal Reasoning generators.

VR is more algorithmic than it looks: codes, letter sequences and hidden words are
pure string manipulation, and analogies and odd-one-out need only a curated set of
word groups plus combinatorics. The word data below is ordinary English vocabulary
chosen for this purpose — nothing is lifted from a published paper.

Each generator names one canonical VR subtopic from elevenplus_data/taxonomy.json.
Seventeen of the taxonomy's 24 are covered here; the rest are pack territory. Question
forms that used to share a subtopic — codes with letter sequences, hidden words
with compound words — are now filed separately, because the taxonomy separates
them and a pupil weak on one is not necessarily weak on the other.

HIDDEN and NumberSequence's rule shapes were checked against 10 real VR papers
(Owl Tutors, GL Assessment, CGP, Bond/OUP) as working notes in plans.md's VR
generator coverage entry before being built/reworked. The wording and numbers
below are still original: only the *shape* (always a 4-letter word spanning a
two-word join; the sequence rule types that recur across publishers) came from
that check, never specific sentences or number lines.

LetterAnalogy, NumberCode, MissingNumberSum, TripletRule and LetterAlgebra (Batch 1
of a second coverage pass, closing part of the 14-subtopic gap left after PR #50)
were checked the same way against a separate 10-paper set in `VR resources/` (GL
Assessment familiarisation, CGP-GL, CGP-CEM, ISEB) — see plans.md's VR generator
coverage entry and the "VR real-paper evidence gathering" plan it cross-references.
Each class's own comment cites the specific paper/question range its mechanic came
from. Every one of the five was built, then independently re-verified at scale
(thousands of builds, answers re-derived from scratch, checked against the real
generate_bank validator) by a second reviewer before being added here — the same
two-pass discipline HIDDEN and NumberSequence went through in PR #50. None of these
five have a `numeric`/`short_text` counterpart in generate_bank.py today (it
hardcodes MCQ for every generated Question) — see each class's own docstring for
how it works around that gap.

WordPattern, DoubleMeaning, LetterMove and AntonymPair (Batch 2 of the same pass —
the lexical-track subtopics, needing a curated word pool rather than pure
computation) went through the same build-then-independently-verify pipeline against
the same `VR resources/` papers. AntonymPair shipped with reduced scope after three
straight pool designs failed independent review, each for a variant of the same
underlying flaw: a pupil could answer without any antonym knowledge, first by
spotting the one option with a different word class, then by spotting the one from
a different topic, then by spotting an obviously-paired decoy. The 11 entries here
(personality traits, sports, travel) draw fillers from a genuinely matching semantic
category and passed clean; the other 15 (concrete physical qualities — hot/cold,
big/small, and similar) are deferred rather than shipped with an invented, unverified
filler strategy — see plans.md's VR generator coverage entry for the full history.
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


@register
class LetterAnalogy(Generator):
    """
    Alphabet-position analogy: "BY is to HS as CX is to ______?"

    Confirmed against a real paper (CGP-GL Q60-64): each letter of the first
    word is shifted a fixed number of alphabet places to produce the second
    word, and applying the same rule to a third word gives the answer.

    DIFFICULTY selects which of the taxonomy's three question_types comes
    out: d1-d2 shift a single letter (`single-letter-shift`), d3-d4 shift a
    two-letter pair — first the same direction, then mirrored, which needs
    two separate rules held in mind at once (`pair-shift`) — and d5 swaps
    letter positions with no value change at all (`position-swap`).
    """
    slug = "vr.letteranalogy"
    section, subtopic = "VR", "Letter Analogies"
    template_id = "letter-analogy"

    def build(self, rng, difficulty):
        if difficulty in (1, 2):
            return self._single(rng, difficulty)
        if difficulty in (3, 4):
            return self._pair(rng, difficulty)
        return self._swap(rng, difficulty)

    @staticmethod
    def _shift(ch, n):
        return ALPHABET[(ALPHABET.index(ch) + n) % 26]

    def _single(self, rng, difficulty):
        # DIFFICULTY: d1 is a small forward-only shift; d2 widens the range
        # and allows a backward shift, so the pupil can no longer assume
        # "the letter after".
        shift = rng.choice([1, 2, 3]) if difficulty == 1 else \
            rng.choice([4, 5, 6, -2, -3, -4])
        a1 = rng.choice(ALPHABET)
        b1 = self._shift(a1, shift)
        a2 = rng.choice([c for c in ALPHABET if c != a1])
        correct = self._shift(a2, shift)
        step = 1 if shift > 0 else -1
        wrong_direction = self._shift(a2, -shift)
        overshoot = self._shift(a2, shift + step)
        undershoot = self._shift(a2, shift - step)
        doubled = self._shift(a2, shift * 2)
        # shuffled_options dedups its `distractors` arg IN LIST ORDER and keeps
        # only the first `keep` survivors — it does not sample. Shuffle here so
        # every candidate, including the misconception-tagged ones at the end
        # of the list, has a fair chance of being one of the 3 kept.
        candidates = [wrong_direction, overshoot, undershoot, doubled, a2]
        rng.shuffle(candidates)
        return Item(
            stem=f"{a1} is to {b1} as {a2} is to ______?",
            options=shuffled_options(rng, correct, candidates),
            difficulty=difficulty,
            params={"kind": "single", "a1": a1, "a2": a2, "shift": shift},
            question_type="single-letter-shift",
            explanation=(f"Each letter moves {abs(shift)} place"
                         f"{'s' if abs(shift) != 1 else ''} "
                         f"{'forward' if shift > 0 else 'back'} in the alphabet, "
                         f"so {a2} becomes {correct}."),
            misconceptions={
                wrong_direction: "shifted-the-wrong-way",
                a2: "no-shift-applied",
            },
        )

    def _pair(self, rng, difficulty):
        # DIFFICULTY: d3 moves both letters the SAME way by the same amount
        # (one rule to spot); d4 mirrors them — first letter forward, second
        # letter back by the same amount, the CGP-GL BY->HS shape — which
        # needs two rules held in mind at once, so it stays the harder tier
        # even though the shift range itself is unchanged.
        mirrored = difficulty == 4
        shift = rng.randint(2, 7)
        first, second = rng.sample(ALPHABET, 2)
        word1 = first + second
        if mirrored:
            word2 = self._shift(first, shift) + self._shift(second, -shift)
        else:
            word2 = self._shift(first, shift) + self._shift(second, shift)

        remaining = [c for c in ALPHABET if c not in (first, second)]
        c1, c2 = rng.sample(remaining, 2)
        word3 = c1 + c2
        if mirrored:
            correct = self._shift(c1, shift) + self._shift(c2, -shift)
            alt_rule = self._shift(c1, shift) + self._shift(c2, shift)      # applied same-direction instead of mirrored
            only_second = c1 + self._shift(c2, -shift)
        else:
            correct = self._shift(c1, shift) + self._shift(c2, shift)
            alt_rule = self._shift(c1, shift) + self._shift(c2, -shift)     # applied mirrored instead of same-direction
            only_second = c1 + self._shift(c2, shift)
        only_first = self._shift(c1, shift) + c2

        rule = (f"the first letter moves forward {shift} places and the second "
                f"moves back {shift} places" if mirrored else
                f"both letters move forward {shift} places")
        # See _single's comment: shuffle before shuffled_options() truncates,
        # so the tail entries (word3, c2+c1) get a fair shot at surviving.
        candidates = [alt_rule, only_first, only_second, word3, c2 + c1]
        rng.shuffle(candidates)
        return Item(
            stem=f"{word1} is to {word2} as {word3} is to ______?",
            options=shuffled_options(rng, correct, candidates),
            difficulty=difficulty,
            params={"kind": "pair", "mirrored": mirrored, "word1": word1,
                    "word3": word3, "shift": shift},
            question_type="pair-shift",
            explanation=f"In the code, {rule}, so {word3} becomes {correct}.",
            misconceptions={
                alt_rule: "used-the-wrong-pair-rule",
                only_first: "shifted-only-one-letter",
                only_second: "shifted-only-one-letter",
                word3: "no-shift-applied",
            },
        )

    def _swap(self, rng, difficulty):
        # DIFFICULTY 5: no letter changes VALUE at all — the first and last
        # letters of a 3-letter group exchange places and the middle one
        # stays put. No arithmetic to invert, only careful bookkeeping of
        # which slot is which, which is a different kind of hard rather than
        # a bigger shift.
        letters1 = rng.sample(ALPHABET, 3)
        word1 = "".join(letters1)
        word2 = word1[2] + word1[1] + word1[0]
        letters2 = rng.sample([c for c in ALPHABET if c not in letters1], 3)
        word3 = "".join(letters2)
        correct = word3[2] + word3[1] + word3[0]
        swap_first_middle = word3[1] + word3[0] + word3[2]
        swap_middle_last = word3[0] + word3[2] + word3[1]
        rotated = word3[1] + word3[2] + word3[0]
        # Same fix as _single/_pair, applied here too even though this branch's
        # earlier check found no collisions — consistent and harmless.
        candidates = [swap_first_middle, swap_middle_last, word3, rotated]
        rng.shuffle(candidates)
        return Item(
            stem=f"{word1} is to {word2} as {word3} is to ______?",
            options=shuffled_options(rng, correct, candidates),
            difficulty=difficulty,
            params={"kind": "swap", "word1": word1, "word3": word3},
            question_type="position-swap",
            explanation=(f"The first and last letters swap places and the middle "
                         f"letter stays put, so {word3} becomes {correct}."),
            misconceptions={
                swap_first_middle: "swapped-the-wrong-letters",
                swap_middle_last: "swapped-the-wrong-letters",
                word3: "did-not-swap",
            },
        )


# Letters restricted to a 9-letter alphabet so that any combination of words
# drawn from NUMCODE_WORDS never needs more than 9 distinct digits/symbols to
# encode. Words are ordinary vocabulary with no repeated letter internally: a
# repeated letter would make its own code self-inconsistent to read off
# position by position, which is exactly the ambiguity real papers avoid by
# never using words like "LETTER" or "APPLE" in this kind of puzzle.
NUMCODE_ALPHABET = set("ADEINORST")
NUMCODE_WORDS = [
    # 4-letter
    "TEAR", "TIRE", "RIDE", "NOTE", "ROSE", "STAR", "RAID", "DATE", "SEAT", "OATS",
    # 5-letter
    "ARISE", "NOISE", "STAIN", "STONE", "STARE", "TRADE", "RESIN", "SEDAN", "RATIO", "ADORN",
    # 6-letter
    "STRAND", "RATION", "DONATE", "ORIENT", "ARDENT",
]

# One symbol per possible letter (9 letters -> 9 symbols), for the
# symbol-substitution variant. "=" and ";" are deliberately excluded: the
# stem itself uses "WORD = code" and ";" between given pairs, so either
# would sit inside the puzzle's own punctuation and could be misread as a
# separator rather than a value.
NUMCODE_SYMBOLS = ["#", "@", "%", "&", "*", "+", "!", "~", "^"]


@register
class NumberCode(Generator):
    """VR Number Codes: a word<->number substitution cipher, confirmed against
    real papers (GL Fam T1/T2/T3, CGP-GL Q70-75). Three of four words are
    shown with their full code; the fourth's code (or one digit/letter
    within it) must be derived by constraint satisfaction — the same letter
    always maps to the same digit/symbol across all shown words — not a
    fixed alphabet-position shift like LetterCode.

    The solver-shaped guarantee: every letter in the target word must
    already appear in the union of the 3 given words, and no given word
    repeats a letter, so reading a given word's code off position-by-
    position pins down exactly one digit/symbol per letter it contains —
    there is no second mapping consistent with the same three pairs.
    """
    slug = "vr.numcode"
    section, subtopic = "VR", "Number Codes"
    template_id = "number-code-cipher"

    # DIFFICULTY: word length rises (4 -> 5 -> 6 distinct letters to track),
    # and from difficulty 4 the code-to-number variant can ask for a single
    # letter's value in isolation rather than a whole word's code — reading
    # off one fact from the constraint set is harder than reading off all of
    # them at once, because there's no "decode everything, done" checkpoint.
    _TARGET_LEN = {1: 4, 2: 4, 3: 5, 4: 5, 5: 6}
    _QTYPES = {
        1: ["number-to-code"],
        2: ["number-to-code", "code-to-number"],
        3: ["number-to-code", "code-to-number", "symbol-substitution"],
        4: ["code-to-number", "symbol-substitution"],
        5: ["code-to-number", "symbol-substitution"],
    }

    def build(self, rng, difficulty):
        qtype = rng.choice(self._QTYPES[difficulty])
        target_len = self._TARGET_LEN[difficulty]
        is_symbol = qtype == "symbol-substitution"

        puzzle = self._make_puzzle(rng, target_len, is_symbol)
        if puzzle is None:
            return None
        target, givens, mapping, letters = puzzle

        if qtype == "code-to-number" and difficulty >= 4 and len(letters) >= 4:
            return self._build_letter_clue(rng, difficulty, target, givens, mapping, letters)
        if qtype == "code-to-number":
            return self._build_decode_word(rng, difficulty, target, givens, mapping, letters)
        return self._build_encode(rng, difficulty, qtype, target, givens, mapping, letters)

    def _make_puzzle(self, rng, target_len, is_symbol, attempts=200):
        """Pick 3 "given" words + 1 target word and a letter->value mapping.

        The hard constraint, and the whole guarantee of a single valid
        answer: every letter in the target word must already appear in the
        union of the 3 given words. Once the target's letters are all
        covered, its code (or any one letter's value within it) is forced,
        not merely "probably right".
        """
        targets = [w for w in NUMCODE_WORDS if len(w) == target_len]
        for _ in range(attempts):
            target = rng.choice(targets)
            pool = [w for w in NUMCODE_WORDS if w != target]
            if len(pool) < 3:
                continue
            givens = rng.sample(pool, 3)
            covered = set("".join(givens))
            if not set(target) <= covered:
                continue
            letters = sorted(covered | set(target))
            values = (rng.sample(NUMCODE_SYMBOLS, len(letters)) if is_symbol
                      else [str(d) for d in rng.sample(range(10), len(letters))])
            mapping = dict(zip(letters, values))

            # Ambiguity guard. Re-derive letter->value purely from what the 3
            # given pairs show (not from `mapping`, which we're trying to
            # check independently), and reject if that re-derivation ever
            # disagrees with itself or fails to nail down every letter the
            # question needs.
            inferred = {}
            ok = True
            for w in givens:
                code = self._encode(w, mapping, is_symbol)
                units = code.split(" ") if is_symbol else list(code)
                for ch, val in zip(w, units):
                    if ch in inferred and inferred[ch] != val:
                        ok = False
                        break
                    inferred[ch] = val
                if not ok:
                    break
            if not ok or any(inferred.get(c) != mapping[c] for c in target):
                continue
            return target, givens, mapping, letters
        return None

    @staticmethod
    def _encode(word, mapping, is_symbol):
        values = [mapping[c] for c in word]
        return " ".join(values) if is_symbol else "".join(values)

    def _build_encode(self, rng, difficulty, qtype, target, givens, mapping, letters):
        is_symbol = qtype == "symbol-substitution"
        noun = "symbols" if is_symbol else "numbers"
        given_lines = "; ".join(
            f"{w} = {self._encode(w, mapping, is_symbol)}" for w in givens)
        correct = self._encode(target, mapping, is_symbol)
        wrong = self._code_distractors(rng, correct, is_symbol)
        return Item(
            stem=(f"In a code, {noun} stand for letters: {given_lines}. "
                  f"Using the same code, what is {target}?"),
            options=shuffled_options(rng, correct, wrong),
            difficulty=difficulty,
            params={"qtype": qtype, "target": target, "givens": sorted(givens),
                    "mapping": mapping},
            question_type=qtype,
            explanation=self._explain(target, mapping, is_symbol, correct),
        )

    def _build_decode_word(self, rng, difficulty, target, givens, mapping, letters):
        is_symbol = False  # full-word decode uses digits; see class docstring
        code = self._encode(target, mapping, is_symbol)
        given_lines = "; ".join(f"{w} = {self._encode(w, mapping, is_symbol)}" for w in givens)
        # Distractors: other real words from the pool, same length as target
        # so the option set doesn't give away the answer by length alone.
        same_len = [w for w in NUMCODE_WORDS
                    if len(w) == len(target) and w != target and w not in givens]
        if len(same_len) < 3:
            same_len = [w for w in NUMCODE_WORDS if w != target and w not in givens]
        wrong = rng.sample(same_len, min(3, len(same_len)))
        return Item(
            stem=(f"In a code, numbers stand for letters: {given_lines}. "
                  f"Using the same code, which word does {code} stand for?"),
            options=shuffled_options(rng, target, wrong),
            difficulty=difficulty,
            params={"qtype": "code-to-number", "mode": "word", "target": target,
                    "givens": sorted(givens), "mapping": mapping},
            question_type="code-to-number",
            explanation=self._explain(target, mapping, is_symbol, code),
        )

    def _build_letter_clue(self, rng, difficulty, target, givens, mapping, letters):
        """Ask which letter one specific digit/symbol stands for.

        Harder than decoding a whole word: there's no full code to lean on,
        just one fact pulled out of the constraint set, so the pupil has to
        re-locate which given word contains that value rather than reading
        top-to-bottom.
        """
        clue_letter = rng.choice(letters)
        clue_value = mapping[clue_letter]
        given_lines = "; ".join(f"{w} = {self._encode(w, mapping, False)}" for w in givens)
        distractor_letters = [l for l in letters if l != clue_letter]
        wrong = rng.sample(distractor_letters, min(3, len(distractor_letters)))
        return Item(
            stem=(f"In a code, numbers stand for letters: {given_lines}. "
                  f"Using the same code, what letter does {clue_value} stand for?"),
            options=shuffled_options(rng, clue_letter, wrong),
            difficulty=difficulty,
            params={"qtype": "code-to-number", "mode": "letter", "target": target,
                    "givens": sorted(givens), "mapping": mapping, "clue": clue_letter},
            question_type="code-to-number",
            explanation=(f"{clue_value} appears in the code for a word containing "
                         f"{clue_letter}, so {clue_value} stands for {clue_letter}."),
        )

    @staticmethod
    def _explain(target, mapping, is_symbol, correct):
        parts = ", ".join(f"{c}={mapping[c]}" for c in sorted(set(target)))
        noun = "symbol" if is_symbol else "number"
        return (f"Each letter always stands for the same {noun}: {parts}. "
                f"Reading {target} letter by letter gives {correct}.")

    @staticmethod
    def _code_distractors(rng, code, is_symbol):
        chars = code.split(" ") if is_symbol else list(code)
        pool = NUMCODE_SYMBOLS if is_symbol else list("0123456789")

        def join(cs):
            return " ".join(cs) if is_symbol else "".join(cs)

        variants = set()
        if len(chars) >= 2:
            swapped = chars[:]
            swapped[0], swapped[1] = swapped[1], swapped[0]
            variants.add(join(swapped))
        last = chars[:]
        last[-1] = rng.choice([v for v in pool if v != last[-1]])
        variants.add(join(last))
        first = chars[:]
        first[0] = rng.choice([v for v in pool if v != first[0]])
        variants.add(join(first))
        variants.add(join(chars[::-1]))
        variants.discard(join(chars))
        return list(variants)


@register
class MissingNumberSum(Generator):
    """VR Missing Number Sums, confirmed against real papers (GL Fam T2
    Q61-67, CGP-GL Q50-54): an arithmetic equation with exactly one blank
    (a missing number or a missing operator), both sides must balance.
    """
    slug = "vr.missingsum"
    section, subtopic = "VR", "Missing Number Sums"
    template_id = "missing-number-sum"

    def build(self, rng, difficulty):
        # DIFFICULTY: one blank operand in a single-step +/- equation, then the
        # same shape with x/div, then a missing OPERATOR (a different kind of
        # reasoning: test the four candidates rather than invert one), then a
        # two-sided equation with one blank operand, then the same two-sided
        # shape with a bracketed three-number reference side. Covers all three
        # taxonomy question_type slugs for this subtopic across the 5 tiers,
        # the same way vr.numseq maps 5 rule shapes onto 5 difficulties.
        if difficulty == 1:
            return self._missing_operand_add_sub(rng, difficulty)
        if difficulty == 2:
            return self._missing_operand_mul_div(rng, difficulty)
        if difficulty == 3:
            return self._missing_operator(rng, difficulty)
        if difficulty == 4:
            return self._balance_simple(rng, difficulty)
        return self._balance_bracketed(rng, difficulty)

    def _missing_operand_add_sub(self, rng, difficulty):
        op = rng.choice(["+", "-"])
        blank_first = rng.random() < 0.5
        if op == "+":
            a, b = rng.randint(3, 45), rng.randint(3, 45)
            total = a + b
            known, correct = (b, a) if blank_first else (a, b)
            stem_expr = (f"? + {known} = {total}" if blank_first
                         else f"{known} + ? = {total}")
            distractors = [total + known, total, correct + 10, max(1, correct - 2)]
            explanation = f"{total} − {known} = {correct}."
        else:
            a = rng.randint(25, 90)
            b = rng.randint(3, a - 10)
            diff = a - b
            if blank_first:
                correct = a
                stem_expr = f"? − {b} = {diff}"
                distractors = [max(1, diff - b), diff + b, correct - 1, correct + 1]
                explanation = f"{diff} + {b} = {correct}."
            else:
                correct = b
                stem_expr = f"{a} − ? = {diff}"
                distractors = [a + diff, max(1, correct - 1), correct + 1, a]
                explanation = f"{a} − {diff} = {correct}."
        return Item(
            stem=f"Find the missing number.  {stem_expr}",
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"kind": "operand-add-sub", "expr": stem_expr, "correct": correct},
            question_type="missing-operand",
            explanation=f"Rearranging the equation: {explanation}",
        )

    def _missing_operand_mul_div(self, rng, difficulty):
        op = rng.choice(["×", "÷"])
        if op == "×":
            a, b = rng.randint(2, 12), rng.randint(2, 12)
            product = a * b
            if rng.random() < 0.5:
                correct, known = a, b
                stem_expr = f"? × {known} = {product}"
            else:
                correct, known = b, a
                stem_expr = f"{known} × ? = {product}"
            distractors = [product, known, correct + 1, max(1, correct - 1)]
            explanation = f"{product} ÷ {known} = {correct}."
        else:
            divisor = rng.randint(2, 12)
            quotient = rng.randint(2, 12)
            dividend = divisor * quotient
            if rng.random() < 0.5:
                correct = dividend
                stem_expr = f"? ÷ {divisor} = {quotient}"
                distractors = [quotient, divisor, dividend + divisor, max(1, dividend - divisor)]
                explanation = f"{quotient} × {divisor} = {correct}."
            else:
                correct = divisor
                stem_expr = f"{dividend} ÷ ? = {quotient}"
                distractors = [dividend, quotient, correct + 1, max(1, correct - 1)]
                explanation = f"{dividend} ÷ {quotient} = {correct}."
        return Item(
            stem=f"Find the missing number.  {stem_expr}",
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"kind": "operand-mul-div", "expr": stem_expr, "correct": correct},
            question_type="missing-operand",
            explanation=f"Rearranging the equation: {explanation}",
        )

    @staticmethod
    def _apply(a, b, op):
        if op == "+":
            return a + b
        if op == "-":
            r = a - b
            return r if r >= 0 else None
        if op == "×":
            return a * b
        if op == "÷":
            return a // b if b != 0 and a % b == 0 else None
        return None

    def _missing_operator(self, rng, difficulty):
        ops = ["+", "-", "×", "÷"]
        for _ in range(60):
            op0 = rng.choice(ops)
            if op0 == "+":
                a, b = rng.randint(2, 40), rng.randint(2, 40)
            elif op0 == "-":
                a = rng.randint(10, 60)
                b = rng.randint(1, a - 1)
            elif op0 == "×":
                a, b = rng.randint(2, 12), rng.randint(2, 12)
            else:
                b = rng.randint(2, 12)
                q = rng.randint(2, 12)
                a = b * q
            target = self._apply(a, b, op0)
            if target is None:
                continue
            matches = [op for op in ops if self._apply(a, b, op) == target]
            if len(matches) == 1:
                correct = op0
                others = [op for op in ops if op != op0]
                return Item(
                    stem=f"Which sign belongs in the box?  {a} ▢ {b} = {target}",
                    options=shuffled_options(rng, correct, others, keep=3),
                    difficulty=difficulty,
                    params={"a": a, "b": b, "op": op0, "target": target},
                    question_type="missing-operator",
                    explanation=(f"{a} {op0} {b} = {target}; none of the other "
                                 f"signs give {target}."),
                )
        return None

    def _solve_blank_side(self, rng, v, allow_mul):
        ops = ["+", "-"] + (["×", "÷"] if allow_mul else [])
        rng.shuffle(ops)
        for op_b in ops:
            if op_b == "+":
                if v < 2:
                    continue
                k = rng.randint(1, v - 1)
                correct = v - k
                expr = f"? + {k}" if rng.random() < 0.5 else f"{k} + ?"
                exp = f"{correct} + {k} = {v}."
                return expr, correct, exp
            if op_b == "-":
                if rng.random() < 0.5:
                    k = rng.randint(1, 40)
                    correct = v + k
                    expr = f"? − {k}"
                    exp = f"{correct} − {k} = {v}."
                else:
                    k = v + rng.randint(1, 40)
                    correct = k - v
                    expr = f"{k} − ?"
                    exp = f"{k} − {correct} = {v}."
                return expr, correct, exp
            if op_b == "×":
                divisors = [d for d in range(2, 10) if v % d == 0]
                if not divisors:
                    continue
                k = rng.choice(divisors)
                correct = v // k
                expr = f"? × {k}" if rng.random() < 0.5 else f"{k} × ?"
                exp = f"{correct} × {k} = {v}."
                return expr, correct, exp
            if op_b == "÷":
                k = rng.randint(2, 9)
                correct = v * k
                expr = f"? ÷ {k}"
                exp = f"{correct} ÷ {k} = {v}."
                return expr, correct, exp
        return None

    def _balance_simple(self, rng, difficulty):
        result = None
        for _ in range(40):
            op_known = rng.choice(["+", "−", "×"])
            if op_known == "+":
                p, q = rng.randint(5, 60), rng.randint(5, 60)
                v = p + q
            elif op_known == "−":
                p = rng.randint(20, 90)
                q = rng.randint(3, p - 5)
                v = p - q
            else:
                p, q = rng.randint(2, 9), rng.randint(2, 9)
                v = p * q
            known_expr = f"{p} {op_known} {q}"
            result = self._solve_blank_side(rng, v, allow_mul=False)
            if result is not None:
                break
        if result is None:
            return None
        blank_expr, correct, exp_line = result

        blank_left = rng.random() < 0.5
        stem = (f"{blank_expr} = {known_expr}" if blank_left
                else f"{known_expr} = {blank_expr}")
        distractors = [v, correct + 1, max(1, correct - 1), correct + 5]
        return Item(
            stem=f"Find the missing number so both sides balance.  {stem}",
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"known": known_expr, "blank": blank_expr, "correct": correct, "v": v},
            question_type="balance-both-sides",
            explanation=(f"{known_expr} = {v}, so the missing number must make "
                         f"the other side equal {v} too: {exp_line}"),
        )

    def _balance_bracketed(self, rng, difficulty):
        template = rng.choice(["sum_mul", "diff_mul", "mul_sub", "mul_add"])
        if template == "sum_mul":
            a, b, c = rng.randint(2, 15), rng.randint(2, 15), rng.randint(2, 9)
            v = (a + b) * c
            known_expr = f"({a} + {b}) × {c}"
        elif template == "diff_mul":
            a = rng.randint(6, 20)
            b = rng.randint(1, a - 2)
            c = rng.randint(2, 9)
            v = (a - b) * c
            known_expr = f"({a} − {b}) × {c}"
        elif template == "mul_sub":
            a, b = rng.randint(2, 9), rng.randint(2, 9)
            product = a * b
            c = rng.randint(1, max(1, product - 1))
            v = product - c
            known_expr = f"({a} × {b}) − {c}"
        else:
            a, b = rng.randint(2, 9), rng.randint(2, 9)
            c = rng.randint(1, 20)
            v = a * b + c
            known_expr = f"({a} × {b}) + {c}"

        result = self._solve_blank_side(rng, v, allow_mul=True)
        if result is None:
            return None
        blank_expr, correct, exp_line = result

        blank_left = rng.random() < 0.5
        stem = (f"{blank_expr} = {known_expr}" if blank_left
                else f"{known_expr} = {blank_expr}")
        distractors = [v, correct + 1, max(1, correct - 1), correct + c]
        return Item(
            stem=f"Find the missing number so both sides balance.  {stem}",
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"known": known_expr, "blank": blank_expr, "correct": correct,
                    "v": v, "template": template},
            question_type="balance-both-sides",
            explanation=(f"{known_expr} = {v}, so the missing number must make "
                         f"the other side equal {v} too: {exp_line}"),
        )


# --------------------------------------------------------------------------
# Rule set for TripletRule. `forward` is the "real" rule that generates a
# consistent triplet (a, b, c) — the correct answer never needs an inverse,
# it's just the value already sitting in the triple before one slot gets
# blanked. `solve_a`/`solve_b` are used only to build distractors and to
# check rule-uniqueness for find-the-rule items — never to compute the
# correct answer itself.
# --------------------------------------------------------------------------

class _TripletRuleSpec:
    __slots__ = ("key", "statement", "sample", "forward", "solve_a", "solve_b")

    def __init__(self, key, statement, sample, forward, solve_a, solve_b):
        self.key = key
        self.statement = statement
        self.sample = sample
        self.forward = forward
        self.solve_a = solve_a
        self.solve_b = solve_b


def _triplet_sample_product(rng):
    return rng.randint(2, 9), rng.randint(2, 9)


def _triplet_sample_sum(rng):
    return rng.randint(2, 40), rng.randint(2, 40)


def _triplet_sample_average(rng):
    a, b = rng.randint(2, 40), rng.randint(2, 40)
    if (a + b) % 2:
        b += 1
    return a, b


def _triplet_sample_double_minus(rng):
    a = rng.randint(3, 20)
    b = rng.randint(1, 2 * a - 1)   # keeps c = 2a - b >= 1
    return a, b


def _triplet_sample_difference(rng):
    a = rng.randint(5, 40)
    b = rng.randint(1, a - 1)       # keeps c = a - b >= 1 and a != b
    return a, b


_TRIPLET_RULES = [
    _TripletRuleSpec(
        "product",
        "the third number is the first number multiplied by the second",
        _triplet_sample_product,
        lambda a, b: a * b,
        lambda b, c: (c // b) if b and c % b == 0 else None,
        lambda a, c: (c // a) if a and c % a == 0 else None,
    ),
    _TripletRuleSpec(
        "sum",
        "the third number is the first number plus the second",
        _triplet_sample_sum,
        lambda a, b: a + b,
        lambda b, c: c - b,
        lambda a, c: c - a,
    ),
    _TripletRuleSpec(
        "average",
        "the third number is halfway between the first two numbers",
        _triplet_sample_average,
        lambda a, b: (a + b) // 2,
        lambda b, c: 2 * c - b,
        lambda a, c: 2 * c - a,
    ),
    _TripletRuleSpec(
        "double_minus",
        "the third number is double the first number, minus the second",
        _triplet_sample_double_minus,
        lambda a, b: 2 * a - b,
        lambda b, c: ((c + b) // 2) if (c + b) % 2 == 0 else None,
        lambda a, c: 2 * a - c,
    ),
    _TripletRuleSpec(
        "difference",
        "the third number is the first number minus the second",
        _triplet_sample_difference,
        lambda a, b: a - b,
        lambda b, c: c + b,
        lambda a, c: a - c,
    ),
]
_TRIPLET_EASY = [_TRIPLET_RULES[0], _TRIPLET_RULES[1]]                                  # product, sum
_TRIPLET_MEDIUM = [_TRIPLET_RULES[0], _TRIPLET_RULES[1], _TRIPLET_RULES[2], _TRIPLET_RULES[4]]  # + average, difference
_TRIPLET_HARD = _TRIPLET_RULES                                                          # + double_minus


def _triplet_fmt(a, b, c, pos=None):
    vals = [a, b, c]
    if pos is not None:
        vals["abc".index(pos)] = "?"
    return "(" + ", ".join(str(v) for v in vals) + ")"


def _triplet_alt_at(rule, pos, a, b, c):
    """What a DIFFERENT rule would say belongs at `pos`, using only the two
    values a pupil actually sees. Returns None if that rule's inverse isn't a
    clean integer here."""
    if pos == "c":
        return rule.forward(a, b)
    if pos == "a":
        return rule.solve_a(b, c)
    return rule.solve_b(a, c)


def _triplet_distractors(rule, pos, a, b, c, correct):
    alts = []
    for rp in _TRIPLET_RULES:
        if rp.key == rule.key:
            continue
        v = _triplet_alt_at(rp, pos, a, b, c)
        if v is not None and v != correct:
            alts.append(v)
    alts.extend([correct + 1, correct - 1, correct + 2, correct - 2])
    return alts


def _triplet_explain(rule, pos, a, b, c, correct, prefix):
    if pos == "c":
        return f"{prefix}{a} and {b} give {correct}."
    if pos == "a":
        return f"{prefix}working back from {b} and {c} gives {correct}."
    return f"{prefix}working back from {a} and {c} gives {correct}."


@register
class TripletRule(Generator):
    """VR Triplet Rules (ISEB §3 "Number Analogies"): several bracketed number
    triplets share one arithmetic rule linking their three numbers; a 4th
    triplet has one number missing and the pupil finds it.

    Two question_types, split by how the rule reaches the pupil:
      - apply-the-rule: the rule is stated outright in the stem, so the item
        is pure computation once it's read.
      - find-the-rule: only complete example triplets are shown, and the
        pupil must notice which rule fits ALL of them before using it on the
        incomplete one. `_find_the_rule` re-draws until no OTHER rule also
        satisfies every example shown — otherwise a pupil could infer a
        different, equally-valid rule from the examples and get a different
        (but equally defensible) missing number.
    """
    slug = "vr.tripletrule"
    section, subtopic = "VR", "Triplet Rules"
    template_id = "triplet-rule"

    def build(self, rng, difficulty):
        # DIFFICULTY: stated rule with the answer always in the last slot,
        # then stated rule with a harder rule pool, then infer-from-3-examples,
        # then a mix of stated-but-work-backwards and infer-from-2-examples,
        # then infer-from-2-examples with the hardest rules and any slot blank.
        if difficulty == 1:
            return self._apply_the_rule(rng, difficulty, _TRIPLET_EASY, ("c",))
        if difficulty == 2:
            return self._apply_the_rule(rng, difficulty, _TRIPLET_MEDIUM, ("c",))
        if difficulty == 3:
            return self._find_the_rule(rng, difficulty, _TRIPLET_EASY, 3, ("c",))
        if difficulty == 4:
            build = rng.choice([
                lambda: self._apply_the_rule(rng, difficulty, _TRIPLET_MEDIUM, ("a", "b", "c")),
                lambda: self._find_the_rule(rng, difficulty, _TRIPLET_MEDIUM, 2, ("c",)),
            ])
            return build()
        return self._find_the_rule(rng, difficulty, _TRIPLET_HARD, 2, ("a", "b", "c"))

    def _apply_the_rule(self, rng, difficulty, rule_pool, positions):
        rule = rng.choice(rule_pool)
        ea, eb = rule.sample(rng)
        ec = rule.forward(ea, eb)
        a, b = rule.sample(rng)
        c = rule.forward(a, b)
        pos = rng.choice(positions)
        correct = {"a": a, "b": b, "c": c}[pos]
        distractors = _triplet_distractors(rule, pos, a, b, c, correct)
        explanation = _triplet_explain(
            rule, pos, a, b, c, correct,
            prefix=f"{rule.statement[0].upper()}{rule.statement[1:]}, so ",
        )
        return Item(
            stem=(f"In each triple of numbers, {rule.statement}. For example, "
                  f"{_triplet_fmt(ea, eb, ec)} follows this rule. Using the same rule, "
                  f"what is the missing number in {_triplet_fmt(a, b, c, pos)}?"),
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"qtype": "apply-the-rule", "rule": rule.key,
                    "demo": [ea, eb, ec], "triplet": [a, b, c], "pos": pos},
            question_type="apply-the-rule",
            explanation=explanation,
        )

    def _find_the_rule(self, rng, difficulty, rule_pool, n_examples, positions):
        for _ in range(80):
            rule = rng.choice(rule_pool)
            examples = []
            for _ in range(n_examples):
                ea, eb = rule.sample(rng)
                examples.append((ea, eb, rule.forward(ea, eb)))
            # Rule-uniqueness: reject if any OTHER rule also fits every
            # example, since then the "rule" a pupil infers is ambiguous.
            if any(all(rp.forward(ea, eb) == ec for ea, eb, ec in examples)
                   for rp in _TRIPLET_RULES if rp.key != rule.key):
                continue
            a, b = rule.sample(rng)
            c = rule.forward(a, b)
            pos = rng.choice(positions)
            correct = {"a": a, "b": b, "c": c}[pos]
            break
        else:
            return None

        distractors = _triplet_distractors(rule, pos, a, b, c, correct)
        examples_str = ", ".join(_triplet_fmt(*ex) for ex in examples)
        explanation = _triplet_explain(
            rule, pos, a, b, c, correct,
            prefix=f"The rule is: {rule.statement}. So ",
        )
        return Item(
            stem=(f"Each of these number triples follows the same rule: "
                  f"{examples_str}. Using the same rule, what is the missing "
                  f"number in {_triplet_fmt(a, b, c, pos)}?"),
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"qtype": "find-the-rule", "rule": rule.key,
                    "examples": examples, "triplet": [a, b, c], "pos": pos},
            question_type="find-the-rule",
            explanation=explanation,
        )


@register
class LetterAlgebra(Generator):
    """VR Letter Algebra: letters stand for numbers (A=2, B=5, C=3, ...).

    Real mechanic (GL Fam T2 Q45-51/T3 Q46-52, CGP-GL Q30-34): the pupil
    evaluates an expression or solves a small equation to reach a NUMBER, but
    the paper's answer format asks for the LETTER that number stands for --
    never the bare number. That "close the loop back to a letter" step is
    what both question_types share and what distinguishes this subtopic from
    plain substitution arithmetic.

    Two question_types, chosen by difficulty:
      - substitute-and-evaluate (d1-3): a full letter->number key is shown,
        the pupil evaluates a 2- or 3-term expression over that key, then
        names the letter (in the same key, extended if necessary) whose
        value equals the result.
      - solve-for-letter (d4-5): a small one- or two-step equation names an
        UNKNOWN letter that is deliberately NOT one of the key's letters (so
        the equation can never contradict a key entry for the same symbol).
        The pupil solves the equation for that unknown's numeric value, then
        -- exactly as in substitute-and-evaluate -- looks that value up in
        the key (extended if necessary) to give the final letter answer.

    generate_bank.py currently writes every generated Question as `kind =
    MCQ` regardless of what a generator would "prefer" (there is no per-
    generator kind hook yet), so this class answers with 4 letter options
    via `shuffled_options` -- the only shape the pipeline can import today.
    The intended long-run kind is still `short_text` (a single typed
    letter), per elevenplus_data/CLAUDE.md's VR answer-kind table; switching
    over, once the pipeline supports it, means dropping the distractor
    options below and keeping just the correct-letter computation.
    """

    slug = "vr.letteralgebra"
    section, subtopic = "VR", "Letter Algebra"
    template_id = "letter-algebra"

    def build(self, rng, difficulty):
        # DIFFICULTY: two-term addition, then addition/subtraction, then a
        # 3-term mixed expression (still substitute-and-evaluate) -- then a
        # one-step equation, then a two-step (multiply, then add/subtract)
        # equation (solve-for-letter). The letter-lookup twist at the end
        # never changes; only how much arithmetic precedes it does.
        if difficulty <= 3:
            return self._substitute(rng, difficulty)
        return self._solve(rng, difficulty)

    # ---- shared key machinery -------------------------------------------

    def _make_key(self, rng, n, low, high):
        """A true bijection by construction: `n` distinct letters (sampled
        without replacement from the alphabet) each mapped to a distinct
        integer (sampled without replacement from [low, high]). Sampling
        without replacement on BOTH sides is what rules out two letters
        ever sharing a value -- there is no post-hoc de-dup step because
        there is nothing to de-dup."""
        letters = rng.sample(ALPHABET, n)
        values = rng.sample(range(low, high + 1), n)
        return dict(zip(letters, values))

    def _letter_for(self, rng, key, reserved, value):
        """The letter mapped to `value`, extending the key with a fresh
        letter if none currently has it. This is the guarantee that a
        computed value -- the correct answer OR a distractor -- always maps
        back to a REAL letter: rather than rejecting a value that isn't
        covered, an uncovered value gets a brand-new entry on the spot,
        using a letter not already in `reserved` (every letter already
        spoken for anywhere in the item so far) -- so successive extensions
        can never collide with each other or with an existing letter's
        value. Returns (letter, possibly-extended key), or (None, key) if
        the alphabet is exhausted."""
        for letter, v in key.items():
            if v == value:
                return letter, key
        spare = [ch for ch in ALPHABET if ch not in reserved]
        if not spare:
            return None, key
        new_letter = rng.choice(spare)
        extended = dict(key)
        extended[new_letter] = value
        return new_letter, extended

    def _key_text(self, key):
        return ", ".join(f"{letter} = {value}" for letter, value in sorted(key.items()))

    def _distractor_letters(self, rng, key, reserved, correct_value, candidate_values,
                             target=4):
        """Map candidate wrong VALUES to letters (extending the key as
        needed via `_letter_for`), skipping the correct value itself,
        non-positive values (no letter stands for zero or a negative number
        in these keys) and any value already claimed by an earlier
        candidate. Returns (letters, key) with `key` folding in every
        extension made along the way.

        Stops once `target` distractors are found (one spare beyond the 3
        `shuffled_options` needs) rather than resolving every candidate,
        since working through all of them regardless would grow the key by
        up to len(candidate_values) letters even when the first 3-4 already
        sufficed."""
        letters = []
        seen_values = {correct_value}
        for value in candidate_values:
            if len(letters) >= target:
                break
            if value is None or value <= 0 or value in seen_values:
                continue
            seen_values.add(value)
            letter, key = self._letter_for(rng, key, reserved, value)
            if letter is None or letter in letters:
                continue
            letters.append(letter)
            reserved.add(letter)
        return letters, key

    # ---- substitute-and-evaluate ------------------------------------------

    @staticmethod
    def _evaluate(key, letters, ops):
        total = key[letters[0]]
        for op, letter in zip(ops, letters[1:]):
            total = total + key[letter] if op == "+" else total - key[letter]
        return total

    def _substitute(self, rng, difficulty):
        n_letters, (low, high), n_terms = {
            1: (5, (1, 9), 2),
            2: (6, (1, 12), 2),
            3: (7, (1, 15), 3),
        }[difficulty]
        for _attempt in range(30):
            key = self._make_key(rng, n_letters, low, high)
            letters = rng.sample(list(key), n_terms)
            if difficulty == 1:
                ops = ["+"]
            else:
                ops = [rng.choice(["+", "-"]) for _ in range(n_terms - 1)]

            result = self._evaluate(key, letters, ops)
            if result <= 0:
                continue  # no "negative letter", and Q=0 reads as broken, not hard
            if any(key[l] == result for l in letters):
                # Self-referential: the result coincides with one of the
                # expression's OWN operand values, so the answer letter would
                # be a letter already sitting in the question. No real paper
                # does this -- the answer is meant to be a letter the pupil
                # had to go looking up, not one already in front of them.
                continue

            reserved = set(key)
            answer_letter, key = self._letter_for(rng, key, reserved, result)
            if answer_letter is None:
                continue
            reserved.add(answer_letter)

            # Distractor VALUES modelled on real slips, not arbitrary noise:
            # off-by-one/two arithmetic, using the wrong operator on one
            # term, reading off a single operand instead of combining them,
            # and (for 3-term expressions) stopping after only two terms.
            candidates = [result + 1, result - 1, result + 2, result - 2]
            flip_idx = rng.randrange(len(ops))
            flipped = list(ops)
            flipped[flip_idx] = "-" if flipped[flip_idx] == "+" else "+"
            candidates.append(self._evaluate(key, letters, flipped))
            candidates.append(key[rng.choice(letters)])
            if n_terms >= 3:
                candidates.append(self._evaluate(key, letters[:-1], ops[:-1]))
            rng.shuffle(candidates)

            distractor_letters, key = self._distractor_letters(
                rng, key, reserved, result, candidates)
            if len(distractor_letters) < 3:
                continue
            break
        else:
            return None

        parts = [letters[0]]
        for op, letter in zip(ops, letters[1:]):
            parts.append(op)
            parts.append(letter)
        expr = " ".join(parts)

        return Item(
            stem=(f"If {self._key_text(key)}, what letter stands for the value of "
                  f"{expr}?"),
            options=shuffled_options(rng, answer_letter, distractor_letters, keep=3),
            difficulty=difficulty,
            params={
                "mode": "substitute",
                "key": sorted(key.items()),
                "letters": letters,
                "ops": ops,
                "result": result,
                "answer": answer_letter,
            },
            question_type="substitute-and-evaluate",
            explanation=(f"{expr} = {result}, and {answer_letter} = {result}, "
                         f"so the answer is {answer_letter}."),
        )

    # ---- solve-for-letter --------------------------------------------------

    def _solve(self, rng, difficulty):
        n_letters, (low, high) = {4: (6, (1, 15)), 5: (7, (1, 20))}[difficulty]
        two_step = difficulty == 5
        for _attempt in range(30):
            key = self._make_key(rng, n_letters, low, high)
            spare = [ch for ch in ALPHABET if ch not in key]
            if not spare:
                continue
            unknown = rng.choice(spare)
            x_value = rng.randint(1, high)

            if not two_step:
                form = rng.choice(["x_plus_a", "a_plus_x", "x_minus_a", "a_minus_x"])
                a = rng.randint(1, x_value) if form == "x_minus_a" else rng.randint(1, 9)
                if form == "x_plus_a":
                    b, equation = x_value + a, f"{unknown} + {a} = {{b}}"
                elif form == "a_plus_x":
                    b, equation = x_value + a, f"{a} + {unknown} = {{b}}"
                elif form == "x_minus_a":
                    b, equation = x_value - a, f"{unknown} - {a} = {{b}}"
                else:  # a_minus_x
                    a = x_value + rng.randint(1, 9)
                    b, equation = a - x_value, f"{a} - {unknown} = {{b}}"
                if b < 0:
                    continue
                equation = equation.format(b=b)
                explain_solve = f"{equation.split(' = ')[0]} = {b} gives {unknown} = {x_value}"
                params_extra = {"form": form, "a": a, "b": b}
                extra_candidates = []
            else:
                m = rng.choice([2, 3])
                a = rng.randint(1, 9)
                sign = rng.choice(["+", "-"])
                if sign == "+":
                    b = x_value * m + a
                    equation = f"{unknown} × {m} + {a} = {b}"
                else:
                    b = x_value * m - a
                    if b < 0:
                        continue
                    equation = f"{unknown} × {m} - {a} = {b}"
                explain_solve = (f"{unknown} × {m} {sign} {a} = {b} gives "
                                 f"{unknown} = {x_value}")
                params_extra = {"m": m, "a": a, "b": b, "sign": sign}
                # A genuine two-step slip: forgetting the +/-a step entirely
                # and just dividing b by m.
                extra_candidates = [b // m] if b % m == 0 else []

            reserved = set(key) | {unknown}
            answer_letter, key = self._letter_for(rng, key, reserved, x_value)
            if answer_letter is None:
                continue
            reserved.add(answer_letter)

            # Distractor VALUES modelled on real slips: off-by-one/two on the
            # solved value, reporting the equation's own numbers (`b`, the
            # right-hand side; `a`, the other operand) instead of actually
            # solving for the unknown, and (two-step only) skipping the
            # +/-a adjustment.
            candidates = [x_value + 1, x_value - 1, x_value + 2, x_value - 2,
                          b, a, *extra_candidates]
            rng.shuffle(candidates)

            distractor_letters, key = self._distractor_letters(
                rng, key, reserved, x_value, candidates)
            if len(distractor_letters) < 3:
                continue
            break
        else:
            return None

        return Item(
            stem=(f"If {self._key_text(key)}, and {equation}, "
                  f"what letter has the same value as {unknown}?"),
            options=shuffled_options(rng, answer_letter, distractor_letters, keep=3),
            difficulty=difficulty,
            params={
                "mode": "solve",
                "key": sorted(key.items()),
                "unknown": unknown,
                "x_value": x_value,
                "two_step": two_step,
                "answer": answer_letter,
                **params_extra,
            },
            question_type="solve-for-letter",
            explanation=(f"{explain_solve}, and {answer_letter} = {x_value}, "
                         f"so the answer is {answer_letter}."),
        )


# --------------------------------------------------------------------------
# WordPattern: rule shapes and curated pool. Each shape names exactly which
# letters from word1/word3 compress together and in what order — the real
# mechanic varies this per example, so it is data here, not a fixed
# algorithm.
# --------------------------------------------------------------------------
def _wp_extract(word, spec):
    pos, n = spec
    if pos == "front":
        return word[:n]
    return word[-n:]


def _wp_apply_rule(word1, word3, rule):
    p1 = _wp_extract(word1, rule["w1"])
    p3 = _wp_extract(word3, rule["w3"])
    return p1 + p3 if rule["order"] == "w1w3" else p3 + p1


def _wp_rule_desc(rule):
    def part(spec, which):
        pos, n = spec
        end = "first" if pos == "front" else "last"
        plural = "letter" if n == 1 else "letters"
        return f"the {end} {n} {plural} of {which}"

    a = part(rule["w1"], "word1")
    b = part(rule["w3"], "word3")
    if rule["order"] == "w1w3":
        return f"{a}, followed by {b}"
    return f"{b}, followed by {a}"


_WP_RULE_SHAPES = {
    "front1_front2": {"w1": ("front", 1), "w3": ("front", 2), "order": "w1w3"},
    "front2_back2":  {"w1": ("front", 2), "w3": ("back", 2),  "order": "w1w3"},
    "back2_front2":  {"w1": ("back", 2),  "w3": ("front", 2), "order": "w1w3"},
    "front2w3_back2w1": {"w1": ("back", 2), "w3": ("front", 2), "order": "w3w1"},
    "front3_back1":  {"w1": ("front", 3), "w3": ("back", 1),  "order": "w1w3"},
    "back1_back2":   {"w1": ("back", 1),  "w3": ("back", 2),  "order": "w1w3"},
}

# (word1, word2, word3, bracket_word). word2 is a plausible filler word only
# — never used by the rule — matching the real layout of three shown words
# where the code is built from just the outer two. Every bracket_word is an
# ordinary short English word, mechanically produced by the stated rule
# from word1/word3 (verified programmatically, and independently
# re-verified: recomputing every entry from scratch reproduced every stored
# bracket_word exactly). Rule-uniqueness was checked exhaustively (not
# sampled) across every demo/target combination `_find_pattern` can
# actually draw, against a 128-candidate alternate-rule space — no
# collision survives anywhere in the pool.
_WP_POOL = {
    "front1_front2": [
        ("TIGER", "LION", "APPLE", "TAP"),
        ("SNAKE", "CLOUD", "UNDER", "SUN"),
        ("DOG", "CAT", "INSECT", "DIN"),
        ("ROBIN", "WREN", "ANTELOPE", "RAN"),
    ],
    "front2_back2": [
        ("CANDLE", "LAMP", "ROPE", "CAPE"),
        ("CABIN", "HUT", "HORSE", "CASE"),
        ("CAMEL", "DESERT", "STONE", "CANE"),
        ("CABBAGE", "CARROT", "SNAKE", "CAKE"),
    ],
    "back2_front2": [
        ("HOUSE", "HOME", "ATOM", "SEAT"),
        ("PULSE", "HEART", "ASHORE", "SEAS"),
        ("STONE", "PEBBLE", "ARROW", "NEAR"),
        ("SHINE", "GLOW", "ONWARD", "NEON"),
    ],
    "front2w3_back2w1": [
        ("ELBOW", "ARM", "SLIP", "SLOW"),
        ("RAINBOW", "CLOUD", "SNOWMAN", "SNOW"),
        ("CHAIN", "LINK", "SPOON", "SPIN"),
        ("GARDEN", "FENCE", "TENNIS", "TEEN"),
    ],
    "front3_back1": [
        ("CARPET", "RUG", "ANT", "CART"),
        ("PARTY", "BALLOON", "TANK", "PARK"),
        ("BARREL", "CASK", "INK", "BARK"),
        ("FARMER", "FIELD", "TEAM", "FARM"),
    ],
    "back1_back2": [
        ("BOOK", "PAGE", "SOLID", "KID"),
        ("TALK", "LOCK", "MONKEY", "KEY"),
        ("CHAIR", "TABLE", "PLUG", "RUG"),
        ("STREET", "ROAD", "ENJOY", "TOY"),
    ],
}


@register
class WordPattern(Generator):
    """VR Word Patterns (GL Fam T1 Q15-21/T2 Q30-36/T3 Q61-67, CGP-GL
    Q65-69, ISEB Section 1 "Letter Codes" in ISEB's own naming — do not
    conflate with this taxonomy's separate `letter_codes` subtopic, a
    different cipher mechanic). Three words are shown in a row; specific
    letters from the FIRST and THIRD word (never the middle one, which is
    present only to match the real three-word row layout) compress
    together into a bracketed code word. A second triplet is shown with its
    code word missing, and the pupil applies the SAME extraction rule (same
    positions, same letter counts, same concatenation order) to derive it.

    The rule genuinely varies per real example — sometimes the first
    letter of word1 plus the first two of word3, sometimes the last two of
    word1 plus the first two of word3, sometimes the third word's letters
    come FIRST in the code — so the rule is stored explicitly alongside
    each pool entry (`_WP_RULE_SHAPES`/`_WP_POOL` above) rather than assumed
    fixed. All bracket_words here are ordinary short English words (CAPE,
    SEAT, SNOW, ...), matching what the cited real papers show; nothing
    here is a copied paper sentence, only the *shape* of the mechanic.

    Two question_types, mirroring TripletRule's apply-the-rule/find-the-rule
    split:
      - apply-pattern: the rule is stated outright in the stem, alongside
        one fully-worked example, so the item is pure mechanical
        application once read.
      - find-pattern: 2-3 complete example triplets are shown (no rule
        stated) and the pupil must notice which extraction rule fits ALL of
        them before applying it to the incomplete one. Checked exhaustively
        (every reachable demo/target combination, not a sample) against a
        128-candidate alternate-rule space, the same rule-uniqueness
        discipline TripletRule applies to its arithmetic rules — no
        collision survives. One genuine ambiguity was caught and fixed
        during authoring: two front2w3_back2w1 entries both happened to end
        in "...OW", which let a different rule also fit both at once —
        resolved by replacing one entry (GARDEN/FENCE/TENNIS -> TEEN).

    Kind/pipeline note: the real paper answer format is `short_text` (the
    pupil writes in the missing code word) — see
    elevenplus_data/CLAUDE.md's VR answer-kind table. generate_bank.py
    hardcodes every generated Question as `kind = MCQ` with no per-generator
    override yet, so — following Batch 1's precedent — this class presents
    4 real-word MCQ options instead. Distractors are drawn from OTHER pool
    entries' bracket_words (all real short words of a plausible length)
    rather than corrupted strings, so a wrong option never telegraphs
    itself by being obviously not-a-word.
    """

    slug = "vr.wordpattern"
    section, subtopic = "VR", "Word Patterns"
    template_id = "word-pattern"
    difficulties = (1, 2, 3, 4, 5)

    # DIFFICULTY: d1-d2 state the rule outright (apply-pattern) over the
    # easier front/back-of-word1 + front/back-of-word3 shapes; d3 keeps
    # apply-pattern but moves to the harder shapes (3+1 split, or the
    # word3-first concatenation order); d4-d5 are find-pattern -- d4 shows
    # 3 demonstrated examples over the easier shapes, d5 shows only 2 over
    # the harder shapes, which is a strictly harder inference task with
    # less evidence to pin the rule down.
    _EASY_SHAPES = ["front1_front2", "front2_back2"]
    _HARD_SHAPES = ["back2_front2", "front2w3_back2w1", "front3_back1", "back1_back2"]

    def build(self, rng, difficulty):
        if difficulty in (1, 2):
            return self._apply_pattern(rng, difficulty, self._EASY_SHAPES)
        if difficulty == 3:
            return self._apply_pattern(rng, difficulty, self._HARD_SHAPES)
        if difficulty == 4:
            return self._find_pattern(rng, difficulty, self._EASY_SHAPES, n_examples=3)
        return self._find_pattern(rng, difficulty, self._HARD_SHAPES, n_examples=2)

    def _all_brackets(self):
        return [b for examples in _WP_POOL.values() for (_, _, _, b) in examples]

    def _apply_pattern(self, rng, difficulty, shape_pool):
        shape_key = rng.choice(shape_pool)
        rule = _WP_RULE_SHAPES[shape_key]
        examples = _WP_POOL[shape_key]
        demo, target = rng.sample(examples, 2)
        dw1, dw2, dw3, dbracket = demo
        tw1, tw2, tw3, correct = target

        others = [b for b in self._all_brackets() if b != correct and b != dbracket]
        distractors = rng.sample(others, min(4, len(others)))

        return Item(
            stem=(f"In this puzzle, the code word is made from {_wp_rule_desc(rule)}. "
                  f"For example: {dw1}, {dw2}, {dw3} -> ({dbracket}). "
                  f"Using the same rule, what is the code word for: "
                  f"{tw1}, {tw2}, {tw3} -> ( ? )"),
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"qtype": "apply-pattern", "shape": shape_key,
                    "demo": [dw1, dw2, dw3, dbracket], "target": [tw1, tw2, tw3]},
            question_type="apply-pattern",
            explanation=(f"The rule is {_wp_rule_desc(rule)}: applying it to "
                         f"{tw1}/{tw3} gives {correct}."),
        )

    def _find_pattern(self, rng, difficulty, shape_pool, n_examples):
        shape_key = rng.choice(shape_pool)
        rule = _WP_RULE_SHAPES[shape_key]
        examples = _WP_POOL[shape_key]
        chosen = rng.sample(examples, n_examples + 1)
        demo, target = chosen[:n_examples], chosen[n_examples]
        tw1, tw2, tw3, correct = target

        demo_str = "; ".join(f"{w1}, {w2}, {w3} -> ({b})" for (w1, w2, w3, b) in demo)
        others = [b for b in self._all_brackets()
                  if b != correct and b not in [d[3] for d in demo]]
        distractors = rng.sample(others, min(4, len(others)))

        return Item(
            stem=(f"Each set of three words below makes a code word in brackets, "
                  f"using the same rule every time. Work out the rule, then find "
                  f"the missing code word.  {demo_str}; {tw1}, {tw2}, {tw3} -> ( ? )"),
            options=shuffled_options(rng, correct, distractors),
            difficulty=difficulty,
            params={"qtype": "find-pattern", "shape": shape_key,
                    "demo": [[w1, w2, w3, b] for (w1, w2, w3, b) in demo],
                    "target": [tw1, tw2, tw3]},
            question_type="find-pattern",
            explanation=(f"The rule is {_wp_rule_desc(rule)}, so {tw1}/{tw3} give "
                         f"{correct}."),
        )


# Pool: (context_a, context_b, answer, [distractor, ...]). Every entry
# verified: the answer genuinely completes both context templates in two
# distinct senses; every distractor was individually checked against BOTH
# contexts and confirmed to fit at most one (never both — that would be a
# second valid answer, the exact bug class HiddenWord's own discipline
# exists to catch). Independent review confirmed all 20 entries clean,
# including two real bugs found and fixed pre-ship: a "night course"
# collision (dropped for "caddy") and a factual error ("penguin" is
# Antarctic, not Arctic — replaced with "narwhal").
DOUBLE_MEANING = {
    2: [
        ("river ___", "___ account", "bank",
         ["side", "savings", "mouth", "loan"]),
        ("cricket ___", "___ cave", "bat",
         ["ball", "wicket", "man", "sea"]),
        ("wrist ___", "___ TV", "watch",
         ["strap", "see", "band", "note"]),
        ("traffic ___", "___ as a feather", "light",
         ["signal", "cone", "jam", "white"]),
        ("the dog's ___", "the ___ of the tree", "bark",
         ["howl", "growl", "trunk", "root"]),
    ],
    3: [
        ("a duck's ___", "pay the ___", "bill",
         ["beak", "feather", "fee", "invoice"]),
        ("an arctic ___", "___ the envelope", "seal",
         ["walrus", "narwhal", "close", "address"]),
        ("electric ___", "football ___", "fan",
         ["heater", "motor", "supporter", "player"]),
        ("a ___ of the alphabet", "post a ___", "letter",
         ["symbol", "sound", "message", "parcel"]),
        ("a postage ___", "___ your foot", "stamp",
         ["sticker", "label", "tap", "stomp"]),
        ("school ___", "a ___ of fabric", "yard",
         ["playground", "gym", "metre", "piece"]),
        ("wear a ___", "the match ended in a ___", "tie",
         ["scarf", "suit", "draw", "victory"]),
        ("light a ___", "a football ___", "match",
         ["candle", "fire", "tournament", "team"]),
        ("an elephant's ___", "the ___ of a tree", "trunk",
         ["tusk", "ear", "branch", "root"]),
        ("a china ___", "___ the ball", "bowl",
         ["plate", "dish", "throw", "pitch"]),
        ("___ tree", "the ___ of your hand", "palm",
         ["coconut", "banana", "heel", "back"]),
    ],
    4: [
        ("a golf ___", "a night ___", "club",
         ["caddy", "ball", "watchman", "gown"]),
        ("blind as a ___", "a ___ on his arm", "mole",
         ["bat", "rat", "spot", "freckle"]),
        ("the ___ of the eye", "a ___ in the classroom", "pupil",
         ["iris", "lens", "student", "teacher"]),
        ("ocean ___", "___ affairs", "current",
         ["floor", "liner", "foreign", "domestic"]),
    ],
}


@register
class DoubleMeaning(Generator):
    """VR Double Meanings: one word, chosen from 5 free-standing options,
    that fits BOTH of two given phrase templates using two different senses
    of the word (a homograph item) -- e.g. (river ___) / (___ account) ->
    BANK. Confirmed against a real paper (GL Fam T1 Q68-74): the pupil is
    given five whole words to choose from, not two bracketed groups.

    question_type: this generator always uses "word-completes-both" rather
    than the subtopic's other slug "two-senses-one-word". Both slugs name
    the same underlying mechanic, but "word-completes-both" ("A word
    completing both sentences") is the literal, mechanical description of
    what build() does -- fill two separate templates with one shared word --
    whereas "two-senses-one-word" reads as the more abstract concept behind
    it. If a future generator asks the pupil to state or explain the two
    senses directly (rather than just pick the one word that slots into
    both templates), that one should carry "two-senses-one-word" instead.

    5 vs 4 options: shuffled_options()'s `keep` defaults to 3, giving 4
    total options. This class passes keep=4 to get the real paper's 5-option
    shape (1 correct + 4 distractors), since the confirmed real-paper example
    is a 5-word multiple choice and there is no pipeline reason to shrink it.
    """
    slug = "vr.doublemeaning"
    section, subtopic = "VR", "Double Meanings"
    template_id = "double-meaning"
    # DIFFICULTY: the mechanism never changes -- only how everyday/concrete
    # the two senses are. d2 pairs are the most obvious, classic homographs
    # (bank, bat, watch, light, bark); d3 covers a wider common-vocabulary
    # set that's still noun/noun or noun/verb; d4 pairs use a subtler second
    # sense (an adjective/noun switch for "current", a less common sense for
    # "mole"/"pupil"/"club").
    difficulties = (2, 3, 4)

    def build(self, rng, difficulty):
        pool = DOUBLE_MEANING[difficulty]
        context_a, context_b, answer, distractors = rng.choice(pool)
        return Item(
            stem=(f"Which one word completes both of these?  "
                  f"({context_a})   ({context_b})"),
            options=shuffled_options(rng, answer, distractors, keep=4),
            difficulty=difficulty,
            params={"answer": answer, "context_a": context_a, "context_b": context_b},
            question_type="word-completes-both",
            explanation=(f"“{answer}” fits both: "
                         f"{context_a.replace('___', answer)} and "
                         f"{context_b.replace('___', answer)}."),
        )


# Curated word-pair pool for VR Letter Moves (GL Fam T1 Q1-7; CGP-GL Q8-12):
# word_a and word_b are both real words; moving exactly one letter OUT of
# word_a (deleting it, keeping the rest of word_a's letters in the same
# order) and INTO word_b (inserted anywhere, again keeping word_b's own
# letters in order) turns both into different real words.
#
# Verified programmatically, not by eye -- the same discipline HiddenWord's
# own comment describes and for the same reason its first draft needed it:
# it is not enough for the INTENDED move to work, every OTHER possible
# single-letter move (any letter, either direction, inserted at any
# position in the other word) has to be checked and shown NOT to also
# produce two real words, or the item has two defensible answers.
#
# That exhaustive check went through two dictionary attempts before this
# pool was usable at all: an unabridged system dictionary (~236k entries)
# failed 21 of the first 23 hand-built candidates, not because the
# candidates were bad, but because an unabridged dictionary is stuffed with
# obscure dialect/archaic entries that surface as a spurious SECOND valid
# move for almost any short insertion — too permissive a bar to build
# against. Switching to the intersection of that dictionary with a
# top-50,000-by-frequency English word list fixed that. The final pool was
# then produced by an exhaustive search (not further hand-guessing) over
# 9,927 unique candidate pairs of the shape every hand-built survivor
# shared (a 5-letter word_a losing a consonant to leave a 4-letter word,
# paired with a 3-letter word_b gaining that consonant); 528 pairs survived
# the full uniqueness check, and 28 were hand-picked from those for
# everyday vocabulary and coverage across 18 distinct moved letters.
# Independent re-verification (a from-scratch dictionary load, not trusting
# the author's word list) confirmed all 28 are genuinely unique, with one
# entry swapped after the reviewer flagged a borderline alternate move
# (BRAND/RAW's alternate RAND/BRAW, where both sides were real if archaic
# words) for MORAL/ANY -> ORAL/MANY, which has zero alternate moves at all.
#
# Tuple shape: (word_a, word_b, new_a, new_b, moved_letter).
LETTERMOVE_D3 = [
    ("CHASE", "OLD", "CASE", "HOLD", "H"),
    ("BREAD", "ONE", "READ", "BONE", "B"),
    ("GHOST", "ONE", "HOST", "GONE", "G"),
    ("FACED", "ONE", "FACE", "DONE", "D"),
    ("PLANE", "LAY", "LANE", "PLAY", "P"),
    ("EARLY", "COP", "EARL", "COPY", "Y"),
    ("WHEEL", "DON", "HEEL", "DOWN", "W"),
    ("DRIVE", "POT", "DIVE", "PORT", "R"),
    ("SPEAK", "AID", "PEAK", "SAID", "S"),
    ("BLACK", "HER", "LACK", "HERB", "B"),
]
LETTERMOVE_D4 = [
    ("MAKER", "BID", "MAKE", "BIRD", "R"),
    ("THINK", "BAN", "THIN", "BANK", "K"),
    ("FRANK", "OLD", "RANK", "FOLD", "F"),
    ("SOLVE", "ICE", "SOLE", "VICE", "V"),
    ("BRUSH", "AGE", "BUSH", "RAGE", "R"),
    ("MARCH", "TIE", "ARCH", "TIME", "M"),
    ("SNAKE", "PIG", "SAKE", "PING", "N"),
    ("BEAST", "OWL", "EAST", "BOWL", "B"),
    ("HAVEN", "BID", "HAVE", "BIND", "N"),
]
LETTERMOVE_D5 = [
    ("TRAIN", "PIN", "RAIN", "PINT", "T"),
    ("CRATE", "LOCK", "RATE", "CLOCK", "C"),
    ("CHOSE", "AID", "HOSE", "ACID", "C"),
    ("DEALT", "MIN", "DEAL", "MINT", "T"),
    ("STONE", "PET", "TONE", "PEST", "S"),
    ("LATEX", "NET", "LATE", "NEXT", "X"),
    ("CLEAN", "AMP", "LEAN", "CAMP", "C"),
    ("MORAL", "ANY", "ORAL", "MANY", "M"),
    ("FLAME", "AMP", "FAME", "LAMP", "L"),
]


@register
class LetterMove(Generator):
    """VR Letter Moves (GL Fam T1 Q1-7; CGP-GL Q8-12): two real words are
    given; moving one letter out of the first and into the second (each
    word's own remaining letters stay in the same relative order) turns
    BOTH into different real words. The pupil identifies the resulting
    pair.

    Every pool entry is checked by exhaustive search, not by eye: for the
    given pair, EVERY possible single-letter move -- any letter, either
    direction, inserted at any position in the other word -- is tried
    against a real-word dictionary, and an entry is kept only if the
    intended move is the ONLY one that turns both words real. See the
    pool's own comment above LETTERMOVE_D3 for the dictionary methodology.

    Only `move-one-letter` is implemented. The taxonomy's other
    question_type for this subtopic, `swap-two-letters`, is a DIFFERENT
    mechanic (real papers describe two letters trading places, not one
    letter relocating), and none of the evidence cited for this subtopic
    (GL Fam T1 Q1-7, CGP-GL Q8-12) demonstrates it -- both citations are
    move-one-letter items. Left for whenever real-paper evidence for that
    question_type specifically turns up (same posture NumberSequence takes
    with the rule shapes it hasn't been shown evidence for).

    Kind/pipeline note, same gap LetterAlgebra documents: the natural
    answer format here is `short_text` (the pupil writes the two new
    words), but generate_bank.py hardcodes every generated Question as
    `kind = MCQ`. So this class presents 4 options -- the correct
    (new_a, new_b) pair plus 3 plausible-but-wrong pairs built from the
    same two words -- rather than a free-text pair.
    """
    slug = "vr.lettermove"
    section, subtopic = "VR", "Letter Moves"
    template_id = "letter-move"
    difficulties = (3, 4, 5)

    def build(self, rng, difficulty):
        pool = {3: LETTERMOVE_D3, 4: LETTERMOVE_D4, 5: LETTERMOVE_D5}[difficulty]
        word_a, word_b, new_a, new_b, letter = rng.choice(pool)

        correct = f"{new_a}, {new_b}"
        # Distractors model the two real slips this item invites: changing
        # only ONE of the two words and leaving the other as given (forgot
        # the letter has to arrive somewhere), in both directions, and
        # reporting the two correct results but in the WRONG word's slot
        # (mixed up which word lost the letter and which gained it).
        only_b_changed = f"{word_a}, {new_b}"
        only_a_changed = f"{new_a}, {word_b}"
        swapped = f"{new_b}, {new_a}"
        return Item(
            stem=(f"Move one letter from “{word_a}” to “{word_b}” to make two "
                  f"new words. Which pair is correct?"),
            options=shuffled_options(rng, correct,
                                     [only_b_changed, only_a_changed, swapped]),
            difficulty=difficulty,
            params={"word_a": word_a, "word_b": word_b, "letter": letter,
                    "new_a": new_a, "new_b": new_b},
            question_type="move-one-letter",
            explanation=(f"Moving {letter} out of {word_a} leaves {new_a}, and "
                         f"putting it into {word_b} makes {new_b}."),
            misconceptions={
                only_b_changed: "only-changed-one-word",
                only_a_changed: "only-changed-one-word",
                swapped: "mixed-up-which-word-changed",
            },
        )


# Curated pool for VR Paired Antonyms (GL Fam T1 Q30-37/T3 Q7-15, CGP-GL
# Q76-80, ISEB Section 4). Each entry: (pos, a_target, (a_filler1,
# a_filler2), b_target, (b_filler1, b_filler2), extra). `pos` records the
# shared part of speech of every word in the entry (all adjectives, or all
# nouns) -- necessary but not sufficient, see the class docstring.
#
# SHIPPED WITH REDUCED SCOPE. Three successive pool designs were tried and
# each failed independent review for a different variant of the same
# underlying flaw -- a pupil could answer correctly with no antonym
# knowledge at all:
#   rev 1: fillers were concrete nouns against abstract targets -> the
#          correct answer was always the one option with a different WORD
#          CLASS (confirmed across 20,000 generated items).
#   rev 2: fillers were same-part-of-speech but drawn from an unrelated
#          semantic domain (e.g. shape words -- "square", "striped" --
#          against temperature/size/speed targets) -> the correct answer
#          was always the one option from a different TOPIC (confirmed in
#          15 of 26 entries).
#   rev 3: fillers were borrowed wholesale from OTHER entries' own target
#          pairs -> a pupil could spot the two borrowed words as an
#          obviously-recognisable decoy PAIR, eliminate them, then use the
#          same topic-mismatch tell from rev 2 on what was left -- stacking
#          both prior flaws rather than fixing either.
# The 11 entries below (personality traits, sports, travel) draw fillers
# from a genuinely matching semantic category for each entry without
# reusing another entry's own pair, and passed independent review clean at
# 30,000+ builds: no word-class tell, no topic tell, no idiom/theme
# collision (an early draft's "trumpet"/"drum" decoys for "arrogant" were
# dropped for independently carrying the same boastfulness idiom as the
# target; "hare" was dropped as a "defeat" decoy for echoing The Tortoise
# and the Hare). The other 15 entries (concrete physical qualities --
# hot/cold, big/small, and similar) are deferred rather than shipped with a
# fourth invented filler strategy -- see plans.md's VR generator coverage
# entry for the full history and for whoever picks this up with real paper
# examples for that tier specifically.
ANTONYM_POOL = [
    ("adj", "diligent", ("shy", "talkative"), "lazy", ("curious", "graceful"), "stubborn"),
    ("noun", "victory", ("stadium", "timer"), "defeat", ("whistle", "scoreboard"), "referee"),
    ("noun", "arrival", ("suitcase", "timetable"), "departure", ("ticket", "platform"), "passport"),
    ("adj", "brave", ("curious", "tidy"), "cowardly", ("forgetful", "sleepy"), "talkative"),
    ("adj", "generous", ("punctual", "talkative"), "stingy", ("impatient", "clumsy"), "studious"),
    ("adj", "honest", ("sleepy", "energetic"), "deceitful", ("graceful", "serious"), "curious"),
    ("adj", "polite", ("studious", "forgetful"), "rude", ("clumsy", "curious"), "punctual"),
    ("adj", "cautious", ("tidy", "talkative"), "reckless", ("sleepy", "forgetful"), "studious"),
    ("adj", "cheerful", ("punctual", "stubborn"), "gloomy", ("curious", "graceful"), "talkative"),
    ("adj", "humble", ("sleepy", "forgetful"), "arrogant", ("clumsy", "serious"), "curious"),
    ("adj", "calm", ("tidy", "studious"), "frantic", ("curious", "punctual"), "clumsy"),
]
_ANTONYM_D3 = ANTONYM_POOL[0:3]
_ANTONYM_D4 = ANTONYM_POOL[3:7]
_ANTONYM_D5 = ANTONYM_POOL[7:11]


@register
class AntonymPair(Generator):
    """VR Paired Antonyms: two bracket groups of 3 words each; the pupil
    picks the one word from each bracket that is most nearly OPPOSITE in
    meaning of any cross-bracket pair -- e.g. (careful, tidy, talkative)
    (reckless, sleepy, forgetful) -> careful/reckless. Confirmed against
    real papers (GL Fam T1 Q30-37/T3 Q7-15, CGP-GL Q76-80, ISEB Section 4).
    See the pool comment above ANTONYM_POOL for why this ships with only 11
    of the originally-drafted 26 entries.

    KIND/PIPELINE MISMATCH: elevenplus_data/CLAUDE.md maps this bracket-pair
    shape to `grouped_options` (pick one word from each of two groups), but
    `Item` only supports a flat `options` list and generate_bank.py only
    ever writes MCQ -- the same gap LetterAlgebra's docstring documents for
    Letter Algebra. This generator flattens the task: both brackets are
    shown in the stem exactly as a real paper would print them, one
    bracket's word is fixed as part of the question ("which word from the
    OTHER bracket is most opposite in meaning to X?"), and that other
    bracket's 3 words become the answer choices, padded with one
    same-part-of-speech extra word to reach a normal 4-option MCQ. Which
    bracket is "first" (the fixed one) is randomised per build so the fixed
    word isn't always drawn from the same side.

    QUESTION_TYPE CHOICE: uses `opposite-pair` rather than the subtopic's
    other slug `one-from-each-group`. The flattened implementation only
    ever asks the pupil to complete one pair (fixed word + best match from
    the second bracket), never to solve both brackets independently -- the
    authentic, un-flattened GL/CGP mechanic `one-from-each-group`'s name
    implies -- which is closer to "find the most opposite pair". Both slugs
    remain weakly/zero evidenced, so this is a low-risk pick rather than a
    settled one.
    """

    slug = "vr.antonympair"
    section, subtopic = "VR", "Paired Antonyms"
    template_id = "antonym-pair-bracket"
    difficulties = (3, 4, 5)

    def build(self, rng, difficulty):
        pool = {3: _ANTONYM_D3, 4: _ANTONYM_D4, 5: _ANTONYM_D5}[difficulty]
        pos, a_target, a_fillers, b_target, b_fillers, extra = rng.choice(pool)

        bracket_a = [a_target, a_fillers[0], a_fillers[1]]
        bracket_b = [b_target, b_fillers[0], b_fillers[1]]
        rng.shuffle(bracket_a)
        rng.shuffle(bracket_b)

        if rng.random() < 0.5:
            first_group, second_group = bracket_a, bracket_b
            fixed_word, correct = a_target, b_target
        else:
            first_group, second_group = bracket_b, bracket_a
            fixed_word, correct = b_target, a_target

        distractors = [w for w in second_group if w != correct] + [extra]
        rng.shuffle(distractors)

        stem = (
            f"({', '.join(first_group)})   ({', '.join(second_group)})\n"
            f"Which word in the second group is most nearly OPPOSITE in "
            f"meaning to “{fixed_word}” in the first group?"
        )
        return Item(
            stem=stem,
            options=shuffled_options(rng, correct, distractors, keep=3),
            difficulty=difficulty,
            params={
                "first_group": sorted(first_group),
                "second_group": sorted(second_group),
                "fixed": fixed_word,
                "correct": correct,
                "extra": extra,
                "pos": pos,
            },
            question_type="opposite-pair",
            explanation=(
                f"“{fixed_word}” means the opposite of “{correct}”. None of "
                f"the other words in the second group have that relationship "
                f"with “{fixed_word}”."
            ),
            misconceptions={d: "not-an-antonym-of-the-fixed-word" for d in distractors},
        )
