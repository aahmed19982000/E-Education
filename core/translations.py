"""Bilingual UI copy for the site, ported from the original design.

Business content that lives in the database (levels, articles, quiz
questions) is NOT here — only static interface strings (nav, headings,
labels) that don't need an editor.
"""

AR = {
    "brand": "أكاديمية E-Education",
    "langToggle": "EN",
    "imgHeroAlt": "صورة طلاب يتعلمون أونلاين",
    "imgAboutAlt": "صورة فريق الأكاديمية",
    "imgTeachersAlt": "صورة ورشة تدريب معلمين",
    "nav": {
        "home": "الرئيسية", "about": "عن الأكاديمية", "levels": "المستويات والأسعار",
        "teachers": "ورش المدرسين", "test": "اختبار المستوى", "articles": "مقالات",
        "contact": "تواصل معنا", "login": "تسجيل الدخول", "logout": "تسجيل الخروج", "cta": "اختبار مجاني",
    },
    "home": {
        "eyebrow": "تعلّم الإنجليزية بخطة واضحة",
        "title": "ارتقِ بلغتك الإنجليزية بخطوات مضمونة، من مستواك الحالي حتى الاحتراف",
        "subtitle": "دورات تفاعلية للطلاب، وورش تخصصية للمدرسين الراغبين في الانتقال للمدارس الدولية. ابدأ باختبار تحديد مستوى مجاني.",
        "cta1": "ابدأ اختبار تحديد المستوى", "cta2": "تصفح المستويات والأسعار",
        "stats": [{"value": "+2,400", "label": "طالب وطالبة"}, {"value": "+60", "label": "مدرس معتمد"}, {"value": "96%", "label": "نسبة رضا الطلاب"}],
        "students": {"title": "أنا طالب أريد تعلّم الإنجليزية", "desc": "اختبر مستواك مجانًا، واشترك في المستوى المناسب لك بشكل فردي أو جماعي، وتابع تقدمك خطوة بخطوة.", "cta": "شاهد المستويات"},
        "teachers": {"title": "أنا مدرس وأريد التطور مهنيًا", "desc": "ورشة متخصصة للمدرسين الراغبين في الانتقال من المدارس المحلية إلى المدارس الدولية، بشهادة معتمدة.", "cta": "تعرف على الورشة"},
        "howTitle": "كيف تبدأ؟",
        "steps": [
            {"n": "1", "title": "اختبار تحديد المستوى", "desc": "اختبار مجاني قصير يحدد مستواك الحالي بدقة."},
            {"n": "2", "title": "اختيار المستوى المناسب", "desc": "اختر بين نظام الجروب أو الخصوصي بالسعر الذي يناسبك."},
            {"n": "3", "title": "ابدأ التعلم", "desc": "جلسات تفاعلية منظمة مع متابعة مستمرة لتقدمك."},
        ],
        "articlesTitle": "مقالات مختارة", "articlesAll": "عرض كل المقالات",
        "bannerTitle": "لسه مش عارف مستواك؟", "bannerSubtitle": "اختبار تحديد المستوى مجاني ويستغرق دقائق معدودة.",
    },
    "about": {
        "title": "عن أكاديمية E-Education",
        "story": "أسسنا الأكاديمية لتقديم تعليم إنجليزي عملي وموجه بالنتائج، لفئتين مختلفتين من المتعلمين: طلاب يريدون تحسين لغتهم للعمل والدراسة، ومدرسين يريدون الانتقال إلى بيئة تدريس دولية. نؤمن أن كل متعلم يحتاج مسارًا مختلفًا، لذلك صممنا برامجنا حول اختبار تحديد مستوى دقيق ومتابعة فردية.",
        "values": [
            {"title": "جودة التدريس", "desc": "مدرسون مؤهلون يخضعون لتدريب داخلي مستمر."},
            {"title": "مسار واضح", "desc": "مستويات متتالية بأهداف محددة لكل مرحلة."},
            {"title": "مرونة", "desc": "اختيار بين الجروب والخصوصي وبين المواعيد المناسبة."},
            {"title": "محتوى داعم", "desc": "مقالات ومصادر مجانية لدعم التعلم بين الجلسات."},
        ],
        "teacherQuality": "نختار مدرسينا وفق معايير تدريس دولية، ويحصلون على تدريب دوري لتطوير أدائهم. هذا ينعكس مباشرة على جودة الجلسات وسرعة تقدم الطلاب.",
    },
    "levels": {
        "title": "المستويات والأسعار", "subtitle": "اختر بين نظام الجروب أو الخصوصي حسب ما يناسبك",
        "group": "نظام الجروب", "private": "نظام الخصوصي", "subscribe": "اشترك الآن",
        "footnote": "الأسعار بالجنيه المصري وتشمل جميع مواد المستوى.", "currency": "ج.م",
    },
    "teachers": {
        "title": "ورشة المدرسين: من المحلي إلى الدولي",
        "intro": "ورشة متخصصة لمدرسي اللغة الإنجليزية الراغبين في الانتقال من مدارس محلية إلى مدارس دولية (IB، بريطاني، أمريكي). تغطي الورشة المناهج الدولية، أساليب التدريس التفاعلي، ومهارات التقديم للوظائف الدولية.",
        "cta": "سجّل اهتمامك بالورشة",
        "details": [
            {"label": "المدة", "value": "6 أسابيع"},
            {"label": "الصيغة", "value": "جلسات أونلاين مباشرة، مرتين أسبوعيًا"},
            {"label": "الشهادة", "value": "شهادة معتمدة من الأكاديمية"},
            {"label": "السعر", "value": "1,800 ج.م"},
            {"label": "المواعيد", "value": "دفعات جديدة كل شهر"},
        ],
        "curriculumTitle": "محتوى الورشة",
        "curriculum": ["مناهج دولية (IB / British / American)", "استراتيجيات تدريس تفاعلي", "معايير تقييم الطلاب دوليًا", "تحضير سيرة ذاتية دولية", "مهارات المقابلات الدولية"],
    },
    "test": {
        "introTitle": "اختبار تحديد المستوى المجاني",
        "introDesc": "6 أسئلة تغطي القواعد والقراءة والاستماع، تستغرق حوالي 5 دقائق، وتعطيك تقديرًا فوريًا لمستواك.",
        "infoItems": ["مجاني بالكامل", "6 أسئلة فقط", "نتيجة فورية"],
        "startBtn": "ابدأ الاختبار الآن",
        "resultEyebrow": "نتيجتك المبدئية",
        "resultDesc": "هذه نتيجة تقريبية بناءً على إجاباتك. يمكنك الاشتراك في هذا المستوى مباشرة أو مراجعته مع فريقنا.",
        "resultCta": "شاهد تفاصيل هذا المستوى",
    },
    "articles": {
        "title": "مقالات ومصادر تعلم اللغة الإنجليزية", "subtitle": "محتوى مجاني يدعم رحلتك في تعلم الإنجليزية",
        "back": "‹ رجوع للمقالات",
        "bodyPlaceholder": "[ نص المقال الكامل يوضع هنا بعد المراجعة النهائية للمحتوى. ]",
    },
    "contact": {
        "title": "تواصل معنا", "subtitle": "هل عندك سؤال عن المستويات أو ورشة المدرسين؟ راسلنا.",
        "name": "الاسم", "email": "البريد الإلكتروني", "phone": "رقم الهاتف", "message": "رسالتك", "submit": "إرسال الرسالة",
        "successTitle": "تم إرسال رسالتك", "successDesc": "سيتواصل معك فريقنا في أقرب وقت ممكن.",
        "info": [{"label": "الهاتف", "value": "01000 000 000"}, {"label": "البريد الإلكتروني", "value": "info@e-education.academy"}, {"label": "مواعيد العمل", "value": "يوميًا من 10ص حتى 10م"}],
    },
    "auth": {
        "login": "تسجيل الدخول", "register": "حساب جديد", "name": "الاسم الكامل", "email": "البريد الإلكتروني",
        "phone": "رقم الهاتف", "password": "كلمة المرور", "password2": "تأكيد كلمة المرور",
        "loginBtn": "دخول", "registerBtn": "إنشاء حساب",
    },
    "footer": {
        "tagline": "منصة تعليم إنجليزي للطلاب والمدرسين، تبدأ باختبار تحديد مستوى مجاني.",
        "linksTitle": "روابط سريعة", "copyright": "© 2026 أكاديمية E-Education. جميع الحقوق محفوظة.",
    },
}

