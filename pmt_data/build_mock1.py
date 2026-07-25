"""Build Mock 1 JSON (per section) + review markdown from transcribed PMT content.

source = "PMT-M1" so the mock never collides with the module packs (source "PMT").
This file currently covers Section 1 (VR) and Section 2 (DM). QR + SJT are added
in a second pass. DM Yes/No-statement questions are split into individual Yes/No items.
"""
import json
import os
from collections import Counter

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
SOURCE = "PMT-M1"
TFC = ["True", "False", "Can't tell"]

# ---------------- Verbal Reasoning ----------------
VR_PASSAGES = {
    "VRTF0024": "The Wars of the Roses were a series of English civil wars fought between supporters of rival branches of the Royal House of Plantagenet for the control of the throne of England. These wars between The House of Lancaster (red rose) and The House of York (white rose) eliminated the male lines of both families. The majority of battles were fought between 1455 and 1487, however fights also occurred before and after this period. Edward, heir of the Duke of York, became the first Yorkist king, Edward IV. His reign began in 1461 but was interrupted by a Lancastrian uprising and re-instalment of Henry VI from 1470 to 1471, after which his reign resumed until his death in 1483. His son reigned for 78 days as Edward V. The final victory went to Henry Tudor, who defeated Richard III at the Battle of Bosworth Field and, as Henry VII, married Elizabeth of York, uniting the claims.",
    "VRTF0001": "The Sykes-Picot Agreement was a secret treaty, created in August 1916 and leaked by the Bolsheviks in November of the following year; it was a pivotal agreement between the Triple Entente that sought to divide the lands of the Ottoman Empire following its defeat at the end of WWI. Russia would be given Constantinople and Armenian provinces, France the land comprising modern day Syria, while the British would have influence over Mesopotamia (modern day Iraq). With the withdrawal of Russia from the war, it was replaced with Italy. The agreement represented a betrayal of earlier pacts made between the Arabs and the British, on which the Arabian revolt was based, executed by Husayn ibn Ali. The imprint of the Class A and B mandates remains in the modern-day borders of Iraq, Israel, Palestine, Jordan, Lebanon and Syria.",
    "VRIC0001": "Chronic obstructive pulmonary disease (COPD) is a chronic lung condition characterised by progressive persistent obstruction to airflow. In the majority of cases COPD is caused by smoking, however other causes include air pollution and occupational hazards. Corticosteroids are anti-inflammatory drugs. They bind to receptors which regulate inflammatory protein synthesis, to switch on or off gene transcription. At a cellular level, this reduces the number of eosinophils, T-lymphocytes, mast cells and dendritic cells in the airways. An exacerbation of COPD is an acute worsening of symptoms; it is important to prevent and treat exacerbations as they can contribute to long-term decline in lung function, increased mortality and reduced quality of life.",
    "VRTF0009": "A minimum price is a price floor set by the government; it is a set level that the price is not allowed to fall below (although it is allowed to rise above it). To be effective the minimum price has to be set higher than the equilibrium price. Alcohol is likely to be over consumed as people overestimate the marginal private benefits and not take into account the marginal social costs. A minimum price should be set on alcohol to reduce alcohol related disease, decrease stress on the NHS and reduce overconsumption. However, some argue it may punish moderate drinkers and could increase poverty as people spend larger proportions of their income on alcohol.",
    "VRIC0003": "Forensic science refers to the application of scientific techniques to assist investigations in criminal law. The first known account was written in 11th century China. During the 19th century, crime scene investigation included footprint analysis, ballistics (the mechanical study of projectiles, such as bullets), early fingerprinting, forensic toxicology and criminal psychology. Perhaps the most major breakthrough in 20th century forensic science is DNA analysis, developed by Sir Alec Jeffreys and first used to solve a crime in 1985. Whilst 99.9% of human DNA is the same between individuals, 0.1% is made up of highly variable repetitive segments (short tandem repeats) that are unique to that individual.",
    "VRIC0002": "Surrealism was an artistic, philosophical and literary movement of the 20th century. The term \"surrealist\" was first coined by French poet Guillaume Apollinaire; however, the first description of surrealism was laid out in the \"Surrealist Manifesto\" written by Andre Breton in 1924. Surrealism was a rejection of conventional perceptions of reality and was heavily influenced by developments in psychology at the time. Perhaps the most famous artist of the movement is Spanish surrealist Salvador Dali, best known for bizarre, dream-like scenes. One of his most recognisable works, \"The Persistence of Memory\", features melting clocks; Dali said they were inspired by the surrealist perception of a Camembert melting in the sun.",
    "VRIC0004": "Sigiriya, Sri Lanka, is a UNESCO world heritage site and ancient rock fortress dating back to approximately 477 CE. The name Sigiriya derives from the Sinhalese for \"Lion Rock\". Sigiriya was established by King Kashyapa as the new capital of Sri Lanka after he seized the throne from his father King Dhatusena, when he discovered his mother was not the true Queen, thus forfeiting his lineage. His half-brother Moggallana, the true heir, returned from India and defeated Kashyapa in 495 CE, after which the King committed suicide. Legend has it that concubines barricaded in the palace perished and transformed into wasps; in modern day, Sigiriya is home to aggressive wasp colonies.",
    "VRTF0003": "Even though the BMA are now calling for all prescriptions in England to be free, Cystic Fibrosis patients still pay for treatment despite continuously being on medication. Neil Churchill, Chief Executive of Asthma UK, said millions of people with long-term conditions bear a disproportionate burden of prescription charges. Invocator, a drug that addresses the genetic defect in certain mutations, has not been made available in Wales for cost reasons. Around 1 in every 2,500 babies born in the UK are affected by CF. A Government report claimed that by 2015 obesity will cost the NHS £6.4bn per year, despite the patient being predominantly responsible for that condition.",
    "VRTF0010": "Positive externalities exist when third parties benefit from the overflow effects of production/consumption, e.g. the social returns from investment in education. Negative externalities happen when production and/or consumption imposes external costs on third parties for which there is no compensation. Merit goods tend to be under-consumed by the free market as people underestimate their benefits due to information failure. Where positive externalities exist, the good is likely to be under-consumed. De-merit goods are believed to be 'bad' for you; their consumption can lead to negative externalities and a fall in social welfare. Consumers may be unaware of the negative externalities these goods create.",
    "VRIC0006": "Tutankhamun was an Ancient Egyptian pharaoh ruling from 1332-1323 BC. He ascended to the throne at age nine, marrying his half-sister Ankhesenamun. The tomb was discovered in the Valley of the Kings in November 1922 by Howard Carter and contained 5,398 items, including a solid gold sarcophagus and golden death mask, trumpets, archery bows, food, wine and fresh linen underwear. There is no surviving documentation of his death. CT scanning in 2005 showed a compound left leg fracture which could have become infected; DNA analysis in 2010 showed malaria; congenital defects were also discovered. Other experts believe he died as the result of an accident such as a chariot crash.",
    "VRIC0008": "The Incas were a South American culture whose empire was the largest in South America pre the Columbian invasion. The Incan empire flourished between 1438 and 1533; its capital was Cusco, Peru. At its peak, the empire incorporated Peru and parts of Ecuador, Bolivia, Colombia, Argentina and Chile. The Incas are famous for their architecture, most notably Machu Picchu, believed to have been created as a citadel for the Incan emperor Pachacuti. The stones are cut and pieced together with such precision that no mortar is used. It is theorised they used a 'wooden wedge technique': driving wet wedges of wood into rock, allowing the wood to freeze and expand, cracking the rock precisely.",
}

