"""Demo courses to try the whole flow: catalog, groups/private cohorts, sessions, a student.

Safe to re-run (everything is keyed by a `demo-` slug / email) and `--reset`
removes only what this command created. Demo team members come from
`seed_demo_team`; run that first to have teachers to pick.
"""
import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import Attendance, Cohort, CohortSlot, Course, Enrollment, EnrollmentRequest
from team.models import TeamMember

DEMO_EMAIL = "demo-student@example.com"
DEMO_PASSWORD = "demo-pass-12345"

COURSES = [
    dict(
        slug="demo-english-speaking", audience=Course.AUDIENCE_STUDENTS,
        title_ar="الإنجليزية للمحادثة اليومية", title_en="Everyday English Conversation",
        description_ar="كورس لايف لتكوين الطلاقة في الكلام: مواقف حقيقية، تصحيح فوري، ومتابعة بعد كل جلسة.",
        description_en="A live course to build speaking fluency: real situations, instant correction and follow-up after every session.",
        offers_group=True, offers_semi_private=True, offers_private=True,
        price_group=600, price_semi_private=900, price_private=1500,
    ),
    dict(
        slug="demo-ielts-prep", audience=Course.AUDIENCE_STUDENTS,
        title_ar="التحضير لاختبار IELTS", title_en="IELTS Preparation",
        description_ar="تدريب على الأقسام الأربعة (استماع، قراءة، كتابة، محادثة) مع اختبارات تجريبية وتقييم فردي.",
        description_en="Training on all four sections (listening, reading, writing, speaking) with mock tests and individual feedback.",
        offers_group=True, offers_semi_private=True, offers_private=True,
        price_group=900, price_semi_private=1400, price_private=2200,
    ),
    dict(
        slug="demo-teacher-international", audience=Course.AUDIENCE_TEACHERS,
        title_ar="مسار المدرس للمدارس الدولية", title_en="International Schools Teacher Track",
        description_ar="تطوير مهارات التدريس بالإنجليزية وإدارة الفصل وتخطيط الدروس للانتقال من المدارس المحلية للدولية.",
        description_en="Build teaching skills in English, classroom management and lesson planning for moving from local to international schools.",
        offers_group=True, offers_private=True, price_group=1800, price_private=4000,
    ),
    dict(
        slug="demo-teacher-workshop", audience=Course.AUDIENCE_TEACHERS,
        title_ar="ورشة أنشطة الفصل التفاعلية", title_en="Interactive Classroom Activities Workshop",
        description_ar="ورشة عملية قصيرة على أنشطة تفاعلية جاهزة للتطبيق في الحصة من أول يوم.",
        description_en="A short hands-on workshop on interactive activities you can use in class from day one.",
        offers_group=True, offers_private=False, price_group=700, price_private=None,
    ),
]

# course slug -> cohorts; (name, mode, teacher slug, weekly slots (weekday, "HH:MM", minutes), weeks)
COHORTS = {
    "demo-english-speaking": [
        ("مجموعة السبت والثلاثاء مساءً", "group", "demo-sara-ali", [(5, "19:00", 60), (1, "19:00", 60)], 6),
        ("مجموعة الأحد والأربعاء صباحًا", "group", "demo-omar-khaled", [(6, "10:00", 60), (2, "10:00", 60)], 6),
        ("مجموعة Semi private — 3 طلاب", "semi_private", "demo-omar-khaled", [(0, "20:00", 60), (3, "20:00", 60)], 6),
        ("جلسات خصوصية — طالب واحد", "private", "demo-sara-ali", [(3, "21:00", 45)], 4),
    ],
    "demo-ielts-prep": [
        ("مجموعة IELTS الأسبوعية", "group", "demo-sara-ali", [(4, "17:00", 90)], 8),
    ],
    "demo-teacher-international": [
        ("دفعة المدرسين — مساء الاثنين", "group", "demo-nour-mahmoud", [(0, "20:00", 90)], 8),
    ],
}


def next_weekday(weekday):
    today = datetime.date.today()
    return today + datetime.timedelta(days=(weekday - today.weekday()) % 7 or 7)


