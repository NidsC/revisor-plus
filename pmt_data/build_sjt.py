"""Build the Situational Judgement JSON + review markdown from transcribed PMT content.

Each scenario has several items; every item is one question with the shared scenario
as passage, the statement as stem, and the 4-point rating scale as options.
"""
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)

APP = ["A very appropriate thing to do.", "Appropriate, but not ideal.",
       "Inappropriate, but not awful.", "A very inappropriate thing to do."]
IMP = ["Very important.", "Important.", "Of minor importance.", "Not important at all."]

APP_LEAD = "How appropriate are each of the following responses in this situation?"
IMP_LEAD = "How important are the following considerations?"

# (code, scale, subtopic, scenario, lead, items[(num, statement, correct_index)])
SCENARIOS = [
    ("SJA0030", "app", "Professionalism",
     "You are a 3rd year medical student on placement. The registrar has been asked to give some lectures on diabetes. However, you hear him say to a colleague that he's not going to give them as teaching isn't part of his job description.",
     APP_LEAD,
     [(1, "Speak to your placement co-ordinator about the issue.", 0),
      (2, "Do nothing, it means you have more free time.", 3),
      (3, "Report his unprofessional behaviour to his supervisor.", 2),
      (4, "Skip placement sessions as all doctors feel that teaching is not worth it.", 3)]),
    ("SJI0020", "imp", "Patient Safety",
     "You are a medical student. The junior doctor has prescribed a penicillin-containing antibiotic to a patient on the ward. You recall the patient telling you that they have a minor allergy to penicillin which causes a skin rash upon administration.",
     IMP_LEAD,
     [(5, "The junior doctor is senior to you.", 3),
      (6, "The patient will only suffer a mild reaction that will clear up within hours.", 2),
      (7, "If you are wrong, the department will judge you.", 3),
      (8, "It is in the best interests of the patient that the junior doctor is informed before the medication is administered.", 0)]),
    ("SJA0024", "app", "Patient Safety",
     "You are a medical student on the cardiology unit. Your registrar has been called away. You are asked to do an electrocardiogram (ECG) for a patient by a junior doctor, however you have never conducted one before and only briefly remember how to do so.",
     APP_LEAD,
     [(9, "Do the ECG, the machine will tell you what to do.", 3),
      (10, "Explain you do not feel comfortable performing an ECG and would like some more experience.", 0),
      (11, "Conduct the ECG. It's a quick procedure and you do not want to look stupid for not being able to do it.", 3),
      (12, "Perform the ECG provided that the junior doctor is willing to supervise you.", 0)]),
    ("SJA0029", "app", "Professionalism",
     "You are asked to see a patient by the nurse as the other foundation doctor says he is busy with a patient. Upon entering the doctor's common room you find him watching TV and eating a takeaway.",
     APP_LEAD,
     [(13, "Explain the situation and ask him why he did not attend the call.", 0),
      (14, "Complain directly to his supervisor.", 2),
      (15, "Do nothing, it was a one off and won't happen again.", 2),
      (16, "Join him and order yourself a takeaway whilst on-call too.", 3)]),
    ("SJA0023", "app", "Coping with Pressure",
     "As part of your medical course there are continuous assessments and examinations that need to be completed successfully in order to continue along the course. It has come to the summer period, where you have 2 essays, 5 exams and you need to complete your attendance log on the wards and in the clinics. Your friend has come to you, asking for your advice as they have fallen behind in their work and are struggling to keep up.",
     APP_LEAD,
     [(17, "Advise them that student support is available to support situations such as stress from workload.", 0),
      (18, "Tell them that skipping placement is a good idea so that they can catch up on work.", 3),
      (19, "Do not offer advice as it means your rank will be better if they struggle.", 3),
      (20, "Advise your friend to talk to their personal tutor and work out a plan to make sure they stay on top of the workload.", 0)]),
    ("SJI0015", "imp", "Professionalism",
     "You are a foundation year doctor gaining some experience at the GP surgery. You notice that one of the GPs is signing off sick notes for long periods of time. You feel some are too long.",
     IMP_LEAD,
     [(21, "You are only a foundation year doctor and the GP is your supervisor.", 3),
      (22, "You probably don't have enough experience in length of sick notes.", 2),
      (23, "No one else in the practice has noticed.", 3),
      (24, "The patients give the practice excellent positive feedback.", 3)]),
    ("SJA0025", "app", "Confidentiality",
     "Hilary is a 3rd year medical student shadowing a doctor whilst completing her placement in A&E. The doctor informs Hilary that they are now going to clerk a 21 year old female and tells her their name. Hilary realises that the girl is in the same year as her at medical school at her university.",
     APP_LEAD,
     [(25, "Inform the doctor that you may know the patient.", 0),
      (26, "Gain consent from the patient to sit in on the consultation.", 0),
      (27, "Pretend that you do not know the patient.", 3),
      (28, "Tell your best friends at university that the girl came into A&E and about the consultation.", 3)]),
    ("SJA0027", "app", "Teamwork",
     "You are examining a child as part of your women and child placement block. The child screams at you to stop touching him.",
     APP_LEAD,
     [(29, "Stop the examination and address the child's concerns.", 0),
      (30, "Shout back at the child.", 3),
      (31, "Stop and ask the senior doctor to finish the examination.", 0),
      (32, "Continue the examination and ignore the child.", 3)]),
    ("SJI0017", "imp", "Patient Safety",
     "You are a foundation year doctor. A lady brings in her 2 year old child. You notice that the child has not received the measles, mumps and rubella (MMR) vaccination as her mother is worried about the risk of autism.",
     IMP_LEAD,
     [(33, "MMR are very serious, possibly life-threatening conditions.", 0),
      (34, "The child's mother is a world-renowned scientist.", 3),
      (35, "It is the mother's decision whether the child receives the MMR vaccine.", 0),
      (36, "An information leaflet and exploration of the mother's concerns may be helpful.", 0)]),
    ("SJI0016", "imp", "Coping with Pressure",
     "You are a 2nd year medical student. You have recently suffered a family bereavement. You feel that you cannot cope with your studies and would rather be with your family.",
     IMP_LEAD,
     [(37, "You will miss important teaching and your studies could suffer.", 3),
      (38, "The medical school should be made aware of your situation.", 0),
      (39, "Student support services are on-hand to help in such situations.", 0),
      (40, "You will be considered 'weak' if you seek help.", 3)]),
    ("SJA0031", "app", "Professionalism",
     "You are a 2nd year medical student in the GP surgery. A patient makes a comment about the shape of your nose as a joke which offends you.",
     APP_LEAD,
     [(41, "Shout at the patient.", 3),
      (42, "Discuss the comments with the GP after the consultation.", 0),
      (43, "Ask to be excused for the remainder of the consultation.", 1),
      (44, "Tell the patient that the comment was inappropriate and ask for an apology.", 2)]),
    ("SJA0041", "app", "Confidentiality",
     "You're a 5th year medical student on the radiology ward and catch sight of another student on the same placement placing some printed x-ray images into his backpack. He explains to you that he takes them back home to study in the evening, and always returns them the following day.",
     APP_LEAD,
     [(45, "Discuss the issue with the student directly.", 0),
      (46, "Report the student to the consultant radiologist.", 2),
      (47, "Explain to the other students on the placement his actions so that they are aware of the situation.", 3),
      (48, "Take some of the x-rays home too to study.", 3)]),
    ("SJA0035", "app", "Professionalism",
     "Lucy is a medical student working on the renal ward. One of the nurses approaches her, and says that she needs a doctor to come and sign a discharge summary so that one of the patients can go home. Lucy has already seen the patient today and knows the consultant has decided that the patient is to be discharged. The nurse tells Lucy that if the patient doesn't leave soon he will miss his transport and have to wait another night.",
     APP_LEAD,
     [(49, "Sign the paperwork so the patient can be discharged as it's what the consultant had planned.", 0),
      (50, "Explain that she is a medical student so she cannot sign a discharge summary.", 0),
      (51, "Find a junior doctor and ask them to sign the discharge summary urgently.", 1),
      (52, "Suggest that the nurse contacts one of the other doctors on the team.", 0)]),
    ("SJI0018", "imp", "Professionalism",
     "You are a foundation year 1 doctor. You feel that the registrar is making sexually inappropriate comments towards you.",
     "How important are the following when considering reporting the registrar's behaviour?",
     [(53, "It's not a problem as you have seen the registrar act this way towards others too.", 3),
      (54, "The seniority of the registrar.", 3),
      (55, "He is married to your consultant.", 3),
      (56, "There is no point mentioning this as it has only occurred three times.", 3)]),
    ("SJI0019", "imp", "Professionalism",
     "You hear a group of medical students discussing how incompetent the consultant is whilst waiting for clinic to begin. You realise that the patients may be able to hear them.",
     IMP_LEAD,
     [(57, "The patients are probably not bothered by what is being said.", 3),
      (58, "You feel the same way about the consultant.", 3),
      (59, "It is unprofessional to discuss colleagues in such a manner in public places.", 0),
      (60, "They are only medical students, no one is going to pay attention.", 3)]),
    ("SJI0030", "imp", "Professionalism",
     "John and Percy are medical students. At the start of first year, they notice that their peer Grace copies her essays and buys them from a central essay database.",
     IMP_LEAD,
     [(61, "They have evidence that Grace copies and buys her essays.", 0),
      (62, "How Grace would react if they reported this.", 3),
      (63, "This conduct is against the professionalism values of medical school.", 0)]),
    ("SJI0023", "imp", "Confidentiality",
     "You are a second year foundation doctor and have just finished your day which included treating a patient with a very rare condition. You all take the same train home, and you hear your colleagues discussing this fascinating case quite loudly. Suddenly, you also realise that the patient they are talking about is on the same train, which your colleagues have not realised.",
     IMP_LEAD,
     [(64, "Your colleagues should be reported to the hospital as soon as possible.", 3),
      (65, "It is unlikely that the patient will realise your colleagues are talking about them.", 3),
      (66, "The patient will be upset if they overhear your colleagues.", 0)]),
    ("SJI0026", "imp", "Confidentiality",
     "You are a GP who has diagnosed a patient, Hassan, with HIV. He contracted it on a night out after he had intercourse with a man he met at a club. Hassan is a muslim and has a wife and two kids and so he does not want to disclose to his wife that he has HIV.",
     IMP_LEAD,
     [(67, "Hassan is a muslim man and if this story gets out into the Islamic community he will be ostracized from his community.", 2),
      (68, "Hassan could transmit HIV to his wife without her knowledge.", 0),
      (69, "Hassan and his wife's marriage is breaking down and they no longer have intercourse.", 2)]),
]


