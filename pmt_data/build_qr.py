"""Build the Quantitative Reasoning JSON + review markdown from transcribed PMT content.

Data-set tables are transcribed into each question's passage; charts/graphs are
attached as images. One data set (QR0017) has a mark-scheme Q4 whose question text
is missing from the paper, so only its 3 complete questions are included.
"""
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)

DI = "Data Interpretation"
PM = "Percentages & Money"
RU = "Ratios & Units"
TS = "Tables & Statistics"
RT = "Rates & Time"

# Each dataset: code, subtopic, image (or None), passage, questions
# question: (stem, [(opt, correct)...], explanation)
DATASETS = [
    ("QR0002", PM, None,
     "Picture Perfect is a photography company offering portraits of individuals, families, babies and pets. "
     "Extras (props, photoshop, custom backgrounds) cost more.\n"
     "Prices — Individual: basic £20.00; Family: basic £30.00; Baby: basic £25.00; Pet: basic £17.50. "
     "For every type: Props +£5.00; Photoshop +15% of the basic price; Custom Backgrounds +£10.00.\n"
     "Bundle discounts: 10% off total for 3 photographs; 15% off for 4; 25% off for 5 or more.",
     [("Debbie has 3 children. She wants two family portraits and an individual portrait of all of them (Debbie + 3 children). She wants all of the photographs photoshopped. How much does she pay in total including the bundle discount?",
       [("£115.25",0),("£117.50",0),("£118.75",0),("£120.75",1),("£122.50",0)],
       "4 individual x 1.15 x 20 = 92; 2 family x 1.15 x 30 = 69; total 161; 6 photos = 25% off; 161 x 0.75 = £120.75."),
      ("Bill wants portraits of his two dogs. He has paid for props, photoshop and custom backgrounds for each portrait. How much does this cost in total?",
       [("£68.50",0),("£69.25",0),("£70.25",1),("£71.50",0),("£72.25",0)],
       "1 dog with photoshop: 17.50 x 1.15 = 20.125; + props + background: 20.125 + 5 + 10 = 35.125; x 2 dogs = £70.25."),
      ("Bill is told that if he gets a portrait of himself as well he will get a 10% discount overall. He decides to get a basic portrait of himself with no additional features. How much more is his new total to the nearest pound?",
       [("£10.00",0),("£11.00",1),("£12.00",0),("£13.00",0),("£14.00",0)],
       "70.25 + 20 = 90.25; x 0.9 = 81.225; 81.225 - 70.25 = 10.975 ~= £11."),
      ("Laura and John have just had a baby. They want a portrait of the baby, an individual portrait of each of themselves and a family portrait. They opt for custom backgrounds and props but not photoshop. How much does this cost in total including the bundle discount?",
       [("£130.25",0),("£131.75",1),("£132.50",0),("£133.75",0),("£134.25",0)],
       "Baby 25+5+10; 2 individual 2x(20+5+10); family 30+5+10; total 155; 4 portraits = 15% off; 155 x 0.85 = £131.75.")]),

    ("QR0028", DI, "questions/qr_ds2_graph.png",
     "Class 1 and Class 2 (each with 30 members) were asked how many countries abroad they had visited within "
     "the last year. The cumulative frequency graph is shown.",
     [("What was the maximum number of countries visited by those in class 1?",
       [("2",0),("3",1),("4",0),("28",0),("30",0)],
       "The cumulative frequency reaches 30 when the x-axis is at 3."),
      ("How many people in class 2 have been to exactly three countries?",
       [("28",0),("20",0),("10",0),("4",1),("2",0)],
       "Difference in cumulative frequency at 3 = 28 - 24 = 4."),
      ("How many more people have been abroad in Class 2 than Class 1?",
       [("1",1),("2",0),("3",0),("4",0),("5",0)],
       "Those who had been to 0 countries: 6 (class 1 start 5) -> difference 6 - 5 = 1."),
      ("How many people across the 2 classes had been abroad to 1 country?",
       [("12",0),("14",0),("17",0),("19",1),("21",0)],
       "Class 1: 10 - 5 = 5; Class 2: 20 - 6 = 14; 14 + 5 = 19.")]),

    ("QR0024", DI, "questions/qr_ds3_pie.png",
     "A wildlife charity focused on conservation and rehabilitating orphaned orangutans allocates resources "
     "monthly. Areas: Staffing and personnel (A); Administrative and running costs (B); Lobbying governments (C); "
     "Fundraising and awareness campaigns (D); Land protection (E); Rehabilitating the orangutans (F). "
     "In January the total income was £46,672. The pie chart shows the allocation of resources in January "
     "(A 20%, B 25%, C 6%, D 13%, E 12%, F 24%).",
     [("In January there was an unexpected influx of rescued baby orangutans and the cost of rehabilitating the animals spiked. In the month prior, rehabilitation costs were £6,543.74. How much more money was spent rehabilitating the orangutans in January compared with December?",
       [("£4657.54",1),("£4736.28",0),("£4984.63",0),("£5127.43",0),("£5473.27",0)],
       "46,672 x 0.24 = 11,201.28; 11,201.28 - 6,543.74 = £4657.54."),
      ("In February, the total income was only £38,463, but the exact same amount was needed for staffing and personnel as in January. What percentage of February's budget went towards staffing and personnel?",
       [("21%",0),("22%",0),("23%",0),("24%",1),("25%",0)],
       "46,672 x 0.2 = 9334.4; 9334.4 / 38,463 x 100 = 24.27 ~= 24%."),
      ("In March, £5646 was spent on land rehabilitation which represented 14% of the total budget for that month. What was the total budget in March rounded up to the nearest pound?",
       [("£38,375",0),("£38,749",0),("£39,184",0),("£40,072",0),("£40,329",1)],
       "5646 / 14 x 100 = 40,328.57 ~= £40,329."),
      ("In January, how much more was spent on administrative and running costs than on staffing and personnel, rounded up to the nearest pound?",
       [("£2128",0),("£2334",1),("£2522",0),("£2698",0),("£2864",0)],
       "25% - 20% = 5%; 46,672 x 0.05 = 2333.6 ~= £2334.")]),

    ("QR0021", RU, None,
     "A baker uses an American recipe for muffins (makes 12 standard-sized muffins or 6 large muffins): "
     "1 cup sugar, 2 1/2 cups flour, 3 eggs, 1 1/2 cups whole milk, 200g chocolate chips, 1 tsp raising powder.\n"
     "Cup measurements: 1 cup flour = 135g; 1 cup sugar = 200g; 1 cup milk = 240ml; 1 cup chocolate chips = 150g; "
     "1 gram = 0.0353 ounces.",
     [("If the baker decides to make 6 large muffins, how much flour, rounded to the nearest ounce, goes into one muffin?",
       [("1oz",0),("2oz",1),("3oz",0),("4oz",0),("5oz",0)],
       "2.5 cups x 135 = 337.5g total; 337.5 x 0.0353 = 11.91oz for 6 muffins; 11.91 / 6 ~= 2oz per muffin.")]),

    ("QR0025", DI, "questions/qr_ds5_bar.png",
     "The bar chart shows the sales (units) of three electronic devices in a popular electronics store in 2018, "
     "by quarter (Phone, Tablet, E-Reader).",
     [("Which item sold the most across the year?",
       [("Phone",0),("Tablet",0),("E-Reader",0),("Two sold the same number",1),("All three sold the same number",0)],
       "Tablet and E-Reader each sold 160 units across the year."),
      ("The E-Reader sold for £25 a device in Quarters 1 to 3 but was discounted by 20% in Quarter 4. How much revenue was made from sales of this device across the year?",
       [("£2500",0),("£3550",0),("£3600",0),("£3950",1),("£4000",0)],
       "(100 x 25) + (25 x 25) + (25 x 25) + (20 x [25 x 0.8=20]) = 2500 + 625 + 625 + 200 = £3950."),
      ("The E-Reader sold 120 units in the period of January to May. How many units did it sell in June?",
       [("0",0),("5",1),("10",0),("20",0),("25",0)],
       "Quarters 1 and 2 (Jan-Jun) total 125; 125 - 120 = 5."),
      ("When analyzing the sales of two sales employees Dan and Tom, the company found that in Quarters 1 and 2, Dan sold twice as many tablets as Tom. How many tablets did Tom sell in Quarters 1 and 2?",
       [("10",0),("20",1),("30",0),("40",0),("60",0)],
       "Total tablet sales in Q1 and Q2 = 60; Dan sold twice as many as Tom, so Tom sold 60 x 1/3 = 20.")]),

    ("QR0012", PM, None,
     "A gym in central London offers monthly memberships and day passes. Joining fee £20.00 for monthly "
     "memberships (not day passes). Premium memberships include fitness classes; standard do not. Classes can be "
     "bought independently with no joining fee.\n"
     "Class passes (Standard / Student): 5 Classes £50 / £40; 10 Classes £90 / £72; 20 Classes £160 / £128.\n"
     "Memberships (Standard / Premium / Standard Student / Premium Student): "
     "Day Pass £10 / £12 / £7 / £9; One Month £30 / £35 / £25 / £27; Six Month £150 / £180 / £120 / £150; "
     "12 Month £240 / £300 / £180 / £240.",
     [("Jessica and Sarah are students looking to join the gym. Sarah wants a 20 class pass. Jessica only wants to join for 6 months: she buys a day pass and a standard student membership for 6 months. Including the joining fee, how much more expensive is Jessica's package than Sarah's, by percentage?",
       [("12%",0),("13%",0),("14%",0),("15%",1),("16%",0)],
       "Sarah: 128. Jessica: 7 + 20 + 120 = 147. 147 - 128 = 19; 19 / 128 x 100 = 14.8% ~= 15%."),
      ("On the basis that there are on average 30 days in a month, how much cheaper is the daily rate of a six month premium membership compared to a single premium day pass?",
       [("£7.00",0),("£8.00",0),("£9.00",0),("£10.00",0),("£11.00",1)],
       "Six month premium daily rate: 180 / (6 x 30) = £1; premium day pass £12; 12 - 1 = £11."),
      ("How much cheaper is a student 20 classes pass per class compared with a standard 5 classes pass per class?",
       [("£3.60",1),("£4.00",0),("£4.40",0),("£4.80",0),("£5.20",0)],
       "Standard 5 pass per class: 50 / 5 = £10; student 20 pass per class: 128 / 20 = £6.40; 10 - 6.40 = £3.60."),
      ("Anthony is a student looking to join for 4 months. He is debating between 4 one-month passes at the premium student rate or a six month pass at the standard student rate. Which is cheaper and by how much?",
       [("Four premium one month passes, by £8.00",0),("Four premium one month passes, by £12.00",1),("Four premium one month passes, by £16.00",0),("Standard six month pass, by £8.00",0),("Standard six month pass, by £12.00",0)],
       "Four premium one-month passes + joining fee: (27 x 4) + 20 = 128; standard six month pass + joining fee: 120 + 20 = 140; 140 - 128 = £12 cheaper for the four premium passes.")]),

    ("QR0004", TS, None,
     "Breakdown of marks for recent medical school finals, by module — Anatomy (/32), Pharmacology (/60), "
     "Neuroscience (/25), Genetics and Reproduction (/20):\n"
     "Tanvir 20/32, 47/60, 7/25, 18/20; Josh 17/32, 31/60, 14/25, 20/20; Chris 18/32, 55/60, 12/25, 15/20; "
     "Jack 30/32, 54/60, 3/25, 5/20; Abishek 14/32, 30/60, 19/25, 8/20; Shwetabh 22/32, 39/60, 20/25, 19/20.",
     [("Who scored the lowest in Pharmacology?",
       [("Chris",0),("Josh",0),("Abishek",1),("Tanvir",0),("Shwetabh",0)],
       "Abishek scored 30/60 (50%), the lowest percentage in Pharmacology."),
      ("What was the mean percentage of marks for Neuroscience?",
       [("75%",0),("12.5%",0),("50%",1),("25%",0),("37.5%",0)],
       "Neuroscience totals: 7+14+12+3+19+20 = 75 out of 6x25 = 150; 75/150 = 50%."),
      ("In order to pass the exams, you have to score more than 50% on all modules. How many need to resit?",
       [("1",0),("2",0),("3",0),("4",1),("5",0)],
       "Four students fall below 50% in at least one module."),
      ("Jack resits his Neuroscience exam. He gains 17 more marks. What is his percentage increase in marks?",
       [("80%",0),("17%",0),("68%",1),("3%",0),("12%",0)],
       "Jack had 3/25; +17 = 20/25. Increase of 17 on 25 = 68%.")]),

    ("QR0017", DI, "questions/qr_ds8_bar.png",
     "The bar chart shows the popularity of different juices served on a flight from Hong Kong to London which "
     "flies 8 times a month; it shows the number of cartons sold per month (Orange / Apple / Cranberry): "
     "January 188/156/84; February 222/148/92; March 216/138/102; April 88/278/134; May 94/264/122; "
     "June 112/244/116. 1 carton has 750ml of juice; 1 serving of juice equals 150ml.",
     [("In April there was an E. coli contamination of citrus fruits which resulted in a drop in popularity of orange juice. By what percentage did the popularity of orange juice drop between March and April?",
       [("59%",1),("60%",0),("61%",0),("62%",0),("63%",0)],
       "March 216, April 88; 216 - 88 = 128; 128 / 216 x 100 = 59%."),
      ("The catering manager wants to know how many litres of juice were served per flight in January. Taking into account all 3 types, rounded to the nearest litre, how many litres of juice were served per flight in January?",
       [("38L",0),("39L",0),("40L",1),("41L",0),("42L",0)],
       "January total cartons 188+156+84 = 428; 428 x 750 / 1000 = 321L; 321 / 8 flights = 40.1 ~= 40L."),
      ("How many servings of juice in total were served in February?",
       [("2190",0),("2240",0),("2270",0),("2310",1),("2360",0)],
       "February cartons 222+148+92 = 462; 5 servings per carton (750/150); 462 x 5 = 2310 servings.")]),

    ("QR0003", PM, None,
     "A salon offers services at prices depending on whether done by a senior, intermediate or junior "
     "professional. Students get 15% discount, loyalty customers 10%, loyalty students 20%. Every 5th week, "
     "wash and blow dry is half price.\n"
     "Prices (Senior / Intermediate / Junior): Permanent colour £50/£35/£25; Semi-permanent colour £40/£30/£20; "
     "Full head highlights £40/£30/£25; Half head highlights £25/£20/£15; Hair cut £45/£30/£22.50; "
     "Wash and blow dry £20/£17.50/£15; Manicure £25/£20/£15.",
     [("Sandra is a loyalty customer. She wants full head highlights and a hair cut. The highlights will be done by a senior employee and the hair cut by an intermediate employee. How much does this cost in total?",
       [("£59.00",0),("£60.00",0),("£61.00",0),("£62.00",0),("£63.00",1)],
       "(40 + 30) x 0.9 = £63."),
      ("Frances is a student who wants a permanent colour, hair cut and a wash and blow dry. At first she wants it done by an intermediate employee but changes her mind and opts for a junior. How much cheaper is the total cost by percentage if she gets it done by a junior?",
       [("15%",0),("18%",0),("24%",1),("28%",0),("35%",0)],
       "Intermediate (35+30+17.5) x 0.85 = 70.125; junior (25+22.5+15) x 0.85 = 53.125; (70.125-53.125)/70.125 = 24%."),
      ("Liz is both a student and a loyalty customer. She wants a hair cut and a wash and blow dry, done by a junior employee; she has had 4 wash and blow dries prior to this. How much more expensive would it be if she wasn't a student, not a loyalty customer, had only 3 wash and blow dries before, and got it done by a senior staff member?",
       [("£41.00",1),("£49.75",0),("£54.01",0),("£57.64",0),("£64.12",0)],
       "Liz (student+loyalty, junior, 5th wash so half price): (22.5 + 7.5) x 0.8 = 24; senior no discount, full price wash: 45 + 20 = 65; 65 - 24 = £41.")]),

    ("QR0011", RT, None,
     "An investment bank has three offices - London, New York and Hong Kong - trying to arrange a meeting suitable "
     "for all. When it is 13:00 in London on the 6th of October, it is 20:00 in Hong Kong and 8:00 in New York on "
     "the same day. The latest a meeting can go on until is 23:00 in any country, and the earliest one can start is "
     "5:00.",
     [("How long is the window period in which all three offices can all have a meeting together?",
       [("1 hour",0),("2 hours",0),("3 hours",0),("4 hours",0),("5 hours",1)],
       "Earliest start uses New York (furthest behind): 5:00 NY = 10:00 London = 18:00 Hong Kong. Latest end uses Hong Kong (furthest ahead) at 23:00. 23:00 - 18:00 = 5 hours.")]),

    ("QR0015", PM, None,
     "A second-hand clothes shop sells clothes with bundle deals: two items 10% off, three items 15% off, four or "
     "more items 20% off.\n"
     "Prices: T-shirts and tops £3.00; Trousers £4.00; Shorts and skirts £3.00; Dresses £4.00; Shoes £6.00; "
     "Jewellery £2.50.",
     [("Rosa is a first time customer. She buys a pair of trousers, a dress, a pair of shoes and a necklace. How much does her total come to?",
       [("£13.20",1),("£14.00",0),("£14.85",0),("£15.15",0),("£15.40",0)],
       "4 + 4 + 6 + 2.50 = 16.5; four items = 20% off; 16.5 x 0.8 = £13.20."),
      ("Christopher buys a pair of shoes, a top and a pair of trousers. He changes his mind and puts the top back. How much less does he end up spending?",
       [("£1.90",0),("£1.95",0),("£2.00",0),("£2.05",1),("£2.10",0)],
       "Three items: (6 + 4 + 3) x 0.85 = 11.05; two items: (6 + 4) x 0.9 = 9; 11.05 - 9 = £2.05."),
      ("Rachel buys two pairs of shoes, a dress, a ring and a skirt. Ellie buys one pair of shoes, a skirt, two tops and a dress. Whose bundle is more expensive and by how much, rounded to the nearest penny?",
       [("Rachel's, by 87p",0),("Rachel's, by £2.00",1),("Ellie's, by 98p",0),("Ellie's, by £1.42",0),("Ellie's, by £2.38",0)],
       "Rachel: 0.80 x [(6 x 2) + 4 + 2.50 + 3] = 17.20; Ellie: 0.80 x [6 + 3 + (2 x 3) + 4] = 15.20; 17.20 - 15.20 = £2.")]),

    ("QR0018", RU, None,
     "A 750ml bottle of mineral water has these minerals dissolved (mg/l): Calcium 41, Magnesium 8, Sodium 11, "
     "Potassium 1, Sulphate 12, Bicarbonate 134, Chloride 10, Nitrate 8.\n"
     "A 2L bottle of the same water has its minerals in the same proportions (mg/l, to the nearest decimal place): "
     "Calcium 109.3, Magnesium ?, Sodium 29.3, Potassium ?, Sulphate 32, Bicarbonate ?, Chloride 26.7, Nitrate 21.3. "
     "Some values are missing.",
     [("Which of the following shows the correct missing values (Magnesium, Potassium, Bicarbonate)?",
       [("Magnesium: 19.7. Potassium: 3.3. Bicarbonate: 357.3.",0),
        ("Magnesium: 23.3. Potassium: 2.7. Bicarbonate: 319.3.",0),
        ("Magnesium: 21.3. Potassium: 2.7. Bicarbonate: 357.3.",1),
        ("Magnesium: 19.7. Potassium: 2.7. Bicarbonate: 319.3.",0),
        ("Magnesium: 23.3. Potassium: 3.3. Bicarbonate: 327.3.",0)],
       "Divide the 750ml values by 750 and multiply by 2000 (i.e. x 200/75): Magnesium 8 -> 21.3; Potassium 1 -> 2.7; Bicarbonate 134 -> 357.3.")]),
]


