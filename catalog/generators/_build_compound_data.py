"""BUILD-TIME ONLY. Regenerates compound_data.py. Never imported at runtime.

Reads /usr/share/dict/web2 (macOS Webster's 2nd), which does NOT exist on the
Render deploy — that is exactly why its output is frozen into compound_data.py
and committed. `generate_bank` runs in build.sh on the server, so nothing the
generator touches may read a system wordlist.

Run:  python3 catalog/generators/_build_compound_data.py
"""
import os, sys

WEB2 = "/usr/share/dict/web2"

HEADS = """rain foot day night book sun moon snow water wind fire sea air hand head
eye door house home school bed tea road farm horse bird fish star sand stone grass
hair gold summer winter spring hill wood milk key life light river forest garden
black blue green white play news post shop table finger arm leg neck heart nose
tooth ear bone skin sheep cow pig dog cat mouse apple corn bread butter salt egg
cake candle clock lamp cup dish pan pot box bag basket bell drum flag rope chain
nail hammer saw brush comb""".split()

TAILS = """bow coat fall drop path ball print step light break dream time mare gown
case mark shelf worm flower rise shine set fly house boat room yard way side line
man land work storm water bell board box cake pot hook stick wheel cloth cup field
gate wood stone bird fish keeper maker book paper card shop bag net hole plate top
back door stairs berry nut seed leaf branch tree horn tail wing foot head eye mouth
ache bite burn cut skin bone milk cream corn meal loaf crust knife spoon fork dish
pan lid""".split()

# Adjudicated Year 5/6-familiar compounds. Selected FROM the web2 candidate set,
# not typed from scratch — see the PR description for the review that produced it.
KEYS = {
"air":["drop","field","man","way"],
"arm":["hole"],
"basket":["ball"],
"bed":["room","side","time"],
"bird":["house","seed"],
"black":["berry","bird","board"],
"blue":["bell","berry","bird","print"],
"book":["case","keeper","mark","shelf","shop","worm"],
"bread":["board","box"],
"butter":["cup","fly","milk"],
"candle":["light","stick"],
"cat":["fish"],
"clock":["maker","work"],
"corn":["field","flower"],
"cow":["bell"],
"cup":["board","cake"],
"day":["break","dream","light","time"],
"dish":["cloth"],
"dog":["house"],
"door":["bell","keeper","man","step","way"],
"drum":["stick"],
"ear":["ache","hole","mark"],
"egg":["cup"],
"eye":["ball","drop","hole","lid"],
"farm":["house","yard"],
"finger":["print"],
"fire":["ball","boat","break","fly","light","man","side","wood","work"],
"fish":["bone","hook"],
"flag":["stone"],
"foot":["ball","fall","light","man","path","print","step","work"],
"gold":["fish"],
"grass":["land"],
"green":["house"],
"hair":["cut","line"],
"hammer":["head"],
"hand":["bag","ball","book","print"],
"head":["ache","board","light","line","set","way"],
"heart":["ache","break","burn"],
"hill":["side","top"],
"home":["land","maker","work"],
"horse":["back","fly","man"],
"house":["boat","break","fly","keeper","work"],
"key":["board","hole","stone"],
"lamp":["light"],
"life":["boat","line","time"],
"light":["house"],
"milk":["man"],
"moon":["light","rise","shine"],
"mouse":["hole"],
"neck":["line"],
"news":["paper","room"],
"night":["fall","gown","mare","time"],
"pan":["cake"],
"pig":["tail"],
"play":["house","room","time"],
"post":["box","man","mark"],
"pot":["hole"],
"rain":["bow","coat","drop","fall","storm"],
"river":["side"],
"road":["side","way"],
"sand":["bag","box","man","paper","stone","storm"],
"school":["bag","book","house","room","work","yard"],
"sea":["man","side"],
"sheep":["skin"],
"shop":["keeper"],
"snow":["ball","drop","fall","storm"],
"spring":["board","time"],
"star":["fish","light"],
"summer":["time"],
"sun":["burn","flower","light","rise","set","shine"],
"table":["cloth","spoon"],
"tea":["cup","house","pot","room","spoon","time"],
"tooth":["ache"],
"water":["fall","mark","side","way"],
"wind":["break","fall","storm"],
"winter":["time"],
"wood":["land","work"],
}

