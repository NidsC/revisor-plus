"""
Exercises elevenplus_data/preview_questions.py's pure functions directly — no HTTP
server, no browser — plus its --write-html flag end to end via subprocess.

Run:  python3 test_preview_questions.py

Until now nothing did this. CI only ran `ast.parse` over the file, which proves it
has no syntax error and nothing else — a change to load_packs(), build_page() or the
marking JS could silently break the tool an author's whole review loop depends on
and nothing would say so.

Stdlib only, matching preview_questions.py's own promise: a contributor runs this
with nothing but Python 3, no Django, no pip install.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "elevenplus_data"))

import preview_questions as pv  # noqa: E402
from passage_lines import passage_lines as reference_passage_lines  # noqa: E402

fails = []


def ck(label, cond, extra=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(label)


EXAMPLES = sorted(glob.glob(os.path.join(REPO, "elevenplus_data", "_EXAMPLE.*.json")))
CONTRIB = sorted(glob.glob(os.path.join(REPO, "elevenplus_data", "contrib_*.json")))
ALL_PACKS = EXAMPLES + CONTRIB

print("== every example and contributor pack loads without error ==")
data, errors = pv.load_packs(ALL_PACKS)
ck("no load errors", errors == [], errors)
ck("at least one question was loaded", len(data["questions"]) > 0, len(data["questions"]))
ck("every one of the eight kinds appears across the examples",
   {"mcq", "numeric", "short_text", "error_span", "select_word", "cloze_gap",
    "grouped_options", "extended_text"} <= {q["kind"] for q in data["questions"]},
   sorted({q["kind"] for q in data["questions"]}))

print("\n== the page builds and names every pack it was given ==")
html = pv.build_page(ALL_PACKS)
ck("finds the embedded pack-data script tag",
   '<script id="pack-data" type="application/json">' in html)
ck("the banner names every pack that was loaded",
   all(os.path.basename(p) in html for p in ALL_PACKS))

print("\n== a stamp, passed only by --write-html, shows up when given and not otherwise ==")
stamped = pv.build_page([EXAMPLES[0]], stamp="2026-01-01 00:00")
ck("the stamp text appears", "2026-01-01 00:00" in stamped)
unstamped = pv.build_page([EXAMPLES[0]])
ck("no 'written' stamp when none is given", "written 20" not in unstamped)

print("\n== a stem containing </script> cannot break out of the embedded JSON ==")
# The one thing standing between an author's own text and an XSS in a tool that is
# never supposed to need one: json.dumps(...).replace("</", "<\\/") in build_page().
injection_pack = {
    "section": {"code": "MAT", "name": "Maths", "source": "CONTRIB-TEST-01",
                "is_placeholder": True},
    "questions": [{
        "subtopic": "Number & Place Value", "question_type": "place-value",
        "stem": "Close the tag: </script><script>alert(1)</script> — what is 2 + 2?",
        "kind": "mcq", "difficulty": 1,
        "options": [{"text": "4", "correct": True}, {"text": "5"}],
    }],
}
with tempfile.TemporaryDirectory() as tmp:
    injected = os.path.join(tmp, "contrib_inject_mat_01.json")
    with open(injected, "w", encoding="utf-8") as f:
        json.dump(injection_pack, f)
    inj_html = pv.build_page([injected])
    after_open = inj_html.split('id="pack-data" type="application/json">', 1)[1]
    json_blob = after_open.split("</script>", 1)[0]
    ck("the injected </script> is escaped inside the JSON blob",
       "<\\/script>" in json_blob)
    ck("no live </script><script> boundary reaches the page",
       "</script><script>" not in json_blob)

print("\n== NVR figures actually draw <svg>, not a placeholder ==")
nvr_data, nvr_errors = pv.load_packs(
    [os.path.join(REPO, "elevenplus_data", "_EXAMPLE.nvr_figures.json")])
ck("no load errors", nvr_errors == [])
with_figures = [q for q in nvr_data["questions"] if q["figure_svg"]]
ck("at least one question has a rendered figure", len(with_figures) > 0)
ck("every rendered figure is real SVG markup",
   # A wide stem figure (>292px) is legitimately wrapped in a scrollable div by
   # render_figure() itself — the .figure-scroll CSS this page defines exists for
   # exactly that case — so this checks for an <svg> inside, not a bare prefix.
   all("<svg" in q["figure_svg"] for q in with_figures))

print("\n== a figure's alt text and each option's resolved figure data reach the page ==")
# What the text-only toggle and the confusable-options aid each read client-side;
# this checks the Python half that feeds them, not the JS rendering itself.
nvr_q = nvr_data["questions"][0]
ck("the stem figure's alt text is captured for the text-only toggle",
   bool(nvr_q["figure_alt"]))
ck("every option with a drawn figure also carries its resolved data",
   all(bool(o["figure_data"]) for o in nvr_q["options"] if o["svg"]))
opts = nvr_q["options"]
ref_opt = next((o for o in opts if o["correct"]), None)
other = next((o for o in opts if o is not ref_opt and o.get("figure_data")
              and o["figure_data"].get("cell", {}).get("rot")
              != (ref_opt or {}).get("figure_data", {}).get("cell", {}).get("rot")), None)
ck("a differing rotation is visible in the raw figure_data (what the JS diff reads)",
   ref_opt is not None and other is not None,
   "fixture question shape changed — pick a different question to diff")

print("\n== the batch overview's key-position spread reuses validate_questions.py's own check ==")
# Not re-derived here — build_page() imports key_positions/check_key_distribution
# from validate_questions.py, so this tests the wiring, not the algorithm itself
# (test_validator.py already exercises that directly).
def _mcq(ref, correct_index, n=4):
    return {"subtopic": "Number & Place Value", "question_type": "place-value",
            "stem": ref, "kind": "mcq", "difficulty": 1, "ref": ref,
            "options": [{"text": f"{ref}-{i}", "correct": i == correct_index} for i in range(n)]}


all_a_pack = {"section": {"code": "MAT", "name": "Maths", "source": "CONTRIB-TEST-KEYS",
                          "is_placeholder": True},
              "questions": [_mcq(f"Q{i}", 0) for i in range(25)]}
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "contrib_test_mat_01.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_a_pack, f)
    html = pv.build_page([path])
    blob = json.loads(html.split('id="pack-data" type="application/json">', 1)[1]
                           .split("</script>", 1)[0])
    ck("all 25 keys land on A", blob["key_spread"]["counts"] == {"A": 25},
       blob["key_spread"]["counts"])
    ck("both the run and skew warnings fire",
       len(blob["key_spread"]["messages"]) == 2, blob["key_spread"]["messages"])

print("\n== the batch overview's subtopic targets come from taxonomy.json, MAT/NVR only ==")
targets = pv.subtopic_targets()
ck("MAT has a target for every subtopic it declares",
   "Number & Place Value" in targets.get("MAT", {}))
ck("ENG carries no per-subtopic targets yet", not targets.get("ENG"))
ck("VR carries no per-subtopic targets yet", not targets.get("VR"))
ck("NVR has per-subtopic targets (the 2026-08-27 rebuild added them)", bool(targets.get("NVR")))

print("\n== the JS side ships the batch-overview and accessibility features (presence check) ==")
# These render client-side, so a stdlib test can't execute them — this only
# guards against the feature being deleted or renamed by accident. The Python
# data each one depends on is exercised for real above.
any_html = pv.build_page([EXAMPLES[0]])
for marker in ("renderOverview", "collectWarnings", "text-only-toggle",
               "confusableOptionsBlock", "statsPlaceholder", "PLACEHOLDER"):
    ck(f"{marker!r} shipped in the page", marker in any_html)

print("\n== a missing figure is reported against where the live template looks ==")
ck("image_hint names static/questions/, matching the live template",
   "static/questions/" in pv._image_hint("nonexistent_figure_for_this_test.png"))

print("\n== passage line-numbering matches elevenplus_data/passage_lines.py ==")
# preview_questions.py keeps its own copy of this algorithm (its header explains
# why) rather than importing the module the validator and the live renderer share.
# If the two ever drift, an author's line_ref would be right here and wrong on the
# live site, or the reverse — the exact bug class PASSAGE_LINE_WIDTH exists to
# prevent, reintroduced through the one place that still duplicates it.
sample_text = ("The wind picked up along the coast that afternoon, and the fishing "
               "boats turned for harbour early.\n\nBy evening the storm had passed, "
               "and the sky over the bay was the colour of a bruise.")
ck("identical output to elevenplus_data/passage_lines.py",
   pv.passage_lines(sample_text) == reference_passage_lines(sample_text))

print("\n== bad input degrades to a banner, never a crash ==")
data, errors = pv.load_packs(["/no/such/file.json"])
ck("a missing file is reported", any("not found" in e for e in errors))
ck("no questions come back", data["questions"] == [])

with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    f.write("{ not valid json")
    broken_path = f.name
try:
    page = pv.build_page([broken_path])
    ck("the error page names the problem", "not valid JSON" in page)
    ck("it's the error page, not an attempt at the pack page",
       "pack-data" not in page)
finally:
    os.unlink(broken_path)

print("\n== --write-html writes the page to disk and exits, without serving ==")
PREVIEW_SCRIPT = os.path.join(REPO, "elevenplus_data", "preview_questions.py")
with tempfile.TemporaryDirectory() as tmp:
    out = os.path.join(tmp, "out.html")
    result = subprocess.run(
        [sys.executable, PREVIEW_SCRIPT, EXAMPLES[0], "--write-html", out],
        capture_output=True, text=True, timeout=15)
    ck("exits 0", result.returncode == 0, result.stderr)
    ck("writes the file", os.path.isfile(out))
    if os.path.isfile(out):
        written = open(out, encoding="utf-8").read()
        ck("the written file is a real preview page",
           '<script id="pack-data" type="application/json">' in written)
        ck("it is stamped with today's date", "written 20" in written)

print("\n== --write-html with no PATH derives <pack>.preview.html next to the pack ==")
with tempfile.TemporaryDirectory() as tmp:
    pack_copy = os.path.join(tmp, "contrib_test_mat_01.json")
    with open(EXAMPLES[0], encoding="utf-8") as src, open(pack_copy, "w", encoding="utf-8") as dst:
        dst.write(src.read())
    result = subprocess.run(
        [sys.executable, PREVIEW_SCRIPT, pack_copy, "--write-html"],
        capture_output=True, text=True, timeout=15)
    expected = os.path.join(tmp, "contrib_test_mat_01.preview.html")
    ck("exits 0", result.returncode == 0, result.stderr)
    ck("derives the default filename next to the pack", os.path.isfile(expected))

if fails:
    print("\nRESULT: FAILURES:", fails)
    raise SystemExit(1)
print("\nRESULT: all checks passed.")
