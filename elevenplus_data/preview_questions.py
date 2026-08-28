#!/usr/bin/env python3
"""
preview_questions.py — see an 11+ question pack the way a pupil will, on localhost.

Stdlib only. No Django, no pip install, no database — a contributor can run it with
nothing but Python 3, exactly like validate_questions.py next door. It writes nothing
to disk and touches nothing in the project; it just serves one page on 127.0.0.1 that
mirrors templates/practice/question.html and templates/practice/mock_result.html:
passage, stem, figure, the answer control for whichever of the seven kinds this is,
moving back and forth through the set, submitting it once, then a marked review with
the author's own metadata beside every question.

This is a *look*, not a gate. `validate_questions.py` is the gate and stays the gate —
nothing here refuses a pack, and a pack this page renders happily can still be wrong.

Usage
-----
    python3 elevenplus_data/preview_questions.py elevenplus_data/contrib_nc_eng_01.json
    python3 elevenplus_data/preview_questions.py elevenplus_data/contrib_*.json

    --port N        start at this port instead of 8770 (steps up if it's taken)
    --no-browser    don't open a browser window automatically
    --write-html [PATH]
                    write the rendered page to PATH and exit, instead of serving it.
                    PATH defaults to the first pack's own name with a .preview.html
                    suffix. For handing the pack to someone without a checkout — a
                    parent, a tutor who doesn't run Django — as one file they can
                    open directly. It is a snapshot, stamped with the date it was
                    made: it will not pick up further edits to the pack, and cannot
                    track a redesign of templates/practice/question.html the way
                    the server does.

Stop it with Ctrl+C. The page re-reads every pack from disk on each refresh, so a
question you add while it is running shows up as soon as you reload — edit, save,
refresh, look. That loop is the whole point of the tool.

NOTE FOR MAINTAINERS: the markup below is a deliberate mirror of
templates/practice/question.html and the CSS subset of templates/base.html that it
uses. If you restyle the real question page, restyle this too or the preview quietly
starts lying — which is worse than having no preview at all.

Two things are copied from the app rather than reinvented, because an author counts
against them and a preview that disagreed would send them chasing a bug that isn't
there: the 100-character passage line measure (catalog/passages.py) and the marking
rules for typed answers (catalog/marking.py). A third thing is reused rather than
copied: the batch overview's key-position spread imports validate_questions.py's own
pure `key_positions`/`check_key_distribution`, so the warning a tutor sees here is
never a second opinion on the one the validator gives at commit time.
"""
import argparse
import datetime
import glob
import json
import mimetypes
import sys
import textwrap
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = (REPO_ROOT / "static").resolve()
TAXONOMY = Path(__file__).resolve().parent / "taxonomy.json"

# The third thing copied from the app rather than reinvented — and the only one
# that is imported rather than transcribed. `catalog/figures` is Django-free and
# stdlib-only precisely so this tool can call it, so the diagrams on this page
# are drawn by the code that draws them on the live site. Porting the drawing to
# JavaScript would have made a fourth place for the rules to live and a fourth
# place for them to drift.
sys.path.insert(0, str(REPO_ROOT))
from catalog.figures import render_figure, render_option_figure  # noqa: E402
from catalog.figures.templates import TEMPLATES  # noqa: E402

# validate_questions.py lives next to this file, so Python already finds it when
# this is run as a script (the interpreter puts a script's own directory on
# sys.path); the explicit insert is what keeps that true when this module is
# imported instead, as test_preview_questions.py does.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_questions import check_key_distribution, key_positions  # noqa: E402

# Not 8765: that is the MedRevisor preview's port, and an author with both checkouts
# open should not have to work out why one of them is showing the other's questions.
DEFAULT_PORT = 8770
PORT_TRIES = 10

# catalog/passages.py — part of the authoring contract, not a styling choice. An
# author writing `"line_ref": "7"` counted against these, so the preview must too.
PASSAGE_LINE_WIDTH = 100
NUMBER_EVERY = 5

# catalog/models.py
NO_ERROR_LABEL = "N"
NO_ERROR_TEXT = "No mistake"
OPTION_LABELS = ("A", "B", "C", "D", "E", "F", "G", "H")

# elevenplus_data/CLAUDE.md's difficulty rubric, in four words each. Printed beside
# the number in the author strip because a mis-set difficulty is one of the three
# mistakes this tool exists to make visible, and "3" on its own reads as fine.
DIFFICULTY_WORDS = {1: "recall, one step", 2: "standard, no trap", 3: "typical exam level",
                    4: "hard, multi-step", 5: "stretch / scholarship"}


def passage_lines(text, width=PASSAGE_LINE_WIDTH):
    """Split a passage into numbered lines. A copy of catalog/passages.py.

    Deliberately done here in Python with the same `textwrap` call the server uses,
    rather than reimplemented in the page's JavaScript: textwrap's hyphen and
    long-word handling is fiddly, and a near-miss would put an author's line 7 one
    line away from the pupil's line 7 — the exact failure the fixed measure exists
    to prevent.

    Returns (line_number, text) pairs; a paragraph break is (None, "") so the gap
    consumes no line number.
    """
    if not text:
        return []
    out, n = [], 0
    for i, para in enumerate(str(text).replace("\r\n", "\n").split("\n\n")):
        if i:
            out.append((None, ""))
        para = " ".join(para.split())
        if not para:
            continue
        for line in textwrap.wrap(para, width=width) or [""]:
            n += 1
            out.append((n, line))
    return out


def format_line_ref(line_ref):
    """"line 7" / "lines 20-21" — catalog/passages.py."""
    ref = (line_ref or "").strip()
    if not ref:
        return ""
    return f"lines {ref}" if "-" in ref else f"line {ref}"


def taxonomy_index():
    """(section code) -> {written subtopic -> (canonical name, {type slug: type name})}.

    The importer resolves a snake_case slug to its Title Case name before storing it,
    so a pack written `"subtopic": "literal_retrieval"` appears to the pupil as
    "Literal Retrieval". Showing the raw slug here would be showing something no
    pupil ever sees. Any problem reading the taxonomy returns {} and the preview
    falls back to the written value — this is a look, not a gate.
    """
    try:
        data = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    index = {}
    for code, sec in (data.get("sections") or {}).items():
        by_key = {}
        for sub in sec.get("subtopics") or []:
            types = {t.get("slug"): t.get("name", "") for t in sub.get("question_types") or []}
            entry = (sub.get("name", ""), types)
            by_key[sub.get("name", "")] = entry
            if sub.get("slug"):
                by_key[sub["slug"]] = entry
        index[code] = by_key
    return index


def subtopic_targets():
    """(section code) -> {subtopic name: target_questions}.

    Only for sections where taxonomy.json sets a per-subtopic target — today MAT
    and NVR; ENG and VR carry only a section-level figure. The batch overview
    shows this batch's own contribution against it, never bank-wide progress:
    this tool has no database access, by design, so it cannot know what the live
    bank already holds.
    """
    try:
        data = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for code, sec in (data.get("sections") or {}).items():
        targets = {sub.get("name", ""): sub["target_questions"]
                   for sub in sec.get("subtopics") or []
                   if "target_questions" in sub}
        if targets:
            out[code] = targets
    return out


# ---------------------------------------------------------------------------
# The page. One self-contained document: Bootstrap from the CDN (as base.html
# does), the CSS subset base.html defines for questions, then a vanilla-JS loop
# that steps through the questions client-side. %%BANNER%% and %%PACK%% are
# substituted per request.
# ---------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Question preview — RevisorPlus</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"
      onerror="window.__cssFailed=true">
