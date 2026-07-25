"""Build Mock 2 JSON (per section) + review markdown — part 1: VR + DM.

source = "PMT-M2". VR is all True/False/Can't-tell. DM Yes/No-statement questions
are split into individual Yes/No items.
"""
import json
import os
from collections import Counter

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
SOURCE = "PMT-M2"
TFC = ["True", "False", "Can't tell"]

# ---------------- Verbal Reasoning (all True/False/Can't-tell) ----------------
VR_PASSAGES = {
    "VRTF0005": "The Pain Society (part of the IASP) defines chronic pain as longer than three months or past the expected time for healing after injury or disease. Chronic pain affects on average 14.1 million people in the UK. Back pain is the most recorded form of chronic pain and puts the most pressure on the NHS. Michael Von Korff states pain should be assessed in three dimensions: severity, duration and impact. There is a deficiency in medical professionals' knowledge of chronic pain, leading to under-diagnosis and under-treatment. Social media has been a vital platform for awareness, but there is a lack of champions for chronic pain awareness compared with cancer or Alzheimer's.",
    "VRTF0025": "President Trump became the first leader of the United States to set foot in North Korea, during a meeting with Kim Jong-un at the border with South Korea. Mr Kim led him a few yards into the North before they crossed back to greet President Moon. Teams of North Korean and US diplomats would resume denuclearisation negotiations, four months after Trump and Kim last met in Hanoi, Vietnam, which was cut short. Trump, 73, and Kim, 35, spoke warmly but did not break their deadlock. Talks will start within three weeks, Mike Pompeo said.",
    "VRTF0004": "The patient had diagnoses of vascular dementia and Alzheimer's disease, diagnosed three years prior. At first he did not exhibit obvious symptoms; mood normal, speech clear, hygiene good. On conversation his short-term memory was declining; he repeated himself unknowingly. His long-term memory remained clear. The patient also had eczema, particularly bad on his face; he would forget not to touch his face, worsening it. This underlines the importance of treating patients holistically. His wife had been instructed to remind him not to rub his face, which was tiring for her.",
    "VRTF0007": "Multiple Myeloma (MM) is a neoplastic disease defined by an accumulation of plasma cells in the bone marrow, accompanied by monoclonal protein in the serum or urine. MM is the second most common haematological cancer (10-15% of cases). Myeloma is the 18th most common cancer in the UK, accounting for around 2% of new cases; 15th most common in males (2%) and 17th in females (1%). In 2014 there were 5,501 new cases in the UK (56% men, 44% women). Rates are expected to rise by up to 10% by 2035.",
    "VRTF0008": "In 1992, Pedro and Josep Brugada from Spain encountered patients with similar ECG findings and ventricular tachycardia, later linked to a mutation in the SCN5A sodium-channel gene. They coined the condition Brugada syndrome (BrS). Its pathophysiological mechanism is controversial with few hypotheses. BrS presents in childhood or adulthood, mean age of sudden death being 40 years. Males are more likely to have it. BrS is thought responsible for 4-12% of unexpected sudden deaths. Before it was termed BrS, natives in South-eastern Asia used terms such as 'bangungut' (Philippines) and 'pokkuri' (Japan, 'sudden and unexpected ceased phenomena').",
    "VRTF0012": "There are two types of electric charge: positive (proton, in the nucleus) and negative (electrons, surrounding it). The movement of electrons is electricity. Components make it harder for current to flow; more light bulbs in series means more resistance (measured in Ohms). Safety steps: resistance wire may glow orange when heated. The laboratory mains power supply is designed to limit current to 1 amp and should contain a 'current overload' indicator; the power pack shows an indicator on current fluctuation. Turn off the power supply when changing wires to avoid electric shock. Record current and voltage readings quickly to avoid overheating.",
    "VRTF0014": "The housing market can impact consumer spending via interest and mortgage rates. During the UK recession (2007), the housing market collapsed; demand for new properties fell and prices edged down. Mortgage rates rose, forcing families to pay more, leading to repossessions and evictions. Households had less spare cash; some switched to cheaper supermarkets. Domestic travel declined as package holidays abroad were cheaper; families cut from 2-3 holidays to one. Inflation increased, further reducing disposable incomes and making it crucial for more than one family member to work. Furniture and carpet sales declined.",
    "VRTF0016": "The Andes are fold mountains formed some 65 million years ago, the longest range in the world at 7000km, running along the West Coast of South America. Average height 4,000m. Formed by the destructive plate boundary between the Nazca Plate (oceanic, denser) and the South American Plate (continental); the Nazca plate is subducted underneath. Mountain slopes are used for farming; potatoes are the staple crop and main food source. Terraces retain water and limit soil movement. Cash crops (soybeans, rice, cotton) grow in lower valleys. Llamas symbolise the Andes and are used as pack animals; alpacas are used for fine clothing.",
    "VRTF0018": "Prices of agricultural products fluctuate more than manufactured products, due to volatility in supply and price-inelastic demand and supply. Buffer stock is a store of a product added to during a surplus and released during a shortage — a government plan to stabilise prices. Price stability exists when average prices are constant or rising at a low predictable rate. Buffer stock schemes secure prices and prevent producers going out of business: in a surplus year the government buys and stores stock (keeping prices higher); in a shortage it sells from its buffer stock (reducing prices).",
    "VRTF0020": "John Bercow is drawing up plans that could force MPs to install video cameras in their offices to protect staff from unwanted sexual advances and bullying, before a report into the 'Pestminster' scandal of 2017. Researchers could be issued with GPS-tracked alarms; alcohol sale could be banned on the Parliamentary estate before 6pm. An inquiry by Gemma White QC examined complaints from the staff of more than 100 MPs. Dame Laura Cox ran a separate enquiry finding widespread bullying; Naomi Ellenbogen QC is investigating the House of Lords. Female MPs, making up only 28% of MPs, attracted nearly half of all complaints investigated.",
    "VRTF0021": "New allegations of sexual misconduct against Oxfam aid workers in African refugee camps will be treated as a priority, according to the charity watchdog. Oxfam opened an investigation into sex-for-aid accusations concerning a refugee camp in Ethiopia, as it tries to restore its reputation after the Haiti scandal. Oxfam made a serious incident report to the Charity Commission. Oxfam is not the only charity accused; findings related to 'a multitude of UN agencies and NGOs', with 'coercive transactional sex' the main form of exploitation. Many details were omitted to protect victim confidentiality. Lesley Agams, a former Oxfam country director, noted the Commission has no regulatory oversight over Oxfam International.",
}
# (code, [(statement, correct_index_into_TFC)...])
VR = [
    ("VRTF0005", [("Chronic pain is equally debilitating as compared to cancer.", 2), ("Knee pain is the commonest type of chronic pain.", 1),
                  ("The Pain Society are a separate body to the International Association for the Study of Pain.", 1), ("Everyone is likely to experience chronic pain at some point in their lifetime.", 2)]),
    ("VRTF0025", [("President Trump became the first American official to step into North Korea.", 2), ("Trump is more than 35 years older than Kim Jong Un.", 0),
                  ("President Moon crossed over into North Korea.", 2), ("Mr Kim was the first North Korean leader to cross into South Vietnam.", 2)]),
    ("VRTF0004", [("The patient's long-term memory was good.", 0), ("Dementia causes a decline in memory.", 0),
                  ("Patient had diagnoses of eczema, Alzheimer's disease and vascular dementia.", 0), ("The patient's wife also suffers from eczema.", 2)]),
    ("VRTF0007", [("Multiple myeloma is accompanied by the presence of monoclonal protein in urine only.", 1), ("Multiple myeloma is the 15th most common cancer in males and females.", 1),
                  ("5,501 new cases of multiple myeloma occur each year.", 2), ("By 2035, the rates of multiple myeloma are expected to rise by 10%.", 0)]),
    ("VRTF0008", [("'Pokkuri' in Japan means sudden and unexpected ceased phenomena.", 0), ("The Human Genome project has provided greater insight into the genetics of various syndromes.", 0),
                  ("Brugada Syndrome has one pathophysiological mechanism only.", 1), ("Pedro and Josep Brugada coined the condition (BrS).", 0)]),
    ("VRTF0012", [("Electrons do not carry a charge.", 1), ("Light bulbs make it harder for an electric current to flow.", 0),
                  ("All mains power supply contain a 'current overload' indicator.", 2), ("All individuals dealing with electricity take the advised safety steps.", 2)]),
    ("VRTF0014", [("The recession took place in 2007 worldwide.", 2), ("The recession meant that individuals did not have as much money to spend on the local economy.", 0),
                  ("Nobody went on holiday during the recession.", 1), ("All households required two members of the family to be working.", 1)]),
    ("VRTF0016", [("The South American plate subducts underneath the Nazca plate.", 1), ("No crops are grown on the gentle slopes of mountains.", 2),
                  ("All potatoes are used for personal consumption.", 2), ("Alpacas are the symbolic animal of the Andes.", 1)]),
    ("VRTF0018", [("Buffer stocks may be used to control the prices of agricultural products.", 0), ("Buffer stocks are sold when there is a shortage of wheat, for example.", 0),
                  ("Market prices rise during a surplus of buffer stocks.", 1), ("Coffee is a buffer stock.", 2)]),
    ("VRTF0020", [("No MPs currently have CCTV in their offices.", 2), ("Alcohol is currently sold in the parliamentary estate before 6pm.", 0),
                  ("Naomi Ellenbogen's report highlighted widespread bullying and harassment.", 1), ("Women make up 50% of MPs.", 1)]),
    ("VRTF0021", [("Oxfam currently do work in Haiti.", 2), ("The sexual exploitation sometimes includes the transfer of money.", 0),
                  ("Oxfam International are regulated by the Charity Commission.", 1), ("The full details of the allegations of child sexual exploitation have not been released.", 0)]),
]