# (code, subtopic, kind, [(stem, [(opt,correct)...] OR tfc_index)...])
VR = [
    ("VRTF0024", "Inference (True/False/Can't Tell)", "tf", [
        ("All of the Wars of the Roses battles were fought between 1455 and 1487.", 1),
        ("Edward IV was king of England for 21 years.", 0),
        ("Edward IV had 2 sons.", 0),
        ("Edward IV had 2 sons.  [NOTE: PMT duplicated this statement as Q3 and Q4 with different answers]", 2)]),
    ("VRTF0001", "Inference (True/False/Can't Tell)", "tf", [
        ("The Sykes-Picot Agreement was leaked by the Bolsheviks in 1917.", 0),
        ("The Triple Entente refers to the countries of France, Russia and Italy.", 1),
        ("Faysal was supported by the allies in the Arabian revolution against the Ottoman Empire to topple the government in Cairo.", 1),
        ("The Class A and B mandates created represent the original lands distributed to France and Britain by the agreement.", 0)]),
    ("VRIC0001", "Reading Comprehension", "mcq", [
        ("The mechanism of action of corticosteroids is:",
         [("Increasing the number of eosinophils in the airways.", 0),
          ("Decreasing the number of eosinophils in the oesophagus.", 0),
          ("Decreasing the number of eosinophils in the airways.", 1),
          ("Decreasing the number of eosinophils in the stomach.", 0)]),
        ("COPD is always caused by smoking.",
         [("Yes.", 0), ("No.", 1), ("Can't tell.", 0)]),
        ("Exacerbation of COPD can contribute to:",
         [("Short-term decline in lung function.", 0), ("Decrease in mortality.", 0),
          ("Increased quality of life.", 0), ("Increased mortality.", 1)]),
        ("Corticosteroids produce their effect by:",
         [("Binding to receptors which regulate inflammatory RNA synthesis.", 0),
          ("Binding to receptors which regulate inflammatory protease synthesis.", 0),
          ("Binding to receptors which regulate inflammatory protein synthesis.", 1),
          ("Binding to receptors which inhibit inflammatory protein synthesis.", 0)])]),
    ("VRTF0009", "Inference (True/False/Can't Tell)", "tf", [
        ("People may underestimate the social cost of consuming alcohol.", 0),
        ("Setting a minimum price on alcohol may reduce the number of alcohol related deaths.", 0),
        ("The price may not rise above the minimum price set by the government.", 1),
        ("Setting a minimum price of alcohol will result in a surge of world poverty.", 2)]),
    ("VRIC0003", "Reading Comprehension", "mcq", [
        ("In forensic science, what describes the mechanical study of projectiles?",
         [("Projectile mechanics.", 0), ("Ballistics.", 1), ("Astrodynamics.", 0), ("Trajectory physics.", 0)]),
        ("Which percentage of human DNA, utilised in DNA profiling, is unique between individuals?",
         [("0.1%.", 1), ("1%.", 0), ("0.01%.", 0), ("10%.", 0)]),
        ("Which year was forensic DNA analysis first used successfully in criminal investigation?",
         [("1991.", 0), ("1981.", 0), ("1976.", 0), ("1985.", 1)]),
        ("Which was not employed as a forensic technique in the 19th century?",
         [("Forensic toxicology.", 0), ("Criminal psychology.", 0), ("Cryptanalysis.", 1), ("Fingerprinting.", 0)])]),
    ("VRIC0002", "Reading Comprehension", "mcq", [
        ("The term \"surrealism\" was first coined by:",
         [("Andre Breton.", 0), ("Salvador Dali.", 0), ("Guillaume Apollinaire.", 1), ("Sigmund Freud.", 0)]),
        ("One of Salvador Dali's most memorable paintings is called:",
         [("The Perception of Memory.", 0), ("The Persistence of Mortality.", 0),
          ("The Petulance of Mortality.", 0), ("The Persistence of Memory.", 1)]),
        ("Surrealism was heavily influenced by developments in:",
         [("Physiology.", 0), ("Psychology.", 1), ("Dream studies.", 0), ("Neurological imaging.", 0)]),
        ("Surrealism was first described by Andre Breton in his 1924 book entitled:",
         [("The Surrealist Declaration.", 0), ("The Surrealist Revolution.", 0),
          ("The Surrealist Proclamation.", 0), ("The Surrealist Manifesto.", 1)])]),
    ("VRIC0004", "Reading Comprehension", "mcq", [
        ("Sigiriya was built as the new capital of Sri Lanka by which ancient King?",
         [("King Moggallana", 0), ("King Kashyapa", 1), ("King Vijaya", 0), ("King Dhatusena", 0)]),
        ("According to legend, deceased concubines in the palace turned into which creature?",
         [("Butterflies", 0), ("Hornets", 0), ("Bees", 0), ("Wasps", 1)]),
        ("Why did King Kashyapa seize the throne from his father in a military coup?",
         [("He disagreed with his father's dictatorship.", 0),
          ("He found out the King wasn't his true father, invalidating his right to the throne.", 0),
          ("He wanted to move the capital from Anuradhapura to Sigiriya, against his father's wishes.", 0),
          ("He found out the true Queen was not his mother, invalidating his right to the throne.", 1)]),
        ("The ancient rock fortress of Sigiriya dates back to which year?",
         [("477 CE", 1), ("495 BC", 0), ("495 CE", 0), ("447 CE", 0)])]),
    ("VRTF0003", "Inference (True/False/Can't Tell)", "tf", [
        ("Cystic Fibrosis patients are not the only people who pay for prescriptions.", 0),
        ("The government report claimed that more money is spent on obesity than on Cystic Fibrosis.", 2),
        ("Neil Churchill believes all prescriptions should be free.", 2),
        ("Invocator is not given to Cystic Fibrosis patients in England because of its cost.", 1)]),
    ("VRTF0010", "Inference (True/False/Can't Tell)", "tf", [
        ("De-merit goods may cause a fall in social welfare.", 0),
        ("The value of merit goods is overestimated.", 1),
        ("Goods that yield positive externalities are likely to be over-consumed.", 1),
        ("All consumers have imperfect information.", 1)]),
    ("VRIC0006", "Reading Comprehension", "mcq", [
        ("How many items were buried with Tutankhamun in his tomb?",
         [("8359", 0), ("3895", 0), ("5839", 0), ("5398", 1)]),
        ("What was the familial relationship between Ankhesenamun and Tutankhamun?",
         [("Cousins", 0), ("Half siblings", 1), ("Siblings", 0), ("Half cousins", 0)]),
        ("According to the article, which of the following objects is not listed as being discovered in the tomb of Tutankhamun?",
         [("Fresh linen underwear", 0), ("Wine", 0), ("His mummified pet cat", 1), ("Archery bows", 0)]),
        ("According to the article, which of the following is not a working hypothesis for the cause of Tutankhamun's death?",
         [("Malaria", 0), ("Infected compound fracture", 0), ("Chariot accident", 0), ("Tuberculosis", 1)])]),
    ("VRIC0008", "Reading Comprehension", "mcq", [
        ("Which of the following statements most accurately describes the geographical reach of the Incan empire?",
         [("Bolivia plus parts of Peru, Chile, Guatemala and Ecuador.", 0),
          ("Peru plus parts of Argentina, Chile, Ecuador and Brazil.", 0),
          ("Ecuador plus parts of Colombia, Argentina, Peru and Bolivia.", 0),
          ("Parts of Ecuador, Bolivia, Colombia, Argentina and Chile as well as Peru itself.", 1)]),
        ("Which of the following is a theorised method for cutting large stones to build with?",
         [("Wet wood technique.", 0), ("Freeze expansion technique.", 0),
          ("Frozen wedge technique.", 0), ("Wooden wedge technique.", 1)]),
        ("The Incan Empire existed between which dates?",
         [("1438-1533", 1), ("1538-1672", 0), ("1433-1538", 0), ("1402-1608", 0)]),
        ("The purpose of Machu Picchu is unclear, but it is believed to be created as:",
         [("A citadel to protect emperors from earthquakes.", 0),
          ("A religious temple complex for worshipping the Sun.", 0),
          ("A citadel for the Incan emperor Pachacuti.", 1),
          ("A mountainous settlement for Incan high priests.", 0)])]),
]

