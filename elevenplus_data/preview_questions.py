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
rules for typed answers (catalog/marking.py).
"""
import argparse
import glob
import json
import mimetypes
import sys
import textwrap
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = (REPO_ROOT / "static").resolve()
TAXONOMY = Path(__file__).resolve().parent / "taxonomy.json"

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
 <span class="ms-auto text-muted small">Preview — your machine only</span>
</div></nav>
<main class="container py-4" style="max-width:56rem"><div id="root"></div></main>
<script id="pack-data" type="application/json">%%PACK%%</script>
<script>
const PACK = JSON.parse(document.getElementById('pack-data').textContent);
const QS = PACK.questions, PASSAGES = PACK.passages;
const root = document.getElementById('root');
let idx = 0, submitted = false;
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
function isAnswered(i){
  const a = answers[i];
  if (a === null) return false;
  return typeof a === 'string' ? a.trim() !== '' : true;
}
function isRight(i){
  const q = QS[i], a = answers[i];
  if (!isAnswered(i)) return false;
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
  if (isChoice(q)){
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
  if (q.kind === 'error_span') return 'Which part of the sentence contains a mistake?';
  if (q.kind === 'select_word') return 'Click the correct word.';
  return q.stem;
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
function figureBlock(q, i){
  if (!q.image) return '';
  return '<img src="' + esc(q.image_url) + '" class="img-fluid border rounded mb-3" ' +
    'alt="Figure for this question" data-fig="' + i + '"><div data-figerr="' + i + '"></div>';
}
// A bad image path is one of the things a preview is FOR — say so loudly, and say
// where the file was actually looked for, because the contract ("filename only,
// committed under static/questions/") and the template ({% static image %}) do not
// obviously agree and an author cannot see either from here.
function wireFigures(){
  root.querySelectorAll('[data-fig]').forEach(img => {
    const i = Number(img.dataset.fig), q = QS[i];
    img.addEventListener('error', () => {
      img.remove();
      const slot = root.querySelector('[data-figerr="' + i + '"]');
      if (slot) slot.innerHTML = '<div class="alert alert-warning small">' +
        '<strong>Figure not found</strong> at <code>' + esc(q.image_url) + '</code>. ' +
        '<code>image</code> is resolved relative to <code>static/</code>, exactly as ' +
        'the live template does. ' + esc(q.image_hint) + '</div>';
    });
  });
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
  return '<div class="author-strip mt-3"><div>' + bits.join(' &middot; ') + '</div>' + extra + '</div>';
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
      '<button type="button" id="submit-open" class="btn btn-sm btn-brand">Submit</button>' +
    '</div></div>' +
   '<div class="d-flex flex-wrap gap-1 mb-3">' + nav + '</div>' +
   '<div class="card"><div class="card-body">' +
     passageBlock(PASSAGES[q.passage_key]) +
     '<h1 class="h5 mb-3">' + esc(heading(q)) + headingBadges(q) + '</h1>' +
     figureBlock(q, idx) +
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
      answers[idx] = isChoice(q) ? Number(e.target.value) : e.target.value;
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
        '<h2 class="h6 mb-3">' + esc(heading(q)) + headingBadges(q) + '</h2>' +
        figureBlock(q, i) + put + control(q, i, true) +
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
    '<div class="text-center my-4"><button type="button" id="again" class="btn btn-brand">' +
      'Start again</button></div>';

  wireFigures();
  root.querySelectorAll('.mark-q').forEach(b => b.addEventListener('click', () => {
    const i = Number(b.dataset.mark);
    marks[i] = !marks[i];
    b.classList.toggle('btn-danger', marks[i]);
    b.classList.toggle('btn-outline-danger', !marks[i]);
  }));
  document.getElementById('again').addEventListener('click', () => {
    idx = 0; submitted = false;
    answers = QS.map(() => null); marks = QS.map(() => false);
    render();
  });
}

function render(){ submitted ? renderReview() : renderQuestion(); }

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


def _image_hint(image):
    """Where the file actually is, for the figure-not-found alert.

    CLAUDE.md says "filename only" and "put the file in static/questions/", but
    templates/practice/question.html renders `{% static q.context_image %}`, which
    makes a bare filename resolve to /static/<filename>. Rather than guess which is
    right, the preview resolves it the way the template does and reports what it
    found on disk, so the author can see the mismatch instead of inferring it.
    """
    if (STATIC_ROOT / "questions" / image).is_file():
        return (f"The file does exist at static/questions/{image} — set "
                f'"image": "questions/{image}" so the live template finds it.')
    return (f"No file at static/{image} or static/questions/{image}. "
            f"CLAUDE.md asks for the figure to be committed under static/questions/.")


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

        for i, q in enumerate(raw.get("questions") or []):
            if not isinstance(q, dict):
                continue
            kind = q.get("kind") or "mcq"
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

            # NVR has no question types to pick from, so a slug on an NVR question
            # is not a mis-file, it is a field that should not be there at all.
            if code == "NVR":
                qtype_note = "NVR questions must not carry a question_type" if qtype else ""
            else:
                qtype_note = "" if not qtype or qtype in types else "not a type of this subtopic"

            segments = [s for s in (q.get("segments") or []) if isinstance(s, dict)]
            joined = "".join(s.get("text", "") for s in segments)
            options = [o for o in (q.get("options") or []) if isinstance(o, dict)]

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
                "explanation": q.get("explanation", ""),
                "image": image,
                "image_url": "/static/" + image if image else "",
                "image_hint": _image_hint(image) if image else "",
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
                "options": [{"label": OPTION_LABELS[j] if j < len(OPTION_LABELS) else "",
                             "text": o.get("text", ""), "correct": bool(o.get("correct"))}
                            for j, o in enumerate(options)],
                "segments": [{"label": s.get("label", ""), "text": s.get("text", "")}
                             for s in segments],
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


def build_page(paths):
    data, errors = load_packs(paths)
    if errors and not data["questions"]:
        body = "".join(f'<div class="alert alert-danger">{esc(e)}</div>' for e in errors)
        return ERROR_PAGE.replace("%%BODY%%", body)

    n = len(data["questions"])
    banner = (f"<strong>Preview</strong> — {esc(', '.join(data['names']))} &middot; "
              f"{n} question{'' if n == 1 else 's'} &middot; running only on your computer. "
              f"A look, not a check: validate_questions.py is still the gate.")
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

    return serve(paths, args.port, not args.no_browser)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
