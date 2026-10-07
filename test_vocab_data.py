"""
Checks `vocab/validate_words.py`, and that the real word packs pass it.

Run:  python3 test_vocab_data.py

A checker that passes the real packs proves nothing on its own — a rule that
never fires passes them too. So each rule is also shown failing, on an entry
built in memory that breaks exactly that rule and nothing else.

Stdlib only and no Django, matching the checker it tests.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocab"))

from validate_words import (  # noqa: E402
    DATA_DIR, check_across, check_entry, check_pack, uses_word, validate,
)

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


GOOD = {
    "word": "meticulous", "pos": "adjective", "year": 7,
    "definition": "Paying very close attention to every detail.",
    "synonyms": ["thorough", "painstaking"],
    "group": "care-and-effort",
    "example": "Her meticulous notes recorded every step.",
    "gap": {"frame": "The watchmaker was so ___ that he checked each screw three times.",
            "distractors": ["careless", "impatient", "generous"]},
}


def entry(**over):
    e = copy.deepcopy(GOOD)
    for k, v in over.items():
        if k.startswith("gap_"):
            e["gap"][k[4:]] = v
        else:
            e[k] = v
    return e


def errs(e):
    return check_entry(e, "e")


def has(errors, needle):
    return any(needle in m for m in errors)


print("== the real packs ==")
paths = sorted(os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if f.endswith(".json"))
ck("vocab/data has the gl and general packs",
   [os.path.basename(p) for p in paths] == ["general.json", "gl.json"],
   str([os.path.basename(p) for p in paths]))
errors, warnings, unreadable = validate(paths)
ck("both packs pass with no errors", not errors and not unreadable, str(errors + unreadable))

print("\n== uses_word: the word in any form ==")
ck("exact", uses_word("The hungry lions devour it.", "devour"))
ck("-ed", uses_word("The lions devoured it.", "devour"))
ck("drops a final e", uses_word("The storm was abating.", "abate"))
ck("y to ied", uses_word("They buried the box.", "bury"))
ck("capitalised", uses_word("Ominous clouds.", "ominous"))
ck("a doubled final consonant", uses_word("The car stopped.", "stop"))
ck("-ly", uses_word("She worked meticulously.", "meticulous"))
ck("a different word sharing a prefix is not a match",
   not uses_word("The cart was full.", "car"))
ck("a longer unrelated word is not a match",
   not uses_word("A scarecrow stood in the field.", "scare"))

print("\n== one entry ==")
ck("the good entry passes", errs(GOOD) == [], str(errs(GOOD)))
e = copy.deepcopy(GOOD)
del e["gap"]
ck("a missing field", has(errs(e), "missing gap"))
ck("an unknown field", has(errs(entry(notes="x")), "unknown field"))
ck("a capitalised word", has(errs(entry(word="Meticulous")), "one lowercase word"))
ck("a two-word headword", has(errs(entry(word="look after")), "one lowercase word"))
ck("an unknown part of speech", has(errs(entry(pos="adj")), "pos"))
ck("year 4", has(errs(entry(year=4)), "year"))
ck("year 9", has(errs(entry(year=9)), "year"))
ck("year as a string", has(errs(entry(year="7")), "year"))
ck("a group that is not a slug", has(errs(entry(group="Care and effort")), "slug"))
ck("an empty definition", has(errs(entry(definition=" ")), "definition is empty"))
ck("a definition that uses the word",
   has(errs(entry(definition="Being meticulous about detail.")), "uses the word itself"))
ck("one synonym is not enough", has(errs(entry(synonyms=["thorough"])), "at least 2"))
ck("a repeated synonym", has(errs(entry(synonyms=["thorough", "thorough"])), "repeats"))
ck("the word as its own synonym",
   has(errs(entry(synonyms=["thorough", "meticulous"])), "itself as a synonym"))
ck("an example without the word",
   has(errs(entry(example="Her notes recorded every step.")), "does not use the word"))
ck("an example containing the gap",
   has(errs(entry(example="Her meticulous ___ notes.")), "contains ___"))
ck("an unfinished example",
   has(errs(entry(example="Her meticulous notes")), "not a finished sentence"))
ck("a frame with no gap",
   has(errs(entry(gap_frame="The watchmaker was careful.")), "exactly once"))
ck("a frame with two gaps",
   has(errs(entry(gap_frame="The ___ watchmaker was ___.")), "exactly once"))
ck("a frame that is the example with the word blanked",
   has(errs(entry(example="Her meticulous notes recorded every step.",
                  gap_frame="Her ___ notes recorded every step.")), "word blanked"))
ck("a frame that gives the word away",
   has(errs(entry(gap_frame="Meticulously, the ___ watchmaker checked every screw.")),
       "gives the word away"))
ck("two distractors", has(errs(entry(gap_distractors=["careless", "impatient"])), "3 different"))
ck("a repeated distractor",
   has(errs(entry(gap_distractors=["careless", "careless", "generous"])), "3 different"))
ck("the word as its own distractor",
   has(errs(entry(gap_distractors=["meticulous", "impatient", "generous"])),
       "its own gap distractors"))
ck("a synonym as a distractor fits too, so it is refused",
   has(errs(entry(gap_distractors=["thorough", "impatient", "generous"])), "fits too"))

print("\n== one pack ==")
pack = {"pack": "gl", "title": "GL", "words": [GOOD]}
e_, w_ = check_pack(pack, "gl.json")
ck("a one-word pack has no errors", e_ == [], str(e_))
ck("...but warns that synonym match has no wrong options", has(w_, "wrong option"))
ck("pack must match its file name",
   has(check_pack(dict(pack, pack="general"), "gl.json")[0], "file name"))
ck("a title is required", has(check_pack(dict(pack, title=""), "gl.json")[0], "title"))
ck("an empty word list", has(check_pack(dict(pack, words=[]), "gl.json")[0], "non-empty"))
ck("the same word twice in one pack",
   has(check_pack(dict(pack, words=[GOOD, GOOD]), "gl.json")[0], "appears twice"))
others = [entry(word=w, group=g, synonyms=[f"{w}-a", f"{w}-b"],
                definition="Something.", example=f"It was {w}.",
                gap_frame="Nobody else was ___ that day.", gap_distractors=["x-a", "x-b", "x-c"])
          for w, g in (("hostile", "unfriendliness"), ("vivid", "brightness"))]
ck("(the two extra entries are themselves valid)",
   all(errs(o) == [] for o in others), str([errs(o) for o in others]))
ck("three or more same-pos wrong options from other groups clears the warning",
   not check_pack(dict(pack, words=[GOOD, *others]), "gl.json")[1])
same_group = [dict(o, group="care-and-effort") for o in others]
ck("...but words from the same group do not count",
   has(check_pack(dict(pack, words=[GOOD, *same_group]), "gl.json")[1], "wrong option"))

print("\n== across entries and packs ==")
def p(name, *words):
    return (name, {"pack": name, "title": name, "words": list(words)})

ck("the same entry in two packs is fine",
   check_across([p("gl", GOOD), p("general", GOOD)]) == [])
ck("the same word with different details in two packs is refused",
   has(check_across([p("gl", GOOD), p("general", entry(year=6))]), "different details"))
careful_a = entry(word="cautious", synonyms=["careful", "wary"], example="A cautious fox.",
                  gap_distractors=["reckless", "bold", "rash"], gap_frame="A ___ fox.")
careful_b = entry(word="meticulous", synonyms=["thorough", "careful"],
                  group="precision")
ck("a synonym shared by entries in different groups is refused",
   has(check_across([p("gl", dict(careful_a, group="caution"), careful_b)]), "different groups"))
ck("...and allowed when they share a group",
   check_across([p("gl", careful_a, dict(careful_b, group="care-and-effort"))]) == [])
ck("a headword listed as another group's synonym is refused",
   has(check_across([p("gl", GOOD, entry(word="exact", synonyms=["meticulous", "precise"],
                                          group="exactness", example="Exact.",
                                          gap_frame="___."))]), "different groups"))
sibling = entry(word="cautious", synonyms=["wary", "prudent"], example="A cautious fox.",
                gap_frame="A ___ fox.", gap_distractors=["reckless", "bold", "rash"])
ck("a gap distractor from the same group is refused",
   has(check_across([p("gl", entry(gap_distractors=["wary", "impatient", "generous"]),
                       sibling)]), "same group"))

if fails:
    print("\nRESULT: FAILURES:", fails)
    sys.exit(1)
print("\nRESULT: all checks passed.")
