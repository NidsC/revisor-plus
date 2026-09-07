"""Word-analogy data: relations, their sentence frames, and the safety table.

Three things live here, and only the first is the obvious one.

**RELATIONS** — ten relations, ten pairs each. Ordinary vocabulary chosen for
this purpose; nothing lifted from a published paper.

**The frame.** The previous generator built every explanation from one template,
`f"a {b1} is {relation} a {a1}"`, over data whose direction was not consistent:
`(petal, flower)` is part-and-whole, `(brush, painter)` is tool-and-user. So the
same template printed "a hat is worn on a head" (right) and "a flower is part of
a petal" (backwards), and for the adjective relations it printed "a scorching is
greater degree a warm", which is not English. **16 of the 28 rows the generator
could ship carried a reversed or ungrammatical explanation, including every
band-4 and band-5 row.** The fix is that direction is now DATA: each relation
carries its own frame, so the ordering of `(a, b)` in the pairs no longer has to
mean the same thing across relations. The adjective relations get frames with no
article at all, which is the real repair for "a scorching" — an a/an helper
alone would only have produced "an scorching" more grammatically.

**ALSO_HOLDS — the safety table, and the point of this module.** The old
generator drew every distractor from a DIFFERENT relation, so no distractor was
ever from the answer's own semantic class. That made it safe and useless: a bot
that ignores the analogy entirely and picks the option in the same class as the
exemplar's answer scored **28/28** on the shipped bank. Fixing that means
offering same-class distractors, which is exactly what opens the two-answer risk
`nightlight` opened for compound words.

`ALSO_HOLDS[relation][a]` lists every OTHER `b` a reasonable Year 6 could defend
for that `a` — beyond the keyed one, which is implied. Together with the keyed
pairs it composes into `DEFENSIBLE`, and the rule the generator obeys is:

    a distractor d is admissible for target a2 only if d not in DEFENSIBLE[a2]

`DEFENSIBLE` is deliberately PERMISSIVE, the role `ATTACHING` plays in
compound_data. Over-listing costs one distractor; omitting an entry ships a
question with two defensible answers. The conservative direction is the same.

**Where this is weaker than compound_data, and a reviewer should push.** web2
settles "is nightlight a word". Nothing settles "is a trowel a sculptor's tool".
`ALSO_HOLDS` is hand-authored judgement, so `test_word_analogies.py` proves the
generator obeys the table — it CANNOT prove the table is complete. That is the
weak point of this change and the thing worth a second reader.

Two classes of two-answer defect are removed structurally instead, because that
is stronger than any table:

  * **`DEFENSIBLE` is flat, not per-relation.** A pair keyed under ANY relation
    blocks that word everywhere. Without this, "Cat is to kitten as dog is to
    ______?" could offer `kennel`, defensible under `home_of`; and "Fast is to
    slow as hot is to ______?" could offer `freezing`, defensible as an opposite
    even though it is keyed under `greater_degree`.
  * **Only b-side words are ever offered.** An a-side word lets a pupil read the
    relation backwards and defend it — `Petal is to flower as rung is to
    ______?` offering `spoke`. The whole reversed-reading class cannot arise.

And where a pair was simply ambiguous it was DELETED rather than tabled, the way
#63 relabelled `handtools` and excluded nuts outright. `(fox, earth)` is gone:
"earth" is also soil, and a fox's home is equally a "den".
"""

