"""The teacher's own dashboard: only their groups, students and sessions."""
import datetime

from django.contrib import messages
from django.db.models import Avg, Count, Exists, OuterRef, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import Attendance, Enrollment, Lesson
from exams.models import Submission
from quiz.models import PlacementResult
from team.models import WEEKDAYS

from .decorators import dashboard_required
from .forms import AttachmentFormSet, TeacherLessonForm
from .permissions import ROLE_TEACHER

WEEKDAY_NAMES = dict(WEEKDAYS)
AT_RISK_RATE = 70  # attendance % below which a student is flagged for follow-up


def _member(request):
    """The teacher's TeamMember profile (None until a manager links it to the account)."""
    profile = getattr(request.user, "profile", None)
    return profile.team_member if profile and profile.role == ROLE_TEACHER else None


def _own_lesson(request, pk):
    member = _member(request)
    if member is None:
        raise Http404
    return get_object_or_404(Lesson.objects.select_related("cohort__course"), pk=pk, cohort__teacher=member)


def _context(request, active):
    from .views import base_context
    return base_context(request, active=active)


def _own_lessons(member):
    """The teacher's sessions, each flagged with whether attendance was already recorded."""
    marked = Attendance.objects.filter(lesson=OuterRef("pk"))
    return (Lesson.objects.filter(cohort__teacher=member).select_related("cohort__course")
            .annotate(has_marks=Exists(marked), students=Count(
                "cohort__enrollments", filter=Q(cohort__enrollments__status=Enrollment.STATUS_ACTIVE), distinct=True)))


def _state(lesson, now):
    """upcoming / live / ended for a session."""
    end = lesson.starts_at + datetime.timedelta(minutes=lesson.duration_minutes)
    if lesson.starts_at > now:
        return "upcoming"
    return "live" if now <= end else "ended"


def student_name(user):
    """A student's name for teachers. Never falls back to the email: teachers get no contact details."""
    return user.get_full_name() or user.first_name or f"طالب #{user.pk}"


def _students(member):
    """Active students of the teacher's groups with attendance, level and a follow-up flag."""
    enrollments = list(Enrollment.objects.filter(cohort__teacher=member, status=Enrollment.STATUS_ACTIVE)
                       .select_related("user__profile", "course", "cohort"))
    levels = {}  # latest level-test result per student
    for r in PlacementResult.objects.filter(user_id__in=[e.user_id for e in enrollments]).order_by("created_at"):
        levels[r.user_id] = r
    rows = []
    for e in enrollments:
        attended, total, percent = e.progress()
        marks = list(e.attendance.select_related("lesson").order_by("-lesson__starts_at").values_list("status", flat=True))
        rate = round(marks.count(Attendance.PRESENT) / len(marks) * 100) if marks else None
        missed_last_two = len(marks) >= 2 and all(s == Attendance.ABSENT for s in marks[:2])
        rows.append({
            "enrollment": e, "name": student_name(e.user),
            "course": e.course.title_ar, "group": e.cohort.name or e.cohort.get_mode_display(),
            "attended": attended, "total": total, "progress": percent, "rate": rate,
            "absences": marks.count(Attendance.ABSENT),
            "level": levels[e.user_id].percent if e.user_id in levels else None,
            "level_date": levels[e.user_id].created_at if e.user_id in levels else None,
            "at_risk": missed_last_two or (rate is not None and len(marks) >= 2 and rate < AT_RISK_RATE),
        })
    return rows


def _no_profile(request, active):
    return render(request, "dashboard/teacher_home.html", {**_context(request, active), "member": None})