# ---------------- Decision Making ----------------
# Standard MCQ: (ref, subtopic, stem, image_or_None, [(opt,correct)...])
DM_MCQ = [
    ("DMDR0001", "Logical Puzzles",
     "Al-Diwaniyah is south of Baqubah which is not as far north as Sulaymaniyah. Al Habbaryah is west of Baghdad which is east of Baqubah. Al Habbaryah is situated:", None,
     [("North of Sulaymaniyah.", 0), ("South of Al-Diwaniyah and west of Baqubah.", 0),
      ("South of Sulaymaniyah and north of Al-Diwaniyah and can be between Baqubah and Baghdad.", 1),
      ("East of Baqubah and south of Al-Diwaniyah.", 0)]),
    ("DMEA0001", "Evaluating Arguments",
     "Should the law be changed to force all soft-drinks manufacturers to label sugar content clearly on their packaging?", None,
     [("Yes, children are particularly fond of sugary soft drinks, which can damage their health.", 0),
      ("Yes, attempts to get the drinks industry to label sugar content on a voluntary basis have given mixed results.", 1),
      ("No, the majority of countries have no equivalent legislation and not all of those have a population obesity problem.", 0),
      ("No, the cost of monitoring the accuracy of labelling would be passed on to the consumer.", 0)]),
    ("DMFR0002", "Interpreting Information",
     "Given the equations shown are true, and given that a circle has the value of 4, what is the value of star + square + triangle + circle?",
     "questions/m1_dm_q5_equations.png",
     [("38", 0), ("40", 0), ("42", 0), ("44", 1), ("46", 0)]),
    ("DMEA0009", "Evaluating Arguments",
     "Should overweight patients not be allowed access to expensive medication and hospital resources because they have brought their demise upon themselves?", None,
     [("Yes, they should just sign up to the gym.", 0),
      ("No, we should tax the people who sell unhealthy foods instead.", 0),
      ("No, the NHS is for everyone and discrimination is a slippery slope, it would be completely biased.", 1),
      ("Yes, the funds and resources saved can be allocated for patients who have more critical illnesses.", 0)]),
    ("DMSR0006", "Interpreting Information",
     "Five new-born babies are weighed. Baby Andrew weighs 3750g. Baby Nina weighs 150g more than baby Charlotte. Baby Gil weighs 80% of baby Charlotte. Baby Oscar weighs more than Nina but less than Andrew. Which weighs the most and which the least?", None,
     [("Baby Nina (most) and baby Gil (least).", 0), ("Baby Oscar (most) and baby Charlotte (least).", 0),
      ("Baby Andrew (most) and baby Nina (least).", 0), ("Baby Andrew (most) and baby Gil (least).", 1)]),
    ("DMEA0011", "Evaluating Arguments",
     "Drugs should be legalised in England, as it would lead to supervision of production and therefore fewer drug related deaths. Which is the strongest argument?", None,
     [("Yes, all drugs should be legalised so that dangerous drug dealers are no longer in business.", 0),
      ("Yes, legalising drugs will ensure less drug-related crime and violence such as fatal stabbings and murder.", 0),
      ("Legalising drugs is a good idea as currently drugs are not regulated which means dangerous and potent levels lead to death.", 1),
      ("Legalising drugs will mean they are widely available, so individuals are more likely to die from abuse and overdose.", 0)]),
    ("DMFR0003", "Venn Diagrams",
     "The diagram presents hospitals in London and Birmingham that final year medical students applied to. How many students applied to hospitals in both London and Birmingham?",
     "questions/m1_dm_q10_venn.png",
     [("119.", 0), ("127.", 1), ("132.", 0), ("120.", 0)]),
    ("DMSR0001", "Interpreting Information",
     "A team of 2 cleaners requires 1 hour more per bedroom above the standard 2 hours to clean a house. How many hours does it take 1 cleaner to clean a 5-bedroom house, considering all cleaners work equally?", None,
     [("3.5 hours.", 0), ("6 hours.", 0), ("14 hours.", 1), ("18 hours.", 0)]),
    ("DMFR0008", "Venn Diagrams",
     "The diagram represents the departments that a group of patients visited over the last year. Which statement is true about this population?",
     "questions/m1_dm_q12_venn.png",
     [("Individuals in group P and T attended either A&E or their GP but not both in the last year.", 1),
      ("Individuals in group S, R and V must have all attended A&E in the last year.", 0),
      ("Individuals in W are fit and healthy and have never required healthcare services.", 0),
      ("Individuals in P and V have attended both their GP and A&E but have not had a hospital admission in the last year.", 0)]),
    ("DMEA0006", "Evaluating Arguments",
     "The UK has one of the highest rates of teenage pregnancy in Western Europe. The age of consent is 16. To reduce teenage pregnancy, should the age of consent be raised from 16 to 18?", None,
     [("Yes. Sixteen-year olds do not have a fully matured prefrontal cortex, and therefore are not competent to agree to sexual intercourse.", 0),
      ("Yes. When such laws are introduced, society's values usually follow suit and people will do more to prevent teenagers from having sex.", 0),
      ("No. It is difficult to catch and punish those who engage in intercourse and so such a law will be difficult to enforce.", 0),
      ("No. Such a law would be ineffectual, and it would be better to focus more on sex education in schools and improving access to contraception.", 1)]),
    ("DMSR0014", "Probability & Statistics",
     "Jason gets on average 5 successful shots out of 20. Michael gets 30 out of 60. If both throw 500 free throws each, which statement is correct?", None,
     [("Jason will have more successful shots than Michael.", 0),
      ("Michael will have the same number of successful shots as Jason.", 0),
      ("Jason will have less successful shots than Michael.", 1),
      ("Michael will have less successful shots than Jason.", 0)]),
    ("DMEA0010", "Evaluating Arguments",
     "Should assisted suicide be made legal for practitioners to relieve suffering of terminal patients?", None,
     [("Yes, because patients deserve dignity in death and have a right to reject treatment.", 1),
      ("Yes, because patients should be able to receive the services they want.", 0),
      ("No, because doctors will be held liable for their patient death.", 0),
      ("No, because doctors should not be in control of who has a right to die or not.", 0)]),
    ("DMFR0001", "Venn Diagrams",
     "In a group of 50 people, twice as many people like carrots only as like peas only. One more person likes carrots and peas as like peas only. 29 people like sweetcorn and nobody likes none of the three. How many people like carrots only?", None,
     [("5.", 0), ("6.", 0), ("10.", 1), ("11.", 0)]),
    ("DMFR0009", "Venn Diagrams",
     "The ethnicity of a sample of patients is noted as A, B, C, D and E. Which statement is true about this population?",
     "questions/m1_dm_q19_chart.png",
     [("In this sample, ethnicity A is the commonest.", 0),
      ("The number of individuals of ethnicity B and E represent half the total patient sample.", 0),
      ("There is an equal number of individuals of ethnicity C and A in the world.", 0),
      ("The number of individuals of ethnicity A and E represent 1/3 of the total patient sample.", 1)]),
    ("DMEA0004", "Evaluating Arguments",
     "The UK breast cancer screening programme offers a mammogram every 3 years for women aged 50 to 70. Should it be extended to younger women and more frequently than every 3 years?", None,
     [("Yes. It is imperative to pick cancers up as early as possible, so extending the programme would improve survival rates.", 0),
      ("Yes. Young women, such as those with genetic mutations, are also at higher risk and should be offered the same programme.", 0),
      ("No. It is not economically feasible for the government to offer the programme more broadly, or else it would already be offered.", 0),
      ("No. Women younger than fifty are not at as high a risk, and more frequent screening would result in a high rate of false positives and unnecessary invasive tests.", 1)]),
    ("DMEA0007", "Evaluating Arguments",
     "To reduce global air pollution, an acceptable level should be agreed and sanctions imposed on countries who exceed it. Select the strongest argument.", None,
     [("Yes. It is important to punish governments who have the worst impact on the environment as an example to others.", 0),
      ("Yes. The concept of benefiting the environment is often not enough incentive for governments to change, so an economic incentive is likely to work.", 1),
      ("No. It would be better to focus on the lifestyles of individuals, taking a 'bottom up' instead of 'top down' approach.", 0),
      ("No. A lot of the countries producing large amounts of air pollution are less developed, and this would cripple them economically.", 0)]),
    ("DMSR0002", "Logical Puzzles",
     "Sarah needs a day and night shift covered on Friday, Saturday and Sunday. No one can work consecutive shifts, and no one can work more than two of the six shifts. Rachel can't work Friday. Ellen can only work Friday and Saturday. Liam can only work day shifts. Who must work Saturday night?", None,
     [("Rachel only.", 0), ("Ellen only.", 1), ("Liam only.", 0), ("Rachel or Ellen.", 0), ("Ellen or Liam.", 0)]),
    ("DMSR0003", "Interpreting Information",
     "The area of a square is the square of its side length. Square X has sides L, Square Y has sides 2L, Square Z has sides 3L. Which is true?", None,
     [("Three X can fill one Z.", 0), ("One Z can accommodate 6 Y.", 0), ("Two X completely fill one Y.", 0),
      ("One Z can accommodate 9 X.", 1), ("Y is twice the size of X.", 0)]),
    ("DMSR0004", "Venn Diagrams",
     "There are 200 students. All speak English. 150 speak Cantonese. 90 speak French. 60 speak all three. 90 speak English and Cantonese but not French. 30 speak English and French but not Cantonese. How many speak just English?", None,
     [("10.", 0), ("20.", 1), ("30.", 0), ("40.", 0), ("50.", 0)]),
    ("DMSR0008", "Logical Puzzles",
     "4, 16, 8, 64, 32, 1024, \"?\". Select the answer which completes this number sequence.", None,
     [("72.", 0), ("2048.", 0), ("512.", 1), ("216.", 0), ("90.", 0)]),
    ("DMFR0012", "Venn Diagrams",
     "The diagram presents the cars driven by people in a neighbourhood. Ferrari, Aston Martin and Lamborghini are 'supercars'; Ford, Fiat and Toyota are 'standard family cars'. How many people drive either both one supercar and one standard family car, or just one supercar?",
     "questions/m1_dm_q27_venn.png",
     [("70.", 0), ("71.", 1), ("74.", 0), ("75.", 0)]),
    ("DMFR0010", "Logical Puzzles",
     "Three sports teams live in coloured houses. The team at the red house drink water. The hockey team live in the green house and drink Coca-Cola. The team who drink milk eat strawberry ice-cream. The football team eat chocolate ice-cream. Which statement is correct?", None,
     [("The football team live in the blue house, drink milk and eat strawberry ice-cream.", 0),
      ("The hockey team live in the green house; they drink Coca-Cola and chocolate ice-cream.", 0),
      ("The hockey team live in the green house, drink Coca-Cola and eat vanilla ice-cream.", 1),
      ("The tennis team live in the red house, drink water and eat vanilla ice-cream.", 0)]),
]

