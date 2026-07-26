"""
English generators: spelling, grammar & punctuation, vocabulary.

Question FORMS follow the KS2 grammar/punctuation/spelling paper and the GL 11+
verbal types researched for this — "find the word closest in meaning" (type K),
"find the word most opposite in meaning" (type U), identify the word class,
choose the correctly punctuated sentence, choose the correct spelling.

The forms are the template; every word list and sentence below is ordinary
English written for this file. Nothing is copied from a paper — KS2 materials are
reusable under OGL v3.0, but their reading booklets contain third-party content
that is not, so the safe line is to borrow structure and never content.

Reading Comprehension is deliberately absent: it needs a passage, which is a
writing job rather than a generation one.
"""
from . import Generator, Item, register, shuffled_options

# (correct spelling, plausible misspellings). The wrong forms are the errors
# pupils actually produce — doubled/undoubled consonants, -ent/-ant, -able/-ible,
# silent letters — not random letter swaps.
SPELLINGS = [
    ("necessary", ["neccessary", "necesary", "neccesary"]),
    ("separate", ["seperate", "seperete", "sepparate"]),
    ("definitely", ["definately", "definatly", "defiantly"]),
    ("occurred", ["occured", "ocurred", "occurrd"]),
    ("embarrass", ["embarass", "embarras", "emmbarrass"]),
    ("accommodate", ["accomodate", "acommodate", "accommadate"]),
    ("rhythm", ["rythm", "rhythem", "rhytham"]),
    ("beginning", ["begining", "beginnning", "begginning"]),
    ("believe", ["beleive", "belive", "beleve"]),
    ("conscience", ["concience", "conscence", "conshience"]),
    ("disappear", ["dissapear", "disapear", "dissappear"]),
    ("environment", ["enviroment", "envrionment", "enviornment"]),
    ("grateful", ["greatful", "gratefull", "gratful"]),
    ("immediately", ["immediatly", "imediately", "immediatley"]),
    ("mischievous", ["mischievious", "mischevous", "mischeivous"]),
    ("privilege", ["priviledge", "privelege", "privilage"]),
    ("recommend", ["reccomend", "recomend", "reccommend"]),
    ("rhyme", ["rhime", "ryhme", "rime"]),
    ("sincerely", ["sincerly", "sincerley", "sinserely"]),
    ("thorough", ["thourough", "thorogh", "thurough"]),
    ("vegetable", ["vegtable", "vegatable", "vegertable"]),
    ("weird", ["wierd", "weerd", "weird"]),
    ("apparent", ["apparant", "aparent", "apparrent"]),
    ("category", ["catagory", "catergory", "cathegory"]),
    ("desperate", ["desparate", "desprate", "desperete"]),
    ("existence", ["existance", "existense", "existince"]),
    ("familiar", ["familar", "fimiliar", "familliar"]),
    ("guarantee", ["garantee", "guarentee", "gaurantee"]),
    ("interrupt", ["interupt", "innterrupt", "interrupte"]),
    ("knowledge", ["knowlege", "knowledje", "nowledge"]),
]

# (word, synonyms, antonyms). Pitched at Year 5/6 comprehension vocabulary.
WORDS = [
    ("reluctant", ["unwilling", "hesitant"], ["eager", "willing"]),
    ("scarce", ["rare", "sparse"], ["plentiful", "abundant"]),
    ("ancient", ["aged", "age-old"], ["modern", "recent"]),
    ("courteous", ["polite", "civil"], ["rude", "impolite"]),
    ("conceal", ["hide", "cover"], ["reveal", "expose"]),
    ("feeble", ["weak", "frail"], ["sturdy", "powerful"]),
    ("vast", ["enormous", "immense"], ["tiny", "minute"]),
    ("permit", ["allow", "let"], ["forbid", "prohibit"]),
    ("weary", ["tired", "exhausted"], ["refreshed", "energetic"]),
    ("peculiar", ["strange", "odd"], ["ordinary", "normal"]),
    ("gather", ["collect", "assemble"], ["scatter", "disperse"]),
    ("brave", ["courageous", "fearless"], ["cowardly", "timid"]),
    ("swift", ["rapid", "speedy"], ["sluggish", "slow"]),
    ("plentiful", ["abundant", "ample"], ["scarce", "meagre"]),
    ("cautious", ["careful", "wary"], ["reckless", "rash"]),
    ("genuine", ["authentic", "real"], ["fake", "counterfeit"]),
    ("obstinate", ["stubborn", "headstrong"], ["yielding", "flexible"]),
    ("tranquil", ["calm", "peaceful"], ["turbulent", "hectic"]),
    ("diminish", ["shrink", "lessen"], ["increase", "expand"]),
    ("frequent", ["regular", "common"], ["rare", "occasional"]),
    ("hostile", ["unfriendly", "aggressive"], ["friendly", "welcoming"]),
    ("humble", ["modest", "unassuming"], ["arrogant", "boastful"]),
    ("sturdy", ["robust", "solid"], ["flimsy", "fragile"]),
    ("vacant", ["empty", "unoccupied"], ["full", "occupied"]),
]