# Relations. Each: (question_type, frame, tier-1 pairs, tier-2 pairs).
#
# `question_type` is a real slug from taxonomy.json's Word Analogies subtopic.
# The old generator emitted "", so none of the subtopic's five types was
# reachable; all five are reachable now.
#
# The frame is rendered with {a} and {b} plus {aa}/{ab}, the correct indefinite
# article for each. A relation whose words are adjectives uses no article.
#
# TIERS ARE A DIFFICULTY JUDGEMENT AND ARE NOT SOURCED. Tier 1 is everyday
# vocabulary a Year 5 meets; tier 2 is vocabulary a Year 6 sitting the exam is
# stretched by. Nothing here was checked against a real GL analogies paper — see
# the caveat in the PR description, which is the same one #58 carries for its
# difficulty-to-step mapping.
RELATIONS = {
    "young_of": (
        "category-relation",
        "{ab} {b} is a young {a}",
        [("dog", "puppy"), ("cat", "kitten"), ("horse", "foal"),
         ("sheep", "lamb"), ("cow", "calf")],
        [("goose", "gosling"), ("swan", "cygnet"), ("deer", "fawn"),
         ("goat", "kid"), ("fox", "cub")],
    ),
    "home_of": (
        "category-relation",
        "{ab} {b} is the home of {aa} {a}",
        [("bee", "hive"), ("bird", "nest"), ("rabbit", "burrow"),
         ("horse", "stable"), ("dog", "kennel")],
        [("badger", "sett"), ("otter", "holt"), ("beaver", "lodge"),
         ("eagle", "eyrie"), ("pig", "sty")],
    ),
    "kind_of": (
        "category-relation",
        "{aa} {a} is a kind of {b}",
        [("oak", "tree"), ("trout", "fish"), ("robin", "bird"),
         ("violin", "instrument"), ("rose", "flower")],
        [("sonnet", "poem"), ("schooner", "ship"), ("spaniel", "dog"),
         ("emerald", "gem"), ("bungalow", "house")],
    ),
    "part_of": (
        "part-whole-relation",
        "{aa} {a} is one part of {ab} {b}",
        [("petal", "flower"), ("page", "book"), ("spoke", "wheel"),
         ("rung", "ladder"), ("branch", "tree")],
        [("keel", "ship"), ("verse", "poem"), ("bristle", "brush"),
         ("nib", "pen"), ("hinge", "door")],
    ),
    "tool_of": (
        "function-relation",
        "{aa} {a} is a tool used by {ab} {b}",
        [("brush", "painter"), ("hammer", "carpenter"), ("needle", "tailor"),
         ("whisk", "baker"), ("spade", "gardener")],
        [("chisel", "sculptor"), ("baton", "conductor"), ("scalpel", "surgeon"),
         ("anvil", "blacksmith"), ("trowel", "bricklayer")],
    ),
    "worn_on": (
        "function-relation",
        "{ab} {b} is worn on the {a}",
        [("foot", "shoe"), ("hand", "glove"), ("head", "hat"),
         ("neck", "scarf"), ("finger", "ring")],
        [("wrist", "bracelet"), ("ear", "earring"), ("waist", "belt"),
         ("leg", "stocking"), ("shoulder", "shawl")],
    ),
    "place_of_work": (
        "function-relation",
        "{aa} {a} works in {ab} {b}",
        [("teacher", "school"), ("chef", "kitchen"), ("farmer", "field"),
         ("nurse", "hospital"), ("shopkeeper", "shop")],
        [("judge", "court"), ("librarian", "library"), ("miner", "mine"),
         ("actor", "theatre"), ("baker", "bakery")],
    ),
    "synonym": (
        "synonym-relation",
        "{b} means the same as {a}",
        [("begin", "start"), ("mend", "repair"), ("shut", "close"),
         ("quick", "rapid"), ("glad", "pleased")],
        [("brave", "courageous"), ("calm", "tranquil"), ("odd", "peculiar"),
         ("firm", "sturdy"), ("vital", "essential")],
    ),
    "greater_degree": (
        "synonym-relation",
        "{b} means extremely {a}",
        [("warm", "scorching"), ("cool", "freezing"), ("big", "enormous"),
         ("small", "tiny"), ("wet", "soaked")],
        [("damp", "sodden"), ("large", "colossal"), ("tired", "exhausted"),
         ("angry", "furious"), ("hungry", "ravenous")],
    ),
    "opposite": (
        "antonym-relation",
        "{b} is the opposite of {a}",
        [("hot", "cold"), ("fast", "slow"), ("heavy", "light"),
         ("early", "late"), ("wide", "narrow")],
        [("ancient", "modern"), ("scarce", "plentiful"), ("reluctant", "eager"),
         ("shallow", "profound"), ("humble", "arrogant")],
    ),
}

