# RevisorPlus — Demo Walkthrough

**Run it:** `bash run_demo.sh` (or `python main.py runserver`), then open
**http://127.0.0.1:8000/**

**Logins**
| Role | Email | Password |
|------|-------|----------|
| **Student — use this one** | `nideesh@revisorplus.test` | `Nids12345` |
| Student (shorter history) | `student@revisorplus.test` | `demo12345` |
| Tutor | `tutor@revisorplus.test` | `demo12345` |
| Admin (question bank) | `admin@revisorplus.test` | `admin12345` — at `/admin/` |

`nideesh` has four months of visibly improving history (3,276 questions, 72%,
climbing 63% → 84%) against a Wilson's target 63 days out. `student` has four
weeks, so the charts are thinner.

**Before recording**
- Record against **local runserver**, not Render — the free instance spins down
  and cold-starts in ~30s, which will ruin a take.
- **Turn off any dark-mode extension** (Dark Reader and similar). The design is
  light-only; forced inversion makes the gradients muddy.
- `python main.py seed_demo` is deterministic (`random.seed(42)`), so re-seeding
  between takes gives byte-identical data and takes can be spliced.

---

## The click-path to present (≈4 minutes)

1. **Landing page** (`/`) — the pitch, with **live counts pulled from the database**
   (~4,600 questions, 4 papers, 20 subtopics, 5 difficulty levels), the six value
   cards, the four-exam roadmap, and pricing. Nothing on it is hardcoded.
2. **Log in as `nideesh`.** Land on the **dashboard**:
   - **Target tracker** at the top: Wilson's School, 63 days, "At risk", 3.1 h/wk
     needed against 2.6 being done, English 70% against a 72% target, Maths met.
   - Stat tiles, **accuracy-by-paper bar chart** (colour-coded — the weak paper
     reads as weak without the axis), and **progress over time** with a 7-day
     average over the raw daily line.
   - **Focus areas** — weakest subtopics, each with a "Practise" button.
3. **Practice.** Click "Practise" on a weak area → answer → **instant marking with a
   worked explanation**, and on a wrong answer the specific mistake:
   *"That's the answer you get if you used the wrong percentage."*
4. **Mock papers** (`/mocks/`) — four timed papers. Start one: the clock runs from a
   **server-set deadline** (reloading buys nothing), questions are drawn fresh and
   spread across the paper. Finish → **marked report** with a per-subtopic breakdown.
   Non-Verbal is the best one to show — the figures are generated SVG.
5. **Log in as the tutor.** **My students**:
   - Twelve pupils sorted **worst-first**, each with target, status, weakest area
     and open homework.
   - Open one → full progress + subtopic breakdown → **assign homework** → it
     appears on that pupil's dashboard.
6. **(Optional) Admin** (`/admin/`) — the question bank, sections and subtopics.

**Do not film**: the Upgrade/checkout flow. Nothing is actually gated behind
Premium, and Stripe is in simulated mode — it prints "simulating a successful
payment". A brand-new signup is also a poor path: it's the empty cold-start state.

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
security hardening, GDPR/Children's-Code compliance, real payment webhooks, email, or production
infrastructure. **That missing work is the ~10-month build** — the demo shows the concept works; the
gap is the value of the labour being discussed.

Three specific things to be straight about if asked, because the product does not
yet do them and the UI deliberately does not claim them:

- **Practice does not adapt.** Question selection is random within a subtopic.
  Difficulty is recorded on all ~4,600 questions but no query reads it yet. What
  is real is weakness *targeting* — the dashboard names the four subtopics to work
  on, and a tutor can set homework straight at them.
- **Nothing is gated behind Premium.** A free account gets the whole product.
- **Written answers are stored but not marked.** Rubric questions in an English
  mock are saved for a tutor; the marking queue that would clear them is not built.

## Pre-meeting checklist

- [ ] `bash run_demo.sh` starts cleanly and http://127.0.0.1:8000/ loads.
- [ ] Charts render (needs internet — Bootstrap & Chart.js load from CDN).
- [ ] **Record a 2-minute screen-capture of the click-path as a backup** in case of a live glitch.
- [ ] Re-seed if needed: `python main.py seed_demo` (resets demo data).