# (sentence with a marked word, the word's class)
WORD_CLASS = [
    ("The <b>ancient</b> bridge crossed the river.", "adjective"),
    ("She <b>hurried</b> along the towpath.", "verb"),
    ("The kettle boiled <b>noisily</b>.", "adverb"),
    ("A <b>lantern</b> hung by the door.", "noun"),
    ("They waited <b>beneath</b> the arch.", "preposition"),
    ("He read the notice <b>and</b> frowned.", "conjunction"),
    ("<b>Their</b> coats were soaked through.", "pronoun"),
    ("The path grew <b>steeper</b> near the top.", "adjective"),
    ("Snow fell <b>silently</b> all night.", "adverb"),
    ("The <b>harbour</b> was empty by dusk.", "noun"),
    ("She <b>sketched</b> the outline quickly.", "verb"),
    ("The book lay <b>under</b> the bench.", "preposition"),
]
CLASSES = ["noun", "verb", "adjective", "adverb", "preposition", "conjunction", "pronoun"]

# (correctly punctuated sentence, wrong variants, what the rule is)
PUNCTUATION = [
    ("After the rain stopped, we walked to the park.",
     ["After the rain stopped we walked, to the park.",
      "After, the rain stopped we walked to the park.",
      "After the rain, stopped we walked to the park."],
     "A comma follows an introductory clause, and goes nowhere else here."),
    ("“Where have you been?” asked Mrs Patel.",
     ["“Where have you been”? asked Mrs Patel.",
      "“Where have you been?” Asked Mrs Patel.",
      "Where have you been? “asked Mrs Patel.”"],
     "The question mark belongs inside the speech marks, and the reporting clause "
     "keeps a lower-case letter."),
    ("The dog wagged its tail.",
     ["The dog wagged it's tail.", "The dog wagged its' tail.",
      "The dog wagged its's tail."],
     "“Its” shows possession; “it's” is short for “it is”."),
    ("My brother's bicycle has a puncture.",
     ["My brothers bicycle has a puncture.", "My brothers' bicycle has a puncture.",
      "My brother's' bicycle has a puncture."],
     "One brother owns it, so the apostrophe comes before the s."),
    ("The girls' changing room was locked.",
     ["The girls's changing room was locked.", "The girl's changing room were locked.",
      "The girls changing room was locked."],
     "A plural already ending in s takes the apostrophe after the s."),
    ("We packed sandwiches, apples, crisps and a flask.",
     ["We packed sandwiches apples, crisps and a flask.",
      "We packed, sandwiches, apples, crisps and a flask.",
      "We packed sandwiches, apples, crisps, and, a flask."],
     "Commas separate items in a list; the last two are joined by “and”."),
    ("Although it was late, nobody wanted to leave.",
     ["Although it was late nobody wanted to leave.",
      "Although, it was late nobody wanted to leave.",
      "Although it was, late nobody wanted to leave."],
     "A subordinate clause at the start of a sentence is followed by a comma."),
    ("You're going to need a warmer coat.",
     ["Your going to need a warmer coat.", "Youre going to need a warmer coat.",
      "You're going to need a warmer coat's."],
     "“You're” is short for “you are”; “your” shows possession."),
    ("The train was late; we missed the connection.",
     ["The train was late, we missed the connection.",
      "The train was late: we missed the connection?",
      "The train was late we missed the connection."],
     "A semicolon joins two closely related complete sentences."),
    ("Sam asked whether we were ready.",
     ["Sam asked whether we were ready?", "Sam asked, “whether we were ready.”",
      "Sam asked whether we were ready!"],
     "This reports a question rather than asking one, so it ends with a full stop."),
]


