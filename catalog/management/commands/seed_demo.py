"""
Seed the demo with ORIGINAL 11+ style sample content, demo users, and a backdated
attempt history so dashboards show real trends.

Run:  python manage.py seed_demo
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from assignments.models import Assignment
from billing.models import Subscription
from catalog.models import AnswerOption, Question, Section, Subtopic
from goals.models import Goal, School, SectionTarget
from practice.models import Attempt, TestSession
from tutoring.models import TutorStudent

User = get_user_model()

SECTIONS = [
    ("ENG", "English", 1),
    ("MAT", "Maths", 2),
    ("VR", "Verbal Reasoning", 3),
    ("NVR", "Non-Verbal Reasoning", 4),
]

# Original questions. Each: section, subtopic, kind, passage, stem, options, explanation.
# options: list of (text, is_correct)
#
# This is demo scaffold, not the question bank — enough items to make every dashboard,
# chart and homework flow show real data. Real content arrives as contrib_*.json packs
# (see elevenplus_data/CLAUDE.md). The NVR items here are deliberately answerable from
# text, because genuine non-verbal questions need a figure in static/questions/ and this
# command ships no images.
QUESTIONS = [
    # ---- English ----
    ("ENG", "Reading Comprehension", "mcq",
     "The Year 6 class turned a patch of waste ground behind the science block into a wildlife "
     "garden. They dug a small pond in the autumn, and by the following June they had counted "
     "eleven species of insect that had never been recorded on the school grounds before. "
     "Mrs Achebe, who supervised the project, admitted she had expected the pond to be the "
     "hardest part; in the end it was persuading the caretaker to leave the grass long that "
     "took the most convincing.",
     "According to the passage, what did Mrs Achebe find hardest about the project?",
     [("Convincing the caretaker not to cut the grass.", True),
      ("Digging the pond during the autumn term.", False),
      ("Counting the eleven new species of insect.", False),
      ("Finding a patch of waste ground to use.", False)],
     "She expected the pond to be hardest, but the passage says it was 'persuading the caretaker "
     "to leave the grass long that took the most convincing'."),
    ("ENG", "Reading Comprehension", "mcq",
     "The Year 6 class turned a patch of waste ground behind the science block into a wildlife "
     "garden. They dug a small pond in the autumn, and by the following June they had counted "
     "eleven species of insect that had never been recorded on the school grounds before. "
     "Mrs Achebe, who supervised the project, admitted she had expected the pond to be the "
     "hardest part; in the end it was persuading the caretaker to leave the grass long that "
     "took the most convincing.",
     "The word 'admitted' suggests that Mrs Achebe was:",
     [("accepting that she had expected the wrong thing.", True),
      ("angry that the project had been delayed.", False),
      ("uninterested in how the garden turned out.", False),
      ("giving the class a firm instruction.", False)],
     "To 'admit' something is to accept it, often a little reluctantly — here she accepts that "
     "her expectation about the pond was mistaken."),
    ("ENG", "Grammar & Punctuation", "mcq", "",
     "Which sentence is punctuated correctly?",
     [("After the rain stopped, we walked to the park.", True),
      ("After the rain stopped we walked, to the park.", False),
      ("After, the rain stopped we walked to the park.", False),
      ("After the rain, stopped we walked to the park.", False)],
     "A comma belongs after the introductory clause 'After the rain stopped' — and nowhere else "
     "in the sentence."),
    ("ENG", "Spelling", "mcq", "",
     "Which word is spelled correctly?",
     [("necessary", True), ("neccessary", False), ("necesary", False), ("neccesary", False)],
     "'Necessary' has one c and two s's. A useful reminder: a shirt has one Collar and two Sleeves."),
    ("ENG", "Vocabulary", "mcq", "",
     "Which word is most nearly OPPOSITE in meaning to 'scarce'?",
     [("plentiful", True), ("unusual", False), ("fragile", False), ("hidden", False)],
     "'Scarce' means in short supply, so its opposite is 'plentiful'. 'Unusual' is closer to a "
     "synonym than an antonym."),

    # ---- Maths ----
    ("MAT", "Number & Place Value", "mcq", "",
     "What is the value of the digit 7 in the number 3,470,912?",
     [("70,000", True), ("7,000", False), ("700,000", False), ("7", False)],
     "In 3,470,912 the 7 sits in the ten-thousands column, so it is worth 7 x 10,000 = 70,000."),
    ("MAT", "Four Operations", "mcq", "",
     "A coach carries 52 passengers. How many coaches are needed to carry 1,000 passengers?",
     [("20", True), ("19", False), ("19.2", False), ("21", False)],
     "1,000 divided by 52 is 19 remainder 12. Those last 12 passengers still need a coach, so "
     "20 coaches are needed."),
    ("MAT", "Fractions, Decimals & Percentages", "mcq", "",
     "What is 35% of 240?",
     [("84", True), ("74", False), ("96", False), ("80", False)],
     "10% of 240 is 24, so 30% is 72. 5% is 12. 72 + 12 = 84."),
    ("MAT", "Ratio & Proportion", "mcq", "",
     "Sam and Tia share 45 pounds in the ratio 4:5. How much does Tia receive?",
     [("25 pounds", True), ("20 pounds", False), ("22.50 pounds", False), ("27 pounds", False)],
     "There are 4 + 5 = 9 equal parts, so each part is 45 / 9 = 5 pounds. Tia's 5 parts are "
     "worth 5 x 5 = 25 pounds."),
    ("MAT", "Measurement", "mcq", "",
     "A film starts at 18:45 and lasts 1 hour 50 minutes. What time does it finish?",
     [("20:35", True), ("20:25", False), ("19:35", False), ("20:45", False)],
     "18:45 plus 1 hour is 19:45. Adding the remaining 50 minutes gives 20:35."),

    # ---- Verbal Reasoning ----
    ("VR", "Analogies", "mcq", "",
     "Foot is to Shoe as Hand is to _____?",
     [("Glove", True), ("Finger", False), ("Wrist", False), ("Wave", False)],
     "A shoe is the item of clothing worn on a foot, so the item worn on a hand is a glove. "
     "Finger and wrist are parts of the hand, not things worn on it."),
    ("VR", "Odd One Out", "mcq", "",
     "Which is the odd one out: oak, birch, ivy, willow, beech?",
     [("ivy", True), ("oak", False), ("willow", False), ("beech", False)],
     "Oak, birch, willow and beech are all trees. Ivy is a climbing plant."),
    ("VR", "Codes & Sequences", "mcq", "",
     "If CAT is written in code as DBU, how is DOG written in the same code?",
     [("EPH", True), ("CNF", False), ("EPG", False), ("DPH", False)],
     "Each letter moves one place forward in the alphabet (C to D, A to B, T to U). So D to E, "
     "O to P and G to H, giving EPH."),
    ("VR", "Hidden & Compound Words", "mcq", "",
     "A four-letter word is hidden across the end of one word and the start of the next. Find it: "
     "'The chef made a superb owl-shaped cake.'",
     [("BOWL", True), ("SUPE", False), ("OWLS", False), ("HEFT", False)],
     "The end of 'superb' joins the start of 'owl': super|b owl gives BOWL."),
    ("VR", "Logic Problems", "mcq", "",
     "Five friends finish a race. Priya finishes ahead of Jack but behind Nia. Omar finishes "
     "last. Leo finishes between Jack and Omar. Who finishes second?",
     [("Priya", True), ("Nia", False), ("Jack", False), ("Leo", False)],
     "Nia beats Priya, who beats Jack; Omar is last and Leo is between Jack and Omar. The order "
     "is Nia, Priya, Jack, Leo, Omar — so Priya is second."),

    # ---- Non-Verbal Reasoning ----
    ("NVR", "Series & Sequences", "mcq", "",
     "A sequence of tile patterns grows by the same amount each time. The first three patterns "
     "use 4, 7 and 10 squares. How many squares does the fifth pattern use?",
     [("16", True), ("13", False), ("15", False), ("19", False)],
     "The pattern adds 3 squares each time: 4, 7, 10, 13, 16. The fifth pattern uses 16 squares."),
    ("NVR", "Rotation & Reflection", "mcq", "",
     "Which capital letter looks exactly the same after being rotated a half turn (180 degrees)?",
     [("H", True), ("F", False), ("G", False), ("P", False)],
     "H has rotational symmetry of order 2, so a half turn leaves it unchanged. F, G and P all "
     "look different once rotated."),
    ("NVR", "3D Shapes & Nets", "mcq", "",
     "A net is made of one square and four identical triangles. Which solid does it fold up to make?",
     [("A square-based pyramid", True), ("A cube", False),
      ("A triangular prism", False), ("A cone", False)],
     "The square forms the base and the four triangles fold up to meet at a single point, which "
     "is a square-based pyramid."),
]

# Target accuracy per subtopic, driving the shape of the demo dashboard.
# The story it tells: solid on Maths computation, shaky on spelling, codes and
# anything spatial — a common and believable 11+ profile. Section averages come
# out roughly MAT 72% > VR 62% > ENG 59% > NVR 54%, so the bar chart has a clear
# read and the focus-areas list is not a coin toss.
ACCURACY = {
    # English
    "Reading Comprehension": 0.71, "Grammar & Punctuation": 0.65,
    "Spelling": 0.43, "Vocabulary": 0.57,
    # Maths
    "Number & Place Value": 0.88, "Four Operations": 0.83,
    "Fractions, Decimals & Percentages": 0.61, "Ratio & Proportion": 0.54,
    "Measurement": 0.76,
    # Verbal Reasoning
    "Analogies": 0.69, "Odd One Out": 0.73, "Codes & Sequences": 0.47,
    "Hidden & Compound Words": 0.59, "Logic Problems": 0.64,
    # Non-Verbal Reasoning
    "Series & Sequences": 0.67, "Rotation & Reflection": 0.51, "3D Shapes & Nets": 0.45,
}

# The tutor's roster, beyond the primary demo student. `skill` shifts every
# subtopic accuracy for that pupil, so each row lands on a different overall
# figure and a different weakest area rather than 11 clones; `activity` scales
# how much history they have, so the Questions column varies too.
#   (email local part, full name, skill, activity)
# Target schools. FACTS ONLY — see goals.models.School for why there is no
# pass-mark field. Every entry ships verified=False and source_url blank: the
# names, areas and the fact that these are selective schools are safe, but nobody
# has checked the assessment details against each school's own admissions
# material, and the UI says so until someone does.
#   (slug, name, area, papers, admissions_body, test_window)
SCHOOLS = [
    ("wilsons", "Wilson's School", "Sutton", ["ENG", "MAT"],
     "Sutton selective eligibility test, then the school's own paper",
     "September, Year 6"),
    ("sutton-grammar", "Sutton Grammar School", "Sutton", ["ENG", "MAT"],
     "Sutton selective eligibility test, then the school's own paper",
     "September, Year 6"),
    ("wallington-county", "Wallington County Grammar School", "Sutton", ["ENG", "MAT"],
     "Sutton selective eligibility test, then the school's own paper",
     "September, Year 6"),
    ("tiffin", "The Tiffin School", "Kingston upon Thames", ["ENG", "MAT"],
     "Two-stage written assessment", "September, Year 6"),
    ("henrietta-barnett", "The Henrietta Barnett School", "Barnet", ["ENG", "MAT"],
     "Two-stage written assessment", "September, Year 6"),
    ("queen-elizabeths-barnet", "Queen Elizabeth's School", "Barnet", ["ENG", "MAT"],
     "Two-stage written assessment", "September, Year 6"),
    ("st-olaves", "St Olave's Grammar School", "Bromley", ["ENG", "MAT"],
     "Two-stage written assessment", "September, Year 6"),
    ("colchester-royal", "Colchester Royal Grammar School", "Essex", ["ENG", "MAT"],
     "Consortium entrance examination", "September, Year 6"),
    ("altrincham-boys", "Altrincham Grammar School for Boys", "Trafford",
     ["ENG", "MAT", "VR"], "Consortium entrance examination", "September, Year 6"),
    ("reading-school", "Reading School", "Reading", ["ENG", "MAT"],
     "Two-stage written assessment", "September, Year 6"),
    ("kendrick", "Kendrick School", "Reading", ["ENG", "MAT"],
     "Two-stage written assessment", "September, Year 6"),
]

# Deliberately identical for every school, and deliberately not a number. This is
# the honest description of how grammar-school selection actually works, and it
# is what the app shows instead of a fabricated cutoff.
SELECTION_NOTE = (
    "Places are awarded by rank against everyone else sitting the test that year, "
    "usually on age-standardised scores rather than a raw percentage. That means "
    "there is no fixed pass mark to quote, and the effective cutoff moves every "
    "year with the strength of the cohort. Set your own target below, and confirm "
    "the current requirements with the school directly."
)

# Goals for the demo roster. Varying the GOAL rather than the practice history is
# what produces a believable spread of on-track / at-risk / behind: a pupil six
# months out is genuinely on track at an hour a week, one three weeks out is not.
# Tuned against the pupils' actual seeded attainment so the roster shows a real
# mix rather than a wall of one status. Attainment keys off the WEAKEST required
# paper, not the average, so the target is set relative to that: within 5 points
# reads as at risk, further reads as behind.
#   (email local part, school slug, weeks until exam, target %, planned hours)
ROSTER_GOALS = [
    # Lead demo pupil. Aspirational target against a weak English paper (59%) —
    # behind on both attainment and pace, which is the story worth demonstrating.
    ("student", "wilsons", 11, 85, 78),
    ("theo", "st-olaves", 24, 82, 55),           # on target and pacing well
    ("freya", "henrietta-barnett", 30, 80, 70),  # on target
    ("maya", "tiffin", 18, 78, 24),              # a few points short
    ("priya", "wallington-county", 14, 68, 45),  # a few points short
    ("zainab", "sutton-grammar", 9, 74, 60),     # practising hard, short runway
    ("oliver", "reading-school", 12, 72, 52),
    ("daniel", "colchester-royal", 7, 70, 55),   # closest exam, furthest behind
    ("harry", "altrincham-boys", 16, 70, 40),
    ("samuel", "queen-elizabeths-barnet", 20, 72, 42),
    ("nina", "kendrick", 34, 70, 26),            # lopsided: strong Maths, weak English
]

# Per-paper targets that differ from the overall figure, to exercise the feature
# that matters for schools needing a strong mark in each paper separately.
# Everyone else inherits target_overall for each paper they sit.
PAPER_TARGET_OVERRIDES = {"student": {"ENG": 85, "MAT": 88}}

ROSTER = [
    ("priya", "Priya Sharma", +0.05, 0.9),
    ("theo", "Theo Ashworth", +0.18, 1.0),
    ("maya", "Maya Okonkwo", +0.09, 0.7),
    ("daniel", "Daniel Reeve", -0.17, 0.5),
    ("zainab", "Zainab Hussain", -0.04, 1.3),
    ("oliver", "Oliver Bancroft", -0.09, 0.8),
    ("freya", "Freya Lindqvist", +0.22, 1.1),
    ("samuel", "Samuel Adeyemi", -0.12, 0.9),
    ("nina", "Nina Kowalski", +0.02, 0.25),
    ("harry", "Harry Pemberton", -0.06, 0.6),
]


# Tags questions this command owns, mirroring import_pack's per-source scoping.
# Anything added through the admin has source="" and is never touched here.
SEED_SOURCE = "seed"


class Command(BaseCommand):
    help = "Seed demo data (sections, sample questions, demo users, attempt history)."

    def handle(self, *args, **options):
        random.seed(42)

        # Purge only sections that are no longer part of the 11+ taxonomy.
        # Deliberately NOT a blanket delete: that cascades into every question,
        # attempt and assignment, including admin-added content.
        stale = Section.objects.exclude(code__in=[code for code, _, _ in SECTIONS])
        if stale.exists():
            self.stdout.write(f"Purging retired sections: {[s.code for s in stale]}")
            stale.delete()

        # Sections + subtopics
        sec_by_code = {}
        for code, name, order in SECTIONS:
            sec, _ = Section.objects.get_or_create(code=code, defaults={"name": name, "order": order})
            sec.name, sec.order = name, order
            sec.save()
            sec_by_code[code] = sec

        # Build subtopics in declared order of first appearance
        sub_lookup = {}
        seen = []
        for q in QUESTIONS:
            key = (q[0], q[1])
            if key not in seen:
                seen.append(key)
        for i, (code, subname) in enumerate(seen):
            sub, _ = Subtopic.objects.get_or_create(
                section=sec_by_code[code], name=subname, defaults={"order": i}
            )
            sub_lookup[(code, subname)] = sub

        # Questions + options. Matched on stem rather than recreated, so question
        # IDs stay stable across deploys: deleting them would cascade into every
        # Attempt that references them. Stem-keyed (not subtopic-keyed) because
        # a question may since have been moved to a different subtopic.
        q_by_sub = {}
        created_count = 0
        for code, subname, kind, passage, stem, options, expl in QUESTIONS:
            sub = sub_lookup[(code, subname)]
            question = Question.objects.filter(stem=stem).first()
            if question is None:
                question = Question.objects.create(
                    subtopic=sub, kind=kind, passage=passage, stem=stem, explanation=expl,
                    difficulty=random.choice([1, 2, 2, 3]), source=SEED_SOURCE,
                    is_placeholder=True,  # seed content is disposable scaffold, not owned IP
                )
                for j, (text, correct) in enumerate(options):
                    AnswerOption.objects.create(question=question, text=text, is_correct=correct, order=j)
                created_count += 1
            elif question.source != SEED_SOURCE or not question.is_placeholder:
                # Tag questions seeded before this command became non-destructive / gained the flag.
                question.source = SEED_SOURCE
                question.is_placeholder = True
                question.save(update_fields=["source", "is_placeholder"])
            q_by_sub.setdefault(question.subtopic_id, []).append(question)

        # Users
        tutor = self._user("tutor@revisorplus.test", "Dr Amara Okafor", User.Role.TUTOR, "demo12345")
        student = self._user("student@revisorplus.test", "Isla Hartley", User.Role.STUDENT, "demo12345")
        roster = [
            (self._user(f"{local}@revisorplus.test", name, User.Role.STUDENT, "demo12345"),
             skill, activity)
            for local, name, skill, activity in ROSTER
        ]
        for s in [student] + [r[0] for r in roster]:
            TutorStudent.objects.get_or_create(tutor=tutor, student=s)
            Subscription.objects.get_or_create(user=s)

        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username="admin", email="admin@revisorplus.test", password="admin12345",
                role=User.Role.ADMIN, full_name="Site Admin",
            )

        # Options cached up front: generating history one query at a time would
        # be thousands of round trips on every deploy.
        opts_by_q = {}
        for q in Question.objects.filter(source=SEED_SOURCE).prefetch_related("options"):
            opts = list(q.options.all())
            opts_by_q[q.id] = (
                next((o for o in opts if o.is_correct), None),
                [o for o in opts if not o.is_correct],
            )

        # Backdated attempt history — first run per student only, so work done
        # during a live demo is preserved on the next deploy.
        now = timezone.now()
        if Attempt.objects.filter(student=student).exists():
            self.stdout.write("Demo student already has attempt history — leaving it alone.")
        else:
            # The primary student gets a longer, denser record: their dashboard
            # is the one presented, so the trend line needs enough points.
            self._history(student, sub_lookup, q_by_sub, opts_by_q, now, days=28)
            for s, skill, activity in roster:
                if not Attempt.objects.filter(student=s).exists():
                    self._history(s, sub_lookup, q_by_sub, opts_by_q, now,
                                  days=28, skill=skill, activity=activity)

        # Homework — first run only, so anything set during a demo survives a
        # redeploy. Spread across several students so the roster's Open HW
        # column is not a column of zeroes.
        if not Assignment.objects.filter(tutor=tutor).exists():
            homework = [
                (student, ("ENG", "Spelling"), 3),
                (student, ("NVR", "3D Shapes & Nets"), 5),
                (roster[0][0], ("VR", "Codes & Sequences"), 4),
                (roster[3][0], ("MAT", "Ratio & Proportion"), 2),
                (roster[3][0], ("ENG", "Vocabulary"), 6),
                (roster[5][0], ("NVR", "Rotation & Reflection"), 5),
                (roster[7][0], ("NVR", "3D Shapes & Nets"), 3),
                (roster[9][0], ("ENG", "Spelling"), 7),
            ]
            for pupil, key, due_in in homework:
                if key in sub_lookup:
                    Assignment.objects.create(
                        tutor=tutor, student=pupil, subtopic=sub_lookup[key],
                        target_count=5, due_date=(now + timedelta(days=due_in)).date(),
                    )

        # School catalogue — facts only, all unverified until a human checks them.
        for slug, name, area, paper_codes, body, window in SCHOOLS:
            school, _ = School.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name, "area": area, "admissions_body": body,
                    "test_window": window, "requirement_note": SELECTION_NOTE,
                    "verified": False, "active": True,
                },
            )
            school.papers.set([sec_by_code[c] for c in paper_codes if c in sec_by_code])

        # Targets — first run only, so a target set during a demo survives a redeploy.
        if not Goal.objects.exists():
            pupils = {u.email.split("@")[0]: u for u in [student] + [r[0] for r in roster]}
            for local, slug, weeks, target, hours in ROSTER_GOALS:
                pupil = pupils.get(local)
                school = School.objects.filter(slug=slug).first()
                if not pupil or not school:
                    continue
                goal = Goal.objects.create(
                    student=pupil, school=school,
                    exam_date=(now + timedelta(weeks=weeks)).date(),
                    target_overall=target, target_hours=hours,
                    weekly_hours_available=round(random.uniform(2.0, 5.0), 1),
                    set_by=Goal.SetBy.TUTOR,
                )
                # Per-paper targets on the papers that school actually sets, so a
                # weak single paper shows as a risk instead of hiding in an average.
                overrides = PAPER_TARGET_OVERRIDES.get(local, {})
                for section in school.papers.all():
                    SectionTarget.objects.create(
                        goal=goal, section=section,
                        target_accuracy=overrides.get(section.code, target),
                    )

        kept = Question.objects.exclude(source=SEED_SOURCE).count()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {Section.objects.count()} sections, {Subtopic.objects.count()} subtopics, "
            f"{Question.objects.count()} questions ({created_count} newly created, "
            f"{kept} user-added preserved), {Attempt.objects.count()} attempts."
        ))
        self.stdout.write(
            f"Roster: {TutorStudent.objects.filter(tutor=tutor).count()} students linked to the "
            f"demo tutor, {Assignment.objects.count()} homework assignments, "
            f"{Goal.objects.count()} targets set."
        )
        self.stdout.write(self.style.WARNING(
            f"  {School.objects.filter(verified=False).count()} of "
            f"{School.objects.count()} schools are UNVERIFIED — names and areas are "
            "safe, but the assessment details have not been checked against each "
            "school's own admissions material, and no pass marks are held (they are "
            "rank-based and not published). Verify before this is shown to parents."
        ))
        self.stdout.write("Logins:")
        self.stdout.write("  student@revisorplus.test / demo12345  (Isla Hartley)")
        self.stdout.write("  tutor@revisorplus.test   / demo12345  (Dr Amara Okafor)")
        self.stdout.write("  admin@revisorplus.test   / admin12345 (Django admin)")
        self.stdout.write(
            "  roster pupils use the same password, e.g. theo@revisorplus.test / demo12345"
        )

    def _history(self, student, sub_lookup, q_by_sub, opts_by_q, now,
                 days=28, skill=0.0, activity=1.0):
        """Backdate a practice record for one student.

        `skill` shifts every subtopic accuracy, `activity` scales how often they
        practised. Attempts are bulk-inserted — one INSERT per attempt would put
        thousands of round trips into every Render build.
        """
        subs = [s for s in sub_lookup.values() if q_by_sub.get(s.id)]
        if not subs:
            return 0

        active_chance = min(0.95, 0.72 * activity)
        rows = []
        for day in range(days, 0, -1):
            if random.random() > active_chance:
                continue  # rest day — nobody practises every single evening
            when = now - timedelta(
                days=day, hours=random.randint(0, 8), minutes=random.randint(0, 59)
            )
            for sub in random.sample(subs, k=min(len(subs), random.randint(1, 4))):
                questions = q_by_sub.get(sub.id, [])
                if not questions:
                    continue
                session = TestSession.objects.create(
                    student=student, subtopic=sub, mode=TestSession.Mode.PRACTICE
                )
                # Clamped so an extreme skill offset never gives a pupil a
                # subtopic they always or never get right.
                acc = min(0.95, max(0.15, ACCURACY.get(sub.name, 0.6) + skill))
                # Session length is sized so measured time-on-task lands in the
                # 1-3 h/week band real 11+ preparation actually occupies. The
                # readiness tracker reads those hours directly, so seeding a
                # tenth of a realistic workload made every pupil look hopelessly
                # behind whatever their plan said.
                for _ in range(random.randint(8, 18)):
                    question = random.choice(questions)
                    correct = random.random() < acc
                    right, wrong = opts_by_q.get(question.id, (None, []))
                    opt = right if correct else (random.choice(wrong) if wrong else None)
                    available = question.marks or 1
                    rows.append(Attempt(
                        session=session, student=student, question=question, subtopic=sub,
                        selected_option=opt, is_correct=correct,
                        marks_earned=available if correct else 0,
                        marks_available=available,
                        time_taken_ms=random.randint(15000, 90000),
                        source=Attempt.Source.PRACTICE, created_at=when,
                    ))
        Attempt.objects.bulk_create(rows, batch_size=500)
        return len(rows)

    def _user(self, email, full_name, role, password):
        u, created = User.objects.get_or_create(
            email=email,
            defaults={"username": email.split("@")[0], "full_name": full_name, "role": role},
        )
        if created:
            u.set_password(password)
            u.full_name = full_name
            u.role = role
            u.save()
        return u
