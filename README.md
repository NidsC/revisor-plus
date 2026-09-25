# RevisorPlus

11+ practice and tutoring platform. Sister product to MedRevisor (the UCAT platform) —
this repo was forked from it and converted, so nothing UCAT-specific should remain.

**Deploy URL:** <https://revisorplus.onrender.com> — live since 2026-08-25, backed by
Postgres. It runs on Render's free tier, so the instance sleeps after 15 minutes idle
and the first request after that takes roughly 30 seconds while it wakes.
(The old `medrevisor.onrender.com` link belongs to MedRevisor, a different product.)

## Logins

You can create your own account as a parent or a tutor. Pupils never self-register — a
parent creates their child's login from their own `/family/` dashboard.

Parents and tutors can also sign in with Google, once `GOOGLE_OAUTH_CLIENT_ID` and
`GOOGLE_OAUTH_CLIENT_SECRET` are set in the environment (the button only appears when
both are present). Pupils never can: the adapter refuses a Google login whose email
belongs to a pupil, and a Google login is never auto-connected to an existing parent
or tutor account by email — an adult connects it themselves from inside their own
logged-in session.

Demo accounts (parent, student, tutor) are only created when `seed_demo` is run with
`DJANGO_DEBUG=1`, or with `DEMO_ACCOUNT_PASSWORD` / `DEMO_SHOWCASE_PASSWORD` set in the
environment — no demo passwords are published here, and none exist in production unless
those variables are explicitly set. A production superuser is created separately with
`python main.py createsuperuser` (guarded by `DEMO_ADMIN_PASSWORD` where applicable), not
seeded with a published password.

| Role | What they can do |
|------|------------------|
| Parent | Create and manage their children's logins, see each child's progress and homework on their own parent dashboard at `/family/child/<id>/`, message the tutor |
| Student | Practise, see progress analytics, complete homework |
| Tutor | Oversee student progress, assign and track homework |
| Admin | Full system access at `/admin/` — tutor accounts, payments, data, and adding/removing questions |

## Payments

Stripe subscriptions, one per child, £29.99/month, paid by the parent (the parent is the
Stripe Customer). `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` and `STRIPE_WEBHOOK_SECRET` are
set in the Render dashboard environment, not in `render.yaml` (a blueprint cannot
generate them and must not contain them). `PREMIUM_GATES_ENABLED` stays `"0"` until the
owner's live green light, even once Stripe is otherwise fully wired — subscriptions sync
regardless of the gate; only the gate decides whether anyone is actually locked out.

To rehearse the webhook locally against Stripe's own test-mode events:

```
stripe listen --forward-to 127.0.0.1:8000/billing/webhook/
# prints a signing secret — export it before starting runserver:
export STRIPE_WEBHOOK_SECRET=whsec_...
python main.py runserver
stripe trigger customer.subscription.updated
```

The runserver log should show a 200 for the forwarded event. (Not run in this session —
the `stripe` CLI isn't available in this environment; every other Phase C check runs
against monkeypatched Stripe calls in `test_billing.py` instead.)

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
- Auth: django-allauth (email login for adults, username for pupils; role-based: parent/student/tutor/admin), plus optional Google sign-in for parents and tutors (`allauth.socialaccount`)
- Frontend: Django templates + Bootstrap 5 + Chart.js
- Database: SQLite (local) → PostgreSQL (production)
- Payments: Stripe subscriptions (Checkout + signed webhook + Customer Portal), test mode until the live green light
- Serving: Gunicorn + WhiteNoise (static files)
- Hosting: Render (web service + managed Postgres)
- Version control: Git / GitHub

## Question bank

~4,600 questions, generated procedurally by `main.py generate_bank` and balanced
across the four papers (roughly 1,150 each). Difficulty is derived from each
question's parameters rather than assigned, and every wrong option records the
mistake it represents so feedback can name the slip. Re-running is safe: questions
are matched on `gen_key`, so a regenerate never deletes a question a pupil has
answered. Non-verbal figures are drawn as SVG from stored parameters — no image
files involved.

Two author-written exam papers live in `elevenplus_data/` and import via
`main.py import_paper`.

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
