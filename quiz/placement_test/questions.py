"""The academy's English placement test: 30 questions from A1 to C2.

Each entry lists the correct answer first; the loader shuffles the options
(with a fixed seed, so the order is the same every time it's loaded).
Grammar and vocabulary items get an Arabic instruction in Arabic mode;
reading and listening items are in English for both languages, as the
comprehension itself is what's being tested.

`level` drives the per-question marks (used when grading per question):
A1/A2 = 1, B1/B2 = 2, C1/C2 = 3.
"""

CATEGORIES = {
    "grammar": ("قواعد", "Grammar"),
    "vocabulary": ("مفردات", "Vocabulary"),
    "reading": ("قراءة", "Reading"),
    "listening": ("استماع", "Listening"),
}

POINTS = {"A1": 1, "A2": 1, "B1": 2, "B2": 2, "C1": 3, "C2": 3}

CHOOSE_AR = "اختر الإجابة الصحيحة: "
CHOOSE_EN = "Choose the correct answer: "

READING_1 = (
    "Maria started working at a small bakery in Alexandria three years ago. At first, she only "
    "cleaned the kitchen and served customers, but she watched the bakers carefully and practised "
    "at home every weekend. Last month, the owner asked her to create a new cake for the shop's "
    "anniversary. It sold out in two hours, and now Maria bakes every morning from 5 a.m."
)

READING_2 = (
    "Remote work was once seen as a perk offered by a handful of technology firms. Today, many "
    "organisations treat it as standard practice. Supporters argue that it saves commuting time and "
    "widens the pool of potential employees. Critics, however, point out that spontaneous "
    "collaboration suffers when colleagues rarely meet, and that new staff in particular may "
    "struggle to absorb a company's culture. As a result, a growing number of employers are "
    "settling on hybrid arrangements, hoping to capture the benefits of both models."
)

LISTENING_1 = {
    "file": "restaurant_booking.mp3",
    "label_ar": "محادثة هاتفية: حجز طاولة في مطعم",
    "label_en": "Phone call: booking a restaurant table",
}

LISTENING_2 = {
    "file": "training_day_announcement.mp3",
    "label_ar": "إعلان في بداية يوم تدريبي",
    "label_en": "Announcement at the start of a training day",
}

READING_SECONDS = 90
LISTENING_SECONDS = 120


def grammar(level, sentence, answer, *wrong):
    return dict(kind="grammar", level=level, text_ar=CHOOSE_AR + sentence, text_en=CHOOSE_EN + sentence,
                options=[answer, *wrong])


def vocab(level, text_ar, text_en, answer, *wrong):
    return dict(kind="vocabulary", level=level, text_ar=text_ar, text_en=text_en, options=[answer, *wrong])


def reading(level, passage, question, answer, *wrong):
    return dict(kind="reading", level=level, passage=passage, text_ar=question, text_en="",
                options=[answer, *wrong], seconds=READING_SECONDS)


def listening(level, clip, question, answer, *wrong):
    return dict(kind="listening", level=level, audio=clip, text_ar=question, text_en="",
                options=[answer, *wrong], seconds=LISTENING_SECONDS)


