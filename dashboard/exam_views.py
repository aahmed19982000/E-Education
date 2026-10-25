"""Building exams, seeing who handed them in, and marking voice / written answers.

Exams belong to a course level (one per session number, plus an end-of-level exam), so every group
at the level gets the same questions. Admins create and edit them. A teacher only reviews: they see
the results of their own groups, listen to the answers and give the marks.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import Cohort, Course, CourseLevel, Enrollment
from exams import bulk
from exams.models import Answer, Exam, Submission
from exams.services import STATE_LATE, STATE_TODO, state_for

from .decorators import dashboard_required
from .forms import CourseLevelFormSet, ExamForm
from .permissions import ROLE_TEACHER, SECTION_COURSES, can_access


def _context(request, active):
    from .views import base_context
    return base_context(request, active=active)


def _teacher_member_id(request):
    profile = getattr(request.user, "profile", None)
    return profile.team_member_id if profile and profile.role == ROLE_TEACHER else None


def _may_see(request, cohort):
    """Own group for a teacher; any group for an admin who can see courses."""
    if request.dashboard_role == ROLE_TEACHER:
        member_id = _teacher_member_id(request)
        return cohort is not None and member_id is not None and cohort.teacher_id == member_id
    return can_access(request.dashboard_role, SECTION_COURSES)


def _may_edit(request, cohort=None):
    """Creating and editing exams is the admin's job; teachers never do it."""
    return request.dashboard_role != ROLE_TEACHER and can_access(request.dashboard_role, SECTION_COURSES, "write")


def _may_grade(request, cohort):
    """Giving marks: the group's own teacher, or an admin who can edit courses."""
    if request.dashboard_role == ROLE_TEACHER:
        return _may_see(request, cohort)
    return _may_edit(request, cohort)


def _visible_cohorts(request):
    qs = Cohort.objects.select_related("course", "level")
    if request.dashboard_role == ROLE_TEACHER:
        member_id = _teacher_member_id(request)
        return qs.filter(teacher_id=member_id) if member_id else qs.none()
    if not can_access(request.dashboard_role, SECTION_COURSES):
        raise PermissionDenied
    return qs


@dashboard_required
def exams_list(request):
    cohorts = list(_visible_cohorts(request).annotate(lessons_count=Count("lessons", distinct=True)))
    levels = CourseLevel.objects.select_related("course")
    if request.dashboard_role == ROLE_TEACHER:
        levels = levels.filter(pk__in={c.level_id for c in cohorts if c.level_id})
    exams = {(e.level_id, e.number if e.kind == Exam.KIND_SESSION else None): e
             for e in Exam.objects.filter(level__in=levels).annotate(
                 subs=Count("submissions", distinct=True),
                 pending=Count("submissions__answers", filter=Q(submissions__answers__points_awarded__isnull=True),
                               distinct=True)).prefetch_related("questions")}
    by_level = {}
    for c in cohorts:
        by_level.setdefault(c.level_id, []).append(c)
    courses = {}
    for level in levels.order_by("course__title_ar", "order", "pk"):
        group = by_level.get(level.pk, [])
        count = max([c.lessons_count for c in group] + [n for (lid, n) in exams if lid == level.pk and n] + [0]) or 8
        rows = [{"number": n, "exam": exams.get((level.pk, n))} for n in range(1, count + 1)]
        courses.setdefault(level.course, []).append(
            {"level": level, "cohorts": group, "rows": rows, "final": exams.get((level.pk, None))})
    if request.dashboard_role != ROLE_TEACHER:  # admins also see courses that have no levels yet
        for course in Course.objects.filter(levels__isnull=True).order_by("title_ar"):
            courses.setdefault(course, [])
    unassigned = [c for c in cohorts if not c.level_id]
    ctx = _context(request, "exams")
    ctx.update({"courses": list(courses.items()), "unassigned": unassigned,
                "can_edit": request.dashboard_role != ROLE_TEACHER and can_access(
                    request.dashboard_role, SECTION_COURSES, "write")})
    return render(request, "dashboard/exams_list.html", ctx)


@dashboard_required
def course_levels(request, course_pk):
    """Add, rename or remove the levels of a course (an exam's questions live under a level)."""
    if not _may_edit(request):
        raise PermissionDenied
    course = get_object_or_404(Course, pk=course_pk)
    formset = CourseLevelFormSet(request.POST or None, instance=course)
    if request.method == "POST" and formset.is_valid():
        formset.save()
        for i, level in enumerate(course.levels.order_by("pk")):
            if level.order != i:
                CourseLevel.objects.filter(pk=level.pk).update(order=i)
        messages.success(request, "تم حفظ المستويات.")
        return redirect("dashboard:exams_list")
    ctx = _context(request, "exams")
    ctx.update({"course": course, "formset": formset})
    return render(request, "dashboard/course_levels.html", ctx)


