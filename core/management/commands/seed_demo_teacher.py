from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand

from courses.models import Cohort
from team.models import TeamMember

EMAIL = "teacher.demo@example.com"
PASSWORD = "demo12345"


class Command(BaseCommand):
    help = f"Create a demo teacher ({EMAIL} / {PASSWORD}) linked to a team profile and to the demo student's group."

    def handle(self, *args, **options):
        call_command("seed_demo_student", stdout=self.stdout)
        member, _ = TeamMember.objects.get_or_create(
            name_ar="أ. منى عادل", defaults={"name_en": "Mona Adel", "role_ar": "مدرسة لغة إنجليزية", "role_en": "English teacher"})
        user, _ = User.objects.get_or_create(username="demo_teacher", defaults={"email": EMAIL, "first_name": "منى", "is_staff": True})
        user.email, user.is_staff = EMAIL, True
        user.set_password(PASSWORD)
        user.save()
        user.profile.role = "teacher"
        user.profile.team_member = member
        user.profile.save()
        Cohort.objects.filter(course__title_ar="الإنجليزية للمحادثة", teacher__isnull=True).update(teacher=member)
        self.stdout.write(self.style.SUCCESS(f"Demo teacher ready: {EMAIL} / {PASSWORD}"))
