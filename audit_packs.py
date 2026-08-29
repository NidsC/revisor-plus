#!/usr/bin/env python3
"""Quality audit for RevisorPlus contributor packs.

Runs the checks the validator does NOT: answer-letter balance, difficulty spread,
in-pack phrase leaks (two questions quoting the same phrase), stems that contain
their own answer, and stem-template repetition ACROSS packs (banned templates and
near-duplicate stem openings, so a pupil can't predict the question shapes).

    python3 audit_packs.py pack_a.json pack_b.json ...

Exit 0 if clean, 1 if any ERROR-level finding. Warnings never fail the run.
This is a quality lens, not the import gate -- validate_questions.py is that.
"""
import json, re, sys, collections

L = "ABCDEFGH"
STOP = set("a an the of to in on at by for and or but with as is was were be been am are "
           "he she it his her him they them we us you your our i my me that this these those "
           "which who what when where why how do does did done not no so if then than into "
           "from over up down out off about their its one two more most very much many "
           "would could should will shall can may might must have has had".split())

# ---- stem templates that must not recur across packs -------------------------
BANNED = [
    r"which of these events happens last",
    r"most nearly means",
    r"which word is a verb",
    r"why does the author begin by",
]

def norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())

def sig_words(s):
    return [w for w in norm(s).split() if w not in STOP and len(w) > 2]

def quoted_phrases(text):
    # single quotes only when they are real quotation marks, i.e. the opening '
    # is not preceded by a word char and the closing ' not followed by one --
    # so a bare apostrophe in a contraction/possessive ("captain's", "man's")
    # doesn't itself open or close a quote. Inside the span, an apostrophe is
    # only allowed as quote CONTENT when it's word-internal ('(?=\w)) -- e.g.
    # "the man's hat fell" -- so a real quoted phrase containing a contraction
    # is still captured, rather than silently failing to match at all.
    out = []
    for m in re.findall(r"(?<!\w)'((?:[^']|'(?=\w)){6,})'(?!\w)", text) + re.findall(r'"([^"]{6,})"', text):
        p = re.sub(r"\s+", " ", m.lower()).strip(" .,;:!?")
        if len(p.split()) >= 2:
            out.append(p)
    return out

# definitional cues that would hand a device-identification question its answer
DEVICE_CUES = {
    "simile": [r"using (the word )?'?like'?", r"with (the word )?'?as'?"],
    "metaphor": [r"without using '?like'? or '?as'?", r"not using '?like'? or '?as'?"],
    "personification": [r"human (qualit|characteristic)", r"giv\w* .*(a )?(living|human)",
                        r"as (though|if) it were (a )?(living|human|person|animal)"],
    "alliteration": [r"same sound at the (start|beginning)", r"begin\w* with the same",
                     r"repeat\w* the .*sound at the (start|beginning)"],
    "onomatopoeia": [r"imitat\w* the sound", r"sounds? like the (noise|sound)",
                     r"words? that sound like"],
    "hyperbole": [r"exaggerat"],
}

