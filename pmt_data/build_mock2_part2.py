"""Build Mock 2 QR + SJT JSON (source PMT-M2) + review markdown (part 2)."""
import json
import os
from collections import Counter

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
SOURCE = "PMT-M2"

APP = ["A very appropriate thing to do.", "Appropriate, but not ideal.",
       "Inappropriate, but not awful.", "A very inappropriate thing to do."]
IMP = ["Very important.", "Important.", "Of minor importance.", "Not important at all."]

# ---------------- Quantitative Reasoning ----------------
QR_TABLES = {
    "QR0031": "A bank charges interest depending on loan type and payback time. Rates (5yr / 10yr / 15yr): "
              "Student Loan 1.5%/2%/4%; Business Loan 5.5%/6.5%/8%; Mortgage 4%/4.5%/5.0%. An interest rate of 100% "
              "means paying back double the loan. First-time homeowners buying under £300,000 get a fixed 0.5% for the "
              "first three years, after which the normal rate resumes.",
    "QR0009": "Francine buys second-hand/vintage clothing and sells it on. The selling website takes a 15% fee based on "
              "the item selling price (not including packing and postage). Estimated shipping costs per item: "
              "Small accessories £1.50; Small clothing items £3.00; Large clothing items £4.00; Large accessories £5.00.",
    "QR0032": "The library (open 8am-5pm) charges overdue fines: Paperbacks £0.50 per day after the due date; "
              "Hardbacks £1.00 per day; Books of the week £0.75 every 1 hour after the due hour, excluding library "
              "closing hours.",
    "QR0035": "Holiday prices (€1 = £0.90): Ice Cream €1.80; Sun Cream €6.50; After Sun Lotion €4.00; 4-pack of Beer "
              "€6.00; Sun Bed €5.00.",
}
# (ref, subtopic, stem, image_or_None, [(opt,correct)...], table_ref_or_None)
QR = [
    ("QR0020-1", "Data Interpretation", "If obstetrics and gynaecology had not been an option, 32 students would have selected general surgery, 11 psychiatry, 29 cardiology, 47 paediatrics and 6 geriatrics. What percentage increase in popularity would this mean for cardiology?", "questions/m2_qr_ds1_specialities.png",
     [("2.7%", 0), ("3.9%", 0), ("4.2%", 0), ("5.6%", 1), ("6.4%", 0)], None),
    ("QR0020-2", "Data Interpretation", "Between cardiology and geriatrics, or between paediatrics and obstetrics & gynaecology, which pair has the higher discrepancy in popularity and by how much?", "questions/m2_qr_ds1_specialities.png",
     [("Cardiology and geriatrics, by 2.6%", 0), ("Cardiology and geriatrics, by 3.8%", 1), ("Paediatrics and obstetrics and gynaecology, by 2.6%", 0),
      ("Paediatrics and obstetrics and gynaecology, by 3.3%", 0), ("Paediatrics and obstetrics and gynaecology, by 3.8%", 0)], None),
    ("QR0020-3", "Data Interpretation", "By percentage, how much more popular is geriatrics as a second or third choice than as a first choice?", "questions/m2_qr_ds1_specialities.png",
     [("16.9%", 1), ("18.1%", 0), ("20.4%", 0), ("23.2%", 0), ("27.3%", 0)], None),
    ("QR0020-4", "Data Interpretation", "In what proportion of students did psychiatry feature in the top three?", "questions/m2_qr_ds1_specialities.png",
     [("15.0%", 0), ("15.5%", 0), ("16.0%", 0), ("16.5%", 1), ("17.0%", 0)], None),
    ("QR0026-5", "Data Interpretation", "Which month had the highest average temperature?", "questions/m2_qr_ds2_temp.png",
     [("April", 0), ("May", 0), ("June", 0), ("July", 0), ("August", 1)], None),
    ("QR0026-6", "Data Interpretation", "Which month had the highest difference between the maximum recorded temperature and the average for the month?", "questions/m2_qr_ds2_temp.png",
     [("April", 0), ("May", 0), ("June", 0), ("July", 1), ("August", 0)], None),
    ("QR0026-7", "Data Interpretation", "Dan only eats ice cream when the temperature is above 20 degrees Celsius. How many days in August could he eat ice cream?", "questions/m2_qr_ds2_temp.png",
     [("5", 0), ("10", 0), ("15", 0), ("20", 0), ("Can't Tell", 1)], None),
    ("QR0026-8", "Data Interpretation", "What was the average temperature across these five months?", "questions/m2_qr_ds2_temp.png",
     [("18.2", 1), ("20", 0), ("25", 0), ("27.2", 0), ("Can't Tell", 0)], None),
    ("QR0019-9", "Rates & Time", "Erin goes from London to Essex then back to London twice during one week (one leg takes 90 minutes). She also travels to Edinburgh and back at the weekend (4.5 hours each way). What proportion of all the hours in the week are spent travelling?", None,
     [("7.2%", 0), ("8.9%", 1), ("9.5%", 0), ("10.8%", 0), ("11.1%", 0)], None),
    ("QR0019-10", "Rates & Time", "Erin has a railcard giving her 1/3 off fares. London-Essex is £8.70 each way without a railcard; London-Edinburgh is £55.00 each way. How much does Erin save by owning a railcard over her week's travel?", None,
     [("£39.20", 0), ("£41.60", 0), ("£44.10", 0), ("£47.40", 0), ("£48.30", 1)], None),
    ("QR0038-11", "Data Interpretation", "30 teenagers were asked which social media app they spend the most time on (see pie chart). How many more people used Instagram the most than Facebook the most?", "questions/m2_qr_ds4_social.png",
     [("15", 0), ("10", 1), ("5", 0), ("0", 0), ("Can't Tell", 0)], None),
    ("QR0038-12", "Data Interpretation", "How many more people used Snapchat the most than Facebook the most?", "questions/m2_qr_ds4_social.png",
     [("10", 0), ("7", 0), ("5", 1), ("3", 0), ("Can't Tell", 0)], None),
    ("QR0038-13", "Data Interpretation", "In a different class of 50, only 20% said they used Instagram the most. Combining the two classes, what percentage of people used Instagram the most?", "questions/m2_qr_ds4_social.png",
     [("30%", 0), ("31.25%", 1), ("32.5%", 0), ("33.75%", 0), ("25%", 0)], None),
    ("QR0038-14", "Data Interpretation", "One-third of the pupils from the original class who answered Instagram later admitted they used Facebook more. Which is now more popular?", "questions/m2_qr_ds4_social.png",
     [("Facebook by 5", 0), ("Instagram by 5", 0), ("Neither as they are the same", 1), ("Instagram by fewer than 5", 0), ("Can't Tell", 0)], None),
    ("QR0031-15", "Percentages & Money", "Isla takes a student loan for a 4-year degree: £9000 fees plus £9000 living costs per year. She pays it back over 10 years, only after the 4 years. How much will she pay back in total?", None,
     [("£72,446", 0), ("£72,884", 0), ("£73,440", 1), ("£73,844", 0), ("£74,282", 0)], "QR0031"),
    ("QR0031-16", "Percentages & Money", "Michael takes a business loan of £150,000 on a 10-year payback plan. How much will he pay back per month over ten years, including loan and interest?", None,
     [("£1278.50", 0), ("£1331.25", 1), ("£1367.75", 0), ("£1412.50", 0), ("£1457.75", 0)], "QR0031"),
    ("QR0031-17", "Percentages & Money", "Tom is a first-time homebuyer purchasing a £240,000 flat on a fifteen-year mortgage. How much of an increase in interest will there be from the last month of his third year to the first month of his fourth year?", None,
     [("£60", 1), ("£65", 0), ("£70", 0), ("£75", 0), ("£80", 0)], "QR0031"),
    ("QR0031-18", "Percentages & Money", "Gemma takes a 10-year mortgage. She is not a first-time home owner; the house is valued at £550,000. How much interest will she pay in total over the ten years?", None,
     [("£23,750", 0), ("£24,150", 0), ("£24,350", 0), ("£24,500", 0), ("£24,750", 1)], "QR0031"),
    ("QR0009-19", "Percentages & Money", "Francine buys a T-shirt (small clothing item) for £2.00 and sells it for £7.50 including packing and postage. Taking into account the website fee, shipping and original cost, how much profit does she make?", None,
     [("£0.47", 0), ("£0.95", 0), ("£1.38", 0), ("£1.83", 1), ("£2.12", 0)], "QR0009"),
    ("QR0009-20", "Percentages & Money", "Francine buys a necklace (small accessory) for 50p and sells it for £6.00. She forgot to include the website fee. How much less is the profit once she takes the website fee into account?", None,
     [("50p", 0), ("60p", 0), ("70p", 0), ("80p", 0), ("90p", 1)], "QR0009"),
    ("QR0009-21", "Percentages & Money", "Francine buys a leather jacket (large clothing item) for £10.00 and wants a profit of at least £20.00. Taking into account shipping and the website fee, and rounded to the nearest pound, what is the minimum she can sell it for?", None,
     [("£37.00", 0), ("£38.00", 0), ("£39.00", 0), ("£40.00", 1), ("£41.00", 0)], "QR0009"),
    ("QR0036-22", "Data Interpretation", "Henry's flat floorplan is a rectangle, a square and a triangle (dimensions shown). What is the area of the triangle in metres squared?", "questions/m2_qr_ds7_floorplan.png",
     [("45", 0), ("36", 0), ("90", 0), ("54", 0), ("27", 1)], None),
    ("QR0036-23", "Data Interpretation", "Which is bigger: the rectangle or the square?", "questions/m2_qr_ds7_floorplan.png",
     [("The square by 24m.", 0), ("The rectangle by 24m.", 0), ("The square by 24m².", 0), ("The rectangle by 24m².", 1), ("Can't Tell", 0)], None),
    ("QR0036-24", "Data Interpretation", "How long is the perimeter of the rectangular room?", "questions/m2_qr_ds7_floorplan.png",
     [("16", 0), ("20", 0), ("32", 1), ("40", 0), ("42", 0)], None),
    ("QR0036-25", "Data Interpretation", "Henry's walls are 2m tall. In the square room, he has a window 4m by 1.5m. What fraction of the wall does it take up?", "questions/m2_qr_ds7_floorplan.png",
     [("1/4", 0), ("1/3", 0), ("1/2", 1), ("2/3", 0), ("3/4", 0)], None),
    ("QR0027-26", "Data Interpretation", "The chart shows the top 4 batsmen's percentage of runs and Cook's runs across a 5-match series. Which test did Cook score the least runs in?", "questions/m2_qr_ds8_batsmen.png",
     [("1st test.", 0), ("2nd test.", 1), ("3rd test.", 0), ("4th test.", 0), ("5th test.", 0)], None),
    ("QR0027-27", "Data Interpretation", "Who contributed the second fewest runs?", "questions/m2_qr_ds8_batsmen.png",
     [("Pietersen", 0), ("Cook", 0), ("Hussain", 1), ("Trescothick", 0), ("Can't Tell", 0)], None),
    ("QR0027-28", "Data Interpretation", "What was Cook's average score across the first three tests of the series?", "questions/m2_qr_ds8_batsmen.png",
     [("100", 0), ("80", 0), ("75", 1), ("60", 0), ("50", 0)], None),
    ("QR0027-29", "Data Interpretation", "If Cook (40% of the top four's runs) scored 100 runs total... how many runs did Trescothick (25%) score?", "questions/m2_qr_ds8_batsmen.png",
     [("50", 0), ("150", 0), ("200", 0), ("250", 1), ("400", 0)], None),
    ("QR0032-30", "Percentages & Money", "How much fine will a student pay if he loans 3 paperbacks (returned 3 days late) and 2 hardbacks (returned 5 days late)?", None,
     [("£8.50", 0), ("£11.00", 0), ("£16.50", 0), ("£14.50", 1), ("£15.50", 0)], "QR0032"),
    ("QR0032-31", "Percentages & Money", "Sam takes out 3 books of the week and a hardback at 9am. The books of the week are loaned for 4 hours. He returns one at 2pm and the other two at 5pm. What fine does he pay? (Library open 8am-5pm.)", None,
     [("£4.75", 0), ("£6.75", 1), ("£6.50", 0), ("£4.50", 0), ("£7.50", 0)], "QR0032"),
    ("QR0032-32", "Percentages & Money", "Peter takes a hardback and a book of the week at 10am Monday (the book of the week loaned for 6 hours). He returns the book of the week Wednesday 2pm and the hardback five days late. How much fine has Peter paid for the two books?", None,
     [("£14.50", 0), ("£16.00", 0), ("£18.00", 0), ("£15.50", 0), ("£17.00", 1)], "QR0032"),
    ("QR0032-33", "Percentages & Money", "Sarah returns her books at 4:00pm and is charged £3.75 for a red-labelled (book of the week) book loaned for 2 hours. At what time might she have taken it out? (Library open 8am-5pm.)", None,
     [("8am", 0), ("8.30am", 0), ("9am", 1), ("10am", 0), ("11am", 0)], "QR0032"),
    ("QR0035-34", "Percentages & Money", "How much more was sun cream than after sun lotion?", None,
     [("£2.50", 0), ("€2.50", 1), ("£2.20", 0), ("€2.20", 0), ("€2.25", 0)], "QR0035"),
    ("QR0035-35", "Percentages & Money", "A British supermarket sells a 6-pack of beer for £6.60. What is the difference in price per can compared with the €6.00 4-pack?", None,
     [("25p more", 0), ("25p less", 1), ("120p more", 0), ("120p less", 0), ("50p more", 0)], "QR0035"),
    ("QR0035-36", "Percentages & Money", "Thomas bought a sun bed and three ice creams. How much did he spend in pounds?", None,
     [("£6.12", 0), ("£6.80", 0), ("£9.36", 1), ("£10.40", 0), ("£12.00", 0)], "QR0035"),
]