@register
class Spelling(Generator):
    slug = "eng.spelling"
    section, subtopic = "ENG", "Spelling"
    template_id = "choose-correct-spelling"

    def build(self, rng, difficulty):
        # DIFFICULTY: shorter, more familiar words first; the longer Latinate ones
        # with doubled consonants last.
        band = {1: SPELLINGS[8:14], 2: SPELLINGS[:8], 3: SPELLINGS[14:22],
                4: SPELLINGS[22:], 5: SPELLINGS[:6] + SPELLINGS[24:]}[difficulty]
        correct, wrong = rng.choice(band)
        return Item(
            stem="Which word is spelled correctly?",
            options=shuffled_options(rng, correct, list(wrong)),
            difficulty=difficulty,
            params={"word": correct},
            explanation=f"“{correct.capitalize()}” is the correct spelling.",
        )


@register
class Synonym(Generator):
    slug = "eng.synonym"
    section, subtopic = "ENG", "Vocabulary"
    template_id = "closest-in-meaning"

    def build(self, rng, difficulty):
        # DIFFICULTY: everyday words first, then the ones that only appear in
        # reading. GL type K.
        pool = WORDS[:10] if difficulty <= 2 else (WORDS[8:18] if difficulty <= 4 else WORDS[14:])
        word, syns, ants = rng.choice(pool)
        correct = rng.choice(syns)
        # Distractors include the ANTONYM, which is the standard trap: a pupil
        # skim-reading "closest" as "connected to" picks it.
        others = [w for w, s, a in WORDS if w != word]
        return Item(
            stem=f"Which word is closest in meaning to “{word}”?",
            options=shuffled_options(rng, correct, [ants[0]] + rng.sample(others, 3)),
            difficulty=difficulty,
            params={"word": word, "syn": correct},
            explanation=f"“{word.capitalize()}” means {correct}. “{ants[0].capitalize()}” "
                        f"is its opposite.",
            misconceptions={ants[0]: "picked-the-opposite-not-the-synonym"},
        )


@register
class Antonym(Generator):
    slug = "eng.antonym"
    section, subtopic = "ENG", "Vocabulary"
    template_id = "opposite-in-meaning"

    def build(self, rng, difficulty):
        # GL type U. Same trap inverted: the synonym is the tempting wrong answer.
        pool = WORDS[:10] if difficulty <= 2 else (WORDS[8:18] if difficulty <= 4 else WORDS[14:])
        word, syns, ants = rng.choice(pool)
        correct = rng.choice(ants)
        others = [w for w, s, a in WORDS if w != word]
        return Item(
            stem=f"Which word is most OPPOSITE in meaning to “{word}”?",
            options=shuffled_options(rng, correct, [syns[0]] + rng.sample(others, 3)),
            difficulty=difficulty,
            params={"word": word, "ant": correct},
            explanation=f"“{word.capitalize()}” means {syns[0]}, so its opposite is "
                        f"“{correct}”.",
            misconceptions={syns[0]: "picked-the-synonym-not-the-opposite"},
        )


@register
class WordClass(Generator):
    slug = "eng.wordclass"
    section, subtopic = "ENG", "Grammar & Punctuation"
    template_id = "identify-word-class"
    difficulties = (1, 2, 3, 4)

    def build(self, rng, difficulty):
        # DIFFICULTY: nouns and verbs are secure by Year 5; prepositions,
        # conjunctions and pronouns are where marks are lost.
        easy = [s for s in WORD_CLASS if s[1] in ("noun", "verb", "adjective")]
        hard = [s for s in WORD_CLASS if s[1] in ("adverb", "preposition",
                                                  "conjunction", "pronoun")]
        sentence, cls = rng.choice(easy if difficulty <= 2 else hard)
        return Item(
            stem=(f"What word class is the word in bold?<br>{sentence}"),
            options=shuffled_options(rng, cls,
                                     rng.sample([c for c in CLASSES if c != cls], 3)),
            difficulty=difficulty,
            params={"sentence": sentence, "cls": cls},
            explanation=f"The bold word is a {cls}.",
        )


@register
class Punctuation(Generator):
    slug = "eng.punctuation"
    section, subtopic = "ENG", "Grammar & Punctuation"
    template_id = "correct-punctuation"

    def build(self, rng, difficulty):
        # DIFFICULTY: commas and apostrophes first, then speech punctuation and
        # semicolons.
        band = {1: PUNCTUATION[:3], 2: PUNCTUATION[2:6], 3: PUNCTUATION[3:7],
                4: PUNCTUATION[6:9], 5: PUNCTUATION[7:]}[difficulty]
        correct, wrong, rule = rng.choice(band)
        return Item(
            stem="Which sentence is punctuated correctly?",
            options=shuffled_options(rng, correct, list(wrong)),
            difficulty=difficulty,
            params={"sentence": correct},
            explanation=rule,
        )
