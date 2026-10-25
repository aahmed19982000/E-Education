"""Email reminders: sessions starting soon (students and teacher) and exams about to be due.

Run it every hour from cron, e.g.:  0 * * * *  cd /path && venv/bin/python manage.py send_reminders
Each reminder is sent once (see core.models.NotificationLog), so running it often is safe.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core import notify
from courses.models import Enrollment, Lesson
from exams.models import Exam, Submission

User = get_user_model()


class Command(BaseCommand):
    help = "Send reminders for sessions and exams that are coming up."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24, help="How far ahead to look (default 24).")

    def handle(self, *args, **options):
        now = timezone.now()
        until = now + datetime.timedelta(hours=options["hours"])
        sent = 0

        lessons = Lesson.objects.filter(starts_at__gt=now, starts_at__lte=until).select_related("cohort__course", "cohort__teacher")
        for lesson in lessons:
            students = User.objects.filter(enrollments__cohort=lesson.cohort, enrollments__status=Enrollment.STATUS_ACTIVE)
            for user in students:
                sent += notify.lesson_reminder(lesson, user)
            if lesson.cohort.teacher_id:
                for teacher in User.objects.filter(profile__team_member=lesson.cohort.teacher):
                    sent += notify.lesson_reminder(lesson, teacher, teacher=True)

        exams = Exam.objects.filter(is_published=True, kind=Exam.KIND_SESSION).select_related("level__course")
        for exam in exams:
            done = set(Submission.objects.filter(exam=exam).values_list("user_id", flat=True))
            for cohort in exam.level.cohorts.all():
                deadline = exam.deadline(cohort)
                if not deadline or not (now < deadline <= until) or not exam.is_open(cohort, now):
                    continue
                students = User.objects.filter(enrollments__cohort=cohort, enrollments__status=Enrollment.STATUS_ACTIVE)
                for user in students.exclude(pk__in=done):
                    sent += notify.exam_due(exam, user, deadline)

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder email(s)."))
