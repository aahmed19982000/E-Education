from django.core.management.base import BaseCommand

from team.models import TeamMember, TeamReview

PREFIX = "demo-"

TEACHERS = [
    dict(
        slug="demo-sara-ali", order=1,
        name_ar="سارة علي", name_en="Sara Ali",
        role_ar="مدرسة لغة إنجليزية", role_en="English Teacher",
        specialties_ar="IELTS، المحادثة، الكتابة الأكاديمية", specialties_en="IELTS, Speaking, Academic Writing",
        bio_ar="خبرة 8 سنوات في تدريس الإنجليزية للكبار والشباب.\nحاصلة على شهادة CELTA وتركّز على بناء الطلاقة في المحادثة.",
        bio_en="8 years of experience teaching English to adults and young learners.\nCELTA certified, with a focus on building speaking fluency.",
        reviews=[
            ("منى حسن", 5, "شرحها بسيط وبتشجعني أتكلم من أول جلسة. مستواي في المحادثة اتحسن جدًا."),
            ("كريم سمير", 5, "جهّزتني لـ IELTS في شهرين وجبت 7 في الاختبار."),
            ("ياسمين طارق", 4, "مدرسة محترمة ومنظمة، وأتمنى جلسات أطول شوية."),
        ],
    ),
    dict(
        slug="demo-omar-khaled", order=2,
        name_ar="عمر خالد", name_en="Omar Khaled",
        role_ar="مدرس قواعد ومفردات", role_en="Grammar & Vocabulary Teacher",
        specialties_ar="القواعد، المفردات، المبتدئين", specialties_en="Grammar, Vocabulary, Beginners",
        bio_ar="متخصص في تأسيس المبتدئين وتبسيط القواعد بأمثلة من الحياة اليومية.",
        bio_en="Specialist in building foundations for beginners, simplifying grammar with everyday examples.",
        reviews=[
            ("أحمد فؤاد", 5, "أول مرة أفهم الأزمنة بشكل واضح. شكرًا يا أستاذ عمر."),
            ("هدى مصطفى", 5, "صبور جدًا ومع كل سؤال بيدي مثال جديد."),
        ],
    ),
    dict(
        slug="demo-nour-mahmoud", order=3,
        name_ar="نور محمود", name_en="Nour Mahmoud",
        role_ar="مدرسة إنجليزي للأطفال", role_en="Kids English Teacher",
        specialties_ar="الأطفال، الفونكس، القصص التفاعلية", specialties_en="Kids, Phonics, Interactive Storytelling",
        bio_ar="تعلّم الأطفال بالألعاب والقصص، وتساعدهم يحبوا اللغة من البداية.",
        bio_en="Teaches children through games and stories, helping them love the language from day one.",
        reviews=[("والدة آدم", 5, "ابني بقى يستنى حصة الإنجليزي كل أسبوع!")],
    ),
    dict(
        slug="demo-hassan-adel", order=4,
        name_ar="حسن عادل", name_en="Hassan Adel",
        role_ar="مدرس إنجليزي للأعمال", role_en="Business English Teacher",
        specialties_ar="إنجليزي الأعمال، المقابلات الوظيفية، الإيميلات", specialties_en="Business English, Job Interviews, Emails",
        bio_ar="عمل 10 سنوات في شركات دولية، ويدرّب الموظفين على التواصل المهني بالإنجليزية.",
        bio_en="10 years in international companies, coaching professionals on workplace English.",
        reviews=[],
    ),
]


class Command(BaseCommand):
    help = "Add demo teachers and reviews (slugs start with 'demo-'). Use --remove to delete them."

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="Delete all demo team members and their reviews.")

    def handle(self, *args, **options):
        if options["remove"]:
            deleted, _ = TeamMember.objects.filter(slug__startswith=PREFIX).delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {deleted} demo objects."))
            return

        for data in TEACHERS:
            data = dict(data)
            reviews = data.pop("reviews")
            member, _ = TeamMember.objects.update_or_create(slug=data.pop("slug"), defaults=data)
            member.reviews.all().delete()
            for i, (student, rating, text) in enumerate(reviews):
                TeamReview.objects.create(member=member, order=i, student_name=student, rating=rating, text=text)
        self.stdout.write(self.style.SUCCESS(f"Demo team: {len(TEACHERS)} teachers added."))
