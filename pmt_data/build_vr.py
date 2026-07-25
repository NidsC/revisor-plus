"""Build the Verbal Reasoning JSON + review markdown from transcribed PMT content.

11 passages: passages 1-2 are 4-option MCQs (Reading Comprehension); passages 3-11
are True/False/Can't-tell inference questions. Each question stores its shared passage.
"""
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)

TFC = ["True", "False", "Can't tell"]

# Passage texts (transcribed).
P = {
    "VRIC0005": (
        "The Stanford Prison Experiment was a famous psychological experiment carried out at Stanford "
        "University in 1971. The experiment lasted 6 days and was an investigation into the effects of "
        "perceived power in a controlled environment. The research was led by Professor Philip Zimbardo, "
        "who had a particular interest in how societal positions of power and validation of antisocial "
        "behaviour can lead \"ordinary\" individuals to commit acts they would have previously deemed immoral. "
        "Twenty four male college students, who had been shown to be psychologically healthy and stable in "
        "preliminary tests, were selected as subjects. The group were then randomly assigned the roles of "
        "\"prison guard\" or \"prisoner\" in a simulated prison within the university walls. There were four "
        "cells, to hold three prisoners each, a closet for solitary confinement, a corridor to serve as the "
        "prison yard and a larger room for the guards and warden. The results were notoriously shocking; "
        "prisoners internalised their roles whilst guards became increasingly cruel, leading to the "
        "experiment being curtailed at 6 days, rather than the projected 14."),
    "VRIC0008": (
        "Norway is one of the wealthiest countries in the world. In 2016 its GDP per capita was reported as "
        "$70,000 - the same as Luxembourg and Switzerland. In 1969, the Ekofisk field, a natural oil field in "
        "the Norwegian North Sea, was discovered. According to the Norwegian government, the oil and gas "
        "sector accounts for 23% of the country's value creation and it is the world's fifth largest oil "
        "exporter. The wealth gained from oil is reinvested more evenly than in other exporter countries, "
        "largely due to a buffer fund set up in 1995 to absorb excess cash flow generated from regional oil "
        "profits, rather than simply reinvesting the money into oil finding and production. The government "
        "declared that only 4% of this fund could be used for current projects, \"saving\" the money for "
        "future generations. The buffer fund currently contains over $890bn, equating to $170,000 per citizen."),
    "VRTF0002": (
        "Renal transplantation (kidney transplantation) is the treatment of choice in patients with end stage "
        "renal disease (ESRD) as an alternative to dialysis. Current guidelines recommend that all patients "
        "with stage 4 or 5 chronic kidney disease likely to require a renal replacement within six months are "
        "considered for transplantation. Kidneys are recovered from living or deceased donors. Deceased donors "
        "are classified as either donation after brain death (DBD) or donation after cardiac death (DCD). The "
        "most common placement of the kidney is in the right lower quadrant of the abdomen; this is preferred "
        "as the blood vessels here are closer to the surface of the skin. Medical complications are generally "
        "related to rejection, immunosuppression, and infection. Early surgical complications include bleeding "
        "and blood clots. Late complications include obstruction of the ureter. Urological complications are "
        "the most common surgical complications."),
    "VRTF0011": (
        "Artificial selection is the way in which desirable alleles are transferred to the offspring whereas "
        "undesirable alleles are removed. Domestication is the process by which a population of animals or "
        "plants is changed at the genetic level through a process of selection, in order to highlight traits "
        "that benefit humans. Groups such as farmers, animal welfare groups and veterinary doctors can debate "
        "the issues surrounding the research and assess any risks and benefits. Selective breeding may be "
        "advantageous to a farmer due to higher profit margins. One method of selective breeding cattle is "
        "artificial insemination (AI); the semen from a bull can be used to inseminate many cows. As yields "
        "increase, the farmers are able to charge the customer less and sustain their competitiveness."),
    "VRTF0023": (
        "Sri Lanka has hired two hangmen as it prepares to carry out four criminal executions - the first in "
        "43 years. This follows an announcement that four prisoners convicted of drug offences have been "
        "sentenced to the death penalty. The hanging will end a moratorium on capital punishment that has been "
        "in place since 1976. In Sri Lanka the crimes of rape, drug trafficking and murder are punishable by "
        "the death penalty. President Sirisena stated that across the country there were 200,000 drug addicts "
        "and 60% of prisoners were in jail due to drug related offences. The UK, France, Norway and the EU "
        "have condemned Sri Lanka's decision. Amnesty International were \"shocked\" and \"outraged\"."),
    "VRTF0019": (
        "Jeremy Hunt's campaign chief has suggested that Boris Johnson worsened matters for Nazanin "
        "Zaghari-Ratcliffe, the jailed British-Iranian mother, when he was foreign secretary. In 2017 Mr "
        "Johnson said that she was teaching journalism while she was in Iran. The Iranian regime cited his "
        "comments as evidence that she had engaged in propaganda, and it charged her with a second set of "
        "offences. She denies all the charges; she and her employer said she was visiting her family. Ms "
        "Zaghari-Ratcliffe, 40, was arrested in Tehran in April 2016 and sentenced to five years in jail for "
        "spying. Mr Johnson said he felt a \"deep sense of anguish\" but that responsibility lay solely with "
        "the Iranians. Ms Zaghari-Ratcliffe and her husband recently ended a 15-day hunger strike."),
    "VRTF0015": (
        "The Mount St. Helens eruption was caused by the Juan de Fuca Plate and the North American Plate which "
        "lie on a destructive plate boundary. The Juan de Fuca Plate (oceanic crust) moves eastward towards "
        "the North American Plate where it is forced downwards (a subduction zone). This movement generates "
        "friction which can manifest as earthquakes and, due to an increase in temperature, destroys the "
        "oceanic crust. Mount St. Helens had been inactive for over 120 years and therefore people did not "
        "expect it to erupt and had built their homes around it. An earthquake of magnitude 5.1 struck and "
        "caused a landslide. The floodwater carried sediment which blocked the port of Portland on the "
        "Columbia River. Every form of life was destroyed. Within three days, the cloud of fine ash reached "
        "the east coast of the USA."),
    "VRTF0013": (
        "The word osmosis is derived from the Greek word osmos, meaning \"to push\". For osmosis, three "
        "conditions are required: a dilute solution, a concentrated solution and a semi-permeable membrane "
        "which separates the two solutions. This membrane allows some molecules to pass through. In most "
        "animals which live in the sea, the concentration of dissolved chemicals in their cells is the same as "
        "that of the sea water. The concentration of chemicals in the body of fresh-water animals is much "
        "higher than in fresh water and therefore water is constantly entering their bodies through osmosis. "
        "The effect of osmosis can be seen during the action of anti-diuretic hormone (ADH) on kidney tubules. "
        "When more ADH is secreted, the cells of the kidney tubules become more permeable to water, so more "
        "water is re-absorbed into the bloodstream by osmosis."),
    "VRTF0006": (
        "The programme on ITV entitled \"Being Paul Gascoigne\" gave real footage into the life of the famous "
        "footballer and his journey through alcohol addiction. It was interesting to see the various schemes "
        "which Gascoigne used to combat his alcoholism. Gascoigne also underwent detoxification. Detox entails "
        "taking a short course of a medicine to aid the prevention of withdrawal symptoms when you stop "
        "drinking alcohol. The most commonly used medicine for detox is chlordiazepoxide. This facility is "
        "available from the GP. Patient.co.uk offers healthcare advice and is set up by two general "
        "practitioners - Dr Tim Kenny and Dr Beverley Kenny. However, having tried this treatment Gascoigne "
        "had a serious reaction to the drugs and was later admitted on life support."),
    "VRTF0026": (
        "In 1985 a study was performed to assess all people born in the year 1970 and screen them for anorexia "
        "nervosa. 23 girls (1 dropped out) and 2 boys fulfilled the diagnostic criteria and they were mixed "
        "with another screening population of 26 girls and 1 boy born between 1971-4. A control group was "
        "selected from the same school classes, matched for multiple factors including age and sex, with no "
        "history of an eating disorder. Global assessment of function (GAF) was assessed via a scale where a "
        "score of <60 was indicative of poor psychosocial functioning. Full symptomatic recovery was assessed "
        "as being symptom free for more than 6 months. This study is the first prospective, longitudinal study "
        "of adolescent onset anorexia based in the community, with no conflicts of interest. It showed a more "
        "positive outlook (12% chronic cases as opposed to 20%) and no deaths. However, the sample size is "
        "small and participants were only assessed on 4 separate occasions."),
    "VRTF0017": (
        "An oligopoly describes a market in which there are a small number of dominant firms. Concentration "
        "ratios measure the market share of the biggest firms in the market. An oligopolistic firm affects its "
        "rivals through its price and output decision, but its own profit can also be affected by how the "
        "rivals react. Competitive oligopolies exist when rival firms are interdependent, in the sense that "
        "they must take account of the reactions of one another when forming a market strategy, but "
        "independent in the sense that they decide market strategies without cooperation or collusion. A "
        "collusive oligopoly is one in which firms cooperate. The kinked demand curve can be used to "
        "illustrate how a competitive oligopolist may be affected by a rival's reaction. In imperfectly "
        "competitive markets, firms do not have full information on demand and revenue curves."),
}