def build():
    questions = []
    counter = 0
    for code, subtopic, image, passage, qs in DATASETS:
        for i, (stem, opts, expl) in enumerate(qs, 1):
            counter += 1
            item = {"number": str(counter), "ref": f"{code} Q{i}", "subtopic": subtopic,
                    "kind": "mcq", "passage": passage, "stem": stem,
                    "options": [{"text": t, "correct": bool(c)} for t, c in opts]}
            if image:
                item["image"] = image
            if expl:
                item["explanation"] = expl
            questions.append(item)

    data = {"section": {"code": "QR", "name": "Quantitative Reasoning"}, "questions": questions}
    with open(os.path.join(HERE, "quantitative_reasoning.json"), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    from collections import Counter
    by_sub = Counter(q["subtopic"] for q in questions)
    lines = ["# Quantitative Reasoning - Imported Questions (Phase 3)\n",
             "Source: PMT Quantitative Reasoning Question Pack 1 (placeholder demo content).\n",
             f"**Practice items:** {len(questions)}  |  **With charts:** {sum(1 for q in questions if q.get('image'))}\n",
             "**By subtopic:** " + ", ".join(f"{k}: {v}" for k, v in sorted(by_sub.items())) + "\n",
             "\n_Note: PMT's QR0017 (juice chart) has a mark-scheme Q4 whose question text is missing from the "
             "paper, so only its 3 complete questions are included._\n"]
    last = None
    for q in questions:
        code = q["ref"].split(" ")[0]
        if code != last:
            img = "  `[chart]`" if q.get("image") else ""
            lines.append(f"\n### {code}{img}\n> {q['passage'].splitlines()[0]}\n")
            last = code
        lines.append(f"\n**{q['number']}. ({q['ref']})** {q['stem']}\n")
        for opt in q["options"]:
            mark = "  ✅" if opt["correct"] else ""
            lines.append(f"- {opt['text']}{mark}")
        if q.get("explanation"):
            lines.append(f"\n_{q['explanation']}_")
        lines.append("")
    with open(os.path.join(ROOT, "imported_questions_review", "quantitative_reasoning.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"Built {len(questions)} QR items across {len(DATASETS)} data sets.")
    print("By subtopic:", dict(by_sub))
    print("With charts:", sum(1 for q in questions if q.get("image")))


if __name__ == "__main__":
    build()
