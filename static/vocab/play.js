/* Word Wizard: the play page, a client of the JSON API in vocab/api.py.
 *
 * The server builds, marks and scores everything; this script only draws what
 * the API returns and posts the pupil's choice. It never knows an answer before
 * the pupil commits to one — the API does not send it. Even the XP shown during
 * a round is the server's figure (round.xp), only animated here.
 *
 * Text from the server is only ever set with textContent, never innerHTML, so
 * nothing in the word data can inject markup.
 *
 * Errors: a 401 sends the pupil to log in; a 403 that is not JSON is Django's
 * CSRF page (an expired token, usually after a long idle), so the page reloads
 * once to get a fresh one, and says so if that does not help; a network
 * failure leaves the question on screen with a "try again".
 *
 * Motion: a right answer pops, throws a few sparkles and a "+10 XP" that rises
 * off the button, and the XP counter in the bar ticks up; a wrong one gives a
 * short shake. The wizard above the answers casts for a right answer and
 * slumps for a wrong one, is posed by score on the summary, and a level-up
 * reveals his new look. He is server-rendered SVG (vocab/wizard_art.py) that
 * the page carries in <template>s; this script only clones him and switches
 * his pose class, and wizard.css does the moving. With prefers-reduced-motion
 * the colours, marks, poses and new totals all still appear, without the
 * movement.
 */
