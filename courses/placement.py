"""Putting students into groups, moving them and taking them out — one place for the rules.

A launched group (confirmed and given a teacher, see `Cohort.is_locked`) is frozen:
nobody joins it and nobody leaves it. Every dashboard action goes through here so
the rule can't be bypassed by a different screen. Each function returns an error
message, or None on success.
"""
from .models import Cohort, Enrollment, EnrollmentRequest

LOCKED = "المجموعة مُطلقة ومُسندة لمدرس، لا يمكن إدخال طلاب أو إخراجهم منها."


def _target_error(cohort, course_id, holds_seat_here=False):
    if cohort.course_id != course_id:
        return "المجموعة تابعة لكورس آخر."
    if cohort.is_locked:
        return LOCKED
    if cohort.mode == "group" and cohort.seats_left == 0 and not holds_seat_here:
        return "المجموعة مكتملة العدد."
    return None


def place_request(req, cohort):
    """Place a request's student: a forming group keeps them waiting (staff-only), otherwise enrol them."""
    if not (req.user and req.course):
        return "لا يمكن التسجيل: الطالب لم ينشئ حسابًا بعد."
    here = (req.cohort_id == cohort.pk and req.status == EnrollmentRequest.STATUS_WAITING) or \
        Enrollment.objects.filter(user=req.user, course=req.course, cohort=cohort).exists()
    error = _target_error(cohort, req.course_id, holds_seat_here=here)
    if error:
        return error
    if req.cohort_id and req.cohort_id != cohort.pk and req.cohort.is_locked:
        return LOCKED
    if cohort.is_forming:
        req.cohort = cohort
        req.status = EnrollmentRequest.STATUS_WAITING
        req.save(update_fields=["cohort", "status"])
        return None
    enrollment, _ = Enrollment.objects.get_or_create(user=req.user, course=req.course)
    if enrollment.cohort_id and enrollment.cohort_id != cohort.pk and enrollment.cohort.is_locked:
        return LOCKED
    enrollment.status = Enrollment.STATUS_ACTIVE
    enrollment.cohort = cohort
    enrollment.save()
    req.cohort = cohort
    req.status = EnrollmentRequest.STATUS_ENROLLED
    req.save(update_fields=["cohort", "status"])
    return None


def move_enrollment(enrollment, cohort):
    """Move an enrolled student to another group of the same course."""
    if enrollment.cohort_id == cohort.pk:
        return None
    if enrollment.cohort_id and enrollment.cohort.is_locked:
        return LOCKED
    error = _target_error(cohort, enrollment.course_id)
    if error:
        return error
    enrollment.cohort = cohort
    enrollment.save(update_fields=["cohort"])
    return None


def remove_enrollment(enrollment):
    """Take a student out of their group (they stay enrolled in the course, unplaced)."""
    if enrollment.cohort_id and enrollment.cohort.is_locked:
        return LOCKED
    enrollment.cohort = None
    enrollment.save(update_fields=["cohort"])
    return None


def move_waiting(req, cohort):
    """Move a waiting (not yet enrolled) student to another group."""
    return place_request(req, cohort)


def remove_waiting(req):
    """Take a student off a forming group's waiting list; their request goes back to 'contacted'."""
    req.cohort = None
    req.status = EnrollmentRequest.STATUS_CONTACTED
    req.save(update_fields=["cohort", "status"])
    return None