# ---------------- Decision Making ----------------
# Standard MCQ: (ref, subtopic, stem, image_or_None, [(opt,correct)...])
DM_MCQ = [
    ("DMEA0002", "Evaluating Arguments", "To completely eliminate childhood obesity in the UK, should further taxes on high sugar foods (akin to the Soft Drinks Industry Levy) be introduced? Choose the strongest argument.", None,
     [("No. The confectionary industry is an important source of revenue and jobs, and impeding it will harm the economy.", 0),
      ("No. Whilst the levy was effective to a degree, obesity is a multifactorial issue often relating to socioeconomic discrepancies, and these taxes don't address that.", 1),
      ("Yes. It is the sole responsibility of governments to make sure their people are as healthy and fit as possible.", 0),
      ("Yes. This will reduce high sugar products bought and generate income for the government in taxes.", 0)]),
    ("DMFR0004", "Venn Diagrams", "The members of different after school clubs are depicted in the figure. Which statement is true?", "questions/m2_dm_q5_clubs.png",
     [("Volunteer club has more members in total than writer's society.", 0),
      ("There are more students who only do drama club than there are total students who do volunteer club.", 0),
      ("There are no students who are in all four clubs.", 1),
      ("There are two more students who do both writer's society and drama club than there are students who do writer's society, drama club and volunteer club.", 0)]),
    ("DMEA0012", "Evaluating Arguments", "Should England and Wales introduce minimum alcohol unit pricing to reduce alcohol consumption?", None,
     [("No, in Scotland, studies have shown no reduction in alcohol consumption after a similar law was passed.", 1),
      ("No, the state shouldn't involve itself in private affairs.", 0),
      ("Yes, excess alcohol consumption is a societal ill.", 0),
      ("Yes, higher prices will lead to people buying less alcohol.", 0)]),
    ("DMEA0014", "Evaluating Arguments", "Should the men's and women's football World Cup winners be given the same prize money to increase equality?", None,
     [("No, the men's tournament attracts more viewers.", 0),
      ("No, it would be a false equality as sponsorship would still be vastly different.", 1),
      ("Yes, the women deserve to be paid the same as the men.", 0),
      ("Yes, women's football is equally exciting.", 0)]),
    ("DMFR0007", "Venn Diagrams", "The diagram represents types of yoga taught in a studio. Due to schedule clashes, two types can never be taught by the same teacher in one week. Which two are they?", "questions/m2_dm_q10_yoga.png",
     [("Ashtanga yoga and yin yoga.", 0), ("Yin yoga and hatha yoga.", 1), ("Bikram yoga and ashtanga yoga.", 0), ("Hatha yoga and bikram yoga.", 0)]),
    ("DMSR0020", "Interpreting Information", "In a team of 5 the average number of yellow cards was 4. One member got seven, another had one. Of the remaining, Harry had one card fewer than Jane and one more than Steve. How many yellow cards did Harry have?", None,
     [("2", 0), ("3", 0), ("4", 1), ("5", 0)]),
    ("DMFR0017", "Logical Puzzles", "Six people in a history class: Ben, Anthony, Yash, Bilal, Rohan, Oscar. Yash beat one person. Only Bilal came ahead of Anthony. Ben and Rohan came in consecutive places. Which statement cannot be true?", None,
     [("Bilal scored highest.", 0), ("Rohan came third.", 0), ("Ben came third.", 0), ("Oscar came fifth.", 1)]),
    ("DMFR0013", "Venn Diagrams", "The same number of people owned a mountain bike only as have a mountain bike and a road bike. One more person has a hybrid only than only has a road bike. Three people have all three. Ten people have exactly two types of bike. Which of the following Venn diagrams (A-D) expresses this situation?", "questions/m2_dm_q13_venns.png",
     [("A", 1), ("B", 0), ("C", 0), ("D", 0)]),
    ("DMSR0009", "Interpreting Information", "A vending machine sells four crisp flavours. Prawn Cocktail costs more than Salt & Vinegar; Ready Salted costs less than Salt & Vinegar. Cheese & Onion costs the same as Prawn Cocktail but twice as much as Ready Salted. Which statement is true?", None,
     [("Cheese and onion will cost less than Salt & Vinegar.", 0),
      ("3 Prawn Cocktail packets will be cheaper than 2 Ready Salted and 1 Cheese and Onion.", 0),
      ("4 Salt & Vinegar packets cost more than 4 Ready Salted.", 0),
      ("6 Ready Salted and 3 Cheese and Onion will cost more than 5 Prawn Cocktail and 1 Salt & Vinegar.", 1)]),
    ("DMFR0014", "Venn Diagrams", "125 people were surveyed about subscriptions. 50 had Netflix. 60 had Prime Video. 25 had neither. How many had both?", None,
     [("5.", 0), ("10.", 1), ("15.", 0), ("20.", 0)]),
    ("DMSR0010", "Logical Puzzles", "Teresa has four pets — a frog, cat, puppy and horse — named Jeff, Monica, Aaron and Simon. Jeff is older than the cat. Monica is the largest. Simon is smaller than the dog. Aaron is less hairy than the cat and slower than the dog. What is the dog called?", None,
     [("Jeff", 1), ("Monica", 0), ("Simon", 0), ("Aaron", 0)]),
    ("DMSR0013", "Logical Puzzles", "A guesthouse has 5 single rooms; check-in 2pm, check-out 8am. Three people checked in Monday for two nights. A couple checked in Wednesday for two nights. Another couple checked in Thursday for four nights. Which is true?", None,
     [("The guest house was fully occupied on Wednesday and Thursday.", 0),
      ("The guest house was less than half occupied on Friday and Sunday.", 0),
      ("The guest house was fully occupied on Monday.", 0),
      ("The guest house was more than half occupied on Saturday.", 1)]),
    ("DMSR0017", "Logical Puzzles", "Marie, Rachel, Carrie and Sara have roles: Registration, matchmaking, publicity, follow up. Hours (ascending): 15, 25, 40, 45. Rachel worked matchmaking or publicity. Sara works 5 hours more than Carrie and Marie combined. The publicity person worked the most hours. Marie worked 10 hours more than Carrie on registration. Which cannot be true?", None,
     [("Sara worked 45 hours on publicity this past week.", 0),
      ("Marie worked on registration for 25 hours.", 0),
      ("Rachel worked 40 hours on publicity.", 1),
      ("Carrie and Marie combined worked the same number of hours as Rachel this week.", 0)]),
    ("DMSR0018", "Logical Puzzles", "Five fans from Wigan, Preston, Lancaster, York, Manchester wore scarves and gloves of different colours (teal, turquoise, maroon, burgundy, violet). No two fans wore the same colour. Wigan wore a teal scarf; her gloves were neither maroon nor violet. Lancaster wore turquoise gloves. Preston wore a maroon scarf; his gloves matched Wigan's scarf colour. York's scarf colour matched Manchester's gloves. Which must be true?", None,
     [("The Manchester person is wearing teal gloves.", 0),
      ("The Wigan fan is wearing burgundy gloves.", 1),
      ("The Preston person is wearing a teal scarf.", 0),
      ("The York person is wearing a turquoise scarf.", 0)]),
    ("DMFR0021", "Logical Puzzles", "H5T do cleaning, events, security and probation, one each in towns W, X, Y, Z (in England, Scotland, Wales, Northern Ireland). Cleaning is not in X nor Scotland. Events work is in Wales; security is in town W. Town Z is in Scotland; town Y is in Northern Ireland. Which must be true?", None,
     [("The cleaning job is in town Z.", 0), ("The cleaning job is in Northern Ireland.", 1),
      ("The probation job is in town Y.", 0), ("The probation job is in Northern Ireland.", 0)]),
]

