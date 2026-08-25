"""
English generators, across the Spelling, Grammar, Punctuation and Vocabulary
topics of elevenplus_data/taxonomy.json.

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
    section, subtopic = "ENG", "Misspelling Spotting"
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
    section, subtopic = "ENG", "Synonyms"
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
    section, subtopic = "ENG", "Antonyms"
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
    section, subtopic = "ENG", "Word Classes"
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
    section, subtopic = "ENG", "Apostrophes"
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


# ---------------------------------------------------------------------------
# Combinatorial English
#
# Everything above this line is a list lookup: one data entry yields exactly one
# question, which capped the whole module at 148 while Maths reached 11,000. The
# generators below build a sentence from FRAMES and WORD POOLS instead, so the
# parameter space is the product of the two rather than the length of a list.
# ---------------------------------------------------------------------------

NOUNS = ["lantern", "harbour", "cottage", "meadow", "kettle", "satchel", "orchard",
         "bridge", "cellar", "hedgerow", "barrow", "chimney", "gatepost", "quarry",
         "thicket", "windmill", "pantry", "stable", "brook", "cobbles"]
ADJECTIVES = ["ancient", "narrow", "brittle", "gleaming", "weathered", "crooked",
              "silent", "damp", "sturdy", "faded", "restless", "hollow"]
VERBS_PAST = ["creaked", "shivered", "glimmered", "rattled", "settled", "drifted",
              "tumbled", "echoed", "faltered", "swayed"]
ADVERBS = ["quietly", "suddenly", "carefully", "faintly", "steadily", "briskly",
           "reluctantly", "neatly"]
PREPOSITIONS = ["beneath", "beyond", "across", "beside", "towards", "underneath"]
CONJUNCTIONS = ["and", "but", "because", "although", "while"]
PRONOUNS = ["their", "his", "her", "our", "its"]
NAMES = ["Ivy", "Amir", "Priya", "Tomas", "Nia", "Ellis", "Rosa", "Kofi", "Maeve", "Jun"]
PLACES = ["park", "market", "station", "library", "harbour", "allotment", "museum"]

CLASS_POOLS = {"noun": NOUNS, "adjective": ADJECTIVES, "verb": VERBS_PAST,
               "adverb": ADVERBS, "preposition": PREPOSITIONS,
               "conjunction": CONJUNCTIONS, "pronoun": PRONOUNS}

# Coherent (subject, verb, adverb, preposition, place) sets. The word-class
# question does not depend on the sentence MEANING anything, but a pupil reading
# "the restless cottage faltered carefully beneath the harbour" reasonably
# concludes the material is nonsense — so the parts are chosen to go together.
SCENES = [
    ("gate", "creaked", "quietly", "beside", "lane"),
    ("kettle", "whistled", "suddenly", "on", "stove"),
    ("floorboard", "groaned", "faintly", "beneath", "carpet"),
    ("curtain", "shifted", "slightly", "across", "window"),
    ("lantern", "flickered", "briefly", "above", "doorway"),
    ("branch", "swayed", "steadily", "over", "path"),
    ("clock", "ticked", "loudly", "in", "hallway"),
    ("river", "glittered", "faintly", "below", "bridge"),
    ("door", "slammed", "abruptly", "behind", "visitor"),
    ("candle", "guttered", "briefly", "near", "window"),
    ("wind", "howled", "fiercely", "around", "chimney"),
    ("cart", "rumbled", "slowly", "along", "cobbles"),
    ("owl", "called", "twice", "from", "orchard"),
    ("rain", "drummed", "steadily", "against", "windowpane"),
    ("fire", "crackled", "softly", "in", "grate"),
    ("bell", "rang", "sharply", "across", "courtyard"),
    ("boat", "drifted", "gently", "towards", "jetty"),
    ("shutter", "banged", "repeatedly", "against", "wall"),
]
# Adjectives that sit sensibly in front of any of the nouns above.
NEUTRAL_ADJECTIVES = ["old", "heavy", "narrow", "wooden", "distant", "small",
                      "faded", "silent", "damp", "crooked", "battered", "rusty"]
# Things a person would actually pack, for the list-punctuation question.
PACKABLE = ["map", "flask", "compass", "notebook", "torch", "blanket", "whistle",
            "pencil case", "spare jumper", "packet of biscuits"]


@register
class WordClassBuilt(Generator):
    slug = "eng.wordclass2"
    section, subtopic = "ENG", "Word Classes"
    template_id = "word-class-built"

    def build(self, rng, difficulty):
        # DIFFICULTY: which class is being asked about. Nouns and verbs are secure
        # by Year 5; prepositions, conjunctions and pronouns are where marks go.
        target = {1: "noun", 2: "verb", 3: "adjective", 4: "adverb",
                  5: rng.choice(["preposition", "conjunction", "pronoun"])}[difficulty]
        # Drawn from a coherent SCENE rather than free-mixing the pools. Mixing
        # produced grammatical nonsense — "the restless cottage faltered carefully
        # beneath the harbour" — which is technically answerable but reads as junk
        # content, and anyone skim-reading a sample would judge the bank on it.
        noun, verb, adv, prep, place = rng.choice(SCENES)
        adj = rng.choice(NEUTRAL_ADJECTIVES)
        word = {"noun": noun, "adjective": adj, "verb": verb, "adverb": adv,
                "preposition": prep, "conjunction": rng.choice(CONJUNCTIONS),
                "pronoun": rng.choice(PRONOUNS)}[target]

        def mark(w):
            return f"<b>{w}</b>" if w == word else w

        if target == "conjunction":
            sentence = (f"The {mark(adj)} {mark(noun)} {mark(verb)} {mark(adv)}, "
                        f"{mark(word)} nobody noticed.")
        elif target == "pronoun":
            sentence = (f"{mark(word).capitalize()} {mark(adj)} {mark(noun)} "
                        f"{mark(verb)} {mark(adv)}.")
        else:
            sentence = (f"The {mark(adj)} {mark(noun)} {mark(verb)} {mark(adv)} "
                        f"{mark(prep)} the {place}.")
        return Item(
            stem=f"What word class is the word in bold?<br>{sentence}",
            options=shuffled_options(
                rng, target, rng.sample([c for c in CLASS_POOLS if c != target], 3)),
            difficulty=difficulty,
            params={"w": word, "t": target, "s": sentence},
            explanation=f"“{word.capitalize()}” is a {target} here.",
        )


@register
class PunctuationBuilt(Generator):
    slug = "eng.punctuation2"
    section, subtopic = "ENG", "Commas"
    template_id = "punctuation-built"

    def build(self, rng, difficulty):
        # DIFFICULTY: introductory commas and lists first, then speech, then
        # possessive apostrophes, then semicolons.
        name, name2 = rng.sample(NAMES, 2)
        place, noun = rng.choice(PLACES), rng.choice(NOUNS)
        if difficulty == 1:
            right = f"After the rain stopped, {name} walked to the {place}."
            wrong = [f"After the rain stopped {name} walked, to the {place}.",
                     f"After, the rain stopped {name} walked to the {place}.",
                     f"After the rain, stopped {name} walked to the {place}."]
            rule = "A comma follows the introductory clause, and goes nowhere else."
        elif difficulty == 2:
            a, b, cc = rng.sample(PACKABLE, 3)
            right = f"{name} packed a {a}, a {b}, some apples and a {cc}."
            wrong = [f"{name} packed a {a} a {b}, some apples and a {cc}.",
                     f"{name}, packed a {a}, a {b}, some apples and a {cc}.",
                     f"{name} packed a {a}, a {b}, some apples, and, a {cc}."]
            rule = "Commas separate items in a list; the last two are joined by “and”."
        elif difficulty == 3:
            right = f"“Where is the {noun}?” asked {name}."
            wrong = [f"“Where is the {noun}”? asked {name}.",
                     f"“Where is the {noun}?” Asked {name}.",
                     f"Where is the {noun}? “asked {name}.”"]
            rule = ("The question mark sits inside the speech marks and the "
                    "reporting clause stays lower-case.")
        elif difficulty == 4:
            right = f"{name}'s {noun} was left at the {place}."
            wrong = [f"{name}s {noun} was left at the {place}.",
                     f"{name}s' {noun} was left at the {place}.",
                     f"{name}'s' {noun} was left at the {place}."]
            rule = f"One person owns it, so the apostrophe comes before the s."
        else:
            right = f"{name} missed the bus; {name2} waited at the {place}."
            wrong = [f"{name} missed the bus, {name2} waited at the {place}.",
                     f"{name} missed the bus: {name2} waited at the {place}?",
                     f"{name} missed the bus {name2} waited at the {place}."]
            rule = "A semicolon joins two closely related complete sentences."
        return Item(
            stem="Which sentence is punctuated correctly?",
            options=shuffled_options(rng, right, wrong),
            difficulty=difficulty,
            params={"r": right},
            explanation=rule,
        )


# (correct word, the others it is confused with, a frame with a {} for the word)
HOMOPHONES = [
    ("their", ["there", "they're"], "The children collected {} coats from the hall."),
    ("there", ["their", "they're"], "We left the basket over {} by the gate."),
    ("they're", ["their", "there"], "I think {} waiting outside for us."),
    ("your", ["you're"], "Have you finished {} homework yet?"),
    ("you're", ["your"], "I hope {} coming to the fair on Saturday."),
    ("its", ["it's"], "The fox lifted {} head and listened."),
    ("it's", ["its"], "I think {} going to rain before evening."),
    ("whose", ["who's"], "Does anybody know {} bicycle this is?"),
    ("who's", ["whose"], "Ask {} coming with us tomorrow."),
    ("too", ["to", "two"], "The bag was far {} heavy to carry."),
    ("to", ["too", "two"], "We walked {} the end of the lane."),
    ("two", ["to", "too"], "There were only {} apples left in the bowl."),
    ("passed", ["past"], "We {} the old windmill on the way home."),
    ("past", ["passed"], "The bus went straight {} without stopping."),
    ("practise", ["practice"], "You should {} the piece again before Friday."),
    ("practice", ["practise"], "Choir {} is on Thursday evening."),
    ("affect", ["effect"], "The rain did not {} the match at all."),
    ("effect", ["affect"], "The medicine had an immediate {}."),
    ("accept", ["except"], "She was happy to {} the invitation."),
    ("except", ["accept"], "Everyone came {} for Amir."),
    ("were", ["where", "we're"], "They {} already halfway up the hill."),
    ("where", ["were", "we're"], "Do you remember {} we left the map?"),
    ("we're", ["were", "where"], "I think {} going to be late."),
    ("quiet", ["quite"], "The house was very {} after they left."),
    ("quite", ["quiet"], "It was {} the loveliest garden in the village."),
]


@register
class Homophone(Generator):
    slug = "eng.homophone"
    section, subtopic = "ENG", "Homophones"
    template_id = "choose-homophone"

    def build(self, rng, difficulty):
        # DIFFICULTY: their/there and to/too first; affect/effect and
        # practise/practice last, because those are rule-based rather than aural.
        band = {1: HOMOPHONES[:6], 2: HOMOPHONES[3:12], 3: HOMOPHONES[9:18],
                4: HOMOPHONES[12:22], 5: HOMOPHONES[14:]}[difficulty]
        correct, others, frame = rng.choice(band)
        # A second, unrelated confusable keeps the options at four without
        # repeating the same pair every time.
        extra = [w for w, o, f in HOMOPHONES if w != correct and w not in others]
        return Item(
            stem=f"Which word correctly completes the sentence?<br>"
                 f"{frame.format('______')}",
            options=shuffled_options(rng, correct, others + rng.sample(extra, 2)),
            difficulty=difficulty,
            params={"w": correct, "f": frame},
            explanation=f"The sentence reads “{frame.format(correct)}”",
        )


# (singular, plural, the rule it demonstrates)
PLURALS = [
    ("box", "boxes", "add -es after x"), ("church", "churches", "add -es after ch"),
    ("bush", "bushes", "add -es after sh"), ("glass", "glasses", "add -es after ss"),
    ("baby", "babies", "consonant + y becomes -ies"),
    ("city", "cities", "consonant + y becomes -ies"),
    ("story", "stories", "consonant + y becomes -ies"),
    ("donkey", "donkeys", "vowel + y just takes -s"),
    ("valley", "valleys", "vowel + y just takes -s"),
    ("leaf", "leaves", "-f becomes -ves"), ("thief", "thieves", "-f becomes -ves"),
    ("shelf", "shelves", "-lf becomes -lves"), ("wolf", "wolves", "-lf becomes -lves"),
    ("knife", "knives", "-fe becomes -ves"), ("life", "lives", "-fe becomes -ves"),
    ("potato", "potatoes", "-o takes -es"), ("hero", "heroes", "-o takes -es"),
    ("piano", "pianos", "musical -o words just take -s"),
    ("child", "children", "irregular"), ("tooth", "teeth", "irregular"),
    ("foot", "feet", "irregular"), ("mouse", "mice", "irregular"),
    ("goose", "geese", "irregular"), ("person", "people", "irregular"),
    ("sheep", "sheep", "unchanged"), ("deer", "deer", "unchanged"),
    ("aircraft", "aircraft", "unchanged"), ("cactus", "cacti", "Latin plural"),
    ("radius", "radii", "Latin plural"), ("crisis", "crises", "Greek plural"),
]


@register
class Plural(Generator):
    slug = "eng.plural"
    section, subtopic = "ENG", "Plurals"
    template_id = "form-the-plural"

    def build(self, rng, difficulty):
        # DIFFICULTY: regular -es first, then y/f changes, then irregulars and
        # unchanged plurals, then the Latin and Greek forms.
        band = {1: PLURALS[:4], 2: PLURALS[4:9], 3: PLURALS[9:18],
                4: PLURALS[18:27], 5: PLURALS[24:]}[difficulty]
        single, plural, rule = rng.choice(band)
        # Wrong forms are the over-generalisations pupils actually write.
        wrong = [single + "s", single + "es"]
        if single.endswith("y"):
            wrong.append(single[:-1] + "ies" if plural.endswith("s") else single + "s")
        if single.endswith(("f", "fe")):
            wrong.append(single.rstrip("e")[:-1] + "ves")
        wrong += [plural + "s", single]
        return Item(
            stem=f"What is the plural of “{single}”?",
            options=shuffled_options(rng, plural, [w for w in wrong if w != plural]),
            difficulty=difficulty,
            params={"s": single},
            explanation=f"“{single.capitalize()}” becomes “{plural}” — {rule}.",
        )
