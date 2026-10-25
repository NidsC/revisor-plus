"""Focused checks of the refreshed student journey and role navigation."""
from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from billing.entitlements import FREE_QUESTIONS_PER_PAPER
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


@override_settings(PREMIUM_GATES_ENABLED=False)
class ReviewTests(TestCase):
    """The Review tab: what is listed where, the retry deck, and session review."""

    @classmethod
    def setUpTestData(cls):
        cls.pupil = User.objects.create(username="rev", role="student")
        cls.other = User.objects.create(username="rev-other", role="student")
        cls.parent = User.objects.create(username="rev-parent", email="rp@example.test", role="parent")
        # Section order is the opposite of creation order, and subtopic order the
        # opposite of alphabetical, so a test can tell ordering from accident.
        cls.maths = Section.objects.create(code="MAT", name="Sec-Maths", order=1)
        cls.english = Section.objects.create(code="ENG", name="Sec-English", order=2)
        cls.zeta = Subtopic.objects.create(section=cls.maths, name="Sub-Zeta", order=1)
        cls.alpha = Subtopic.objects.create(section=cls.maths, name="Sub-Alpha", order=2)
        cls.eng = Subtopic.objects.create(section=cls.english, name="Sub-Eng", order=1)
        cls.q_zeta = cls._mcq(cls.zeta, "Stem-Zeta")
        cls.q_alpha = cls._mcq(cls.alpha, "Stem-Alpha")
        cls.q_eng = cls._mcq(cls.eng, "Stem-Eng")
        cls.q_other = cls._mcq(cls.zeta, "Stem-Never-Attempted")
        cls.q_rubric = Question.objects.create(
            subtopic=cls.alpha, stem="Stem-Rubric", kind=Question.Kind.EXTENDED_TEXT,
            marking=Question.Marking.RUBRIC,
        )

    @staticmethod
    def _mcq(subtopic, stem):
        q = Question.objects.create(subtopic=subtopic, stem=stem)
        AnswerOption.objects.create(question=q, text=f"{stem} right", is_correct=True)
        AnswerOption.objects.create(question=q, text=f"{stem} wrong", is_correct=False)
        return q

    def setUp(self):
        self.client.force_login(self.pupil)
        self.tick = 0

    def _attempt(self, pupil, q, correct, mode="practice", awaiting=False):
        self.tick += 1
        stamp = timezone.now() - timedelta(days=1) + timedelta(minutes=self.tick)
        session = TestSession.objects.create(
            student=pupil, subtopic=None if mode == "mock" else q.subtopic, mode=mode,
            finished_at=stamp,
        )
        option = q.options.filter(is_correct=correct).first()
        return Attempt.objects.create(
            session=session, student=pupil, question=q, subtopic=q.subtopic,
            selected_option=option, is_correct=correct and not awaiting,
            awaiting_marking=awaiting, created_at=stamp,
        )

    def _page(self, query=""):
        """The review page's (To review, Reviewed) HTML halves."""
        response = self.client.get(reverse("practice:review") + query)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        head, rest = html.split('<h2 class="h5">Reviewed', 1)
        return head, rest

    def _one_question_session(self):
        """Drive start -> answer -> next -> summary for a one-question deck."""
        self.client.get(reverse("practice:start", args=[self.eng.pk]) + "?count=1")
        qid = self.client.session["deck"]["qids"][0]
        right = AnswerOption.objects.get(question_id=qid, is_correct=True)
        self.client.post(reverse("practice:answer"), {"option": right.pk, "qid": qid})
        self.client.get(reverse("practice:next"))
        summary = self.client.get(reverse("practice:summary"))
        return TestSession.objects.filter(student=self.pupil).latest("id"), summary

    def test_wrong_then_right_moves_to_reviewed(self):
        self._attempt(self.pupil, self.q_zeta, False)
        self._attempt(self.pupil, self.q_zeta, True)
        to_review, reviewed = self._page()
        self.assertNotIn("Stem-Zeta", to_review)
        self.assertIn("Stem-Zeta", reviewed)
        self.assertIn("Wrong 1 time,", reviewed)

    def test_latest_wrong_stays_in_to_review_with_count(self):
        self._attempt(self.pupil, self.q_zeta, True)
        self._attempt(self.pupil, self.q_zeta, False)
        self._attempt(self.pupil, self.q_alpha, False)
        self._attempt(self.pupil, self.q_alpha, True)
        self._attempt(self.pupil, self.q_alpha, False)
        to_review, reviewed = self._page()
        self.assertIn("Stem-Zeta", to_review)
        self.assertIn("Stem-Alpha", to_review)
        self.assertIn("Wrong 2 times,", to_review)
        self.assertNotIn("Stem-Alpha", reviewed)

    def test_awaiting_marking_is_pending_never_reviewed(self):
        self._attempt(self.pupil, self.q_rubric, False, awaiting=True)
        to_review, reviewed = self._page()
        self.assertIn("Stem-Rubric", to_review)
        self.assertIn("waiting to be marked", to_review)
        self.assertNotIn(reverse("practice:retry", args=[self.q_rubric.pk]), to_review)
        self.assertNotIn("Stem-Rubric", reviewed)

    def test_try_again_sits_inside_its_card(self):
        self._attempt(self.pupil, self.q_zeta, False)
        self._attempt(self.pupil, self.q_alpha, False)
        to_review, _ = self._page()
        card = to_review[to_review.index("Stem-Zeta"):]
        card = card[:card.index("Try again")]
        self.assertIn(reverse("practice:retry", args=[self.q_zeta.pk]), card)
        self.assertNotIn("border rounded", card)

    def test_groups_follow_section_then_subtopic_order(self):
        self._attempt(self.pupil, self.q_eng, False)
        self._attempt(self.pupil, self.q_alpha, False)
        self._attempt(self.pupil, self.q_zeta, False)
        to_review, _ = self._page()
        positions = [to_review.index(name) for name in
                     ("Sec-Maths", "Sub-Zeta", "Sub-Alpha", "Sec-English", "Sub-Eng")]
        self.assertEqual(positions, sorted(positions))

    def test_mock_badge_and_filter(self):
        self._attempt(self.pupil, self.q_zeta, False, mode="mock")
        self._attempt(self.pupil, self.q_alpha, False)
        to_review, _ = self._page()
        self.assertIn('ms-1">Mock</span>', to_review)
        self.assertIn('ms-1">Practice</span>', to_review)
        only_mock, _ = self._page("?view=mock")
        self.assertIn("Stem-Zeta", only_mock)
        self.assertNotIn("Stem-Alpha", only_mock)
        only_practice, _ = self._page("?view=practice")
        self.assertIn("Stem-Alpha", only_practice)
        self.assertNotIn("Stem-Zeta", only_practice)
        bogus, _ = self._page("?view=bogus")
        self.assertIn("Stem-Zeta", bogus)
        self.assertIn("Stem-Alpha", bogus)

    def test_retry_deals_a_deck_and_a_correct_answer_moves_it_to_reviewed(self):
        self._attempt(self.pupil, self.q_zeta, False)
        before = TestSession.objects.filter(student=self.pupil).count()
        response = self.client.post(reverse("practice:retry", args=[self.q_zeta.pk]))
        self.assertRedirects(response, reverse("practice:question"), fetch_redirect_response=False)
        self.assertEqual(TestSession.objects.filter(student=self.pupil).count(), before + 1)
        self.assertContains(self.client.get(reverse("practice:question")), "Stem-Zeta")
        right = AnswerOption.objects.get(question=self.q_zeta, is_correct=True)
        self.client.post(reverse("practice:answer"), {"option": right.pk, "qid": self.q_zeta.pk})
        to_review, reviewed = self._page()
        self.assertNotIn("Stem-Zeta", to_review)
        self.assertIn("Stem-Zeta", reviewed)

    def test_retry_refuses_get_unknown_and_unanswerable_questions(self):
        self._attempt(self.pupil, self.q_zeta, False)
        self._attempt(self.pupil, self.q_rubric, False, awaiting=True)
        before = TestSession.objects.count()
        self.assertEqual(self.client.get(reverse("practice:retry", args=[self.q_zeta.pk])).status_code, 405)
        self.assertEqual(TestSession.objects.count(), before)
        self.assertEqual(self.client.post(reverse("practice:retry", args=[self.q_other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("practice:retry", args=[self.q_rubric.pk])).status_code, 404)
        self.assertEqual(TestSession.objects.count(), before)

    @override_settings(PREMIUM_GATES_ENABLED=True)
    def test_retry_respects_the_free_cap(self):
        session = TestSession.objects.create(student=self.pupil, subtopic=self.zeta, finished_at=timezone.now())
        Attempt.objects.bulk_create([
            Attempt(session=session, student=self.pupil, question=self.q_zeta, subtopic=self.zeta,
                    is_correct=False, tier=Attempt.Tier.FREE, source=Attempt.Source.PRACTICE)
            for _ in range(FREE_QUESTIONS_PER_PAPER)
        ])
        before = TestSession.objects.count()
        response = self.client.post(reverse("practice:retry", args=[self.q_zeta.pk]))
        self.assertRedirects(response, reverse("practice:choose"), fetch_redirect_response=False)
        self.assertIn("free Sec-Maths questions", " ".join(str(m) for m in get_messages(response.wsgi_request)))
        self.assertEqual(TestSession.objects.count(), before)

    def test_session_review_access_and_rendering(self):
        foreign = self._attempt(self.other, self.q_zeta, False).session
        self.assertEqual(self.client.get(reverse("practice:session_review", args=[foreign.pk])).status_code, 404)
        session, _ = self._one_question_session()
        self.assertNotIn("deck", self.client.session)
        response = self.client.get(reverse("practice:session_review", args=[session.pk]))
        self.assertContains(response, "You put")
        mock = self._attempt(self.pupil, self.q_zeta, False, mode="mock").session
        redirected = self.client.get(reverse("practice:session_review", args=[mock.pk]))
        self.assertRedirects(redirected, reverse("practice:mock_result"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("practice:mock_result")).status_code, 200)
        self.client.force_login(self.parent)
        self.assertRedirects(
            self.client.get(reverse("practice:session_review", args=[session.pk])),
            reverse("after_login"), fetch_redirect_response=False,
        )

    def test_summary_links_to_the_session_review(self):
        session, summary = self._one_question_session()
        self.assertContains(summary, reverse("practice:session_review", args=[session.pk]))

    def test_mock_result_still_renders_the_answers(self):
        mock = self._attempt(self.pupil, self.q_zeta, False, mode="mock").session
        stored = self.client.session
        stored["last_mock"] = mock.pk
        stored.save()
        response = self.client.get(reverse("practice:mock_result"))
        self.assertContains(response, "You put")
        self.assertContains(response, "Answer:")
