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

# Target accuracy per subtopic to create clear strengths/weaknesses in the dashboard.
ACCURACY = {
    "Reading Comprehension": 0.68, "Grammar & Punctuation": 0.74, "Spelling": 0.46,
    "Vocabulary": 0.58,
    "Number & Place Value": 0.86, "Four Operations": 0.80,
    "Fractions, Decimals & Percentages": 0.55, "Ratio & Proportion": 0.62, "Measurement": 0.78,
    "Analogies": 0.70, "Odd One Out": 0.66, "Codes & Sequences": 0.48,
    "Hidden & Compound Words": 0.52, "Logic Problems": 0.60,
    "Series & Sequences": 0.72, "Rotation & Reflection": 0.56, "3D Shapes & Nets": 0.50,
}


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
        student = self._user("student@revisorplus.test", "Jordan Ellis", User.Role.STUDENT, "demo12345")
        student2 = self._user("priya@revisorplus.test", "Priya Sharma", User.Role.STUDENT, "demo12345")
        for s in (student, student2):
            TutorStudent.objects.get_or_create(tutor=tutor, student=s)
            Subscription.objects.get_or_create(user=s)

        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username="admin", email="admin@revisorplus.test", password="admin12345",
                role=User.Role.ADMIN, full_name="Site Admin",
            )

        # Backdated attempt history for the primary demo student — first run only,
        # so anything done during a live demo is preserved on the next deploy.
        now = timezone.now()
        if Attempt.objects.filter(student=student).exists():
            self.stdout.write("Demo student already has attempt history — leaving it alone.")
        else:
            for day in range(21, 0, -1):
                when = now - timedelta(days=day, hours=random.randint(0, 6))
                # each "day" practise 1-2 random subtopics
                for sub in random.sample(list(sub_lookup.values()), k=random.randint(1, 2)):
                    questions = q_by_sub.get(sub.id, [])
                    if not questions:
                        continue
                    session = TestSession.objects.create(
                        student=student, subtopic=sub, mode=TestSession.Mode.PRACTICE
                    )
                    acc = ACCURACY.get(sub.name, 0.6)
                    for _ in range(random.randint(3, 6)):
                        question = random.choice(questions)
                        correct = random.random() < acc
                        opt = (question.correct_option() if correct
                               else question.options.filter(is_correct=False).first())
                        Attempt.objects.create(
                            session=session, student=student, question=question, subtopic=sub,
                            selected_option=opt, is_correct=correct,
                            time_taken_ms=random.randint(15000, 90000),
                            source=Attempt.Source.PRACTICE, created_at=when,
                        )

        # A couple of assignments — first run only, so homework set during a demo
        # (and the student's progress against it) survives redeployment.
        if not Assignment.objects.filter(tutor=tutor).exists():
            weak = sub_lookup[("ENG", "Spelling")]
            weak2 = sub_lookup[("VR", "Codes & Sequences")]
            Assignment.objects.create(
                tutor=tutor, student=student, subtopic=weak,
                target_count=5, due_date=(now + timedelta(days=3)).date(),
            )
            Assignment.objects.create(
                tutor=tutor, student=student, subtopic=weak2,
                target_count=5, due_date=(now + timedelta(days=5)).date(),
            )

        kept = Question.objects.exclude(source=SEED_SOURCE).count()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {Section.objects.count()} sections, {Subtopic.objects.count()} subtopics, "
            f"{Question.objects.count()} questions ({created_count} newly created, "
            f"{kept} user-added preserved), {Attempt.objects.count()} attempts."
        ))
        self.stdout.write("Logins:")
        self.stdout.write("  student@revisorplus.test / demo12345  (Jordan Ellis)")
        self.stdout.write("  tutor@revisorplus.test   / demo12345  (Dr Amara Okafor)")
        self.stdout.write("  admin@revisorplus.test   / admin12345 (Django admin)")

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
