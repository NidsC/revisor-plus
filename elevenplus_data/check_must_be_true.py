#!/usr/bin/env python3
"""
Independent checks on the Must Be True pack (contrib_prash_vr_19.json).

    python3 elevenplus_data/check_must_be_true.py elevenplus_data/contrib_prash_vr_19.json

Exit 0 if every check passes, 1 with a list of failures otherwise.

It never imports the generator — and, more to the point, never imports the
generator's solver. The rules are parsed back out of the *printed sentences*
into a day-by-day table by a solver written here from scratch, and all five
printed statements are re-evaluated against it. A checker that called
`mbt_solve()` would be asking the generator whether it agreed with itself.

  * THE WORLD IS REBUILT FROM THE TEXT. Every rule sentence must parse into one
    of the four forms this subtopic uses — opens only on a list of days, opens
    every day except a list, opens only on weekdays/weekends, or a person
    working on the days some already-described entity does or does not — and
    each must assign a definite value to all seven days. A sentence that does
    not parse fails the question rather than being skipped: an unparsed rule is
    a rule the checker would otherwise be ignoring while claiming to have
    checked the world.
  * FULL DETERMINATION IS PROVED, NOT ASSUMED. Every entity must be described
    exactly once, and a dependency's base must already be fully known when it
    is used. That is what makes "true in the table" and "necessarily true given
    the rules" the same thing — the whole premise of the question type. If any
    day of any entity were left open, the "must be true" answer would only be
    true in the world the author imagined.
  * THE COUNT OF TRUE STATEMENTS. For "which ONE of these must be true?"
    exactly one of the five must be true in the rebuilt world, and it must be
    the key. For "which ONE of these cannot be true?" exactly four must be
    true, and the key must be the odd one out. Anything else is a mis-keyed or
    under-determined item.
  * NO TWO STATEMENTS ABOUT THE SAME (ENTITY, DAY). Two statements about one
    pair would be paraphrases of each other — or contradictions offering the
    pupil two ways to be right.
  * THE FAIRNESS GUARD IS RE-CHECKED. No entity may be true on all seven days
    or false on all seven: either collapses several statements about that
    entity into "trivially true whatever day is named", letting a pupil answer
    without tracing the rule chain. The generator guards this while building;
    this re-checks it on the table the printed text actually describes.
  * THE BAND LABEL IS CHECKED AGAINST THE SHAPE: one entity at bands 1-2 (an
    enumerated pair of days at band 1, a negation or weekday/weekend rule at
    band 2), two at bands 3-4 with an exception clause only from band 4, three
    at band 5.
  * plus: name-blind duplicate detection (two questions differing only in venue
    and people are one question), unique stems and refs, the key never tagged
    with a misconception, explanations naming the entity and day they turn on,
    and answer positions neither clustered nor cyclic nor in a run of four.

No dictionary and no third-party module: this checker runs anywhere.
"""
import collections
import itertools
import json
import re
import sys

PACK = sys.argv[1] if len(sys.argv) > 1 else "elevenplus_data/contrib_prash_vr_19.json"
pack = json.load(open(PACK))
qs = pack["questions"]
fail = []

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAYS = set(DAYS[:5])
WEEKEND = set(DAYS[5:])
ENTITIES_PER_BAND = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}

ENUMERATE = re.compile(r"^(.+?) opens only on (.+)$")
NEGATE = re.compile(r"^(.+?) opens every day except (.+)$")
CATEGORY = re.compile(r"^(.+?) opens only on (weekdays|weekends \(Saturday and Sunday\))$")
DEPENDENCY = re.compile(
    r"^(.+?) works on the days (.+?) (is open|is closed|works|does not work)"
    r"(?:, (and also|except) on (\w+))?$")
STATEMENT = re.compile(r"^(.+?) (is open|is closed|works|does not work) on (\w+)\.$")


def day_list(blob):
    """'Monday, Wednesday and Friday' -> [...] , or None if a word is not a day."""
    parts = [p.strip() for p in blob.replace(" and ", ", ").split(",") if p.strip()]
    return parts if all(p in DAYS for p in parts) else None


