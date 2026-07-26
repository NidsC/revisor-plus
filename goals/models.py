from django.conf import settings
from django.db import models
from django.utils import timezone


class School(models.Model):
    """A target school — publishable facts only.

    NOTE THE ABSENCE OF A PASS-MARK FIELD, AND DO NOT ADD ONE.

    Most UK grammar schools do not publish a fixed pass percentage. Selection is
    typically by age-standardised score and/or rank against the cohort ("the top
    N candidates are offered places"), so the effective cutoff is not knowable in
    advance and moves every year with the intake. Wilson's, for example, runs the
    Sutton SET as stage one and its own paper as stage two.

    Storing a threshold here would mean putting a number we invented next to a
    real school's name, in front of parents making decisions about their child's
    schooling. The numeric target lives on Goal instead, where it belongs to a
    named human (see Goal.set_by). Use `requirement_note` to describe how a school
    actually selects, in words, without asserting a figure.
    """

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    area = models.CharField(max_length=100, blank=True)  # "Sutton", "Trafford"
    admissions_body = models.CharField(max_length=150, blank=True)  # consortium / test used
    # Which papers candidates actually sit — drives which section targets a goal needs.
    papers = models.ManyToManyField("catalog.Section", blank=True, related_name="schools")
    test_window = models.CharField(max_length=80, blank=True)  # "September, Year 6"
    requirement_note = models.TextField(
        blank=True,
        help_text="How selection works, in words. Never state a pass mark unless it "
                  "is officially published — and record the source below if it is.",
    )
    source_url = models.URLField(blank=True)
    source_year = models.PositiveSmallIntegerField(null=True, blank=True)
    # False until a human has checked the details against the school's own
    # admissions material. Surfaced in the UI so seed data is never mistaken for
    # verified fact.
    verified = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["area", "name"]

    def __str__(self):
        return f"{self.name} ({self.area})" if self.area else self.name


class Goal(models.Model):
    """A pupil's target: which school, by when, and to what standard.

    Every number here is a plan input owned by a person, not a fact about the
    school. `set_by` records whose judgement it was.
    """

    class SetBy(models.TextChoices):
        STUDENT = "student", "Student"
        PARENT = "parent", "Parent"
        TUTOR = "tutor", "Tutor"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals"
    )
    # Nullable: "aiming at a grammar school, not decided which" is a real state,
    # and forcing the choice would push pupils into picking one arbitrarily.
    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="goals"
    )
    school_note = models.CharField(max_length=200, blank=True)  # school not in the catalogue

    exam_date = models.DateField()
    target_overall = models.PositiveSmallIntegerField(default=80)  # %

    # Total hours the plan assumes. An INPUT, not a prediction — the readiness
    # engine measures hours actually done and compares them against this.
    target_hours = models.PositiveSmallIntegerField(default=60)
    weekly_hours_available = models.FloatField(default=3.0)  # what the pupil says they can manage

    set_by = models.CharField(max_length=10, choices=SetBy.choices, default=SetBy.STUDENT)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} → {self.target_label} by {self.exam_date:%b %Y}"

    @property
    def target_label(self):
        if self.school:
            return self.school.name
        return self.school_note or "a grammar school"

    @property
    def days_remaining(self):
        return (self.exam_date - timezone.localdate()).days

    @property
    def has_passed(self):
        return self.days_remaining < 0

    def required_sections(self):
        """The papers this goal is judged on: the school's, else whatever is targeted."""
        if self.school_id:
            papers = list(self.school.papers.all())
            if papers:
                return papers
        return [t.section for t in self.section_targets.select_related("section")]


class SectionTarget(models.Model):
    """Per-paper target accuracy.

    Separate from `Goal.target_overall` because entry to a school like Wilson's
    needs a high mark in *both* English and Maths. A strong average carrying one
    weak paper does not get an offer, so a single overall figure would hide
    exactly the risk a tutor needs to see.
    """

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="section_targets")
    section = models.ForeignKey("catalog.Section", on_delete=models.CASCADE)
    target_accuracy = models.PositiveSmallIntegerField(default=80)  # %

    class Meta:
        unique_together = [("goal", "section")]
        ordering = ["section__order"]

    def __str__(self):
        return f"{self.section.code} >= {self.target_accuracy}%"