# Yes/No-statement DM questions: (ref, scenario, [(letter, statement, is_yes)...])
DM_YESNO = [
    ("DMDR0010", "This child is a menace. All menaces are annoying.",
     [("A", "All children are menaces.", 0), ("B", "All annoying things are menaces.", 0),
      ("C", "Some menaces are annoying.", 1), ("D", "Some menaces are children.", 1),
      ("E", "Some children are annoying.", 1)]),
    ("DMDR0011", "Not all the people at the circus were clowns but all the clowns were in makeup. Some clowns were not professionals.",
     [("A", "All those in makeup were clowns.", 0), ("B", "A person present was either a clown or not a professional.", 0),
      ("C", "Only clowns were professionals.", 0), ("D", "Some clowns were professionals.", 1),
      ("E", "The clowns who were male weren't in makeup.", 0)]),
    ("DMDR0004", "All monkeys are simians. All humans are apes. No apes are simians.",
     [("A", "All humans are simians.", 0), ("B", "Some humans are apes.", 1),
      ("C", "No monkeys are apes.", 1), ("D", "No monkeys are human.", 1),
      ("E", "All simians are monkeys.", 0)]),
    ("DMDR0002", "Charlotte has three exams starting Monday with a day break between each. Lucy finishes before Charlotte with no day breaks, starting her four exams after Charlotte starts. Louie starts on the same day as Lucy. Both Louie and Lucy have two exams on one day; Charlotte has a single exam that day. No exams at weekends; up to 2 sittings per day.",
     [("A", "Charlotte has an exam for each of her modules.", 0), ("B", "Lucy and Louie have two exams each on Wednesday.", 1),
      ("C", "All three friends have exams on Thursday.", 0), ("D", "There are 10 exams in the passage.", 1),
      ("E", "The majority of Charlotte's exams don't coincide with her friend's exams.", 1)]),
    ("DMDR0003", "A neurosurgeon has surgery at 5pm needing a bed. Two patients left UCLH at midday while one was admitted through A&E. Before 4pm, the Royal Free transferred an elderly patient in while the earlier A&E patient was discharged. As the operation ends, a further two patients are admitted from A&E.",
     [("A", "There were enough beds at midday for the surgery to go ahead.", 1), ("B", "The highest number of beds available at one point was three.", 0),
      ("C", "A&E patients take priority over surgical patients when it comes to beds.", 0), ("D", "The neurosurgeon started the operation with four beds available.", 1),
      ("E", "Upon the operation ending there were two beds available.", 1)]),
    ("DMDR0005", "Most chickens are egg-layers. No egg-layers can fly.",
     [("A", "Most chickens cannot fly.", 1), ("B", "Some egg-layers can fly.", 0),
      ("C", "The chickens which are not egg-layers can fly.", 0), ("D", "A penguin can fly so it must not be an egg-layer.", 1),
      ("E", "All chickens cannot fly.", 0)]),
    ("DMDR0015", "Bennie has 6 bikes to repair. Half of them are red, with two black bikes.",
     [("A", "There could be two silver bikes.", 0), ("B", "There are 3 red vehicles on site.", 0),
      ("C", "He has at least 3 red bikes on site.", 1), ("D", "A third of the bikes for repair are black.", 1),
      ("E", "There is one silver bike.", 0)]),
]


