/* Word Wizard: the play page, a client of the JSON API in vocab/api.py.
 *
 * The server builds, marks and scores everything; this script only draws what
 * the API returns and posts the pupil's choice. It never knows an answer before
 * the pupil commits to one — the API does not send it.
 *
 * Text from the server is only ever set with textContent, never innerHTML, so
 * nothing in the word data can inject markup.
 *
 * Errors: a 401 sends the pupil to log in; a 403 that is not JSON is Django's
 * CSRF page (an expired token, usually after a long idle), so the page reloads
 * once to get a fresh one, and says so if that does not help; a network
 * failure leaves the question on screen with a "try again".
 */
(function () {
  "use strict";

  const root = document.getElementById("wiz-play");
  if (!root) return;

  const cfg = root.dataset;
  const KIND_LABEL = { synonym: "Synonym match", odd_one_out: "Odd one out", gap: "Fill the gap" };
  let kind = cfg.kind || "mixed";
  let onKey = null;

  // ------------------------------------------------------------------ helpers

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  // The cookie if there is one (it is the freshest), else the token the page
  // was rendered with. The view sets the cookie, so normally both agree.
  function csrf() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : (cfg.csrf || "");
  }

  // A non-JSON 403 is Django's CSRF page: reload once for a fresh token. If
  // the reload does not cure it, say so, rather than reloading for ever.
  const RELOAD_KEY = "wiz-csrf-reload";
  function reloadOnce() {
    let last = 0;
    try { last = Number(sessionStorage.getItem(RELOAD_KEY)) || 0; } catch (e) { /* storage off */ }
    if (Date.now() - last < 30000) {
      message("Word Wizard couldn't check your login. Please refresh the page, or log out and back in.");
      return;
    }
    try { sessionStorage.setItem(RELOAD_KEY, String(Date.now())); } catch (e) { /* storage off */ }
    window.location.reload();
  }

  async function api(method, url, body) {
    let res;
    try {
      res = await fetch(url, {
        method,
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf(), "Accept": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      return { status: 0, data: null };
    }
    const isJson = (res.headers.get("Content-Type") || "").includes("application/json");
    if (res.status === 401) { window.location.href = cfg.login; return null; }
    if (res.status === 403 && !isJson) { reloadOnce(); return null; }
    if (res.ok) { try { sessionStorage.removeItem(RELOAD_KEY); } catch (e) { /* storage off */ } }
    return { status: res.status, data: isJson ? await res.json() : null };
  }

  function clear() {
    if (onKey) { document.removeEventListener("keydown", onKey); onKey = null; }
    root.replaceChildren();
    window.scrollTo(0, 0);
  }

  function message(text, actionText, action) {
    clear();
    const box = el("div", "wiz-state");
    box.append(el("p", null, text));
    if (actionText) {
      const b = el("button", "wiz-btn wiz-btn--go", actionText);
      b.type = "button";
      b.addEventListener("click", action);
      box.append(b);
    }
    const back = el("a", "wiz-btn wiz-btn--quiet", "Back to Word Wizard");
    back.href = cfg.home;
    back.style.marginTop = ".6rem";
    box.append(back);
    root.append(box);
  }

  function bar(round, current) {
    const top = el("div", "wiz-play__bar");
    const close = el("a", "wiz-close", "×");
    close.href = cfg.home;
    close.setAttribute("aria-label", "Leave this round. You can carry on later.");
    const dots = el("ol", "wiz-dots");
    dots.setAttribute("aria-hidden", "true");
    round.progress.forEach((p, i) => {
      const d = el("li");
      if (p === true) d.className = "is-right";
      else if (p === false) d.className = "is-wrong";
      else if (i === current) d.className = "is-now";
      dots.append(d);
    });
    const count = el("span", "wiz-count", `${Math.min(current + 1, round.total)}/${round.total}`);
    count.setAttribute("aria-label", `Word ${Math.min(current + 1, round.total)} of ${round.total}`);
    top.append(close, dots, count);
    return top;
  }

  function sentence(text) {
    const p = el("p", "wiz-q__sentence");
    const parts = text.split("___");
    p.append(document.createTextNode(parts[0]));
    const gap = el("span", "wiz-gap", " ");
    gap.setAttribute("aria-label", "blank");
    p.append(gap, document.createTextNode(parts.slice(1).join("___")));
    return p;
  }

  function wordCard(w) {
    const card = el("div", "wiz-word wiz-panelbox");
    const head = el("p", "wiz-word__head", w.headword);
    head.append(el("span", "wiz-word__pos", w.pos));
    card.append(head, el("p", "wiz-word__def", w.definition), el("p", "wiz-word__eg", w.example));
    if (w.synonyms && w.synonyms.length) {
      card.append(el("p", "wiz-word__syn", "Means the same as: " + w.synonyms.join(", ")));
    }
    return card;
  }

  // ------------------------------------------------------------------ flow

  async function start() {
    const r = await api("POST", cfg.apiRound, { kind });
    if (!r) return;
    if (r.status === 503) return message("The word lists aren't ready yet. Please try again a little later.");
    if (r.status === 403) return message("Word Wizard isn't available on this account.");
    if (r.status !== 200 && r.status !== 201) {
      return message("Something went wrong getting your words.", "Try again", start);
    }
    const round = r.data.round;
    const resumed = r.data.resumed && round.answered > 0;
    if (round.item) showItem(round, round.item, resumed);
    else showSummary(round.id, null);
  }

  function showItem(round, item, resumed) {
    clear();
    root.append(bar(round, item.number - 1));
    if (resumed) root.append(el("p", "wiz-toast", "Carrying on where you left off."));

    const q = el("div", "wiz-q");
    q.append(el("span", "wiz-q__kind", KIND_LABEL[item.kind] || ""));
    // With a target word shown large underneath, the heading stops short of it
    // rather than saying the word twice; screen readers still get the whole
    // question from the API's prompt.
    const prompt = el("h1", "wiz-q__prompt", item.target ? "Which word means the same as" : item.prompt);
    if (item.target) prompt.setAttribute("aria-label", item.prompt);
    prompt.tabIndex = -1;
    q.append(prompt);
    if (item.target) {
      const target = el("span", "wiz-q__target", item.target);
      target.setAttribute("aria-hidden", "true");
      q.append(target);
    }
    if (item.sentence) q.append(sentence(item.sentence));
    root.append(q);

    const answers = el("div", "wiz-answers");
    answers.setAttribute("role", "group");
    answers.setAttribute("aria-label", "Answers");
    const buttons = item.options.map((text, i) => {
      const b = el("button", "wiz-answer", text);
      b.type = "button";
      b.addEventListener("click", () => choose(round, item, i, buttons));
      answers.append(b);
      return b;
    });
    root.append(answers);
    const feedback = el("div", "wiz-feedback");
    feedback.setAttribute("aria-live", "polite");
    root.append(feedback);

    onKey = (e) => {
      const n = parseInt(e.key, 10);
      if (n >= 1 && n <= buttons.length && !buttons[0].disabled) buttons[n - 1].click();
    };
    document.addEventListener("keydown", onKey);
    prompt.focus({ preventScroll: true });
  }

  async function choose(round, item, index, buttons) {
    buttons.forEach((b) => { b.disabled = true; });
    const r = await api("POST", cfg.apiAnswer, { item: item.id, choice: index });
    if (!r) return;
    if (r.status !== 200) {
      buttons.forEach((b) => { b.disabled = false; });
      const fb = root.querySelector(".wiz-feedback");
      fb.replaceChildren(el("p", "wiz-feedback__verdict is-wrong",
        r.status === 0 ? "Couldn't reach the server. Check your connection and tap again."
                       : "That didn't go through. Tap your answer again."));
      return;
    }
    showResult(r.data.result, r.data.round, r.data.finished, buttons);
  }

  function showResult(res, round, finished, buttons) {
    if (onKey) { document.removeEventListener("keydown", onKey); onKey = null; }
    buttons.forEach((b, i) => {
      b.disabled = true;
      if (i === res.answer_index) {
        b.classList.add("is-right");
        b.append(el("span", "wiz-mark", "✓"));
      } else if (i === res.chosen_index) {
        b.classList.add("is-wrong");
        b.append(el("span", "wiz-mark", "✗"));
      } else {
        b.classList.add("is-faded");
      }
    });
    root.querySelector(".wiz-play__bar").replaceWith(bar(round, res.number - 1));

    const fb = root.querySelector(".wiz-feedback");
    const right = res.correct;
    fb.replaceChildren(
      el("p", "wiz-feedback__verdict " + (right ? "is-right" : "is-wrong"),
         right ? "Right! +10 XP" : `Not quite. It's “${res.options[res.answer_index]}”.`),
    );
    if (res.kind === "odd_one_out") {
      // Say why: the other three all mean the same, and the card below is about them.
      const same = res.options.filter((_, i) => i !== res.answer_index).map((o) => `“${o}”`);
      fb.append(el("p", "wiz-feedback__why",
        `${same.slice(0, -1).join(", ")} and ${same[same.length - 1]} all mean the same.`));
    }
    fb.append(wordCard(res.word));
    const next = el("button", "wiz-btn wiz-btn--go", finished ? "See how you did" : "Next word");
    next.type = "button";
    next.addEventListener("click", () => {
      if (finished || !round.item) showSummary(round.id, finished);
      else showItem(round, round.item, false);
    });
    fb.append(next);
    next.focus({ preventScroll: true });
    next.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  async function showSummary(roundId, finished) {
    const r = await api("GET", cfg.apiDetail.replace(/\/0\/$/, `/${roundId}/`));
    if (!r) return;
    if (r.status !== 200) return message("Your round is saved, but the results didn't load.", "Try again",
                                         () => showSummary(roundId, finished));
    const s = r.data.summary;
    const level = (finished && finished.level) || s.level;
    const streak = finished ? finished.streak : s.streak.current;
    const correct = s.correct, total = s.total;

    clear();
    const done = el("div", "wiz-done");
    const score = el("p", "wiz-done__score", `${correct}/${total}`);
    score.setAttribute("aria-label", `${correct} out of ${total}`);
    const line = correct === total ? "Perfect round!" : correct >= 7 ? "Great work!"
               : correct >= 4 ? "Good effort!" : "Keep going. These words will come back to you.";
    done.append(score, el("p", "wiz-done__line", line), el("span", "wiz-done__xp", `+${s.xp} XP`));
    if (finished && finished.levelled_up) {
      done.append(el("p", "wiz-levelup", `Level up! You're now a ${level.rank}.`));
    }

    const rank = el("div", "wiz-done__rank wiz-panelbox");
    rank.append(el("p", null, `${level.rank} · Level ${level.level}`));
    const track = el("div", "wiz-bar");
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-label", "XP towards the next level");
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", String(level.xp_for_level));
    track.setAttribute("aria-valuenow", String(level.xp_into_level));
    const fill = el("span", "wiz-bar__fill");
    fill.style.width = `${Math.round(100 * level.xp_into_level / level.xp_for_level)}%`;
    track.append(fill);
    rank.append(track, el("small", null, `${level.xp_to_next} XP to level ${level.level + 1}`));
    done.append(rank);
    done.append(el("p", "wiz-done__streak",
      streak === 1 ? "Day streak: 1. Come back tomorrow to make it 2!" : `Day streak: ${streak} days in a row!`));

    const list = el("ul", "wiz-review");
    list.setAttribute("aria-label", "This round's words");
    r.data.items.forEach((it) => {
      const li = el("li");
      const mark = el("span", "wiz-review__mark " + (it.correct ? "is-right" : "is-wrong"), it.correct ? "✓" : "✗");
      mark.setAttribute("aria-label", it.correct ? "right" : "wrong");
      li.append(mark, el("b", null, it.word.headword), el("span", "wiz-review__def", it.word.definition));
      list.append(li);
    });
    done.append(list);

    const actions = el("div", "wiz-done__actions");
    const again = el("button", "wiz-btn wiz-btn--go", "Play again");
    again.type = "button";
    again.addEventListener("click", () => { root.replaceChildren(el("div", "wiz-state", "Getting your words ready…")); start(); });
    const back = el("a", "wiz-btn wiz-btn--quiet", "Back to Word Wizard");
    back.href = cfg.home;
    actions.append(again, back);
    done.append(actions);
    root.append(done);
    again.focus({ preventScroll: true });
  }

  start();
})();
