"""Issue completion certificates: a passed (fully graded) end-of-level exam earns one."""
from django.conf import settings

from .models import Certificate, Enrollment


def issue_if_eligible(submission):
    """Called when a submission becomes fully graded. Returns the new Certificate or None."""
    exam = submission.exam
    if exam.kind != exam.KIND_LEVEL or not submission.is_graded:
        return None
    if submission.percent < settings.CERTIFICATE_PASS_PERCENT:
        return None
    enrollment = Enrollment.objects.filter(user=submission.user, cohort_id=submission.cohort_id,
                                           status=Enrollment.STATUS_ACTIVE).first()
    if enrollment is None:
        return None
    cert, created = Certificate.objects.get_or_create(enrollment=enrollment,
                                                      defaults={"final_percent": submission.percent})
    if created:
        from core import notify
        notify.certificate_issued(cert)
    return cert
