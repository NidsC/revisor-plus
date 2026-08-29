# Question Quality — defects found building English packs 01–05

This is a field guide for anyone authoring 11+ question packs. Every defect below is
one we actually shipped, or nearly shipped, while building the five English comprehension
packs (`contrib_pk_eng_01`…`05`). For each: what it is, a real example from our packs,
why it hurts the pupil, and **who catches it** — the automated checkers or a human reading
the questions.

This document is about *quality*. The **contract** (what imports at all) lives in
[`elevenplus_data/CLAUDE.md`](elevenplus_data/CLAUDE.md); read that first. Two tools guard
quality:

- **`validate_questions.py`** — the import gate. Runs in CI. Refuses a pack that breaks the
  contract (bad section, reserved/duplicate `source`, missing required fields, no correct
  option, a distractor equal in value to the key, duplicate refs, unknown subtopic/type).
- **`audit_packs.py`** — a quality lens, run by the author. Its checks are numbered `[1]`–`[7]`
  and referenced throughout below.

> **The single most important thing on this page:** *a green checker does not mean a good
> question.* Most of the defects that matter most — a mislabelled skill, an implausible
> distractor, a stem that hands you the answer in different words, a passage nobody should
> reuse — are invisible to both tools. **They need a human to read the questions.** The
> automated checks exist to catch the mechanical mistakes so the human can spend attention
> on the ones that require judgement.

**Legend for "Caught by":**

| Symbol | Meaning |
|--------|---------|
| 🟢 **Audit `[N]`** | `audit_packs.py` catches it automatically (check number given) |
| 🟢 **Validator** | `validate_questions.py` (the import gate / CI) catches it |
| 🟡 **Tripwire** | a *lexical* heuristic — catches the obvious cases, misses cleverly-worded ones |
| 🔴 **Human** | no checker will ever catch it; someone must read the questions |

---

## ANSWER KEYS

A pupil who spots a pattern in *where the correct answer sits* stops reading the questions
and starts reading the key. Every defect here makes the paper gameable.

### Clustering
**All the keys land on the same letter.** Not a slip — a systemic behaviour of whatever
generates the options.
- *Example:* pack 01, first draft — **all 25 keys were option A.** The builder placed the
  correct answer first every time, so it clustered by construction.
- *Why it matters:* a child who notices "it's always A" scores full marks without reading a
  word. It also makes every question effectively easier than its band claims.
- *Caught by:* 🟢 **Audit `[1]`** — flags an unbalanced answer-letter distribution.

### Cyclic patterns
**"Fixing" the clustering by forcing exactly five of each letter can create a repeating
cycle.** Even distribution is not the goal; *unpredictability* is.
- *Example:* pack 02, after balancing "5 of each" by construction — the keys ran
  `A,C,E,B,D,A,C,E,B,D…`, a period-5 cycle. Perfectly balanced, perfectly predictable.
- *Why it matters:* a test-wise pupil learns the cycle and predicts the next answer. A
  balanced count hid a worse pattern than the clustering it replaced.
- *Caught by:* 🟢 **Audit `[1]`** — detects periodic runs, not just counts. The fix is to
  *randomise* key positions and then verify, never to construct a balanced sequence.

### Same-letter runs
**A short streak of identical keys** — a period-1 pattern that count-and-cycle checks miss.
- *Example:* pack 04, a randomisation draft — keys `…D **B B B B** E…`, four B's in a row at
  Q4–Q7.
- *Why it matters:* a run of four is a visible tell; a pupil unsure of Q6 sees B,B on either
  side and guesses B.
- *Caught by:* 🟢 **Audit `[1]`** — reports the longest same-letter run. Re-randomise until
  no run exceeds 2.

> **How keys should be set:** draw each key position at random, then *verify* the whole
> sequence has no clustering, no cycle, and no run > 2. Balancing to "5 each" up front is the
> trap that produced the cycle above.

---

## STEM DEFECTS

### Answer in the stem
**The stem states, defines, or all-but-says its own answer.**
- *Examples:*
  - Pack 01, original Q6: *"'Spring was moving in the air'… what season is it?"* — the stem
    names the season it asks for.
  - A figurative question: *"…a comparison made **without using 'like' or 'as'** — what device
    is this?"* — "without like or as" **is** the definition of a metaphor.
