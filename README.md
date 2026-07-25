# RevisorPlus

11+ practice and tutoring platform. Sister product to MedRevisor (the UCAT platform) —
this repo was forked from it and converted, so nothing UCAT-specific should remain.

**Deploy URL:** _not yet deployed — add the Render link here once it is live._
(The old `medrevisor.onrender.com` link belongs to MedRevisor, a different product.)

## Logins

You can create your own account as a student.

| Role | Email | Password | What they can do |
|------|-------|----------|------------------|
| Student | `student@revisorplus.test` | `demo12345` | Practise, see progress analytics, complete homework |
| Tutor | `tutor@revisorplus.test` | `demo12345` | Oversee student progress, assign and track homework |
| Admin | `admin@revisorplus.test` | `admin12345` | Full system access at `/admin/` — tutor accounts, payments, data, and adding/removing questions |

## Papers

Four sections, matching the 11+ papers: **English (ENG)**, **Maths (MAT)**,
**Verbal Reasoning (VR)** and **Non-Verbal Reasoning (NVR)**. All questions are multiple
choice.

## Questions

The bank is built from JSON packs in `elevenplus_data/`. Anything named `contrib_*.json`
is auto-imported on deploy, so a merged pack goes live without touching `build.sh`.
See `elevenplus_data/CLAUDE.md` for the authoring contract and `CONTRIBUTOR_QUICKSTART.md`
for the non-developer walkthrough. CI validates every pack on the PR.

## Tech stack

- Backend: Python 3.12 + Django 5.1
- Auth: django-allauth (email login, role-based: student/tutor/admin)
- Frontend: Django templates + Bootstrap 5 + Chart.js
- Database: SQLite (local) → PostgreSQL (production)
- Payments: Stripe (test-mode Checkout)
- Serving: Gunicorn + WhiteNoise (static files)
- Hosting: Render (web service + managed Postgres)
- Version control: Git / GitHub

## Known TODOs

- [ ] **Landing page** — cleared during the 11+ conversion and currently a holding page.
      The old copy made UCAT and question-count claims that aren't true here. See the
      `TODO` comment in `templates/pages/landing.html`.
- [ ] **Deploy URL** — fill in above once RevisorPlus has its own Render service.
- [ ] **Question bank is empty** — only the 18 sample questions from `seed_demo` exist.
      Real content arrives as `contrib_*.json` packs.
- [ ] **NVR needs figures** — genuine non-verbal questions require images in
      `static/questions/`; the seeded NVR samples are text-only stand-ins.
