#!/usr/bin/env python3
"""
validate_words.py — pre-merge checker for RevisorPlus vocabulary word packs.

Stdlib only, no Django, matching elevenplus_data/validate_questions.py: whoever
writes words can run it with nothing but Python 3.

Word packs are NOT question packs. They live in vocab/data/, never in
elevenplus_data/ — that folder's own validator globs `elevenplus_data/*.json`
and build.sh feeds `contrib_*.json` from it to import_pack, so a word pack
there would be checked and imported as something it is not.

Usage
-----
    python3 vocab/validate_words.py                     # every pack in vocab/data/
    python3 vocab/validate_words.py vocab/data/gl.json  # just these

Exit codes
----------
    0  no ERRORS (warnings may still be printed)
    1  at least one ERROR — do not merge until fixed
    2  a file could not be read or parsed as JSON

What a pack looks like
----------------------
    {
      "pack": "gl",                  # must equal the file name's stem
      "title": "GL Assessment",
      "words": [
        {
          "word": "meticulous",      # lowercase; the form the gap frame takes
          "pos": "adjective",        # noun | verb | adjective | adverb
          "year": 7,                 # 5-8, orders new words by difficulty
          "definition": "...",       # must not use the word itself
          "synonyms": ["thorough", "painstaking", "precise"],   # 2 or more
          "group": "care-and-effort",
          "example": "...",          # shows the meaning; uses the word
          "gap": {
            "frame": "... ___ ...",  # tests the meaning; exactly one ___
            "distractors": ["careless", "impatient", "generous"]
          }
        }
      ]
    }

Why `group` exists
------------------
Synonym match and odd one out draw their wrong options from other entries.
That is only safe if no wrong option is secretly a fair answer — the problem
catalog/generators/analogy_data.py's ALSO_HOLDS table exists to manage. A
group is a set of entries close enough in meaning that they must never be
used as wrong options for each other. Put two entries in one group whenever
a pupil could reasonably argue one means the other ("meticulous" and
"cautious" both shade into "careful"). Groups are shared across packs.

The checker enforces the part of that it can see — a word listed under two
entries must be in one group — but it cannot see near-synonyms nobody
listed. That is what human review of each pack is for.

The gap frame
-------------
Its three distractors are written by hand, not drawn at play time, because
"exactly one of the four options fits this sentence" is a judgement about
that sentence and can only be checked where it is written. The checker
refuses a distractor that is the word, one of its synonyms, or any word of
an entry in the same group; whether the remaining three truly fail to fit
is checked by the author and the reviewer.
"""
import glob
import json
import os
import re
import sys

POS = ("noun", "verb", "adjective", "adverb")
YEARS = range(5, 9)
GAP = "___"
N_DISTRACTORS = 3
MIN_SYNONYMS = 2
# Synonym match needs three wrong options of the same part of speech.
MIN_POOL = 3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

_WORD_RE = re.compile(r"^[a-z][a-z'-]*[a-z]$")
_TERM_RE = re.compile(r"^[a-z][a-z' -]*[a-z]$")   # synonyms may be phrases
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_TOKEN_RE = re.compile(r"[a-z][a-z'-]*")
_ENDINGS = ("s", "es", "d", "ed", "ing", "ied", "ies", "r", "er", "st", "est", "ly", "ily")
REQUIRED = ("word", "pos", "year", "definition", "synonyms", "group",
            "example", "gap")


def uses_word(text, word):
    """True if `text` contains `word` or an inflection of it.

    "devour" matches "devoured", "abate" matches "abating", "bury" matches
    "buried", "stop" matches "stopped", "meticulous" matches "meticulously" —
    because the example sentence is free to inflect, and the gap frame must
    not give the answer away in any form. Only those endings count, so
    "scare" does not match "scarecrow".
    """
    bases = {word, word + word[-1]}
    if word.endswith(("e", "y")):
        bases.add(word[:-1])
    forms = {word} | {b + s for b in bases for s in _ENDINGS}
    return any(token in forms for token in _TOKEN_RE.findall(text.lower()))


def _ends_sentence(text):
    return text.rstrip().endswith((".", "!", "?", '"', "”"))