def teacher_home(request):
    member = _member(request)
    if member is None:
        return _no_profile(request, "index")
    ctx = _context(request, "index")
    now = timezone.now()
    today = timezone.localdate()
    lessons = _own_lessons(member)

    todays = []
    for l in lessons.filter(starts_at__date=today).order_by("starts_at"):
        l.state = _state(l, now)
        todays.append(l)
    upcoming = list(lessons.filter(starts_at__gte=now).order_by("starts_at")[:6])
    pending = [l for l in lessons.filter(starts_at__lt=now, has_marks=False, students__gt=0).order_by("-starts_at")[:30]
               if l.is_past]
    no_link = [l for l in upcoming if not l.zoom_url]
    no_recording = list(lessons.filter(starts_at__lt=now, recording_url="").filter(has_marks=True).order_by("-starts_at")[:4])

    # A 7-day strip starting today: how many sessions each day has.
    strip = []
    for i in range(7):
        day = today + datetime.timedelta(days=i)
        strip.append({"day": day, "name": WEEKDAY_NAMES[day.weekday()], "count": sum(
            1 for l in lessons.filter(starts_at__date=day)), "today": i == 0})

    students = _students(member)
    cohorts = list(member.cohorts.select_related("course").annotate(
        total=Count("lessons", distinct=True),
        done=Count("lessons", filter=Q(lessons__starts_at__lt=now), distinct=True),
        students=Count("enrollments", filter=Q(enrollments__status=Enrollment.STATUS_ACTIVE), distinct=True)))
    for c in cohorts:
        c.percent = round(c.done / c.total * 100) if c.total else 0
        c.next_lesson = c.lessons.filter(starts_at__gte=now).first()
    to_grade = list(Submission.objects.filter(exam__cohort__teacher=member, graded_at__isnull=True)
                    .select_related("exam__cohort__course", "exam__lesson", "user").order_by("submitted_at"))
    for sub in to_grade:
        sub.student_name = student_name(sub.user)
    rating = member.reviews.aggregate(avg=Avg("rating"), n=Count("id"))
    hour = timezone.localtime(now).hour
    ctx.update({
        "member": member, "greeting": "صباح الخير" if hour < 12 else "مساء الخير",
        "todays": todays, "next": upcoming[0] if upcoming else None, "upcoming": upcoming[1:5],
        "to_grade": to_grade[:5], "to_grade_count": len(to_grade),
        "pending": pending[:5], "pending_count": len(pending), "no_link": no_link, "no_recording": no_recording,
        "strip": strip, "week_count": sum(d["count"] for d in strip),
        "cohorts": cohorts, "students_count": len(students), "follow_up": [s for s in students if s["at_risk"]][:5],
        "rating_avg": round(rating["avg"], 1) if rating["avg"] else None, "rating_n": rating["n"], "today": today,
    })
    return render(request, "dashboard/teacher_home.html", ctx)


@dashboard_required
def teacher_schedule(request):
    member = _member(request)
    if member is None:
        return _no_profile(request, "t_schedule")
    now = timezone.now()
    today = timezone.localdate()
    try:
        offset = int(request.GET.get("week", 0))
    except ValueError:
        offset = 0
    # Weeks run Saturday to Friday.
    start = today - datetime.timedelta(days=(today.weekday() + 2) % 7) + datetime.timedelta(weeks=offset)
    end = start + datetime.timedelta(days=7)
    lessons = list(_own_lessons(member).filter(starts_at__date__gte=start, starts_at__date__lt=end).order_by("starts_at"))
    days = []
    for i in range(7):
        day = start + datetime.timedelta(days=i)
        items = [l for l in lessons if timezone.localtime(l.starts_at).date() == day]
        for l in items:
            l.state = _state(l, now)
        days.append({"day": day, "name": WEEKDAY_NAMES[day.weekday()], "items": items, "today": day == today})
    ctx = _context(request, "t_schedule")
    ctx.update({"member": member, "days": days, "start": start, "end": end - datetime.timedelta(days=1),
                "offset": offset, "total": len(lessons)})
    return render(request, "dashboard/teacher_schedule.html", ctx)


@dashboard_required
def teacher_students(request):
    member = _member(request)
    if member is None:
        return _no_profile(request, "t_students")
    rows = _students(member)
    group = request.GET.get("group", "")
    query = request.GET.get("q", "").strip()
    groups = sorted({r["enrollment"].cohort_id: r["group"] + " — " + r["course"] for r in rows}.items())
    if group.isdigit():
        rows = [r for r in rows if r["enrollment"].cohort_id == int(group)]
    if query:
        rows = [r for r in rows if query.lower() in r["name"].lower()]
    rows.sort(key=lambda r: (not r["at_risk"], r["name"]))
    ctx = _context(request, "t_students")
    ctx.update({"member": member, "rows": rows, "groups": groups, "group": group, "query": query,
                "risk_count": sum(1 for r in rows if r["at_risk"])})
    return render(request, "dashboard/teacher_students.html", ctx)


@dashboard_required
def teacher_lesson(request, pk):
    lesson = _own_lesson(request, pk)
    form = TeacherLessonForm(request.POST or None, instance=lesson)
    files = AttachmentFormSet(request.POST or None, request.FILES or None, instance=lesson)
    if request.method == "POST" and form.is_valid() and files.is_valid():
        form.save()
        files.save()
        messages.success(request, "تم حفظ الجلسة.")
        return redirect("dashboard:index")
    ctx = _context(request, "t_schedule")
    ctx.update({"form": form, "files": files, "lesson": lesson, "cohort": lesson.cohort, "course": lesson.cohort.course})
    return render(request, "dashboard/teacher_lesson.html", ctx)


@dashboard_required
def teacher_attendance(request, pk):
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
    levels = {r.user_id: r.percent for r in PlacementResult.objects.filter(
        user_id__in=[e.user_id for e in enrollments]).order_by("created_at")}
    rows = [{"enrollment": e, "name": student_name(e.user), "level": levels.get(e.user_id),
             "present": marked.get(e.pk, Attendance.PRESENT) == Attendance.PRESENT} for e in enrollments]
    ctx = _context(request, "t_schedule")
    ctx.update({"lesson": lesson, "cohort": lesson.cohort, "course": lesson.cohort.course, "rows": rows})
    return render(request, "dashboard/teacher_attendance.html", ctx)
