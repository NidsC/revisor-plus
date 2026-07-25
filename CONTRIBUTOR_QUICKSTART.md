# Contributor Quickstart — adding 11+ questions

Welcome. This guide gets you from nothing to writing questions that land in the RevisorPlus
question bank. You do **not** need to be a developer, and you do **not** need to install or run
the app itself — you only ever work with question files, and an assistant does the fiddly parts.

You write questions by opening **Claude Code** in your copy of the project and typing
**`/questions`**. It walks you through the whole session and does the technical steps for you.

---

## One-time setup (about 20 minutes, once)

Do these once. If you get stuck on step 3 or 4, ask Nideesh for a quick screen-share — git
sign-in is the one part that's genuinely fiddly, and it's easiest to sort out together.

1. **Get a GitHub account** — free, at [github.com](https://github.com). Tell Nideesh your
   username so he can give you read access to the project.

2. **Install GitHub Desktop** — [desktop.github.com](https://desktop.github.com). This handles
   signing in, copying the project to your computer, and sending your work back, all with
   buttons instead of typed commands. Sign in to it with your GitHub account.

3. **Make your own copy of the project (a "fork").** Open the project page Nideesh sends you and
   click **Fork** (top-right). This creates *your* copy under your account. You'll work in your
   fork and send finished questions over for review — you can't accidentally change the real
   project, which is exactly how it should be.

4. **Download your fork to your computer.** In GitHub Desktop: **File → Clone repository →** pick
   your fork **→ Clone**. Note the folder it saves to.

5. **Install Claude Code and sign in** — follow the instructions at the link Nideesh gives you.
   This is the tool you'll type `/questions` into.

6. **Check you have Python 3.** On Mac it's almost always already there. On Windows, install it
   from [python.org](https://python.org) if the assistant tells you it's missing. That's the only
   other thing needed, and it's used automatically — you never run it yourself.

---

## Each writing session (the part you'll repeat)

1. **(Optional but tidy) Update your copy first.** On your fork's page on github.com, click
   **Sync fork → Update branch** so you're starting from the latest questions.

2. **Open the project folder in a terminal.** Easiest way: in GitHub Desktop, **Repository →
   Open in Terminal**.

3. **Start Claude Code** by typing:
   ```
   claude
   ```

4. **Run the question workflow.** Type `/questions` and, if you like, the section and how many:
   ```
   /questions MAT 15
   ```
   Sections are `ENG` (English), `MAT` (Maths), `VR` (Verbal Reasoning) and
   `NVR` (Non-Verbal Reasoning). Aim for **10–20 questions** a session.

5. **Work with the assistant.** It will:
   - put you on a fresh working branch automatically,
   - help you write the questions and check each one,
   - run the quality checker,
   - save and upload your work to your fork,
   - and give you a **link to open a pull request** (your way of saying "these are ready").

6. **Open the pull request.** Click the link the assistant gives you, add the one-line summary it
   suggests, and submit. That's you done — Nideesh takes it from there.

---

## What happens after you open the pull request

- An automatic check runs your questions through the validator. Green tick = the format is good.
- Nideesh reviews the actual questions and merges them.
- Once merged, they appear on the live site on the next update. **You don't need to do anything
  else** — no build files to edit, nothing to deploy.

---

## The golden rules (the assistant enforces these, but good to know)

- **One section per file.** Don't mix English and Maths in one batch.
- **Your questions are original** — they're marked as owned work, not placeholder content.
- **Never touch another contributor's question file** — only the one for your own batch.
- **Don't try to merge your own pull request** — review is Nideesh's step.
- If the checker flags something, fix it and re-run. Don't work around it.

---

## If something goes wrong

- **"It won't let me upload / sign-in error"** — this is almost always the git sign-in from setup
  step 2. It can't damage anything; it just means your work is stuck on your computer until it's
  sorted. Ping Nideesh. Nothing you do here can break the live project — the worst case is your
  own work waits a bit.
- **The checker keeps failing** — read what it says (it's specific), fix that, and run it again.
  The assistant will help. A failing check simply means "not ready yet," not "broken."
- **Anything else** — describe what you saw to the assistant or to Nideesh. Screenshots help.
