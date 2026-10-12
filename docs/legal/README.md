# Legal documents — status and review log

This folder holds the source text of RevisorPlus's public legal documents. **Nothing here is
served by the website.** Django renders only `templates/`; a document goes live only when a
later PR copies the agreed text into a template and adds a route, and that PR must not be
opened until the gates below are green.

| Document | File | Status |
|---|---|---|
| Privacy Policy | `privacy-policy.md` | Draft 0.1, 2026-10-12. Not agreed, not reviewed, not published. |
| Terms of Service | `terms-of-service.md` | Draft 0.1, 2026-10-12. Not agreed, not reviewed, not published. |
| Children's Code / DPIA note | `childrens-code-dpia-note.md` | Draft 0.1, 2026-10-12. Supports the two documents; not a public page. |

## Gates before either document is published

1. **Team agreement** — unanimous, recorded here with the date and the names of who agreed.
2. **Solicitor review** — recorded here with the date and the reviewer. Every `[CHECK]`
   marker in the drafts is a question for that review or a fact the team must confirm first.
3. **The code matches the text.** The drafts describe the app as it should be, and three
   things in the app do not yet match:
   - The add-child form (`templates/accounts/home.html`) labels the display-name field
     "Child's name". The policy says we collect a nickname, not a full name. The label and its
     help text must change to "Nickname (not your child's full name)" first.
   - The policy promises automatic deletion of a pupil's data after 12 months of inactivity.
     No such job exists. A management command (for example `purge_inactive_pupils --days 365`)
     run from `build.sh` on each deploy, with a dry-run flag and a log line, must exist and
     have run at least once before the promise goes live.
   - Self-hosting Bootstrap and the Inter font would remove the third-party IP disclosure in
     Privacy section 6. Optional, but decide before publication so the paragraph can be
     dropped or kept.
4. **Facts to confirm** (each is a `[CHECK]` in the text): the partnership's legal name and
   address; VAT position; Render's transfer mechanism for the Oregon region (Data Privacy
   Framework UK extension, or IDTA/Addendum in its DPA) and its log retention; that Stripe's
   DPA is accepted on the account; which security certifications to cite.

## Decisions already taken by the owner (2026-10-11)

- Controller identity: RevisorPlus; contact revisorplus@gmail.com.
- Refund: full refund within 14 days of a pupil's first subscription payment; no partial
  refunds after that. No free trial; free resources (100 practice answers per paper) instead.
- Retention: a pupil's account, results and history are deleted after 12 months of inactivity;
  parents can request deletion of a pupil account alone, or of the parent account, which
  deletes every pupil under it.
- Hosting: Render, US (Oregon).
- Governing law: England and Wales.
- Pupil data is collected only to provide targeted practice and target-school tracking: a
  nickname (never a full name), the target school, scores and attempts. No age, location or
  current school is asked for. Email addresses are collected from parents and tutors only.
- Subject access requests are honoured on request.
- Card details are held and processed by Stripe only.

## Review log

| Date | Event | Who |
|---|---|---|
| 2026-10-12 | Drafts 0.1 written from the decisions above and the code on `main` | advisory session |
