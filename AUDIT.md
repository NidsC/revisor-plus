# audit_packs.py — the question-quality audit

A quality lens for RevisorPlus question packs, deliberately **separate from
`elevenplus_data/validate_questions.py`**. The validator is the *import gate*: it decides
whether a pack is well-formed enough to load (valid section, non-colliding `source`, required
fields, one correct option, valid subtopics/types). This tool asks a different question —
**is the pack any good?** — and never blocks import. Run it yourself before opening a PR.

```bash
# audit one pack against the others already in the batch
python3 audit_packs.py elevenplus_data/contrib_pk_eng_02.json \
    --baseline elevenplus_data/contrib_pk_eng_01.json \
    --target 3,12,8,2

# audit several at once (cross-pack checks compare every audited pack)
python3 audit_packs.py elevenplus_data/contrib_*.json --target 3,12,8,2
```

- `--baseline <file>` (repeatable): a pack already merged. Its stems and skeleton inform the
  cross-pack checks, but it is not itself held to them.
- `--target b12,b3,b4,b5`: the intended difficulty spread (bands 1-2 / 3 / 4 / 5), e.g.
  `3,12,8,2`.
- Exit `0` if clean, `1` if any error. Warnings never fail the run.

> **What it cannot do.** Every check below is mechanical. The defects that matter most —
> an implausible distractor, a mislabelled skill, a stem that implies its answer, a repeated
> *concept* worded differently — are invisible to it. A clean audit means "no mechanical
> faults found", not "good questions". See [`QUESTION_QUALITY.md`](QUESTION_QUALITY.md) for the
> full picture of what needs a human.

## The seven checks

**`[1]` Answer-key pattern** — reports the A–E distribution and flags three ways keys become
predictable: **clustering** (too many on one letter), a **cyclic pattern** (a repeating
sequence such as `C,A,E,B,D,…`, which is what "balance to 5 each" tends to produce), and a
**same-letter run** (e.g. `B,B,B,B`). *Why:* a pupil who spots where the answer sits stops
reading the questions. Even distribution is not the goal — unpredictability is; assign key
positions at random, then let this check verify.

**`[2]` Difficulty spread** — buckets the questions into bands 1-2 / 3 / 4 / 5 and compares to
`--target`. *Why:* a bottom-heavy pack (nothing above band 3) leaves the targeted-paper
feature nothing to serve a strong pupil. This checks the *shape* of the spread, not whether
any single label is honest — that still needs a human.

**`[3]` Phrase reuse** — flags any quoted phrase that appears in two different questions,
across **both stems and options**, including when a short quote is a **substring** of a longer
one. *Why:* the same fragment twice nudges the pupil and wastes the passage; 25 questions
should touch 25 different places in the text.

**`[3b]` Phantom quotes** (part of check 3) — every phrase a question quotes must actually
appear in the printed extract. *Why:* catches options that quote text from elsewhere in the
book, or a misremembered wording, which make the question unanswerable from what the child is
shown. *Limitation:* phrases containing an apostrophe (`man's`, `What's`) are not extracted,
so a phantom quote hiding a contraction slips past.

**`[4]` Stem contains its own answer** — flags a key repeated verbatim in the stem, and
**device-definition give-aways** (a stem that states the defining property of the device it
asks for — "a comparison made without 'like' or 'as'" gives away *metaphor*). "Pick the word"
questions are exempted, because the target word is legitimately in the quoted sentence. *Why:*
such a question tests reading the stem, not the passage or the skill. Note it only catches the
mechanical cases — an answer merely *implied* by a stem word needs a human.

**`[5]` Cross-pack stem templates** — flags **banned stem templates** (phrasings we chose to
retire, e.g. "most nearly means", "which of these events happens LAST") and **repeated stem
openings** across packs (two packs whose questions start with the same words). *Why:* a pupil
working through several papers learns the phrasing, not the reading; each pack should ask in
its own words.

**`[6]` Cross-pack question skeleton** — flags when two packs share the same ordered
`(question_type, difficulty)` sequence. *Why:* if Q14 is always the simile and Q19 always the
verb, the child learns the paper's shape and predicts each slot before reading it. Shuffle
each pack to a different order.

**`[7]` Answer-concept overlap** — a **lexical tripwire**: flags a distinctive *word* that
appears in the keys of three or more questions, after excluding generic words and the
passage's own subject/proper-noun words. *Why:* it stops the blatant case where one idea keys
half the paper (five pack-05 answers all on "warm nephew vs cold Scrooge"). **It is not a
guarantee:** it catches repeated key*words*, not repeated key*concepts* — two answers sharing
an idea in *different words* pass it. A green `[7]` means "no obvious lexical repeat", and the
human still has to read the keys.

*The contract these packs must satisfy is [`elevenplus_data/CLAUDE.md`](elevenplus_data/CLAUDE.md);
the wider catalogue of quality defects is [`QUESTION_QUALITY.md`](QUESTION_QUALITY.md).*