def check_entry(entry, where):
    """Errors in one entry, judged on its own."""
    errors = []
    if not isinstance(entry, dict):
        return [f"{where}: not an object"]
    missing = [k for k in REQUIRED if k not in entry]
    if missing:
        return [f"{where}: missing {', '.join(missing)}"]
    unknown = sorted(set(entry) - set(REQUIRED))
    if unknown:
        errors.append(f"{where}: unknown field(s) {', '.join(unknown)}")

    word = entry["word"]
    if not isinstance(word, str) or not _WORD_RE.match(word):
        return errors + [f"{where}: word {word!r} must be one lowercase word"]
    where = f"{where} ({word})"

    if entry["pos"] not in POS:
        errors.append(f"{where}: pos {entry['pos']!r} must be one of {', '.join(POS)}")
    if not isinstance(entry["year"], int) or entry["year"] not in YEARS:
        errors.append(f"{where}: year {entry['year']!r} must be 5, 6, 7 or 8")
    if not isinstance(entry["group"], str) or not _SLUG_RE.match(entry["group"]):
        errors.append(f"{where}: group {entry['group']!r} must be a lowercase-hyphenated slug")

    definition = entry["definition"]
    if not isinstance(definition, str) or not definition.strip():
        errors.append(f"{where}: definition is empty")
    elif uses_word(definition, word):
        errors.append(f"{where}: definition uses the word itself")

    synonyms = entry["synonyms"]
    if not isinstance(synonyms, list) or len(synonyms) < MIN_SYNONYMS:
        errors.append(f"{where}: needs at least {MIN_SYNONYMS} synonyms")
    else:
        for s in synonyms:
            if not isinstance(s, str) or not _TERM_RE.match(s):
                errors.append(f"{where}: synonym {s!r} must be lowercase words")
            elif s == word:
                errors.append(f"{where}: lists itself as a synonym")
        if len(set(synonyms)) != len(synonyms):
            errors.append(f"{where}: repeats a synonym")

    example = entry["example"]
    if not isinstance(example, str) or not example.strip():
        errors.append(f"{where}: example is empty")
    else:
        if not uses_word(example, word):
            errors.append(f"{where}: example does not use the word")
        if GAP in example:
            errors.append(f"{where}: example contains {GAP} — the gap belongs in gap.frame")
        if not _ends_sentence(example):
            errors.append(f"{where}: example is not a finished sentence")

    gap = entry["gap"]
    if not isinstance(gap, dict) or set(gap) != {"frame", "distractors"}:
        errors.append(f"{where}: gap must have exactly frame and distractors")
        return errors
    frame = gap["frame"]
    if not isinstance(frame, str) or frame.count(GAP) != 1:
        errors.append(f"{where}: gap.frame must contain {GAP} exactly once")
    else:
        blanked = example.replace(word, GAP) if isinstance(example, str) else ""
        if frame.strip() == blanked.strip():
            errors.append(f"{where}: gap.frame is the example sentence with the word blanked")
        if uses_word(frame.replace(GAP, " "), word):
            errors.append(f"{where}: gap.frame gives the word away")
        if not _ends_sentence(frame):
            errors.append(f"{where}: gap.frame is not a finished sentence")
    distractors = gap["distractors"]
    if (not isinstance(distractors, list) or len(distractors) != N_DISTRACTORS
            or len(set(distractors)) != N_DISTRACTORS):
        errors.append(f"{where}: gap.distractors must be {N_DISTRACTORS} different words")
    else:
        for d in distractors:
            if not isinstance(d, str) or not _TERM_RE.match(d):
                errors.append(f"{where}: gap distractor {d!r} must be lowercase words")
            elif d == word:
                errors.append(f"{where}: the word is one of its own gap distractors")
            elif isinstance(synonyms, list) and d in synonyms:
                errors.append(f"{where}: gap distractor {d!r} is a synonym, so it fits too")
    return errors


