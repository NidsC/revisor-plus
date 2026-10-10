"""Focused checks of the refreshed student journey and role navigation."""
from django.test import TestCase, override_settings
from django.urls import reverse
from accounts.models import User
from catalog.models import Section, Subtopic, Question, AnswerOption
from practice.models import Attempt, TestSession
from analytics.services import compute_subject_summary


@override_settings(PREMIUM_GATES_ENABLED=False)
class StudentJourneyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pupil = User.objects.create(username="alex", role="student")
        cls.parent = User.objects.create(username="parent", email="parent@example.test", role="parent")
        cls.tutor = User.objects.create(username="tutor", email="tutor@example.test", role="tutor")
        cls.section = Section.objects.create(code="MAT", name="Maths")
        cls.topic = Subtopic.objects.create(section=cls.section, name="Fractions", topic="Number")
        cls.q = Question.objects.create(subtopic=cls.topic, stem="What is half of 8?")
        cls.answer = AnswerOption.objects.create(question=cls.q, text="4", is_correct=True)
        AnswerOption.objects.create(question=cls.q, text="8", is_correct=False)

    def setUp(self):
        self.client.force_login(self.pupil)

    def test_role_specific_dashboard_redirects(self):
        for user, destination in [(self.parent, "family:home"), (self.tutor, "tutoring:dashboard")]:
            self.client.force_login(user)
            # Two hops since the pupils-only gate: the gate sends non-pupils to
            # after_login, which then sends them to their own home.
            self.assertRedirects(
                self.client.get(reverse("practice:dashboard")), reverse("after_login"),
                fetch_redirect_response=False,
            )
            self.assertRedirects(
                self.client.get(reverse("after_login")), reverse(destination),
                fetch_redirect_response=False,
            )

    def test_student_has_a_name_and_no_parent_dashboard(self):
        response = self.client.get(reverse("practice:dashboard"))
        self.assertContains(response, "alex")
        self.assertNotContains(response, "Parent dashboard")
        self.assertContains(response, "Ready when you are")
        self.assertContains(response, "aria-current=\"page\"")

    def test_accuracy_is_distinct_from_bank_coverage(self):
        Question.objects.create(subtopic=self.topic, stem="Another question")
        session = TestSession.objects.create(student=self.pupil, subtopic=self.topic)
        Attempt.objects.create(student=self.pupil, session=session, question=self.q, subtopic=self.topic, is_correct=True)
        summary = compute_subject_summary(self.pupil)[0]
        self.assertEqual(summary["recent_accuracy"], 100)
        self.assertEqual(summary["pct_complete"], 50)
        response = self.client.get(reverse("practice:dashboard"))
        self.assertContains(response, "100% accuracy · last 30 days")

    def test_parent_assigned_homework_is_labelled_as_parent(self):
        from assignments.models import Assignment
        from django.utils import timezone
        Assignment.objects.create(tutor=self.parent, student=self.pupil, subtopic=self.topic, due_date=timezone.localdate())
        self.assertContains(self.client.get(reverse("practice:dashboard")), "From your parent")

    def test_question_renders_readable_text_and_answer_can_be_submitted(self):
        response = self.client.get(reverse("practice:start", args=[self.topic.pk]) + "?count=1", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What is half of 8?")
        self.assertNotContains(response, "â€")
        self.assertContains(response, "Question 1 of 1")
        self.client.post(reverse("practice:answer"), {"option": self.answer.pk})
        self.assertEqual(Attempt.objects.filter(student=self.pupil, is_correct=True).count(), 1)

    def test_pause_and_resume_preserve_question(self):
        self.client.get(reverse("practice:start", args=[self.topic.pk]) + "?count=1")
        self.client.get(reverse("practice:pause"))
        response = self.client.get(reverse("practice:dashboard"))
        self.assertContains(response, "Continue practice")
        session = TestSession.objects.get(student=self.pupil)
        resumed = self.client.get(reverse("practice:resume", args=[session.pk]), follow=True)
        self.assertContains(resumed, self.q.stem)

    def test_practice_subject_controls_still_target_correct_endpoints(self):
        response = self.client.get(reverse("practice:choose"))
        self.assertContains(response, reverse("practice:start_subject", args=["MAT"]))
        self.assertContains(response, reverse("practice:start", args=[self.topic.pk]))
        response = self.client.get(reverse("practice:subject_detail", args=["MAT"]))
        self.assertContains(response, 'id="practiceModal"')
        self.assertContains(response, 'max="40"')
