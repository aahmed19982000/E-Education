import datetime

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import Attendance, Cohort, Course, Enrollment, EnrollmentRequest, Lesson, LessonAttachment
from quiz.models import PlacementResult

EMAIL = "student@example.com"
PASSWORD = "demo12345"


class Command(BaseCommand):
    help = f"Create a demo student ({EMAIL} / {PASSWORD}) with sessions, attendance, homework, recordings and a pending request."

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(username="demo_student", defaults={"email": EMAIL, "first_name": "سارة"})
        user.email = EMAIL
        user.set_password(PASSWORD)
        user.save()
        if Enrollment.objects.filter(user=user).exists():
            self.stdout.write("Demo student already has data; login only was refreshed.")
            return

        speaking, _ = Course.objects.get_or_create(
            title_ar="الإنجليزية للمحادثة", defaults={"title_en": "Conversation English", "is_published": True,
                                                       "price_group": 500, "price_private": 900})
        ielts, _ = Course.objects.get_or_create(
            title_ar="تحضير IELTS", defaults={"title_en": "IELTS Prep", "is_published": True, "price_group": 700})

        now = timezone.now()
        cohort = Cohort.objects.create(course=speaking, mode="private", name="سارة — خاص", confirmed_at=now)
        enrollment = Enrollment.objects.create(user=user, course=speaking, cohort=cohort)
        offsets = [-9, -6, -3, 1, 4, 8]
        lessons = [Lesson.objects.create(
            cohort=cohort, number=i, starts_at=now + datetime.timedelta(days=d, hours=1),
            zoom_url="https://zoom.us/j/123456789" if d > 0 else "",
            recording_url="https://example.com/recording" if d < 0 else "",
            notes_ar="راجع الواجب قبل الجلسة." if d > 0 else "",
        ) for i, d in enumerate(offsets, start=1)]
        for lesson, status in zip(lessons[:3], [Attendance.PRESENT, Attendance.PRESENT, Attendance.ABSENT]):
            Attendance.objects.create(lesson=lesson, enrollment=enrollment, status=status)
        homework = LessonAttachment(lesson=lessons[2], kind=LessonAttachment.KIND_HOMEWORK, title="Unit 3 worksheet")
        homework.file.save("worksheet.txt", ContentFile(b"Demo homework"))

        PlacementResult.objects.create(user=user, percent=72)
        EnrollmentRequest.objects.create(
            user=user, course=ielts, full_name="سارة", email=EMAIL, phone="01000000000",
            status=EnrollmentRequest.STATUS_WAITING)
        self.stdout.write(self.style.SUCCESS(f"Demo student ready: {EMAIL} / {PASSWORD}"))