def build():
    # ---- VR JSON ----
    vr_q = []
    n = 0
    for code, sub, kind, items in VR:
        for item in items:
            n += 1
            if kind == "tf":
                stem, ci = item
                vr_q.append({"number": str(n), "ref": f"M1 {code} Q{n}", "subtopic": sub, "kind": "tf",
                             "passage": VR_PASSAGES[code], "stem": stem,
                             "options": [{"text": t, "correct": (i == ci)} for i, t in enumerate(TFC)]})
            else:
                stem, opts = item
                vr_q.append({"number": str(n), "ref": f"M1 {code} Q{n}", "subtopic": sub, "kind": "mcq",
                             "passage": VR_PASSAGES[code], "stem": stem,
                             "options": [{"text": t, "correct": bool(c)} for t, c in opts]})
    _write("mock1_vr.json", {"section": {"code": "VR", "name": "Verbal Reasoning", "source": SOURCE}, "questions": vr_q})

    # ---- DM JSON ----
    dm_q = []
    n = 0
    dm_index = {c[0]: c for c in DM_MCQ}
    yn_index = {y[0]: y for y in DM_YESNO}
    # Order follows the paper (Q1..Q29)
    ORDER = ["DMDR0001", "DMDR0010", "DMEA0001", "DMDR0011", "DMFR0002", "DMEA0009", "DMSR0006",
             "DMEA0011", "DMDR0004", "DMFR0003", "DMSR0001", "DMFR0008", "DMEA0006", "DMSR0014",
             "DMDR0002", "DMEA0010", "DMFR0001", "DMDR0003", "DMFR0009", "DMDR0005", "DMEA0004",
             "DMEA0007", "DMSR0002", "DMSR0003", "DMSR0004", "DMSR0008", "DMFR0012", "DMFR0010", "DMDR0015"]
    for code in ORDER:
        if code in dm_index:
            _, sub, stem, image, opts = dm_index[code]
            n += 1
            q = {"number": str(n), "ref": f"M1 {code} Q{n}", "subtopic": sub, "kind": "mcq",
                 "stem": stem, "options": [{"text": t, "correct": bool(c)} for t, c in opts]}
            if image:
                q["image"] = image
            dm_q.append(q)
        else:
            _, scenario, statements = yn_index[code]
            n += 1
            for letter, statement, is_yes in statements:
                dm_q.append({"number": f"{n}{letter}", "ref": f"M1 {code} Q{n}{letter}", "subtopic": "Syllogisms",
                             "kind": "mcq", "passage": scenario,
                             "stem": f'"{statement}"  —  Does this follow from the information above?',
                             "options": [{"text": "Yes", "correct": bool(is_yes)}, {"text": "No", "correct": not bool(is_yes)}]})
    _write("mock1_dm.json", {"section": {"code": "DM", "name": "Decision Making", "source": SOURCE}, "questions": dm_q})

    # ---- Review markdown ----
    lines = ["# Mock 1 - Imported Questions (Phase 5, part 1: VR + DM)\n",
             "Source: PMT UCAT Mock Examination 1 (placeholder demo content, tagged PMT-M1).\n",
             f"**Verbal Reasoning:** {len(vr_q)} items (44 source questions across 11 passages)",
             f"**Decision Making:** {len(dm_q)} items (22 MCQ + {len(dm_q)-22} Yes/No items from 7 statement questions)\n",
             "\n_Flags: VR passage 1 (VRTF0024) duplicates its statement as Q3 & Q4 with different answers "
             "(PMT error, transferred verbatim). VR Q21 mark scheme was garbled ('Cryptanalysis'); the correct "
             "answer per the passage is Guillaume Apollinaire. DM Q20 (DMDR0005) mark scheme was garbled; Yes/No "
             "answers derived logically._\n",
             "\n---\n## Verbal Reasoning\n"]
    for q in vr_q:
        code = q["ref"].split(" ")[1]
        lines.append(f"\n**{q['number']}. ({code})** {q['stem']}")
        for opt in q["options"]:
            lines.append(f"- {opt['text']}{'  ✅' if opt['correct'] else ''}")
    lines.append("\n---\n## Decision Making\n")
    for q in dm_q:
        lines.append(f"\n**{q['number']}.** {q['stem']}{'  `[image]`' if q.get('image') else ''}")
        for opt in q["options"]:
            lines.append(f"- {opt['text']}{'  ✅' if opt['correct'] else ''}")
    with open(os.path.join(ROOT, "imported_questions_review", "mock1.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"VR items: {len(vr_q)} | DM items: {len(dm_q)}")
    print("DM by subtopic:", dict(Counter(q["subtopic"] for q in dm_q)))


def _write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    build()
