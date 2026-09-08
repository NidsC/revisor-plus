"""
Verbal Reasoning generators.

VR is more algorithmic than it looks: codes, letter sequences and hidden words are
pure string manipulation, and analogies and odd-one-out need only a curated set of
word groups plus combinatorics. The word data below is ordinary English vocabulary
chosen for this purpose — nothing is lifted from a published paper.

Each generator names one canonical VR subtopic from elevenplus_data/taxonomy.json.
All 24 are covered here as of `MiddleWord` (see its own docstring) -- this count was
stale at "twenty-one" for a while before that; check `catalog/generators/__init__.py`'s
`REGISTRY` if it drifts again rather than trusting this comment. Question
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

MustBeTrue (Batch 3) is a logic-puzzle generator, not a curated-pool one, and was
treated as its own design pass rather than a quick fourth/fifth generator, per this
project's own warning that a "must be true" item with an under-determined world is
the worst failure mode a hand-written logic puzzle can have. It sidesteps that risk
by only ever generating scenarios where the stated rules fully pin down a day-by-day
table with no residual freedom — see its own docstring. Verified against three
independently-written solvers (never trusting the generator's own labelling) across
tens of thousands of builds, catching one real fairness gap (a rule combination that
let an entity become trivially true every day) before it shipped.

Anagram, ConnectingLetter and Directions close 3 of the last 4 gap subtopics, after
this project's own paper corpora (VR resources/ and VR example papers /) turned up
no evidence for any of the remaining 4 (middle_word, anagrams, connecting_letter,
directions). Their mechanics instead come from published 11+ type descriptions found
via web research rather than a paper read directly by this project — a weaker-but-
still-cited form of evidence, flagged honestly in each class's own docstring, the
same way an earlier VR promotion was flagged as "collaborator report, not a paper
audited here" in taxonomy.json. `middle_word` turned out to duplicate WordPattern's
own mechanic under a different publisher's name and was not built — see plans.md.
Directions shipped only after two serious bugs (a real-world/grid unit mismatch, and
under-determined indirect-pair questions) were caught by independent verification and
fixed at the root cause; see its own docstring for the full account.

CONVENTION — params["variant"]. When a generator can build more than one structural
shape under the SAME question_type (LetterAnalogy's "single"/"pair"/"swap" all answer
under a different question_type each, so they don't need one; NumberCode's two
code-to-number branches — decode a whole word vs. one isolated letter — share a
question_type and do), record which shape it built under a single "variant" key in
params. Never invent a second key ("qtype", "mode", "shape", "kind" have all been used
here at one point) for a second axis — compose one string instead, colon-separated
(NumberCode: "code-to-number:word" / "code-to-number:letter"; WordPattern:
"find-pattern:front_2_back_2"). "kind" specifically is reserved for Item.kind (the
answer-mechanism format — mcq/numeric/short_text/etc.) below; a generator that used
params["kind"] for its own purposes before this convention has been migrated to
"variant". Omit the key entirely when a generator has only one shape per question_type
(MissingNumberSum's missing-operator/balance-both-sides branches, for instance) —
presence of the key is itself a signal that real structural variety exists to measure.

EXCEPTION — gen_key collisions across DIFFERENT question_types. Item.key() hashes
generator slug + template_id + params ONLY; question_type is not part of the identity.
So when two different question_types can be built from the SAME underlying draw (as
LetterCode's word-to-code/code-to-word do — both directions of one (word, shift)
puzzle), params still needs a "variant" key even though the question_types already
differ, or the two Items collide on one gen_key and overwrite each other. The "presence
of the key signals real variety" reading above is about within-question_type shapes;
this is a second, narrower reason to keep it, worth checking whenever a generator
starts drawing one puzzle and presenting it more than one way.
"""
import string

from . import Generator, Item, register, shuffled_options
from .analogy_data import CLASS as ANALOGY_CLASS
from .analogy_data import DEFENSIBLE as ANALOGY_DEFENSIBLE
from .analogy_data import PAIRS as ANALOGY_PAIRS
from .analogy_data import RELATIONS as ANALOGY_RELATIONS
from .analogy_data import B_WORDS as ANALOGY_B_WORDS
from .analogy_data import render as analogy_render
from .compound_data import ATTACHING, KEYS, TAILS
from .oddoneout_data import CATEGORIES, FAR_FOILS, NEAR_FOILS

ALPHABET = string.ascii_uppercase


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



@register
class LetterCode(Generator):
    slug = "vr.code"
    section, subtopic = "VR", "Letter Codes"
    template_id = "letter-shift-code"

    # Word pool: 30 words across lengths 3-6
    WORDS = [
        # 3-letter (8)
        "CAT", "DOG", "PEN", "HAT", "SUN", "BED", "CUP", "JAR",
        # 4-letter (10)
        "TREE", "LAMP", "BIRD", "FROG", "CAKE", "BOOK", "FISH", "STAR", "BOAT", "DUCK",
        # 5-letter (7)
        "STONE", "RIVER", "HOUSE", "PLANT", "CHAIR", "CLOUD", "TIGER",
        # 6-letter (5)
        "CANDLE", "BRIDGE", "MONKEY", "PENCIL", "WINDOW",
    ]

    # PROVISIONAL — not checked against a real GL letter-codes paper. Which shifts
    # sit in which band is our judgement: magnitude, then direction, then whether
    # the direction alternates. One shift per band would make every question in it
    # the same puzzle with a different word, so each band offers several of
    # comparable difficulty.
    SHIFTS = {
        1: (1, 2),
        2: (2, 3, 4),
        3: (-1, -2),
        4: (3, 4, 5, -3, -4),
        5: (2, -2, 3, -3),
    }

    def __init__(self):
        super().__init__()
        # Per-difficulty pools of (target, shift) puzzles, drawn without replacement
        self._pools = {}
        # Used puzzles, tracked across difficulties: the bands share shift values,
        # so the same puzzle could otherwise be served under two difficulty labels.
        self._used = set()

    def _draw(self, rng, difficulty):
        """Draw an unused (target, shift) puzzle, plus an example word to show it with.

        The puzzle is the pair, not the triple: the example only demonstrates the
        rule, so two questions sharing a target and shift have identical options
        and identical answers however the example is varied.
        """
        if difficulty not in self._pools or not self._pools[difficulty]:
            targets = [w for w in self.WORDS if len(w) <= 3 + difficulty]
            puzzles = [(tgt, sh) for tgt in targets for sh in self.SHIFTS[difficulty]
                       if (tgt, sh) not in self._used]
            rng.shuffle(puzzles)
            self._pools[difficulty] = puzzles
        while self._pools[difficulty]:
            puzzle = self._pools[difficulty].pop()
            if puzzle not in self._used:
                self._used.add(puzzle)
                word, shift = puzzle
                example = rng.choice([w for w in self.WORDS
                                      if w != word and len(w) <= 4])
                return example, word, shift
        raise RuntimeError(f"LetterCode puzzles exhausted for difficulty {difficulty}")

    def build(self, rng, difficulty):
        # DIFFICULTY: a +1 shift is spotted instantly; larger shifts, backwards
        # shifts and alternating shifts each add a step of reasoning.
        example, word, shift = self._draw(rng, difficulty)
        alternating = difficulty == 5

        def encode(w):
            out = []
            for i, ch in enumerate(w):
                s = shift * (1 if not alternating or i % 2 == 0 else -1)
                out.append(ALPHABET[(ALPHABET.index(ch) + s) % 26])
            return "".join(out)

        def uniform(w, s):
            return "".join(ALPHABET[(ALPHABET.index(c) + s) % 26] for c in w)

        # Both directions of the SAME (word, shift) puzzle are drawn from one
        # shared per-difficulty pool via _draw's `_used` tracking above, so a
        # puzzle served as code-to-word can never also be served, unchanged,
        # as word-to-code (or vice versa) — the two variants compete for the
        # same finite puzzle supply rather than doubling it.
        if rng.random() < 0.5:
            return self._build_code_to_word(rng, difficulty, example, word, shift,
                                            alternating, encode)
        return self._build_word_to_code(rng, difficulty, example, word, shift,
                                        alternating, encode, uniform)

    def _build_word_to_code(self, rng, difficulty, example, word, shift,
                            alternating, encode, uniform):
        # An off-by-one in the wrong direction would be a zero shift — i.e. the
        # word printed unchanged, which no pupil picks and which hands over a
        # free elimination. Step the other way when that happens.
        miscount = shift + 1 if shift + 1 not in (0, shift, -shift) else shift - 1
        correct = encode(word)
        wrong_way = uniform(word, -shift)
        # More distractors than slots, so a collision costs a spare rather than an
        # option: `uniform(word, shift)` IS the key unless the shift alternates, so
        # it only survives at difficulty 5 — where missing the alternation is the
        # mistake the question is actually about.
        return Item(
            stem=(f"If {example} is written in code as {encode(example)}, "
                  f"how is {word} written in the same code?"),
            options=shuffled_options(rng, correct, [
                wrong_way,
                uniform(word, miscount),
                word[::-1],
                uniform(word, shift),
                uniform(word, shift * 2),
            ]),
            difficulty=difficulty,
            params={"variant": "word-to-code", "word": word, "shift": shift,
                    "alt": alternating},
            question_type="word-to-code",
            explanation=(f"Each letter moves {abs(shift)} place"
                         f"{'s' if abs(shift) != 1 else ''} "
                         f"{'forward' if shift > 0 else 'back'} in the alphabet"
                         f"{', alternating direction' if alternating else ''}, "
                         f"giving {correct}."),
            misconceptions={wrong_way: "shifted-the-wrong-way"},
        )

    def _build_code_to_word(self, rng, difficulty, example, word, shift,
                            alternating, encode):
        """The reverse presentation: the code is shown, the plaintext is the
        answer. Uniqueness is not assumed — it follows from the same shift
        being a per-position bijection on the alphabet (a substitution
        cipher), so two DIFFERENT same-length words always encode to
        DIFFERENT codes under this shift; no distractor word can therefore
        also produce the shown code, whatever length-matched word is drawn.
        """
        code = encode(word)
        pool = [w for w in self.WORDS if len(w) == len(word) and w != word]
        if len(pool) < 3:
            return None
        wrong = rng.sample(pool, 3)
        return Item(
            stem=(f"If {example} is written in code as {encode(example)}, "
                  f"which word is written in the same code as {code}?"),
            options=shuffled_options(rng, word, wrong),
            difficulty=difficulty,
            params={"variant": "code-to-word", "word": word, "shift": shift,
                    "alt": alternating},
            question_type="code-to-word",
            explanation=(f"Each letter moves {abs(shift)} place"
                         f"{'s' if abs(shift) != 1 else ''} "
                         f"{'forward' if shift > 0 else 'back'} in the alphabet"
                         f"{', alternating direction' if alternating else ''}, "
                         f"so {code} decodes to {word}."),
        )


def _places(step):
    """'3 places forward' / '1 place back' — used in explanations."""
    return (f"{abs(step)} place{'s' if abs(step) != 1 else ''} "
            f"{'forward' if step > 0 else 'back'}")


@register
class LetterSequence(Generator):
    slug = "vr.letterseq"
    section, subtopic = "VR", "Letter Sequences"
    template_id = "letter-sequence"

    # PROVISIONAL — not checked against a real GL letter-sequences paper. Which
    # steps sit in which band is our judgement, on the axis LetterCode.SHIFTS
    # already uses: magnitude first, then direction. One step per band made every
    # question in that band the same puzzle at a different starting letter — the
    # defect b7615bd fixed for LetterCode and this table fixes here.
    STEPS = {
        1: (1, 2),
        2: (2, 3),
        3: (3, 4, -2),
        4: (-2, -3, -4, 5),
        5: (2, 3, -2, -3),
    }
    # Band 5 interleaves two sequences, so the second letter needs its own step.
    # It must differ from the first letter's step, or the pair moves as a block
    # and the question is a one-rule item wearing pairs.
    SECOND_STEPS = (1, 3, 4, -1, -3)

    PAIRED_BAND = 5

    def __init__(self):
        super().__init__()
        # Per-difficulty pools of puzzles, drawn without replacement.
        self._pools = {}
        # Used puzzles, tracked across difficulties: the bands share step values,
        # so the same puzzle could otherwise be served under two difficulty labels.
        self._used = set()

    def _draw(self, rng, difficulty):
        """Draw an unused puzzle for this band.

        The puzzle is the starting letter(s) and the step(s) — everything a pupil
        reads a rule out of. Two questions agreeing on those are the same
        question however they are shuffled, so they are drawn without
        replacement, the fix 1fb28f1 made for LetterCode and never reached here.
        """
        if not self._pools.get(difficulty):
            if difficulty == self.PAIRED_BAND:
                puzzles = [(start, step, second, second_step)
                           for start in range(26)
                           for step in self.STEPS[difficulty]
                           for second in range(26)
                           for second_step in self.SECOND_STEPS
                           if second_step != step]
            else:
                puzzles = [(start, step, None, None)
                           for start in range(26)
                           for step in self.STEPS[difficulty]]
            puzzles = [p for p in puzzles if p not in self._used]
            rng.shuffle(puzzles)
            self._pools[difficulty] = puzzles
        while self._pools[difficulty]:
            puzzle = self._pools[difficulty].pop()
            if puzzle not in self._used:
                self._used.add(puzzle)
                return puzzle
        raise RuntimeError(
            f"LetterSequence puzzles exhausted for difficulty {difficulty}")

    def build(self, rng, difficulty):
        # DIFFICULTY: a small forward step is spotted instantly; a larger step, a
        # backward one, and a second interleaved sequence each add a step of
        # reasoning. The start is any letter of the alphabet in every band — the
        # sequence wrapping round past Z is part of the skill, and clamping it
        # away (`max(start, 6)`, once applied to the backward bands) collapsed
        # six of band 4's fourteen starts onto one.
        start, step, second, second_step = self._draw(rng, difficulty)

        if difficulty == self.PAIRED_BAND:
            def pair(first, rest):
                return f"{ALPHABET[first % 26]}{ALPHABET[rest % 26]}"

            terms = [pair(start + i * step, second + i * second_step)
                     for i in range(4)]
            correct = pair(start + 4 * step, second + 4 * second_step)
            candidates = [
                pair(start + 4 * step, second + 3 * second_step),   # 2nd left behind
                pair(start + 3 * step, second + 4 * second_step),   # 1st left behind
                pair(start + 5 * step, second + 5 * second_step),   # one term too far
                pair(start + 4 * step, second + 4 * step),          # one rule for both
                pair(start + 4 * second_step, second + 4 * step),   # steps swapped
            ]
            explanation = (f"The first letters move {_places(step)} each time and "
                           f"the second letters move {_places(second_step)}, "
                           f"giving {correct}.")
            question_type = "paired-letters"
            params = {"start": start, "step": step, "second": second,
                      "second_step": second_step, "d": difficulty}
            misconceptions = {}
        else:
            terms = [ALPHABET[(start + i * step) % 26] for i in range(5)]
            correct = ALPHABET[(start + 5 * step) % 26]
            one_too_far = ALPHABET[(start + 6 * step) % 26]
            backwards = ALPHABET[(start - step) % 26]
            wrong_way = ALPHABET[(start - 5 * step) % 26]
            candidates = [
                one_too_far,                              # counted an extra term
                backwards,                                # read the sequence in reverse
                ALPHABET[(start + 5 * step + 1) % 26],    # miscounted the alphabet
                wrong_way,                                # stepped the wrong way
                ALPHABET[(start + 5 * step - 1) % 26],
            ]
            explanation = (f"The letters move {_places(step)} each time, "
                           f"giving {correct}.")
            question_type = "constant-shift"
            params = {"start": start, "step": step, "d": difficulty}
            misconceptions = {backwards: "applied-the-step-backwards",
                              wrong_way: "shifted-the-wrong-way"}

        # A distractor already printed in the sequence hands over a free
        # elimination — no pupil picks a term the question has just shown them,
        # and the old third distractor was ALWAYS the last term shown. Same guard
        # as LetterCode's `miscount`, which sidesteps the shift that would print
        # the word unchanged. More candidates than slots, so a collision costs a
        # spare rather than an option.
        shown = set(terms)
        distractors = [c for c in candidates if c != correct and c not in shown]
        options = shuffled_options(rng, correct, distractors)
        chosen = {text for text, _ in options}
        return Item(
            stem=f"What comes next in this sequence?  {', '.join(terms)}, ___",
            options=options,
            difficulty=difficulty,
            params=params,
            question_type=question_type,
            explanation=explanation,
            misconceptions={text: slug for text, slug in misconceptions.items()
                            if text in chosen},
        )


