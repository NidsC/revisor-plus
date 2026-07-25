"""Build the Decision Making JSON + review markdown from transcribed PMT content.

Standard MCQs are stored as-is. Yes/No-statement questions are split into one
Yes/No item per statement (the single-answer model can't hold multi-statement).
"""
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)

# ---- Standard multiple-choice questions -------------------------------------
# dict: num, ref, subtopic, stem, (passage), (image), (explanation), options[(text,correct)]
STANDARD = [
    dict(num=1, ref="DMSR0011", subtopic="Logical Puzzles",
         stem="8 motorbikers are in a race. Astrid wins the race, but Estelle was just behind. Cerys couldn't beat Dominic. Fatima and Gosia couldn't beat Harry, but they could beat Beatrice. Dominic just lost to Beatrice. Where does Cerys come in the race?",
         options=[("4th", 0), ("5th", 0), ("6th", 0), ("7th", 0), ("8th", 1)]),
    dict(num=2, ref="DMFR0018", subtopic="Venn Diagrams", image="questions/dm_q2_venn.png",
         stem="A series of foods have the allergens shown in the diagram. A person is gluten-free and dairy-free only. Which letter represents foods she can eat?",
         options=[("A", 0), ("B", 0), ("C", 1), ("D", 0)]),
    dict(num=3, ref="DMEA0005", subtopic="Evaluating Arguments",
         passage="Children who are conceived through donated eggs or donated sperm should have a right to know who their biological parents are and should be supplied with their contact details, given that those details are available.",
         stem="Which of the following is the strongest argument in response to the statement above?",
         explanation="A is the strongest argument: it makes the case for the human right to truth but also acknowledges it will not necessarily make the person happier. B assumes all donors act for financial reward. C is weaker because the child's right to their origin outweighs placating non-biological parents. D is weaker because nothing states the children have a right to financial or emotional assistance.",
         options=[("Yes. Although it may not necessarily increase their happiness, human beings have a right to the truth surrounding their identity and origin.", 1),
                  ("Yes. This will force people to think more carefully about donating their gametes, and not just do it for the immediate financial reward.", 0),
                  ("No. It is not fair on the 'non-biological' parents who have raised the child and have invested both emotionally and financially into their up bringing.", 0),
                  ("No. This might deter potential egg or sperm donors if they think that in the future their genetic offspring might contact them for financial or emotional assistance.", 0)]),
    dict(num=5, ref="DMSR0019", subtopic="Interpreting Information",
         stem="There are 59 club members who are either juniors or seniors. There are 5 more male than female members. 20 of the 25 juniors are male. How many female seniors are there?",
         explanation="59 - 5 = 54. 54/2 = 27, so there are 27 females and 32 males. 27 - 5 = 22 female seniors.",
         options=[("22", 1), ("24", 0), ("30", 0), ("32", 0), ("34", 0)]),
    dict(num=6, ref="DMFR0015", subtopic="Logical Puzzles",
         stem="Ed Woodward is looking at his transfer target list. Mr Dybala, Mr Maguire, Mr Fernando, Mr James and Mr Bale are the five names on the list. Mr Bale is just in front of Mr Maguire and just behind Mr James. Mr Dybala is fourth in the list. Which of the following cannot be true?",
         explanation="James, Bale and Maguire must be in that order. Since Mr Dybala is fourth, they occupy first, second and third, so Mr Maguire is third (not fifth) and Mr Fernando is fifth.",
         options=[("Mr Bale is in second.", 0), ("Mr James is top of the list.", 0),
                  ("Mr Maguire is fifth in the list.", 1), ("Mr Fernando is fifth in the list.", 0)]),
    dict(num=7, ref="DMSR0012", subtopic="Logical Puzzles",
         stem="A group of young people go on an activity holiday in Wales. All of the girls liked horse-riding while most of the boys didn't enjoy speed walking. All members used the all-inclusive restaurant each evening but some opted out of the all-inclusive bar. Which of the following statements is true?",
         options=[("None of the girls used the all-inclusive bar.", 0), ("None of the boys enjoyed horse-riding.", 0),
                  ("All of the boys used the all-inclusive restaurant.", 1), ("Most of the boys didn't go speed walking.", 0)]),
    dict(num=8, ref="DMFR0006", subtopic="Venn Diagrams", image="questions/dm_q8_skating.png",
         stem="The diagram shows the different types of figure skating events at the Olympics and the number of individual skaters competing in each event. The only mutually exclusive events are men's singles and ladies' singles. Competitors can take part in all other events otherwise. How many pairs are there in the pair skating event in total?",
         explanation="Total number of individuals in the pentagon (pair skating) = 42. 42 / 2 = 21 pairs.",
         options=[("8 pairs", 0), ("14 pairs", 0), ("21 pairs", 1), ("32 pairs", 0)]),
    dict(num=9, ref="DMSR0005", subtopic="Interpreting Information",
         stem="Meadowbank Care Home looks after elderly people aged 75 or older. Lola turned 81 in 2015 and 2 years later came to Meadowbank where her friend Harriet, who is 1 year her junior, had already been a resident for 4 years. In 2017, James joined Meadowbank. Wendy joined Meadowbank sometime between turning 75 in 2014 and James joining in 2017. Which of these statements MUST be true?",
         explanation="Lola joined in 2017; Harriet had been there 4 years, so joined in 2013. Harriet is one year younger than Lola (80 in 2015), so in 2013 she was 78 - two years before turning eighty.",
         options=[("Wendy is older than Harriet.", 0), ("Harriet joined Meadowbank two years before she turned eighty.", 1),
                  ("James is younger than Wendy.", 0), ("Wendy joined after Lola did.", 0)]),
    dict(num=10, ref="DMEA0003", subtopic="Evaluating Arguments",
         stem="After 40 years of eating meat, Thomas reads a study which states that a vegan diet is associated with a lower risk of getting cancer, and so he takes up veganism. Will taking up veganism definitively lower Thomas' risk of getting cancer?",
         explanation="C is strongest: association is not causation, and the lower rates could be due to other lifestyle factors. A over-extrapolates from smoked foods/gastric cancer; B assumes a vegan diet means eating lots of fruit and vegetables; D wrongly assumes it is too late at 40.",
         options=[("Yes. There have been studies which demonstrate a strong correlation between smoked meats and smoked fish and gastric cancer.", 0),
                  ("Yes. Diet is one of the biggest factors which can contribute to an individual's risk of getting cancer and so consuming more fruits and vegetables will lower this risk.", 0),
                  ("No. The study only stated that veganism is associated with lower rates of cancer, and this association could be due to other lifestyle factors associated with a vegan diet.", 1),
                  ("No. After 40 years of consuming meat and animal products, it is too late to reverse the damage that this would have caused.", 0)]),
    dict(num=12, ref="DMEA0008", subtopic="Evaluating Arguments",
         passage="In order to encourage individuals to develop healthy lifestyle habits that will last throughout their life, cooking lessons should be made compulsory in schools and there should be more time for sports and physical activity.",
         stem="Choose the strongest argument from the statements below.",
         explanation="B is strongest: it directly addresses the impact of learning habits at a younger age on developing healthy lifestyles. A discusses employment; C discusses academics; D discusses short-term financial burden - none directly on point.",
         options=[("Yes. Adding compulsory cooking lessons and a greater emphasis on games means that there will be more teaching jobs required and so it will create greater employment opportunity.", 0),
                  ("Yes. While it is possible to develop new habits as an adult, learning them at a younger age means that they are more likely to stick.", 1),
                  ("No. Teaching cooking and putting more time for sports in the school timetable will detract from more academic pursuits.", 0),
                  ("No. It is not an efficient use of resources for the government to be adding these additional components into school curriculums.", 0)]),
    dict(num=13, ref="DMFR0005", subtopic="Logical Puzzles",
         passage="Four women are seated next to one another in a row (seats 1-4). One has brunette hair, one blonde, one red and one grey. The names, in no particular order, are Sandra, Grace, Beatrice and Jessica. Beatrice is sat next to both Grace and Sandra. Jessica is in seat number 4. The women at either end of the row have blonde hair and red hair. Sandra has grey hair. Grace is only sat next to one other person. The woman in seat number 2 is brunette.",
         stem="Which of the following combinations MUST be true?",
         explanation="Beatrice must be in seat 2 (brunette). Seats 1/4 are blonde/red; seats 2/3 are grey/brunette. Sandra (grey) is in seat 3; Grace in seat 1 (blonde); Jessica in seat 4 (red). So Beatrice - Brunette must be true.",
         options=[("Sandra - Red", 0), ("Beatrice - Brunette", 1), ("Jessica - Blonde", 0), ("Grace - Grey", 0)]),
    dict(num=14, ref="DMEA0013", subtopic="Evaluating Arguments",
         stem="Should fines for littering be increased to clean up our public spaces?",
         explanation="A is strongest: it addresses both aspects of the question and provides evidence to back it up.",
         options=[("Yes, a study in Malta which has fines of up to €2000 (around 50 times the current UK fine) showed a reduction in littering by greater than 50%.", 1),
                  ("Yes, it could pay for more public bins.", 0),
                  ("No, the real issue is a lack of available bins.", 0),
                  ("No, it's a nuisance but many couldn't afford a higher fine.", 0)]),
    dict(num=16, ref="DMFR0016", subtopic="Logical Puzzles",
         stem="In a school race, five runners took part: Harri, Jamie, Nathan, Piri and Sam. Harri was two places ahead of Sam, whose name was only next to one other on the results board. Nathan and Piri were separated by a photo finish. The top three appeared on the podium. Which of the following MUST be true?",
         explanation="Sam is last (5th) and Harri is 3rd. Nathan and Piri took the only consecutive places (1st/2nd, split by a photo finish). That leaves 4th for Jamie.",
         options=[("Nathan came first.", 0), ("Piri came second.", 0), ("Jamie came fourth.", 1), ("Harri was not on the podium.", 0)]),
    dict(num=19, ref="DMSR0016", subtopic="Logical Puzzles",
         stem="8 cars are in a race. Car A wins. Car E wasn't far behind. Car C could not beat Car D. Car F and Car G couldn't beat Car H, but they did beat Car B. Car D just lost out to Car B. What place did Car B come?",
         explanation="Order: 1. Car A, 2. Car E, 3. Car H, 4. Car F/G, 5. Car F/G, 6. Car B, 7. Car D, 8. Car C. Car B came 6th.",
         options=[("4th", 0), ("5th", 0), ("6th", 1), ("7th", 0), ("8th", 0)]),
    dict(num=20, ref="DMEA0017", subtopic="Evaluating Arguments",
         stem="Should there be a minimum body mass index (BMI) for weight reduction surgery on the NHS?",
         options=[("Yes, obesity is one of the leading killers and any measure should be taken to stop it.", 0),
                  ("No. That is discrimination.", 0),
                  ("Yes. The NHS doesn't have funds to provide weight reduction surgery to all overweight patients.", 1),
                  ("Yes. Otherwise patients with a poor body image may opt for it which could be dangerous.", 0)]),
    dict(num=21, ref="DMDR0025", subtopic="Logical Puzzles",
         stem="There are 4 pupils from a primary school: John, Tim, Jess and Peppa. They like 4 different colours. They all drew different objects with their favourite colours. John drew a boat and Peppa's object was yellow. There was a purple octopus. Tim does not like blue nor flowers. Jess drew the house. Which of the following must be true?",
         options=[("Jess' favourite colour is blue.", 0), ("John's drawing is blue.", 0),
                  ("The house is yellow.", 0), ("Tim drew the octopus.", 1)]),
    dict(num=22, ref="DMFR0025", subtopic="Venn Diagrams", image="questions/dm_q22_languages.png",
         stem="The diagram represents a population of 150 people and the languages they speak. How many people speak two languages?",
         explanation="The people speaking exactly two languages lie in the regions where exactly two shapes overlap; these sum to 45.",
         options=[("25", 0), ("34", 0), ("38", 0), ("45", 1)]),
    dict(num=24, ref="DMFR0020", subtopic="Interpreting Information", image="questions/dm_q24_shapes.png",
         stem="Consider the equations shown. How many squares is one diamond equal to?",
         explanation="Let circle=C, triangle=T, diamond=D, square=S. 2C=3T, D=S+T, C=D+S. Substituting gives 2(D+S)=3(D-S), so 5S=D: one diamond equals 5 squares.",
         options=[("6", 0), ("5", 1), ("4", 0), ("3", 0)]),
    dict(num=25, ref="DMSR0015", subtopic="Logical Puzzles",
         stem="8 friends are running in a race. Ben wins the race, but Sam was not far behind. Joseph could not beat Sarah. Sophie and Ryan could not beat Christina, but they could beat Tom. Sarah just lost out to Tom. Where does Tom come in the race?",
         explanation="Ben 1st, Sam 2nd. Sophie and Ryan lose to Christina and beat Tom; Joseph loses to Sarah. So Joseph 8th, Sarah 7th, Tom 6th.",
         options=[("4th", 0), ("5th", 0), ("6th", 1), ("7th", 0), ("8th", 0)]),
    dict(num=26, ref="DMEA0016", subtopic="Evaluating Arguments",
         stem="Should doctors who are against abortion have to perform them?",
         options=[("Yes, it is the patient's decision what happens to her body, not the doctor's.", 0),
                  ("Yes. Not performing the abortion may mean the patient has to wait for treatment.", 0),
                  ("No. It may be against the doctor's religious or ethical beliefs.", 1),
                  ("No. Doctors must do no harm and abortion is murder.", 0)]),
    dict(num=27, ref="DMSR0025", subtopic="Interpreting Information",
         stem="6 friends - Terry, Phil, Simon, Elaine, Jemima and Jess - go out for lunch for Phil's birthday one afternoon. On average they spent £20 each. Simon didn't bring any money so Elaine had to pay £50 to cover her and Simon. Phil didn't pay anything because it was his birthday. Terry didn't eat much so only paid 75% of the average. Jemima spent 120% of what Jess did. How much did Jemima spend?",
         options=[("£40", 0), ("£30", 1), ("£20", 0), ("£35", 0), ("£25", 0)]),
    dict(num=29, ref="DMFR0024", subtopic="Venn Diagrams", image="questions/dm_q29_flowers.png",
         stem="The diagram represents the different types of flower that can be found in 100 gardens in houses located in the same town. All gardens have at least one type of flower. Which of the following statements is true?",
         explanation="Roses total = 30 + X + Y, daisies total = 36 + X + Y, so there are always more daisies than roses regardless of X and Y. (A false: 48 have exactly one type; B false: 0 have all four; D false: 10 have roses and daisies but no tulips.)",
         options=[("There are 50 gardens with exactly one type of flower.", 0),
                  ("It cannot be determined how many gardens have all four types of flower.", 0),
                  ("Daisies are more commonly grown than roses.", 1),
                  ("12 gardens have roses and daisies but no tulips.", 0)]),
]

