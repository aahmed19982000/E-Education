from django.core.management import call_command
from django.core.management.base import BaseCommand

from articles.models import Article
from levels.models import Level
from quiz.models import Question

LEVELS = [
    dict(order=1, code="A1", name_ar="المستوى الأول: التأسيس", name_en="Level 1: Foundations",
         description_ar="أساسيات القواعد والمفردات للمبتدئين تمامًا.", description_en="Core grammar and vocabulary for absolute beginners.",
         duration_ar="4 أسابيع · 8 جلسات", duration_en="4 weeks · 8 sessions", price_group=1200, price_private=2400),
    dict(order=2, code="A2", name_ar="المستوى الثاني: الأساسيات المتقدمة", name_en="Level 2: Elementary",
         description_ar="بناء جمل أطول والتحدث في مواقف يومية.", description_en="Building longer sentences for everyday situations.",
         duration_ar="4 أسابيع · 8 جلسات", duration_en="4 weeks · 8 sessions", price_group=1300, price_private=2600),
    dict(order=3, code="B1", name_ar="المستوى الثالث: ما قبل المتوسط", name_en="Level 3: Pre-Intermediate",
         description_ar="التعبير عن الرأي ومناقشة مواضيع متنوعة.", description_en="Expressing opinions and discussing varied topics.",
         duration_ar="4 أسابيع · 8 جلسات", duration_en="4 weeks · 8 sessions", price_group=1400, price_private=2800),
    dict(order=4, code="B2", name_ar="المستوى الرابع: المتوسط", name_en="Level 4: Intermediate",
         description_ar="طلاقة أكبر في الكتابة والمحادثة المهنية.", description_en="Greater fluency in writing and professional talk.",
         duration_ar="5 أسابيع · 10 جلسات", duration_en="5 weeks · 10 sessions", price_group=1500, price_private=3000),
    dict(order=5, code="C1", name_ar="المستوى الخامس: فوق المتوسط", name_en="Level 5: Upper-Intermediate",
         description_ar="تحليل نصوص معقدة والتحدث بثقة في العمل.", description_en="Analyzing complex texts, speaking confidently at work.",
         duration_ar="5 أسابيع · 10 جلسات", duration_en="5 weeks · 10 sessions", price_group=1600, price_private=3200),
    dict(order=6, code="C2", name_ar="المستوى السادس: المتقدم", name_en="Level 6: Advanced",
         description_ar="إتقان قريب من اللغة الأم في جميع المهارات.", description_en="Near-native command across all language skills.",
         duration_ar="6 أسابيع · 12 جلسة", duration_en="6 weeks · 12 sessions", price_group=1700, price_private=3400),
]

ARTICLES = [
    dict(order=1, category_ar="قواعد", category_en="Grammar",
         title_ar="الفرق بين Present Perfect و Past Simple", title_en="Present Perfect vs Past Simple",
         excerpt_ar="شرح مبسط للفرق بين الزمنين مع أمثلة عملية من الحياة اليومية.", excerpt_en="A simple explanation of the two tenses with everyday examples.",
         read_time_ar="5 دقائق قراءة", read_time_en="5 min read"),
    dict(order=2, category_ar="مفردات", category_en="Vocabulary",
         title_ar="50 كلمة إنجليزية تستخدم يوميًا في العمل", title_en="50 English words used daily at work",
         excerpt_ar="قائمة مفردات أساسية لبيئة العمل مع طريقة استخدام كل كلمة.", excerpt_en="Essential workplace vocabulary with usage notes.",
         read_time_ar="7 دقائق قراءة", read_time_en="7 min read"),
    dict(order=3, category_ar="اختبارات دولية", category_en="International Exams",
         title_ar="كيف تجهز لامتحان IELTS في 3 أشهر", title_en="How to prepare for IELTS in 3 months",
         excerpt_ar="خطة أسبوعية مبسطة للتحضير لاختبار IELTS بدون ضغط.", excerpt_en="A simple weekly plan to prepare for IELTS without stress.",
         read_time_ar="8 دقائق قراءة", read_time_en="8 min read"),
    dict(order=4, category_ar="إنجليزي الأعمال", category_en="Business English",
         title_ar="عبارات أساسية لمقابلات العمل بالإنجليزي", title_en="Key phrases for English job interviews",
         excerpt_ar="جمل جاهزة تساعدك على الرد بثقة في مقابلات العمل.", excerpt_en="Ready phrases to help you answer confidently in interviews.",
         read_time_ar="6 دقائق قراءة", read_time_en="6 min read"),
    dict(order=5, category_ar="النطق", category_en="Pronunciation",
         title_ar="5 أخطاء شائعة في النطق وكيف تتجنبها", title_en="5 common pronunciation mistakes to avoid",
         excerpt_ar="الأخطاء الأكثر شيوعًا بين المتعلمين العرب وطرق تصحيحها.", excerpt_en="The most common mistakes among Arabic speakers and fixes.",
         read_time_ar="4 دقائق قراءة", read_time_en="4 min read"),
    dict(order=6, category_ar="نصائح دراسية", category_en="Study Tips",
         title_ar="أفضل طريقة لحفظ المفردات بدون نسيان", title_en="The best way to memorize vocabulary",
         excerpt_ar="تقنية التكرار المتباعد وكيف تطبقها في تعلم الإنجليزية.", excerpt_en="Spaced repetition and how to apply it to English learning.",
         read_time_ar="5 دقائق قراءة", read_time_en="5 min read"),
]

class Command(BaseCommand):
    help = "Seed levels and articles, and load the placement test if the quiz is empty."

    def handle(self, *args, **options):
        for data in LEVELS:
            Level.objects.update_or_create(code=data["code"], defaults=data)
        self.stdout.write(self.style.SUCCESS(f"Levels: {len(LEVELS)}"))

        for data in ARTICLES:
            Article.objects.update_or_create(title_en=data["title_en"], defaults=data)
        self.stdout.write(self.style.SUCCESS(f"Articles: {len(ARTICLES)}"))

        # Never touches existing questions: the real placement test is loaded only into an empty quiz.
        if Question.objects.exists():
            self.stdout.write(f"Quiz questions: {Question.objects.count()} already exist, left unchanged.")
        else:
            call_command("load_placement_test", stdout=self.stdout)