- *Why it matters:* it tests reading the stem, not the passage or the skill. A pupil who
  knows nothing scores it.
- *Caught by:* 🟢 **Audit `[4]`** for the mechanical subclasses — a key repeated verbatim in
  the stem, and *device-definition give-aways* (it knows the defining phrases of simile,
  metaphor, personification, alliteration, onomatopoeia, hyperbole). 🔴 **Human** for the
  general case: "Spring was moving… what season" is only *implied*, and no checker spots that
  the answer is inferable from a stem word.

### Cross-question leaks
**One question's stem or options give away a different question's answer.**
- *Example:* pack 01 — Q15's stem quoted *"the carol of happy birds fell on his dulled hearing
  almost like a shout"*, which was exactly the answer to Q4 (*"what fell on his dulled
  hearing?"*). Answer Q15 and you've been handed Q4.
- *Why it matters:* the pupil who reads in order is rewarded for nothing; the ordering of the
  paper changes the score.
- *Caught by:* 🟡 **Audit `[3]`** *only* when both questions quote the same phrase (then it
  reads as phrase reuse). 🔴 **Human** in general — a stem that reveals another answer *in
  different words* slips straight through.

### Phrase reuse in options (including substrings)
**The same quoted phrase appears in two questions** — often as a shorter quote inside a
longer one.
- *Example:* pack 03 — Q7 quoted *"…a tuft of snow piled on his **broad shoulders**"* as a
  distractor, and Q16 offered *"**broad shoulders**"* as an alliteration option. The shorter
  is a substring of the longer.
- *Why it matters:* seeing the same fragment twice nudges the pupil, and it wastes the
  passage — 25 questions should touch 25 different places in the text.
- *Caught by:* 🟢 **Audit `[3]`** — compares quoted phrases across **stems and options**, and
  flags substring overlaps, not just identical strings.

### Phantom quotes
**An option or stem quotes text that isn't in the printed extract** — usually a phrase from
elsewhere in the book, pulled from memory.
- *Example:* pack 02 — Q16's alliteration options included *"the brown old seaman"*, which is
  from **line 152 of Treasure Island, before our extract begins**. A pupil looking for it in
  the passage never finds it. (Pack 01 had the cousin defect: Q24 quoted *"a spirit of divine
  discontent"* when the text reads *"**its** spirit…"* — a misquote of text that *is* present.
  Fixed in the pack now shipping; kept here as the worked example of the defect.)
- *Why it matters:* the question is unanswerable from what the child is shown, or trains them
  to accept a misremembered wording.
- *Caught by:* 🟢 **Audit `[3b]`** — checks every quoted phrase actually occurs in the
  passage, including one containing a contraction or possessive (`man's`, `What's`) — an
  earlier version of the check missed those; fixed once a real pack tripped it. Only runs on a
  pack that has a printed passage at all, so it says nothing about a spelling or vocabulary
  pack's example sentences.

### Implausible distractors
**Four obviously-wrong options and one real answer is not a question** — it's a formality.
- *Example:* the first-draft word-class questions asked *"which word is a verb?"* with the
  target word's class obvious from context and the wrong options nowhere near credible.
  Contrast the fix — *"what type of word is 'cut' in line 4?"* with **noun / verb / adjective**
  all genuinely arguable until you check how it's used.
- *Why it matters:* a distractor must be a mistake a real pupil actually makes. If it isn't,
  the "hard" question is a giveaway and tells you nothing about the child.
- *Caught by:* 🔴 **Human.** No tool can judge whether a wrong answer is tempting. This is the
  single most important thing a reviewer does.

---

## PASSAGE INTEGRITY

### Answers relying on cut text
**Trimming the passage removes the very words a question needed.**
- *Example:* pack 01 — when the Alice extract was trimmed to length, a question about the
  marmalade jar lost the clause its answer depended on; the answer was no longer supported by
  the printed text.
- *Why it matters:* the question becomes unanswerable, or answerable only by a child who has
  read the whole book.