# ---- Yes/No-statement questions (split into one item per statement) ----------
# scenario + statements[(letter, text, is_yes)]
YESNO = [
    dict(num=4, ref="DMDR0034", subtopic="Syllogisms",
         scenario="All microorganisms which replicate by infecting a host cell are viruses. Those that replicate in the cytoplasm tend to be RNA viruses, while those that replicate in the nucleus tend to be DNA viruses although this is not always true.",
         statements=[("A", "You cannot always determine the type of virus by where it replicates in the cell.", 1),
                     ("B", "Viruses cannot replicate their genetic material without infecting a host cell.", 1),
                     ("C", "Not all microorganisms replicate intracellularly.", 1),
                     ("D", "A virus replicates its genetic material in the nucleus of a cell. It must be an RNA virus.", 0),
                     ("E", "A microorganism does not require a host to replicate. It must be a bacteria.", 0)]),
    dict(num=11, ref="DMDR0038", subtopic="Syllogisms",
         scenario="During the weekdays, there are 3 direct flights from London Heathrow to Tegel Airport, Berlin. The flights depart at 06:30, 10:30 and 19:00, with the journey taking two and a half hours from take-off to landing. For one adult passenger flying economy class the cost of the ticket is between £120 to £160, depending on which flight is taken.",
         statements=[("A", "For an adult flying economy class, the maximum amount for a ticket is £160.", 1),
                     ("B", "There are 4 flights from London to Berlin bank holiday mondays.", 0),
                     ("C", "The earliest flight from London to Berlin is at 06:00.", 0),
                     ("D", "Some tickets from London Heathrow to Tegel Airport, Berlin are £120.", 1)]),
    dict(num=15, ref="DMDR0012", subtopic="Syllogisms",
         scenario="In this country not all politicians are male. However all politicians are honest except for Tom and Tim.",
         statements=[("A", "Some male politicians are honest.", 0),
                     ("B", "If Harry is a politician in this country, he is honest.", 1),
                     ("C", "Not all honest politicians in this country are male.", 0),
                     ("D", "If a politician is honest, it isn't Tom or Tim.", 1),
                     ("E", "All politicians except Tom and Tim are honest.", 0)]),
    dict(num=17, ref="DMDR0043", subtopic="Syllogisms",
         scenario="Everyone in a certain house likes ketchup, apart from Yewande. More than one person likes brown sauce.",
         statements=[("A", "At least one person likes both ketchup and brown sauce.", 1),
                     ("B", "If a person in the house dislikes ketchup, they must be Yewande.", 1),
                     ("C", "Yewande likes brown sauce.", 0),
                     ("D", "If a person likes brown sauce and ketchup, they must not be Yewande.", 1)]),
    dict(num=18, ref="DMDR0021", subtopic="Syllogisms",
         scenario="ELRM is a conglomerate corporation made of three smaller companies, X, Y and Z. Everything produced by company X is food or drink related. 75% of company Y's products are food or drink related. Company Z does not produce anything food or drink related.",
         statements=[("A", "Angie works for a company that produces food or drink related products, therefore she can't work for company Z.", 1),
                     ("B", "Allie works for 2 different companies within ELRM, and spends no time dealing with food or drink related products. Therefore she must work for company Y and company Z.", 1),
                     ("C", "Company Y will always produce less total food or drink related products compared with company X.", 0),
                     ("D", "Jenny is CEO of one of the smaller companies and spends time dealing with food or drink related products. She must be CEO of company X.", 0),
                     ("E", "Most of ELRM's products are food and drink related.", 0)]),
    dict(num=23, ref="DMDR0024", subtopic="Syllogisms",
         scenario="Mrs Pettigrew is in charge of the year 5 school trip. The children are divided into two groups: boys and girls. All the boys had an apple. Some boys and some girls had a banana. All children had a cheese sandwich. Yoghurts were only eaten by girls.",
         statements=[("A", "Girls had a cheese sandwich and yoghurt.", 1),
                     ("B", "The children ate cheese and yoghurts.", 0),
                     ("C", "All the boys had an orange.", 0),
                     ("D", "Some boys had an apple and banana.", 1),
                     ("E", "All boys had a cheese sandwich and an apple.", 1)]),
    dict(num=28, ref="DMDR0026", subtopic="Syllogisms",
         scenario="I like cats and reptiles, but I dislike dogs. I like snakes, but only if they are pythons. I am allergic to certain types of cats and dogs. My sister brought a new pet which she says I will like.",
         statements=[("A", "The new pet might be a lizard.", 1),
                     ("B", "I will be allergic to the new pet.", 0),
                     ("C", "If the new pet is a reptile I will like it.", 0),
                     ("D", "The new pet will not bark.", 1),
                     ("E", "The new pet will be an insect.", 0)]),
]


