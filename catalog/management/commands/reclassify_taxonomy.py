"""
Reclassify the question bank to the official UCAT taxonomy.

Idempotent and content-keyed (subtopic names + stem/image text), so it runs the
same way on a fresh Render DB after seed_demo + all import_pmt commands.

Run:  python manage.py reclassify_taxonomy
"""
from django.core.management.base import BaseCommand

from catalog.models import Question, Section, Subtopic


def _sub(section, name):
    return Subtopic.objects.get_or_create(section=section, name=name)[0]


def merge(section, old_name, new_name):
    """Repoint all questions from old_name subtopic to new_name, then delete the empty old one."""
    old = Subtopic.objects.filter(section=section, name=old_name).first()
    if not old:
        return
    new = _sub(section, new_name)
    if old.id != new.id:
        Question.objects.filter(subtopic=old).update(subtopic=new)
        old.delete()


def repoint(qs, section, name):
    qs.update(subtopic=_sub(section, name))


# DM Yes/No scenarios that are data/scenario deductions, not categorical logic → Interpreting Information
DM_INTERPRETING_PREFIXES = [
    "During the weekdays, there are 3 direct flights",
    "Charlotte has three exams starting Monday",
    "A neurosurgeon has surgery at 5pm",
    "Bennie has 6 bikes to repair",
    "Lydia's pencil case has 25 pencils",
    "Set point weight theory",
    "ELRM is a conglomerate",
    "Among all married people who have an affair",
]


class Command(BaseCommand):
    help = "Reclassify subtopics to the official UCAT taxonomy."

    def handle(self, *args, **opts):
        VR = Section.objects.get(code="VR")
        DM = Section.objects.get(code="DM")
        QR = Section.objects.get(code="QR")

        # ---------------- VR ----------------
        merge(VR, "Critical Reasoning", "Reading Comprehension")

        # ---------------- DM ----------------
        merge(DM, "Evaluating Arguments", "Recognising Assumptions")
        merge(DM, "Probability & Statistics", "Probabilistic Reasoning")
        syll = Subtopic.objects.filter(section=DM, name="Syllogisms").first()
        if syll:
            interp = _sub(DM, "Interpreting Information")
            for prefix in DM_INTERPRETING_PREFIXES:
                Question.objects.filter(subtopic=syll, passage__startswith=prefix).update(subtopic=interp)

        # ---------------- QR (re-cut into 7) ----------------
        qr = Question.objects.filter(subtopic__section=QR)
        # 1) Geometry (leave Data Interpretation before parent merges)
        repoint(qr.filter(image__icontains="dancefloor"), QR, "Geometry & Measurement")
        repoint(Question.objects.filter(subtopic__section=QR, image__icontains="floorplan"),
                QR, "Geometry & Measurement")
        # 2) Averages & Statistics
        repoint(Question.objects.filter(subtopic__section=QR, stem__icontains="mean monthly admission"),
                QR, "Averages & Statistics")
        merge(QR, "Tables & Statistics", "Averages & Statistics")
        # 3) Ratios, Proportion & Units
        repoint(Question.objects.filter(subtopic__section=QR, stem__icontains="drug is dosed"),
                QR, "Ratios, Proportion & Units")
        merge(QR, "Ratios & Units", "Ratios, Proportion & Units")
        # 4) Rates: Speed, Distance & Time
        merge(QR, "Rates & Time", "Rates: Speed, Distance & Time")
        # 5) Percentages (pull ward-occupancy out of Arithmetic, hCG out of Percentages & Money)
        repoint(Question.objects.filter(subtopic__section=QR, stem__icontains="currently 75% occupied"),
                QR, "Percentages")
        repoint(Question.objects.filter(subtopic__section=QR, stem__icontains="hCG"), QR, "Percentages")
        # 6) Money & Finance (everything left in Percentages & Money)
        merge(QR, "Percentages & Money", "Money & Finance")
        # 7) Arithmetic is now empty (drug dose → Ratios, ward beds → Percentages)
        merge(QR, "Arithmetic", "Percentages")  # safety: any stragglers go to Percentages
        # Data Interpretation keeps its name.

        # ---------------- cleanup: drop any empty subtopics ----------------
        removed = 0
        for st in Subtopic.objects.all():
            if st.questions.count() == 0:
                st.delete()
                removed += 1

        self.stdout.write(self.style.SUCCESS(f"Reclassified taxonomy; removed {removed} empty subtopics."))
        for sec in Section.objects.order_by("order"):
            names = list(Subtopic.objects.filter(section=sec).order_by("name").values_list("name", flat=True))
            self.stdout.write(f"  {sec.code}: {', '.join(names)}")