<style>
 /* Copied from templates/base.html — keep in sync, or the preview stops matching
    the site. Only the subset question.html actually uses is here; the preview has
    no nav, dashboard or auth pages to style. */
 :root{
   color-scheme:light;
   --brand:#2563EB; --brand-dark:#1D4ED8; --brand-accent:#60A5FA; --brand-light:#DBEAFE;
   --ink:#0F172A; --body:#3F4C5F; --muted:#64748B; --border:#E6EBF2;
   --ok:#16A34A; --warn:#D97706; --bad:#DC2626;
   --surface:#FFFFFF; --canvas:#F6F8FC;
   --r-sm:.5rem; --r:.85rem; --ease:cubic-bezier(.22,.61,.36,1);
 }
 body{ background:var(--canvas); color:var(--body);
       font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }
 h1,h2,h3,h4,h5,h6{ color:var(--ink); font-weight:700; letter-spacing:-.018em; }
 .text-muted{ color:var(--muted) !important; }
 .text-brand{ color:var(--brand); }
 .btn{ border-radius:var(--r-sm); font-weight:600; }
 .btn-brand{ background:linear-gradient(135deg,var(--brand),#3B82F6); color:#fff; border:0; }
 .btn-brand:hover,.btn-brand:focus{ background:var(--brand-dark); color:#fff; }
 .card{ border:1px solid var(--border); border-radius:var(--r); background:var(--surface); }
 .bg-success{ background-color:var(--ok) !important; }
 .bg-brand-soft{ background:var(--brand-light); color:var(--brand-dark); }
 .badge{ border-radius:999px; font-weight:600; }
 label.list-group-item{
   cursor:pointer; border-radius:var(--r-sm) !important; border:1px solid var(--border);
   margin-bottom:.5rem; padding:.85rem 1rem; background:var(--surface);
 }
 label.list-group-item:hover{ border-color:var(--brand-accent); background:#FAFCFF; }
 label.list-group-item:has(input:checked){ border-color:var(--brand); background:var(--brand-light); }
 .list-group-item-success{ border-color:#86EFAC !important; background:#F0FDF4 !important; }
 .list-group-item-danger{ border-color:#FCA5A5 !important; background:#FEF2F2 !important; }
 /* Spot-the-error and click-the-word: the sentence itself is the control. */
 .selection-sentence{ font-size:1.15rem; line-height:2.5; }
 .selection-span{ display:inline; cursor:pointer; border-radius:var(--r-sm);
   padding:.15rem .1rem; border-bottom:2px solid transparent; }
 .selection-span:hover{ background:var(--brand-light); border-bottom-color:var(--brand-accent); }
 .selection-span:has(input:checked){ background:var(--brand-light); border-bottom-color:var(--brand); }
 .selection-letter{ display:inline-block; min-width:1.15rem; margin-right:.15rem;
   text-align:center; font-size:.7rem; font-weight:700; color:var(--muted); vertical-align:.55em; }
 .selection-span:has(input:checked) .selection-letter{ color:var(--brand-dark); }
 .selection-span.is-correct{ background:#F0FDF4; border-bottom-color:var(--ok); }
 .selection-span.is-correct .selection-letter{ color:var(--ok); }
 .selection-span.is-wrong{ background:#FEF2F2; border-bottom-color:var(--bad); }
 .selection-span.is-wrong .selection-letter{ color:var(--bad); }
 /* Non-verbal answers: a tile per option, holding its panel, its letter and its
    radio. Mirrors the .nvr-option block in templates/base.html — including
    --fig-scale and its two breakpoints, because the whole point of the preview
    is to show an author what a pupil will see, phone included. */
 :root{ --fig-scale:1; }
 @media (max-width:576px){ :root{ --fig-scale:.82; } }
 @media (max-width:400px){ :root{ --fig-scale:.70; } }
 .figure-scroll{ overflow-x:auto; max-width:100%; padding-bottom:.15rem; }
 .nvr-options{ display:flex; flex-wrap:wrap; gap:.75rem; }
 .nvr-option{ display:flex; flex-direction:column; align-items:center; gap:.35rem;
   justify-content:space-between;
   padding:.55rem .55rem .4rem; cursor:pointer; background:var(--surface);
   border:1px solid var(--border); border-radius:var(--r); }
 .nvr-option:hover{ border-color:var(--brand-accent); }
 .nvr-option:has(input:checked){ border-color:var(--brand); background:var(--brand-light); }
 .nvr-option-figure{ display:flex; align-items:center; flex:1 0 auto; line-height:0; }
 .nvr-option-letter{ font-size:.8rem; font-weight:700; color:var(--muted); }
 .nvr-option:has(input:checked) .nvr-option-letter{ color:var(--brand-dark); }
 .nvr-option.is-correct{ background:#F0FDF4; border-color:var(--ok); }
 .nvr-option.is-correct .nvr-option-letter{ color:var(--ok); }
 .nvr-option.is-wrong{ background:#FEF2F2; border-color:var(--bad); }
 .nvr-option.is-wrong .nvr-option-letter{ color:var(--bad); }
 /* Reading passages, numbered at the contract's fixed measure. */
 .passage-numbered{ display:grid; grid-template-columns:2.25rem 1fr; row-gap:.15rem; }
 .passage-num{ grid-column:1; text-align:right; padding-right:.75rem; color:var(--muted);
   font-variant-numeric:tabular-nums; font-size:.78em; user-select:none; }
 .passage-line{ grid-column:2; }
 .passage-gap{ grid-column:1 / -1; height:.6rem; }
 /* preview-only chrome, deliberately not part of the pupil view */
 .preview-bar{ background:#FEF3C7; border-bottom:1px solid #FDE68A; color:#78350F;
               font-size:.8125rem; padding:.4rem 0; }
 .author-strip{ background:#F8FAFC; border:1px dashed var(--border); border-radius:var(--r-sm);
                font-size:.8125rem; padding:.6rem .8rem; }
 .author-strip code{ color:var(--brand-dark); }
 .cdn-warn{ background:#FEE2E2; border-bottom:1px solid #FECACA; color:#7F1D1D;
            font-size:.8125rem; padding:.4rem 0; }
 /* Batch overview: a bar is a track + a filled amount, reused for both the
    difficulty and key-position histograms rather than two separate styles.
    !important on background: something in Bootstrap's cascade otherwise wins
    over these two plain single-class selectors despite loading first — traced
    empirically (an inline !important override was the only thing that painted
    a background at all), not worth chasing further for a two-rule widget. */
 .overview-bar-track{ height:.9rem; background:#E6EBF2 !important; border-radius:999px; }
 .overview-bar-fill{ height:100%; background:#60A5FA !important; border-radius:999px; }
</style>
</head>
<body>
<div class="cdn-warn" id="cdn-warn" hidden><div class="container">
 The page styling didn't load — that needs an internet connection, exactly as the real
 site does. Everything below is still your pack, just unstyled.
</div></div>
<div class="preview-bar"><div class="container">%%BANNER%%</div></div>
<nav class="navbar navbar-expand-lg bg-white border-bottom"><div class="container">
 <span class="navbar-brand fw-bold">Revisor<span class="text-brand">Plus</span></span>
 <div class="ms-auto d-flex align-items-center gap-3">
   <label class="form-check form-switch small text-muted mb-0 d-flex align-items-center gap-1"
          title="Hides every figure and image, showing only its text description in its place — a fast way to judge whether a question genuinely stands without sight.">
     <input class="form-check-input" type="checkbox" id="text-only-toggle" role="switch">
     Text-only view
   </label>
   <span class="text-muted small">Preview — your machine only</span>
 </div>
</div></nav>
<main class="container py-4" style="max-width:56rem"><div id="root"></div></main>
<script id="pack-data" type="application/json">%%PACK%%</script>
<script>
const PACK = JSON.parse(document.getElementById('pack-data').textContent);
const QS = PACK.questions, PASSAGES = PACK.passages;
const root = document.getElementById('root');
let idx = 0, submitted = false;
// 'overview' | 'question' | 'review' — a batch overview opens first so a tutor
// judging 50 questions can see key/difficulty spread and every warning at once,
// rather than only after paging through the whole thing.
let view = 'overview';
let textOnly = false;   // the nav-bar toggle; read by figureBlock() and control()
let answers = QS.map(() => null);   // option index, segment label, or typed string
let marks = QS.map(() => false);    // preview-only: "come back to this one"

function esc(s){
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// --- marking, mirroring catalog/marking.py -------------------------------
// Close enough to show an author whether their own answer key marks: JS's \w is
// ASCII where Python's is Unicode, and the word-number forms ("eleven") are not
// reproduced. catalog/marking.py is the truth; this only has to be honest about
// the common cases, and it is never what decides a pupil's mark.
function normalise(s){
  return String(s == null ? '' : s).normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
    .replace(/\u2019/g,"'").toLowerCase().trim()
    .replace(/[^\w\s'%/.\-]/g,' ').replace(/\s+/g,' ').trim();
}
function parseNumber(t){
  if (t == null || t === '') return null;
  const cleaned = String(t).replace(/[£$€,\s]/g,'').replace(/(\d)(st|nd|rd|th)\b/gi,'$1').trim();
  const frac = cleaned.match(/^(-?\d+)\s*\/\s*(\d+)$/);
  if (frac && Number(frac[2]) !== 0) return Number(frac[1]) / Number(frac[2]);
  const d = cleaned.match(/-?\d+(?:\.\d+)?/);
  return d ? Number(d[0]) : null;
}
function markNumeric(q, given){
  const target = parseNumber(q.answer), got = parseNumber(given);
  if (got === null || target === null) return false;
  const tol = Number(q.tolerance) || 0;
  if (Math.abs(got - target) <= tol) return true;
  return (q.accepted_alternatives || []).some(alt => {
    const a = parseNumber(alt);
    return (a !== null && Math.abs(got - a) <= tol) ||
           (normalise(alt) && normalise(alt) === normalise(given));
  });
}
function markShortText(q, given){
  const text = normalise(given);
  if (!text) return false;
  if (q.answer && normalise(q.answer) === text) return true;   // the key always counts
  return (q.accepted_alternatives || []).some(g => normalise(g) && text.includes(normalise(g)));
}
function isSelection(q){ return q.kind === 'error_span' || q.kind === 'select_word'; }
function isChoice(q){ return q.kind === 'mcq' || q.kind === 'cloze_gap'; }
function isTyped(q){ return q.kind === 'numeric' || q.kind === 'short_text'; }
function isGrouped(q){ return q.kind === 'grouped_options'; }
function isAnswered(i){
  const q = QS[i], a = answers[i];
  if (a === null) return false;
  // A grouped question's answer is one pick per bracket, held as an array with a
  // slot per bracket. It is not answered until every bracket has been filled.
  if (isGrouped(q)) return Array.isArray(a) && a.length === q.option_groups.length &&
    a.every(v => v !== null && v !== undefined);
  return typeof a === 'string' ? a.trim() !== '' : true;
}
function isRight(i){
  const q = QS[i], a = answers[i];
  if (!isAnswered(i)) return false;
  // Both brackets, or neither. One mark for the pair, as a paper gives.
  if (isGrouped(q)) return q.option_groups.every((g, k) => !!(g.options[a[k]] || {}).correct);
  if (isChoice(q)) return !!(q.options[a] || {}).correct;
  if (isSelection(q)) return a === q.answer;
  if (q.kind === 'numeric') return markNumeric(q, a);
  if (q.kind === 'short_text') return markShortText(q, a);
  return false;   // extended_text is never auto-marked
}

// --- passage -------------------------------------------------------------
// Lines arrive already wrapped and numbered by the server at the contract's
// 100-character measure, so the line an author cites is the line a pupil counts.
function passageBlock(p){
  if (!p) return '';
  let rows = '';
  p.lines.forEach(([n, line]) => {
    if (n === null){ rows += '<span class="passage-gap" aria-hidden="true"></span>'; return; }
    rows += '<span class="passage-num" aria-hidden="true">' + (n % %%EVERY%% === 0 ? n : '') +
      '</span><span class="passage-line">' + esc(line) + '</span>';
  });
  return '<div class="p-3 mb-3 bg-light rounded small border">' +
    (p.title ? '<h2 class="h6 mb-2 text-center">' + esc(p.title) + '</h2>' : '') +
    '<div class="passage-numbered">' + rows + '</div>' +
    (p.source_note ? '<p class="text-muted mt-3 mb-0" style="font-size:.75rem">' +
      esc(p.source_note) + '</p>' : '') + '</div>';
}

// --- the answer control, one per kind ------------------------------------
// `review` shows the marked state instead of a live control.
function control(q, i, review){
  const a = answers[i];
  if (isSelection(q)){
    // The stem IS the sentence, so it is rendered here as the control and NOT
    // repeated as the heading — templates/practice/question.html does the same,
    // and showing it twice invites an author to "fix" a spelling error that the
    // pupil is supposed to find.
    let spans = '';
    q.segments.forEach(seg => {
      const cls = !review ? '' : seg.label === q.answer ? ' is-correct'
                : seg.label === a ? ' is-wrong' : '';
      spans += '<label class="selection-span' + cls + '">' +
        '<input class="visually-hidden" type="radio" name="opt' + i + '" value="' +
          esc(seg.label) + '"' + (a === seg.label ? ' checked' : '') +
          (review ? ' disabled' : '') + '>' +
        '<span class="selection-letter" aria-hidden="true">' + esc(seg.label) + '</span>' +
        '<span class="selection-text">' + esc(seg.text) + '</span></label>';
    });
    let out = '<div class="selection-sentence my-3">' + spans + '</div>';
    if (q.allow_no_error){
      const cls = !review ? '' : q.answer === '%%NOERR%%' ? ' list-group-item-success'
                : a === '%%NOERR%%' ? ' list-group-item-danger' : '';
      out += '<label class="list-group-item d-flex align-items-center gap-2 mb-2' + cls + '">' +
        '<input class="form-check-input m-0" type="radio" name="opt' + i + '" value="%%NOERR%%"' +
        (a === '%%NOERR%%' ? ' checked' : '') + (review ? ' disabled' : '') + '>' +
        '<span><strong>%%NOERR%%</strong> &mdash; %%NOERRTEXT%%</span></label>';
    }
    return out;
  }
  if (isGrouped(q)){
    // One bracket at a time, side by side, the way the paper prints it. Each
    // bracket needs its own radio name or the browser treats every word as one
    // group and allows a single pick in total.
    let out = '';
    q.option_groups.forEach((g, k) => {
      let words = '';
      g.options.forEach((o, j) => {
        const picked = Array.isArray(a) && a[k] === j;
        const cls = !review ? '' : o.correct ? ' bg-success-subtle'
                  : picked ? ' bg-danger-subtle' : '';
        words += '<label class="d-flex align-items-center gap-2 px-1 py-1 rounded' + cls + '">' +
          '<input class="form-check-input m-0" type="radio" name="opt' + i + 'g' + k + '" ' +
            'value="' + j + '"' + (picked ? ' checked' : '') + (review ? ' disabled' : '') + '>' +
          '<span>' + esc(o.text) + '</span></label>';
      });
      out += '<fieldset class="border rounded p-2" style="min-width:9rem">' +
        '<legend class="float-none w-auto px-2 mb-0 small text-muted">Bracket ' +
        esc(g.group) + '</legend>' + words + '</fieldset>';
    });
    return '<div class="d-flex flex-wrap gap-3 my-3">' + out + '</div>';
  }
  if (isChoice(q)){
    // Answers that are pictures. Each option is a tile carrying its own panel,
    // its letter and its radio input, exactly as templates/practice/question.html
    // renders it — the letter is HTML so it cannot scale with the drawing.
    if (q.options.some(o => o.svg)){
      let tiles = '';
      q.options.forEach((o, j) => {
        const cls = !review ? '' : o.correct ? ' is-correct'
                  : j === a ? ' is-wrong' : '';
        tiles += '<label class="nvr-option' + cls + '">' +
          '<input class="visually-hidden" type="radio" name="opt' + i + '" value="' + j + '"' +
            (a === j ? ' checked' : '') + (review ? ' disabled' : '') + '>' +
          (textOnly
            ? '<span class="small text-center px-1" style="max-width:8rem">' + esc(o.text) + '</span>'
            : '<span class="nvr-option-figure" aria-hidden="true">' + (o.svg || '') + '</span>') +
          '<span class="nvr-option-letter">' + esc(o.label || (j + 1)) + '</span>' +
          '</label>';
      });
      // The descriptions are shown here and not on the live site. An author
      // needs to see that two options describe different pictures, which is
      // the check a pupil cannot do for them. Text-only mode already shows the
      // same text inline on the tile, so the collapsed duplicate is skipped.
      if (textOnly) return '<div class="nvr-options my-3">' + tiles + '</div>';
      let described = '';
      q.options.forEach((o, j) => {
        described += '<div><b>' + esc(o.label || (j + 1)) + '</b> ' + esc(o.text) +
          (o.correct ? ' <span class="badge bg-success">key</span>' : '') + '</div>';
      });
      return '<div class="nvr-options my-3">' + tiles + '</div>' +
        '<details class="small text-muted mb-2"><summary>What each answer says in words' +
        ' (screen readers, and a failed drawing)</summary>' + described + '</details>';
    }
    let out = '';
    q.options.forEach((o, j) => {
      const cls = !review ? '' : o.correct ? ' list-group-item-success'
                : j === a ? ' list-group-item-danger' : '';
      out += '<label class="list-group-item d-flex align-items-center gap-2' + cls + '">' +
        '<input class="form-check-input m-0" type="radio" name="opt' + i + '" value="' + j + '"' +
        (a === j ? ' checked' : '') + (review ? ' disabled' : '') + '>' +
        '<span>' + esc(o.text) + '</span>' +
        (review && o.correct ? '<span class="ms-auto badge bg-success">Correct</span>' : '') +
        (review && j === a && !o.correct ? '<span class="ms-auto badge bg-danger">You put this</span>' : '') +
        '</label>';
    });
    return '<div class="list-group my-2">' + out + '</div>';
  }
  if (q.kind === 'extended_text'){
    return '<div class="my-3">' +
      '<label class="form-label small" for="ans' + i + '">Your answer</label>' +
      '<textarea class="form-control" id="ans' + i + '" rows="8"' + (review ? ' disabled' : '') +
        '>' + esc(a || '') + '</textarea>' +
      '<div class="form-text">A teacher marks this one, so it won\'t be scored straight away.</div>' +
      '</div>';
  }
  // numeric / short_text. Deliberately type="text", as question.html is: type=number
  // blocks "1/2" and silently swallows characters on mobile.
  return '<div class="my-3" style="max-width:22rem">' +
    '<label class="form-label small" for="ans' + i + '">Your answer</label>' +
    '<div class="input-group">' +
      '<input type="text" class="form-control form-control-lg" id="ans' + i + '" ' +
        'value="' + esc(a || '') + '" autocomplete="off"' + (review ? ' disabled' : '') + '>' +
      (q.unit ? '<span class="input-group-text">' + esc(q.unit) + '</span>' : '') +
    '</div>' +
    (q.kind === 'short_text' ? '<div class="form-text">A word or short phrase is enough.</div>' : '') +
    '</div>';
}

// The heading a pupil reads. A selection question's stem is the sentence below it,
// so the heading carries the instruction the printed paper puts above the block.
function heading(q){
  // A pack-supplied instruction has already been printed above, so these two
  // standing lines are dropped rather than stating the task a second time.
  if (isSelection(q)) return q.instruction ? '' :
    (q.kind === 'error_span' ? 'Which part of the sentence contains a mistake?'
                             : 'Click the correct word.');
  return q.stem;
}
// The instruction and worked example a paper prints once above a block. Shown on
// every question because that is how a pupil meets it in practice: a deck is
// dealt across subtopics, so an item arrives out of its block.
function instructionBlock(q){
  if (!q.instruction) return '';
  return '<div class="p-3 mb-3 border-start border-3 border-brand bg-light rounded-end">' +
    '<p class="mb-0 small">' + esc(q.instruction) + '</p>' +
    (q.worked_example ? '<p class="mb-0 mt-2 small text-muted"><strong>Example.</strong> ' +
      esc(q.worked_example) + '</p>' : '') + '</div>';
}
// A shared code grid, drawn the way catalog/figures.py draws it: a blank cell is
// the value the pupil has to supply, so it renders as an empty box rather than
// the word "null".
function tableBlock(q){
  const t = q.table;
  if (!t) return '';
  let head = '';
  (t.headers || []).forEach(h => { head += '<th>' + esc(h) + '</th>'; });
  let body = '';
  (t.rows || []).forEach(row => {
    body += '<tr>';
    row.forEach(c => {
      const blank = c === null || c === undefined || String(c).trim() === '';
      body += blank ? '<td class="bg-light">&nbsp;</td>' : '<td>' + esc(c) + '</td>';
    });
    body += '</tr>';
  });
  return '<div class="table-responsive mb-3"><table class="table table-sm table-bordered ' +
    'align-middle mb-0" style="width:auto"><thead><tr>' + head + '</tr></thead><tbody>' +
    body + '</tbody></table></div>';
}
function headingBadges(q){
  let b = '';
  if (q.line_ref_label) b += ' <span class="badge bg-light text-dark border align-middle">' +
    esc(q.line_ref_label) + '</span>';
  if (q.gap_number) b += ' <span class="badge bg-brand-soft align-middle">Gap ' +
    esc(q.gap_number) + '</span>';
  if (q.marks > 1) b += ' <span class="badge bg-light text-dark border align-middle">' +
    esc(q.marks) + ' marks</span>';
  return b;
}
// A generic, unmistakably-fake bar chart, for the one gap `figure` cannot draw:
// bar/pie/line/pictogram charts are not in the closed vocabulary (see
// elevenplus_data/CLAUDE.md), so a Statistics & Data question with no committed
// `image` renders nothing at all today. This lets a tutor judge roughly where a
// chart will sit before the real file exists — it is NOT data-driven (the pack
// format has no chart-data field to draw from, and inventing one here would be a
// second, unofficial chart renderer the live site does not have) and says so.
function statsPlaceholder(){
  return '<div class="mb-3">' +
    '<div class="alert alert-warning small mb-2"><strong>PLACEHOLDER</strong> — not what ' +
    'pupils will see. This subtopic needs a committed <code>image</code>: bar, pie, line and ' +
    'pictogram charts are not in the drawable figure vocabulary.</div>' +
    '<svg viewBox="0 0 220 120" width="220" height="120" role="img" ' +
    'aria-label="Placeholder bar chart, not real data" ' +
    'style="background:#F6F8FC;border:1px dashed #CBD5E1;border-radius:.5rem">' +
    '<line x1="20" y1="10" x2="20" y2="100" stroke="#94A3B8"/>' +
    '<line x1="20" y1="100" x2="210" y2="100" stroke="#94A3B8"/>' +
    '<rect x="35" y="55" width="24" height="45" fill="#CBD5E1"/>' +
    '<rect x="75" y="30" width="24" height="70" fill="#CBD5E1"/>' +
    '<rect x="115" y="70" width="24" height="30" fill="#CBD5E1"/>' +
    '<rect x="155" y="45" width="24" height="55" fill="#CBD5E1"/>' +
    '</svg></div>';
}
function isStats(q){ return q.section_code === 'MAT' && q.subtopic_display === 'Statistics & Data'; }
function figureBlock(q, i){
  // A figure declared as data is drawn by catalog/figures, in Python, before
  // this page is written — the same code the live site runs, not a copy of it
  // in JavaScript. A preview that draws its own version of the figures is a
  // preview that can disagree with the site, which is how this tool spent weeks
  // showing authors passage line numbers the live site did not agree with.
  if (textOnly){
    // The same honesty elevenplus_data/CLAUDE.md asks of NVR authors, turned
    // into a check: show exactly what a pupil who cannot see the picture is
    // actually left with, which for a stem figure is sometimes nothing at all.
    if (q.figure_svg) return '<div class="alert alert-secondary small mb-3">' +
      '<strong>Text-only view.</strong> ' + (q.figure_alt ? esc(q.figure_alt)
        : '<span class="text-danger">No text description (\'alt\') was given for this ' +
          'figure — a pupil who cannot see it has nothing to go on.</span>') + '</div>';
    if (q.image) return '<div class="alert alert-secondary small mb-3">' +
      '<strong>Text-only view.</strong> <span class="text-danger">The pack format has no ' +
      'text-description field for an <code>image</code> figure — a pupil who cannot see it ' +
      'has nothing to go on.</span></div>';
    if (isStats(q)) return '<div class="alert alert-secondary small mb-3">' +
      '<strong>Text-only view.</strong> This Statistics &amp; Data question needs a ' +
      'committed chart image — nothing to describe yet.</div>';
    return '';
  }
  if (q.figure_svg) return '<div class="mb-3">' + q.figure_svg + '</div>';
  if (q.image) return '<img src="' + esc(q.image_url) + '" class="img-fluid border rounded mb-3" ' +
    'alt="Figure for this question" data-fig="' + i + '"><div data-figerr="' + i + '"></div>';
  if (isStats(q)) return statsPlaceholder();
  return '';
}
// A missing figure is one of the things a preview is FOR — say so loudly, and say
// where the file was looked for. An author cannot see static/questions/ from here,
// and a question whose answer depends on a figure is unanswerable without it.
function wireFigures(){
  root.querySelectorAll('[data-fig]').forEach(img => {
    const i = Number(img.dataset.fig), q = QS[i];
    img.addEventListener('error', () => {
      img.remove();
      const slot = root.querySelector('[data-figerr="' + i + '"]');
      if (slot) slot.innerHTML = '<div class="alert alert-warning small">' +
        '<strong>Figure not found</strong> at <code>' + esc(q.image_url) + '</code>. ' +
        '<code>image</code> is resolved under <code>static/questions/</code>, exactly ' +
        'as the live template does. ' + esc(q.image_hint) + '</div>';
    });
  });
}

// --- confusable options ---------------------------------------------------
// validate_questions.py already errors on two option figures that draw the
// EXACT same picture (see _check_option_figures). What it cannot catch by
// design is a near-miss a human should still look at — a 15° rotation, `hatch`
// vs `cross_hatch` — so this complements it rather than repeating it: a plain
// data diff against the key, not a new rendering check.
function flattenSpec(obj, prefix, out){
  out = out || {};
  if (Array.isArray(obj)){
    obj.forEach((v, i) => flattenSpec(v, (prefix || '') + '[' + i + ']', out));
  } else if (obj !== null && typeof obj === 'object'){
    Object.keys(obj).forEach(k => flattenSpec(obj[k], prefix ? prefix + '.' + k : k, out));
  } else {
    out[prefix] = obj;
  }
  return out;
}
function specDiffKeys(a, b){
  const fa = flattenSpec(a || {}), fb = flattenSpec(b || {});
  const keys = new Set(Object.keys(fa).concat(Object.keys(fb)));
  const diffs = [];
  keys.forEach(k => { if (JSON.stringify(fa[k]) !== JSON.stringify(fb[k])) diffs.push(k); });
  return diffs.sort();
}
function confusableOptionsBlock(q){
  if (!q.options.some(o => o.figure_data)) return '';
  const ref = q.options.find(o => o.correct) || q.options[0];
  const rows = q.options.filter(o => o !== ref).map(o => {
    const diffs = specDiffKeys(ref.figure_data, o.figure_data);
    return '<div>' + esc(o.label) + ' vs key: ' + (diffs.length
      ? '<code>' + diffs.map(esc).join(', ') + '</code>'
      : '<span class="text-danger">identical spec — the validator should have refused ' +
        'this pack</span>') + '</div>';
  }).join('');
  return '<div class="mt-1"><details><summary class="small text-muted">Option spec ' +
    'differences vs. the key (a near-miss the exact-duplicate check can\'t catch)</summary>' +
    rows + '</details></div>';
}

// --- the author strip ----------------------------------------------------
// Everything a pupil never sees. The three mistakes this is here to catch are a
// mis-set difficulty, a wrong question_type, and a distractor that is arguably
// also correct — so difficulty carries its rubric word, the question type carries
// its taxonomy name, and the key is marked in the option list above.
function authorStrip(q, i){
  const bits = [];
  bits.push('#' + esc(q.number || (i + 1)) + (q.ref ? ' &middot; <code>' + esc(q.ref) + '</code>' : ''));
  bits.push(esc(q.section_code) + ' &middot; ' + esc(q.subtopic_display) +
    (q.subtopic_note ? ' <span class="text-danger">(' + esc(q.subtopic_note) + ')</span>' : ''));
  if (q.question_type || q.section_code !== 'NVR')
    bits.push('<code>' + esc(q.question_type || '(none)') + '</code>' +
      (q.question_type_name ? ' &mdash; ' + esc(q.question_type_name) : '') +
      (q.question_type_note ? ' <span class="text-danger">(' + esc(q.question_type_note) +
        ')</span>' : ''));
  bits.push('difficulty <strong>' + esc(q.difficulty) + '</strong>' +
    (q.difficulty_word ? ' &mdash; ' + esc(q.difficulty_word) : '') +
    (q.difficulty_note ? ' <span class="text-danger">(' + esc(q.difficulty_note) + ')</span>' : ''));
  bits.push('<code>' + esc(q.kind) + '</code>');
  if (q.passage_key !== null) bits.push('passage <code>' + esc(q.passage_ref || 'inline') + '</code>');
  bits.push(esc(q.pack));
  let extra = '';
  if (isTyped(q)) extra += '<div class="mt-1">answer <code>' + esc(q.answer) + '</code>' +
    (q.unit ? ' + unit <code>' + esc(q.unit) + '</code>' : '') +
    (q.kind === 'numeric' ? ' &middot; tolerance ' + esc(q.tolerance) : '') + '</div>';
  // Alternatives are shown in full: a list that misses an obvious synonym marks a
  // right answer wrong, and nothing but reading it catches that.
  if (q.kind === 'short_text' || (q.kind === 'numeric' && q.accepted_alternatives.length))
    extra += '<div class="mt-1">also accepted: ' + (q.accepted_alternatives.length
      ? q.accepted_alternatives.map(a => '<code>' + esc(a) + '</code>').join(', ')
      : '<span class="text-warning-emphasis">nothing &mdash; only the exact answer marks</span>') +
      '</div>';
  if (isSelection(q)) extra += '<div class="mt-1">key <code>' + esc(q.answer) + '</code>' +
    (q.kind === 'error_span' && !q.allow_no_error
      ? ' <span class="text-danger">no <code>allow_no_error</code> &mdash; a pupil who thinks ' +
        'the sentence is already correct cannot say so</span>' : '') +
    (q.segments_note ? ' <span class="text-danger">' + esc(q.segments_note) + '</span>' : '') +
    '</div>';
  if (q.kind === 'extended_text') extra += '<div class="mt-1">' + esc(q.marks) + ' marks, ' +
    (q.model_answer ? 'model answer given' : '<span class="text-danger">no model answer</span>') +
    ', ' + (q.rubric ? 'rubric given' : '<span class="text-danger">no rubric</span>') + '</div>';
  if (q.kind === 'cloze_gap' && q.gap_note)
    extra += '<div class="mt-1 text-muted">' + esc(q.gap_note) + '</div>';
  if (q.also_tests.length) extra += '<div class="mt-1">also tests: ' +
    q.also_tests.map(t => esc((t.subtopic || '') + ' / ' + (t.question_type || ''))).join('; ') +
    '</div>';
  extra += confusableOptionsBlock(q);
  return '<div class="author-strip mt-3"><div>' + bits.join(' &middot; ') + '</div>' + extra + '</div>';
}

// --- the batch overview ----------------------------------------------------
// Shown first, and reachable again from either the question or review screen:
// a tutor judging a 50-question batch a page at a time cannot see a skewed
// answer key or an unbalanced difficulty spread until they have read the whole
// thing. Reuses whatever is already on each question (the same fields
// authorStrip() reads) rather than defining a second, parallel notion of what
// counts as a warning.
function collectWarnings(){
  const out = [];
  const flag = (i, text) => out.push({i, text});
  QS.forEach((q, i) => {
    if (q.subtopic_note) flag(i, q.subtopic_note);
    if (q.question_type_note) flag(i, q.question_type_note);
    if (q.difficulty_note) flag(i, q.difficulty_note);
    if (q.segments_note) flag(i, q.segments_note);
    if (!q.explanation) flag(i, 'no explanation');
    if (q.kind === 'error_span' && !q.allow_no_error) flag(i, 'no allow_no_error');
    if (q.kind === 'extended_text' && !q.model_answer && !q.rubric)
      flag(i, 'no rubric or model answer');
    if (q.kind === 'short_text' && !q.accepted_alternatives.length)
      flag(i, 'no accepted_alternatives');
    if (isStats(q) && !q.image && !q.figure_svg)
      flag(i, 'Statistics & Data with no committed image — placeholder chart shown');
  });
  return out;
}
function barRow(label, n, max, extra){
  return '<div class="d-flex align-items-center gap-2 small mb-1">' +
    '<span style="width:1.75rem">' + esc(label) + '</span>' +
    '<div class="overview-bar-track flex-grow-1"><div class="overview-bar-fill" style="width:' +
    (max ? Math.round(100 * n / max) : 0) + '%"></div></div>' +
    '<span class="text-muted" style="width:1.75rem">' + n + '</span>' +
    (extra || '') + '</div>';
}
function renderOverview(){
  const diff = {};
  QS.forEach(q => { diff[q.difficulty] = (diff[q.difficulty] || 0) + 1; });
  const diffMax = Math.max(1, ...[1, 2, 3, 4, 5].map(d => diff[d] || 0));
  const diffRows = [1, 2, 3, 4, 5].map(d => barRow(d, diff[d] || 0, diffMax)).join('');

  const spread = PACK.key_spread || {counts: {}, messages: []};
  const letters = Object.keys(spread.counts);
  const keyMax = Math.max(1, ...Object.values(spread.counts));
  const keyRows = letters.length ? letters.map(l => barRow(l, spread.counts[l], keyMax)).join('')
    : '<p class="text-muted small mb-0">No multiple-choice or cloze-gap questions to check.</p>';
  const keyWarnings = spread.messages.length
    ? '<ul class="small text-danger mt-2 mb-0 ps-3">' +
      spread.messages.map(m => '<li>' + esc(m) + '</li>').join('') + '</ul>'
    : '<p class="small text-success mt-2 mb-0">No run or skew warnings.</p>';

  const targets = PACK.targets || {};
  const bySection = {};
  QS.forEach(q => {
    (bySection[q.section_code] = bySection[q.section_code] || {})[q.subtopic_display] =
      (bySection[q.section_code][q.subtopic_display] || 0) + 1;
  });
  let progressHtml = Object.keys(bySection).sort().map(section => {
    const secTargets = targets[section];
    if (!secTargets) return '<h3 class="h6 mt-3">' + esc(section) + '</h3>' +
      '<p class="small text-muted">No per-subtopic targets set for this section yet in ' +
      'taxonomy.json.</p>';
    const rows = Object.keys(bySection[section]).sort().map(sub => {
      const n = bySection[section][sub], target = secTargets[sub];
      return '<div class="mb-1 small">' + esc(sub) + ': <strong>' + n +
        (target ? ' of ' + target + ' target' : ' — no target set for this subtopic') +
        '</strong> <span class="text-muted">(this batch’s contribution only, not the ' +
        'live bank)</span></div>';
    }).join('');
    return '<h3 class="h6 mt-3">' + esc(section) + '</h3>' + rows;
  }).join('');
  if (!progressHtml) progressHtml = '<p class="small text-muted">No questions loaded.</p>';

  const warnings = collectWarnings();
  const warningsHtml = warnings.length
    ? '<div class="list-group">' + warnings.map(w =>
        '<button type="button" class="list-group-item list-group-item-action small overview-jump" ' +
        'data-goto="' + w.i + '">Q' + (w.i + 1) + ' — ' + esc(w.text) + '</button>').join('') +
      '</div>'
    : '<p class="small text-success mb-0">Nothing flagged.</p>';

  root.innerHTML =
    '<div class="card mb-3"><div class="card-body">' +
      '<h1 class="h4 mb-1">Batch overview</h1>' +
      '<p class="text-muted small mb-3">' + QS.length + ' question' +
        (QS.length === 1 ? '' : 's') + ' across ' + PACK.names.length + ' file' +
        (PACK.names.length === 1 ? '' : 's') + '.</p>' +
      '<div class="row g-4">' +
        '<div class="col-md-6"><h2 class="h6">Difficulty spread</h2>' + diffRows + '</div>' +
        '<div class="col-md-6"><h2 class="h6">Key position spread</h2>' + keyRows +
          keyWarnings + '</div>' +
      '</div>' +
      '<h2 class="h6 mt-4">Subtopic progress</h2>' + progressHtml +
      '<h2 class="h6 mt-4">Warnings</h2>' + warningsHtml +
      '<div class="text-center mt-4"><button type="button" id="start-review" ' +
        'class="btn btn-brand">Start reviewing question 1</button></div>' +
    '</div></div>';

  document.getElementById('start-review').addEventListener('click', () => {
    view = 'question'; idx = 0; render();
  });
  root.querySelectorAll('.overview-jump').forEach(b => b.addEventListener('click', () => {
    view = 'question'; idx = Number(b.dataset.goto); render();
  }));
}

// --- the pupil view ------------------------------------------------------
function renderQuestion(){
  const q = QS[idx], total = QS.length;
  let nav = '';
  QS.forEach((_, i) => {
    const cls = i === idx ? 'btn-brand'
              : isAnswered(i) ? 'btn-outline-success' : 'btn-outline-secondary';
    nav += '<button type="button" class="btn btn-sm ' + cls + ' nav-q" data-goto="' + i + '">' +
      (i + 1) + '</button>';
  });
  const blanks = QS.filter((_, i) => !isAnswered(i)).length;

  root.innerHTML =
   '<div class="d-flex justify-content-between align-items-center mb-2">' +
    '<span class="badge bg-light text-dark border">' + esc(q.section_code) + ' &middot; ' +
      esc(q.subtopic_display) + '</span>' +
    '<div class="d-flex align-items-center gap-2">' +
      '<span class="text-muted small">Question ' + (idx + 1) + ' of ' + total + '</span>' +
      '<button type="button" id="show-overview" class="btn btn-sm btn-outline-secondary">' +
        'Overview</button>' +
      '<button type="button" id="submit-open" class="btn btn-sm btn-brand">Submit</button>' +
    '</div></div>' +
   '<div class="d-flex flex-wrap gap-1 mb-3">' + nav + '</div>' +
   '<div class="card"><div class="card-body">' +
     passageBlock(PASSAGES[q.passage_key]) +
     instructionBlock(q) +
     '<h1 class="h5 mb-3">' + esc(heading(q)) + headingBadges(q) + '</h1>' +
     tableBlock(q) + figureBlock(q, idx) +
     '<form id="qform">' + control(q, idx, false) +
       '<div class="d-flex justify-content-between mt-3">' +
         '<button type="button" class="btn btn-outline-secondary nav-q" data-goto="' + (idx - 1) +
           '"' + (idx === 0 ? ' disabled' : '') + '>Back</button>' +
         '<button type="button" class="btn btn-brand nav-q" data-goto="' + (idx + 1) + '"' +
           (idx + 1 >= total ? ' disabled' : '') + '>Next</button>' +
       '</div></form>' +
     authorStrip(q, idx) +
   '</div></div>' +
   // The real page uses server-rendered pages, not a modal; this native <dialog>
   // just stops a stray click ending the run. No .card on the <dialog> itself:
   // Bootstrap's .card sets display:flex, which beats dialog:not([open]).
   '<dialog id="confirm-submit" class="p-0 border-0 bg-transparent">' +
     '<div class="card"><div class="card-body" style="max-width:32rem">' +
       '<h2 class="h5">Ready to submit?</h2>' +
       '<p class="mb-0">You will see how each question marked, with its explanation ' +
         'and the details you filed it under.</p>' +
       (blanks ? '<p class="text-danger small mt-2 mb-0">' + blanks + ' question' +
         (blanks === 1 ? ' is' : 's are') + ' still unanswered.</p>' : '') +
       '<div class="d-flex justify-content-end gap-2 mt-3">' +
         '<button type="button" id="confirm-no" class="btn btn-outline-secondary">Keep going</button>' +
         '<button type="button" id="confirm-yes" class="btn btn-brand">Submit</button>' +
       '</div></div></div></dialog>';

  const form = document.getElementById('qform');
  form.addEventListener('change', e => {
    if (e.target.type === 'radio'){
      if (isGrouped(q)){
        // One slot per bracket, filled independently. The radio's name carries
        // which bracket it belongs to: opt<question>g<bracket>.
        const k = Number(e.target.name.split('g').pop());
        const cur = Array.isArray(answers[idx])
          ? answers[idx].slice() : new Array(q.option_groups.length).fill(null);
        cur[k] = Number(e.target.value);
        answers[idx] = cur;
      } else {
        answers[idx] = isChoice(q) ? Number(e.target.value) : e.target.value;
      }
      render();   // repaint the jump list and the blank count
    }
  });
  // Typed answers must NOT re-render on every keystroke — that would blur the box.
  form.addEventListener('input', e => {
    if (e.target.tagName === 'INPUT' && e.target.type === 'text') answers[idx] = e.target.value;
    if (e.target.tagName === 'TEXTAREA') answers[idx] = e.target.value;
  });

  wireFigures();
  root.querySelectorAll('.nav-q').forEach(b => b.addEventListener('click', () => {
    const to = Number(b.dataset.goto);
    if (to >= 0 && to < QS.length){ idx = to; render(); }
  }));
  document.getElementById('show-overview').addEventListener('click', () => {
    view = 'overview'; render();
  });
  const dlg = document.getElementById('confirm-submit');
  document.getElementById('submit-open').addEventListener('click', () => dlg.showModal());
  document.getElementById('confirm-no').addEventListener('click', () => dlg.close());
  document.getElementById('confirm-yes').addEventListener('click', () => {
    dlg.close(); submitted = true; render();
  });
}

// --- the review ----------------------------------------------------------
function renderReview(){
  const auto = QS.filter(q => q.kind !== 'extended_text').length;
  const score = QS.filter((_, i) => isRight(i)).length;
  const forMarking = QS.length - auto;

  let cards = '', lastPassage = -2;
  QS.forEach((q, i) => {
    // The passage is rendered once for the run of questions that share it, not
    // reprinted per question: the container it comes from is never a question in
    // its own right, and repeating it hides how much text a pupil is really given.
    if (q.passage_key !== lastPassage){
      lastPassage = q.passage_key;
      if (q.passage_key !== null) cards += '<div class="card mb-3"><div class="card-body">' +
        passageBlock(PASSAGES[q.passage_key]) +
        '<div class="text-muted small">The questions below share this passage. It is one ' +
        'container row on import and is never served to a pupil on its own.</div></div></div>';
    }
    const badge = q.kind === 'extended_text'
        ? '<span class="badge bg-info text-dark">for a teacher to mark</span>'
      : !isAnswered(i) ? '<span class="badge bg-secondary">Not answered</span>'
      : isRight(i) ? '<span class="badge bg-success">Correct</span>'
      : '<span class="badge bg-danger">Incorrect</span>';
    let put = '';
    if (isTyped(q) || q.kind === 'extended_text')
      put = '<div class="small mb-2">You put: <strong>' +
        (isAnswered(i) ? esc(answers[i]) : '&mdash; nothing &mdash;') + '</strong>' +
        (isTyped(q) ? ' &middot; answer: <strong class="text-success">' + esc(q.answer) +
          esc(q.unit) + '</strong>' : '') + '</div>';
    cards +=
      '<div class="card mb-3"><div class="card-body">' +
        '<div class="d-flex justify-content-between align-items-start gap-2 mb-2">' +
          '<div class="d-flex align-items-center gap-2">' +
            '<span class="text-muted small">Question ' + (i + 1) + '</span>' + badge + '</div>' +
          '<button type="button" class="btn btn-sm ' +
            (marks[i] ? 'btn-danger' : 'btn-outline-danger') + ' mark-q" data-mark="' + i + '" ' +
            'title="Preview-only note to yourself. The site has no flagging.">Needs work</button>' +
        '</div>' +
        instructionBlock(q) +
        '<h2 class="h6 mb-3">' + esc(heading(q)) + headingBadges(q) + '</h2>' +
        tableBlock(q) + figureBlock(q, i) + put + control(q, i, true) +
        (q.kind === 'extended_text' && q.model_answer
          ? '<div class="alert alert-info small mb-0">A strong answer would cover: ' +
            esc(q.model_answer) + '</div>' : '') +
        (q.explanation ? '<div class="alert alert-secondary mb-0 mt-2">' +
          '<strong class="d-block small text-uppercase">Explanation</strong>' +
          esc(q.explanation) + '</div>'
          : '<div class="alert alert-warning small mb-0 mt-2">No explanation. A pupil who got ' +
            'this wrong is told only that they were wrong.</div>') +
        authorStrip(q, i) +
      '</div></div>';
  });

  root.innerHTML =
    '<div class="card mb-3"><div class="card-body text-center py-4">' +
      '<h1 class="h3">End of preview</h1>' +
      '<p class="lead mb-0">Auto-marked <span class="text-brand fw-bold">' + score + '/' + auto +
      '</span>' + (forMarking ? ', plus ' + forMarking + ' for a teacher to mark' : '') + '.</p>' +
      '</div></div>' + cards +
    '<div class="text-center my-4">' +
      '<button type="button" id="show-overview" class="btn btn-outline-secondary me-2">' +
        'Overview</button>' +
      '<button type="button" id="again" class="btn btn-brand">Start again</button>' +
    '</div>';

  wireFigures();
  root.querySelectorAll('.mark-q').forEach(b => b.addEventListener('click', () => {
    const i = Number(b.dataset.mark);
    marks[i] = !marks[i];
    b.classList.toggle('btn-danger', marks[i]);
    b.classList.toggle('btn-outline-danger', !marks[i]);
  }));
  document.getElementById('show-overview').addEventListener('click', () => {
    view = 'overview'; render();
  });
  document.getElementById('again').addEventListener('click', () => {
    idx = 0; submitted = false;
    answers = QS.map(() => null); marks = QS.map(() => false);
    render();
  });
}

function render(){
  if (submitted) return renderReview();
  if (view === 'overview') return renderOverview();
  return renderQuestion();
}

document.getElementById('text-only-toggle').addEventListener('change', e => {
  textOnly = e.target.checked;
  render();
});

if (window.__cssFailed) document.getElementById('cdn-warn').hidden = false;
if (QS.length) render();
else root.innerHTML = '<div class="alert alert-info">Nothing to preview yet — no ' +
  'questions in this pack. Write one, then refresh.</div>';
</script>
</body>
</html>
"""

ERROR_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Preview — problem reading the pack</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head><body><main class="container py-5" style="max-width:44rem">
<h1 class="h4 mb-3">The pack couldn't be read</h1>
%%BODY%%
<p class="text-muted small mt-4">Fix the file and refresh this page — nothing needs restarting.</p>
</main></body></html>
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _resolve_figure(figure):
    """A pack's figure, resolving a `template_id` if it carries one.

    Mirrors `import_pack.py`'s `_resolve_figure` — this tool renders straight
    from the pack file rather than the database, so a templated figure needs
    the same resolution here or it would draw nothing. Silent on a bad
    template: this page is a look, not a gate, so an unknown id or missing
    slot data draws a blank figure rather than crashing the preview —
    `validate_questions.py` is where that is an error.
    """
    if not isinstance(figure, dict) or "template_id" not in figure:
        return figure
    template = TEMPLATES.get(figure["template_id"])
    if template is None:
        return None
    try:
        return template.build(figure.get("data") or {})
    except (KeyError, TypeError, ValueError):
        return None


def _image_hint(image):
    """Where the file was looked for, for the figure-not-found alert.

    The contract and the live template used to disagree: CLAUDE.md said "filename
    only, committed under static/questions/", while question.html rendered
    `{% static q.context_image %}`, which resolves a bare filename to
    /static/<filename>. That was settled in favour of the contract — the template
    now prefixes `questions/`, so a filename is all an author ever writes and both
    resolve to the same place. This preview does the same, so it stays a faithful
    preview rather than a second opinion.

    What is left to report is the ordinary case: the file was not committed.
    """
    if (STATIC_ROOT / image).is_file():
        return (f"There is a file at static/{image}, but question figures are "
                f"looked for in static/questions/. Move it there — `image` is a "
                f"filename and the folder is fixed.")
    return (f"No file at static/questions/{image}. Commit the figure there; "
            f"`image` is the filename only, with no path.")


def _passage_entry(store, title, source_note, text, ref):
    """Intern one passage; questions sharing text share an entry (and so a heading)."""
    key = (title, source_note, text)
    if key not in store:
        store[key] = {
            "index": len(store),
            "title": title, "source_note": source_note, "ref": ref,
            "lines": [[n, line] for n, line in passage_lines(text)],
        }
    return store[key]["index"]


def load_packs(paths):
    """Read every pack and flatten to one question list. Returns (data, errors).

    A missing file or a syntax error becomes a banner, never a traceback: an author
    hits save mid-edit and refreshes, and a preview that dies on a stray comma is a
    preview they stop using.
    """
    taxonomy = taxonomy_index()
    questions, errors, names = [], [], []
    passage_store = {}

    for p in paths:
        path = Path(p)
        names.append(path.name)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(f"{path}: file not found.")
            continue
        except json.JSONDecodeError as e:
            errors.append(f"{path}: not valid JSON — {e} (line {e.lineno}, column {e.colno}).")
            continue
        except OSError as e:
            errors.append(f"{path}: could not be read — {e}.")
            continue
        if not isinstance(raw, dict):
            errors.append(f"{path}: the top level should be an object with "
                          f"'section' and 'questions'.")
            continue

        sec = raw.get("section") if isinstance(raw.get("section"), dict) else {}
        code = sec.get("code", "??")
        subs = taxonomy.get(code, {})

        # Shared passages, declared once at the top of the pack. A question points at
        # one with passage_ref; on import that becomes a container row.
        declared = {}
        for pas in raw.get("passages") or []:
            if not isinstance(pas, dict) or not pas.get("passage_ref"):
                continue
            declared[pas["passage_ref"]] = (
                _passage_entry(passage_store, pas.get("title", ""), pas.get("source_note", ""),
                               pas.get("text", ""), pas["passage_ref"]),
                str(pas.get("text", "")),
            )

        # Shared instruction blocks and data tables. Unlike a passage these are
        # copied onto each question rather than rendered once above a run, because
        # that is what the importer does and what a pupil meets: a practice deck
        # deals a question out of its block.
        declared_groups = {g["group_ref"]: g for g in (raw.get("groups") or [])
                           if isinstance(g, dict) and g.get("group_ref")}
        declared_tables = {t["table_ref"]: t for t in (raw.get("tables") or [])
                           if isinstance(t, dict) and t.get("table_ref")}

        for i, q in enumerate(raw.get("questions") or []):
            if not isinstance(q, dict):
                continue
            kind = q.get("kind") or "mcq"

            g_ref = q.get("group_ref")
            block = declared_groups.get(g_ref) or {}
            if g_ref and not block:
                errors.append(f"{path.name} q{i + 1}: group_ref '{g_ref}' is not in "
                              f"this pack's 'groups'.")
            t_ref = q.get("table_ref")
            shared_table = declared_tables.get(t_ref)
            if t_ref and shared_table is None:
                errors.append(f"{path.name} q{i + 1}: table_ref '{t_ref}' is not in "
                              f"this pack's 'tables'.")
            written = q.get("subtopic", "")
            canonical, types = subs.get(written, ("", {}))
            qtype = q.get("question_type", "")
            image = q.get("image", "") or ""

            # A question uses passage_ref OR an inline passage, never both.
            ref = q.get("passage_ref")
            if ref and ref in declared:
                key, passage_text = declared[ref]
            elif ref:
                errors.append(f"{path.name} q{i + 1}: passage_ref '{ref}' is not in "
                              f"this pack's 'passages'.")
                key, passage_text = None, ""
            elif q.get("passage"):
                key = _passage_entry(passage_store, "", "", q["passage"], "")
                passage_text = str(q["passage"])
            else:
                key, passage_text = None, ""

            try:
                difficulty = int(q.get("difficulty"))
            except (TypeError, ValueError):
                # Keep it hashable and printable — a difficulty of [] or {} is a
                # thing to show the author, not a thing to crash on.
                difficulty = str(q.get("difficulty"))

            qtype_note = "" if not qtype or qtype in types else "not a type of this subtopic"

            segments = [s for s in (q.get("segments") or []) if isinstance(s, dict)]
            joined = "".join(s.get("text", "") for s in segments)
            options = [o for o in (q.get("options") or []) if isinstance(o, dict)]

            # Resolved once per option (a template_id, if any, only ever needs
            # resolving once) so the text-only toggle and the confusable-options
            # aid can both read the same `data` a rendered SVG came from, without
            # re-resolving a template a second and third time for each.
            stem_figure = _resolve_figure(q.get("figure"))
            stem_figure_data = stem_figure.get("data") if isinstance(stem_figure, dict) else None
            opt_list = []
            for j, o in enumerate(options):
                resolved = _resolve_figure(o.get("figure"))
                opt_list.append({
                    "label": OPTION_LABELS[j] if j < len(OPTION_LABELS) else "",
                    "text": o.get("text", ""), "correct": bool(o.get("correct")),
                    "svg": render_option_figure(resolved),
                    "figure_data": resolved.get("data") if isinstance(resolved, dict) else None,
                })

            questions.append({
                "pack": path.name,
                "section_code": code,
                "number": q.get("number", ""),
                "ref": q.get("ref", ""),
                "subtopic_display": canonical or written,
                "subtopic_note": "" if canonical or not written
                                 else "not in taxonomy.json for this section",
                "question_type": qtype,
                "question_type_name": types.get(qtype, ""),
                "question_type_note": qtype_note,
                "difficulty": difficulty,
                "difficulty_word": DIFFICULTY_WORDS.get(difficulty, ""),
                "difficulty_note": "" if difficulty in DIFFICULTY_WORDS
                                   else "difficulty must be an integer 1-5",
                "kind": kind,
                "stem": q.get("stem", ""),
                "instruction": block.get("instruction", ""),
                "worked_example": block.get("example", ""),
                "table": ({"headers": list(shared_table.get("headers") or []),
                           "rows": [r for r in (shared_table.get("rows") or [])
                                    if isinstance(r, list)]}
                          if shared_table else None),
                "explanation": q.get("explanation", ""),
                "image": image,
                "image_url": "/static/questions/" + image if image else "",
                "image_hint": _image_hint(image) if image else "",
                # Drawn here, in Python, by the same package the live site uses.
                # Resolved first in case the pack names a template rather than a
                # hand-built figure — see _resolve_figure.
                "figure_svg": render_figure(stem_figure),
                # The optional `alt` a stem figure may carry, for the text-only
                # toggle. Often blank — a stem figure has no field that is always
                # required to describe it the way an answer option's `text` is,
                # and the toggle exists partly to make that gap visible rather
                # than paper over it.
                "figure_alt": (stem_figure_data or {}).get("alt", "")
                              if isinstance(stem_figure_data, dict) else "",
                "unit": q.get("unit", "") or "",
                "marks": q.get("marks", 1) or 1,
                "line_ref_label": format_line_ref(q.get("line_ref", "")),
                "gap_number": q.get("gap_number"),
                # A cloze gap is a numbered hole in a passage, and the passage marks
                # it "(3)". Nothing requires the marker — _EXAMPLE.shared_passage.json
                # numbers gaps in a passage that has none — so this is a neutral note
                # about what the pupil will actually see, not a complaint.
                "gap_note": (f"the passage has no '({q.get('gap_number')})' marker, so the "
                             f"gap shows only as this question's number")
                            if kind == "cloze_gap" and key is not None
                            and f"({q.get('gap_number')})" not in passage_text else "",
                "answer": q.get("answer", ""),
                "tolerance": q.get("tolerance", 0) or 0,
                "accepted_alternatives": [str(a) for a in q.get("accepted_alternatives") or []],
                "model_answer": q.get("model_answer", ""),
                "rubric": q.get("rubric") if isinstance(q.get("rubric"), dict) else None,
                "allow_no_error": bool(q.get("allow_no_error")),
                "also_tests": [t for t in (q.get("also_tests") or []) if isinstance(t, dict)],
                "options": opt_list,
                "segments": [{"label": s.get("label", ""), "text": s.get("text", "")}
                             for s in segments],
                # The brackets of a "one word from each" question. No labels: a
                # paper does not letter the words inside a bracket, they are read
                # as part of the sentence.
                "option_groups": [
                    {"group": g.get("group", n + 1),
                     "options": [{"text": o.get("text", ""),
                                  "correct": bool(o.get("correct"))}
                                 for o in (g.get("options") or [])
                                 if isinstance(o, dict)]}
                    for n, g in enumerate(q.get("option_groups") or [])
                    if isinstance(g, dict)],
                # The check the split-a-sentence format invites you to fail: silently
                # correcting the sentence while cutting it up, so the pupil is asked
                # to find a mistake that is no longer there.
                "segments_note": ("segments do not rejoin to the stem exactly"
                                  if segments and joined != q.get("stem", "") else ""),
                "passage_key": key,
                "passage_ref": ref or "",
            })

    passages = [None] * len(passage_store)
    for entry in passage_store.values():
        passages[entry["index"]] = entry
    return {"questions": questions, "passages": passages, "names": names}, errors


def build_page(paths, stamp=None):
    data, errors = load_packs(paths)
    if errors and not data["questions"]:
        body = "".join(f'<div class="alert alert-danger">{esc(e)}</div>' for e in errors)
        return ERROR_PAGE.replace("%%BODY%%", body)

    # The batch overview's two Python-computed pieces. Difficulty spread and the
    # warnings roll-up are cheap enough, and read straight enough off fields
    # already on each question, to compute client-side in JS instead — see
    # collectWarnings() and renderOverview() below.
    key_pos = key_positions(data["questions"])
    counts = Counter(i for _, i in key_pos)
    data["key_spread"] = {
        "counts": {OPTION_LABELS[i]: counts[i] for i in range(len(OPTION_LABELS)) if counts.get(i)},
        "messages": [m for _, m in check_key_distribution(key_pos)],
    }
    data["targets"] = subtopic_targets()

    n = len(data["questions"])
    banner = (f"<strong>Preview</strong> — {esc(', '.join(data['names']))} &middot; "
              f"{n} question{'' if n == 1 else 's'} &middot; running only on your computer. "
              f"A look, not a check: validate_questions.py is still the gate.")
    if stamp:
        # Set only by --write-html. The live server never goes stale — it re-reads
        # the pack on every refresh — but a file written to disk outlives the
        # session and cannot re-render itself when the pack or the template moves.
        banner += (f' &middot; <span class="fw-bold">written {esc(stamp)} — a snapshot, '
                   f"not live. It will not pick up further edits to the pack, or a "
                   f"redesign of the real question page.</span>")
    for note in errors:
        banner += ' &middot; <span class="fw-bold">' + esc(note) + "</span>"
    pack = json.dumps(data).replace("</", "<\\/")
    # %%PACK%% last: a question's own text can then never be read as a placeholder.
    return (PAGE.replace("%%EVERY%%", str(NUMBER_EVERY))
                .replace("%%NOERRTEXT%%", NO_ERROR_TEXT)
                .replace("%%NOERR%%", NO_ERROR_LABEL)
                .replace("%%BANNER%%", banner)
                .replace("%%PACK%%", pack))


def make_handler(paths):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RevisorPlusPreview/1.0"

        def do_GET(self):
            route = unquote(urlparse(self.path).path)
            if route in ("/", "/index.html"):
                # Rebuilt from disk every request, so refresh is the edit loop.
                self._send(200, "text/html; charset=utf-8", build_page(paths).encode("utf-8"))
            elif route.startswith("/static/"):
                self._send_static(route[len("/static/"):])
            elif route == "/favicon.ico":
                self._send(204, "text/plain", b"")
            else:
                self._send(404, "text/plain; charset=utf-8", b"Not found")

        def _send_static(self, rel):
            # Never let a crafted path escape static/ — this server exists only to
            # hand out question figures.
            try:
                target = (STATIC_ROOT / rel).resolve()
                target.relative_to(STATIC_ROOT)
            except (ValueError, OSError):
                self._send(404, "text/plain; charset=utf-8", b"Not found")
                return
            if not target.is_file():
                self._send(404, "text/plain; charset=utf-8", b"Not found")
                return
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._send(200, ctype, target.read_bytes())

        def _send(self, code, ctype, body):
            try:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if body:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser navigated away mid-response; nothing to do

        def log_message(self, *args):
            pass  # an author doesn't need a request log scrolling past

    return Handler


def serve(paths, port, open_browser):
    httpd = last_err = None
    for candidate in range(port, port + PORT_TRIES):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate), make_handler(paths))
            port = candidate
            break
        except OSError as e:
            last_err = e
    if httpd is None:
        print(f"Could not open a port between {port} and {port + PORT_TRIES - 1}: {last_err}")
        return 1

    url = f"http://127.0.0.1:{port}"
    print(f"Preview running at {url}")
    print("Refresh the page to pick up questions added since it started.")
    print("Press Ctrl+C to stop it.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass  # headless or no default browser — the URL above still works
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview stopped.")
    finally:
        httpd.server_close()
    return 0


def main(argv):
    ap = argparse.ArgumentParser(
        description="Preview a RevisorPlus 11+ question pack the way a pupil sees it.")
    ap.add_argument("packs", nargs="*", help="one or more pack JSON files")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port to start from (default {DEFAULT_PORT}); steps up if taken")
    ap.add_argument("--no-browser", action="store_true",
                    help="don't open a browser window automatically")
    ap.add_argument("--write-html", nargs="?", const="", default=None, metavar="PATH",
                    help="write the rendered page to PATH (default: the first pack's "
                         "own name with a .preview.html suffix) and exit, instead of "
                         "serving it")
    args = ap.parse_args(argv[1:])

    if not args.packs:
        print(__doc__)
        return 0

    # Expand globs the shell may not have (Windows, quoted args) — same as the validator.
    paths = []
    for a in args.packs:
        matched = sorted(glob.glob(a))
        paths.extend(matched if matched else [a])

    missing = [p for p in paths if not Path(p).exists()]
    if len(missing) == len(paths):
        print("No pack files found: " + ", ".join(missing))
        return 2

    if args.write_html is not None:
        out = Path(args.write_html) if args.write_html else Path(paths[0]).with_suffix(".preview.html")
        html = build_page(paths, stamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        out.write_text(html, encoding="utf-8")
        print(f"Wrote {out} ({len(html)} bytes) from {', '.join(paths)}.")
        print("A snapshot, not live — re-run this to pick up any edits made since.")
        return 0

    return serve(paths, args.port, not args.no_browser)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