# THE SAFETY TABLE. relation -> a-word -> other b-words a pupil could defend.
#
# The keyed answer is implied and must NOT be repeated here — an entry that
# names it blocks nothing, which is the no-op trap #63 found in its own
# AMBIGUOUS list. `_build` raises on that, and on a word that appears nowhere in
# the data.
#
# Read the comment beside each entry as the argument a pupil would make. If you
# cannot write that argument, the entry is probably not needed; if you can write
# one for a pair that is NOT here, that is a defect and belongs here.
ALSO_HOLDS = {
    "young_of": {
        # Red deer young are calves, not only fawns.
        "deer": ["calf"],
    },
    "home_of": {
        # A sett IS a burrow; an eyrie IS a nest. Both keys are the precise word
        # for a general one that is equally true.
        "badger": ["burrow"],
        "eagle": ["nest"],
        # Beavers use bank burrows as well as lodges.
        "beaver": ["burrow"],
        # An eagle is a bird, so its eyrie is a bird's home too; bees nest as
        # well as hive; a holt is usually a burrow in a bank.
        "bird": ["eyrie"],
        "bee": ["nest"],
        "otter": ["burrow"],
    },
    "kind_of": {},
    "part_of": {},
    "tool_of": {
        # This relation is where the two-answer risk actually lives. A trade's
        # tool is rarely exclusive to that trade, so almost every pair here
        # needs its neighbours blocked.
        "trowel": ["gardener", "sculptor"],   # garden trowel; sculptor's trowel
        "chisel": ["carpenter", "blacksmith", "bricklayer"],
        "hammer": ["blacksmith", "sculptor", "bricklayer"],
        "brush": ["sculptor"],                # sculptors brush and finish work
        "needle": ["surgeon"],                # a surgical needle is a needle
        "spade": ["bricklayer"],
        # A metal sculptor forges on an anvil; a bricklayer's brick hammer and
        # bolster chisel are a hammer and a chisel.
        "anvil": ["sculptor"],
    },
    "worn_on": {
        # A ring is worn on the hand as well as on the finger, and a glove
        # covers the fingers as well as the hand — so each blocks the other.
        "hand": ["ring"],
        "finger": ["glove"],
        # A shawl goes round the neck; a scarf goes round the shoulders.
        "neck": ["shawl"],
        "shoulder": ["scarf"],
        # A stocking covers the foot as well as the leg.
        "foot": ["stocking"],
        # A headscarf is worn on the head; a glove covers the wrist.
        "head": ["scarf"],
        "wrist": ["glove"],
    },
    "place_of_work": {
        # A chef may work in a bakery and a baker in a kitchen.
        "chef": ["bakery"],
        "baker": ["kitchen"],
        # A school nurse works in a school.
        "nurse": ["school"],
    },
    "synonym": {},
    "greater_degree": {
        # enormous/colossal and soaked/sodden are interchangeable at this level,
        # so each pair's key is defensible for the other pair's stem word.
        "big": ["colossal"],
        "large": ["enormous"],
        "wet": ["sodden"],
        "damp": ["soaked"],
        # CROSS-RELATION: "freezing" is keyed under greater_degree but is a
        # perfectly defensible opposite of hot, and "cold" an extreme of cool.
        "cool": ["cold"],
    },
    "opposite": {
        # CROSS-RELATION, the mirror of the entry above.
        "hot": ["freezing"],
    },
}

# Words whose indefinite article the first-letter rule gets wrong ("a uniform",
# "an hour"). None are in the data today; the assertion below keeps it that way
# rather than trusting that a future pair will not add one.
_ARTICLE_TRAPS = ("uniform", "unicorn", "unit", "union", "european", "ewe",
                  "one", "once", "hour", "honest", "honour", "heir")