# ---------------- Situational Judgement ----------------
# (code, scale, subtopic, scenario, lead, [(statement, correct_index)...])
SJT = [
    ("SJI0010", IMP, "Professionalism",
     "You are in the medical student common room. You notice some 2nd year medical students making rude, derogatory comments about the patients on the ward.",
     "How important to take into account are the following considerations?",
     [("The students are only second year and so it doesn't matter what they say.", 3), ("The students did not mention the names of the patients.", 3),
      ("It is none of your business.", 3), ("You agree with the comments they are making about the patients.", 3)]),
    ("SJA0010", APP, "Patient Safety",
     "You are a junior doctor, worried that the locum consultant seems to be making some inappropriate discharges, in your opinion.",
     "How appropriate are the following actions in response to the situation?",
     [("Alert the locum consultant of your concerns.", 0), ("Phone the newspaper to make sure the public are warned about the consultant.", 3),
      ("Speak to the locum consultant's line manager.", 1), ("Make sure the nurses do not assign patients to that consultant.", 3)]),
    ("SJI0011", IMP, "Professionalism",
     "Phyllida is ending her first F1 rotation. The consultant has called her an 'idiot' and repeatedly stated she does not deserve to be a doctor. Phyllida is losing self-confidence and no longer wants to come to work.",
     "How important to take into account are the following considerations by Phyllida?",
     [("The consultant is very senior and is probably correct in the remarks he has made.", 3), ("The remarks are impacting her ability to provide optimum patient care.", 0),
      ("It is recommended that individuals inform supervisors in such situations.", 0), ("She is shortly due to move firms, so it doesn't matter.", 2)]),
    ("SJA0011", APP, "Teamwork",
     "You enter the doctor's mess to find your colleague fast asleep. He is on call and has not answered his bleep all night. This has happened before and you are not coping with the extra workload.",
     "How appropriate are the following actions in response to the situation?",
     [("Speak to your colleague about what's been happening and if there's a reason he is acting this way.", 0), ("Encourage your colleague to speak to his supervisor.", 0),
      ("Inform your consultant about the impact it is having on you.", 2), ("Inform the General Medical Council immediately.", 3)]),
    ("SJI0012", IMP, "Patient Safety",
     "Josie is a 4th year medical student who has just returned after intercalation and feels nervous. The F1 has asked Josie to carry out catheterisation on an aggressive patient.",
     "How important to take into account are the following considerations by the F1?",
     [("Josie has never performed catheterisation before.", 0), ("If she refuses, the F1 will not be impressed.", 2),
      ("Josie is afraid that the patient's aggression may put her at harm.", 0), ("Josie may be called a 'waste of space' by the ward staff.", 3)]),
    ("SJA0012", APP, "Confidentiality",
     "You are a third-year medical student in the hospital coffee shop. You hear some fifth-year medical students discussing patients on the Stroke ward, within earshot of patients on the next table.",
     "How appropriate are the following actions in response to the situation?",
     [("Do nothing as they are senior to you and know best.", 3), ("Request that they discuss specific details in private elsewhere.", 0),
      ("Threaten that you will report this to the medical school.", 2), ("Join in with discussing patients as it is good for your medical knowledge.", 3)]),
    ("SJI0013", IMP, "Patient Safety",
     "You are a foundation year doctor at a GP surgery. You notice that one of the GPs has pre-signed his prescription pad to allow a nurse to issue prescriptions to patients.",
     "How important to take into account are the following considerations?",
     [("The GP surgery is very busy.", 3), ("The nurse was top of the year at university.", 3),
      ("Ignoring the situation means more patient interaction and one-to-one sessions with the GP.", 3), ("Pre-signing prescriptions is a very serious matter.", 0)]),
    ("SJA0013", APP, "Professionalism",
     "An elderly lady comes into A&E. Whilst clerking her, you notice the healthcare assistant taking the lady's wallet and putting it into her pockets.",
     "How appropriate are the following actions in response to the situation?",
     [("Call the police as a theft has occurred.", 2), ("Confront the healthcare assistant and ask them to empty their pockets immediately.", 3),
      ("Confirm whether the patient has something missing and discuss what you have seen with the healthcare assistant.", 0), ("Talk to your superior about what you've seen.", 1)]),
    ("SJI0029", IMP, "Confidentiality",
     "Priya is a medical student sitting in on a compulsory outpatient breast clinic. The consultant (a male doctor) does not introduce her to patients or explain who she is, and never asks for a chaperone.",
     "How important are the following considerations for Priya to take into account?",
     [("She is only a medical student.", 3), ("The cases the consultant sees are interesting.", 3),
      ("Reception should inform patients that a medical student will be present.", 0), ("The consultant is the best in the field.", 3)]),
    ("SJA0015", APP, "Coping with Pressure",
     "Your neighbours ask you to look after their pet kittens for a week. You realise you forgot to replenish their food bowls the day before and notice one of the kittens looks extremely unwell.",
     "How appropriate are the following responses?",
     [("Phone your neighbours and explain what has happened.", 0), ("Feed all the kittens extra food for the next few days to ensure they stay in good health.", 2),
      ("Call a vet to inspect the unwell kitten and inform the neighbours.", 0), ("Call the police on 999 to explain the harm you have accidentally brought to the kitten.", 3)]),
    ("SJA0019", APP, "Patient Safety",
     "You are a medical student on a surgical ward. The Registrar asks you to take an X-Ray form to Radiology for Mrs Jones (urgent, possible pelvic fracture). On your way you notice part of the form has not been signed.",
     "How appropriate are each of the following responses?",
     [("Sign the X-Ray form yourself.", 3), ("Give the form in anyway, the registrar knows what he is doing.", 2),
      ("Copy the registrar's signature on to the form.", 3), ("Explain to Radiology that the signature has been missed off but the patient requires the X-Ray urgently.", 1)]),
    ("SJA0014", APP, "Confidentiality",
     "You are a junior doctor. You realise that one of your colleagues always takes home a printout of the patients' X-Rays, and patient identifiable information is not removed.",
     "How appropriate are the following actions in response to the situation?",
     [("Ask him how to print off the X-Rays so you can look good on the ward rounds.", 3), ("Speak to your supervisor about your concerns regarding taking patient identifiable information home.", 0),
      ("Threaten your colleague that you will report his behaviour to the GMC.", 3), ("Remove the printer from the ward without informing the ward manager.", 3)]),
    ("SJA0020", APP, "Confidentiality",
     "You are at a GP surgery, having a great experience. However, you notice the next patient is your mum's best friend, Julia.",
     "How appropriate are each of the following responses?",
     [("Ask for Julia's (the patient's) consent to sit in for the consultation.", 0), ("Discuss with the GP that you know Julia and don't believe you should stay in this consultation.", 0),
      ("Call your mum and tell her that Julia is at the GP.", 3), ("Pretend you do not recognise Julia.", 3)]),
    ("SJA0017", APP, "Confidentiality",
     "Joe is a third-year medical student. The consultant suggests he reads the previous patient's clinical notes. Having flicked through them, Joe places them on a table near an open window; a gust of wind blows a page out the window onto the road.",
     "How appropriate are each of the following responses by Joe?",
     [("Run outside to make sure he obtains the page.", 1), ("Pretend nothing has happened.", 3),
      ("Explain to the consultant what has happened.", 0), ("Complain that he has a headache to go home early.", 3)]),
    ("SJA0021", APP, "Confidentiality",
     "It is your first day as a 3rd year medical student. You must prepare a case-based discussion. Mrs Phillips has an interesting case history and you would like a copy of her notes.",
     "How appropriate are each of the following responses?",
     [("Take a picture of the notes, including patient identifiable information.", 3), ("Rewrite the relevant information into your notebook without patient identifiable information.", 0),
      ("Take the relevant pages from the patient's notes folder, planning to return them after the session.", 3), ("Photocopy the notes with patient identifiable information as there may be many Mrs Jones in the hospital.", 3)]),
    ("SJA0018", APP, "Professionalism",
     "On the morning before Jonathan's last day of placement he vomits but attributes it to something he ate. He no longer feels unwell after being sick.",
     "How appropriate are the following responses?",
     [("As he feels better, he should attend placement as normal.", 3), ("Skip placement but do not inform the secretary.", 3),
      ("Call his education supervisor immediately to explain what has happened.", 0), ("Do not attend placement and follow the local guidelines for reporting absences.", 0)]),
    ("SJA0022", APP, "Patient Safety",
     "You are a medical student at a GP surgery with Mr Thomas. Just as the GP is about to give his X-Ray results, the GP receives a phone call and steps out. Mr Thomas is desperate to know and asks if you can tell him.",
     "How appropriate are each of the following responses?",
     [("Tell them you will go and find the doctor.", 2), ("Tell Mr Thomas that you have not covered how to read X-Rays thoroughly in your medical training.", 2),
      ("Explain that you are a medical student and it is best that the doctor explains the X-Ray findings.", 0), ("Tell the patient you cannot see any major abnormalities so he is less anxious, though you are not sure.", 3)]),
    ("SJA0016", APP, "Coping with Pressure",
     "Nadia is a third-year medical student on her first surgical placement. A short-tempered consultant surgeon invites her to take part in a surgery. Once scrubbed up, she realises it is the amputation of a gangrenous toe; asked to cut back some skin, she immediately feels nauseated.",
     "How appropriate are the following responses by Nadia?",
     [("Admit to the surgeon that she feels unwell and ask to leave the theatre.", 0)]),
]