EN = {
    "brand": "E-Education Academy",
    "langToggle": "AR",
    "imgHeroAlt": "students learning online",
    "imgAboutAlt": "academy team",
    "imgTeachersAlt": "teacher training workshop",
    "nav": {
        "home": "Home", "about": "About", "levels": "Levels & Pricing",
        "teachers": "Teacher Track", "test": "Level Test", "articles": "Articles",
        "contact": "Contact", "login": "Log in", "logout": "Log out", "cta": "Free level test",
    },
    "home": {
        "eyebrow": "Learn English with a clear plan",
        "title": "Advance your English with a guaranteed path, from where you are now to fluency",
        "subtitle": "Interactive courses for students, and specialized workshops for teachers moving to international schools. Start with a free level test.",
        "cta1": "Start the level test", "cta2": "Browse levels & pricing",
        "stats": [{"value": "2,400+", "label": "students"}, {"value": "60+", "label": "certified teachers"}, {"value": "96%", "label": "student satisfaction"}],
        "students": {"title": "I'm a student learning English", "desc": "Test your level for free, join the right level in a group or private track, and track your progress step by step.", "cta": "See levels"},
        "teachers": {"title": "I'm a teacher growing my career", "desc": "A dedicated workshop for teachers moving from local to international schools, with a certificate.", "cta": "See the workshop"},
        "howTitle": "How it works",
        "steps": [
            {"n": "1", "title": "Free level test", "desc": "A short free test that pinpoints your current level."},
            {"n": "2", "title": "Pick your level", "desc": "Choose group or private pricing to fit your budget."},
            {"n": "3", "title": "Start learning", "desc": "Structured interactive sessions with ongoing progress tracking."},
        ],
        "articlesTitle": "Featured articles", "articlesAll": "View all articles",
        "bannerTitle": "Not sure of your level yet?", "bannerSubtitle": "The level test is free and takes just a few minutes.",
    },
    "about": {
        "title": "About E-Education Academy",
        "story": "We built this academy to deliver practical, results-driven English education to two kinds of learners: students improving their English for work and study, and teachers moving into international teaching environments. Every learner needs a different path, so our programs start with an accurate level test and individual follow-up.",
        "values": [
            {"title": "Teaching quality", "desc": "Qualified teachers with continuous internal training."},
            {"title": "A clear path", "desc": "Sequential levels with a defined goal at each stage."},
            {"title": "Flexibility", "desc": "Choose group or private, and the schedule that fits you."},
            {"title": "Supporting content", "desc": "Free articles and resources between sessions."},
        ],
        "teacherQuality": "Our teachers are selected against international teaching standards and receive regular training. This shows directly in session quality and how fast students progress.",
    },
    "levels": {
        "title": "Levels & Pricing", "subtitle": "Choose group or private pricing based on what suits you",
        "group": "Group", "private": "Private", "subscribe": "Subscribe now",
        "footnote": "Prices in Egyptian pounds, all level materials included.", "currency": "EGP",
    },
    "teachers": {
        "title": "Teacher Track: Local to International",
        "intro": "A dedicated workshop for English teachers moving from local schools to international ones (IB, British, American). It covers international curricula, interactive teaching methods, and international job application skills.",
        "cta": "Register your interest",
        "details": [
            {"label": "Duration", "value": "6 weeks"},
            {"label": "Format", "value": "Live online sessions, twice a week"},
            {"label": "Certificate", "value": "Academy-accredited certificate"},
            {"label": "Price", "value": "EGP 1,800"},
            {"label": "Start dates", "value": "New cohort every month"},
        ],
        "curriculumTitle": "Workshop content",
        "curriculum": ["International curricula (IB / British / American)", "Interactive teaching strategies", "International assessment standards", "International CV preparation", "International interview skills"],
    },
    "test": {
        "introTitle": "Free level test",
        "introDesc": "6 questions covering grammar, reading and listening, about 5 minutes, with an instant estimate of your level.",
        "infoItems": ["Completely free", "Just 6 questions", "Instant result"],
        "startBtn": "Start the test",
        "resultEyebrow": "Your initial result",
        "resultDesc": "This is an approximate result based on your answers. You can subscribe to this level directly or review it with our team.",
        "resultCta": "See this level's details",
    },
    "articles": {
        "title": "English learning articles & resources", "subtitle": "Free content to support your English learning journey",
        "back": "‹ Back to articles",
        "bodyPlaceholder": "[ Full article text goes here after final content review. ]",
    },
    "contact": {
        "title": "Contact us", "subtitle": "Have a question about levels or the teacher workshop? Reach out.",
        "name": "Name", "email": "Email", "phone": "Phone number", "message": "Your message", "submit": "Send message",
        "successTitle": "Message sent", "successDesc": "Our team will get back to you shortly.",
        "info": [{"label": "Phone", "value": "01000 000 000"}, {"label": "Email", "value": "info@e-education.academy"}, {"label": "Hours", "value": "Daily, 10am–10pm"}],
    },
    "auth": {
        "login": "Log in", "register": "New account", "name": "Full name", "email": "Email",
        "phone": "Phone number", "password": "Password", "password2": "Confirm password",
        "loginBtn": "Log in", "registerBtn": "Create account",
    },
    "footer": {
        "tagline": "An English learning platform for students and teachers, starting with a free level test.",
        "linksTitle": "Quick links", "copyright": "© 2026 E-Education Academy. All rights reserved.",
    },
}

LEVEL_NAMES = {
    "ar": ["A1 — التأسيس", "A2 — الأساسيات المتقدمة", "B1 — ما قبل المتوسط", "B2 — المتوسط", "C1 — فوق المتوسط", "C2 — المتقدم"],
    "en": ["A1 — Foundations", "A2 — Elementary", "B1 — Pre-Intermediate", "B2 — Intermediate", "C1 — Upper-Intermediate", "C2 — Advanced"],
}


def get_translations(lang):
    return AR if lang == "ar" else EN