def check_pack(pack, name):
    """(errors, warnings) for one pack file's contents."""
    errors, warnings = [], []
    if not isinstance(pack, dict):
        return [f"{name}: top level must be an object"], []
    stem = os.path.splitext(os.path.basename(name))[0]
    if pack.get("pack") != stem:
        errors.append(f"{name}: \"pack\" must be {stem!r}, the file name, not {pack.get('pack')!r}")
    if not isinstance(pack.get("title"), str) or not pack["title"].strip():
        errors.append(f"{name}: needs a title")
    words = pack.get("words")
    if not isinstance(words, list) or not words:
        return errors + [f"{name}: \"words\" must be a non-empty list"], warnings

    seen = {}
    for i, entry in enumerate(words):
        errors += check_entry(entry, f"{name} words[{i}]")
        w = entry.get("word") if isinstance(entry, dict) else None
        if w in seen:
            errors.append(f"{name}: {w!r} appears twice (words[{seen[w]}] and words[{i}])")
        elif w:
            seen[w] = i

    # Can synonym match find three same-part-of-speech wrong options from
    # other groups? Fine to fall short in a sample pack; not in a real one.
    good = [e for e in words if isinstance(e, dict) and not check_entry(e, "")]
    for e in good:
        pool = {t for o in good if o["pos"] == e["pos"] and o["group"] != e["group"]
                for t in [o["word"], *o["synonyms"]]}
        if len(pool) < MIN_POOL:
            warnings.append(f"{name} ({e['word']}): only {len(pool)} {e['pos']} wrong "
                            f"option(s) from other groups — a round needs {MIN_POOL}")
    return errors, warnings


def check_across(packs):
    """Errors that only show up across entries, or across packs.

    `packs` is a list of (name, pack) whose entries already pass check_entry.
    """
    errors = []
    by_word = {}       # word -> (pack name, entry): shared words must agree
    groups_of = {}     # term -> {group: [entry words]}
    group_terms = {}   # group -> every word and synonym in it
    for name, pack in packs:
        for e in pack["words"]:
            prior = by_word.get(e["word"])
            if prior is None:
                by_word[e["word"]] = (name, e)
            elif prior[1] != e:
                errors.append(f"{e['word']!r} is in {prior[0]} and {name} with different "
                              f"details — a shared word is stored once, so both copies must match")
                continue
            elif prior[0] != name:
                continue   # the same entry in a second pack: counted once
            for term in [e["word"], *e["synonyms"]]:
                groups_of.setdefault(term, {}).setdefault(e["group"], []).append(e["word"])
            group_terms.setdefault(e["group"], set()).update([e["word"], *e["synonyms"]])

    for term, groups in sorted(groups_of.items()):
        if len(groups) > 1:
            where = "; ".join(f"{g}: {', '.join(ws)}" for g, ws in sorted(groups.items()))
            errors.append(f"{term!r} belongs to entries in different groups ({where}) — "
                          f"it could be a wrong option for an entry it fits; "
                          f"merge the groups or drop the overlap")

    for word, (name, e) in sorted(by_word.items()):
        siblings = group_terms.get(e["group"], set()) - {word}
        for d in e["gap"]["distractors"]:
            if d in siblings:
                errors.append(f"{name} ({word}): gap distractor {d!r} is in the same group "
                              f"({e['group']}), so it may fit the sentence too")
    return errors


def validate(paths):
    """(errors, warnings, unreadable) over every path, plus cross-pack checks."""
    errors, warnings, unreadable, loaded = [], [], [], []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                pack = json.load(f)
        except (OSError, ValueError) as exc:
            unreadable.append(f"{path}: {exc}")
            continue
        e, w = check_pack(pack, os.path.basename(path))
        errors += e
        warnings += w
        if not e:
            loaded.append((os.path.basename(path), pack))
    if not errors:
        errors += check_across(loaded)
    return errors, warnings, unreadable


def summary(pack):
    words = pack["words"]
    years = {y: sum(e["year"] == y for e in words) for y in YEARS}
    pos = {p: sum(e["pos"] == p for e in words) for p in POS}
    return (f"{len(words)} words | years " + " ".join(f"Y{y}:{n}" for y, n in years.items())
            + " | " + " ".join(f"{p}:{n}" for p, n in pos.items() if n))


def main(argv):
    paths = []
    for a in argv or [os.path.join(DATA_DIR, "*.json")]:
        matched = sorted(glob.glob(a))
        paths += matched or [a]
    errors, warnings, unreadable = validate(paths)
    for msg in unreadable:
        print(f"UNREADABLE  {msg}")
    for msg in errors:
        print(f"ERROR       {msg}")
    for msg in warnings:
        print(f"WARNING     {msg}")
    if not errors and not unreadable:
        for path in paths:
            with open(path, encoding="utf-8") as f:
                print(f"OK          {os.path.basename(path)}: {summary(json.load(f))}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s), "
          f"{len(unreadable)} unreadable, {len(paths)} file(s)")
    if unreadable:
        return 2
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
