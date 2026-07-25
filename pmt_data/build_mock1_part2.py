"""Build Mock 1 QR + SJT JSON (source PMT-M1) + review markdown (part 2).

QR: data-set tables transcribed into passages; charts attached as images.
SJT: 18 scenarios; each item is one question with the shared scenario + the
4-point importance or appropriateness scale.
"""
import json
import os
from collections import Counter

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
SOURCE = "PMT-M1"

APP = ["A very appropriate thing to do.", "Appropriate, but not ideal.",
       "Inappropriate, but not awful.", "A very inappropriate thing to do."]
IMP = ["Very important.", "Important.", "Of minor importance.", "Not important at all."]

# ---------------- Quantitative Reasoning ----------------
QR_TABLES = {
    "QR0001": "Ticket rates for Butterfly World theme park. Standard (Mon-Fri) / Weekend (Sat-Sun) / Bank Holiday: "
              "Adults £10.00/£15.00/£12.50; Children (12 and under) £5.00/£7.50/£6.50; Infants (3 and under) Free/Free/Free; "
              "Students £7.50/£9.50/£8.50; Seniors (65+) £5.00/£7.50/£6.50; Family (2 adults + 2 children) £25.00/£30.00/£27.50.",
    "QR0005": "A cohort of 250 Year 11 students named their least favourite subject. Maths, Biology, Chemistry and Physics "
              "are 'Sciences'; all others are 'Arts'. Least favourite counts: Maths 64, English 76, Biology 12, Physics 78, "
              "Chemistry 16, PE 3, Design Technology 2.",
    "QR0007": "Sugar and Spice, a London bakery, makes custom cakes with free delivery within 3km, otherwise delivery within "
              "20km costs £5.00 plus 50p per km. Cupcakes: one tier = one dozen; +£10 if cupcakes instead of a cake. "
              "Prices (One/Two/Three/Four Tiers): Basic £20/£25/£30/£40; Cake Toppers +£4.00/£5.00/£6.00/£7.00; "
              "Writing +£5.00/£5.50/£6.00/£6.50; Sparkler Candles +£2.50/£2.75/£3.00/£3.25.",
    "QR0016": "Stanley trades mobile phones in Hong Kong Dollars (HKD). 10 HKD = £1; 8 HKD = $1 (US). Prices in HKD "
              "(Bought as excess stock / Bought second hand / Marked up from excess stock / Marked up second hand sold whole / "
              "Marked up second hand sold for parts): Vela Pulsar X 400/300/700/450/550; Andromeda 200 250/150/450/350/325; "
              "Primus 16 650/500/1000/675/750; Gravida 3 200/125/375/200/250; Hai Mish 1C 500/375/850/450/550.",
}
# (ref, subtopic, stem, image_or_None, [(opt,correct_bool)...], data_set_ref_for_table_or_None)
QR = [
    ("QR0001-1", "Percentages & Money", "A group of seven students go to Butterfly World on a Saturday. Three forget their student ID and pay a full adult ticket. How much more expensive is the overall cost by %?", None,
     [("10%", 0), ("15%", 0), ("20%", 0), ("25%", 1), ("30%", 0)], "QR0001"),
    ("QR0001-2", "Percentages & Money", "A family of 2 adults and 4 children (ages 4-12) visit on a normal Tuesday. How much cheaper is it to buy the family package plus two extra child tickets compared to buying all tickets separately?", None,
     [("£2.50", 0), ("£5.00", 1), ("£7.50", 0), ("£10.00", 0), ("£12.50", 0)], "QR0001"),
    ("QR0001-3", "Percentages & Money", "A family (two adults, an 8-year-old and a 3-year-old) visit on a bank holiday. Which is cheaper: two adult tickets and a child ticket (infants free), or the family package, and by how much?", None,
     [("Individual tickets, by £4.00.", 0), ("Family package, by £2.50.", 0), ("Family package, by £4.00.", 1),
      ("Family package, by £5.50.", 0), ("Individual tickets, by £6.00.", 0)], "QR0001"),
    ("QR0001-4", "Percentages & Money", "An extended family of 4 adults, 2 seniors, 2 students, 4 children and an infant visit on a normal Wednesday. Using the family group discount, how much will they pay?", None,
     [("£75.00", 1), ("£80.00", 0), ("£85.00", 0), ("£90.00", 0), ("£95.00", 0)], "QR0001"),
    ("QR0010", "Percentages & Money", "Jenny buys a car in 2010 worth £20,000. On purchase it is worth £1,500 less, and each year thereafter it depreciates by 10%. In 2014 she buys a new car costing £15,000 and sells her old car. How much will she still have to pay for the new car?", None,
     [("£1646.75", 0), ("£2264.35", 0), ("£2674.95", 0), ("£2862.15", 1), ("£3124.50", 0)], None),
    ("QR0005-6", "Data Interpretation", "Which is the least liked subject?", None,
     [("English", 0), ("Maths", 0), ("Physics", 1), ("Design Technology", 0), ("Chemistry", 0)], "QR0005"),
    ("QR0005-7", "Data Interpretation", "What percentage of students least liked a 'science' subject?", None,
     [("68%", 1), ("64%", 0), ("42%", 0), ("86%", 0), ("7%", 0)], "QR0005"),
    ("QR0005-8", "Data Interpretation", "What was the least liked 'Arts' subject?", None,
     [("PE", 0), ("Maths", 0), ("English", 1), ("Physics", 0), ("Design Technology", 0)], "QR0005"),
    ("QR0005-9", "Data Interpretation", "The school changed its physics teacher. The next 250-student cohort did the same questionnaire and 54 chose physics. What percentage decrease occurred?", None,
     [("21.6%", 0), ("54%", 0), ("24%", 0), ("9.6%", 1), ("31.2%", 0)], "QR0005"),
    ("QR0006-10", "Data Interpretation", "Mr Duhra wants a circular dance floor in his rectangular basement (16m x 14m, circle radius 7m). Marble is £4.30/m². What percentage of the basement area is the dance floor?", "questions/m1_qr_ds3_dancefloor.png",
     [("68.7%", 1), ("153.4%", 0), ("68.4%", 0), ("224%", 0), ("70.6%", 0)], None),
    ("QR0006-11", "Data Interpretation", "What is the perimeter of the dance floor (radius 7m)?", "questions/m1_qr_ds3_dancefloor.png",
     [("44.0m", 1), ("22.0m", 0), ("153.4m", 0), ("153.9m", 0), ("Can't tell.", 0)], None),
    ("QR0006-12", "Data Interpretation", "How much will it cost Mr Duhra to marble the dance floor at £4.30/m²?", "questions/m1_qr_ds3_dancefloor.png",
     [("£963.20", 0), ("£294.55", 0), ("£661.60", 1), ("£189.20", 0), ("£94.60", 0)], None),
    ("QR0006-13", "Data Interpretation", "Mr Duhra adds a water feature in the centre with a rectangular base of 4m x 2.3m. What percentage area of the dance floor does it cover?", "questions/m1_qr_ds3_dancefloor.png",
     [("4.1%", 0), ("5.9%", 0), ("6.0%", 1), ("8.4%", 0), ("8.5%", 0)], None),
    ("QR0007-14", "Percentages & Money", "Emma lives 2km from the bakery. She chooses between a four-tier cake with cake toppers and sparkler candles, or the equivalent cupcakes with no candles or toppers. Which is cheaper and by how much?", None,
     [("The cake, by 25p.", 0), ("The cake, by 50p.", 0), ("The cake, by 75p.", 0), ("The cupcakes, by 25p.", 1), ("The cupcakes, by 50p.", 0)], "QR0007"),
    ("QR0007-15", "Percentages & Money", "Gregory orders a three-tier cake with writing and sparkler candles. He lives 7km away and opts for delivery. How much does his order total?", None,
     [("£44.50", 0), ("£46.00", 0), ("£47.50", 1), ("£48.00", 0), ("£49.50", 0)], "QR0007"),
    ("QR0007-16", "Percentages & Money", "Nina has a £55.00 budget for a cake and delivery. She lives 12km away and wants a cake with toppers, writing and candles. How many tiers can she afford?", None,
     [("No tiers.", 0), ("One tier.", 0), ("Two tiers.", 1), ("Three tiers.", 0), ("Four tiers.", 0)], "QR0007"),
    ("QR0007-17", "Percentages & Money", "Juan orders a dozen cupcakes with writing and opts for delivery. His total comes to £47.00. How far away does he live?", None,
     [("10km", 0), ("11km", 0), ("12km", 0), ("13km", 0), ("7km", 1)], "QR0007"),
    ("QR0023", "Tables & Statistics", "Katie scores an average of 81% across five subjects. She got 78% in French, 85% in English, 73% in History and 80% in Maths. What did she get in Biology?", None,
     [("79%", 0), ("81%", 0), ("83%", 0), ("86%", 0), ("89%", 1)], None),
    ("QR0029-19", "Data Interpretation", "The chart shows the average and highest return prices of a standard-class train from London to Leeds booked 12 weeks in advance. Which month had the lowest average return price?", "questions/m1_qr_ds5_train.png",
     [("May", 0), ("June", 1), ("July", 0), ("August", 0), ("September", 0)], None),
    ("QR0029-20", "Data Interpretation", "The second most expensive return price was found in which month?", "questions/m1_qr_ds5_train.png",
     [("June", 0), ("July", 0), ("August", 0), ("September", 0), ("Can't tell.", 1)], None),
    ("QR0029-21", "Data Interpretation", "Which two months had the same average return price?", "questions/m1_qr_ds5_train.png",
     [("May and July", 0), ("May and June", 0), ("June and July", 0), ("July and September", 1), ("May and September", 0)], None),
    ("QR0029-22", "Data Interpretation", "If I buy the most expensive return ticket for each month, how much will I pay?", "questions/m1_qr_ds5_train.png",
     [("£67", 0), ("£68", 0), ("£122", 0), ("£123", 0), ("£124", 1)], None),
    ("QR0022", "Percentages & Money", "In a normal early pregnancy, hCG rises by about 66% every 48h. Claudia is 6 weeks pregnant with an hCG level of 1200 units. Given a normal pregnancy, what level would you expect two weeks later?", None,
     [("2432", 0), ("23,412", 0), ("35,639", 0), ("41,681", 1), ("42,374", 0)], None),
    ("QR0016-24", "Percentages & Money", "Stanley buys 20 Gravida 3s, 10 Hai Mish 1Cs and 30 Vela Pulsar Xs as excess stock and sells them all on as marked-up excess factory stock. How much profit does he make (HKD)?", None,
     [("$13,000", 0), ("$14,000", 0), ("$15,000", 0), ("$16,000", 1), ("$17,000", 0)], "QR0016"),
    ("QR0016-25", "Percentages & Money", "A UK company buys the spare parts of 8 second-hand Hai Mish 1Cs and 15 Primus 16s. Stanley charges a $350 shipping fee. How much does this cost them in pounds sterling?", None,
     [("£1550", 0), ("£1600", 1), ("£1650", 0), ("£1700", 0), ("£1750", 0)], "QR0016"),
    ("QR0016-26", "Percentages & Money", "Stanley buys 50 Vela Pulsar Xs as excess stock but mistakenly sells them as second-hand phones. How much more profit would he have made if he had sold them correctly?", None,
     [("$2500", 0), ("$3725", 0), ("$5000", 1), ("$9750", 0), ("$12500", 0)], "QR0016"),
    ("QR0016-27", "Percentages & Money", "A US shop buys 150 Andromedas from Stanley to sell as second-hand whole phones. Stanley charges 600 HKD shipping. The shop marks the phones up by 20% and sells them. How much profit do they make in USD?", None,
     [("$1264.80", 0), ("$1327.50", 1), ("$1412.10", 0), ("$1772.50", 0), ("$1812.50", 0)], "QR0016"),
    ("QR0030-28", "Data Interpretation", "The chart shows taxation data (Corporation tax, Basic Rate Income Tax, VAT) of European countries in 2018. Which country has the lowest VAT?", "questions/m1_qr_ds7_tax.png",
     [("UK", 0), ("Ireland", 0), ("Sweden", 0), ("Switzerland", 1), ("Can't tell.", 0)], None),
    ("QR0030-29", "Data Interpretation", "Which country has the highest average tax rate?", "questions/m1_qr_ds7_tax.png",
     [("UK", 0), ("Ireland", 0), ("Sweden", 1), ("Switzerland", 0), ("Can't tell.", 0)], None),
    ("QR0030-30", "Data Interpretation", "Dan buys an item which without VAT costs the equivalent of £10. If he pays £11.50, which country is he in?", "questions/m1_qr_ds7_tax.png",
     [("UK", 0), ("Ireland", 1), ("Sweden", 0), ("Switzerland", 0), ("Can't tell.", 0)], None),
    ("QR0030-31", "Data Interpretation", "In the UK, Harry pays £15,000 in taxation. How much does he earn post tax?", "questions/m1_qr_ds7_tax.png",
     [("£60000", 0), ("£55000", 0), ("£50000", 0), ("£45000", 1), ("£40000", 0)], None),
    ("QR0014", "Ratios & Units", "A candle is scented using lemon, grapefruit, raspberry and vanillin in the ratio 1:2:1:3. A 600g candle needs 4ml of grapefruit oil. For a candle double that weight, how much vanillin oil is required?", None,
     [("4ml", 0), ("8ml", 0), ("10ml", 0), ("12ml", 1), ("16ml", 0)], None),
    ("QR0008-33", "Data Interpretation", "The pie chart shows genres sold by a bookshop in May (1351 total: Historical 167, Biographical 254, Children's 378, Classics 143, New Fiction 321, Poetry 88). The owner sold an extra 100 poetry books not accounted for. What is the new percentage of total sales made up by poetry, to the nearest 0.5%?", "questions/m1_qr_ds8_pie.png",
     [("6.5%", 0), ("8%", 0), ("10.5%", 0), ("13%", 1), ("14%", 0)], None),
    ("QR0008-34", "Data Interpretation", "The owner also forgot cookery: 198 cookery books sold in May. What is the percentage difference between the proportion of cookery books and children's books sold, using the new total, to the nearest 1%?", "questions/m1_qr_ds8_pie.png",
     [("9%", 0), ("10%", 0), ("11%", 1), ("12%", 0), ("13%", 0)], None),
    ("QR0008-35", "Data Interpretation", "Using the original pie chart data, what percentage of total books sold do the two biggest sellers, Children's and New Fiction, represent, to the nearest 1%?", "questions/m1_qr_ds8_pie.png",
     [("48%", 0), ("49%", 0), ("50%", 0), ("51%", 0), ("52%", 1)], None),
    ("QR0013", "Rates & Time", "A taxi company charges £3.00 baseline, 80p per km after that, £1.50 if booked online, and £2.50 for luggage or animals. Freddy books a taxi online to take his dog to the vet, costing £16.60. How far away is the vet?", None,
     [("8km", 0), ("9km", 0), ("10km", 0), ("11km", 0), ("12km", 1)], None),
]