# MCQ passages (1-2): code, [(stem, [(opt, correct)...])...]
MCQ = [
    ("VRIC0005", "Reading Comprehension", [
        ("Which statement most accurately describes the layout of the simulated \"prison\" in the Stanford Prison Experiment?",
         [("Four cells holding three \"prisoners\", a corridor for solitary confinement and access to a small outdoor yard.", 0),
          ("Three cells holding four \"prisoners\", a closet for solitary confinement and a larger room as a \"prison yard\".", 0),
          ("Four cells holding three \"prisoners\", a closet for solitary confinement and a corridor as a \"prison yard\".", 1),
          ("Three cells holding four \"prisoners\", a dark room for solitary confinement and a small corridor as a \"prison yard\".", 0)]),
        ("Which statement best summarises the objectives of the Stanford Prison Experiment?",
         [("To investigate how best to rehabilitate repeat offenders in the US prison system.", 0),
          ("To investigate the origins of cruelty amongst prison guards.", 0),
          ("To investigate the psychological effects of imprisonment.", 0),
          ("To investigate the psychological effects of perceived power.", 1)]),
        ("Which of the following does not describe the participants of the Stanford Prison Experiment?",
         [("College students", 0), ("Male", 0), ("Aged 21 to 30", 1), ("Psychologically healthy and stable", 0)]),
        ("Which of the following statements best describes the duration of the experiment?",
         [("6 days in total, as planned", 0), ("6 days instead of the original 14 days", 1),
          ("7 days instead of the original 10 days", 0), ("10 days in total, as planned", 0)]),
    ]),
    ("VRIC0008", "Reading Comprehension", [
        ("Which of the following statements describes the buffer fund set up by the Norwegian government?",
         [("Set up in 1995, it absorbs excess cash flow generated by regional oil companies for reinvestment into Norway's future generations", 1),
          ("Set up in 1969, it ensures that profits generated by regional oil companies are reinvested into the finding and production of oil", 0),
          ("Set up in 1995, it ensures that 50% of profits generated by regional oil companies is reinvested in public projects", 0),
          ("Set up in 1985, it absorbs 4% of excess cash flow generated by regional oil companies to fund future generations' pensions", 0)]),
        ("What is the name of the natural resource discovered in Norwegian waters in 1969?",
         [("Scandinavian Oil Reserve", 0), ("Norwegian North Sea Oil Field", 0),
          ("Ekofisk Oil Field", 1), ("Norwegian Oil Reserve", 0)]),
        ("What is the current estimated value of the Norwegian buffer fund?",
         [("Nine hundred and ninety million dollars", 0), ("Eight hundred and ninety billion Norwegian krones", 0),
          ("Nine hundred and eighty billion Norwegian krones", 0), ("Eight hundred and ninety billion dollars", 1)]),
        ("According to the Norwegian government, the oil industry accounts for what percentage of Norway's value creation?",
         [("2.3%", 0), ("32%", 0), ("23%", 1), ("3.2%", 0)]),
    ]),
]