def _save_exam(request, level, kind, number=None):
    exam = Exam.objects.filter(level=level, kind=kind, number=number).first()
    instance = exam or Exam(level=level, kind=kind, number=number)
    form = ExamForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save()
                bulk.apply(saved, form.parsed)
        except bulk.BulkError as exc:
            for line in exc.errors:
                messages.error(request, line)
        else:
            messages.success(request, f"تم حفظ الامتحان ({len(form.parsed)} سؤال).")
            return redirect("dashboard:exam_results", pk=saved.pk) if saved.is_published else redirect(request.path)
    title = instance.display_title if exam else ("اختبار نهاية المستوى" if kind == Exam.KIND_LEVEL
                                                  else f"امتحان الجلسة {number}")
    ctx = _context(request, "exams")
    ctx.update({"form": form, "exam": exam, "level": level, "title": title,
                "answered": bool(exam and exam.submissions.exists())})
    return render(request, "dashboard/exam_form.html", ctx)


@dashboard_required
def exam_for_session(request, level_pk, number):
    level = get_object_or_404(CourseLevel.objects.select_related("course"), pk=level_pk)
    if not _may_edit(request):
        raise PermissionDenied
    return _save_exam(request, level, Exam.KIND_SESSION, number)


@dashboard_required
def exam_for_final(request, level_pk):
    level = get_object_or_404(CourseLevel.objects.select_related("course"), pk=level_pk)
    if not _may_edit(request):
        raise PermissionDenied
    return _save_exam(request, level, Exam.KIND_LEVEL)


@dashboard_required
def exam_results(request, pk):
    exam = get_object_or_404(Exam.objects.select_related("level__course"), pk=pk)
    cohorts = [c for c in _visible_cohorts(request).filter(level=exam.level)]
    if request.dashboard_role == ROLE_TEACHER and not cohorts:
        raise Http404
    now = timezone.now()
    subs = {s.user_id: s for s in exam.submissions.prefetch_related("answers")}
    groups = []
    order = {"submitted": 0, "late": 1, "todo": 2, "graded": 3, "not_open": 4}
    for cohort in cohorts:
        rows = []
        for e in cohort.enrollments.filter(status=Enrollment.STATUS_ACTIVE).select_related("user"):
            sub = subs.get(e.user_id)
            rows.append({"enrollment": e, "name": _student_name(e.user), "submission": sub,
                         "state": state_for(exam, e.user, sub, now, cohort)})
        rows.sort(key=lambda r: (order[r["state"]], r["name"]))
        groups.append({"cohort": cohort, "rows": rows, "opens_at": exam.opens_at(cohort),
                       "deadline": exam.deadline(cohort)})
    ctx = _context(request, "exams")
    ctx.update({"exam": exam, "groups": groups, "total": exam.total_points(), "can_edit": _may_edit(request)})
    return render(request, "dashboard/exam_results.html", ctx)


def _student_name(user):
    from .teacher import student_name
    return student_name(user)


@dashboard_required
def submission_grade(request, pk):
    submission = get_object_or_404(Submission.objects.select_related("exam__level__course", "cohort", "user"), pk=pk)
    exam = submission.exam
    if not _may_see(request, submission.cohort):
        raise Http404 if request.dashboard_role == ROLE_TEACHER else PermissionDenied
    can_grade = _may_grade(request, submission.cohort)
    answers = list(submission.answers.select_related("question"))
    if request.method == "POST":
        if not can_grade:
            raise PermissionDenied
        errors = []
        for a in answers:
            if a.question.is_auto:
                continue
            raw = request.POST.get(f"pts-{a.pk}", "").strip()
            if raw != "":
                try:
                    value = Decimal(raw)
                except InvalidOperation:
                    errors.append(f"الدرجة «{raw}» غير صالحة.")
                    continue
                if not Decimal(0) <= value <= a.question.points:
                    errors.append(f"الدرجة لازم تكون بين 0 و{a.question.points:g}.")
                    continue
                a.points_awarded = value
            a.feedback = request.POST.get(f"fb-{a.pk}", "").strip()
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            for a in answers:
                if not a.question.is_auto:
                    a.save(update_fields=["points_awarded", "feedback"])
            submission.feedback = request.POST.get("feedback", "").strip()
            submission.save(update_fields=["feedback"])
            submission.refresh_graded()
            messages.success(request, "تم حفظ التقييم.")
            return redirect("dashboard:exam_results", pk=exam.pk)
    ctx = _context(request, "exams")
    ctx.update({"submission": submission, "exam": exam, "answers": answers, "can_grade": can_grade,
                "student": _student_name(submission.user), "earned": submission.earned(), "total": submission.total()})
    return render(request, "dashboard/submission_grade.html", ctx)