# ---------------- Situational Judgement ----------------
# (code, scale, subtopic, scenario, lead, [(statement, correct_index)...])
SJT = [
    ("SJI0001", IMP, "Professionalism",
     "You are walking past the Care of the Elderly ward. You notice Sarah, a junior nurse, shout at her patients and storm off the ward. You have not seen Sarah behave like this before.",
     "How important to take into account are the following considerations?",
     [("You have not seen Sarah act like this before.", 2), ("The patient was misbehaving and deserved it.", 3),
      ("The patient is very distressed by the situation.", 0), ("Sarah is a good nurse and is vital for the smooth running of the department.", 2)]),
    ("SJA0001", APP, "Confidentiality",
     "John is a final year medical student. He has just observed the consultant diagnose Mrs Jones with breast cancer. As John is leaving, Mrs Jones' husband approaches and asks about the results.",
     "How appropriate are the following actions in response to the situation?",
     [("Inform Mrs Jones' husband that she is suffering from brain cancer.", 0), ("Lie and tell Mrs Jones' husband that she is absolutely fine as you don't want to cause him distress.", 3),
      ("Advise Mrs Jones' husband that it is best if he spoke to her.", 0), ("Politely inform Mrs Jones' husband that you are a medical student and the consultant in charge would know best.", 0)]),
    ("SJI0002", IMP, "Professionalism",
     "A patient has made an official complaint. Your name has been mentioned in the complaint.",
     "How important to take into account are the following when considering your next step?",
     [("You are a member of a defence union.", 2), ("You never liked the patient.", 3),
      ("Your friend told you to just ignore the complaint.", 3), ("It is hospital policy to discuss such complaints with a supervisor.", 0)]),
    ("SJA0002", APP, "Professionalism",
     "You are a medical student, shopping with your friends. A patient you saw last week approaches you and asks you to look at his foot ulcer.",
     "How appropriate are the following actions in response to the situation?",
     [("Advise him to book an appointment with the GP.", 0), ("Pretend you didn't hear him and carry on shopping.", 3),
      ("Find a first aid room and examine his foot ulcer.", 3), ("Advise him you are a medical student, so you aren't able to provide medical advice.", 1)]),
    ("SJI0003", IMP, "Patient Safety",
     "A nurse contacts you to inform you that you have incorrectly prescribed co-amoxiclav (a penicillin-containing antibiotic) to a patient who is allergic to penicillin.",
     "How important to take into account are the following considerations?",
     [("The patient did not suffer a reaction.", 2), ("Ensure the patient understands what has happened.", 0),
      ("Personally apologise to the patient.", 0), ("The patient has dementia and probably won't remember.", 3)]),
    ("SJA0003", APP, "Patient Safety",
     "You are a medical student and accidentally suffer a needlestick injury whilst attempting to draw blood from a patient.",
     "How appropriate are the following actions in response to the situation?",
     [("Immediately stop your attempt to draw blood.", 0), ("Ask the patient if you can have another try at drawing blood immediately after.", 3),
      ("Inform the ward staff of the incident.", 0), ("Contact occupational health.", 0)]),
    ("SJI0004", IMP, "Patient Safety",
     "You are working in the oncology unit. Mr Jones is refusing to take his chemotherapy tablets. You have explained the risks if he does not take the tablet.",
     "How important to take into account are the following considerations?",
     [("Assess the patient's mental state.", 0), ("Documentation of this encounter is vital.", 0),
      ("The patient has capacity to make such decisions.", 0), ("The patient probably wouldn't notice if you mix the tablet in his water jug.", 3)]),
    ("SJA0004", APP, "Professionalism",
     "A patient approaches you and explains that he is not happy with the care he has received. He does not like the hospital food and finds that the nurses are rude.",
     "How appropriate are the following actions in response to the situation?",
     [("Listen carefully to the patient's views and see if you can resolve the problems.", 0), ("Apologise that the standard of care hasn't reached his expectations.", 1),
      ("Tell the patient that you will only provide him with treatment if he is respectful.", 3), ("Explain how stretched the NHS is.", 3)]),
    ("SJI0005", IMP, "Patient Safety",
     "A patient is rushed into A&E, suspected to have appendicitis. The ambulance staff inform you the patient speaks very little English.",
     "How important to take into account are the following considerations?",
     [("Your colleague speaks the patient's language and would be able to communicate.", 0), ("The patient doesn't need to understand the procedure as he is too unwell.", 3),
      ("The NHS translator services are on hand to help.", 0), ("The patient's family may be able to translate.", 2)]),
    ("SJA0005", APP, "Confidentiality",
     "You have downloaded patient data on to a USB stick. When you check your bag later on, it is no longer there.",
     "How appropriate are the following actions in response to the situation?",
     [("You know that your USB is password protected so do nothing.", 3), ("Tell your junior doctor colleagues to keep an eye out.", 1),
      ("Discuss the situation with the information governance department.", 0), ("Report the issue to your consultant.", 1)]),
    ("SJI0006", IMP, "Professionalism",
     "You are a 5th year medical student on GP placement. You notice another 5th year student, Jonathan, constantly putting down a 4th year student, Sophie, in front of patients.",
     "How important to take into account are the following considerations for Sophie?",
     [("Jonathan is in the year above.", 3), ("This may be a form of bullying.", 0),
      ("It is best to do nothing as Jonathan is a very good medical student.", 3), ("The supervisor of the placement offered to help in such situations.", 0)]),
    ("SJA0006", APP, "Professionalism",
     "Mrs Johnson's son would like to make an official complaint regarding the way his mother has been treated on your ward.",
     "How appropriate are the following actions in response to the situation?",
     [("Discuss the reasoning for the complaint with the patient and the ward manager.", 1), ("Advise the patient's son that he can contact the Patient Advice and Liaison Service to make his complaint.", 0),
      ("Tell the patient's son that you are very busy and do not have time to deal with such small matters.", 3), ("Ignore the patient's son and tell him that all the staff are wonderful and the patient is in great hands.", 3)]),
    ("SJI0007", IMP, "Professionalism",
     "You are a 3rd year medical student at a district general hospital. You notice that two of your colleagues sign the register for each other and are often absent for teaching sessions.",
     "How important to take into account are the following considerations?",
     [("They both have many publications and are probably making better use of their time.", 3), ("You think the teaching sessions are useless anyway.", 3),
      ("It offers more teaching opportunities if many people are away.", 3), ("You find the teaching valuable.", 1)]),
    ("SJA0007", APP, "Teamwork",
     "You are working within a busy A&E department. You see that a number of tasks you assigned to the nurse have not been completed within the expected time.",
     "How appropriate are the following actions in response to the situation?",
     [("Inform the nurse in charge.", 1), ("Inform the nurse responsible.", 0),
      ("Write the reason for the delay in the documents.", 0), ("Contact the Medical Defence Union immediately.", 3)]),
    ("SJI0008", IMP, "Professionalism",
     "You are a junior doctor on a surgical ward. A female junior doctor, Sophie, says that the registrar in your firm has been making sexually inappropriate jokes.",
     "How important to take into account are the following considerations by Sophie?",
     [("As the registrar is very senior, he may not offer you a role in the department if you mention anything.", 3), ("You feel threatened by the situation.", 0),
      ("It has only occurred once.", 3), ("The registrar has acted this way to other female doctors.", 1)]),
    ("SJA0008", APP, "Patient Safety",
     "There is an emergency on the ward and the nurse shouts for your help. She requests that you immediately perform a procedure you have seen only once before.",
     "How appropriate are the following actions in response to the situation?",
     [("Call your supervisor for support.", 0), ("Perform the procedure alone.", 3),
      ("Ask the nurse to call for urgent help whilst you begin to prepare for and perform the procedure.", 2), ("Ask the nurse to call for urgent help whilst you begin to prepare for the procedure.", 1)]),
    ("SJI0009", IMP, "Coping with Pressure",
     "It is Monday morning on the acute medical unit. You have a stack of jobs waiting and your bleep is continuously ringing. You feel very overwhelmed.",
     "How important to take into account are the following considerations?",
     [("Prioritise the jobs.", 0), ("Ask if another colleague is available to help as you feel flustered.", 0),
      ("Taking a short break will let the department down.", 1), ("The shift ends soon.", 1)]),
    ("SJA0009", APP, "Professionalism",
     "Your fellow junior doctor colleague asks you to prescribe some medication for his son. You are not aware of the medication and have never met your colleague's son.",
     "How appropriate are the following actions in response to the situation?",
     [("Refuse to prescribe the medication and suggest that he takes his son to their GP.", 0)]),
]