# Yes/No: (ref, scenario, [(letter, statement, is_yes)...])
DM_YESNO = [
    ("DMDR0006", "Penguins and chicken are birds. Neither penguins nor chicken fly but they do lay eggs. Fish lay eggs but are not birds.",
     [("A", "Only birds lay eggs.", 0), ("B", "Most birds can fly.", 0), ("C", "All birds lay eggs.", 0),
      ("D", "If something can fly and lay eggs, it is a bird.", 0), ("E", "If a bird doesn't fly, it cannot be a chicken.", 0)]),
    ("DMDR0007", "All tennis balls are bouncy. All cricket balls are hard. This ball is either a tennis ball or a cricket ball.",
     [("A", "This ball is bouncy or a cricket ball.", 1), ("B", "All balls are bouncy or hard.", 0), ("C", "If this ball is bouncy, it cannot be a tennis ball.", 0),
      ("D", "This ball is bouncy or hard.", 1), ("E", "Some cricket balls are hard.", 1)]),
    ("DMDR0008", "Most serious cyclists own more than one bike. Some cyclists use cleats. All Mamils (middle-aged men in lycra) own lycra.",
     [("A", "Some Mamils use cleats.", 0), ("B", "Some serious cyclists own one bike.", 1), ("C", "Most serious cyclists use cleats.", 0),
      ("D", "Some Mamils own Lycra.", 1), ("E", "Some serious cyclists use cleats.", 0)]),
    ("DMSR0007", "Lydia's pencil case has 25 pencils in 5 colours. She has 5 Red pencils (the only odd number). She has fewer Green than Red. She has the same number of Pink and Orange. She has more Orange than Green and Blue combined.",
     [("A", "Red is the most common colour in the case.", 0), ("B", "There are 8 Pink pencils in the case.", 1),
      ("C", "There are equal numbers of Green and Blue pencils in the case.", 1), ("D", "There are fewer Orange pencils than Red pencils in the case.", 0)]),
    ("DMDR0009", "Jenna is a civil servant. All civil servants are wealthy. All wealthy people pay higher rate tax.",
     [("A", "Jenna pays higher rate tax.", 1), ("B", "Most civil servants pay higher rate tax.", 1), ("C", "No civil servants are not wealthy.", 1),
      ("D", "Either a person is a civil servant, or they are not wealthy.", 0), ("E", "All higher rate taxpayers are wealthy.", 0)]),
    ("DMDR0013", "All people in the class, except for Mike, like apples. More than one person likes bananas.",
     [("A", "Mike likes bananas.", 0), ("B", "If a person in the class dislikes apples, it must be Mike.", 1), ("C", "If a person in the class dislikes bananas, they must like apples.", 0),
      ("D", "If only two people in the class like bananas, one must be Mike.", 0), ("E", "Someone in the class likes both apples and bananas.", 1)]),
    ("DMDR0014", "Harry has a box of sweet and sour chews. Some of the sweet chews are blue but the rest of the chews are yellow.",
     [("A", "All the sour chews are yellow.", 1), ("B", "All the chews are yellow or blue.", 1), ("C", "Some of the sweet chews are yellow.", 1),
      ("D", "Some of the yellow chews are sour.", 1), ("E", "None of the blue sweets are sour.", 1)]),
    ("DMDR0016", "All college students wear suits apart from BTEC sport pupils who wear tracksuits. Boys must wear a collared shirt and tie; girls also have the option of a dress in summer.",
     [("A", "A student is wearing a dress so it must be summer.", 1), ("B", "A student is not wearing a tie so they must be a female pupil.", 0), ("C", "A pupil is wearing a tie so they must be male.", 0),
      ("D", "A boy is wearing jeans and a T-shirt in a lesson so they cannot be a college student.", 1), ("E", "All boys wear collared shirts in winter.", 0)]),
    ("DMDR0022", "Set point weight theory: the body's optimal weight range is largely determined by genetics; attempts to go below or above are combated by changes in metabolism and appetite. The set point can be raised by yo-yo dieting or lowered by regular exercise.",
     [("A", "This theory makes BMI less of an authority on someone's state of health, because they may have a natural set point that gives them a BMI above the healthy range.", 1),
      ("B", "It is impossible to go above or below your body's set point weight range.", 0),
      ("C", "Dieting may give results in the short term but is ineffective in the long term at lowering body weight.", 1),
      ("D", "Someone who attempts to go below their set point will experience an increase in appetite and a decrease in metabolic rate.", 1),
      ("E", "If someone believes in set point weight theory, then they most likely have had an eating disorder.", 0)]),
    ("DMDR0017", "All polar bears are white. All seals are grey. This animal is a seal or a polar bear.",
     [("A", "If an animal is grey, it is a seal.", 0), ("B", "This animal is grey or a polar bear.", 1), ("C", "No seal is white.", 1),
      ("D", "Some polar bears are white.", 1), ("E", "This animal is white or a polar bear.", 0)]),
    ("DMDR0018", "The main library is open to all three types of students (medical, science, humanities). Only medics can use the medical library. The science library is not restricted to science students, but humanities students cannot use it.",
     [("A", "If a student is using the medical library, they neither study science nor the humanities.", 1), ("B", "Humanities students can only use the main library.", 1),
      ("C", "If a student is studying in the science library, then they must study science.", 0), ("D", "Medical students can use the science library.", 1),
      ("E", "Science students can use all three libraries.", 0)]),
    ("DMDR0019", "Amongst the talent show entrants in the musical category this year, none were male singers.",
     [("A", "The only people to enter the talent show were women.", 0), ("B", "If someone sang in the musical category, they must have been female.", 1),
      ("C", "The only people competing in the talent show this year were female singers.", 0), ("D", "The musical category of the talent show was dominated by females this year.", 0),
      ("E", "A female competing in the talent show must have been a singer.", 0)]),
    ("DMDR0020", "Among all married people who have an affair, most do not disclose the affair to their partner unless they are found out or they wish to inflict emotional distress.",
     [("A", "All people who are discovered having an affair by their partner will disclose it.", 0),
      ("B", "If a married person having an affair does not disclose it, they do not wish to inflict emotional distress on their partner.", 0),
      ("C", "A person who discloses their affair, who does not wish to inflict emotional distress, must have been found out.", 1),
      ("D", "The partner on the receiving end of the confession will be emotionally distressed.", 0),
      ("E", "More married people will keep quiet about having an affair than will confess to it.", 1)]),
    ("DMDR0023", "At a concert, all the singers have costumes. Some singers can dance. None of the backup dancers sing in the concert and they are wearing all black.",
     [("A", "All the singers dance.", 0), ("B", "If a performer is wearing all black, they do not sing.", 1), ("C", "If someone is dancing, then they are not a singer.", 0),
      ("D", "If a performer is wearing a costume, then they can dance and sing.", 0), ("E", "Outside of the concert, some of the backup dancers might sing.", 1)]),
]

