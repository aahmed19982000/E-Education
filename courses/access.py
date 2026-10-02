"""Who may see a course's private material (Zoom link, recordings, files)."""
from dashboard.permissions import get_dashboard_role

from .models import Enrollment


def has_active_enrollment(user, course):
    if not getattr(user, "is_authenticated", False):
        return False
    return Enrollment.objects.filter(user=user, course=course, status=Enrollment.STATUS_ACTIVE).exists()


def can_view_course_material(user, course):
    """Active students, plus dashboard staff (who manage the course)."""
    return has_active_enrollment(user, course) or get_dashboard_role(user) is not None