QUESTIONS = [
    # --- A1 -------------------------------------------------------------------
    grammar("A1", "My sister ___ a doctor.", "is", "are", "am", "be"),
    grammar("A1", "___ you like coffee?", "Do", "Does", "Are", "Is"),
    vocab("A1", "اختر عكس كلمة «cold»:", "Choose the opposite of “cold”:", "hot", "old", "tall", "slow"),

    # --- A2 -------------------------------------------------------------------
    grammar("A2", "Yesterday we ___ to the cinema.", "went", "go", "gone", "going"),
    grammar("A2", "This bag is ___ than that one.", "heavier", "heavy", "more heavy", "heaviest"),
    vocab("A2", CHOOSE_AR + "I need to ___ an appointment with the dentist.",
          CHOOSE_EN + "I need to ___ an appointment with the dentist.", "make", "do", "take", "go"),

    reading("A2", READING_1, "What did Maria do when she first started at the bakery?",
            "She cleaned the kitchen and served customers.", "She baked bread every morning.",
            "She managed the shop.", "She delivered cakes to customers."),
    reading("B1", READING_1, "How did Maria learn to bake?",
            "By watching the bakers and practising at home.", "By taking a course at a cooking school.",
            "Her mother taught her when she was young.", "The owner trained her every weekend."),
    reading("B1", READING_1, "What happened to the cake Maria created?",
            "It sold out in two hours.", "Nobody wanted to buy it.",
            "It won a prize at the anniversary.", "The owner decided not to sell it."),

    listening("A2", LISTENING_1, "How many people is the table for?", "Four", "Two", "Eight", "Nine"),
    listening("B1", LISTENING_1, "What time is the table booked for?", "7:30", "8:00", "9:00", "7:00"),

    # --- B1 -------------------------------------------------------------------
    grammar("B1", "I have lived here ___ 2015.", "since", "for", "from", "at"),
    grammar("B1", "If it rains tomorrow, we ___ at home.", "will stay", "would stay", "stayed", "had stayed"),
    vocab("B1", CHOOSE_AR + "Can you ___ me some money until Friday?",
          CHOOSE_EN + "Can you ___ me some money until Friday?", "lend", "borrow", "owe", "rent"),
    vocab("B1", CHOOSE_AR + "She's very ___ — she always tells the truth.",
          CHOOSE_EN + "She's very ___ — she always tells the truth.", "honest", "polite", "generous", "patient"),

    # --- B2 -------------------------------------------------------------------
    grammar("B2", "The report ___ by the manager before the meeting started.",
            "had been checked", "has checked", "was checking", "had checked"),
    grammar("B2", "If I ___ about the traffic, I would have left earlier.",
            "had known", "knew", "have known", "would know"),
    vocab("B2", CHOOSE_AR + "The new rules will ___ effect next month.",
          CHOOSE_EN + "The new rules will ___ effect next month.", "take", "make", "give", "put"),
    vocab("B2", "أقرب معنى لكلمة «reluctant»:", "The closest meaning to “reluctant” is:",
          "unwilling", "eager", "careful", "unable"),

    reading("B2", READING_2, "According to the text, how has the view of remote work changed?",
            "It went from a rare perk to standard practice.", "It has become much less popular.",
            "It is now offered only by technology firms.", "It has always been standard practice."),
    reading("C1", READING_2, "Who may find remote work particularly difficult, according to critics?",
            "New members of staff", "Senior managers", "Technology companies", "People with long commutes"),
    reading("C1", READING_2, "In the text, “settling on” is closest in meaning to:",
            "deciding on after consideration", "rejecting completely", "postponing", "complaining about"),

    listening("B2", LISTENING_2, "Why has the presentation skills workshop been moved?",
              "The trainer's train has been delayed.", "The trainer is ill.",
              "The main hall is not available.", "Not enough people signed up."),
    listening("C1", LISTENING_2, "When will the certificates be handed out?",
              "At the end of the day", "After each session", "During lunch", "Next week by email"),

    # --- C1 -------------------------------------------------------------------
    grammar("C1", "Not only ___ late, but he also forgot the documents.",
            "did he arrive", "he arrived", "he did arrive", "arrived he"),
    grammar("C1", "It's high time we ___ a decision.", "made", "make", "will make", "have made"),
    vocab("C1", CHOOSE_AR + "The results were ___, so no firm conclusions could be drawn.",
          CHOOSE_EN + "The results were ___, so no firm conclusions could be drawn.",
          "inconclusive", "inevitable", "indispensable", "insistent"),

    # --- C2 -------------------------------------------------------------------
    grammar("C2", "___ the company to fail, hundreds of jobs would be lost.", "Were", "Should", "Had", "If"),
    grammar("C2", "The proposal, ___ merits were widely acknowledged, was nevertheless rejected.",
            "whose", "which", "that", "its"),
    vocab("C2", CHOOSE_AR + "His explanation was so ___ that nobody could follow it.",
          CHOOSE_EN + "His explanation was so ___ that nobody could follow it.",
          "convoluted", "concise", "candid", "cogent"),
]