def _article(word):
    """"a" or "an" for `word`. Guarded by _ARTICLE_TRAPS, not trusted blindly."""
    return "an" if word[0].lower() in "aeiou" else "a"


def render(relation, a, b):
    """The relation as a sentence. Direction comes from the frame, not the caller."""
    frame = RELATIONS[relation][1]
    return frame.format(a=a, b=b, aa=_article(a), ab=_article(b))


def _build():
    """Derive the lookups, and refuse to load if the hand-written data is wrong.

    Everything below is an assertion about ALS0_HOLDS or the pairs being
    MEANINGFUL, not merely well-formed. #63's most useful self-catch was that
    almost every entry in its hand-written blocklist named a word that was
    already a member, so it blocked nothing — the list looked like a guard and
    was a comment. The same mistake is available here in two forms (naming the
    key, or naming a word that is not in the data at all) and both raise.
    """
    pairs = {}          # relation -> [(a, b, tier), ...]
    a_words, b_words = set(), set()
    keyed = {}          # a-word -> {b-word: relation}

    for rel, (qtype, frame, t1, t2) in RELATIONS.items():
        rows = [(a, b, 1) for a, b in t1] + [(a, b, 2) for a, b in t2]
        pairs[rel] = rows
        assert len(t1) == len(t2) == 5, f"{rel}: want 5 pairs per tier"
        for a, b, _tier in rows:
            assert a != b, f"{rel}: {a!r} paired with itself"
            a_words.add(a)
            b_words.add(b)
            keyed.setdefault(a, {})[b] = rel
        # The frame must actually use both slots, or the explanation silently
        # drops half the relation.
        assert "{a}" in frame and "{b}" in frame, f"{rel}: frame ignores a slot"
        assert qtype, f"{rel}: no question_type"

    for w in a_words | b_words:
        assert w.lower() not in _ARTICLE_TRAPS, (
            f"{w!r} is an a/an trap — the first-letter rule gets it wrong. "
            f"Extend render() before adding it.")

    # DEFENSIBLE — flat across relations, which is what blocks `kennel` for
    # (dog, puppy) and `freezing` for (hot, cold).
    defensible = {a: set(bs) for a, bs in keyed.items()}
    for rel, entries in ALSO_HOLDS.items():
        assert rel in RELATIONS, f"ALSO_HOLDS names unknown relation {rel!r}"
        rel_pairs = {a: b for a, b, _t in pairs[rel]}
        for a, extra in entries.items():
            assert a in rel_pairs, (
                f"ALSO_HOLDS[{rel!r}] names {a!r}, which is not an a-word of "
                f"that relation — it blocks nothing.")
            for b in extra:
                if b == rel_pairs[a]:
                    raise AssertionError(
                        f"ALSO_HOLDS[{rel!r}][{a!r}] names {b!r}, which is "
                        f"already the keyed answer. This entry blocks nothing.")
                if b not in b_words:
                    raise AssertionError(
                        f"ALSO_HOLDS[{rel!r}][{a!r}] names {b!r}, which is not "
                        f"a b-word anywhere in the data, so nothing can offer "
                        f"it and this entry blocks nothing.")
                defensible.setdefault(a, set()).add(b)

    # Every frame must render for every pair it will ever be given. A frame that
    # only reads correctly for the pairs its author happened to try is the
    # defect this whole module exists to fix.
    for rel, rows in pairs.items():
        for a, b, _t in rows:
            text = render(rel, a, b)
            assert "{" not in text, f"{rel}: unfilled slot in {text!r}"

    return pairs, dict(sorted(defensible.items())), sorted(b_words), sorted(a_words)


PAIRS, DEFENSIBLE, B_WORDS, A_WORDS = _build()

# Which b-words belong to each relation — the answer's own semantic class, and
# therefore the pool a same-class distractor is drawn from.
CLASS = {rel: [b for _a, b, _t in rows] for rel, rows in PAIRS.items()}