def build():
    questions = []
    for q in STANDARD:
        item = {"number": str(q["num"]), "ref": q["ref"], "subtopic": q["subtopic"],
                "kind": "mcq", "stem": q["stem"],
                "options": [{"text": t, "correct": bool(c)} for t, c in q["options"]]}
        if q.get("passage"):
            item["passage"] = q["passage"]
        if q.get("image"):
            item["image"] = q["image"]
        if q.get("explanation"):
            item["explanation"] = q["explanation"]
        questions.append(item)

    for q in YESNO:
        for letter, text, is_yes in q["statements"]:
            questions.append({
                "number": f"{q['num']}{letter}", "ref": f"{q['ref']}-{letter}",
                "subtopic": q["subtopic"], "kind": "mcq",
                "passage": q["scenario"],
                "stem": f'"{text}"  —  Does this follow from the information above?',
                "options": [{"text": "Yes", "correct": bool(is_yes)},
                            {"text": "No", "correct": not bool(is_yes)}],
            })

    # sort by numeric part then letter for stable ordering
    def key(it):
        n = it["number"]
        digits = "".join(c for c in n if c.isdigit())
        suffix = "".join(c for c in n if not c.isdigit())
        return (int(digits), suffix)
    questions.sort(key=key)

    data = {"section": {"code": "DM", "name": "Decision Making"}, "questions": questions}
    with open(os.path.join(HERE, "decision_making.json"), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # review markdown
    from collections import Counter
    by_sub = Counter(q["subtopic"] for q in questions)
    lines = ["# Decision Making - Imported Questions (Phase 1 complete)\n",
             f"Source: PMT Decision Making Question Pack 1 (placeholder demo content).",
             f"\n**Source questions:** 29  |  **Practice items created:** {len(questions)} "
             f"(22 standard MCQ + {len(questions)-22} Yes/No items from 7 statement questions)\n",
             "**By subtopic:** " + ", ".join(f"{k}: {v}" for k, v in sorted(by_sub.items())) + "\n"]
    for q in questions:
        img = "  `[has image]`" if q.get("image") else ""
        lines.append(f"\n## {q['number']}. [{q['subtopic']}]  ({q['ref']}){img}\n")
        if q.get("passage"):
            lines.append(f"> {q['passage']}\n")
        lines.append(f"**Q:** {q['stem']}\n")
        for opt in q["options"]:
            mark = "  ✅ **(correct)**" if opt["correct"] else ""
            lines.append(f"- {opt['text']}{mark}")
        if q.get("explanation"):
            lines.append(f"\n*Explanation:* {q['explanation']}")
        lines.append("")
    os.makedirs(os.path.join(ROOT, "imported_questions_review"), exist_ok=True)
    with open(os.path.join(ROOT, "imported_questions_review", "decision_making.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"Built {len(questions)} items (from 29 source questions).")
    print("By subtopic:", dict(by_sub))
    print(f"With images: {sum(1 for q in questions if q.get('image'))}")


if __name__ == "__main__":
    build()