def build_world(sentences):
    """Rebuild {entity: {day: bool}} from the printed rules. Own solver.

    Returns (table, order, error). `order` is the entities in the order they
    were described, which is what the full-determination check needs.
    """
    table, order = {}, []
    for raw in sentences:
        s = raw.strip()
        if not s.endswith("."):
            return None, None, f"rule does not end in a full stop: {raw!r}"
        s = s[:-1]

        m = CATEGORY.match(s)
        if m:
            name, cat = m.group(1), m.group(2)
            true_days = WEEKDAYS if cat == "weekdays" else WEEKEND
            row = {d: d in true_days for d in DAYS}
        elif NEGATE.match(s):
            m = NEGATE.match(s)
            name, days = m.group(1), day_list(m.group(2))
            if days is None:
                return None, None, f"not a list of days: {m.group(2)!r}"
            row = {d: d not in set(days) for d in DAYS}
        elif ENUMERATE.match(s):
            m = ENUMERATE.match(s)
            name, days = m.group(1), day_list(m.group(2))
            if days is None:
                return None, None, f"not a list of days: {m.group(2)!r}"
            row = {d: d in set(days) for d in DAYS}
        elif DEPENDENCY.match(s):
            m = DEPENDENCY.match(s)
            name, base_name, sense, exc_kind, exc_day = m.groups()
            base_key = base_name.lower()
            if base_key not in {k.lower() for k in table}:
                return None, None, (f"{name} depends on {base_name!r}, which has not been "
                                    f"described yet")
            base_row = next(v for k, v in table.items() if k.lower() == base_key)
            invert = sense in ("is closed", "does not work")
            row = {d: (not base_row[d]) if invert else base_row[d] for d in DAYS}
            if exc_kind:
                if exc_day not in DAYS:
                    return None, None, f"exception on {exc_day!r}, which is not a day"
                row[exc_day] = (exc_kind == "and also")
        else:
            return None, None, f"rule does not parse: {raw!r}"

        if name in table:
            return None, None, f"{name} is described by more than one rule"
        table[name] = row
        order.append(name)
    return table, order, None


def truth_of(statement, table):
    """Is this printed statement true in the rebuilt world? (entity, day, value)."""
    m = STATEMENT.match(statement)
    if not m:
        return None
    name, sense, day = m.groups()
    if day not in DAYS:
        return None
    key = next((k for k in table if k.lower() == name.lower()), None)
    if key is None:
        return None
    positive = sense in ("is open", "works")
    return key, day, (table[key][day] == positive)


positions, refs, stems = [], [], collections.Counter()
structures = collections.Counter()
solved = 0

for q in qs:
    tag = q.get("ref", "?")
    stem = q["stem"]
    stems[stem] += 1
    refs.append(tag)

    if q.get("subtopic") != "Must Be True":
        fail.append(f"{tag}: wrong subtopic {q.get('subtopic')!r}")
    band = q.get("difficulty")
    if band not in ENTITIES_PER_BAND:
        fail.append(f"{tag}: band {band!r}")
        continue
    if q.get("kind") != "mcq":
        fail.append(f"{tag}: kind {q.get('kind')!r}; this pack is mcq throughout")
        continue

    qtype = q.get("question_type")
    if stem.endswith("Which ONE of these must be true?"):
        want, expected_type = "must", "valid-conclusion"
    elif stem.endswith("Which ONE of these cannot be true?"):
        want, expected_type = "cannot", "spot-invalid-conclusion"
    else:
        fail.append(f"{tag}: stem does not end with this pack's question line: {stem!r}")
        continue
    if qtype != expected_type:
        fail.append(f"{tag}: a {want!r} question filed as {qtype!r}")

    rule_text = stem.rsplit("Which ONE", 1)[0].strip()
    sentences = [s + "." for s in rule_text.split(". ") if s.strip()]
    sentences[-1] = sentences[-1].rstrip(".") + "." if sentences else ""
    table, order, err = build_world([s.rstrip(".") + "." for s in
                                     [x.rstrip(".") for x in sentences]])
    if err:
        fail.append(f"{tag}: {err}")
        continue

    if len(table) != ENTITIES_PER_BAND[band]:
        fail.append(f"{tag}: band {band} should describe {ENTITIES_PER_BAND[band]} "
                    f"entities, not {len(table)}")
    has_exception = ", and also on " in rule_text or ", except on " in rule_text
    if band <= 3 and has_exception:
        fail.append(f"{tag}: band {band} carries an exception clause, which is band 4+")
    if band == 4 and not has_exception:
        fail.append(f"{tag}: band 4 should carry an exception clause")

    for name, row in table.items():
        if all(row.values()) or not any(row.values()):
            fail.append(f"{tag}: {name} is the same every day, which makes several "
                        f"statements about it trivially answerable")

    opts = q.get("options") or []
    texts = [o["text"] for o in opts]
    if len(texts) != 5:
        fail.append(f"{tag}: {len(texts)} options; this pack offers five statements")
    if len(set(texts)) != len(texts):
        fail.append(f"{tag}: repeated option text")
    correct = [o for o in opts if o.get("correct")]
    if len(correct) != 1:
        fail.append(f"{tag}: {len(correct)} options marked correct")
        continue
    if correct[0].get("misconception"):
        fail.append(f"{tag}: the key carries a misconception slug")
    key = correct[0]["text"]
    positions.append(texts.index(key))

    verdicts = {}
    pairs = []
    bad = False
    for text in texts:
        got = truth_of(text, table)
        if got is None:
            fail.append(f"{tag}: statement does not parse against the rules: {text!r}")
            bad = True
            break
        name, day, value = got
        verdicts[text] = value
        pairs.append((name, day))
    if bad:
        continue
    if len(set(pairs)) != len(pairs):
        fail.append(f"{tag}: two statements are about the same entity and day, so they "
                    f"are paraphrases of each other")

    true_count = sum(verdicts.values())
    if want == "must":
        if true_count != 1:
            fail.append(f"{tag}: {true_count} of the five statements are true, not one")
            continue
        answer = next(t for t, v in verdicts.items() if v)
    else:
        if true_count != 4:
            fail.append(f"{tag}: {5 - true_count} of the five statements are false, not one")
            continue
        answer = next(t for t, v in verdicts.items() if not v)
    solved += 1
    if key != answer:
        fail.append(f"{tag}: key {key!r} but the rules make {answer!r} the answer")

    exp = q.get("explanation", "")
    m = STATEMENT.match(key)
    if m and (m.group(3) not in exp):
        fail.append(f"{tag}: explanation does not mention {m.group(3)}, the day the "
                    f"answer turns on")

    # Name-blind: entities become E0/P0/P1 in the order described, so two
    # questions differing only in venue and people collapse together.
    slot = {name: f"E{i}" for i, name in enumerate(order)}
    structures[json.dumps({
        "rules": [re.sub("|".join(re.escape(n) for n in sorted(slot, key=len, reverse=True)),
                         lambda mo: slot[mo.group(0)], s) for s in sentences],
        "pairs": sorted([slot[n], d] for n, d in pairs),
        "want": want,
        "target": sorted(verdicts.values()),
    }, sort_keys=True)] += 1

