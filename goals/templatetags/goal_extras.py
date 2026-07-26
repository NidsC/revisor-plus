from django import template

from analytics import readiness as R

register = template.Library()

# Bootstrap contextual class per status. Kept in one place so the dashboard,
# tracker panel and tutor roster cannot drift into disagreeing about what
# "at risk" looks like.
_CLASSES = {
    R.READY: "bg-success",
    R.ON_TRACK: "bg-success",
    R.AT_RISK: "bg-warning text-dark",
    R.BEHIND: "bg-danger",
    R.NOT_STARTED: "bg-secondary",
    R.EXAM_PASSED: "bg-secondary",
    R.NO_GOAL: "bg-light text-dark",
}


@register.filter
def status_class(status):
    return _CLASSES.get(status, "bg-secondary")


@register.filter
def status_label(status):
    return R.STATUS_LABEL.get(status, "—")