# Real compounds judged too obscure/adult/regional for Year 5-6, held back from
# KEYS pending tutor review. They still count as ATTACHING (safety), so they are
# never offered as distractors either.
MARGINAL = {
"basket":["work"],
"bed":["pan"],
"bell":["flower"],
"black":["ball","head"],
"blue":["fish"],
"bone":["head"],
"book":["maker","plate"],
"box":["wood"],
"bread":["maker"],
"brush":["wood","work"],
"butter":["ball","nut"],
"candle":["maker"],
"dish":["pan","water"],
"dog":["fish","wood"],
"egg":["head"],
"fire":["bird","house"],
"fish":["tail"],
"green":["horn","keeper","room","wood"],
"hand":["set","work"],
"head":["land","room","stone"],
"heart":["land","wood"],
"house":["coat","top"],
"moon":["stone"],
"news":["man","print"],
"pig":["skin"],
"play":["back","book","maker"],
"road":["house"],
"salt":["pan"],
"saw":["fish"],
"sea":["board"],
"stone":["work"],
"sun":["fish","room"],
"table":["land"],
"tea":["cake","shop"],
"water":["line","man","work"],
"white":["fish","head","tail"],
"wind":["bag"],
"wood":["cut","man","worm"],
}

# Real words that are NOT compounds of the head and tail they happen to spell.
# `starboard` is Old English steorbord ("steering side"), not star + board, so a
# question built on it would carry a false explanation -- the same defect class as
# `panache` (pan + ache). `horsetail` and `fisheye` are excluded for a different
# reason: both invite a pupil to reason correctly from the parts and land on the
# wrong sense (the plant, the lens). `footmark` is a third case -- a genuine
# compound, but one an ordinary synonym has displaced: `footprint` is the word a
# child reaches for, so the item tests vocabulary trivia rather than compounding.
# All of these stay in ATTACHING -- they must never be offered as distractors
# either, since they ARE words -- but they can never become keys.
STRUCK = {"fish":["eye"],"foot":["mark"],"horse":["tail"],"star":["board"]}

# Compounds web2 does NOT list closed, because they are usually written open or
# hyphenated. THIS IS THE SAFETY-CRITICAL LIST: without it these become
# distractors and the question has two right answers. `nightlight` is the one
# that shipped — it appeared twice in a 15-question sample of the old generator.
OPEN_COMPOUNDS = {
"night":["light"], "book":["light"], "snow":["man","board"],
"white":["board"], "table":["top"], "rain":["water"], "salt":["water"],
"fish":["cake"], "bread":["stick"], "air":["line","bag"], "post":["card"],
"summer":["house"], "apple":["tree"], "sun":["cream"], "tea":["bag"],
}


def main():
    if not os.path.exists(WEB2):
        sys.exit(f"{WEB2} not found — this script only runs on macOS.")
    words = {l.strip().lower() for l in open(WEB2)}
    H, T = sorted(set(HEADS)), sorted(set(TAILS))

    attaching = {h: set() for h in H}
    for h in H:
        for t in T:
            if h != t and h + t in words:
                attaching[h].add(t)
    for src in (KEYS, MARGINAL, STRUCK, OPEN_COMPOUNDS):
        for h, ts in src.items():
            attaching[h].update(ts)

    for h, ts in KEYS.items():
        unknown = set(ts) - attaching[h]
        assert not unknown, f"{h}: keys not in attaching set: {unknown}"
    for h, ts in STRUCK.items():
        assert not (set(ts) & set(KEYS.get(h, []))), f"{h}: struck pair is also a key"
        assert not (set(ts) & set(MARGINAL.get(h, []))), f"{h}: struck pair still marginal"

    def fmt(d):
        return "\n".join(f'    {k!r}: {sorted(v)},'
                         for k, v in sorted(d.items()) if v)

    out = f'''"""Compound-word data. GENERATED by _build_compound_data.py — do not hand-edit.

`ATTACHING` is the permissive safety relation: every (head, tail) pair that
forms a word, from web2 plus the open/hyphenated compounds web2 omits. It exists
to REJECT distractors, so over-inclusion is free and omission ships a question
with two right answers. `KEYS` is the narrow, adjudicated subset fair to ask a
Year 5/6 pupil. The two are deliberately different sizes.
"""

HEADS = {sorted(set(HEADS))!r}

TAILS = {sorted(set(TAILS))!r}

# Adjudicated as fair to ask. {sum(len(v) for v in KEYS.values())} pairs.
KEYS = {{
{fmt(KEYS)}
}}

# Real, but held back from KEYS as too obscure/adult/regional. Still ATTACHING.
MARGINAL = {{
{fmt(MARGINAL)}
}}

# Real words that are not compounds of these parts, or whose parts mislead.
# Never keys, never promotable. Still ATTACHING, so never distractors either.
STRUCK = {{
{fmt(STRUCK)}
}}

# Permissive safety relation — governs distractor rejection only.
ATTACHING = {{
{fmt(attaching)}
}}
'''
    path = os.path.join(os.path.dirname(__file__), "compound_data.py")
    with open(path, "w") as f:
        f.write(out)
    n_at = sum(len(v) for v in attaching.values())
    print(f"wrote {path}")
    print(f"  heads={len(H)} tails={len(T)}  KEYS={sum(len(v) for v in KEYS.values())} "
          f"MARGINAL={sum(len(v) for v in MARGINAL.values())} ATTACHING={n_at}")


if __name__ == "__main__":
    main()