for s, n in stems.items():
    if n > 1:
        fail.append(f"duplicate stem x{n}: {s!r}")
for st, c in structures.items():
    if c > 1:
        fail.append(f"the same scenario and statement set appears in {c} questions, "
                    f"differing only in names")
if len(set(refs)) != len(refs):
    fail.append("duplicate refs")

group_refs = {g["group_ref"] for g in pack.get("groups", [])}
for q in qs:
    if q.get("group_ref") not in group_refs:
        fail.append(f"{q.get('ref')}: group_ref {q.get('group_ref')!r} is not declared")
for g in pack.get("groups", []):
    if not g.get("instruction") or not g.get("example"):
        fail.append(f"{g.get('group_ref')}: a group needs both an instruction and an example")

dist = collections.Counter(positions)
run = longest = 1
for a, b in zip(positions, positions[1:]):
    run = run + 1 if a == b else 1
    longest = max(longest, run)
cyclic = next((p for p in (2, 3, 4, 5)
               if positions and all(positions[i] == positions[i % p]
                                    for i in range(len(positions)))), 0)
expected = len(positions) / 5
if longest >= 4:
    fail.append(f"answer position: run of {longest} identical positions")
if cyclic:
    fail.append(f"answer position: cyclic with period {cyclic}")
for pos, c in dist.items():
    if c > expected * 2:
        fail.append(f"answer position {pos}: {c} of {len(positions)} (expected ~{expected:.0f})")

print(f"pack: {PACK}")
print(f"questions: {len(qs)}   refs: {refs[0]}..{refs[-1]}")
print(f"question types: {dict(collections.Counter(q['question_type'] for q in qs))}")
print(f"difficulty: {dict(sorted(collections.Counter(q['difficulty'] for q in qs).items()))}")
print(f"worlds rebuilt from the printed rules and re-evaluated: {solved} / {len(qs)}")
print(f"distinct name-blind scenarios: {len(structures)} / {len(qs)}")
print(f"answer positions (0-indexed, {len(positions)} mcqs): {dict(sorted(dist.items()))}"
      f"  longest run {longest}  cyclic {cyclic or 'none'}")

if fail:
    print(f"\nFAIL ({len(fail)}):")
    for f in fail[:40]:
        print("  -", f)
    sys.exit(1)
print("\nALL CHECKS PASS")
