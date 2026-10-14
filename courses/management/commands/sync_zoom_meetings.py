from django.core.management.base import BaseCommand, CommandError

from courses import zoom
from courses.models import Cohort


class Command(BaseCommand):
    help = "Create Zoom meetings for upcoming sessions that have no link yet."

    def handle(self, *args, **options):
        if not zoom.is_configured():
            raise CommandError("Set ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET first.")
        total = 0
        for cohort in Cohort.objects.select_related("course"):
            created, errors = zoom.sync_cohort(cohort)
            total += created
            if errors:
                raise CommandError(errors[0])
        self.stdout.write(f"Created {total} meeting(s).")