# (words shown from the category, which foil pool). A FAR foil comes from
# another domain and is obvious; a NEAR foil comes from a neighbouring category
# and has to be rejected with a reason. Those are two different questions, which
# is what the old `foils[:1]` split was reaching for -- it just made bands 1 and
# 2 identical to each other, and 3 and 4 identical to each other, so four labels
# described two bands.
_ODD_BANDS = {1: (3, "far"), 2: (4, "far"), 3: (4, "near"), 4: (5, "near"), 5: (6, "near")}


@register
class OddOneOut(Generator):
    slug = "vr.oddoneout"
    section, subtopic = "VR", "Odd One Out"
    template_id = "odd-one-out"
    difficulties = (1, 2, 3, 4, 5)

    def build(self, rng, difficulty):
        n, kind = _ODD_BANDS[difficulty]
        # "Two Odd Ones Out" -- the established GL format asking a pupil to
        # find the TWO words that don't belong, not one -- is only offered at
        # the "near" bands (3-5): it needs two foils each requiring a reason
        # to reject, which is exactly what NEAR_FOILS is for. Pairing it with
        # the far/obvious bands would ask a band-1-grade question twice over,
        # not a genuinely harder one.
        two_odd = kind == "near" and rng.random() < 0.5
        pools = NEAR_FOILS if kind == "near" else FAR_FOILS
        cats = sorted(CATEGORIES)
        rng.shuffle(cats)
        for slug in cats:
            label, members = CATEGORIES[slug]
            if len(members) < n or len(pools[slug]) < (2 if two_odd else 1):
                continue
            shown = rng.sample(members, n)
            if two_odd:
                odd_a, odd_b = rng.sample(pools[slug], 2)
                return self._build_two_odd(rng, difficulty, slug, label, shown,
                                           odd_a, odd_b)
            odd = rng.choice(pools[slug])
            return Item(
                # EVERY word in the stem is an option. The old version printed
                # `n` members plus the odd one but offered only `chosen[:3]`,
                # so at bands 3-4 one word on the page could not be picked --
                # and the explanation then named it as one of the words that DO
                # belong. Passing keep=n is what keeps the two lists in step.
                stem=("Which is the odd one out?  "
                      + ", ".join(rng.sample(shown + [odd], n + 1))),
                options=shuffled_options(rng, odd, shown, keep=n),
                difficulty=difficulty,
                # `difficulty` is part of the identity. Without it the same
                # category and word set at two bands hashed to one gen_key and
                # the bands overwrote each other's rows.
                params={"variant": "single-odd", "category": slug, "odd": odd,
                        "words": sorted(shown), "difficulty": difficulty},
                question_type="by-category",
                explanation=(f"{', '.join(sorted(shown))} are all {label}. "
                             f"{odd.capitalize()} is not."),
            )
        return None

    def _build_two_odd(self, rng, difficulty, slug, label, shown, odd_a, odd_b):
        """Two Odd Ones Out: n category members shown alongside two foils,
        and the pupil must name BOTH outsiders. Exactly two of the n+2 shown
        words are ever non-members -- `shown` is drawn from the category's
        own member list and odd_a/odd_b from NEAR_FOILS, which is already
        proven (test_odd_one_out.py) disjoint from every category's own
        members -- so there is never a third defensible "odd one" hiding
        among the n category words.

        The answer is a PAIR, so options are candidate pairs of words (as
        plain MCQ text, no model/pipeline change needed) rather than single
        words. The two "half-right" distractors -- a real foil paired with a
        real member -- are the natural trap: a pupil who spots only one of
        the two outsiders picks one of these.
        """
        correct_pair = f"{odd_a} and {odd_b}"
        decoys = list(shown)
        rng.shuffle(decoys)
        half_right_1 = f"{odd_a} and {decoys[0]}"
        half_right_2 = f"{odd_b} and {decoys[1]}"
        both_members = f"{decoys[2]} and {decoys[3]}"
        options = shuffled_options(
            rng, correct_pair, [half_right_1, half_right_2, both_members])
        chosen = {text for text, is_correct in options if not is_correct}
        misconceptions = {
            pair: "found-only-one-of-the-two-odd-words-out"
            for pair in (half_right_1, half_right_2) if pair in chosen
        }
        return Item(
            stem=("Which TWO words are the odd ones out?  "
                  + ", ".join(rng.sample(shown + [odd_a, odd_b], len(shown) + 2))),
            options=options,
            difficulty=difficulty,
            params={"variant": "two-odd", "category": slug,
                    "odd": sorted([odd_a, odd_b]), "words": sorted(shown),
                    "difficulty": difficulty},
            question_type="by-category",
            explanation=(f"{', '.join(sorted(shown))} are all {label}. "
                         f"{odd_a.capitalize()} and {odd_b} are not."),
            misconceptions=misconceptions,
        )


# Distractor pressure and vocabulary tier per band -- the two axes that replace
# "the relation type IS the difficulty". The old generator sliced a 7-element
# relation list per band, so band determined relation: a pupil who learned that
# band 5 is always degree-or-opposite knew the relation before reading the stem,
# and bands 1/2, 2/3, 3/4 and 4/5 shared a relation apiece and so produced
# byte-identical questions.
#
# (exemplar tier, target tier, same-class distractors). All five entries differ
# in at least one axis, so no two bands can emit the same question.
#
# Band 1 has NO same-class distractor, so it is deliberately answerable by
# spotting which option is the same kind of thing as the exemplar's answer. That
# is a scaffold for the weakest pupils, not an oversight -- it is the tell that
# bands 2-5 exist to close, and test_word_analogies.py measures it per band.
_ANALOGY_BANDS = {1: (1, 1, 0), 2: (1, 1, 1), 3: (1, 2, 1),
                  4: (2, 2, 2), 5: (2, 2, 3)}


@register
class Analogy(Generator):
    slug = "vr.analogy"
    section, subtopic = "VR", "Word Analogies"
    template_id = "word-analogy"
    difficulties = (1, 2, 3, 4, 5)

    def build(self, rng, difficulty):
        ex_tier, tg_tier, n_same = _ANALOGY_BANDS[difficulty]
        relations = sorted(ANALOGY_PAIRS)
        rng.shuffle(relations)
        for relation in relations:
            rows = ANALOGY_PAIRS[relation]
            exemplars = [(a, b) for a, b, t in rows if t == ex_tier]
            targets = [(a, b) for a, b, t in rows if t == tg_tier]
            rng.shuffle(exemplars)
            for a1, b1 in exemplars:
                choices = [p for p in targets if p != (a1, b1)]
                rng.shuffle(choices)
                for a2, b2 in choices:
                    picked = self._distractors(rng, relation, a1, b1, a2, b2,
                                               n_same)
                    if picked is None:
                        continue
                    return Item(
                        stem=f"{a1.capitalize()} is to {b1} as {a2} is to ______?",
                        options=shuffled_options(rng, b2, picked),
                        difficulty=difficulty,
                        # The exemplar and the difficulty are both part of the
                        # identity. Without the exemplar, the 84 stems the old
                        # generator could word collapsed onto 28 gen_keys and 56
                        # were discarded unseen; without the difficulty, 20 of
                        # those 28 were reachable at two bands and overwrote
                        # each other, so which band a question shipped at was
                        # decided by draw order.
                        params={"relation": relation, "exemplar": [a1, b1],
                                "pair": [a2, b2], "difficulty": difficulty},
                        question_type=ANALOGY_RELATIONS[relation][0],
                        explanation=(
                            f"{analogy_render(relation, a1, b1).capitalize()}, "
                            f"and in the same way "
                            f"{analogy_render(relation, a2, b2)}."),
                    )
        return None

    @staticmethod
    def _distractors(rng, relation, a1, b1, a2, b2, n_same):
        """`n_same` distractors from the answer's own class, the rest from outside.

        The same-class draw is what this rewrite exists for: every distractor
        used to come from a DIFFERENT relation, so none was ever the same kind
        of thing as the answer and a bot that ignored the analogy and matched
        the category scored 28/28 on the shipped bank.

        Offering a same-class word is what opens the two-answer risk, so both
        pools are filtered through DEFENSIBLE -- the permissive table in
        analogy_data, the role ATTACHING plays for compound words. It is flat
        across relations on purpose: `kennel` is blocked for (dog, puppy)
        because dog+kennel is keyed under `home_of`, and `freezing` is blocked
        for (hot, cold) because it is a defensible opposite even though it is
        keyed under `greater_degree`.

        Only b-side words are ever candidates, which removes the whole class of
        distractor a pupil could defend by reading the relation backwards.
        """
        blocked = set(ANALOGY_DEFENSIBLE.get(a2, ())) | {a1, b1, a2, b2}
        same = [w for w in ANALOGY_CLASS[relation] if w not in blocked]
        outside = [w for w in ANALOGY_B_WORDS
                   if w not in blocked and w not in ANALOGY_CLASS[relation]]
        if len(same) < n_same or len(outside) < 3 - n_same:
            return None
        return (rng.sample(same, n_same) + rng.sample(outside, 3 - n_same))


# How many pool heads a tail forms a word with. `light` attaches to sun, day,
# foot and more; `gown` to almost nothing. That number is the difficulty axis
# below AND the guard that keeps a productive tail out of the distractor slot
# unless it has been checked against this head — the defect that put `light`
# beside `night` as a wrong answer when `nightlight` is a word.
PRODUCTIVITY = {t: sum(1 for ts in ATTACHING.values() if t in ts) for t in TAILS}

# Distractor productivity allowed per band. Low = obviously unrelated words;
# high = tails that genuinely compound with other heads, so the pupil has to
# know THIS head rather than recognise a word-shaped ending.
_COMPOUND_BANDS = {1: (0, 0), 2: (0, 1), 3: (1, 3), 4: (2, 6), 5: (4, 99)}


@register
class CompoundWord(Generator):
    slug = "vr.compound"
    section, subtopic = "VR", "Compound Words"
    template_id = "compound-word"
    difficulties = (1, 2, 3, 4, 5)

    def build(self, rng, difficulty):
        lo, hi = _COMPOUND_BANDS[difficulty]
        heads = sorted(KEYS)
        rng.shuffle(heads)
        for head in heads:
            correct = rng.choice(KEYS[head])
            # A distractor must not join THIS head. `ATTACHING` is the permissive
            # relation — web2 plus the open/hyphenated compounds it omits — so a
            # pair it does not list is genuinely not a word, and the question has
            # exactly one answer.
            attached = ATTACHING.get(head, ())
            pool = [t for t in TAILS
                    if t != correct and t not in attached and t != head
                    and lo <= PRODUCTIVITY[t] <= hi]
            if len(pool) < 3:
                continue
            return Item(
                stem=(f"Which word makes a new word when placed after "
                      f"\u201c{head}\u201d?  ({head}____)"),
                options=shuffled_options(rng, correct, rng.sample(pool, 3)),
                difficulty=difficulty,
                # `difficulty` is part of the identity: the same head+tail at two
                # bands is two different questions, and leaving it out made three
                # bands collide on one gen_key and overwrite each other's rows.
                params={"head": head, "tail": correct, "difficulty": difficulty},
                question_type="join-two-words",
                explanation=(f"\u201c{head}{correct}\u201d is a word. None of the "
                             f"other choices joins to \u201c{head}\u201d."),
            )
        return None


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


# Two real-world framings of the SAME single-total-order mechanic (a race and
# a row of seats), evidenced by the same real-paper category: GL Fam Test 2
# Q22's "floors" puzzle is exactly this shape with a third framing (storeys),
# which is why the distance-clue vocabulary matters as much as the framing
# does — see LogicOrdering's own class docstring for the citation and why
# `attribute-grid` (the taxonomy's third, still-unbuilt Scenario Deduction
# slug) is deliberately NOT one of these framings.
_LOGIC_FRAMINGS = {
    "race": {
        "intro": "{n} friends run a race.",
        "adjacent": "{a} finishes ahead of {b}",
        "distance": "{a} finishes {k} places ahead of {b}",
        "anchor": "{a} finishes last",
        "question": "Who finishes {ordinal}?",
    },
    "seating": {
        "intro": "{n} friends sit in a row of seats numbered 1 (leftmost) to {n} (rightmost).",
        "adjacent": "{a} sits immediately to the left of {b}",
        "distance": "{a} sits {k} seats to the left of {b}",
        "anchor": "{a} sits in seat {n}",
        "question": "Who is sitting in seat {ordinal} from the left?",
    },
}
_LOGIC_QUESTION_TYPE = {"race": "ranking", "seating": "seating-order"}
_LOGIC_ORDINALS = ["first", "second", "third", "fourth", "fifth"]