# True/False/Can't-tell passages (3-11): code, [(statement, correct_index_into_TFC)...]
TFQ = [
    ("VRTF0002", [
        ("Living donors may be divided into DBD and DCD.", 1),
        ("The most common placement of the kidney is in the right lower quadrant as the vessels are deep to the surface.", 1),
        ("Urological complications occur early post-transplantation.", 2),
        ("Patients with Stage 5 chronic kidney disease are not eligible for renal transplantation.", 1)]),
    ("VRTF0011", [
        ("Domestication is the process by which a population of animals or plants is changed at the environmental level.", 1),
        ("Veterinary doctors are not able to discuss the risk and benefits of studies and experiments.", 1),
        ("Artificial insemination is a form of selective breeding.", 0),
        ("All farmers charge their customers less as the yield of meat products increases.", 2)]),
    ("VRTF0023", [
        ("Sri Lanka repealed the death penalty in 1976.", 1),
        ("Only people with drug convictions are going to be executed.", 2),
        ("60% of people in Sri Lankan jails could be eligible for the death penalty.", 2),
        ("The passage reveals that the United States has condemned the move.", 1)]),
    ("VRTF0019", [
        ("Nazanin Zaghari-Ratcliffe was training journalists in Iran.", 2),
        ("Boris Johnson is accused of having contributed to the evidence against Nazanin.", 0),
        ("Boris Johnson has apologised for his comments in parliament regarding the case.", 2),
        ("Nazanin Zaghari-Ratcliffe recently spent more than two weeks on hunger strike.", 0)]),
    ("VRTF0015", [
        ("The oceanic crust is destroyed due to friction causing an increase in temperature.", 0),
        ("Everyone expected Mount St Helens to erupt.", 1),
        ("Some humans survived the earthquake.", 2),
        ("The port of Portland was blocked due to the earthquake.", 0)]),
    ("VRTF0013", [
        ("The semi-permeable membrane allows passage of molecules.", 0),
        ("Water loss may occur during defecation.", 2),
        ("ADH acts on kidney tubules only.", 2),
        ("Concentration of chemicals in fresh water is lower than in the body of most animals.", 0)]),
    ("VRTF0006", [
        ("Patient.co.uk is set up by general practitioners.", 0),
        ("Everyone who has an alcohol addiction undergoes detoxification.", 2),
        ("Celebrities and public figures may be impacted by alcoholism.", 0),
        ("Schemes to combat alcoholism may incur costs.", 0)]),
    ("VRTF0026", [
        ("Global Assessment of Function is a reliable method of assessing psychosocial function.", 2),
        ("This study's validity can be questioned as there were conflicts of interest.", 1),
        ("Members of society were selected for a control group, one factor that was matched was their hair colour.", 2),
        ("To be referred to as having a full symptomatic recovery the participant must have been symptom free for more than 3 months.", 1)]),
    ("VRTF0017", [
        ("Competitive oligopolies must take into account actions of rivals.", 0),
        ("Firms may affect profit margins of other firms.", 0),
        ("In imperfectly competitive markets, firms have full knowledge on the demand and revenue curves.", 1),
        ("Competitive oligopoly is defined as a market with more than 4 dominant firms.", 2)]),
]


