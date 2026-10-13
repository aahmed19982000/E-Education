"""The teacher's own dashboard: only their groups, students and sessions."""
import datetime

from django.contrib import messages
from django.db.models import Avg, Count, Exists, OuterRef, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import Attendance, Enrollment, Lesson
from quiz.models import PlacementResult

from .decorators import dashboard_required
from .forms import AttachmentFormSet, TeacherLessonForm
from .permissions import ROLE_TEACHER


def _member(request):
    """The teacher's TeamMember profile (None until a manager links it to the account)."""
    profile = getattr(request.user, "profile", None)
    return profile.team_member if profile and profile.role == ROLE_TEACHER else None


def _own_lesson(request, pk):
    member = _member(request)
    if member is None:
        raise Http404
    return get_object_or_404(Lesson.objects.select_related("cohort__course"), pk=pk, cohort__teacher=member)


def teacher_home(request):
    from .views import base_context
    ctx = base_context(request, active="index")
    member = _member(request)
    ctx["member"] = member
    if member is None:
        return render(request, "dashboard/teacher_home.html", ctx)

    now = timezone.now()
    lessons = Lesson.objects.filter(cohort__teacher=member).select_related("cohort__course")
    marked = Attendance.objects.filter(lesson=OuterRef("pk"))
    # Sessions that already happened in a group with students but have no attendance recorded yet.
    needs_attendance = [
        l for l in lessons.filter(starts_at__lt=now, cohort__enrollments__status=Enrollment.STATUS_ACTIVE)
        .annotate(has_marks=Exists(marked)).filter(has_marks=False).distinct().order_by("-starts_at")[:20]
        if l.is_past
    ]
    upcoming = list(lessons.filter(starts_at__gte=now)[:6])
    cohorts = list(member.cohorts.select_related("course").annotate(
        students=Count("enrollments", filter=Q(enrollments__status=Enrollment.STATUS_ACTIVE), distinct=True)))
    for cohort in cohorts:
        cohort.next_lesson = cohort.lessons.filter(starts_at__gte=now).first()

    enrollments = (Enrollment.objects.filter(cohort__teacher=member, status=Enrollment.STATUS_ACTIVE)
                   .select_related("user__profile", "course", "cohort"))
    results = {}
    for r in PlacementResult.objects.filter(user_id__in=[e.user_id for e in enrollments]).order_by("created_at"):
        results[r.user_id] = r.percent
    students = []
    for e in enrollments:
        attended, total, percent = e.progress()
        students.append({"enrollment": e, "attended": attended, "total": total, "percent": percent,
                         "level": results.get(e.user_id)})
    rating = member.reviews.aggregate(avg=Avg("rating"), n=Count("id"))
    week_end = now + datetime.timedelta(days=7)
    ctx.update({
        "cohorts": cohorts, "students": students, "upcoming": upcoming[1:], "next": upcoming[0] if upcoming else None,
        "needs_attendance": needs_attendance[:6], "needs_attendance_count": len(needs_attendance),
        "week_count": lessons.filter(starts_at__gte=now, starts_at__lt=week_end).count(),
        "rating_avg": round(rating["avg"], 1) if rating["avg"] else None, "rating_n": rating["n"],
        "today": timezone.localdate(),
    })
    return render(request, "dashboard/teacher_home.html", ctx)


@dashboard_required
def teacher_lesson(request, pk):
    from .views import base_context
    lesson = _own_lesson(request, pk)
    form = TeacherLessonForm(request.POST or None, instance=lesson)
    files = AttachmentFormSet(request.POST or None, request.FILES or None, instance=lesson)
    if request.method == "POST" and form.is_valid() and files.is_valid():
        form.save()
        files.save()
        messages.success(request, "تم حفظ الجلسة.")
        return redirect("dashboard:index")
    ctx = base_context(request, active="index")
    ctx.update({"form": form, "files": files, "lesson": lesson, "cohort": lesson.cohort, "course": lesson.cohort.course})
    return render(request, "dashboard/teacher_lesson.html", ctx)


@dashboard_required
def teacher_attendance(request, pk):
    from .views import base_context
    lesson = _own_lesson(request, pk)
    enrollments = list(lesson.cohort.enrollments.filter(status=Enrollment.STATUS_ACTIVE).select_related("user"))
    if request.method == "POST":
        present_ids = set(request.POST.getlist("present"))
        for e in enrollments:
            status = Attendance.PRESENT if str(e.pk) in present_ids else Attendance.ABSENT
            Attendance.objects.update_or_create(lesson=lesson, enrollment=e, defaults={"status": status})
        messages.success(request, "تم حفظ الحضور.")
        return redirect("dashboard:index")
    marked = {a.enrollment_id: a.status for a in lesson.attendance.all()}
    rows = [{"enrollment": e, "present": marked.get(e.pk, Attendance.PRESENT) == Attendance.PRESENT} for e in enrollments]
    ctx = base_context(request, active="index")
    ctx.update({"lesson": lesson, "cohort": lesson.cohort, "course": lesson.cohort.course, "rows": rows})
    return render(request, "dashboard/teacher_attendance.html", ctx)