- *Caught by:* 🟡 **Audit `[3b]`** *if* the answer quotes the cut phrase (it becomes a phantom
  quote). 🔴 **Human** when the dependency is semantic rather than a quotation. **Author the
  questions against the final trimmed passage, never the full text.**

### Broken dialogue
**Cutting a line of a conversation leaves the remaining turns talking to nothing.**
- *Example:* pack 05 — excluding Scrooge's "boiled with his own pudding" line also swallowed
  the blank line after it, which merged and then deleted the nephew's *"Uncle!"* plea. Result:
  Scrooge spoke twice in a row and the reply *"Nephew!"* answered no one.
- *Why it matters:* the passage no longer makes sense; comprehension questions about "who says
  what" become unanswerable, and the pupil loses trust in the text.
- *Caught by:* 🔴 **Human.** Nothing checks that dialogue alternates. After any trim, read the
  passage aloud.

### Length
**Too short and 25 questions pile onto the same three sentences; too long and it won't fit
the page.**
- *Example:* our first English conversion sat at ~470 words — every question kept returning to
  the same handful of lines. Re-cutting to **600–700 words** gave 25 questions room to touch
  different places.
- *Why it matters:* a cramped passage produces repetitive questions and forces phrase reuse;
  it also stops resembling a real paper, where the text carries a full spread of retrieval,
  inference and vocabulary.
- *Caught by:* 🔴 **Human.** Target **600–700 words**. (A word count is trivial to eyeball; no
  tool enforces it.)

### Over-used passages
**A passage that appears in every prep book — and in this repo's own example packs —
teaches nothing new and risks colliding with content the pupil has already drilled.**
- *Example:* *Alice's Adventures in Wonderland* is used by `_EXAMPLE.shared_passage.json` and
  `_EXAMPLE.answer_kinds.json`; *A Little Princess* opens half the comprehension anthologies on
  the market. Our early drafts leant on both.
- *Why it matters:* a child who has seen the passage answers from memory; and duplicating the
  repo's own examples makes packs look interchangeable.
- *Caught by:* 🟡 **Validator** catches the mechanical symptom — it warns on a **duplicate stem
  across packs**, which fires if you reuse the example packs' questions. 🔴 **Human** for the
  judgement "this passage is a cliché." Prefer a fresh, self-contained extract from a
  pre-1928 public-domain work, and vary the author and period across packs.

---

## TAXONOMY ACCURACY

### Mislabelled skills
**A question filed under the wrong subtopic or `question_type`.**
- *Example:* early drafts tagged plain retrieval ("what did X do?") as `inference`. The label
  passed the validator because `inference` is a real type — it was just the wrong one.
- *Why it matters:* the whole point of the taxonomy is the **weakness report**. If retrieval
  questions are counted as inference, a child weak at inference looks fine, and a child weak at
  retrieval is told to practise the wrong thing. The mislabel silently corrupts diagnostics.
- *Caught by:* 🔴 **Human.** 🟢 The **Validator** checks the label is a *valid* subtopic/type,
  never that it is the *correct* one for this question.

### Difficulty pitch
**A question banded honestly on paper but pitched at the wrong level in reality.**
- *Example:* the original word-class questions were **Year 3 standard** — "which word is a
  verb?" with the answer obvious. Real GL asks about words whose class is genuinely ambiguous:
  an `-ing` word acting as an adjective, a past participle as an adjective, a noun used as a
  verb. The rewrite cites words by line and offers credible competing classes, and is honestly
  band 3–4.
- *Why it matters:* a paper of secretly-easy questions flatters every pupil and discriminates
  between none of them — it can't tell a strong child from a weak one.
- *Caught by:* 🔴 **Human.** No tool judges whether a single question's difficulty label is
  honest; `[2]` only checks the *spread* against a target.

### Bottom-heavy difficulty
**A pack with nothing hard in it.**
- *Example:* pack 01, as first built — nothing above band 3. The **targeted-paper feature**,
  which serves band 4–5 questions to a pupil above ~75% accuracy, had *nothing to reach for*.