def build():
    qr_q = []
    n = 0
    for ref, sub, stem, image, opts, table in QR:
        n += 1
        q = {"number": str(n), "ref": f"M2 {ref}", "subtopic": sub, "kind": "mcq", "stem": stem,
             "options": [{"text": t, "correct": bool(c)} for t, c in opts]}
        if table:
            q["passage"] = QR_TABLES[table]
        if image:
            q["image"] = image
        qr_q.append(q)
    _write("mock2_qr.json", {"section": {"code": "QR", "name": "Quantitative Reasoning", "source": SOURCE}, "questions": qr_q})

    sjt_q = []
    n = 0
    for code, scale, sub, scenario, lead, items in SJT:
        for statement, ci in items:
            n += 1
            sjt_q.append({"number": str(n), "ref": f"M2 {code} Q{n}", "subtopic": sub, "kind": "mcq",
                          "passage": f"{scenario}\n\n{lead}", "stem": statement,
                          "options": [{"text": t, "correct": (i == ci)} for i, t in enumerate(scale)]})
    _write("mock2_sjt.json", {"section": {"code": "SJT", "name": "Situational Judgement", "source": SOURCE}, "questions": sjt_q})

    lines = ["# Mock 2 - Imported Questions (part 2: QR + SJT)\n",
             "Source: PMT UCAT Mock Examination 2 (placeholder demo content, tagged PMT-M2).\n",
             f"**Quantitative Reasoning:** {len(qr_q)} items ({sum(1 for q in qr_q if q.get('image'))} with charts)",
             f"**Situational Judgement:** {len(sjt_q)} items across 18 scenarios\n",
             "\n---\n## Quantitative Reasoning\n"]
    for q in qr_q:
        lines.append(f"\n**{q['number']}. ({q['ref'].split()[1]})** {q['stem']}{'  `[chart]`' if q.get('image') else ''}")
        for opt in q["options"]:
            lines.append(f"- {opt['text']}{'  ✅' if opt['correct'] else ''}")
    lines.append("\n---\n## Situational Judgement\n")
    last = None
    for q in sjt_q:
        code = q["ref"].split()[1]
        if code != last:
            lines.append(f"\n### Scenario {code}\n> {q['passage'].splitlines()[0]}\n")
            last = code
        lines.append(f"\n**{q['number']}.** {q['stem']}")
        for opt in q["options"]:
            lines.append(f"- {opt['text']}{'  ✅' if opt['correct'] else ''}")
    with open(os.path.join(ROOT, "imported_questions_review", "mock2_part2.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"QR items: {len(qr_q)} ({sum(1 for q in qr_q if q.get('image'))} charts) | SJT items: {len(sjt_q)}")
    print("QR by subtopic:", dict(Counter(q["subtopic"] for q in qr_q)))
    print("SJT by subtopic:", dict(Counter(q["subtopic"] for q in sjt_q)))


def _write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    build()