def build():
    # ---- QR ----
    qr_q = []
    n = 0
    for ref, sub, stem, image, opts, table in QR:
        n += 1
        q = {"number": str(n), "ref": f"M1 {ref}", "subtopic": sub, "kind": "mcq", "stem": stem,
             "options": [{"text": t, "correct": bool(c)} for t, c in opts]}
        if table:
            q["passage"] = QR_TABLES[table]
        if image:
            q["image"] = image
        qr_q.append(q)
    _write("mock1_qr.json", {"section": {"code": "QR", "name": "Quantitative Reasoning", "source": SOURCE}, "questions": qr_q})

    # ---- SJT ----
    sjt_q = []
    n = 0
    for code, scale, sub, scenario, lead, items in SJT:
        for statement, ci in items:
            n += 1
            sjt_q.append({"number": str(n), "ref": f"M1 {code} Q{n}", "subtopic": sub, "kind": "mcq",
                          "passage": f"{scenario}\n\n{lead}", "stem": statement,
                          "options": [{"text": t, "correct": (i == ci)} for i, t in enumerate(scale)]})
    _write("mock1_sjt.json", {"section": {"code": "SJT", "name": "Situational Judgement", "source": SOURCE}, "questions": sjt_q})

    # ---- Review markdown ----
    lines = ["# Mock 1 - Imported Questions (Phase 5, part 2: QR + SJT)\n",
             "Source: PMT UCAT Mock Examination 1 (placeholder demo content, tagged PMT-M1).\n",
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
    with open(os.path.join(ROOT, "imported_questions_review", "mock1_part2.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"QR items: {len(qr_q)} ({sum(1 for q in qr_q if q.get('image'))} charts) | SJT items: {len(sjt_q)}")
    print("QR by subtopic:", dict(Counter(q["subtopic"] for q in qr_q)))
    print("SJT by subtopic:", dict(Counter(q["subtopic"] for q in sjt_q)))


def _write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    build()