def cyclic_run(seq):
    """Return (period, run_length) for the longest periodic tail, else None.
    Catches construction-balanced keys like C,A,E,B,D,C,A,E,B,D..."""
    n = len(seq); best = None
    for p in range(2, n // 2 + 1):
        run = mx = 0
        for i in range(p, n):
            run = run + 1 if seq[i] == seq[i - p] else 0
            mx = max(mx, run)
        if mx >= max(6, 2 * p) and (best is None or mx > best[1]):
            best = (p, mx)
    return best

# generic key-words that are not themselves an "answer concept"
GENERIC = set(("show shows make makes made tell tells give gives given reader writer author "
               "passage thing things way ways feel feels seem seems look looks come comes takes "
               "help turn find finds know goes going puts word words line means mean sense idea "
               "point wants want lets let sets used using across whole scene extract other others "
               "long rest free freely new best good better much more less kind sort full part "
               "real just even still keeps keep trying tries meet meeting person people place").split())

def concept_overlap(qs, corpus):
    """Heuristic for 'three or more questions key on the same idea': a
    distinctive word (prefix-stemmed) in the KEY of 3+ questions. To avoid
    flagging the passage's own subjects/proper nouns, a stem is dropped when
    its prefix recurs in the PASSAGE itself (>=3 times) -- those are what the
    text is ABOUT, not a repeated answer concept -- as are generic words and
    any stem in >30% of keys. A lexical tripwire, not a semantic guarantee."""
    gstems = {g[:4] for g in GENERIC}
    # exact words to drop whose 4-prefix would otherwise collide with a real
    # concept (e.g. "understand" vs "underground" both -> "unde")
    fullstop = {"understand", "understands", "understanding"}
    corpus = corpus.lower()
    def stems(text):
        return set(w[:4] for w in sig_words(text)
                   if len(w) >= 4 and w not in fullstop and w[:4] not in gstems)
    keys = [(q["ref"], stems(answer_text(q) or "")) for q in qs]
    n = len(qs)
    df = collections.Counter(w for _, ws in keys for w in ws)
    flags = []
    for w, c in sorted(df.items(), key=lambda x: -x[1]):
        if c < 3 or c > max(4, 0.30 * n):
            continue
        if corpus.count(w) >= 2:          # a subject/proper noun the passage is about
            continue
        flags.append((w, [ref for ref, ws in keys if w in ws]))
    return flags

def max_streak(seq):
    """Longest run of the SAME key letter in a row (a period-1 pattern)."""
    best = cur = 1
    for i in range(1, len(seq)):
        cur = cur + 1 if seq[i] == seq[i - 1] else 1
        best = max(best, cur)
    return best

def load(path):
    with open(path) as f:
        return json.load(f)

def key_letter(q):
    """Only mcq/cloze_gap have a single lettered options list with one
    'correct' -- error_span/select_word are answered by segment label,
    numeric/short_text/extended_text have no options at all, and
    grouped_options has several per-bracket keys, not one. None of those
    have a meaningful answer-LETTER position, so return None for them
    rather than crash; callers filter None out of the sequence."""
    opts = q.get("options")
    if not opts:
        return None
    for i, o in enumerate(opts):
        if o.get("correct"):
            return L[i]
    return "?"

def answer_text(q):
    """The text of the correct answer, across every kind that has one
    fixed, findable answer. None for grouped_options (several keys, one
    per bracket) and extended_text (no fixed key) -- checks that need a
    single answer string skip a question when this returns None."""
    opts = q.get("options")
    if opts:
        return next((o["text"] for o in opts if o.get("correct")), None)
    segs = q.get("segments")
    if segs and q.get("answer"):
        seg = next((s for s in segs if s.get("label") == q["answer"]), None)
        return seg["text"] if seg else None
    ans = q.get("answer")
    if isinstance(ans, str):
        return ans
    return None

def text_pool(q):
    """Every bit of text a phrase-reuse/phantom-quote check should scan:
    the stem, plus options/segments text when the kind has them, plus a
    string-typed answer. Kind-agnostic so it doesn't crash on error_span,
    select_word, numeric or short_text questions."""
    parts = [q.get("stem", "")]
    parts += [o.get("text", "") for o in q.get("options", [])]
    parts += [s.get("text", "") for s in q.get("segments", [])]
    ans = q.get("answer")
    if isinstance(ans, str):
        parts.append(ans)
    return " ".join(parts)

def audit_pack(path, pack, target=None):
    errs, warns = [], []
    qs = pack["questions"]
    label = path.split("/")[-1]
    section_code = pack.get("section", {}).get("code")
    has_passages = bool(pack.get("passages"))

    # 1. answer-letter distribution + cyclic-pattern detection -- only
    #    over questions that have a lettered key at all (see key_letter).
    seq_all = [key_letter(q) for q in qs]
    seq = [k for k in seq_all if k is not None]
    skipped = len(seq_all) - len(seq)
    skip_note = f"  ({skipped} question(s) with no lettered key skipped)" if skipped else ""
    if not seq:
        print(f"  [1] answer-letter distribution: n/a -- no lettered-key questions in this pack{skip_note}")
        dist = collections.Counter()
        skew = {}
        cyc = None
        streak = 0
    else:
        dist = collections.Counter(seq)
        n = len(seq)
        first_lettered = next((q for q in qs if q.get("options")), None)
        opts = len(first_lettered["options"]) if first_lettered else 0
        ideal = n / opts if opts else 0
        skew = {k: v for k, v in dist.items() if abs(v - ideal) > max(2, ideal * 0.6)}
        cyc = cyclic_run(seq)
        streak = max_streak(seq)
        print(f"  [1] answer-letter distribution: {dict(sorted(dist.items()))}  "
              f"(ideal ~{ideal:.1f} each) -> {'CLUSTERED' if skew else 'balanced'}; "
              f"cyclic pattern -> {'PERIOD ' + str(cyc[0]) if cyc else 'none'}; "
              f"longest same-letter run -> {streak}{skip_note}")
    if skew:
        warns.append(f"answer-letter clustering: {skew}")
    if cyc:
        warns.append(f"answer keys follow a period-{cyc[0]} cycle over {cyc[1]+cyc[0]} questions "
                     f"({''.join(seq)}) -- randomise, don't construct")
    if streak >= 4:
        warns.append(f"answer keys include a run of {streak} identical letters in a row "
                     f"({''.join(seq)}) -- looks like a pattern")

    # 2. difficulty spread (bands: 1-2 / 3 / 4 / 5) against target
    diff = collections.Counter(q.get("difficulty") for q in qs)
    bands = (diff.get(1, 0) + diff.get(2, 0), diff.get(3, 0), diff.get(4, 0), diff.get(5, 0))
    tstr = ""
    if target:
        ok = tuple(target) == bands
        tstr = f"  target {tuple(target)} -> {'MATCH' if ok else 'MISMATCH'}"
        if not ok:
            warns.append(f"difficulty spread {bands} does not match target {tuple(target)}")
    print(f"  [2] difficulty spread: raw {dict(sorted(diff.items()))}  "
          f"bands(1-2/3/4/5)={bands}{tstr}")
    if bands[2] + bands[3] == 0:
        warns.append("no band-4/5 questions -- starves the targeted-paper feature")

    # 3. in-pack phrase reuse across questions -- STEMS AND OPTIONS, and now
    #    catching substring overlaps ("broad shoulders" inside a longer quote),
    #    not just identical phrases.
    qphr = []
    for q in qs:
        qphr.append((q["ref"], sorted(set(quoted_phrases(text_pool(q))))))
    reuse, seen_pairs = [], set()
    for i in range(len(qphr)):
        for j in range(i + 1, len(qphr)):
            ri, pi = qphr[i]; rj, pj = qphr[j]
            for a in pi:
                for b in pj:
                    if a == b or a in b or b in a:
                        shared = a if len(a) <= len(b) else b
                        k = (shared, ri, rj)
                        if k not in seen_pairs:
                            seen_pairs.add(k); reuse.append(k)
    print(f"  [3] phrase reuse across questions (stems+options, incl. substrings): "
          f"{'none' if not reuse else str(len(reuse)) + ' found'}")
    for shared, ri, rj in reuse:
        errs.append(f"phrase reuse: {shared!r} appears in both {ri} and {rj}")

    # 3b. every quoted phrase must actually appear in the printed extract --
    #     only means anything for a pack that HAS a printed extract. Without
    #     one, a quote mark in a stem is a punctuated example sentence or an
    #     idiom, not a passage citation, and "not in the printed extract" is
    #     true of everything by construction -- a pack-wide false positive,
    #     not a defect. Confirmed against the punctuation/vocabulary packs.
    if not has_passages:
        print(f"  [3b] quoted phrases present in the extract: n/a -- pack has no passages")
    else:
        corpus = re.sub(r"\s+", " ", " ".join(pp.get("text", "") for pp in pack.get("passages", [])).lower())
        phantom = 0
        for q in qs:
            for p in set(quoted_phrases(text_pool(q))):
                if p not in corpus:
                    errs.append(f"{q['ref']}: quoted phrase {p!r} is not in the printed extract")
                    phantom += 1
        print(f"  [3b] quoted phrases present in the extract: "
              f"{'all' if not phantom else str(phantom) + ' missing'}")

    # 4. stem contains its own answer -- an English-comprehension concept
    # (a stem handing away a reading/inference answer). Maths MCQs routinely
    # and legitimately name their own candidates in a comparison stem ("which
    # shop offers better value: Shop A or Shop B?", "which is longer: 1.5km
    # or 1,400m?") or land on a value already in a calculation ("angle
    # vertically opposite a 118 degree angle" = 118 degrees) -- confirmed
    # every flagged case in the Maths pack was one of these shapes, not a
    # giveaway. Scope to ENG rather than exempt each shape individually.
    if section_code != "ENG":
        print(f"  [4] stems containing their own answer: n/a -- English-only check")
    else:
        before = len(errs)
        for q in qs:
            if q.get("kind") in ("error_span", "select_word"):
                # segments ARE pieces of the stem by construction -- the
                # correct segment's text is always "in" the stem. That is
                # how the kind works, not a giveaway; nothing to check here.
                continue
            key = answer_text(q)
            if key is None:
                # no single fixed answer text to compare (grouped_options,
                # extended_text, or a segment kind with no matching label)
                continue
            if re.fullmatch(r"-?[\d,]+(\.\d+)?%?", key.strip()):
                # a purely numeric key legitimately recurs in a stem that
                # lists several numbers to compare or calculate from.
                continue
            stem = norm(q["stem"])
            opt_texts = [o["text"] for o in q.get("options", [])]
            # exempt "pick the word" questions: the target word is in the quoted
            # sentence by design, and so are the distractors -- not a giveaway.
            singles = [t for t in opt_texts if len(norm(t).split()) == 1]
            if len(norm(key).split()) == 1 and len(singles) >= len(opt_texts) - 1 \
               and sum(1 for t in singles if norm(t).strip() in stem.split()) >= 2:
                continue
            if norm(key) and norm(key) in stem:
                errs.append(f"{q['ref']}: stem contains the correct answer verbatim")
                continue
            # definitional giveaway: the answer is a device and the stem states its
            # defining property (e.g. "made without using 'like' or 'as'" => metaphor)
            kl = key.lower()
            for dev, cues in DEVICE_CUES.items():
                if dev in kl and any(re.search(c, q["stem"].lower()) for c in cues):
                    errs.append(f"{q['ref']}: stem gives away its own answer -- "
                                f"it states the definition of '{dev}'")
                    break
            kw = sig_words(key)
            if len(kw) >= 3:
                hit = sum(1 for w in kw if w in stem.split())
                if hit / len(kw) >= 0.8:
                    warns.append(f"{q['ref']}: {hit}/{len(kw)} answer key-words already in the stem")
        found = len(errs) - before
        print(f"  [4] stems containing their own answer: {'none' if not found else str(found) + ' found'}"
              f"  (pick-the-word questions exempted)")

    # 7. answer-concept overlap: a single idea keying 3+ questions (heuristic).
    # Also English-only -- confirmed against the Maths pack that a shared unit
    # word ("degrees", "square", "minutes") recurring across many answers in
    # the same subtopic is expected domain vocabulary, not a repeated idea;
    # the whole premise (a passage's theme leaking into several answers) is
    # about comprehension, not calculation.
    if section_code != "ENG":
        print(f"  [7] answer-concept overlap (one idea keys 3+ questions): n/a -- English-only check")
    else:
        corpus = " ".join(pp.get("text", "") for pp in pack.get("passages", []))
        cf = concept_overlap(qs, corpus)
        print(f"  [7] answer-concept overlap (one idea keys 3+ questions): "
              f"{'none' if not cf else str(len(cf)) + ' found'}")
        for w, refs in cf:
            warns.append(f"answer-concept overlap: key-word '{w}...' in {len(refs)} keys "
                         f"({', '.join(refs)}) -- check these aren't the same idea")
    return errs, warns

def cross_pack(audit_stems, baseline_stems):
    """Stems are (pack_label, ref, stem). Only audit_stems are held to the
    banned-template rule; baseline packs (already merged) merely contribute
    their openings so new packs can't echo them."""
    errs = []
    for lbl, ref, stem in audit_stems:
        for pat in BANNED:
            if re.search(pat, stem.lower()):
                errs.append(f"banned template /{pat}/ in {lbl} {ref}")
    # near-duplicate openings: an audited stem must not share its opening with
    # any other pack (audited or baseline).
    openings = collections.defaultdict(list)
    for lbl, ref, stem in audit_stems + baseline_stems:
        w = sig_words(stem)
        if len(w) >= 4:
            openings[" ".join(w[:4])].append((lbl, ref))
    audit_labels = {s[0] for s in audit_stems}
    for op, hits in sorted(openings.items()):
        packs = {h[0] for h in hits}
        if len(packs) > 1 and any(h[0] in audit_labels for h in hits):
            errs.append(f"repeated stem opening {op!r} across packs: "
                        + ", ".join(f"{l}:{r}" for l, r in hits))
    return errs

def stems_of(path):
    lbl = path.split("/")[-1]
    return [(lbl, q["ref"], q["stem"]) for q in load(path)["questions"]]

def type_seq(path):
    """The pack's ordered (question_type, difficulty) skeleton."""
    return tuple((q["question_type"], q["difficulty"]) for q in load(path)["questions"])

def type_seq_check(audit_paths, baseline_paths):
    """Flag packs that share an identical type-and-difficulty sequence -- i.e.
    the same question skeleton, so a pupil learns the paper's shape not the skills.
    Errors only when an audited pack is involved."""
    errs = []
    seqs = {p: type_seq(p) for p in audit_paths + baseline_paths}
    aset = set(audit_paths)
    paths = audit_paths + baseline_paths
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            a, b = paths[i], paths[j]
            if seqs[a] == seqs[b] and (a in aset or b in aset):
                errs.append(f"identical type/difficulty sequence: "
                            f"{a.split('/')[-1]} and {b.split('/')[-1]}")
    return errs

def main(argv):
    audit_paths, baseline_paths, target = [], [], None
    i = 0
    while i < len(argv):
        if argv[i] == "--baseline":
            baseline_paths.append(argv[i + 1]); i += 2
        elif argv[i] == "--target":
            target = [int(x) for x in argv[i + 1].split(",")]; i += 2
        else:
            audit_paths.append(argv[i]); i += 1

    total_err, total_warn, audit_stems = 0, 0, []
    for path in audit_paths:
        pack = load(path)
        print(f"\n=== {path} ===")
        errs, warns = audit_pack(path, pack, target)
        for e in errs:
            print(f"  ERROR  {e}")
        for w in warns:
            print(f"  warn   {w}")
        total_err += len(errs); total_warn += len(warns)
        audit_stems += stems_of(path)

    baseline_stems = [s for p in baseline_paths for s in stems_of(p)]
    tag = f"{len(audit_paths)} audited"
    if baseline_paths:
        tag += f", {len(baseline_paths)} baseline"
    print(f"\n=== [5] cross-pack stem-template check ({tag}) ===")
    cerrs = cross_pack(audit_stems, baseline_stems)
    for e in cerrs:
        print(f"  ERROR  {e}")
    if not cerrs:
        print("  OK -- no banned templates or repeated stem openings across packs.")
    total_err += len(cerrs)

    print(f"\n=== [6] cross-pack question-skeleton check ({tag}) ===")
    serrs = type_seq_check(audit_paths, baseline_paths)
    for e in serrs:
        print(f"  ERROR  {e}")
    if not serrs:
        print("  OK -- no two packs share the same type/difficulty sequence.")
    total_err += len(serrs)

    print("\n" + "-" * 60)
    print(f"AUDIT: {total_err} error(s), {total_warn} warning(s).")
    return 1 if total_err else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
