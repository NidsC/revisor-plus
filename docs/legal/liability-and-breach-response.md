# Liability, breach response and compensation — what can and cannot be done

> Draft 0.1, 2026-10-12, advisory session. Internal document. A lay reading of UK law for the
> solicitor to confirm, not legal advice. Companion to `privacy-policy.md`,
> `terms-of-service.md` and `childrens-code-dpia-note.md`. Keep it current: every item in
> section 6 has an owner and a status.

## 1. The legal position in one paragraph

Under UK GDPR, RevisorPlus is the **controller** of every piece of personal data the service
holds, and Render (hosting), Stripe (payments) and Google (sign-in) are its **processors**.
The duty to protect the data, to notify the ICO within 72 hours of a breach that is likely to
risk people's rights, to tell affected people, and to compensate them rests on the controller.
That duty cannot be moved by a sentence in the Terms. What can be moved is the **money** (to
the processor at fault, and to an insurer) and the **size of the exposure** (by holding less
data). This document sets out how.

## 2. What cannot be done

- A term saying "RevisorPlus is not liable if our hosting or payment provider is breached"
  does not remove the controller's duty. Against a consumer it is void under the Consumer
  Rights Act 2015, and the ICO treats such a clause as evidence the duty was not taken
  seriously, which raises a penalty rather than lowering it.
- Data protection obligations cannot be excluded or limited by contract (Terms section 10
  carves them out for exactly this reason).
- Liability for death or personal injury caused by negligence, for fraud, and for breach of
  consumers' statutory rights cannot be excluded.

## 3. What can be done, in order of value

| # | Measure | What it buys | Cost | Status |
|---|---|---|---|---|
| 1 | **Accept and keep the processors' Data Processing Addenda** (Render, Stripe; Google's terms for sign-in). UK GDPR Art. 28 obliges a processor to secure the data, assist with breaches and rights requests and allow audits; Art. 82 makes a processor liable for damage its own breach causes, so sums paid out can be recovered from it. | Recovery of compensation and costs from the provider at fault | None | **Open** — confirm acceptance on each account, save PDFs here, record dates in section 6 |
| 2 | **Hold the minimum data.** Card data is Stripe's; a Stripe breach is Stripe's PCI incident. The RevisorPlus database holds nicknames, usernames, hashed passwords, parent and tutor emails, attempts, targets, messages. No full names, dates of birth, addresses, current schools, photos. | A breach of minimal, pseudonymous data is a low-severity incident; identifying data is not | Discipline, plus the "Nickname" form change | **Open** — form label change pending (see `pending_issues.md`) |
| 3 | **Be able to show diligence.** Regulators and courts ask what you did, not what you promised. | Defence against penalty even where compensation is owed | Record-keeping | In progress — this folder is the record |
| 4 | **Insure the residual.** Cyber liability cover for a small UK business: notification costs, forensics, legal fees, third-party claims. | Pays while recovery from the processor is pursued | Annual premium | **Open** — needs the partnership to exist; ask the accountant or a broker |
| 5 | **Cap what the law allows**, in the Terms: liability limited to what the family paid in the last 12 months; foreseeable loss only; no business losses; provider failures treated as outside our control for *availability*. | Handles "the site was down" cleanly; valid because it carves out what the law protects | Drafted | Done in Terms 0.1, section 10 |
| 6 | **A written breach runbook** (section 5) | Speed, which is what keeps claims trivial | An hour | Drafted below |

## 4. Compensation: what a breach would actually cost

Two different things are called "compensation".

**Regulatory fines go to the state.** The ICO's statutory ceiling is £17.5m or 4% of turnover.
For a small partnership with a minimal dataset and a documented security record, the realistic
outcomes are a reprimand or an enforcement notice. The ICO does not award money to individuals.

**Compensation to individuals comes from a court claim**, under UK GDPR Article 82, for
financial loss or for distress. The bar is real:

- *Lloyd v Google* (UK Supreme Court, 2021): loss of control of data on its own is not enough;
  the claimant must show actual damage or distress.
- *Rolfe v Veale Wasbrough Vizards* (High Court, 2021): a misdirected email containing school-fee
  details was too trivial to compensate; the claimants paid the defendant's costs.
- *Driver v CPS* (High Court, 2022): a distress claim that succeeded sat "at the lowest end of
  the spectrum" and was awarded £250.

Reported low-level distress awards sit in the low hundreds to low thousands of pounds, rising
only where the data is sensitive, the exposure wide and the harm shown. RevisorPlus's data is
at the low-sensitivity end; the subjects being children weighs the other way on any claim that
clears the bar.

**Planning figure:** small per genuinely affected family, dominated by handling and legal
costs, recoverable from the processor if the failure was theirs, and insurable. The two things
that change it are holding more identifying data than today, or responding slowly.

**What to offer unprompted** after a breach, as goodwill not admission: an apology, one to three
months of Premium free for affected families, a named contact, and immediate deletion of a
pupil's data on request. No unsolicited cash offers; those are for the insurer and solicitor.

## 5. Breach runbook (draft — adopt, name the people, rehearse once)

