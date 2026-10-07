"""
The vocab trainer's logic. Views stay thin and call in here.

So far: which word pack a pupil gets. Round building, marking, spaced
repetition, XP and the streak arrive in stage 5.
"""
from analytics.readiness import active_goal
from goals.models import School

from .models import WordPack

GENERAL = "general"

# A school's entrance-test format -> the pack its pupils practise. The Sutton
# SET follows the GL format, so it gets the GL pack. Bespoke tests, schools with
# no format recorded, and pupils with no goal or no school all get GENERAL.
FORMAT_TO_PACK = {
    School.ExamFormat.GL: "gl",
    School.ExamFormat.SET: "gl",
}


def pack_slug_for(pupil):
    """The slug of the pack this pupil should practise."""
    goal = active_goal(pupil)
    exam_format = goal.school.exam_format if goal and goal.school else ""
    return FORMAT_TO_PACK.get(exam_format, GENERAL)


def pack_for(pupil):
    """This pupil's WordPack, or None if the packs have not been loaded.

    None rather than an exception: a deploy whose load_vocab failed should show
    the pupil "not available yet", not a server error.
    """
    return WordPack.objects.filter(slug=pack_slug_for(pupil)).first()
