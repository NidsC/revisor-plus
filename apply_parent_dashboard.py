from pathlib import Path
import re
import shutil
from datetime import datetime

ROOT = Path(__file__).resolve().parent

FILES = {
    "dashboard": ROOT / "templates" / "practice" / "dashboard.html",
    "base": ROOT / "templates" / "base.html",
    "views": ROOT / "practice" / "views.py",
    "urls": ROOT / "practice" / "urls.py",
    "parent_template": ROOT / "templates" / "practice" / "parent_dashboard.html",
}

def load(path):
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    return text, newline

def save(path, text, newline="\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if newline == "\r\n":
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))

def matching_div_end(text, start):
    tag_re = re.compile(r"</?div\b[^>]*>", re.I)
    depth = 0
    started = False
    for m in tag_re.finditer(text, start):
        tag = m.group(0).lower()
        if tag.startswith("</div"):
            depth -= 1
        else:
            depth += 1
            started = True
        if started and depth == 0:
            return m.end()
    raise RuntimeError("Could not find the closing </div> for a dashboard section.")

def backup(paths):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = ROOT / ".parent-dashboard-backup" / stamp
    for path in paths:
        if path.exists():
            rel = path.relative_to(ROOT)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return dest

def main():
    missing = [str(p.relative_to(ROOT)) for k, p in FILES.items()
               if k != "parent_template" and not p.exists()]
    if missing:
        print("ERROR: This patch must be placed in the RevisorPlus project root.")
        print("Missing:", ", ".join(missing))
        input("\nPress Enter to close...")
        return

    backup_dir = backup([
        FILES["dashboard"], FILES["base"], FILES["views"],
        FILES["urls"], FILES["parent_template"]
    ])

    dashboard, dashboard_nl = load(FILES["dashboard"])

    # 1) Pull the existing Parent summary UI out of the student dashboard.
    parent_token = '<div class="kid-dash__view" id="parent-view"'
    parent_start = dashboard.find(parent_token)

    if parent_start >= 0:
        parent_start = dashboard.rfind("\n", 0, parent_start) + 1
        parent_end = matching_div_end(dashboard, parent_start)
        parent_block = dashboard[parent_start:parent_end]

        # Remove only the outer hidden tab-panel wrapper.
        first_gt = parent_block.find(">")
        last_close = parent_block.rfind("</div>")
        parent_inner = parent_block[first_gt + 1:last_close].strip("\n")

        parent_template = '''{% extends "base.html" %}
{% load account %}
{% load static %}
{% block title %}Parent summary — RevisorPlus{% endblock %}

{% block extra_head %}
<link rel="stylesheet" href="{% static 'student_portals/dashboard.css' %}?v=10">
{% endblock %}

{% block main_class %}rp-bleed py-4{% endblock %}

{% block main %}
<div class="kid-dash">
  {% user_display user as pupil_name %}
  <div class="kid-dash__shell">
%s
  </div>
</div>
{% endblock %}
''' % parent_inner

        save(FILES["parent_template"], parent_template, dashboard_nl)
        dashboard = dashboard[:parent_start] + dashboard[parent_end:]
        print("OK: Created templates/practice/parent_dashboard.html")
    elif FILES["parent_template"].exists():
        print("OK: Parent template already exists.")
    else:
        raise RuntimeError(
            "Could not find the existing Parent summary panel in "
            "templates/practice/dashboard.html."
        )

    # 2) Remove the student/parent toggle bar.
    tabs_token = '<div class="kid-dash__tabs"'
    tabs_start = dashboard.find(tabs_token)
    if tabs_start >= 0:
        tabs_start = dashboard.rfind("\n", 0, tabs_start) + 1
        tabs_end = matching_div_end(dashboard, tabs_start)
        dashboard = dashboard[:tabs_start] + dashboard[tabs_end:]
        print("OK: Removed dashboard toggle tabs.")

    # Student view is no longer a tab panel.
    dashboard = re.sub(
        r'<div class="kid-dash__view"\s+id="student-view"\s+role="tabpanel"\s+'
        r'aria-labelledby="student-tab"\s+data-dashboard-view="student">',
        '<div class="kid-dash__view">',
        dashboard,
        count=1,
    )

    # Remove old tab JavaScript.
    scripts = list(re.finditer(r"<script\b[^>]*>.*?</script>", dashboard, re.S | re.I))
    for m in reversed(scripts):
        if "data-dashboard-tab" in m.group(0) or "parent-summary" in m.group(0):
            dashboard = dashboard[:m.start()] + dashboard[m.end():]
            print("OK: Removed old tab JavaScript.")

    save(FILES["dashboard"], dashboard, dashboard_nl)

    # 3) Add dedicated parent_dashboard view.
    views, views_nl = load(FILES["views"])
    if "def parent_dashboard(request):" not in views:
        insertion_marker = "\n\n# The question bank page states"
        insert_at = views.find(insertion_marker)
        if insert_at < 0:
            insert_at = len(views)

        parent_view = r'''

@login_required
def parent_dashboard(request):
    # Dedicated parent-facing progress summary.
    data = compute_progress(request.user)

    section_names = {s["code"]: s["name"] for s in data["sections"]}
    for weakness in data["weak"]:
        weakness["section_name"] = section_names.get(
            weakness["section"], weakness["section"]
        )

    assignments = Assignment.objects.filter(student=request.user).select_related(
        "subtopic", "subtopic__section"
    )
    for assignment in assignments:
        assignment.refresh_status()
        assignment.done = assignment.progress_count()
        assignment.pct_done = (
            min(100, round(100 * assignment.done / assignment.target_count))
            if assignment.target_count else 100
        )

    pending_assignments = [
        assignment for assignment in assignments
        if assignment.status == Assignment.Status.ASSIGNED
    ]

    strongest_section = max(
        (section for section in data["sections"] if section["total"] > 0),
        key=lambda section: section["accuracy"],
        default=None,
    )

    readiness = compute_readiness(request.user, progress=data)

    return render(request, "practice/parent_dashboard.html", {
        "data": data,
        "pending_assignments": pending_assignments,
        "homework_count": len(pending_assignments),
        "section_by_code": {s["code"]: s for s in data["sections"]},
        "strongest_section": strongest_section,
        "readiness": readiness,
        "overall_accuracy": data["overall"],
        "questions_done": data["total"],
    })
'''
        views = views[:insert_at] + parent_view + views[insert_at:]
        save(FILES["views"], views, views_nl)
        print("OK: Added parent_dashboard view.")
    else:
        print("OK: parent_dashboard view already exists.")

    # 4) Add /parent/ route.
    urls, urls_nl = load(FILES["urls"])
    if 'name="parent_dashboard"' not in urls:
        dashboard_route = '    path("dashboard/", views.dashboard, name="dashboard"),'
        replacement = (
            dashboard_route
            + '\n    path("parent/", views.parent_dashboard, name="parent_dashboard"),'
        )
        if dashboard_route not in urls:
            raise RuntimeError("Could not find dashboard route in practice/urls.py.")
        urls = urls.replace(dashboard_route, replacement, 1)
        save(FILES["urls"], urls, urls_nl)
        print("OK: Added /parent/ URL.")
    else:
        print("OK: Parent URL already exists.")

    # 5) Add Parent to the main navbar beside My target.
    base, base_nl = load(FILES["base"])
    if "practice:parent_dashboard" not in base:
        target_link = '<a class="nav-link d-inline" href="{% url \'goals:detail\' %}">My target</a>'
        parent_link = (
            target_link
            + '\n        <a class="nav-link d-inline" '
              'href="{% url \'practice:parent_dashboard\' %}">Parent</a>'
        )

        if target_link in base:
            base = base.replace(target_link, parent_link, 1)
        else:
            pattern = re.compile(
                r'(?P<indent>[ \t]*)<a(?P<attrs>[^>]*href="\{% url \'goals:detail\' %\}"[^>]*)>'
                r'My target</a>'
            )
            m = pattern.search(base)
            if not m:
                raise RuntimeError(
                    "Could not find the My target navbar link in templates/base.html."
                )
            original = m.group(0)
            indent = m.group("indent")
            new = (
                original
                + '\n' + indent
                + '<a class="nav-link d-inline" '
                  'href="{% url \'practice:parent_dashboard\' %}">Parent</a>'
            )
            base = base[:m.start()] + new + base[m.end():]

        save(FILES["base"], base, base_nl)
        print("OK: Added Parent to main navigation.")
    else:
        print("OK: Parent nav link already exists.")

    print("\nDONE.")
    print("Parent summary is now its own top-level page:")
    print("http://127.0.0.1:8000/parent/")
    print("Backups saved to:", backup_dir.relative_to(ROOT))
    print("\nIf Django runserver is already running, it should reload automatically.")
    input("\nPress Enter to close...")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nPATCH FAILED:", exc)
        print("A backup was created before the patch started.")
        input("\nPress Enter to close...")