- *Why it matters:* strong pupils are never stretched; the bank can't produce a hard paper.
- *Caught by:* 🟢 **Audit `[2]`** — compares the difficulty spread to a target (we settled on
  **3 / 12 / 8 / 2** across bands 1–2 / 3 / 4 / 5) and flags a mismatch; an earlier form warned
  outright when a pack had no band-4/5 questions. **Note:** it checks the *shape*, not whether
  each label is honest — see "Difficulty pitch" above.

---

## CROSS-PACK REPETITION

These only appear when you look at several packs together. A pupil working through a whole
prep book meets them; a single-pack review never does.

### Identical question skeletons
**Every pack has the same `question_type` at the same difficulty in the same slot.**
- *Example:* packs 02–04 were all built from one template, so Q14 was *always* the simile, Q16
  *always* the alliteration example, Q19 *always* "which word is the verb". A child doing three
  papers learns the paper's shape, not the skills.
- *Why it matters:* the pupil predicts what Q19 will be before reading it, and drills the
  format instead of the reading.
- *Caught by:* 🟢 **Audit `[6]`** — flags when two packs share the same ordered
  `(question_type, difficulty)` sequence. Shuffle each pack to a *different* order.

### Repeated answer concepts
**Three or more questions in a pack that all key on the same idea.**
- *Example:* pack 05 — **five** questions (including *both* band-5s) all keyed on "the nephew's
  warmth versus Scrooge's coldness". Pack 03 had a version of it (the ouzel's "joyful" keyed
  three answers); pack 02 another (the captain's "danger"/"unease").
- *Why it matters:* the pupil learns one idea answers half the paper. It also wastes the
  passage — a rich text reduced to a single observation repeated.
- *Caught by:* 🟡 **Audit `[7]` — a lexical tripwire, not a guarantee.** It flags a distinctive
  *word* that appears in the keys of 3+ questions (after excluding generic words and the
  passage's own subject/proper-noun words). **It catches repeated key*words*, not repeated
  key*concepts*.** Two answers that share an idea phrased in *different words* — "cheerful
  nephew" in one key, "the nephew's sunny good humour" in another — sail straight past it. So a
  green `[7]` means *no blatant lexical repeat*, not *no repeated concept*. 🔴 **Human** is the
  real defence; `[7]` just stops you shipping the obvious ones.

---

## MECHANICAL

Contract-level mistakes. These the tools *do* catch — but two of them are dangerous enough to
understand rather than rely on.

### Ref scheme
**Content-derived refs collide between authors by construction.**
- *Example:* pack `pk` and another author's pack `pr` both numbered their questions
  `EN-LITERAL_RETRIEVAL-001`, `EN-INFERENCE-001`, … Every ref collided the moment both packs
  were validated together.
- *Why it matters:* refs must be unique across the whole bank (they're used for dedup). A
  content-derived scheme guarantees collisions the moment two people author the same section.
- *Caught by:* 🟢 **Validator** — the cross-pack ref check fails the build. **The fix is
  structural:** use **handle-scoped** refs, `PK-ENG-0001`, `PK-ENG-0002`, … — unique per
  author by design.

### Source tags
**Reusing a `source` for a section silently deletes the previous author's pack on import.**
- *Why it matters:* `import_pack` deletes every question with the same `(section, source)`
  before importing, and deleting a question cascades into every pupil `Attempt` against it.
  Reusing another author's `source` **erases their questions and the pupils' history** — with
  no error.
- *Caught by:* 🟢 **Validator** — flags a duplicate `source` across packs, *when it is given
  several packs at once* (which is why CI runs it over the whole folder). Use a `source` unique
  to your batch, e.g. `CONTRIB-PK-01`; never `seed`.

---

## COMPOSITION

The defect no checker will ever flag, because it isn't visible in any single pack.

### A comprehension-only bank
**A real GL English paper is roughly 45% reading comprehension. The rest is spelling
error-spotting, punctuation error-spotting, and cloze.** Our five packs are **100%
comprehension.**
- *Why it matters:* a child who drills only our bank meets none of the spelling, punctuation
  or cloze sections that make up more than half of the real exam, and arrives unprepared for
  most of the paper.
- *Caught by:* 🔴 **Human — strategic.** No per-pack checker can see the shape of the *whole
  bank*. The contract already supports the needed kinds — `error_span` (spot-the-error),
  `select_word`, `cloze_gap` — see [`elevenplus_data/CLAUDE.md`](elevenplus_data/CLAUDE.md).
  Someone has to decide to *author* them. Track section balance at the bank level, not the pack
  level.

---

## What the automation can and cannot do — in one place

| Defect | Caught by |
|--------|-----------|
| Key clustering / cycles / runs | 🟢 Audit `[1]` |
| Difficulty spread wrong shape | 🟢 Audit `[2]` |
| Phrase reuse across questions (incl. substrings) | 🟢 Audit `[3]` |
| Quoted phrase not in the extract | 🟢 Audit `[3b]` (ENG comprehension packs only — needs a `passages` block) |
| Answer verbatim in stem / device-definition give-away | 🟢 Audit `[4]` (ENG only) |
| Banned stem templates / repeated stem openings | 🟢 Audit `[5]` |
| Identical question skeleton across packs | 🟢 Audit `[6]` |
| Repeated key**word** across 3+ answers | 🟡 Audit `[7]` (tripwire, ENG only) |
| Bad section / source / refs / required fields | 🟢 Validator |
| **Answer implied (not stated) in stem** | 🔴 Human |
| **Cross-question answer leak in different words** | 🔴 Human |
| **Implausible distractors** | 🔴 Human |
| **Answer depends on cut text (semantic)** | 🔴 Human |
| **Broken / non-alternating dialogue** | 🔴 Human |
| **Passage too short / too long / clichéd** | 🔴 Human |
| **Mislabelled skill (valid but wrong type)** | 🔴 Human |
| **Dishonest difficulty label** | 🔴 Human |
| **Repeated answer *concept* in different words** | 🔴 Human |
| **Bank is 100% comprehension** | 🔴 Human (strategic) |

The pattern: **the automation catches mechanics; the human catches meaning.** Run both tools,
then read every question as a pupil would.

---

## Reviewing an existing pack

Everything above is written for someone *authoring* a pack — the template at the end of this
document folds all of it into one prompt for a fresh batch. This section is the other half:
what to do when a pack is already written (yours, a collaborator's, or one nobody has looked
at since it merged) and the question is simply *is it any good*.

**First, run the tools — they're free and they're not what this checklist is for.**

```bash
python3 elevenplus_data/validate_questions.py elevenplus_data/*.json
python3 audit_packs.py <the pack> --baseline <every other pack already merged>
```

Fix whatever they flag before reading a single question by eye — there is no point spending
human attention on a mechanical fault a script would have caught for free. What's below is
**only the rows neither tool can touch** — every 🔴 Human and 🟡 tripwire row from the table
above, turned into a question to actually ask while reading. Answer each one against the real
passage and the real options, not from memory of what the pack is supposed to contain.

1. **Answer implied in the stem.** For each question: could a pupil who has never read the
   passage answer this from the stem's own wording alone? (Not "does the stem repeat the key
   verbatim" — the audit already checked that. This is the softer case: a stem word that makes
   the answer guessable without the passage.)
2. **Cross-question leaks.** Does any question's stem or option — in different words, not a
   shared quoted phrase — give away another question's answer?
3. **Implausible distractors.** For every wrong option: is this a mistake a real pupil
   actually makes, or is it obviously silly? A "hard" question with four absurd options is a
   giveaway wearing five choices.
4. **Cut-text dependency.** If the passage was trimmed from a longer source, does any
   question's answer depend on something that isn't in the printed extract?
5. **Broken dialogue.** If the passage contains dialogue, read it aloud. Does every character's
   line make sense as a reply to the one before it? A cut line can leave a reply answering no
   one.
6. **Passage shape.** Is it roughly 600–700 words? Is it a fresh extract, not one already used
   by this repo's own `_EXAMPLE` packs or another contributor pack (the validator's duplicate-
   stem check across packs is the closest mechanical proxy, but "this text is a cliché" is a
   judgement call it can't make)?
7. **Mislabelled skill.** For each question: is the `question_type` the *right* one, not merely
   a *valid* one for its `subtopic`? A retrieval question tagged `inference` passes every
   automated check and still corrupts the weakness report.
8. **Dishonest difficulty.** For each question: is the `difficulty` label honest for a Year 5/6
   pupil sitting the exam, or is a `3` actually `1`-easy (or a `4` actually a `2`)? The audit
   only checks the *shape* of the spread against a target, never whether one label is true.
9. **Repeated answer concept.** Read all the correct answers together, in order, ignoring the
   questions. Do three or more converge on the same idea in different words? (`[7]` only
   catches a shared *word* — "warm nephew, sunny good humour, cheerful disposition" all pass it
   and are still one idea repeated three times.)
10. **Bank composition** (pack-set level, not per-pack). Across the packs that ship together,
    is the mix of question kinds roughly what a real paper has, or is everything one kind? This
    was a real gap as of the packs 01–05 build (100% comprehension against a real paper's ~45%)
    and is closed as of packs 06–16 (spelling, punctuation, cloze, vocabulary, poetry, grammar
    now shipping) — worth re-checking whenever a new batch of packs merges, since nothing
    mechanical tracks the bank's shape over time.

**Worked example — `contrib_pk_eng_14.json`, reviewed 2026-08-29.** Chosen because it had never
been through `audit_packs.py` (added after the tool, never audited) or this checklist. Both
tools clean (`validate_questions.py` exit 0, `audit_packs.py` 0 errors/0 warnings once run
against the full batch). Recorded here as the checklist's first real pass, findings and all —
not a template nobody has used.

- **Items 1, 3, 4, 5, 7, 8, 9 — clean.** No stem answers itself without the passage; every
  distractor is a plausible near-miss (the "1966"/"1606"/"1676" year options are exactly the
  kind of mistake a pupil transposing digits actually makes, not filler); the passage is an
  original work, so no cut-text dependency; no dialogue to break; all 25 `question_type`s match
  what the question actually tests (`cause-in-text` on PK-ENG-0329 is a genuine literal-cause
  case — the passage states the cause outright — not a mislabelled inference); the difficulty
  bands are `3/12/8/2`, exactly on the documented target, and each label reads honest for its
  band; no single answer concept keys more than two questions.
- **Item 6 — a real finding.** The passage is **247 words**, well under the contract's
  600–700 word target. It doesn't show the failure the target exists to prevent — zero phrase
  reuse, and all 25 questions genuinely draw on different sentences and skills — most likely
  because it's dense factual recount (a date, a cause, a named diarist, a casualty figure, a
  rebuilding decision) rather than a slower literary narrative, so more distinct question-worthy
  facts fit in fewer words. Worth a decision rather than an edit: either this pack is short of
  contract, or informational (non-fiction) passages earn a shorter target than literary ones —
  nothing currently says which.
- **Item 2 — a borderline case, not a defect.** PK-ENG-0332 (infer-character: the Lord Mayor
  "badly underestimated how serious the fire was") is answered before PK-ENG-0347 asks *why the
  writer includes* the Lord Mayor story ("to show how one poor decision let the fire grow far
  worse"). The two overlap thematically and sit in reading order, but they test different
  skills — inferring a trait from behaviour, versus reasoning about authorial purpose — so
  answering one doesn't let a pupil skip reasoning through the other. Noted rather than flagged.

---

## The finished authoring template

Everything above, folded into one prompt. Start a new English comprehension pack from this
rather than from an earlier pack — it is the version with the defects already designed out.

````text
You are authoring one English comprehension pack of 25 multiple-choice questions for the
RevisorPlus 11+ bank. Follow every rule below; then run validate_questions.py AND
audit_packs.py and fix anything they flag; then read all 25 questions as a pupil would.

PASSAGE
- 600–700 words. Shorter forces 25 questions onto the same few sentences; longer won't fit.
- A self-contained extract from a pre-1928, public-domain work. Fresh — NOT Alice in
  Wonderland or A Little Princess (used by the repo's example packs and every prep book).
- Vary author AND period from the other packs in the batch.
- After you trim to length, re-read: no question may depend on a clause you cut, and any
  dialogue must still alternate (no character speaking twice in a row, no reply to nothing).
- Quote the text EXACTLY. Every phrase a question quotes must appear, verbatim, in the
  printed extract — never from memory or from elsewhere in the book.
- source_note stating provenance ("Public domain: … (1894)."). If you altered typography
  (curly to straight quotes) or omitted a line, say so.

THE 25 QUESTIONS — shape
Use these subtopics/types (the standard English-comprehension shape), but PUT THEM IN A
DIFFERENT ORDER from every other pack in the batch (no shared type/difficulty sequence):
  4 literal_retrieval  (fact-recall x2, locate-detail x2)
  5 inference          (infer-character x2, infer-situation, select-evidence, infer-motive)
  4 vocab_in_context   (word-meaning-in-context x3, phrase-meaning)
  4 authors_purpose    (why-detail-included x2, why-structured-this-way, viewpoint-and-tone)
  4 figurative_language(identify-device x2, find-example-of-device, effect-of-device)
  2 text_structure     (sequence-events, overall-shape)
  2 word_classes       (identify-word-class, word-class-in-context)
Label each honestly — a retrieval question is retrieval, not inference. The weakness report
depends on the label being the *right* type, not merely a valid one.

DIFFICULTY — spread 3 / 12 / 8 / 2 across bands 1-2 / 3 / 4 / 5
- Band honestly (Year 5/6 sitting the exam, not an adult). Include genuine band 4-5 so the
  targeted-paper feature has hard questions to serve. Don't relabel to hit the shape.

WORD-CLASS QUESTIONS — 11+ standard, not Year 3
- NEVER quote the word inside a phrase that makes its class obvious. Cite it by line:
  "What type of word is 'X' in line 12?"
- Choose words whose class is genuinely ambiguous: an -ing word working as an adjective, a
  past participle as an adjective, a noun used as a verb, a word plausibly two classes.
- Include one "which of these five words (each from a different line) is a <part of speech>?"
  and one "what are the classes of 'X' (line a) and 'Y' (line b)?".
- Distractors must be classes the word could credibly be. Four absurd options is not a
  question.

EVERY QUESTION
- Exactly one correct option. 5 options, all plausible. A distractor must be a mistake a real
  pupil makes; no distractor may be arguably-also-correct or numerically equal to the key.
- The stem must not state, define, or imply its own answer. Do not name a device's definition
  ("without like or as", "giving it human qualities") when the answer is that device.
- No two questions may quote the same phrase (nor one phrase inside another).
- No question's stem may reveal another question's answer, in the same words OR different ones.
- Explanations are shown after answering; put the teaching there, not the give-away in the stem.
- Use line_ref for a question tied to a specific line; count lines at 100 characters wide.

ANSWER KEYS
- Assign key positions at RANDOM, then verify: roughly even A-E, no cyclic pattern, no run of
  the same letter longer than 2. Do not construct "5 of each" — that produces a cycle.

NO REPEATED ANSWER CONCEPT
- No single idea may be the key to more than two questions. (Five questions all keying on
  "warm nephew vs cold Scrooge" is the failure to avoid.) audit_packs.py [7] catches repeated
  key WORDS; it will NOT catch the same idea phrased differently — you must read the keys.

MECHANICAL
- Handle-scoped refs: PK-ENG-0001, PK-ENG-0002, … (content-derived refs collide between
  authors). One unique source per batch, e.g. CONTRIB-PK-01; never reuse one, never "seed".
- Filename contrib_<handle>_eng_<nn>.json; section {code:"ENG", name:"English"};
  is_placeholder:false.

BEFORE YOU FINISH
- python3 elevenplus_data/validate_questions.py elevenplus_data/*.json   → exit 0
- python3 audit_packs.py <this pack> --baseline <other packs> --target 3,12,8,2 → 0 warnings
- Then READ all 25 as a pupil: are the distractors tempting? is any answer inferable from the
  stem? is any skill mislabelled? is any single idea keying three answers? The tools cannot
  see these; you must.
````

*Written from the packs 01–05 build. The contract these rules sit on is
[`elevenplus_data/CLAUDE.md`](elevenplus_data/CLAUDE.md); the audit checks referenced as
`[1]`–`[7]` live in `audit_packs.py`.*
