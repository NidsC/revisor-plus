from datetime import timedelta

from django import forms
from django.utils import timezone

from catalog.models import Section

from .models import Goal, School, SectionTarget


class GoalForm(forms.ModelForm):
    """Set or change a target.

    Per-paper targets are rendered as one field per section rather than an
    inline formset: a parent setting this up on a phone should see four plain
    number boxes, not a formset with add/delete controls.
    """

    class Meta:
        model = Goal
        fields = ["school", "school_note", "exam_date", "target_overall",
                  "target_hours", "weekly_hours_available"]
        widgets = {
            "exam_date": forms.DateInput(attrs={"type": "date"}),
            "school_note": forms.TextInput(
                attrs={"placeholder": "e.g. St Olave's — only if not in the list above"}
            ),
            "target_overall": forms.NumberInput(attrs={"min": 40, "max": 100, "step": 1}),
            "target_hours": forms.NumberInput(attrs={"min": 1, "max": 2000, "step": 5}),
            "weekly_hours_available": forms.NumberInput(
                attrs={"min": 0.5, "max": 40, "step": 0.5}
            ),
        }
        labels = {
            "school": "Target school",
            "school_note": "Other school",
            "exam_date": "Exam date",
            "target_overall": "Target score (%)",
            "target_hours": "Total practice hours you're planning",
            "weekly_hours_available": "Hours a week you can realistically do",
        }
        help_texts = {
            "school": "Schools are listed for reference only — we don't hold their "
                      "pass marks, because most aren't published.",
            "target_overall": "Your own target, not the school's. Used as the "
                              "fallback for any paper without its own target below.",
            "target_hours": "A plan, not a prediction. We measure the hours you "
                            "actually do and compare them against this.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["school"].queryset = School.objects.filter(active=True)
        self.fields["school"].required = False
        self.fields["school"].empty_label = "Not decided yet"
        if not self.instance.pk:
            # Default to the usual 11+ window: September of the next school year.
            today = timezone.localdate()
            year = today.year if today.month < 9 else today.year + 1
            self.fields["exam_date"].initial = f"{year}-09-10"

        existing = {}
        if self.instance.pk:
            existing = {t.section_id: t.target_accuracy
                        for t in self.instance.section_targets.all()}
        self.section_fields = []
        for section in Section.objects.all():
            name = f"target_{section.code}"
            self.fields[name] = forms.IntegerField(
                required=False, min_value=0, max_value=100,
                initial=existing.get(section.id),
                label=f"{section.name} target (%)",
                widget=forms.NumberInput(attrs={"min": 0, "max": 100, "placeholder": "—"}),
            )
            self.section_fields.append((section, name))

        # Bootstrap classes applied here rather than repeated on every widget
        # declaration above, and last so the generated section fields get them too.
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

    @property
    def section_bound_fields(self):
        """(section, BoundField) pairs, so the template can render each paper's
        target box directly instead of hunting through the whole form."""
        return [(section, self[name]) for section, name in self.section_fields]

    def clean_exam_date(self):
        date = self.cleaned_data["exam_date"]
        # A past date silently produces an "exam passed" tracker, which looks like
        # a bug to whoever typed it. Reject it at the door instead.
        if date < timezone.localdate() - timedelta(days=1):
            raise forms.ValidationError("That date has already passed — pick the date of the exam you're preparing for.")
        return date

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("school") and not (cleaned.get("school_note") or "").strip():
            # Not an error: "undecided" is a legitimate state the model supports.
            pass
        return cleaned

    def save(self, commit=True, set_by=None):
        goal = super().save(commit=False)
        if set_by:
            goal.set_by = set_by
        if commit:
            goal.save()
            for section, name in self.section_fields:
                value = self.cleaned_data.get(name)
                if value:
                    SectionTarget.objects.update_or_create(
                        goal=goal, section=section,
                        defaults={"target_accuracy": value},
                    )
                else:
                    SectionTarget.objects.filter(goal=goal, section=section).delete()
        return goal