| Step | When | Who | Action |
|---|---|---|---|
| 1 | Hour 0 | On-call partner | Confirm the incident is real: Render status page, Stripe status page, server logs, `StripeEvent` table. Start a timestamped incident note in this folder. |
| 2 | Hour 0–4 | Partner + execution session | Contain: rotate `DJANGO_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` and database credentials in the Render dashboard; force password resets by expiring sessions; take a database backup for evidence before changing data. |
| 3 | Hour 4–24 | Partner | Assess: what data, how many accounts, children involved (yes, always), likelihood of harm. Decide whether the 72-hour ICO notification applies (it does unless the risk is clearly negligible). |
| 4 | Within 72 h | Partner | Notify the ICO (ico.org.uk/breach). Notify Render or Stripe under their DPA if the fault is theirs, and ask for their incident report. |
| 5 | Without undue delay | Partner | Email every affected parent and tutor in plain words: what happened, what was exposed, what we did, what they should do (new password), the contact address. Children are told through parents. |
| 6 | Week 1 | Partner | Goodwill measures (section 4). Log every request received and its handling. |
| 7 | Week 2–4 | Partner + solicitor | Root cause fixed and verified; insurer notified; recovery claim to the processor if applicable; update this document and the DPIA note. |

## 6. Compliance register — what a court or auditor would ask to see

| Item | Evidence | Owner | Status (2026-10-12) |
|---|---|---|---|
| Who the controller is | Partnership agreement, UTR, trading address | owner | Pending partnership |
| Privacy Policy and Terms, agreed and reviewed | `docs/legal/README.md` review log; solicitor's note | owner | Draft 0.1 |
| DPIA / Children's Code assessment | `childrens-code-dpia-note.md`, kept current | owner | Draft 0.1 |
| Processor contracts | Render DPA, Stripe DPA, Google terms, saved PDFs with acceptance dates | owner | **Open** |
| International transfer safeguard (US hosting) | Render's DPF UK-extension certification or IDTA/Addendum, plus a transfer risk assessment | owner | **Open** |
| Data minimisation in the product | Models and forms hold no age, DOB, address, school, full name; "Nickname" label | execution session | Form label **open** |
| Retention enforced | `purge_inactive_pupils` command, its build.sh line, its log output | execution session | **Open** |
| Rights handling | Mailbox revisorplus@gmail.com monitored; SAR and deletion handled within one month; log of requests | owner | Process to adopt |
| Security measures | HTTPS, hashed passwords, CI gate on main, row locks on billing, backups tested; provider attestations | execution session / owner | Mostly in place; backup test and attestations **open** |
| Breach runbook, rehearsed | Section 5, with names | owner | Draft |
| Insurance | Policy document | owner | **Open** |
| ICO data protection fee | Registration confirmation and fee receipt from ico.org.uk (annual; micro-organisation tier, confirm with the ICO self-assessment) | owner | **Open** — required by law before processing continues at scale; a fixed penalty applies for non-payment |
| Consumer Contracts Regulations: model cancellation form and durable-medium confirmation | The model cancellation form annexed to the Terms; a confirmation email sent to the parent after each subscription purchase containing the Terms link and the cancellation right | owner / execution session | **Open** — the form is a text annex; the confirmation email needs the transactional mail backend, which does not exist (`pending_issues.md`) |
| Record of decisions | `README.md` decisions table; `plans.md` Done entry | advisory session | Done |

## 6a. Two statutory items added 2026-10-12

- **ICO data protection fee.** Nearly every organisation that processes personal data
  electronically must register with the ICO and pay the annual data protection fee (the
  micro-organisation tier is around £50; confirm the tier with the ICO's online
  self-assessment). Not paying is a fixed-penalty offence. Register once the partnership
  exists and before the first live charge; file the receipt in this folder.
- **Consumer Contracts Regulations 2013, regulations 12–16 and Schedule 3.** Before a parent
  subscribes they must be given the cancellation information and the model cancellation form,
  and the contract must be confirmed on a durable medium (an email) within a reasonable time
  after purchase. The form is annexed to the Terms. The confirmation email requires a working
  transactional mail backend, which the site does not have: today the only email a parent
  receives after paying is Stripe's receipt, if enabled, and whether that satisfies the
  regulation is a question for the solicitor. Until the mail backend exists this item cannot
  be closed.

## 7. Suggestions not yet decided

1. **A `/legal/` route only when published.** Keep the Markdown as the source of truth; the
   pages PR copies the agreed text verbatim and records the version number so the site and
   this folder cannot drift.
2. **A quarterly review date** in the README: retention job ran, request log reviewed, DPAs
   still current, no new data fields added without updating the policy.
3. **Self-host Bootstrap and the Inter font** so section 6 of the policy can drop the
   third-party disclosure and the Children's Code "data sharing" line gets simpler.
4. **Tutor onboarding acceptance**: when tutors are onboarded at scale, a one-time "I will use
   pupil data only for the linked pupil" acceptance, logged with a timestamp.
5. **Self-service deletion later.** Not needed for compliance (email handling within a month
   is lawful) but it is what the Children's Code calls an "online tool" and would remove a
   `[CHECK]` from the policy.
6. **Separate the tracked legal folder from the gitignored working notes** in CLAUDE.md so a
   future session knows `docs/legal/` is shipped content and must not be edited without the
   review log being updated.