def build():
    questions = []
    counter = 0
    order = ["VRIC0005", "VRIC0008", "VRTF0002", "VRTF0011", "VRTF0023", "VRTF0019",
             "VRTF0015", "VRTF0013", "VRTF0006", "VRTF0026", "VRTF0017"]
    mcq_map = {code: (sub, qs) for code, sub, qs in MCQ}
    tfq_map = {code: qs for code, qs in TFQ}

    for code in order:
        if code in mcq_map:
            sub, qs = mcq_map[code]
            for stem, opts in qs:
                counter += 1
                questions.append({
                    "number": str(counter), "ref": f"{code} Q{counter}", "subtopic": sub,
                    "kind": "mcq", "passage": P[code], "stem": stem,
                    "options": [{"text": t, "correct": bool(c)} for t, c in opts]})
        else:
            for statement, correct in tfq_map[code]:
                counter += 1
                questions.append({
                    "number": str(counter), "ref": f"{code} Q{counter}",
                    "subtopic": "Inference (True/False/Can't Tell)", "kind": "tf",
                    "passage": P[code], "stem": statement,
                    "options": [{"text": t, "correct": (i == correct)} for i, t in enumerate(TFC)]})

    data = {"section": {"code": "VR", "name": "Verbal Reasoning"}, "questions": questions}
    with open(os.path.join(HERE, "verbal_reasoning.json"), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    from collections import Counter
    by_sub = Counter(q["subtopic"] for q in questions)
    lines = ["# Verbal Reasoning - Imported Questions (Phase 4)\n",
             "Source: PMT Verbal Reasoning Question Pack 1 (placeholder demo content).\n",
             f"**Practice items:** {len(questions)} (across 11 passages)\n",
             "**By subtopic:** " + ", ".join(f"{k}: {v}" for k, v in sorted(by_sub.items())) + "\n"]
    last = None
    for q in questions:
        code = q["ref"].split(" ")[0]
        if code != last:
            lines.append(f"\n### Passage {code}\n> {q['passage'][:150]}...\n")
            last = code
        lines.append(f"\n**{q['number']}.** {q['stem']}\n")
        for opt in q["options"]:
            mark = "  ✅" if opt["correct"] else ""
            lines.append(f"- {opt['text']}{mark}")
        lines.append("")
    with open(os.path.join(ROOT, "imported_questions_review", "verbal_reasoning.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"Built {len(questions)} VR items across 11 passages.")
    print("By subtopic:", dict(by_sub))


if __name__ == "__main__":
    build()