@register
class LogicOrdering(Generator):
    """VR Scenario Deduction: a single total order over n named people/
    seats, derived from clues that are generated FROM a known ordering and
    only ever restated (never independently hand-written), so the puzzle is
    always solvable and always has exactly one answer -- the failure mode of
    a hand-written logic puzzle is an under-constrained one with two valid
    solutions.

    Two framings share this one mechanic (`ranking`, the original race
    framing, and `seating-order`, added alongside it): both are the same
    combinatorial shape with different real-world vocabulary, which is what
    the diversity audit's Stage 3 research found evidence for -- a
    relative-distance ordering puzzle (GL Fam Test 2 Q22: "Natalie lives two
    floors below Michelle...") -- rather than for the taxonomy's third,
    still-unbuilt slug `attribute-grid` (a genuinely different, multi-
    category constraint-matching mechanic with no real-paper evidence found
    anywhere in this project's 21-paper corpus for what it should even look
    like; left alone, not attempted here).

    DIFFICULTY, band 3+: exactly one pair of adjacent clue-steps is merged
    into a single relative-distance clue ("X finishes 2 places ahead of Y"),
    which skips stating a clue for exactly one person in the middle. That
    person's position is then only recoverable by ELIMINATION: every other
    position is pinned by an explicit clue, there are exactly as many named
    people as slots, so exactly one slot is left for exactly one person.
    Never merges two steps in a row and never skips more than one person at
    once -- with two unmentioned people and two remaining slots, nothing
    would pin which one goes where, and the puzzle would have two valid
    solutions. This is why the merge index is drawn once per build and used
    for exactly one merge, not a general k-skip.
    """
    slug = "vr.logic"
    section, subtopic = "VR", "Scenario Deduction"
    template_id = "ordering-puzzle"

    def build(self, rng, difficulty):
        # DIFFICULTY: the number of people to order, band 1-2, plus (band 3+)
        # exactly one relative-distance merge -- see class docstring.
        n = {1: 3, 2: 4, 3: 4, 4: 5, 5: 5}[difficulty]
        people = rng.sample(
            ["Priya", "Jack", "Nia", "Omar", "Leo", "Zara", "Ben", "Mia"], n)
        order = people[:]          # index 0 finishes first / sits leftmost

        framing_key = rng.choice(["race", "seating"])
        framing = _LOGIC_FRAMINGS[framing_key]

        merge_at = None
        if difficulty >= 3 and n >= 4:
            merge_at = rng.randrange(n - 2)   # merges steps merge_at, merge_at+1

        clues = []
        i = 0
        while i < n - 1:
            if merge_at is not None and i == merge_at:
                a, b = order[i], order[i + 2]
                clues.append(framing["distance"].format(a=a, b=b, k=2))
                i += 2
            else:
                a, b = order[i], order[i + 1]
                clues.append(framing["adjacent"].format(a=a, b=b))
                i += 1
        clues.append(framing["anchor"].format(a=order[-1], n=n))
        rng.shuffle(clues)

        place = rng.randrange(n)
        ordinal = _LOGIC_ORDINALS[place]
        stem = (framing["intro"].format(n=n) + " " + ". ".join(clues) + ". "
                + framing["question"].format(ordinal=ordinal))
        return Item(
            stem=stem,
            options=shuffled_options(rng, order[place],
                                     [p for p in people if p != order[place]][:3]),
            difficulty=difficulty,
            # variant disambiguates the two framings' gen_key even though they
            # can draw an identical (order, place, merge_at) triple -- see the
            # module docstring's gen_key-collision exception to the variant
            # convention.
            params={"variant": framing_key, "order": order, "place": place,
                    "merge_at": merge_at},
            question_type=_LOGIC_QUESTION_TYPE[framing_key],
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
            params={"variant": "constant", "start": start, "step": step},
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
            params={"variant": "changing", "start": start, "d0": d0, "dstep": dstep},
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
            params={"variant": "multiplicative", "start": start, "ratio": ratio, "divide": divide},
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
            params={"variant": "two-step", "start": start, "mult": mult, "sub": sub},
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
            params={"variant": "alternating", "start_a": start_a, "step_a": step_a,
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
            params={"variant": "single", "a1": a1, "a2": a2, "shift": shift},
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
            params={"variant": "pair", "mirrored": mirrored, "word1": word1,
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
            params={"variant": "swap", "word1": word1, "word3": word3},
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
        options = shuffled_options(rng, correct, list(wrong))
        chosen = {text for text, is_correct in options if not is_correct}
        return Item(
            stem=(f"In a code, {noun} stand for letters: {given_lines}. "
                  f"Using the same code, what is {target}?"),
            options=options,
            difficulty=difficulty,
            params={"variant": qtype, "target": target, "givens": sorted(givens),
                    "mapping": mapping},
            question_type=qtype,
            explanation=self._explain(target, mapping, is_symbol, correct),
            misconceptions={code: slug for code, slug in wrong.items()
                            if slug and code in chosen},
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
            params={"variant": "code-to-number:word", "target": target,
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
            params={"variant": "code-to-number:letter", "target": target,
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
        """Returns {distractor code: misconception slug or None}, insertion
        order preserved (a dict, not the plain set this used to be) so a
        caller can still label the structured slips -- swapping the first
        two symbols, reading the whole code backwards -- without guessing
        which string in the result came from which construction."""
        chars = code.split(" ") if is_symbol else list(code)
        pool = NUMCODE_SYMBOLS if is_symbol else list("0123456789")

        def join(cs):
            return " ".join(cs) if is_symbol else "".join(cs)

        variants = {}
        if len(chars) >= 2:
            swapped = chars[:]
            swapped[0], swapped[1] = swapped[1], swapped[0]
            variants[join(swapped)] = "swapped-two-symbols-in-the-code"
        last = chars[:]
        last[-1] = rng.choice([v for v in pool if v != last[-1]])
        variants[join(last)] = None
        first = chars[:]
        first[0] = rng.choice([v for v in pool if v != first[0]])
        variants[join(first)] = None
        variants[join(chars[::-1])] = "read-the-code-in-reverse"
        variants.pop(join(chars), None)
        return variants


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
        misconceptions = {}
        if op == "+":
            a, b = rng.randint(3, 45), rng.randint(3, 45)
            total = a + b
            known, correct = (b, a) if blank_first else (a, b)
            stem_expr = (f"? + {known} = {total}" if blank_first
                         else f"{known} + ? = {total}")
            distractors = [total + known, total, correct + 10, max(1, correct - 2)]
            explanation = f"{total} − {known} = {correct}."
            misconceptions = {total + known: "did-not-undo-the-operation",
                              total: "copied-a-given-number-instead-of-solving"}
        else:
            a = rng.randint(25, 90)
            b = rng.randint(3, a - 10)
            diff = a - b
            if blank_first:
                correct = a
                stem_expr = f"? − {b} = {diff}"
                distractors = [max(1, diff - b), diff + b, correct - 1, correct + 1]
                explanation = f"{diff} + {b} = {correct}."
                misconceptions = {max(1, diff - b): "did-not-undo-the-operation"}
            else:
                correct = b
                stem_expr = f"{a} − ? = {diff}"
                distractors = [a + diff, max(1, correct - 1), correct + 1, a]
                explanation = f"{a} − {diff} = {correct}."
                misconceptions = {a + diff: "did-not-undo-the-operation",
                                  a: "copied-a-given-number-instead-of-solving"}
        options = shuffled_options(rng, correct, distractors)
        chosen = {text for text, is_correct in options if not is_correct}
        return Item(
            stem=f"Find the missing number.  {stem_expr}",
            options=options,
            difficulty=difficulty,
            params={"variant": "operand-add-sub", "expr": stem_expr, "correct": correct},
            question_type="missing-operand",
            explanation=f"Rearranging the equation: {explanation}",
            misconceptions={str(v): slug for v, slug in misconceptions.items()
                            if str(v) in chosen},
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
            misconceptions = {product: "copied-a-given-number-instead-of-solving",
                              known: "copied-a-given-number-instead-of-solving"}
        else:
            divisor = rng.randint(2, 12)
            quotient = rng.randint(2, 12)
            dividend = divisor * quotient
            if rng.random() < 0.5:
                correct = dividend
                stem_expr = f"? ÷ {divisor} = {quotient}"
                distractors = [quotient, divisor, dividend + divisor, max(1, dividend - divisor)]
                explanation = f"{quotient} × {divisor} = {correct}."
                misconceptions = {quotient: "copied-a-given-number-instead-of-solving",
                                  divisor: "copied-a-given-number-instead-of-solving"}
            else:
                correct = divisor
                stem_expr = f"{dividend} ÷ ? = {quotient}"
                distractors = [dividend, quotient, correct + 1, max(1, correct - 1)]
                explanation = f"{dividend} ÷ {quotient} = {correct}."
                misconceptions = {dividend: "copied-a-given-number-instead-of-solving",
                                  quotient: "copied-a-given-number-instead-of-solving"}
        options = shuffled_options(rng, correct, distractors)
        chosen = {text for text, is_correct in options if not is_correct}
        return Item(
            stem=f"Find the missing number.  {stem_expr}",
            options=options,
            difficulty=difficulty,
            params={"variant": "operand-mul-div", "expr": stem_expr, "correct": correct},
            question_type="missing-operand",
            explanation=f"Rearranging the equation: {explanation}",
            misconceptions={str(v): slug for v, slug in misconceptions.items()
                            if str(v) in chosen},
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
        options = shuffled_options(rng, correct, distractors)
        chosen = {text for text, is_correct in options if not is_correct}
        misconceptions = {str(v): "copied-a-given-number-instead-of-solving"} if str(v) in chosen else {}
        return Item(
            stem=f"Find the missing number so both sides balance.  {stem}",
            options=options,
            difficulty=difficulty,
            params={"known": known_expr, "blank": blank_expr, "correct": correct, "v": v},
            question_type="balance-both-sides",
            explanation=(f"{known_expr} = {v}, so the missing number must make "
                         f"the other side equal {v} too: {exp_line}"),
            misconceptions=misconceptions,
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
        options = shuffled_options(rng, correct, distractors)
        chosen = {text for text, is_correct in options if not is_correct}
        misconceptions = {str(v): "copied-a-given-number-instead-of-solving"} if str(v) in chosen else {}
        return Item(
            stem=f"Find the missing number so both sides balance.  {stem}",
            options=options,
            difficulty=difficulty,
            params={"known": known_expr, "blank": blank_expr, "correct": correct,
                    "v": v, "template": template},
            question_type="balance-both-sides",
            explanation=(f"{known_expr} = {v}, so the missing number must make "
                         f"the other side equal {v} too: {exp_line}"),
            misconceptions=misconceptions,
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
            params={"variant": "apply-the-rule", "rule": rule.key,
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
            params={"variant": "find-the-rule", "rule": rule.key,
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

    `Item.kind` exists and `generate_bank.py` respects it (`item.kind or
    Question.Kind.MCQ`) -- the hook is real, nobody has pointed this class at
    it yet. This class still answers with 4 letter options via
    `shuffled_options`, the MCQ shape. The intended long-run kind is still
    `short_text` (a single typed letter), per elevenplus_data/CLAUDE.md's VR
    answer-kind table; switching over means setting `kind=Question.Kind.
    SHORT_TEXT` on the returned `Item` and dropping the distractor options
    below, keeping just the correct-letter computation.
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

    def _distractor_letters(self, rng, key, reserved, correct_value, candidates,
                             target=4):
        """Map candidate wrong (VALUE, misconception-slug-or-None) pairs to
        letters (extending the key as needed via `_letter_for`), skipping
        the correct value itself, non-positive values (no letter stands for
        zero or a negative number in these keys) and any value already
        claimed by an earlier candidate. Returns (letters, key,
        misconceptions) with `key` folding in every extension made along the
        way and `misconceptions` mapping each resulting letter to the slug
        its source candidate carried, where one was given.

        Stops once `target` distractors are found (one spare beyond the 3
        `shuffled_options` needs) rather than resolving every candidate,
        since working through all of them regardless would grow the key by
        up to len(candidates) letters even when the first 3-4 already
        sufficed."""
        letters = []
        misconceptions = {}
        seen_values = {correct_value}
        for value, slug in candidates:
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
            if slug:
                misconceptions[letter] = slug
        return letters, key, misconceptions

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
            candidates = [(result + 1, None), (result - 1, None),
                          (result + 2, None), (result - 2, None)]
            flip_idx = rng.randrange(len(ops))
            flipped = list(ops)
            flipped[flip_idx] = "-" if flipped[flip_idx] == "+" else "+"
            candidates.append((self._evaluate(key, letters, flipped),
                               "flipped-the-sign-of-one-term"))
            candidates.append((key[rng.choice(letters)],
                               "found-one-part-then-stopped"))
            if n_terms >= 3:
                candidates.append((self._evaluate(key, letters[:-1], ops[:-1]),
                                   "found-one-part-then-stopped"))
            rng.shuffle(candidates)

            distractor_letters, key, misc = self._distractor_letters(
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

        options = shuffled_options(rng, answer_letter, distractor_letters, keep=3)
        chosen = {text for text, is_correct in options if not is_correct}
        return Item(
            stem=(f"If {self._key_text(key)}, what letter stands for the value of "
                  f"{expr}?"),
            options=options,
            difficulty=difficulty,
            params={
                "variant": "substitute",
                "key": sorted(key.items()),
                "letters": letters,
                "ops": ops,
                "result": result,
                "answer": answer_letter,
            },
            question_type="substitute-and-evaluate",
            explanation=(f"{expr} = {result}, and {answer_letter} = {result}, "
                         f"so the answer is {answer_letter}."),
            misconceptions={letter: slug for letter, slug in misc.items()
                            if letter in chosen},
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
            candidates = [(x_value + 1, None), (x_value - 1, None),
                          (x_value + 2, None), (x_value - 2, None),
                          (b, "copied-a-given-number-instead-of-solving"),
                          (a, "copied-a-given-number-instead-of-solving")]
            candidates.extend((v, "skipped-a-step-of-the-equation")
                              for v in extra_candidates)
            rng.shuffle(candidates)

            distractor_letters, key, misc = self._distractor_letters(
                rng, key, reserved, x_value, candidates)
            if len(distractor_letters) < 3:
                continue
            break
        else:
            return None

        options = shuffled_options(rng, answer_letter, distractor_letters, keep=3)
        chosen = {text for text, is_correct in options if not is_correct}
        return Item(
            stem=(f"If {self._key_text(key)}, and {equation}, "
                  f"what letter has the same value as {unknown}?"),
            options=options,
            difficulty=difficulty,
            params={
                "variant": "solve",
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
            misconceptions={letter: slug for letter, slug in misc.items()
                            if letter in chosen},
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
    elevenplus_data/CLAUDE.md's VR answer-kind table. `Item.kind` exists and
    `generate_bank.py` respects it, but nobody has pointed this class at it
    yet, so — following Batch 1's precedent — this class presents
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
            params={"variant": f"apply-pattern:{shape_key}",
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
            params={"variant": f"find-pattern:{shape_key}",
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

    Kind/pipeline note, same gap LetterAlgebra documents: `Item.kind` exists
    (the hook is real) but nobody has pointed this class at it yet. The
    natural answer format here is `short_text` (the pupil writes the two new
    words), so this class presents 4 options instead -- the correct
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
    `Item` has no `option_groups` field and `generate_bank._write()` only
    ever writes flat `options` -- a different, more fundamental gap than
    LetterAlgebra's (where `Item.kind` exists and just isn't set to
    `short_text` yet): here the pipeline has nowhere to PUT bracket data
    even if `kind` were set to `grouped_options`. This generator flattens
    the task instead: both brackets are
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


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DAY_INDEX = {d: i for i, d in enumerate(DAYS)}
WEEKDAY_SET = set(DAYS[:5])
WEEKEND_SET = set(DAYS[5:])

MBT_PLACE_NOUNS = ["cinema", "library", "swimming pool", "museum", "leisure centre",
                   "art gallery", "skate park", "bowling alley"]
MBT_PERSON_NAMES = ["Priya", "Jamal", "Nia", "Omar", "Leo", "Zara", "Sam", "Grace"]


def _mbt_list_join(days_list):
    """'Monday' / 'Monday and Wednesday' / 'Monday, Wednesday and Friday'."""
    ordered = sorted(days_list, key=lambda d: _DAY_INDEX[d])
    if len(ordered) == 1:
        return ordered[0]
    return ", ".join(ordered[:-1]) + " and " + ordered[-1]


def mbt_solve(rules):
    """THE SOLVER. Mechanically computes entity -> {day: bool} from a list of
    rule dicts, in the order given (a dependency rule's `base` entity must
    already have been processed, which the generator guarantees by always
    building the base entity's rule before any rule that depends on it).

    This is the ONLY place truth values are decided. Every candidate
    statement in `build()` is checked against this table's output — it is
    never told the "intended" answer directly.
    """
    table = {}
    for rule in rules:
        eid = rule["entity"]
        kind = rule["type"]
        if kind == "enumerate":
            true_days = set(rule["days"])
            table[eid] = {d: (d in true_days) for d in DAYS}
        elif kind == "negate":
            false_days = set(rule["exclude"])
            table[eid] = {d: (d not in false_days) for d in DAYS}
        elif kind == "category":
            true_days = WEEKDAY_SET if rule["cat"] == "weekday" else WEEKEND_SET
            table[eid] = {d: (d in true_days) for d in DAYS}
        elif kind == "dependency":
            base_table = table[rule["base"]]
            invert = rule["invert"]
            row = {d: ((not base_table[d]) if invert else base_table[d]) for d in DAYS}
            exc = rule.get("exception")
            if exc:
                row[exc["day"]] = exc["value"]
            table[eid] = row
        else:
            raise ValueError(f"unknown rule type {kind!r}")
    return table


@register
class MustBeTrue(Generator):
    """VR "Must Be True": a short set of rules fully pins down a day-by-day
    table (who/what does an activity on which day of the week), and the
    pupil must spot the one of five statements that MUST be true
    (`valid-conclusion`) or the one that CANNOT be true (`spot-invalid-
    conclusion`) — confirmed against real papers (GL Fam T1 Q67, a cinema's
    opening-hours rules; GL Fam T3 Q53, two sisters' lunch schedule).

    THE AMBIGUITY RISK AND HOW THIS AVOIDS IT. A hand-written "must be true"
    puzzle's classic failure is under-determination: the stated facts are
    consistent with more than one world, so the "true" conclusion is only
    true in the world the author happened to imagine. This generator never
    writes a fact in free-standing prose and then hopes it pins down the
    world — instead every rule is one of three EXHAUSTIVE closed-form shapes
    (`enumerate`: true only on a named list of days; `negate`: true every day
    except a named list; `category`: true only on weekdays or only at the
    weekend) for the first entity, and every other entity is defined by a
    `dependency` rule that is a total function of an ALREADY fully-known
    entity's table (optionally overridden on one named exception day). Each
    rule therefore assigns a definite boolean to every one of the 7 days for
    its entity, with no day left to a reader's judgement call — so the table
    `mbt_solve()` computes is not "the world I had in mind while writing
    this", it is the unique world the rules describe. Once that is true,
    "true in the table" and "necessarily true given the rules" are the same
    thing and there is no separate modal question to get wrong.

    Candidate statements are built by picking 5 DISTINCT (entity, day) pairs
    (never repeating a pair, so no two candidates can be paraphrases of each
    other) and, for each one, choosing the WORDING (positive: "is open" /
    "works"; negative: "is closed" / "does not work") that gives it whatever
    truth value the question type needs there. Concretely: for
    valid-conclusion, one target pair is worded to match the table (making it
    the one true statement) and the other four are worded to CONTRADICT the
    table (the "opposite of what's true" mistake real pupils make); for
    spot-invalid-conclusion it's the reverse. This is why the correct
    candidate is always computed from `mbt_solve()`'s output rather than
    decided first and back-filled — see `build()`.

    Verified against three independently-written solvers (never trusting
    this class's own option labelling) across tens of thousands of builds.
    That process caught one real fairness gap pre-ship: a dependency's
    exception day could push an entity to true-every-day or false-every-day
    when its base row already had only one day of headroom, letting 3 of the
    5 candidates about that entity become trivially answerable without
    tracing the rule chain. `build()`'s exception-selection guards both
    directions symmetrically — see the comment there — and since DAYS has 7
    slots, the two guard conditions (`true_day_count<=1`,
    `false_day_count<=1`) can never both hold, so they never conflict.

    DIFFICULTY / question_type split: `valid-conclusion` and
    `spot-invalid-conclusion` are just two different ways of grading the same
    5 statements against the same table (see `build()`), so which one comes
    up is randomised per build rather than tied to a difficulty tier — the
    same reasoning applies at every tier. Difficulty instead controls the
    SCENARIO'S shape, the way vr.numseq's tiers pick different rule shapes:
    d1 is one entity with the simplest rule (a short enumerated list); d2 is
    one entity with a negation or weekday/weekend rule; d3 adds a second
    entity (a person) whose activity depends on the first with no exception;
    d4 adds an exception day to that dependency; d5 chains a THIRD entity off
    the second, with an exception guaranteed somewhere in the chain — each
    step is still a total function of already-known days, so the table stays
    fully determined no matter how many entities are chained.
    """
    slug = "vr.mustbetrue"
    section, subtopic = "VR", "Must Be True"
    template_id = "must-be-true-table"
    difficulties = (1, 2, 3, 4, 5)

    def build(self, rng, difficulty):
        entities = []
        rules = []

        place = {"id": "E0", "kind": "place", "noun": rng.choice(MBT_PLACE_NOUNS)}
        place["display"] = f"The {place['noun']}"
        entities.append(place)

        # --- primary rule for the place: always one of the three closed-form,
        # exhaustive shapes, so its table has no residual freedom. ---
        if difficulty == 1:
            prim_kind = "enumerate"
        elif difficulty == 2:
            prim_kind = rng.choice(["negate", "category"])
        else:
            prim_kind = rng.choice(["enumerate", "negate", "category"])

        if prim_kind == "enumerate":
            k = 2 if difficulty == 1 else rng.randint(2, 4)
            days = sorted(rng.sample(DAYS, k), key=lambda d: _DAY_INDEX[d])
            rules.append({"type": "enumerate", "entity": place["id"], "days": days})
        elif prim_kind == "negate":
            k = rng.randint(1, 3)
            exclude = sorted(rng.sample(DAYS, k), key=lambda d: _DAY_INDEX[d])
            rules.append({"type": "negate", "entity": place["id"], "exclude": exclude})
        else:
            cat = rng.choice(["weekday", "weekend"])
            rules.append({"type": "category", "entity": place["id"], "cat": cat})

        # --- extra entities via dependency rules, more of them / more
        # complex (an exception day) as difficulty rises. Each dependency is
        # a total function of an entity whose table is already fully known,
        # so full determination is preserved at every link in the chain. ---
        n_people = {1: 0, 2: 0, 3: 1, 4: 1, 5: 2}[difficulty]
        used_names = []
        prev_entity = place
        for i in range(n_people):
            name = rng.choice([n for n in MBT_PERSON_NAMES if n not in used_names])
            used_names.append(name)
            person = {"id": f"P{i}", "kind": "person", "name": name, "display": name}
            entities.append(person)

            # Solve what's known SO FAR so the exception day can be picked
            # against real values, not guessed blind.
            partial_table = mbt_solve(rules)
            invert = bool(rng.getrandbits(1))
            base_row = {d: ((not partial_table[prev_entity["id"]][d]) if invert
                             else partial_table[prev_entity["id"]][d]) for d in DAYS}

            force_exception = (difficulty == 4) or (difficulty == 5 and i == n_people - 1)
            allow_exception = force_exception or difficulty == 5
            exception = None
            true_day_count = sum(1 for d in DAYS if base_row[d])
            false_day_count = len(DAYS) - true_day_count
            if allow_exception and rng.random() < (1.0 if force_exception else 0.5):
                etype = rng.choice(["plus", "except"])
                # Quality guard, not a correctness one, in BOTH directions:
                # an "except" that removes the base rule's ONLY true day
                # leaves the entity never doing the activity at all, and
                # symmetrically a "plus" that adds the base rule's ONLY
                # false day leaves the entity doing it EVERY day — either
                # way still fully determined (so still unambiguous), but
                # each collapses 3 of the 5 candidate statements about that
                # entity to "trivially true/false regardless of the day
                # named", letting a pupil answer without tracing the rule
                # chain, and reads as a rule no real paper would write
                # ("works on the days Sam doesn't, except that day" / "...,
                # and also on the one day she doesn't already"). Fall back
                # to the other exception shape whenever the chosen one would
                # zero out or fill up the entity's table; DAYS has 7 slots,
                # so true_day_count<=1 and false_day_count<=1 can never both
                # hold, meaning at most one of these two swaps ever fires.
                if etype == "except" and true_day_count <= 1:
                    etype = "plus"
                elif etype == "plus" and false_day_count <= 1:
                    etype = "except"
                if etype == "plus":
                    cands = [d for d in DAYS if not base_row[d]]
                    if cands:
                        day = rng.choice(cands)
                        exception = {"day": day, "value": True, "type": "plus"}
                if exception is None:  # "except", or "plus" had no candidates
                    cands = [d for d in DAYS if base_row[d]]
                    if cands:
                        day = rng.choice(cands)
                        exception = {"day": day, "value": False, "type": "except"}

            rules.append({
                "type": "dependency", "entity": person["id"], "base": prev_entity["id"],
                "invert": invert, "exception": exception,
            })
            prev_entity = person

        table = mbt_solve(rules)

        # --- 5 distinct (entity, day) candidate pairs ---
        ids = [e["id"] for e in entities]
        chosen = set()
        pairs = []
        if len(ids) > 1:
            for eid in ids:
                d = rng.choice(DAYS)
                if (eid, d) not in chosen:
                    chosen.add((eid, d))
                    pairs.append((eid, d))
        attempts = 0
        while len(pairs) < 5 and attempts < 500:
            attempts += 1
            cand = (rng.choice(ids), rng.choice(DAYS))
            if cand not in chosen:
                chosen.add(cand)
                pairs.append(cand)
        if len(pairs) < 5:
            return None
        rng.shuffle(pairs)
        pairs = pairs[:5]

        entities_by_id = {e["id"]: e for e in entities}
        rules_by_entity = {r["entity"]: r for r in rules}
        qtype = rng.choice(["valid-conclusion", "spot-invalid-conclusion"])
        target_index = rng.randrange(5)

        option_rows = []
        for i, (eid, day) in enumerate(pairs):
            entity = entities_by_id[eid]
            actual = table[eid][day]
            if qtype == "valid-conclusion":
                want_true = (i == target_index)
            else:
                want_true = (i != target_index)
            positive_wording = actual if want_true else (not actual)
            text = self._phrase(entity, day, positive_wording)
            option_rows.append((text, i == target_index))

        rng.shuffle(option_rows)

        target_eid, target_day = pairs[target_index]
        target_entity = entities_by_id[target_eid]
        reasoning = self._why(target_entity, target_day, entities_by_id,
                               rules_by_entity, table)
        if qtype == "valid-conclusion":
            question_line = "Which ONE of these must be true?"
            tail = "That statement must be true."
        else:
            question_line = "Which ONE of these cannot be true?"
            tail = "Every other statement is consistent with the rules; that one is not."

        rule_sentences = [self._rule_sentence(r, entities_by_id) for r in rules]
        stem = " ".join(rule_sentences + [question_line])

        return Item(
            stem=stem,
            options=option_rows,
            difficulty=difficulty,
            params={"rules": rules, "pairs": [list(p) for p in pairs],
                    "variant": qtype, "target": target_index,
                    # Identity bookkeeping only (which id is which noun/name
                    # and place-vs-person) — NOT a computed truth value, so
                    # exposing it doesn't hand the self-test the answer. The
                    # self-test still recomputes every statement's truth from
                    # `rules` alone via its own from-scratch solver.
                    "entities": [{"id": e["id"], "kind": e["kind"], "display": e["display"]}
                                 for e in entities]},
            question_type=qtype,
            explanation=f"{reasoning} {tail}",
        )

    # -- wording helpers -----------------------------------------------
    @staticmethod
    def _phrase(entity, day, positive):
        if entity["kind"] == "place":
            return (f"{entity['display']} is open on {day}." if positive
                    else f"{entity['display']} is closed on {day}.")
        return (f"{entity['display']} works on {day}." if positive
                else f"{entity['display']} does not work on {day}.")

    @staticmethod
    def _rule_sentence(rule, entities_by_id):
        entity = entities_by_id[rule["entity"]]
        if rule["type"] == "enumerate":
            return f"{entity['display']} opens only on {_mbt_list_join(rule['days'])}."
        if rule["type"] == "negate":
            return f"{entity['display']} opens every day except {_mbt_list_join(rule['exclude'])}."
        if rule["type"] == "category":
            cat = "weekdays" if rule["cat"] == "weekday" else "weekends (Saturday and Sunday)"
            return f"{entity['display']} opens only on {cat}."
        # dependency
        base = entities_by_id[rule["base"]]
        if base["kind"] == "place":
            base_clause = (f"the days {base['display'].replace('The', 'the', 1)} is closed"
                           if rule["invert"] else
                           f"the days {base['display'].replace('The', 'the', 1)} is open")
        else:
            base_clause = (f"the days {base['display']} does not work" if rule["invert"]
                           else f"the days {base['display']} works")
        # Dependency rules only ever target a person entity (the place is
        # always the primary, rule-driven entity), so the verb is fixed.
        sentence = f"{entity['display']} works on {base_clause}"
        exc = rule.get("exception")
        if exc:
            if exc["type"] == "plus":
                sentence += f", and also on {exc['day']}"
            else:
                sentence += f", except on {exc['day']}"
        return sentence + "."

    @staticmethod
    def _why(entity, day, entities_by_id, rules_by_entity, table):
        rule = rules_by_entity[entity["id"]]
        val = table[entity["id"]][day]
        if rule["type"] == "enumerate":
            return (f"{entity['display']} opens only on {_mbt_list_join(rule['days'])}, "
                    f"so on {day} it is {'open' if val else 'closed'}.")
        if rule["type"] == "negate":
            return (f"{entity['display']} opens every day except "
                    f"{_mbt_list_join(rule['exclude'])}, so on {day} it is "
                    f"{'open' if val else 'closed'}.")
        if rule["type"] == "category":
            cat = "weekdays" if rule["cat"] == "weekday" else "weekends"
            return (f"{entity['display']} opens only on {cat}, so on {day} it is "
                    f"{'open' if val else 'closed'}.")
        # dependency
        base = entities_by_id[rule["base"]]
        base_val = table[rule["base"]][day]
        if base["kind"] == "place":
            base_desc = f"{base['display']} is {'open' if base_val else 'closed'}"
        else:
            base_desc = f"{base['display']} {'works' if base_val else 'does not work'}"
        verb = "works" if val else "does not work"
        exc = rule.get("exception")
        note = " (the stated exception for that day)" if exc and exc["day"] == day else ""
        return f"On {day}, {base_desc}, so {entity['display']} {verb}{note}."


# Curated pool for VR Anagrams `plain-anagram`: a word is scrambled and shown
# in capitals embedded in a sentence; the pupil rearranges the letters to
# form the real word that fits the sentence's meaning. Confirmed against a
# real published 11+ example (11plusehelp.co.uk): "The girl sat on a ARCIH."
# -> CHAIR.
#
# AMBIGUITY DISCIPLINE, mirroring HiddenWord's and LetterMove's own pool
# comments: an anagram puzzle's single biggest failure mode is a letter set
# with MORE THAN ONE valid real-word unscrambling (STOP/POTS/TOPS/OPTS,
# LISTEN/SILENT/ENLIST). Every entry below was chosen only after checking,
# programmatically and not by eye, that its letter multiset has ZERO other
# real-word anagrams against a frequency-filtered "everyday word" set
# (intersection of an unabridged dictionary with a 60k-word frequency list —
# the same two-source methodology LetterMove's own pool comment describes).
# 220 candidate words were checked this way; 52 were rejected outright for
# having at least one other real-word anagram in that filtered set — e.g.
# GARDEN also spells DANGER/GANDER/RANGED, FLOWER also spells FOWLER,
# STREAM also spells MASTER. Independent verification additionally checked
# every shipped entry against the FULL unabridged dictionary (no frequency
# filter) and found 14 of 40 do have a technically-real competing anagram
# there (e.g. CHAIR/CHRIA, TABLE/BATEL) — each was hand-confirmed archaic,
# dialectal, or excluded by the sentence/clue's own grammar or meaning, so
# none creates real ambiguity for an 11-year-old; see the verification
# record in plans.md's VR generator coverage entry for the full list.
#
# Tuple shape: (answer, scrambled_letters, sentence_with_a_blank).
PLAIN_ANAGRAM_D2 = [
    ("DESK", "SDKE", "She keeps her pencils and books tidy inside the ___."),
    ("FISH", "IFHS", "We caught a shiny silver ___ in the stream."),
    ("BIRD", "IRDB", "A tiny ___ built its nest in the old oak tree."),
    ("FROG", "GFRO", "The bright green ___ leapt into the pond with a splash."),
    ("CAKE", "KCEA", "Mum baked a chocolate ___ for my birthday party."),
]
PLAIN_ANAGRAM_D3 = [
    ("CHAIR", "HCRAI", "The girl pulled up a wooden ___ and sat down at her desk."),
    ("HOUSE", "OUHES", "Every morning he walks past the same red brick ___."),
    ("TABLE", "ETLAB", "Please put the clean plates on the kitchen ___."),
    ("WHALE", "LWEAH", "The tourists watched a huge grey ___ swim beside the boat."),
    ("SHARK", "KSHAR", "A sleek grey ___ circled slowly near the coral reef."),
    ("PUPPY", "YPUPP", "The playful little ___ chased its tail around the garden."),
]
PLAIN_ANAGRAM_D4 = [
    ("CASTLE", "SLCAET", "The knights defended the tall stone ___ from the invaders."),
    ("SPIDER", "DSERIP", "A large ___ had spun its web across the doorway overnight."),
    ("PENCIL", "CPIELN", "She sharpened her ___ carefully before the spelling test began."),
    ("WINDOW", "NWOWID", "Bright morning sunlight streamed through the open ___."),
    ("ROCKET", "TCKERO", "The astronauts climbed aboard the gleaming silver ___."),
    ("RABBIT", "TBRABI", "A brown ___ hopped quickly across the meadow at dawn."),
    ("DRAGON", "RONDGA", "In the old story, a fierce ___ guarded a hoard of gold."),
    ("BASKET", "ABETKS", "She carried the ripe apples home in a woven ___."),
]
PLAIN_ANAGRAM_D5 = [
    ("BLANKET", "KTNLEAB", "She wrapped the sleeping baby in a soft woollen ___."),
    ("CURTAIN", "ACTRUNI", "He drew the heavy velvet ___ to block out the afternoon sun."),
    ("TRUMPET", "PTTUEMR", "He practises his ___ in the garage every evening after school."),
]
PLAIN_ANAGRAM = {2: PLAIN_ANAGRAM_D2, 3: PLAIN_ANAGRAM_D3, 4: PLAIN_ANAGRAM_D4,
                  5: PLAIN_ANAGRAM_D5}

# Curated pool for VR Anagrams `anagram-with-clue`: the same scrambled-word
# task, but a short definition/clue replaces sentence context, e.g.
# "Rearrange NELVE to make a number: ______" -> ELEVEN. WEAKER EVIDENCE than
# PLAIN_ANAGRAM above: this specific wording convention (clue instead of
# sentence) was not independently found in a cited real paper during this
# pass — it is the standard variant this question_type's own taxonomy name
# ("Rearrange, guided by a clue") implies, not a confirmed one. Same
# ambiguity discipline: every entry's letter multiset was checked against
# the same frequency-filtered real-word set (see PLAIN_ANAGRAM's comment for
# the full 220-tried/168-survived/52-rejected methodology; a single
# candidate list was checked once and split across both pools).
#
# Tuple shape: (answer, scrambled_letters, clue).
ANAGRAM_CLUE_D2 = [
    ("FOUR", "OFRU", "a number that comes between three and five"),
    ("NINE", "ENIN", "a number that comes right after eight"),
    ("JUNE", "NEJU", "the sixth month of the year"),
]
ANAGRAM_CLUE_D3 = [
    ("EIGHT", "IHTEG", "a number that comes right after seven"),
    ("BROWN", "NBWOR", "a colour like chocolate or wet soil"),
    ("WHITE", "HETWI", "a colour as pale as fresh snow"),
    ("UNCLE", "CEUNL", "your mother's or father's brother"),
    ("RULER", "ULRRE", "a tool used for measuring things or drawing straight lines"),
]
ANAGRAM_CLUE_D4 = [
    ("TWELVE", "EELWTV", "a number that comes between eleven and thirteen"),
    ("FATHER", "HEAFRT", "another word for your dad"),
    ("NEPHEW", "EPENWH", "your brother's or sister's son"),
    ("FRIDAY", "RAFYID", "the day of the week that comes right before Saturday"),
    ("ERASER", "SEERRA", "a tool used for rubbing out pencil marks"),
    ("SUMMER", "MEURMS", "the warmest season of the year"),
    ("SATURN", "UTSRNA", "the planet best known for the rings around it"),
]
ANAGRAM_CLUE_D5 = [
    ("GIRAFFE", "AEFFGIR", "the tallest land animal, famous for its very long neck"),
    ("DOLPHIN", "OPNDILH",
     "an intelligent sea mammal that leaps out of the water and clicks to communicate"),
    ("PENGUIN", "NPGUINE",
     "a flightless black-and-white bird that slides on its belly across the ice"),
]
ANAGRAM_CLUE = {2: ANAGRAM_CLUE_D2, 3: ANAGRAM_CLUE_D3, 4: ANAGRAM_CLUE_D4,
                 5: ANAGRAM_CLUE_D5}

# Distractor source: every answer word from both pools, grouped by letter
# count, so a wrong option is always a real word of the SAME LENGTH as the
# answer rather than a giveaway-short or giveaway-long one. Deliberately NOT
# drawn from other anagrams of the correct answer's own letters -- those
# would reintroduce exactly the ambiguity the pool was built to avoid; every
# distractor here is a different word entirely.
_ANSWERS_BY_LEN = {}
for _pool in list(PLAIN_ANAGRAM.values()) + list(ANAGRAM_CLUE.values()):
    for _answer, _scrambled, _context in _pool:
        _ANSWERS_BY_LEN.setdefault(len(_answer), []).append(_answer)


@register
class Anagram(Generator):
    """VR Anagrams: a word's letters are scrambled and shown in capitals; the
    pupil rearranges them to recover the real word. Covers both of the
    taxonomy's question_types for this subtopic:

      - plain-anagram: the scrambled word sits inside a sentence, and the
        sentence's MEANING is what tells the pupil which word is wanted.
        CONFIRMED against a real published 11+ example (11plusehelp.co.uk):
        "The girl sat on a ARCIH." -> CHAIR -- this exact mechanic (a word
        scrambled and embedded in a sentence) is the cited source's own
        worked example, not an inference.

      - anagram-with-clue: the same scrambled-letters task, but a short
        definition/clue is given directly instead of sentence context, e.g.
        "Rearrange NELVE to make a number: ______" -> ELEVEN. WEAKER
        EVIDENCE than plain-anagram: this specific wording convention was
        NOT independently found in a cited real paper during this pass. It
        is built as the natural clue-based variant this question_type's own
        taxonomy name ("Rearrange, guided by a clue") implies, following
        standard 11+ convention, but should be treated as inferred rather
        than confirmed until a real paper example turns up.

    AMBIGUITY DISCIPLINE: see the comments above PLAIN_ANAGRAM_D2 and
    ANAGRAM_CLUE_D2 for the full methodology. In short: every answer word in
    both pools was checked programmatically (not by eye) to have ZERO other
    real-word anagrams against a frequency-filtered real-word set. 14 of the
    40 entries do have a technically-real competing anagram in an unfiltered
    unabridged dictionary (e.g. CHAIR/CHRIA), independently re-checked and
    confirmed archaic/obscure/grammatically excluded, not a genuine second
    answer for an 11-year-old.

    Kind/pipeline note: the real answer format here is `short_text` (the
    pupil writes in the unscrambled word) -- see elevenplus_data/CLAUDE.md's
    VR answer-kind table -- but generate_bank.py hardcodes every generated
    Question as `kind = MCQ`, the same gap Batch 1/2's classes (e.g.
    LetterMove, WordPattern) document and work around. Following that
    precedent, this class presents 4 real-word MCQ options: the correct word
    plus 3 plausible-but-wrong real words of the SAME LETTER COUNT, drawn
    from the other pool entries. Distractors are never other anagrams of the
    same letters -- that would reintroduce the exact ambiguity the pool was
    built to avoid; every distractor is simply a different word.

    DIFFICULTY: the anagram mechanism itself never changes -- only the
    word's length, the same posture HiddenWord takes with sentence
    length/vocabulary rather than the hidden-word mechanism. 4-letter words
    are difficulty 2, 5-letter difficulty 3, 6-letter difficulty 4, 7-letter
    difficulty 5. There is no difficulty 1: a 3-letter-or-shorter anagram is
    trivial to brute-force by trying every arrangement and is not a
    meaningful test of this skill.
    """
    slug = "vr.anagram"
    section, subtopic = "VR", "Anagrams"
    template_id = "anagram"
    difficulties = (2, 3, 4, 5)

    def build(self, rng, difficulty):
        qtype = rng.choice(["plain-anagram", "anagram-with-clue"])
        pool = (PLAIN_ANAGRAM if qtype == "plain-anagram" else ANAGRAM_CLUE)[difficulty]
        answer, scrambled, context = rng.choice(pool)

        same_len = [w for w in _ANSWERS_BY_LEN.get(len(answer), []) if w != answer]
        distractors = rng.sample(same_len, min(3, len(same_len)))

        if qtype == "plain-anagram":
            stem = (f"Rearrange the capital letters to make a word that fits the "
                    f"sentence:  {context.replace('___', scrambled)}")
            explanation = (f"The letters {scrambled} rearrange to {answer}, which "
                           f"fits the sentence: {context.replace('___', answer)}")
        else:
            stem = (f"Rearrange {scrambled} to make a word that means: "
                    f"{context}.  ______")
            explanation = f"The letters {scrambled} rearrange to {answer}: {context}."

        return Item(
            stem=stem,
            options=shuffled_options(rng, answer, distractors),
            difficulty=difficulty,
            params={"variant": qtype, "answer": answer, "scrambled": scrambled},
            question_type=qtype,
            explanation=explanation,
        )


# ---------------------------------------------------------------------------
# Curated pool for VR Connecting Letters (single-letter variant, taxonomy
# question_type `single-connector`): two word-fragment pairs are shown, each
# with a gap -- e.g. BA(_)ON and CU(_)EN -- and the SAME letter fills every
# gap, turning BOTH halves of BOTH pairs into real words at once:
# BA(_)ON -> BAT/TON, CU(_)EN -> CUT/TEN. Confirmed against two independent
# published sources (11plusforparents.co.uk Type A; examhappy.co.uk Type 5,
# whose own worked example -- col(_)ram bel(_)oll -> T, giving COLT/TRAM and
# BELT/TOLL -- is entry #18 below, unchanged, because it independently
# passed this pool's own uniqueness check).
#
# UNIQUENESS is the entire puzzle, exactly like LetterMove, and was checked
# the same way: exhaustively, not by eye. Candidate fragment pairs were
# generated from real dictionary words (never hand-guessed), and for every
# candidate the FULL a-z alphabet was tried against BOTH fragment pairs
# before it was allowed into this pool at all -- so every entry below
# already carries the "no other letter solves both pairs" guarantee, rather
# than being verified after the fact.
#
# Word-validity oracle: the intersection of the system dictionary
# (/usr/share/dict/words, ~236k entries) with a frequency list at zipf >=
# 1.2 (~52k words survive) -- the same "an unabridged dictionary alone is
# too permissive" fix LetterMove's own pool comment describes, for the same
# reason. Checked directly: against the raw, frequency-unfiltered
# dictionary, one entry below (COLT/TRAM, BELT/TOLL) picks up a second
# spurious hit at letter D (COLD and DRAM are both genuinely common, but
# BELD -- an archaic dialect word, zipf 0.0 -- is not a word an 11+ pupil
# would ever encounter). Intersecting with the frequency list removes BELD
# and restores a single unique answer, T -- independently reproduced by a
# second reviewer using a completely separate frequency corpus, confirming
# this project's existing "top-~50k-by-frequency" bar is the right one to
# build against, not the raw dictionary.
#
# Vocabulary appropriateness (not uniqueness -- that was already guaranteed
# by construction) was the real editorial filter applied by hand: candidates
# were rejected for being proper nouns, brand names, slang or archaic hits
# that happened to clear the frequency bar anyway. 22 entries survived that
# filter across 22 distinct connecting letters (every letter except J, Q, V,
# X, for which no candidate cleared both the uniqueness check and the
# vocabulary filter -- English simply has too few short words ending in
# those letters for this puzzle shape, the same posture LetterMove takes
# toward its own uncovered question_type).
#
# Tuple shape: (prefix1, suffix1, prefix2, suffix2, connector, wrong_letters).
# wrong_letters are 3 real distractor letters, confirmed NOT to solve both
# fragment pairs at once.
_CONNECT_D2 = [
    ("BA", "AG", "BAN", "ET", "G", ["C", "D", "K"]),        # BAG/GAG, BANG/GET
    ("AG", "AK", "ALS", "LD", "O", ["Y", "P", "N"]),        # AGO/OAK, ALSO/OLD
    ("IDE", "CE", "SOD", "RT", "A", ["B", "Z", "C"]),       # IDEA/ACE, SODA/ART
    ("AR", "AB", "CHI", "ASE", "C", ["N", "T", "D"]),       # ARC/CAB, CHIC/CASE
    ("ACI", "AD", "AD", "ARK", "D", ["Y", "E", "C"]),       # ACID/DAD, ADD/DARK
    ("ARC", "AD", "AS", "ALF", "H", ["I", "G", "J"]),       # ARCH/HAD, ASH/HALF
    ("AL", "AB", "BAI", "ADY", "L", ["N", "T", "M"]),       # ALL/LAB, BAIL/LADY
    ("AI", "ACE", "BA", "EEF", "R", ["D", "L", "S"]),       # AIR/RACE, BAR/REEF
    ("BLO", "ADE", "BO", "EB", "W", ["B", "C", "D"]),       # BLOW/WADE, BOW/WEB
]
_CONNECT_D3 = [
    ("BO", "ABE", "BOM", "ABY", "B", ["W", "C", "A"]),      # BOB/BABE, BOMB/BABY
    ("ABL", "ACH", "AC", "AST", "E", ["F", "D", "G"]),      # ABLE/EACH, ACE/EAST
    ("ANT", "CE", "TAX", "CON", "I", ["A", "J", "H"]),      # ANTI/ICE, TAXI/ICON
    ("DIS", "EY", "PAR", "ING", "K", ["H", "S", "D"]),      # DISK/KEY, PARK/KING
    ("AKI", "AIL", "AME", "ET", "N", ["O", "M", "P"]),      # AKIN/NAIL, AMEN/NET
    ("AM", "ACE", "ATO", "ACK", "P", ["M", "Q", "O"]),      # AMP/PACE, ATOP/PACK
    ("FL", "NIT", "MEN", "RGE", "U", ["V", "T", "W"]),      # FLU/UNIT, MENU/URGE
    ("AN", "ARD", "BUS", "OLK", "Y", ["N", "Z", "X"]),      # ANY/YARD, BUSY/YOLK
    ("BUZ", "ERO", "JAZ", "OO", "Z", ["A", "Y", "B"]),      # BUZZ/ZERO, JAZZ/ZOO
]
_CONNECT_D4 = [
    ("BEE", "ACE", "BUF", "AIR", "F", ["N", "R", "G"]),     # BEEF/FACE, BUFF/FAIR
    ("FAR", "ANY", "FOR", "ARK", "M", ["B", "D", "N"]),     # FARM/MANY, FORM/MARK
    ("ALA", "ACK", "ARM", "AFE", "S", ["R", "T", "U"]),     # ALAS/SACK, ARMS/SAFE
    ("COL", "RAM", "BEL", "OLL", "T", ["D", "L", "U"]),     # COLT/TRAM, BELT/TOLL
]

# Curated pool for the taxonomy's `two-connectors` question_type: the same
# mechanic with a TWO-letter connector, e.g. CRAB(__)ABBEY -> AB gives
# CRAB/ABBEY. This is the natural two-letter extension of the mechanic
# above, not independently demonstrated in either published source cited
# there (both only ever show single-letter connectors) -- flagged here as
# inferred, not confirmed, the same honesty LetterMove's own docstring
# applies to its unimplemented `swap-two-letters` question_type. Generated
# and verified the same exhaustive way: every candidate was checked against
# all 676 two-letter combinations (aa-zz) before being kept, and every
# wrong-pair distractor is confirmed not to solve both fragment pairs. Only
# 12 entries survived the same vocabulary filter described above -- shipped
# honestly smaller than the single-letter pool rather than padded out with
# borderline vocabulary.
_CONNECT_TWO = [
    ("CR", "BEY", "GR", "LE", "AB", ["AT", "ID", "BA"]),      # CRAB/ABBEY, GRAB/ABLE
    ("DE", "FAIR", "LE", "TER", "AF", ["AL", "AT", "FA"]),    # DEAF/AFFAIR, LEAF/AFTER
    ("DR", "AIN", "FL", "ED", "AG", ["AM", "AX", "GA"]),      # DRAG/AGAIN, FLAG/AGED
    ("BE", "T", "ORG", "Y", "AN", ["AL", "AM", "NA"]),        # BEAN/ANT, ORGAN/ANY
    ("CH", "ART", "CHE", "PLE", "AP", ["PA", "AQ", "AO"]),    # CHAP/APART, CHEAP/APPLE
    ("ALT", "CADE", "APPE", "EA", "AR", ["RA", "AS", "AQ"]),  # ALTAR/ARCADE, APPEAR/AREA
    ("AL", "HES", "ATL", "IDE", "AS", ["SA", "AT", "AR"]),    # ALAS/ASHES, ATLAS/ASIDE
    ("BE", "TACH", "BO", "OM", "AT", ["BO", "LO", "TA"]),     # BEAT/ATTACH, BOAT/ATOM
    ("CL", "AIT", "DR", "AY", "AW", ["WA", "AX", "AV"]),      # CLAW/AWAIT, DRAW/AWAY
    ("ADO", "ACH", "BRI", "AR", "BE", ["RE", "AR", "DE"]),    # ADOBE/BEACH, BRIBE/BEAR
    ("AR", "AIN", "ATTA", "AIR", "CH", ["HC", "CI", "CG"]),   # ARCH/CHAIN, ATTACH/CHAIR
    ("ABI", "AD", "AI", "AL", "DE", ["LE", "RE", "ED"]),      # ABIDE/DEAD, AIDE/DEAL
]


@register
class ConnectingLetter(Generator):
    """VR Connecting Letters: two word-fragment pairs are shown, each with a
    gap -- e.g. BA(_)ON and CU(_)EN -- and the SAME letter fills every gap,
    turning BOTH halves of BOTH pairs into real words at once: BA(_)ON ->
    BAT/TON, CU(_)EN -> CUT/TEN. Confirmed against two independent published
    sources (11plusforparents.co.uk Type A; examhappy.co.uk Type 5).

    UNIQUENESS is the entire puzzle, exactly like LetterMove: every pool
    entry was generated and checked by exhaustive search, not by eye -- see
    the comment above _CONNECT_D2 for the dictionary methodology, which
    independently rediscovers the same "raw dictionary is too permissive"
    lesson LetterMove's own pool comment describes. Independently
    re-verified against three separate word-frequency sources.

    DIFFICULTY: d2-d4 use the `single-connector` pool, split into three
    tiers by the combined length of the four resulting words (longer words
    are slower to check by eye even though the mechanism never changes, the
    same posture HiddenWord takes toward its own three tiers). d5 switches
    to the `two-connectors` pool -- the harder, two-letter variant.

    Only `single-connector` and `two-connectors` -- both of this subtopic's
    taxonomy question_types -- are implemented. `two-connectors` is the
    natural two-letter extension of the same mechanic (structurally
    obvious, but not independently demonstrated in either source cited
    above) and ships with a visibly smaller pool (12 vs 22 entries) for
    that reason -- see its own comment above _CONNECT_TWO.

    Kind/pipeline note, same gap several sibling generators document: the
    natural answer format here is `short_text` (the pupil writes the
    connecting letter or letters), but generate_bank.py hardcodes every
    generated Question as `kind = MCQ`. So this class presents 4 options --
    the correct connector plus 3 wrong letters/letter-pairs that do NOT
    solve both fragment pairs at once -- rather than free text.
    """
    slug = "vr.connectingletter"
    section, subtopic = "VR", "Connecting Letters"
    template_id = "connecting-letter"
    difficulties = (2, 3, 4, 5)

    def build(self, rng, difficulty):
        if difficulty == 5:
            return self._two_connector(rng, difficulty)
        return self._single_connector(rng, difficulty)

    def _single_connector(self, rng, difficulty):
        pool = {2: _CONNECT_D2, 3: _CONNECT_D3, 4: _CONNECT_D4}[difficulty]
        p1, s1, p2, s2, letter, wrong = rng.choice(pool)
        w1, w2, w3, w4 = p1 + letter, letter + s1, p2 + letter, letter + s2
        return Item(
            stem=(f"The same letter goes in both gaps below, making a real "
                  f"word each time. What is the letter?\n"
                  f"{p1}(_){s1}     {p2}(_){s2}"),
            options=shuffled_options(rng, letter, wrong),
            difficulty=difficulty,
            params={"p1": p1, "s1": s1, "p2": p2, "s2": s2, "letter": letter},
            question_type="single-connector",
            explanation=(f"{letter} gives {w1} and {w2} from the first pair, "
                         f"and {w3} and {w4} from the second."),
        )

    def _two_connector(self, rng, difficulty):
        p1, s1, p2, s2, conn, wrong = rng.choice(_CONNECT_TWO)
        w1, w2, w3, w4 = p1 + conn, conn + s1, p2 + conn, conn + s2
        return Item(
            stem=(f"The same two letters go in both gaps below, making a "
                  f"real word each time. What are the two letters?\n"
                  f"{p1}(__){s1}     {p2}(__){s2}"),
            options=shuffled_options(rng, conn, wrong),
            difficulty=difficulty,
            params={"p1": p1, "s1": s1, "p2": p2, "s2": s2, "conn": conn},
            question_type="two-connectors",
            explanation=(f"{conn} gives {w1} and {w2} from the first pair, "
                         f"and {w3} and {w4} from the second."),
        )


# The 8 standard compass points, clockwise from North, and their full names
# as used in question stems/options (hyphenated, matching typical UK 11+
# paper phrasing: "North-East", not "Northeast").
COMPASS_POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
COMPASS_WORDS = {
    "N": "North", "NE": "North-East", "E": "East", "SE": "South-East",
    "S": "South", "SW": "South-West", "W": "West", "NW": "North-West",
}
COMPASS_OPPOSITE = {
    "N": "S", "NE": "SW", "E": "W", "SE": "NW",
    "S": "N", "SW": "NE", "W": "E", "NW": "SE",
}
# Unit step per compass point on an integer (east, north) grid. Diagonal
# steps use length 1 in EACH axis (not a normalised length of 1 overall) so
# that every coordinate anywhere in this generator stays an exact integer,
# and adding two or more of these together algebraically can only ever land
# on another exact compass direction or on a genuinely off-compass vector —
# see `compass_of_vector` below, which is what tells the two apart.
COMPASS_STEP = {
    "N": (0, 1), "NE": (1, 1), "E": (1, 0), "SE": (1, -1),
    "S": (0, -1), "SW": (-1, -1), "W": (-1, 0), "NW": (-1, 1),
}


def compass_of_vector(dx, dy):
    """The exact compass point of an (east, north) integer vector, or None.

    A vector points EXACTLY at one of the 8 standard compass directions iff
    it lies on an axis (dx == 0 xor dy == 0) or on a true diagonal
    (abs(dx) == abs(dy)) — anything else (e.g. (1, 2), pointing at a real
    angle of about 26.6 degrees east of north) sits between two compass
    points with no single correct answer, and must be rejected rather than
    rounded to "the closest" one.

    This is an exact INTEGER check, not a tolerance-on-an-angle one: nothing
    in this generator ever computes a floating-point angle, so there is no
    22.5-degree boundary case to get subtly wrong by rounding. Every caller
    below either uses the result immediately as a fully-determined answer,
    or discards the pair and does not ask about it at all.
    """
    if dx == 0 and dy == 0:
        return None
    if dx == 0:
        return "N" if dy > 0 else "S"
    if dy == 0:
        return "E" if dx > 0 else "W"
    if abs(dx) == abs(dy):
        if dx > 0 and dy > 0:
            return "NE"
        if dx > 0 and dy < 0:
            return "SE"
        if dx < 0 and dy < 0:
            return "SW"
        return "NW"
    return None


@register
class Directions(Generator):
    """VR Directions: compass bearings, turning to a final facing direction,
    and the compass direction of one point relative to another on a small
    grid of points defined by directional statements.

    PROVENANCE — WEAKER EVIDENCE THAN THIS FILE'S OTHER LOGIC GENERATORS.
    LogicOrdering and MustBeTrue's puzzle *shapes*, and HIDDEN/NumberSequence/
    LetterAnalogy/NumberCode/MissingNumberSum/TripletRule/LetterAlgebra's
    mechanics, were each checked as working notes against specific cited UK
    GL/CEM 11+ papers (see the module docstring and each class's own
    docstring). This one was not: compass bearings, turning by a stated
    angle, and relative position among points are a standard, well-
    established convention in general verbal-reasoning/aptitude-test
    material, confirmed against general sources describing that convention —
    but NOT against a specific 11+ paper example the way the others above
    were. This is a published type description, not an independently
    confirmed 11+ paper example. All three question_types are `proposed` in
    taxonomy.json for the same reason; treat this class as a starting
    hypothesis and re-check against a real paper before relying on it the
    way the paper-evidenced generators can be.

    THE AMBIGUITY RISK AND HOW THIS AVOIDS IT — the same failure mode
    MustBeTrue's docstring warns about (an under-determined world where the
    "right" answer is only right in the world the author happened to
    imagine), here in a coordinate-geometry shape rather than a day-table
    one. A "what direction is X from Y" question is only fair if X and Y's
    relative position is EXACTLY one of the 8 standard compass points, not
    merely close to one. A single directional statement ("P is North of Q")
    fixes only one axis and says nothing about the other, so two such
    statements about different points do not, in general, pin down an exact
    bearing between them: "2 east, 3 north" of somewhere points at a real
    angle of about 56 degrees from north — neither North-East nor due East —
    a case a hand-written puzzle could get wrong by eyeballing it as
    "roughly north-east".

    Every point is placed on an integer (east, north) grid, built
    mechanically from a chain of stated directional moves (each move one of
    the 8 compass unit steps in COMPASS_STEP, times a small integer
    distance) — a turtle-graphics walk, not prose the author hopes adds up.
    Any two points' relative bearing is then just their coordinate
    difference, and `compass_of_vector()` classifies that difference as one
    of the 8 points ONLY if it lies exactly on an axis or exactly on a
    diagonal — see that function's own docstring for why this is an exact
    integer check with no floating-point boundary case, unlike a
    tolerance-on-an-angle test. `build()` computes every pairwise bearing
    among the generated points up front (`_relative`) or the one resultant
    bearing of a two-leg walk (`_bearing`), and only ever asks about a pair
    that passed; if none did, it returns None (bounded retries) rather than
    ship a guess. `turns-and-facing` needs no such filter at all: every turn
    is a multiple of 45 degrees by construction, so the running facing
    direction is always exactly one of the 8 points at every step — there is
    no vector arithmetic in that mechanic to go off-compass in the first
    place.

    TWO REAL BUGS THIS SHIPPED WITH FIRST, CAUGHT BY INDEPENDENT ADVERSARIAL
    VERIFICATION (not this class's own self-test, which checked the claimed
    answer against this class's own internal grid — necessary but not
    sufficient, because both bugs were about the internal grid disagreeing
    with what the STEM told the pupil, not about the grid's own arithmetic):

    1. `_bearing`'s stem originally said "8km North-West", implying real
       Euclidean distance, while COMPASS_STEP moves a diagonal leg 8 units on
       BOTH axes internally (a grid/turtle-walk abstraction, not true 8km of
       displacement — true Euclidean 8km North-West is (-8/sqrt(2), 8/sqrt(2)),
       not (-8, 8)). Whenever at least one leg was diagonal, the stem's
       implied real-world geometry and the internal grid disagreed, and the
       "exact" answer computed from the grid was frequently wrong against
       real-world trigonometry (measured 74.1% mismatch on diagonal-inclusive
       legs). Fixed by reframing the stem as an abstract square grid ("X
       squares North-West", not "Xkm") so the pupil is never told or implied
       a real-world distance unit — the stem's own geometry now IS the grid
       COMPASS_STEP computes, with nothing left to disagree.
    2. `_relative`'s statements originally gave only a direction ("R is North
       of Q"), never a distance, then asked about an INDIRECT pair (e.g. R
       from S, where R and S are both spokes off a shared point but not
       stated relative to each other). A direction-only statement fixes only
       one axis; the indirect pair's true bearing depends on the two legs'
       relative (undisclosed) magnitudes, which the stem never gave the
       pupil any way to know — so the "exact" answer computed from this
       class's own internally-generated distances was right about this
       class's own hidden state but not derivable from what the pupil was
       actually shown (measured 65-66% of such questions had a true answer
       that flipped under a different, equally stem-consistent distance
       draw). Fixed by disclosing every leg's distance in its statement ("R
       is 4 squares North of Q") — once distances are stated, a pupil
       COULD in principle plot every point exactly from what's given, so an
       indirect pair's bearing is answerable, and `compass_of_vector`'s
       existing exactness filter (which was never the bug) is now checking
       a claim that's actually derivable from the stem rather than one only
       this class's own hidden state could confirm.

    DIFFICULTY / question_type split: d1-d2 are `turns-and-facing` (one turn,
    then two turns to hold in mind at once — see _turns); d3 is
    `compass-bearing` (a two-leg walk between three named places, asking the
    bearing of one from another — see _bearing; the single-leg "what's the
    opposite of X" shape is simple enough it would belong at d1, but is
    folded into the two-leg case instead so this subtopic doesn't ship a
    whole tier that's pure "opposite direction" vocabulary recall); d4-d5 are
    `relative-position` (a hub-and-spoke layout of 3 points at d4 — one
    combination step; a 4-point layout at d5 where later points can hang off
    an earlier spoke rather than only the hub, so the query pair can need two
    hops of reasoning — see _relative).

    Kind is `mcq` throughout: the answer is always one of the 8 compass
    direction names, which is a natural closed set of options
    (elevenplus_data/CLAUDE.md's VR answer-format table maps "pick one
    answer" to `mcq`) — no numeric/short_text workaround needed here, unlike
    several of this file's other VR generators.
    """
    slug = "vr.directions"
    section, subtopic = "VR", "Directions"
    template_id = "directions-compass"
    difficulties = (1, 2, 3, 4, 5)

    _TURN_ANGLES_D1 = [90, 180]
    _TURN_ANGLES = [45, 90, 135, 180]
    _PLACE_NAMES = ["Ashford", "Denby", "Elmsworth", "Fenwick", "Gorley",
                    "Harden", "Ipswold", "Kelston"]
    _POINT_NAMES = list("PQRST")

    def build(self, rng, difficulty):
        if difficulty in (1, 2):
            return self._turns(rng, difficulty)
        if difficulty == 3:
            return self._bearing(rng, difficulty)
        return self._relative(rng, difficulty)

    def _turns(self, rng, difficulty):
        # DIFFICULTY: one turn to apply, then two turns applied in sequence —
        # every angle is a multiple of 45 degrees, so the running facing
        # direction is always exactly one of the 8 compass points with no
        # vector arithmetic and therefore no off-compass case to guard
        # against (contrast _bearing/_relative, which do need one).
        n_turns = 1 if difficulty == 1 else 2
        angles_pool = self._TURN_ANGLES_D1 if difficulty == 1 else self._TURN_ANGLES
        start_idx = rng.randrange(8)
        turns = [(rng.choice(angles_pool), rng.random() < 0.5) for _ in range(n_turns)]

        def final_index(turn_list):
            idx = start_idx
            for angle, clockwise in turn_list:
                delta = (angle // 45) * (1 if clockwise else -1)
                idx = (idx + delta) % 8
            return idx

        idx = final_index(turns)
        correct = COMPASS_POINTS[idx]
        start = COMPASS_POINTS[start_idx]

        # Distractors: the answer you'd get if the LAST turn had gone the
        # other way round (mixing up clockwise/anticlockwise is the obvious
        # real mistake here), the starting direction (forgot to turn at
        # all), and the two points adjacent to the correct one (off-by-one-
        # eighth-turn slip). At d2 (two turns) there's a second, equally
        # real mistake shape — applying only one of the two turns and
        # forgetting the other, in either order — so those are added too:
        # with only 4 candidates for `keep=3`, a single coincidental
        # collision (e.g. flipping the last turn happens to land back on
        # the start direction) could leave fewer than 3 distinct distractors
        # and ship a 3-option question. More candidates than are needed
        # makes that "spare a collision, not the question" (see
        # shuffled_options's own docstring).
        flipped_last = turns[:-1] + [(turns[-1][0], not turns[-1][1])]
        wrong_flip_last = COMPASS_POINTS[final_index(flipped_last)]
        wrong_neighbours = [COMPASS_POINTS[(idx + 1) % 8], COMPASS_POINTS[(idx - 1) % 8]]
        candidates = [wrong_flip_last, start] + wrong_neighbours
        if n_turns == 2:
            flipped_first = [(turns[0][0], not turns[0][1]), turns[1]]
            candidates += [
                COMPASS_POINTS[final_index(flipped_first)],   # flipped the FIRST turn instead
                COMPASS_POINTS[final_index([turns[0]])],       # only applied the first turn
                COMPASS_POINTS[final_index([turns[1]])],       # only applied the second turn
            ]

        turn_phrases = [
            f"turns {angle}° {'clockwise' if cw else 'anticlockwise'}"
            for angle, cw in turns
        ]
        action = ", then ".join(turn_phrases)
        stem = (f"Priya is facing {COMPASS_WORDS[start]}. She {action}. "
                f"Which direction is she facing now?")
        # shuffled_options dedups its `distractors` arg IN LIST ORDER and
        # keeps only the first `keep` survivors — shuffle first so every
        # candidate has a fair chance of being kept (see LetterAnalogy's
        # same comment above for why this matters).
        rng.shuffle(candidates)
        return Item(
            stem=stem,
            options=shuffled_options(rng, COMPASS_WORDS[correct],
                                      [COMPASS_WORDS[c] for c in candidates]),
            difficulty=difficulty,
            params={"variant": "turns", "start": start, "turns": turns},
            question_type="turns-and-facing",
            explanation=(f"Starting at {COMPASS_WORDS[start]} and applying each turn "
                         f"in order gives {COMPASS_WORDS[correct]}."),
        )

    def _bearing(self, rng, difficulty):
        # DIFFICULTY 3: a two-leg walk between three named places. The
        # resultant bearing of the third place from the first is only ever
        # asked about once verified exact (compass_of_vector) — see the
        # class docstring for why a single leg's direction fixes only one
        # axis and two legs don't automatically compose into a clean
        # 8-point bearing.
        names = rng.sample(self._PLACE_NAMES, 3)
        a, b, c = names
        resultant = None
        for _ in range(200):
            dir1 = rng.choice(COMPASS_POINTS)
            dist1 = rng.randint(2, 8)
            dir2 = rng.choice([d for d in COMPASS_POINTS if d != dir1])
            dist2 = rng.randint(2, 8)
            dx = COMPASS_STEP[dir1][0] * dist1 + COMPASS_STEP[dir2][0] * dist2
            dy = COMPASS_STEP[dir1][1] * dist1 + COMPASS_STEP[dir2][1] * dist2
            candidate_resultant = compass_of_vector(dx, dy)
            # Require the resultant to differ from BOTH individual legs, so
            # the question needs real composition rather than being
            # answerable by glancing at one leg alone.
            if candidate_resultant is not None and candidate_resultant not in (dir1, dir2):
                resultant = candidate_resultant
                break
        if resultant is None:
            return None

        ask_reverse = rng.random() < 0.5
        if ask_reverse:
            correct = COMPASS_OPPOSITE[resultant]
            asked_from, asked_of = a, c
        else:
            correct = resultant
            asked_from, asked_of = c, a

        stem = (f"On a square grid, {b} is {dist1} squares {COMPASS_WORDS[dir1]} of {a}. "
                f"{c} is {dist2} squares {COMPASS_WORDS[dir2]} of {b}. "
                f"Which direction is {asked_from} from {asked_of}?")

        correct_idx = COMPASS_POINTS.index(correct)
        # Distractors: the opposite of the correct answer (answered the
        # reverse question by mistake), each leg's own direction taken alone
        # (forgot to combine both legs, oriented for whichever framing was
        # asked), and the two points adjacent to the correct one.
        leg1_alone = dir1 if ask_reverse else COMPASS_OPPOSITE[dir1]
        leg2_alone = dir2 if ask_reverse else COMPASS_OPPOSITE[dir2]
        candidates = [
            COMPASS_OPPOSITE[correct], leg1_alone, leg2_alone,
            COMPASS_POINTS[(correct_idx + 1) % 8],
            COMPASS_POINTS[(correct_idx - 1) % 8],
        ]
        rng.shuffle(candidates)
        return Item(
            stem=stem,
            options=shuffled_options(rng, COMPASS_WORDS[correct],
                                      [COMPASS_WORDS[w] for w in candidates]),
            difficulty=difficulty,
            params={"variant": "bearing", "a": a, "b": b, "c": c, "dir1": dir1,
                    "dist1": dist1, "dir2": dir2, "dist2": dist2,
                    "ask_reverse": ask_reverse},
            question_type="compass-bearing",
            explanation=(f"Combining both legs, {c} is {COMPASS_WORDS[resultant]} of {a}"
                         + (f", so {a} is {COMPASS_WORDS[correct]} of {c}."
                            if ask_reverse else ".")),
        )

    def _relative(self, rng, difficulty):
        # DIFFICULTY: 3 points (hub + 2 spokes, every point defined directly
        # off the hub) at d4; 4 points at d5 where a later point can be
        # defined off an EARLIER SPOKE rather than only the hub, so the
        # query pair can require chaining two hops rather than one. Either
        # way, every pairwise bearing is computed from real coordinates and
        # only an exact one (compass_of_vector) is ever asked about.
        #
        # Two independently-placed points are exactly aligned (axis or
        # diagonal) only a minority of the time for d4's single-hop layout
        # (measured ~35%); at d5's 4-point layout it's actually a MAJORITY
        # (~69%), since more point pairs exist to check. Either way, a
        # single random layout can still have NO askable pair at all, so
        # rather than accept that as "no question this difficulty", retry
        # the ENTIRE layout with a fresh random draw; each retry is cheap
        # integer arithmetic, and the odds of every one of many retries
        # failing are negligible.
        n_points = 3 if difficulty == 4 else 4
        for _attempt in range(300):
            names = rng.sample(self._POINT_NAMES, n_points)
            hub = names[0]
            coords = {hub: (0, 0)}
            statements = []
            parent_of = {}
            ok = True
            for name in names[1:]:
                parent = hub if difficulty == 4 else rng.choice(list(coords.keys()))
                placed = False
                cx = cy = None
                d = None
                for _ in range(50):
                    d = rng.choice(COMPASS_POINTS)
                    dist = rng.randint(2, 6)
                    px, py = coords[parent]
                    cx = px + COMPASS_STEP[d][0] * dist
                    cy = py + COMPASS_STEP[d][1] * dist
                    if (cx, cy) not in coords.values():
                        placed = True
                        break
                if not placed:
                    ok = False
                    break
                coords[name] = (cx, cy)
                parent_of[name] = parent
                statements.append(f"{name} is {dist} squares {COMPASS_WORDS[d]} of {parent}.")
            if not ok:
                continue

            # Pairs whose relation was stated directly (either order —
            # reading the reverse off a direct statement is just "the
            # opposite", not genuine composition) are excluded from the
            # question pool below.
            direct_pairs = {(n, p) for n, p in parent_of.items()} | \
                           {(p, n) for n, p in parent_of.items()}

            candidates = []
            for ni in names:
                for nj in names:
                    if ni == nj or (ni, nj) in direct_pairs:
                        continue
                    dx = coords[ni][0] - coords[nj][0]
                    dy = coords[ni][1] - coords[nj][1]
                    bearing = compass_of_vector(dx, dy)
                    if bearing is not None:
                        candidates.append((ni, nj, bearing))
            if candidates:
                break
        else:
            return None
        query_from, query_to, correct = rng.choice(candidates)

        stem = ("On a square grid, " + " ".join(statements) +
                f" Which direction is {query_from} from {query_to}?")
        correct_idx = COMPASS_POINTS.index(correct)
        wrong = [
            COMPASS_OPPOSITE[correct],
            COMPASS_POINTS[(correct_idx + 1) % 8],
            COMPASS_POINTS[(correct_idx - 1) % 8],
            COMPASS_POINTS[(correct_idx + 2) % 8],
        ]
        rng.shuffle(wrong)
        return Item(
            stem=stem,
            options=shuffled_options(rng, COMPASS_WORDS[correct],
                                      [COMPASS_WORDS[w] for w in wrong]),
            difficulty=difficulty,
            params={"variant": "relative", "names": names, "parent_of": parent_of,
                    "coords": coords, "query": [query_from, query_to]},
            question_type="relative-position",
            explanation=(f"Plotting the points from the statements, {query_from} ends up "
                         f"{COMPASS_WORDS[correct]} of {query_to}."),
        )


# Curated pool for VR Paired Synonyms, targeting `closest-pair` specifically
# (not the subtopic's other slug `one-from-each-group`, which taxonomy.json's
# only citation for this subtopic -- one weak collaborator report shared
# verbatim with Paired Antonyms -- covers already). `closest-pair` has since
# been directly evidenced by four independent real papers this project has
# read (GL Assessment official Familiarisation, CGP-GL, Owl Tutors x2,
# Bond/OUP) for the exact "closest/most similar in meaning" bracket-pair
# mechanic AntonymPair already implements for opposites -- e.g. CGP-GL's own
# worked example, (weak, soft, small) (tiny, strong, large), whose intended
# pair is small/tiny, exactly entry 9 below.
#
# Ported STRUCTURE directly from ANTONYM_POOL, but NOT assembled the same
# casual way -- AntonymPair's pool needed three rejected rounds before
# shipping, each failing independent review for a different variant of "a
# pupil can answer with no synonym/antonym knowledge at all" (see
# ANTONYM_POOL's own comment for the full history: mismatched word class,
# mismatched semantic domain, and fillers borrowed from another entry's own
# target pair, letting a pupil spot an obviously-paired decoy). This pool
# applies all three of those safeguards from the start rather than by
# trial and error: every word in the whole pool is the same part of speech
# (adjective); every entry's fillers are drawn from the SAME semantic
# sub-domain as that entry's own target pair (temperament words alongside a
# temperament target, size words alongside a size target -- an early draft
# mixed huge/enormous with temperament fillers, which would have let a
# pupil spot the odd size-word by TOPIC alone, the same tell AntonymPair's
# rev2 failed on); and no word is ever both a TARGET in one entry and a
# FILLER anywhere else, checked programmatically before this pool was
# committed (63 distinct words across 9 entries, zero overlap). This is a
# first-ship pool, not one that has been through multiple independent
# human review rounds the way ANTONYM_POOL's final 11 entries were -- treat
# it with the same scrutiny any new content pool gets before merging.
SYNONYM_POOL = [
    ("adj", "brave", ("lazy", "tidy"), "courageous", ("forgetful", "punctual"), "talkative"),
    ("adj", "happy", ("rude", "clumsy"), "cheerful", ("stubborn", "sleepy"), "curious"),
    ("adj", "angry", ("shy", "studious"), "furious", ("graceful", "serious"), "generous"),
    ("adj", "clever", ("humble", "calm"), "intelligent", ("frantic", "cowardly"), "gloomy"),
    ("adj", "scared", ("honest", "polite"), "frightened", ("deceitful", "impolite"), "arrogant"),
    ("adj", "quiet", ("reckless", "diligent"), "silent", ("stingy", "energetic"), "cautious"),
    ("adj", "kind", ("selfish", "greedy"), "caring", ("harsh", "jealous"), "vain"),
    ("adj", "huge", ("narrow", "shallow"), "enormous", ("distant", "thin"), "steep"),
    ("adj", "small", ("wide", "tall"), "tiny", ("thick", "long"), "deep"),
]
_SYNONYM_D3 = SYNONYM_POOL[0:3]
_SYNONYM_D4 = SYNONYM_POOL[3:6]
_SYNONYM_D5 = SYNONYM_POOL[6:9]


@register
class SynonymPair(Generator):
    """VR Paired Synonyms: two bracket groups of 3 words each; the pupil
    picks the one word from each bracket that is CLOSEST in meaning to any
    cross-bracket pair -- e.g. (brave, lazy, tidy) (courageous, forgetful,
    punctual) -> brave/courageous. Directly evidenced (see SYNONYM_POOL's
    own comment for the four independent real-paper citations).

    Structurally a direct port of AntonymPair (same bracket/fixed-word/
    distractor-padding mechanic, opposite relation), including the same
    KIND/PIPELINE MISMATCH: elevenplus_data/CLAUDE.md maps this shape to
    `grouped_options`, but `Item` has no `option_groups` field and
    `generate_bank._write()` only ever writes flat `options` -- so this
    flattens the task exactly as AntonymPair does, for the same reason.

    QUESTION_TYPE CHOICE: uses `closest-pair`, the freshly-evidenced slug
    (see SYNONYM_POOL's comment), not `one-from-each-group`.
    """

    slug = "vr.synonympair"
    section, subtopic = "VR", "Paired Synonyms"
    template_id = "synonym-pair-bracket"
    difficulties = (3, 4, 5)

    def build(self, rng, difficulty):
        pool = {3: _SYNONYM_D3, 4: _SYNONYM_D4, 5: _SYNONYM_D5}[difficulty]
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
            f"Which word in the second group is CLOSEST in meaning to "
            f"“{fixed_word}” in the first group?"
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
            question_type="closest-pair",
            explanation=(
                f"“{fixed_word}” means much the same as “{correct}”. None of "
                f"the other words in the second group are as close in meaning."
            ),
        )


# ThreeLetterInsertion pool. Evidenced directly, not by analogy: all three GL
# Assessment official Familiarisation booklets carry an identical section --
# "the word in capitals has had three letters next to each other taken out.
# These three letters will make one correctly-spelt word without changing
# their order. The sentence that you make must make sense" (Test 1 Booklet
# Q52 p.14, Test 2 Booklet Q1 p.2, Test 3 Booklet Q24 p.8) -- worked example
# "The cat scratched him with his CS" -> LAW -> CLAWS.
#
# Every entry is checked exhaustively, not by eye, and the real uniqueness
# question is narrower than "does this base word have another 3-letter
# substring that's also a word" -- it's "does any OTHER accepted English
# word ALSO fill this exact shown gap" (prefix+word+suffix). A base word can
# have several individually-unique decompositions (BREATH is both REA->BTH
# and EAT->BRH) without the puzzle being ambiguous, since only one is ever
# shown -- what would be a real defect is a second word fitting the SAME
# gap. "Accepted" means the intersection of /usr/share/dict/web2 (~234k
# entries) with a wordfreq zipf>=1.2 floor (~59k words survive) -- the same
# "an unabridged dictionary alone is too permissive" fix LetterMove's and
# ConnectingLetter's own pool comments describe, checked for the same
# reason here (their comments also cover why this needs a system
# dictionary, not just wordfreq: zipf alone doesn't say whether a string is
# an ENGLISH WORD at all, only how common a known one is).
#
# That check needs a system dictionary this project's own production deploy
# does not have -- see _build_compound_data.py's own docstring: Render has
# no /usr/share/dict, so nothing a generator touches at runtime may read
# one. It ran once, offline, against every entry below before they were
# committed. catalog/generators/test_verbal_gap_batch.py's own regression
# check is deliberately NOT a re-run of that dictionary search (structural
# only, no dictionary needed) -- the same posture ConnectingLetter's own
# checker already takes, for the same reason: the deep proof lives here, in
# this comment and the PR that added it, not in a CI step that would need a
# word list this deploy doesn't have.
#
# Tuple shape: (base_word, start, fragment, sentence_template).
_TLI_EASY = [
    ("YOURS", 1, "OUR", "Is this coat {} or mine?"),
    ("THUMB", 1, "HUM", "She hurt her {} while chopping vegetables."),
    ("PLEASE", 1, "LEA", "Could you {} pass the salt?"),
    ("CHANGE", 1, "HAN", "I need some {} for the car park."),
    ("BRIGHT", 1, "RIG", "The sky was {} and clear this morning."),
    ("FOREST", 1, "ORE", "They went for a walk in the thick {}."),
]
_TLI_MEDIUM = [
    ("NEARBY", 1, "EAR", "There is a park {} where we can play."),
    ("BREATH", 2, "EAT", "Take a deep {} before the race starts."),
    ("DRAGON", 2, "AGO", "In the story, the knight fought a fierce {}."),
    ("GALAXY", 1, "ALA", "The Milky Way is our {}."),
    ("WEALTH", 2, "ALT", "His family's {} came from trading spices."),
    ("CREDIT", 1, "RED", "She received {} for her hard work."),
]
_TLI_HARD = [
    ("CABBAGE", 3, "BAG", "She grew a large {} in her garden."),
    ("UPRIGHT", 2, "RIG", "Please sit {} in your chair."),
    ("DOLPHIN", 3, "PHI", "We watched a {} leap out of the sea."),
    ("HAIRCUT", 1, "AIR", "He got a new {} before school started."),
    ("COTTAGE", 3, "TAG", "They spent the holiday at a small {} by the sea."),
    ("ATHLETE", 3, "LET", "She trains every day because she is an {}."),
]
_TLI_POOLS = {2: _TLI_EASY, 3: _TLI_MEDIUM, 4: _TLI_HARD}
_TLI_ALL_FRAGMENTS = [frag for pool in _TLI_POOLS.values() for _w, _s, frag, _t in pool]


@register
class ThreeLetterInsertion(Generator):
    """VR Three-Letter Insertion (GL Fam Test 1/2/3 Booklets -- see the pool
    comment above _TLI_EASY for exact question numbers and pages). A word in
    capitals has had three consecutive letters removed, shown as the
    remaining letters run together with NO gap marker -- the real papers'
    own convention ("CS", not "C_S"). The pupil finds the three letters
    that are themselves a real word AND slot back in, without changing
    order, to make the sentence make sense.

    Distractors are drawn from OTHER pool entries' own correct fragments --
    real 3-letter English words, never invented strings, so a wrong answer
    is never eliminated just by not looking like a word. Every fragment in
    the whole pool has already been checked (see the pool comment) to not
    fit any OTHER entry's gap either, so no distractor can accidentally
    make its own second correct answer when substituted in.
    """
    slug = "vr.threeletterinsertion"
    section, subtopic = "VR", "Three-Letter Insertion"
    template_id = "three-letter-insertion"
    difficulties = (2, 3, 4)

    def build(self, rng, difficulty):
        pool = _TLI_POOLS[difficulty]
        word, start, fragment, sentence = rng.choice(pool)
        remainder = word[:start] + word[start + 3:]
        distractor_pool = [f for f in _TLI_ALL_FRAGMENTS if f != fragment]
        distractors = rng.sample(distractor_pool, min(3, len(distractor_pool)))
        rendered = sentence.format(remainder)
        return Item(
            stem=(f"The word in CAPITALS has had three letters taken out and "
                  f"run together with no gap. Find the three letters -- "
                  f"themselves a real word -- that slot back in, without "
                  f"changing their order, to complete the word and make the "
                  f"sentence make sense.  {rendered}"),
            options=shuffled_options(rng, fragment, distractors, keep=3),
            difficulty=difficulty,
            params={"word": word, "start": start, "fragment": fragment},
            question_type="insert-to-complete",
            explanation=(f"Putting {fragment} back gives {word}: "
                         f"“{rendered}” becomes "
                         f"“{sentence.format(word)}”."),
        )


# Middle Word pool. Evidenced directly, distinctly from WordPattern: Bond/OUP's
# "Verbal Reasoning 11+ Practice Test" (Alison Primrose, 2015 -- VR example
# papers /VERBAL REASONING 10.pdf and 11.pdf, byte-identical copies of the same
# paper, both p.4 Q52-57) prints "Look at the first group of three words. The
# word in the middle has been made from the other two words. Complete the
# second group of three words in the same way, making a new word in the
# middle" with the worked example PAIN/INTO/TOOK, ALSO/SOON/ONLY -- confirmed
# by direct computation, not assumed: INTO = PAIN[-2:] + TOOK[:2] ("in"+"to"),
# SOON = ALSO[-2:] + ONLY[:2] ("so"+"on"), both exact.
#
# This is NOT WordPattern under a different name, despite surface similarity
# in the letter-arithmetic -- prior research in this repo (plans.md's VR
# generator coverage entry, "middle_word" Outstanding item) concluded the two
# were the same mechanic and left this subtopic unbuilt; re-checked directly
# against this real paper rather than assumed, and the presentation is
# genuinely different. WordPattern's own docstring is explicit that its
# middle word is a DECOY, "present only to match the real three-word row
# layout", with the derived word shown SEPARATELY as a fourth, bracketed
# item -- a 4-slot row. This paper's Middle Word puzzle has no decoy and no
# bracket: three words only, and the derived word occupies the middle slot
# itself -- a 3-slot row where "the middle" IS the answer, not a distraction
# from it. Same rule family (letters from two flanking words compress
# together), different real-paper task.
#
# Every entry: word1[-2:] + word3[:2] reproduces the stored middle word
# exactly (verified programmatically, not by eye -- see the assertion this
# pool was built and checked against). Words are ordinary, common English
# vocabulary (zipf >= 4.0, checked against a system dictionary offline, same
# "unabridged alone is too permissive" methodology LetterMove/ConnectingLetter/
# ThreeLetterInsertion already use) -- no proper nouns or brand-adjacent
# entries. No word is ever reused across the whole pool (as word1, word3 OR a
# middle word), so a distractor drawn from one entry can never coincide with
# another entry's own correct answer. The rule is stated outright via a fixed
# worked example shown in every stem (the two real citations above, used
# every time, never as a gradable item themselves) -- the pupil is TOLD the
# extraction rule, not asked to infer it, so unlike WordPattern's
# `find-pattern` there is no rule-ambiguity risk, only the ordinary "is the
# right answer the only real word this computation could produce" check,
# which is exact and deterministic here.
#
# Tuple shape: (word1, word3, middle_word).
_MW_EASY = [
    ("GRAB", "LEAD", "ABLE"),
    ("DRAG", "EDGE", "AGED"),
    ("APPEAR", "EACH", "AREA"),
    ("BEAR", "MYSELF", "ARMY"),
    ("TRIBE", "ATTACK", "BEAT"),
    ("TUBE", "EFFECT", "BEEF"),
]
_MW_MEDIUM = [
    ("ARCH", "ATTEND", "CHAT"),
    ("BEACH", "EFFORT", "CHEF"),
    ("ASIDE", "ALARM", "DEAL"),
    ("BESIDE", "ARCTIC", "DEAR"),
    ("BLADE", "EPIC", "DEEP"),
]
_MW_HARD = [
    ("BLONDE", "SKETCH", "DESK"),
    ("IDEA", "SEAL", "EASE"),
    ("ADDED", "ITEM", "EDIT"),
    ("ANGEL", "SEALED", "ELSE"),
    ("CLEAN", "TICKET", "ANTI"),
]
_MW_POOLS = {2: _MW_EASY, 3: _MW_MEDIUM, 4: _MW_HARD}
_MW_ALL_MIDDLES = [mid for pool in _MW_POOLS.values() for _w1, _w3, mid in pool]
_MW_DEMO = ("PAIN", "TOOK", "INTO"), ("ALSO", "ONLY", "SOON")


@register
class MiddleWord(Generator):
    """VR Middle Word (Bond/OUP "Verbal Reasoning 11+ Practice Test" p.4
    Q52-57 -- see the pool comment above _MW_EASY for the exact citation and
    the worked verification). Three words are shown in a row: the first, a
    blank, and the third. The word belonging in the blank is made by joining
    the last two letters of the first word to the first two letters of the
    third. A worked example demonstrating this (the paper's own two example
    triples) is shown in every stem, so the rule is given, not inferred.

    Distractors are drawn from OTHER pool entries' own correct middle words
    -- real English words, never invented strings -- so a wrong answer is
    never eliminated just by not looking like a word. No word in the whole
    pool is ever reused as word1, word3 or a middle word anywhere else, so a
    distractor can never coincide with the correct answer for a different
    reason than being wrong.
    """
    slug = "vr.middleword"
    section, subtopic = "VR", "Middle Word"
    template_id = "middle-word"
    difficulties = (2, 3, 4)

    def build(self, rng, difficulty):
        pool = _MW_POOLS[difficulty]
        word1, word3, middle = rng.choice(pool)
        demo1, demo2 = _MW_DEMO
        distractor_pool = [m for m in _MW_ALL_MIDDLES if m != middle]
        distractors = rng.sample(distractor_pool, min(3, len(distractor_pool)))
        return Item(
            stem=("Look at the first group of three words. The word in the "
                  "middle has been made from the other two words -- the "
                  "last two letters of the first word, then the first two "
                  "letters of the third.\n"
                  f"Example   {demo1[0]}   {demo1[2]}   {demo1[1]}      "
                  f"{demo2[0]}   {demo2[2]}   {demo2[1]}\n"
                  "Complete the next group of three words in the same way, "
                  "making a new word in the middle.\n"
                  f"{word1}   ______   {word3}"),
            options=shuffled_options(rng, middle, distractors, keep=3),
            difficulty=difficulty,
            params={"word1": word1, "word3": word3, "middle": middle},
            question_type="derive-from-both-sides",
            explanation=(f"The last two letters of {word1} ("
                         f"{word1[-2:]}) and the first two letters of "
                         f"{word3} ({word3[:2]}) join to make {middle}."),
        )