class Command(BaseCommand):
    help = "Create demo courses, cohorts with weekly sessions, a demo student and sample requests."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete the demo data instead of creating it")

    def handle(self, *args, **options):
        if options["reset"]:
            Course.objects.filter(slug__startswith="demo-").delete()
            EnrollmentRequest.objects.filter(email__endswith="@example.com").delete()
            User.objects.filter(email__endswith="@example.com", email__startswith="demo-").delete()
            self.stdout.write(self.style.SUCCESS("Demo courses removed."))
            return

        teachers = {m.slug: m for m in TeamMember.objects.filter(slug__startswith="demo-")}
        if not teachers:
            self.stdout.write(self.style.WARNING("No demo teachers found (run seed_demo_team first); cohorts get no teacher."))

        courses = {}
        for data in COURSES:
            slug = data.pop("slug")
            course, _ = Course.objects.update_or_create(slug=slug, defaults={**data, "is_published": True})
            courses[slug] = course
            data["slug"] = slug

        cohorts = {}
        for slug, specs in COHORTS.items():
            for name, mode, teacher_slug, slots, weeks in specs:
                first_day = min(next_weekday(wd) for wd, _t, _m in slots)
                cohort, _ = Cohort.objects.update_or_create(
                    course=courses[slug], name=name,
                    defaults=dict(mode=mode, teacher=teachers.get(teacher_slug), start_date=first_day, weeks=weeks,
                                  **({"min_students": 2, "max_students": 3} if mode == "semi_private" else {})),
                )
                for weekday, hhmm, minutes in slots:
                    CohortSlot.objects.update_or_create(
                        cohort=cohort, weekday=weekday, start_time=datetime.time.fromisoformat(hhmm),
                        defaults={"duration_minutes": minutes},
                    )
                cohort.generate_lessons()
                cohorts[name] = cohort

        # A demo student placed in the first group, with the first session marked present.
        user, created = User.objects.get_or_create(
            username=DEMO_EMAIL, defaults=dict(email=DEMO_EMAIL, first_name="طالب", last_name="تجريبي"))
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        group = cohorts["مجموعة السبت والثلاثاء مساءً"]
        if not group.confirmed_at:  # the demo student is already attending it
            group.confirmed_at = timezone.now()
            group.save(update_fields=["confirmed_at"])
        enrollment, _ = Enrollment.objects.update_or_create(
            user=user, course=group.course, defaults={"cohort": group, "status": Enrollment.STATUS_ACTIVE})
        first = group.lessons.first()
        first.zoom_url = first.zoom_url or "https://zoom.us/j/1234567890"
        first.title_ar = first.title_ar or "التعارف وتحديد الأهداف"
        first.notes_ar = first.notes_ar or "تعرّفنا على مستوى كل طالب وحددنا أهداف الكورس."
        first.save()
        Attendance.objects.update_or_create(lesson=first, enrollment=enrollment, defaults={"status": Attendance.PRESENT})

        # Requests in different states for the admin inbox.
        samples = [
            ("demo-paid@example.com", "منى أحمد", "01000000001", "private", EnrollmentRequest.PAYMENT_PAID,
             EnrollmentRequest.STATUS_NEW, "أفضل المواعيد بعد الساعة 8 مساءً."),
            ("demo-unpaid@example.com", "خالد سمير", "01000000002", "group", EnrollmentRequest.PAYMENT_UNPAID,
             EnrollmentRequest.STATUS_NEW, "لم يكمل الدفع — يحتاج متابعة."),
            ("demo-contacted@example.com", "هبة محمود", "01000000003", "group", EnrollmentRequest.PAYMENT_UNPAID,
             EnrollmentRequest.STATUS_CONTACTED, ""),
        ]
        for email, name, phone, mode, pay, status, notes in samples:
            EnrollmentRequest.objects.update_or_create(
                email=email, course=courses["demo-english-speaking"],
                defaults=dict(full_name=name, phone=phone, mode=mode, payment_status=pay, status=status,
                              preferred_times=notes),
            )

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(courses)} courses, {len(cohorts)} cohorts, "
            f"{sum(c.lessons.count() for c in cohorts.values())} sessions, 3 requests."))
        self.stdout.write(f"Demo student login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
