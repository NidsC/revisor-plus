"""
Verbal Reasoning generators.

VR is more algorithmic than it looks: codes, letter sequences and hidden words are
pure string manipulation, and analogies and odd-one-out need only a curated set of
word groups plus combinatorics. The word data below is ordinary English vocabulary
chosen for this purpose — nothing is lifted from a published paper.

Each generator names one canonical VR subtopic from elevenplus_data/taxonomy.json.
Seven of the taxonomy's 24 are covered here; the rest are pack territory. Question
forms that used to share a subtopic — codes with letter sequences, hidden words
with compound words — are now filed separately, because the taxonomy separates
them and a pupil weak on one is not necessarily weak on the other.
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
HIDDEN = [
    ("The chef made a superb owl-shaped cake.", "BOWL"),
    ("We should ask her mother about it.", "ASKHER"),
    ("The plan tables were left in the hall.", "ANTA"),
    ("He hid behind the great oak tree.", "ATOA"),
    ("I saw a strange bird in the garden.", "GEBI"),
    ("Please carry on with the task.", "RYON"),
    ("The storm arrived before dawn.", "MAR"),
    ("She left her scarf on the bus.", "FON"),
]

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
        sentence, hidden = rng.choice(HIDDEN[:4] if difficulty == 3 else HIDDEN)
        letters = "".join(c for c in sentence.upper() if c.isalpha())
        # Distractors are real substrings of the sentence that are NOT words, so
        # the pupil has to check meaning rather than just spot a run of letters.
        idx = letters.find(hidden)
        near = [letters[max(0, idx - 2):idx + 2], letters[idx + 1:idx + 5],
                letters[max(0, idx - 4):idx]]
        return Item(
            stem=(f"A {len(hidden)}-letter word is hidden across the end of one word "
                  f"and the start of the next. Find it:  “{sentence}”"),
            options=shuffled_options(rng, hidden, [n for n in near if n and n != hidden]),
            difficulty=difficulty,
            params={"sentence": sentence},
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
