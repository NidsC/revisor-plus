# Children's Code and data protection impact note

> Draft 0.1, 2026-10-12, advisory session. Internal document, not a public page. It records
> the assessment behind the Privacy Policy and Terms of Service drafts, written against the
> code on `main` at commit `8329402`. The ICO's Age Appropriate Design Code (standard 2)
> asks for a data protection impact assessment for any service likely to be accessed by
> children; this is that assessment in short form, to be kept current as the service changes.

## 1. The processing in one paragraph

RevisorPlus lets a parent create a login for their child (aged roughly 9 to 11) to practise
11+ exam questions. The service records which questions the child answers and how, derives
progress and weak areas from those answers, tracks them against a target school and exam
date the family enters, and lets a tutor the parent has linked set homework and message the
parent. Parents pay a monthly subscription per child through Stripe. The service is hosted
by Render in the United States.

## 2. Necessity and proportionality

| Data about the child | Necessary for | Could we do without it? |
|---|---|---|
| Nickname and username | Logging in; showing the child their own pages | A username alone would work; the nickname is for the family's benefit and is set by the parent. Keep, but enforce "nickname, not full name" on the form. |
| Hashed password | Account security | No. |
| Attempts (question, answer, correct, time) | Marking, adaptive practice, progress, free-tier count | No; this is the service. |
| Target school, exam date, target scores, target hours | Readiness tracking against the real goal | The service works without a target (the "skip" path exists) but is less useful. Keep, optional, deletable. |
| Vocabulary progress | The Word Wizard trainer | No, for that feature. |
| Homework and tutor messages | The tutor feature | Only when a parent links a tutor. |

Not collected, by design: age, date of birth, current school, address, location, photo,
contact details. The sign-up form has no such fields and the models have no such columns.

## 3. Risks to the child and how they are handled

| Risk | Likelihood / severity | Mitigation in place | Gap |
|---|---|---|---|
| A parent enters the child's full name as the display name | High / low (visible only to the family and a linked tutor) | None today | Change the form label and help text to "Nickname"; **required before publication** |
| The child's practice data is exposed to someone outside the family | Low / high | Parent-only ownership guards on every family page; tutor pages require an active parent-made link; pupils-only decorator on practice; password hashing; HTTPS; no public profiles | Keep the guard tests in `test_hardening.py` green |
| Data retained indefinitely after the family stops using the service | High today / medium | Policy: delete after 12 months' inactivity | **No purge job exists**; build it before publication |
| International transfer (US hosting) | Certain / medium | Render's contractual safeguards | Confirm the mechanism (DPF UK extension or IDTA/Addendum) and record it |
| Third-party IP disclosure on page load (CDN, fonts) | Certain / low | Disclosed in the policy | Self-host to remove it |
| A hosting-provider breach | Low / high | Provider certifications; breach-notification duty | Record Render's security attestations; keep backups current |
| Profiling or nudging the child | Low / medium | The only profiling chooses practice topics; no streak-pressure beyond the vocabulary trainer's own streak display; no advertising | Review the vocabulary streak against "nudge techniques" (standard 13) when the UI next changes |
| Child cannot exercise rights directly | Medium / low | Parent acts for the child; the policy says a child's own message will be handled with the same care | None further for this age group |
| Tutor misuse of pupil data | Low / medium | Tutors see only linked pupils; Terms section 7 binds them | Consider a tutor-side acceptance step when tutors are onboarded at scale |

## 4. Age Appropriate Design Code standards, one line each

1. Best interests: practice data used only to help the child learn. ✔
2. DPIA: this note. ✔ (keep current)
3. Age-appropriate application: all pupils are treated as children; no age gate needed because only parents create pupil accounts. ✔
4. Transparency: Privacy Policy section 2 is written for the child. ✔
5. Detrimental use of data: none; no advertising, no sale. ✔
6. Policies and community standards: the service enforces what the policy says, with the two gaps above. ◻ until fixed
7. Default settings: pupil pages private by default; nothing public. ✔
8. Data minimisation: no age, location, school, full name. ✔ (form label gap)
9. Data sharing: only parent and linked tutor; processors named. ✔
10. Geolocation: not collected. ✔
11. Parental controls: the parent creates, controls and can delete the account and can see everything; the child is told this in section 2. ✔
12. Profiling: limited to practice selection; off for everything else. ✔
13. Nudge techniques: none intended; review the vocabulary streak. ◻
14. Connected toys and devices: not applicable. —
15. Online tools: rights exercised by email via the parent; no in-app button yet. ◻ acceptable for now, revisit with self-service deletion

## 5. Decisions and sign-off

| Date | Decision or sign-off | Who |
|---|---|---|
| 2026-10-11 | Retention 12 months' inactivity; refund 14 days first subscription; governing law England and Wales; controller RevisorPlus | owner |
| 2026-10-12 | Draft 0.1 written | advisory session |
| | Team review | |
| | Solicitor review | |
