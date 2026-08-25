# RevisorPlus

11+ practice and tutoring platform. Sister product to MedRevisor (the UCAT platform) —
this repo was forked from it and converted, so nothing UCAT-specific should remain.

**Deploy URL:** <https://revisorplus.onrender.com> — live since 2026-08-25, backed by
Postgres. It runs on Render's free tier, so the instance sleeps after 15 minutes idle
and the first request after that takes roughly 30 seconds while it wakes.
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

## Question bank

~4,600 questions, generated procedurally by `manage.py generate_bank` and balanced
across the four papers (roughly 1,150 each). Difficulty is derived from each
question's parameters rather than assigned, and every wrong option records the
mistake it represents so feedback can name the slip. Re-running is safe: questions
are matched on `gen_key`, so a regenerate never deletes a question a pupil has
answered. Non-verbal figures are drawn as SVG from stored parameters — no image
files involved.

Two author-written exam papers live in `elevenplus_data/` and import via
`manage.py import_paper`.

## Known TODOs

- [ ] **Deploy URL** — fill in above once RevisorPlus has its own Render service.
- [ ] **Adaptive selection** — `practice.views.start()` still picks at random.
      `difficulty` is recorded on every question but no query reads it yet, so the
      landing page deliberately claims weakness targeting rather than adaptivity.
- [ ] **Nothing is gated behind Premium** — a free account currently gets the whole
      product. Pricing describes the plan honestly, but there is no paywall.
- [ ] **Written answers have nowhere to go** — rubric-marked questions set
      `awaiting_marking` and no tutor marking queue exists to clear it.
- [ ] **Thin subtopics** — Reading Comprehension (5, needs passages), VR Analogies
      (29) and NVR Rotation (49) are limited by source data, not by the generator.
- [ ] **SQLite is rebuilt on every deploy** — see the note in `render.yaml`. Fine
      while the bank is generated; not fine once anyone authors via the admin.