DM_ORDER = ["DMDR0006", "DMDR0007", "DMEA0002", "DMDR0008", "DMFR0004", "DMEA0012", "DMSR0007",
            "DMEA0014", "DMDR0009", "DMFR0007", "DMSR0020", "DMFR0017", "DMFR0013", "DMSR0009",
            "DMDR0013", "DMDR0014", "DMFR0014", "DMDR0016", "DMDR0022", "DMDR0017", "DMDR0018",
            "DMDR0019", "DMSR0010", "DMSR0013", "DMSR0017", "DMSR0018", "DMFR0021", "DMDR0020", "DMDR0023"]


def build():
    # VR
    vr_q = []
    n = 0
    for code, items in VR:
        for statement, ci in items:
            n += 1
            vr_q.append({"number": str(n), "ref": f"M2 {code} Q{n}", "subtopic": "Inference (True/False/Can't Tell)",
                         "kind": "tf", "passage": VR_PASSAGES[code], "stem": statement,
                         "options": [{"text": t, "correct": (i == ci)} for i, t in enumerate(TFC)]})
    _write("mock2_vr.json", {"section": {"code": "VR", "name": "Verbal Reasoning", "source": SOURCE}, "questions": vr_q})

    # DM
    dm_q = []
    n = 0
    mcq_map = {c[0]: c for c in DM_MCQ}
    yn_map = {y[0]: y for y in DM_YESNO}
    for code in DM_ORDER:
        n += 1
        if code in mcq_map:
            _, sub, stem, image, opts = mcq_map[code]
            q = {"number": str(n), "ref": f"M2 {code} Q{n}", "subtopic": sub, "kind": "mcq",
                 "stem": stem, "options": [{"text": t, "correct": bool(c)} for t, c in opts]}
            if image:
                q["image"] = image
            dm_q.append(q)
        else:
            _, scenario, statements = yn_map[code]
            for letter, statement, is_yes in statements:
                dm_q.append({"number": f"{n}{letter}", "ref": f"M2 {code} Q{n}{letter}", "subtopic": "Syllogisms",
                             "kind": "mcq", "passage": scenario,
                             "stem": f'"{statement}"  —  Does this follow from the information above?',
                             "options": [{"text": "Yes", "correct": bool(is_yes)}, {"text": "No", "correct": not bool(is_yes)}]})
    _write("mock2_dm.json", {"section": {"code": "DM", "name": "Decision Making", "source": SOURCE}, "questions": dm_q})

    # Review markdown
    lines = ["# Mock 2 - Imported Questions (part 1: VR + DM)\n",
             "Source: PMT UCAT Mock Examination 2 (placeholder demo content, tagged PMT-M2).\n",
             f"**Verbal Reasoning:** {len(vr_q)} items (all True/False/Can't-tell, 11 passages)",
             f"**Decision Making:** {len(dm_q)} items ({len(DM_MCQ)} MCQ + {len(dm_q)-len(DM_MCQ)} Yes/No items)\n",
             "\n---\n## Verbal Reasoning\n"]
    for q in vr_q:
        lines.append(f"\n**{q['number']}. ({q['ref'].split()[1]})** {q['stem']}")
        for opt in q["options"]:
            lines.append(f"- {opt['text']}{'  ✅' if opt['correct'] else ''}")
    lines.append("\n---\n## Decision Making\n")
    for q in dm_q:
        lines.append(f"\n**{q['number']}.** {q['stem']}{'  `[image]`' if q.get('image') else ''}")
        for opt in q["options"]:
            lines.append(f"- {opt['text']}{'  ✅' if opt['correct'] else ''}")
    with open(os.path.join(ROOT, "imported_questions_review", "mock2.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"VR items: {len(vr_q)} | DM items: {len(dm_q)}")
    print("DM by subtopic:", dict(Counter(q["subtopic"] for q in dm_q)))


def _write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    build()
