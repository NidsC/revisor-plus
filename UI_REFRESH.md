# RevisorPlus — UI refresh

The existing Django application now has a quieter, more consistent visual design. The project structure and deployment approach stay compatible with the original upload. No new runtime dependencies or database migrations are introduced by this update.

## What changed

- A shared palette, spacing, rounded cards, consistent buttons, keyboard focus styles and clear navigation.
- A student dashboard with one next step, four subject cards, manageable tasks and a calmer introduction to mock papers.
- A parent dashboard with properly styled subject cards, expandable topic breakdowns, clearer empty states, section shortcuts and responsive homework/message layouts.
- A family overview with distinct child cards and a clearer add-child form.
- A simpler practice chooser: four subjects initially, with topics available on demand. Untimed practice is the primary action.
- A more comfortable question layout, a question-position indicator, readable punctuation and encouraging session summaries.
- A refreshed homepage that matches the learning area.

## Bugs fixed

1. Parent subject links now use `/family/child/<pupil_id>/subject/<code>/` and load that child's results. The detail page is read-only and checks ownership and Premium access.
2. Parents and tutors opening `/dashboard/` are routed to their respective dashboards. Parent navigation shows family tools.
3. Pupil accounts without an email or full name show their username in the account menu.
4. Student subject bars show recent accuracy, with a matching label. The old bars showed bank coverage under an accuracy heading.
5. Missing parent subject/topic/password-form styles are implemented. Unstarted subjects show an empty state instead of an apparent 0% result.
6. Hovering over practice subjects no longer changes padding or enlarges text, so rows do not jump around.
7. Saved practice counts are clamped to the current allowance when the modal opens. Arrow keys work between timed and untimed choices.
8. The homework form correctly hides, announces its expanded state, and focuses the topic selector when opened.
9. Parent-set homework is attributed to the parent on the student dashboard.
10. Garbled punctuation on the question page is corrected. Error notifications use the correct Bootstrap colour, and dismissal buttons have accessible names.
11. Auth checkbox/radio controls no longer inherit full-width text-input styling.
12. The obsolete installer instructions are corrected. Legacy dashboard/portal installers detect the new UI and leave it intact.

## Run the project

Use your existing environment and accounts, or extract the project into a separate folder for review.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py migrate
python main.py runserver
```

For an existing installation, use its current environment and database. No database is included in this archive. `seed_demo` can create fictional accounts for a fresh local review environment; it is not required for the update.

The separate `RevisorPlus_Visual_Preview.html` opens directly in a browser and contains 14 example pages with desktop, tablet and phone views. It uses fictional data and does not submit forms or start learning sessions. It is a review aid; the application code in this archive provides the working features.

Deploy through your existing Render/GitHub workflow. Static assets must be collected as usual:

```text
python main.py collectstatic --noinput
```

This delivery updates source files; it does not deploy to the live service.

## Verification

- 20 Django regression tests pass: child ownership and sibling isolation, Premium gating, parent navigation, homework, tutor messaging, student practice, pause/resume and accuracy semantics.
- 20 JavaScript interaction checks pass using a DOM emulator: disclosures, session sizing, allowance boundaries, modal validation, keyboard operation, homework focus and script initialisation.
- Existing `test_subject_dashboard.py`, `test_hardening.py` and `test_billing.py` suites pass on an isolated fixture database.
- 14 page responses render successfully with one main heading, unique IDs, labelled fields and available local assets.
- All templates compile, CSS parses without errors, and `collectstatic` succeeds.
- A supported live browser was unavailable in the editing environment. Responsive layouts were implemented and reviewed in code; screenshot, overflow and real-browser keyboard checks still need local review. Use the visual preview, then check real student and parent accounts before deploying.

Run the included regression tests:

```text
python main.py test accounts practice
```

## Source files

Shared UI: `templates/base.html`, `templates/ui/icon.html`, `static/ui/foundation.css`.

Student pages: `templates/practice/dashboard.html`, `choose.html`, `_qbank_controls.html`, `question.html`, `subject.html`, `summary.html`; `static/student_portals/dashboard.css`, `question_bank.css`, `question_bank.js`; `static/practice/practice_modal.js`.

Parent pages: `templates/accounts/home.html`, `child.html`; `static/student_portals/parent_dashboard.css`; `accounts/views.py`, `accounts/urls.py`.

Homepage: `templates/pages/landing.html`, `static/pages/landing.css`.

Shared analytics and routes: `analytics/services.py`, `practice/views.py`.

Regression tests: `accounts/tests.py`, `practice/tests.py`.

Setup documentation and safeguards: `README.md`, `README.txt`, `apply_parent_dashboard.py`, `install_student_portals.py`.
