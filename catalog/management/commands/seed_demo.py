"""
Seed the Med-revisor demo with ORIGINAL UCAT-style content (not PMT material),
demo users, and a backdated attempt history so dashboards show real trends.

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
    ("VR", "Verbal Reasoning", 1),
    ("DM", "Decision Making", 2),
    ("QR", "Quantitative Reasoning", 3),
    ("SJT", "Situational Judgement", 4),
]

# Original questions. Each: section, subtopic, kind, passage, stem, options, explanation.
# options: list of (text, is_correct)
QUESTIONS = [
    # ---- Verbal Reasoning ----
    ("VR", "Reading Comprehension", "mcq",
     "A community pharmacy trialled a text-message reminder service for patients collecting repeat "
     "prescriptions. Over six months, missed collections fell by 18%, though uptake of the service was "
     "highest among patients under 40.",
     "Which conclusion is best supported by the passage?",
     [("The reminder service reduced missed collections during the trial.", True),
      ("Text reminders eliminate missed prescriptions entirely.", False),
      ("Older patients benefited most from the service.", False),
      ("The service will cut costs for every pharmacy.", False)],
     "Only the first option restates evidence given; the others overstate or contradict the passage."),
    ("VR", "Reading Comprehension", "mcq",
     "The hospital's new triage protocol prioritises patients by clinical urgency rather than arrival "
     "time. Early audit data suggest shorter waits for the most unwell, but slightly longer waits for "
     "minor complaints.",
     "According to the passage, the protocol changed prioritisation based on:",
     [("clinical urgency", True), ("arrival time", False),
      ("patient age", False), ("staff availability", False)],
     "The passage states prioritisation is by clinical urgency rather than arrival time."),
    ("VR", "Critical Reasoning", "mcq",
     "A study found that students who used spaced practice scored higher on a mock exam than those who "
     "crammed. Both groups spent the same total hours studying.",
     "Which statement, if true, most strengthens the claim that spacing caused the higher scores?",
     [("The two groups were similar in prior attainment and only differed in study schedule.", True),
      ("The spaced group happened to include more high achievers.", False),
      ("The crammers studied a different syllabus.", False),
      ("The mock exam was taken on different days.", False)],
     "Controlling for prior attainment isolates schedule as the cause; the others introduce confounders."),
    ("VR", "Inference (True/False/Can't Tell)", "tf",
     "Applicants to the programme must complete an interview and submit two references. Shortlisting is "
     "based solely on the personal statement.",
     "Statement: An applicant with weak references but a strong personal statement could still be "
     "shortlisted.",
     [("True", True), ("False", False), ("Can't Tell", False)],
     "Shortlisting is stated to be based solely on the personal statement, so references do not affect it."),
    ("VR", "Inference (True/False/Can't Tell)", "tf",
     "The library extends its opening hours during examination periods. It does not change its hours at "
     "any other time of year.",
     "Statement: The library is open later on public holidays.",
     [("True", False), ("False", False), ("Can't Tell", True)],
     "Nothing is said about public holidays specifically, so it cannot be determined."),

    # ---- Decision Making ----
    ("DM", "Logical Puzzles", "mcq",
     "",
     "Four doctors — P, Q, R, S — are on call on consecutive days, one each day, Monday to Thursday. "
     "Q is on call the day before R. P is not on Monday. S is on Thursday. Who is on call on Monday?",
     [("Q", True), ("P", False), ("R", False), ("S", False)],
     "S is Thursday. Q immediately precedes R, so Q-R occupy Tue-Wed. P is not Monday, so Q must be "
     "Monday? Check: if Q-R are Tue-Wed, Monday is P or... P not Monday leaves Q, but Q is Tue. "
     "So Q-R = Mon-Tue, R=Tue, P=Wed, S=Thu — Monday is Q."),
    ("DM", "Syllogisms", "mcq",
     "",
     "All members of the surgical team scrubbed in. Some who scrubbed in are consultants. "
     "Which conclusion necessarily follows?",
     [("Some members of the surgical team may be consultants.", True),
      ("All consultants are on the surgical team.", False),
      ("No consultants scrubbed in.", False),
      ("Every consultant scrubbed in.", False)],
     "From the premises only a possibility (some) can be inferred, not a universal claim."),
    ("DM", "Probability & Statistics", "mcq",
     "",
     "A bag holds 3 red and 5 blue tokens. One token is drawn at random. What is the probability it "
     "is red?",
     [("3/8", True), ("5/8", False), ("3/5", False), ("1/3", False)],
     "3 red out of 8 total = 3/8."),
    ("DM", "Probability & Statistics", "mcq",
     "",
     "A test correctly identifies a condition 90% of the time. If 200 patients have the condition, "
     "roughly how many would the test correctly identify?",
     [("180", True), ("90", False), ("120", False), ("200", False)],
     "90% of 200 = 180."),

    # ---- Quantitative Reasoning ----
    ("QR", "Arithmetic", "mcq",
     "",
     "A ward has 24 beds and is currently 75% occupied. How many beds are free?",
     [("6", True), ("18", False), ("8", False), ("4", False)],
     "75% of 24 = 18 occupied, so 24 - 18 = 6 free."),
    ("QR", "Arithmetic", "mcq",
     "",
     "A drug is dosed at 5 mg per kg of body weight. What dose does a 12 kg child need?",
     [("60 mg", True), ("17 mg", False), ("50 mg", False), ("72 mg", False)],
     "5 mg x 12 kg = 60 mg."),
    ("QR", "Percentages", "mcq",
     "",
     "A clinic saw 250 patients in March and 300 in April. What was the percentage increase?",
     [("20%", True), ("50%", False), ("16.7%", False), ("25%", False)],
     "(300-250)/250 = 50/250 = 20%."),
    ("QR", "Percentages", "mcq",
     "",
     "An item costs £80 after a 20% discount. What was the original price?",
     [("£100", True), ("£96", False), ("£64", False), ("£120", False)],
     "£80 is 80% of the original, so original = 80 / 0.8 = £100."),
    ("QR", "Data Interpretation", "mcq",
     "",
     "A chart shows monthly admissions: Jan 40, Feb 60, Mar 50. What is the mean monthly admission "
     "over the three months?",
     [("50", True), ("60", False), ("45", False), ("55", False)],
     "(40+60+50)/3 = 150/3 = 50."),

    # ---- Situational Judgement ----
    ("SJT", "Professionalism", "mcq",
     "",
     "A medical student notices a peer has copied answers in an online assessment. What is the most "
     "appropriate first action?",
     [("Speak to the peer privately and encourage them to report it.", True),
      ("Ignore it, as it is not their concern.", False),
      ("Post about it in the group chat.", False),
      ("Copy answers too, to be fair.", False)],
     "Addressing it directly and encouraging self-reporting is the professional, proportionate step."),
    ("SJT", "Patient Safety", "mcq",
     "",
     "A student on placement sees a colleague about to give a medication without checking the patient's "
     "wristband. What should they do?",
     [("Politely prompt the colleague to check the patient's identity first.", True),
      ("Say nothing to avoid embarrassment.", False),
      ("Wait until after to mention it.", False),
      ("Assume the colleague knows best.", False)],
     "Patient safety takes priority; a timely, respectful prompt prevents a potential error."),
    ("SJT", "Teamwork", "mcq",
     "",
     "During a group task, one team member is dominating and others are disengaging. What is the best "
     "response?",
     [("Invite quieter members to share their views to rebalance the discussion.", True),
      ("Let the dominant member decide everything.", False),
      ("Compete to talk over them.", False),
      ("Leave the group.", False)],
     "Actively including others restores balanced teamwork without escalating conflict."),
]

# Target accuracy per subtopic to create clear strengths/weaknesses in the dashboard.
ACCURACY = {
    "Reading Comprehension": 0.62, "Critical Reasoning": 0.52, "Inference (True/False/Can't Tell)": 0.44,
    "Logical Puzzles": 0.70, "Syllogisms": 0.64, "Probability & Statistics": 0.58,
    "Arithmetic": 0.86, "Percentages": 0.80, "Data Interpretation": 0.74,
    "Professionalism": 0.72, "Patient Safety": 0.60, "Teamwork": 0.50,
}


# Tags questions this command owns, mirroring import_pmt's per-source scoping.
# Anything added through the admin has source="" and is never touched here.
SEED_SOURCE = "seed"


class Command(BaseCommand):
    help = "Seed demo data for Med-revisor."

    def handle(self, *args, **options):
        random.seed(42)

        # Purge only sections that are no longer part of the UCAT (e.g. Abstract
        # Reasoning). Deliberately NOT a blanket delete: that cascades into every
        # question, attempt and assignment, including admin-added content.
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
        # reclassify_taxonomy may have moved a question to a different subtopic.
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
        tutor = self._user("tutor@medrevisor.test", "Dr Amara Okafor", User.Role.TUTOR, "demo12345")
        student = self._user("student@medrevisor.test", "Jordan Ellis", User.Role.STUDENT, "demo12345")
        student2 = self._user("priya@medrevisor.test", "Priya Sharma", User.Role.STUDENT, "demo12345")
        for s in (student, student2):
            TutorStudent.objects.get_or_create(tutor=tutor, student=s)
            Subscription.objects.get_or_create(user=s)

        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username="admin", email="admin@medrevisor.test", password="admin12345",
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
            weak = sub_lookup[("VR", "Inference (True/False/Can't Tell)")]
            weak2 = sub_lookup[("SJT", "Teamwork")]
            Assignment.objects.create(
                tutor=tutor, student=student, subtopic=weak,
                target_count=5, due_date=(now + timedelta(days=3)).date(),
            )
            Assignment.objects.create(
                tutor=tutor, student=student, subtopic=weak2,
                target_count=5, due_date=(now + timedelta(days=5)).date(),
            )

        kept = Question.objects.exclude(source=SEED_SOURCE).exclude(source__startswith="PMT").count()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {Section.objects.count()} sections, {Subtopic.objects.count()} subtopics, "
            f"{Question.objects.count()} questions ({created_count} newly created, "
            f"{kept} user-added preserved), {Attempt.objects.count()} attempts."
        ))
        self.stdout.write("Logins:")
        self.stdout.write("  student@medrevisor.test / demo12345  (Jordan Ellis)")
        self.stdout.write("  tutor@medrevisor.test   / demo12345  (Dr Amara Okafor)")
        self.stdout.write("  admin@medrevisor.test   / admin12345 (Django admin)")

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
