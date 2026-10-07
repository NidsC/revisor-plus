"""Regression coverage for the parent dashboard's child-scoped progress links."""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from assignments.models import Assignment
from catalog.models import Section, Subtopic, Question, AnswerOption
from practice.models import Attempt, TestSession
from tutoring.models import TutorStudent, TutorMessage


@override_settings(PREMIUM_GATES_ENABLED=False)
class FamilyDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.parent = User.objects.create_user(username="parent", email="parent@example.test", role="parent")
        cls.other_parent = User.objects.create_user(username="other", email="other@example.test", role="parent")
        cls.pupil = User.objects.create(username="ben", full_name="Ben", parent=cls.parent, role="student")
        cls.sibling = User.objects.create(username="sibling", full_name="Maya", parent=cls.parent, role="student")
        cls.unrelated = User.objects.create(username="other-child", parent=cls.other_parent, role="student")
        cls.tutor = User.objects.create_user(username="tutor", email="tutor@example.test", full_name="Sam", role="tutor")
        for i, (code, name) in enumerate([("MAT", "Maths"), ("ENG", "English"), ("VR", "Verbal Reasoning"), ("NVR", "Non-Verbal Reasoning")]):
            Section.objects.create(code=code, name=name, order=i)
        cls.section = Section.objects.get(code="MAT")
        cls.topic = Subtopic.objects.create(section=cls.section, name="Fractions", topic="Number")
        cls.question = Question.objects.create(subtopic=cls.topic, stem="What is half of 8?")
        AnswerOption.objects.create(question=cls.question, text="4", is_correct=True)
        session = TestSession.objects.create(student=cls.pupil, subtopic=cls.topic)
        for _ in range(3):
            Attempt.objects.create(student=cls.pupil, session=session, question=cls.question,
                                   subtopic=cls.topic, is_correct=True, marks_earned=1)
        cls.link = TutorStudent.objects.create(student=cls.pupil, tutor=cls.tutor)

    def setUp(self):
        self.client.force_login(self.parent)
        self.child_url = reverse("family:child", args=[self.pupil.pk])
        self.subject_url = reverse("family:child_subject", args=[self.pupil.pk, "MAT"])

    def test_child_links_use_selected_child(self):
        response = self.client.get(self.child_url)
        self.assertEqual(response.status_code, 200)
        for code in ["MAT", "ENG", "VR", "NVR"]:
            self.assertContains(response, reverse("family:child_subject", args=[self.pupil.pk, code]))
        self.assertNotContains(response, 'href="/practice/subject/')

    def test_parent_sees_child_data_and_cannot_start_from_read_only_view(self):
        response = self.client.get(self.subject_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pupil"], self.pupil)
        topic = response.context["subtopics"][0]
        self.assertEqual((topic["attempted"], topic["accuracy"]), (3, 100))
        self.assertContains(response, "Ben's subject progress")
        self.assertNotContains(response, 'id="practiceModal"')
        self.assertNotContains(response, 'href="/practice/start/')
        self.assertContains(response, f'href="{self.child_url}"')

    def test_siblings_have_separate_results(self):
        response = self.client.get(reverse("family:child_subject", args=[self.sibling.pk, "MAT"]))
        self.assertEqual(response.context["subtopics"][0]["attempted"], 0)
        self.assertIsNone(response.context["subtopics"][0]["accuracy"])

    def test_other_parents_cannot_open_child_or_subject(self):
        self.client.force_login(self.other_parent)
        self.assertEqual(self.client.get(self.child_url).status_code, 403)
        self.assertEqual(self.client.get(self.subject_url).status_code, 403)

    def test_pupil_and_tutor_cannot_open_parent_routes(self):
        for user in [self.pupil, self.tutor]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.child_url).status_code, 403)
            self.assertEqual(self.client.get(self.subject_url).status_code, 403)

    def test_unauthenticated_visitors_are_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.subject_url).status_code, 302)

    def test_missing_child_or_subject_returns_404(self):
        self.assertEqual(self.client.get(reverse("family:child_subject", args=[9999, "MAT"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("family:child_subject", args=[self.pupil.pk, "UNKNOWN"])).status_code, 404)

    @override_settings(PREMIUM_GATES_ENABLED=True)
    def test_parent_detail_keeps_premium_gate(self):
        self.assertRedirects(self.client.get(self.subject_url), self.child_url)

    def test_zero_attempts_have_empty_state_not_zero_accuracy(self):
        response = self.client.get(reverse("family:child", args=[self.sibling.pk]))
        self.assertContains(response, "A fresh start in maths.")
        self.assertContains(response, "<strong>—</strong>", html=True)
        self.assertNotContains(response, "0% current accuracy")

    def test_homework_can_be_created_and_removed(self):
        self.client.post(self.child_url, {"action": "add_homework", "subtopic": self.topic.pk,
                         "target_count": "8", "due_date": (timezone.localdate() + timedelta(days=7)).isoformat()})
        assignment = Assignment.objects.get(student=self.pupil)
        self.assertEqual(assignment.target_count, 8)
        self.assertEqual(assignment.tutor, self.parent)
        self.client.post(self.child_url, {"action": "delete_homework", "assignment_id": assignment.pk})
        self.assertFalse(Assignment.objects.filter(pk=assignment.pk).exists())

    def test_parent_cannot_remove_tutor_homework(self):
        assignment = Assignment.objects.create(student=self.pupil, tutor=self.tutor, subtopic=self.topic,
                                               due_date=timezone.localdate())
        self.assertEqual(self.client.post(self.child_url, {"action": "delete_homework", "assignment_id": assignment.pk}).status_code, 404)
        self.assertTrue(Assignment.objects.filter(pk=assignment.pk).exists())

    def test_tutor_message_stays_with_selected_child(self):
        self.client.post(self.child_url, {"action": "send_tutor_message", "message": "Could we review fractions?"})
        message = TutorMessage.objects.get()
        self.assertEqual(message.link, self.link)
        self.assertEqual(message.sender, self.parent)
        self.assertContains(self.client.get(self.child_url), "Could we review fractions?")

    def test_parent_nav_has_family_instead_of_student_tools(self):
        response = self.client.get(reverse("family:home"))
        self.assertContains(response, "My family")
        self.assertNotContains(response, 'href="/practice/"')
        self.assertNotContains(response, 'href="/mocks/"')
