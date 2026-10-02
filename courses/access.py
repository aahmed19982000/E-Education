"""Who may see a course's private material (Zoom link, recordings, files)."""
from dashboard.permissions import get_dashboard_role

from .models import Enrollment


def has_active_enrollment(user, course):
    if not getattr(user, "is_authenticated", False):
        return False
    return Enrollment.objects.filter(user=user, course=course, status=Enrollment.STATUS_ACTIVE).exists()


def is_staff_user(user):
    return get_dashboard_role(user) is not None


def can_view_lesson_material(user, lesson):
    """Only students placed in the lesson's own cohort, plus dashboard staff.

    Times differ per group/student, so enrolling in the course alone does not
    open another cohort's Zoom link, recordings or files.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if is_staff_user(user):
        return True
    return Enrollment.objects.filter(
        user=user, cohort_id=lesson.cohort_id, status=Enrollment.STATUS_ACTIVE,
    ).exists()
