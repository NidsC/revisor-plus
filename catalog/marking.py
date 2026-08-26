"""
Marking engine.

One entry point — `mark(question, given)` — returning a Result. Handles every
answer kind the question bank supports:

    mcq            the submitted AnswerOption is the correct one
    error_span     ditto — the options are the segments of the sentence
    select_word    ditto — the options are the words of the sentence
    cloze_gap      ditto — the options are the choices offered for the gap
    grouped_options one pick per bracket, all of them right, for one mark
    numeric        parsed as a number, compared within `tolerance`
    short_text     keyword matching against accept/reject lists
    extended_text  cannot be marked here; goes to a human

Deliberately lenient about presentation and strict about substance: an 11+ pupil
typing "£25", "25 cm" or "1,240" has given the right number, and should not lose
a mark to a currency symbol. It will not, however, accept a wrong number.
"""
import re
import unicodedata
from dataclasses import dataclass, field

# Kinds answered by choosing one of the stored options. They differ in how they
# are presented to the pupil, not in how a choice is scored.
OPTION_KINDS = frozenset({"mcq", "error_span", "select_word", "cloze_gap"})

# Answered by choosing one option from each of several brackets. Kept apart from
# OPTION_KINDS because the submission is a set of picks rather than one, and
# "did the pupil pick the right one" has no answer for a question with two.
GROUPED_KINDS = frozenset({"grouped_options"})

# Number words a pupil might type instead of digits. Deliberately short — this
# covers the range that actually shows up in answers, not a general parser.
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
}

# Ordinals, for answers like "the seventh lamp" -> 7.
ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
    "twelfth": 12,
}

# Stripped before numeric parsing: currency, units, thousands separators.
_NUMERIC_NOISE = re.compile(r"[£$€,\s]|(?<=\d)(?:st|nd|rd|th)\b", re.I)


@dataclass
class Result:
    marks: int = 0
    available: int = 1
    correct: bool = False
    awaiting_marking: bool = False
    detail: list = field(default_factory=list)  # per-criterion notes, for feedback

    @property
    def partial(self):
        return 0 < self.marks < self.available


def normalise(text):
    """Casefold, strip accents and collapse whitespace/punctuation for comparison."""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("’", "'").casefold().strip()
    text = re.sub(r"[^\w\s'%/.-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_number(text):
    """Best-effort number out of pupil input. Returns float, or None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)

    raw = normalise(text)
    if not raw:
        return None

    # "7", "-3", "1,240", "£25", "47°", "1/2", "0.5"
    cleaned = _NUMERIC_NOISE.sub("", str(text)).strip()
    frac = re.search(r"^(-?\d+)\s*/\s*(\d+)$", cleaned)
    if frac and float(frac.group(2)) != 0:
        return float(frac.group(1)) / float(frac.group(2))
    digits = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if digits:
        return float(digits.group())

    # Word forms: "eleven", "the seventh", "twenty five"
    words = [w for w in re.split(r"[\s-]+", raw) if w]
    for w in words:
        if w in ORDINAL_WORDS:
            return float(ORDINAL_WORDS[w])
    total, current, seen = 0, 0, False
    for w in words:
        if w not in NUMBER_WORDS:
            continue
        seen = True
        value = NUMBER_WORDS[w]
        if value == 100:
            current = (current or 1) * 100
        elif value == 1000:
            total += (current or 1) * 1000
            current = 0
        else:
            current += value
    return float(total + current) if seen else None


def _mark_numeric(question, given):
    target = parse_number(question.answer_text)
    got = parse_number(given)
    if got is None or target is None:
        return False
    if abs(got - target) <= (question.tolerance or 0):
        return True
    # An accepted alternative may be a word form or a differently-expressed value.
    for alt in question.accepted_alternatives or []:
        alt_num = parse_number(alt)
        if alt_num is not None and abs(got - alt_num) <= (question.tolerance or 0):
            return True
        if normalise(alt) and normalise(alt) == normalise(given):
            return True
    return False


def _mark_short_text(question, given):
    """Keyword matching: any accepted phrase present, no rejected phrase present.

    Reject wins over accept — "not injured" should not score on "injured".
    """
    text = normalise(given)
    if not text:
        return False
    for bad in question.reject_keywords or []:
        if normalise(bad) and normalise(bad) in text:
            return False
    # The canonical answer always counts. It used to be consulted only when
    # `accepted_alternatives` was empty, which meant that listing an alternative
    # silently stopped the real answer scoring: the shipped template's own
    # example answers "reflex" and lists "reflex angle" and "a reflex angle", so
    # a pupil typing exactly "reflex" was marked wrong. Matched exactly rather
    # than as a substring, because a canonical answer as short as "no" would
    # otherwise score inside "not sure".
    if question.answer_text and normalise(question.answer_text) == text:
        return True
    accepted = question.accepted_alternatives or []
    return any(normalise(good) and normalise(good) in text for good in accepted)


def _mark_grouped(question, options):
    """One word picked from each bracket. Both right, or the question is wrong.

    All-or-nothing and worth one mark, because that is what a paper gives: the
    answer to "money is to (…) as tea is to (…)" is the pair, and half a pair is
    not half an analogy. Partial credit here would also quietly reward guessing,
    since two brackets of three can be half-right by chance one time in two.

    A miss names the bracket rather than only saying "not quite" — the pupil who
    got the relationship right and the second word wrong has made a different
    mistake from the one who got neither, and that is the difference between
    marking and teaching.
    """
    picked = {o.group: o for o in (options or []) if o is not None}
    expected = {o.group for o in question.options.all()}
    # A bracket left blank is not a wrong answer to score against; it is an
    # unanswered question. Treated as wrong, but with nothing to say about it.
    if set(picked) != expected:
        return False, []
    wrong = sorted(g for g, o in picked.items() if not o.is_correct)
    return (not wrong), [f"bracket {g}" for g in wrong]


def mark(question, given=None, option=None, options=None):
    """Mark one answerable question.

    `option` is a single AnswerOption, for the kinds answered by one pick.
    `options` is a list of them, for a question answered by one pick per bracket.
    """
    available = question.marks or 1
    result = Result(available=available)

    if question.kind == question.Kind.EXTENDED_TEXT or question.marking == question.Marking.RUBRIC:
        # Nothing here can judge a 4-mark character study. Store it for a marker.
        result.awaiting_marking = True
        return result

    # Spotting the error, clicking the word and filling a cloze gap all come
    # down to "did the pupil pick the right one of these", so they mark exactly
    # as multiple choice does. What differs is how they are shown, not how they
    # are scored, and giving them their own marking path would only be a second
    # place for the same bug to live.
    if question.kind in GROUPED_KINDS:
        result.correct, result.detail = _mark_grouped(question, options)
    elif question.kind in OPTION_KINDS:
        result.correct = bool(option and option.is_correct)
        # Name the slip. Each generated distractor records the error it models,
        # so a wrong answer can say WHICH mistake was made rather than only that
        # one was — which is the difference between marking and teaching.
        if option is not None and not result.correct and option.misconception:
            result.detail.append(option.misconception_text)
    elif question.kind == question.Kind.NUMERIC:
        result.correct = _mark_numeric(question, given)
    elif question.kind == question.Kind.SHORT_TEXT:
        result.correct = _mark_short_text(question, given)

    result.marks = available if result.correct else 0
    return result
