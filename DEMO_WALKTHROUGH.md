# RevisorPlus — Demo Walkthrough

**Run it:** `bash run_demo.sh` (or `python manage.py runserver`), then open
**http://127.0.0.1:8000/**

**Logins**
| Role | Email | Password |
|------|-------|----------|
| Student | `student@revisorplus.test` | `demo12345` |
| Tutor | `tutor@revisorplus.test` | `demo12345` |
| Admin (question bank) | `admin@revisorplus.test` | `admin12345` — at `/admin/` |

---

## The click-path to present (≈4 minutes)

1. **Landing page** (`/`) — currently a **holding page** (sign up / log in only). The old copy
   was UCAT sales text and was cleared during the 11+ conversion; it still needs writing, so
   either skip past it or say so up front rather than presenting it as finished.
2. **Log in as the student.** Land on the **dashboard**:
   - Overall accuracy, questions done, correct, open homework (stat tiles).
   - **Accuracy-by-section bar chart** and **progress-over-time line chart** (real, from seeded history).
   - **Focus areas** — the weakest subtopics, each with a "Practise" button.
   - **Homework from your tutor** — with live progress bars.
3. **Practice a deck.** Click "Practise" on a weak area → answer a question → see the **instant
   correct/incorrect feedback + worked explanation** → Next → finish → summary.
   - Show a **Timed** deck too (the countdown badge) to demonstrate exam-mode.
4. **Upgrade** (`/billing/`) — the pricing page → "Subscribe with card" → Stripe test checkout
   (or simulated) → **Premium unlocked**. (Test card `4242 4242 4242 4242` if Stripe keys are set.)
5. **Log out, log in as the tutor.** Land on **My students**:
   - Roster with each student's overall %, weakest area, open homework.
   - Open a student → **their full progress + subtopic breakdown** → **assign homework**
     (subtopic + target + due date) → it appears on the student's dashboard.
6. **(Optional) Admin** (`/admin/`) — show the question bank being managed: sections, subtopics,
   questions with options. "This is where your content lives and is added."

---

## Talking points (say these out loud)

- "The **progress tracking and the tutor workflow** are the core — everything reads from one
  `Attempt` record per answered question, so analytics are just queries."
- "A tutor can **only ever see their own students** — that access rule is enforced on the server
  (I can show the 403 if I try to reach someone else's student)."
- "This runs on **Django**, the same foundation as the production plan — the demo is the real
  data model, just on a lighter runtime."

## Be honest about what this is (protects you in the negotiation)

This is a **proof-of-concept demo**, not the finished product. It intentionally does **not** include:
security hardening, GDPR/Children's-Code compliance, real payment webhooks, email, a full question
bank, or production infrastructure. **That missing work is the ~10-month build** — the demo shows the
concept works; the gap is the value of the labour being discussed.

## Pre-meeting checklist

- [ ] `bash run_demo.sh` starts cleanly and http://127.0.0.1:8000/ loads.
- [ ] Charts render (needs internet — Bootstrap & Chart.js load from CDN).
- [ ] **Record a 2-minute screen-capture of the click-path as a backup** in case of a live glitch.
- [ ] Re-seed if needed: `python manage.py seed_demo` (resets demo data).