(function () {
  "use strict";

  const root = document.getElementById("wiz-play");
  if (!root) return;

  const cfg = root.dataset;
  const KIND_LABEL = { synonym: "Synonym match", odd_one_out: "Odd one out", gap: "Fill the gap" };
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let kind = cfg.kind || "mixed";
  let onKey = null;
  let shownXp = 0;          // what the bar's XP counter currently says

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

  // ------------------------------------------------------------------ the wizard

  const POSES = ["idle", "cast", "slump", "cheer", "wave"];
  const LINES = {
    start: "Let's go!",
    synonym: "Which one means the same?",
    odd_one_out: "One of these doesn't belong…",
    gap: "Read the whole sentence first.",
    right: ["Brilliant!", "Spot on!", "Magic!", "You know it!", "Wizard work!"],
    wrong: ["Oops! Let's learn this one.", "Tricky! Read the card below.", "Not quite. It'll stick next time."],
  };
  const pick = (list) => list[Math.floor(Math.random() * list.length)];

  function sprite(id, pose) {
    const t = document.getElementById(id);
    if (!t) return null;
    const node = t.content.firstElementChild.cloneNode(true);
    setPose(node, pose);
    return node;
  }

  function setPose(node, pose) {
    if (!node) return;
    POSES.forEach((p) => node.classList.remove(`wiz-char--${p}`));
    void node.offsetWidth;             // restart the pose's one-off animation
    node.classList.add(`wiz-char--${pose}`);
  }

  // ------------------------------------------------------------------ the bar

  function bar(round, current) {
    const top = el("div", "wiz-play__bar");
    const close = el("a", "wiz-close", "×");
    close.href = cfg.home;
    close.setAttribute("aria-label", "Leave this round. You can carry on later.");
    const dots = el("ol", "wiz-dots");
    dots.setAttribute("aria-hidden", "true");
    const count = el("span", "wiz-count");
    const xp = el("span", "wiz-xp", `${shownXp} XP`);
    xp.setAttribute("aria-live", "polite");
    top.append(close, dots, count, xp);
    updateBar(top, round, current);
    return top;
  }

  function updateBar(top, round, current) {
    const dots = top.querySelector(".wiz-dots");
    dots.replaceChildren(...round.progress.map((p, i) => {
      const d = el("li");
      if (p === true) d.className = "is-right";
      else if (p === false) d.className = "is-wrong";
      else if (i === current) d.className = "is-now";
      return d;
    }));
    const n = Math.min(current + 1, round.total);
    const count = top.querySelector(".wiz-count");
    count.textContent = `${n}/${round.total}`;
    count.setAttribute("aria-label", `Word ${n} of ${round.total}`);
    tickXp(top.querySelector(".wiz-xp"), round.xp);
  }

  // Count the bar's XP up to `to`, with a little bump when it moves.
  function tickXp(node, to) {
    const from = shownXp;
    shownXp = to;
    if (to === from || calm) { node.textContent = `${to} XP`; return; }
    node.classList.remove("is-bump");
    void node.offsetWidth;            // restart the animation
    node.classList.add("is-bump");
    const start = performance.now(), ms = 600;
    (function frame(t) {
      const k = Math.min(1, (t - start) / ms);
      node.textContent = `${Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)))} XP`;
      if (k < 1) requestAnimationFrame(frame);
    })(start);
  }

  // A right answer: sparkles and "+10 XP" rising off the button.
  function celebrate(button, gained) {
    if (calm) return;
    const burst = el("span", "wiz-burst");
    burst.setAttribute("aria-hidden", "true");
    const N = 8;
    for (let i = 0; i < N; i++) {
      const a = (2 * Math.PI * i) / N + Math.random() * 0.4;
      const r = 3 + Math.random() * 1.5;
      const s = el("span", "wiz-spark", i % 2 ? "✦" : "★");
      s.style.setProperty("--dx", `${(Math.cos(a) * r).toFixed(2)}rem`);
      s.style.setProperty("--dy", `${(Math.sin(a) * r * 0.6).toFixed(2)}rem`);
      burst.append(s);
    }
    if (gained > 0) burst.append(el("span", "wiz-float", `+${gained} XP`));
    button.append(burst);
    setTimeout(() => burst.remove(), 1200);
  }

  function sentence(text) {
    const p = el("p", "wiz-q__sentence");
    const parts = text.split("___");
    p.append(document.createTextNode(parts[0]));
    const gap = el("span", "wiz-gap", " ");
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
    shownXp = round.xp;       // a resumed round starts from what it has already earned
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

    // The wizard, in the space above the answers, with something to say.
    const stage = el("div", "wiz-stage");
    const char = sprite("wiz-now", "idle");
    const bubble = el("p", "wiz-bubble", item.number === 1 && !resumed ? LINES.start : LINES[item.kind]);
    if (char) stage.append(char);
    stage.append(bubble);
    root.append(stage);

    const answers = el("div", "wiz-answers");
    answers.setAttribute("role", "group");
    answers.setAttribute("aria-label", "Answers");
    const buttons = item.options.map((text, i) => {
      const b = el("button", "wiz-answer");
      b.append(el("span", "wiz-answer__text", text));
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
    const gained = Math.max(0, round.xp - shownXp);
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
    const chosen = buttons[res.chosen_index];
    chosen.classList.add("is-chosen");
    setPose(root.querySelector(".wiz-stage .wiz-char"), res.correct ? "cast" : "slump");
    const bubble = root.querySelector(".wiz-bubble");
    if (bubble) {
      bubble.textContent = res.correct ? pick(LINES.right) : pick(LINES.wrong);
      bubble.className = "wiz-bubble " + (res.correct ? "is-right" : "is-wrong");
    }
    if (res.correct && !res.already_answered) celebrate(chosen, gained);
    updateBar(root.querySelector(".wiz-play__bar"), round, res.number - 1);

    const fb = root.querySelector(".wiz-feedback");
    fb.replaceChildren(
      el("p", "wiz-feedback__verdict " + (res.correct ? "is-right" : "is-wrong"),
         res.correct ? "Right!" : `Not quite. It's “${res.options[res.answer_index]}”.`),
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
    next.scrollIntoView({ block: "nearest", behavior: calm ? "auto" : "smooth" });
  }

  // ------------------------------------------------------------------ the end

  // Leads with what the pupil got right, however little. The words to work on
  // are there, but folded away behind one tap, so a hard round does not end on
  // a wall of red crosses.
  function headline(correct, total) {
    if (correct === total) return "Perfect round!";
    if (correct >= 7) return "Great work!";
    if (correct >= 4) return "Nice work. You're getting there!";
    if (correct >= 1) return `Good start! You knew ${correct === 1 ? "a word" : correct + " words"}.`;
    return "A tricky round! These words will come back so you can learn them.";
  }

  function reviewList(items, right) {
    const list = el("ul", "wiz-review");
    items.forEach((it) => {
      const li = el("li");
      const mark = el("span", "wiz-review__mark " + (right ? "is-right" : "is-practise"), right ? "✓" : "•");
      mark.setAttribute("aria-hidden", "true");
      li.append(mark, el("b", null, it.word.headword), el("span", "wiz-review__def", it.word.definition));
      list.append(li);
    });
    return list;
  }

  function summaryPose(correct, total) {
    if (correct >= 7) return "cheer";
    if (correct >= 4) return "cast";
    if (correct >= 1) return "idle";
    return "wave";           // nothing right: an encouraging wave, not a slump
  }

  // The level-up moment: the old wizard shakes and fades in a flash, and the
  // new look springs in over turning light, with what it has unlocked.
  function levelUp(level) {
    const box = el("section", "wiz-lvl");
    box.setAttribute("aria-label", `Level up! You're now a ${level.rank}.`);
    box.append(el("span", "wiz-lvl__rays"));
    const stage = el("div", "wiz-lvl__stage");
    const old = sprite("wiz-now-lg", "idle");
    const fresh = sprite("wiz-next", "cheer");
    if (old) { old.classList.add("wiz-lvl__old"); stage.append(old); }
    stage.append(el("span", "wiz-lvl__flash"));
    if (fresh) { fresh.classList.add("wiz-lvl__new"); stage.append(fresh); }
    box.append(stage);
    const text = el("div", "wiz-lvl__text");
    text.append(el("p", "wiz-lvl__kicker", `Level up! Level ${level.level}`),
                el("p", "wiz-lvl__rank", `You're now a ${level.rank}!`));
    if (cfg.nextNew) text.append(el("p", "wiz-lvl__new-look", `New: ${cfg.nextNew}.`));
    box.append(text);
    return box;
  }

  // The XP bar fills from where the round started to where it ended, rather
  // than jumping; across a level-up it fills to the end, then starts the new
  // level from empty.
  function fillBar(fill, before, after) {
    const pct = (l) => `${Math.round(100 * l.xp_into_level / l.xp_for_level)}%`;
    if (calm || !before) { fill.style.width = pct(after); return; }
    fill.style.width = pct(before);
    const crossed = after.level > before.level;
    setTimeout(() => {
      fill.style.width = crossed ? "100%" : pct(after);
      if (!crossed) return;
      setTimeout(() => {
        fill.style.transition = "none";
        fill.style.width = "0%";
        void fill.offsetWidth;
        fill.style.transition = "";
        fill.style.width = pct(after);
      }, 950);
    }, crossed ? 1900 : 500);
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
    const right = r.data.items.filter((it) => it.correct);
    const practise = r.data.items.filter((it) => !it.correct);

    clear();
    const done = el("div", "wiz-done");
    const levelledUp = finished && finished.levelled_up && document.getElementById("wiz-next");
    if (levelledUp) done.append(levelUp(level));

    const top = el("div", "wiz-done__top");
    if (!levelledUp) top.append(sprite("wiz-now-lg", summaryPose(correct, total)));
    const words = el("div");
    if (correct > 0) {
      const big = el("p", "wiz-done__score");
      big.append(document.createTextNode(String(correct)));
      big.append(el("span", "wiz-done__of", correct === 1 ? " word right" : " words right"));
      words.append(big);
    }
    words.append(el("p", "wiz-done__line", headline(correct, total)));
    if (s.xp > 0) words.append(el("span", "wiz-done__xp", `+${s.xp} XP`));
    top.append(words);
    done.append(top);

    if (right.length) {
      done.append(el("h2", "wiz-done__head", "You got these right"));
      done.append(reviewList(right, true));
    }
    if (practise.length) {
      const more = el("details", "wiz-practise");
      more.append(el("summary", null, `Words to practise (${practise.length})`));
      more.append(el("p", "wiz-practise__note", "These will come back tomorrow, so you get another go."));
      more.append(reviewList(practise, false));
      done.append(more);
    }

    const rank = el("div", "wiz-done__rank wiz-panelbox");
    rank.append(el("p", null, `${level.rank} · Level ${level.level}`));
    const track = el("div", "wiz-bar");
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-label", "XP towards the next level");
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", String(level.xp_for_level));
    track.setAttribute("aria-valuenow", String(level.xp_into_level));
    const fill = el("span", "wiz-bar__fill is-driven");
    track.append(fill);
    fillBar(fill, finished && finished.level_before, level);
    rank.append(track, el("small", null, `${level.xp_to_next} XP to level ${level.level + 1}`));
    done.append(rank);
    done.append(el("p", "wiz-done__streak",
      streak === 1 ? "Day streak: 1. Come back tomorrow to make it 2!" : `Day streak: ${streak} days in a row!`));

    const actions = el("div", "wiz-done__actions");
    const again = el("button", "wiz-btn wiz-btn--go", "Play again");
    again.type = "button";
    // A fresh page, not just a fresh round: after a level-up the page's wizard
    // templates are a level behind.
    again.addEventListener("click", () => {
      window.location.href = `${window.location.pathname}?kind=${encodeURIComponent(kind)}`;
    });
    const back = el("a", "wiz-btn wiz-btn--quiet", "Back to Word Wizard");
    back.href = cfg.home;
    actions.append(again, back);
    done.append(actions);
    root.append(done);
    again.focus({ preventScroll: true });
  }

  start();
})();