def build():
    questions = []
    for code, scale, subtopic, scenario, lead, items in SCENARIOS:
        opts = APP if scale == "app" else IMP
        for num, statement, correct in items:
            questions.append({
                "number": str(num), "ref": f"{code} Q{num}", "subtopic": subtopic,
                "kind": "mcq",
                "passage": f"{scenario}\n\n{lead}",
                "stem": statement,
                "options": [{"text": t, "correct": (i == correct)} for i, t in enumerate(opts)],
            })
    questions.sort(key=lambda q: int(q["number"]))

    data = {"section": {"code": "SJT", "name": "Situational Judgement"}, "questions": questions}
    with open(os.path.join(HERE, "situational_judgement.json"), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    from collections import Counter
    by_sub = Counter(q["subtopic"] for q in questions)
    lines = ["# Situational Judgement - Imported Questions (Phase 2)\n",
             "Source: PMT Situational Judgement Question Pack 1 (placeholder demo content).\n",
             f"**Source questions:** {len(questions)}  |  **Practice items:** {len(questions)} "
             f"(1:1 - each rating item is one question)\n",
             "**By subtopic:** " + ", ".join(f"{k}: {v}" for k, v in sorted(by_sub.items())) + "\n"]
    last_ref = None
    for q in questions:
        code = q["ref"].split(" ")[0]
        if code != last_ref:
            lines.append(f"\n### Scenario {code}\n> {q['passage'].splitlines()[0]}\n")
            last_ref = code
        lines.append(f"\n**{q['number']}. ({q['ref']})** {q['stem']}\n")
        for opt in q["options"]:
            mark = "  ✅" if opt["correct"] else ""
            lines.append(f"- {opt['text']}{mark}")
        lines.append("")
    with open(os.path.join(ROOT, "imported_questions_review", "situational_judgement.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"Built {len(questions)} SJT items.")
    print("By subtopic:", dict(by_sub))


if __name__ == "__main__":
    build()
