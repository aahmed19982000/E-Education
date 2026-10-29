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
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.models import Cohort, Course, CourseLevel, Enrollment
from exams.models import Answer, Exam, ExamQuestion, Submission
from exams.services import STATE_LATE, STATE_TODO, state_for
from quiz.models import AUDIO_MAX_MB, MAX_OPTIONS, MIN_OPTIONS

from .decorators import dashboard_required
from .forms import CourseLevelFormSet, ExamForm, ExamQuestionForm
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
    """The exam's page: its settings, and the list of its questions (added one by one)."""
    exam = Exam.objects.filter(level=level, kind=kind, number=number).first()
    instance = exam or Exam(level=level, kind=kind, number=number)
    form = ExamForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        if "add_question" in request.POST:
            return redirect("dashboard:exam_question_create", exam_pk=saved.pk)
        messages.success(request, "تم حفظ الامتحان.")
        return redirect(request.path)
    title = instance.display_title if exam else ("اختبار نهاية المستوى" if kind == Exam.KIND_LEVEL
                                                  else f"امتحان الجلسة {number}")
    questions = list(exam.questions.annotate(num_answers=Count("answers"))) if exam else []
    ctx = _context(request, "exams")
    ctx.update({"form": form, "exam": exam, "level": level, "title": title, "questions": questions,
                "total_points": sum((q.points for q in questions), Decimal(0)),
                "answered": bool(exam and exam.submissions.exists())})
    return render(request, "dashboard/exam_form.html", ctx)


def _exam_url(exam):
    if exam.kind == Exam.KIND_LEVEL:
        return reverse("dashboard:exam_for_final", args=[exam.level_id])
    return reverse("dashboard:exam_for_session", args=[exam.level_id, exam.number])


def _exam_page(exam):
    return redirect(_exam_url(exam))


@dashboard_required
def exam_question_form(request, exam_pk=None, pk=None):
    """Add or edit one exam question, the same way placement-test questions are written."""
    if not _may_edit(request):
        raise PermissionDenied
    if pk:
        instance = get_object_or_404(ExamQuestion.objects.select_related("exam__level__course"), pk=pk)
        exam = instance.exam
    else:
        instance = None
        exam = get_object_or_404(Exam.objects.select_related("level__course"), pk=exam_pk)
    form = ExamQuestionForm(request.POST or None, request.FILES or None, instance=instance, exam=exam)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "تم حفظ السؤال.")
        if "save_add_another" in request.POST:
            return redirect("dashboard:exam_question_create", exam_pk=exam.pk)
        return _exam_page(exam)
    ctx = _context(request, "exams")
    ctx.update({
        "form": form, "instance": instance, "exam": exam, "level": exam.level,
        "title": "تعديل سؤال" if instance else "إضافة سؤال",
        "option_rows": form.option_rows(), "max_options": MAX_OPTIONS, "min_options": MIN_OPTIONS,
        "audio_max_mb": AUDIO_MAX_MB, "answered": form.answered, "back_url": _exam_url(exam),
    })
    return render(request, "dashboard/exam_question_form.html", ctx)


@dashboard_required
def exam_question_delete(request, pk):
    if not _may_edit(request):
        raise PermissionDenied
    question = get_object_or_404(ExamQuestion.objects.select_related("exam__level__course"), pk=pk)
    exam = question.exam
    if question.answers.exists():
        messages.error(request, "لا يمكن حذف سؤال أجاب عنه الطلاب بالفعل. عدّل نصه أو اتركه.")
        return _exam_page(exam)
    if request.method == "POST":
        with transaction.atomic():
            question.delete()
            rest = list(exam.questions.order_by("order", "pk"))
            for number, q in enumerate(rest, start=1):
                q.order = number
            ExamQuestion.objects.bulk_update(rest, ["order"])
            if not rest and exam.is_published:  # an empty exam can't stay in front of students
                exam.is_published = False
                exam.save(update_fields=["is_published"])
                messages.info(request, "تم إلغاء نشر الامتحان لأنه لم يعد فيه أسئلة.")
        messages.success(request, "تم حذف السؤال.")
        return _exam_page(exam)
    ctx = _context(request, "exams")
    ctx.update({"question": question, "exam": exam, "level": exam.level, "back_url": _exam_url(exam)})
    return render(request, "dashboard/exam_question_delete.html", ctx)


@dashboard_required
@require_POST
def exam_questions_reorder(request, exam_pk):
    """Save a new order for an exam's questions. Expects every question id, in the desired order."""
    if not _may_edit(request):
        raise PermissionDenied
    exam = get_object_or_404(Exam, pk=exam_pk)
    try:
        ids = [int(pk) for pk in request.POST.getlist("ids")]
    except ValueError:
        return JsonResponse({"ok": False, "error": "invalid ids"}, status=400)
    questions = {q.pk: q for q in exam.questions.all()}
    if len(ids) != len(set(ids)) or set(ids) != set(questions):
        return JsonResponse({"ok": False, "error": "stale"}, status=409)  # added/deleted since the page loaded
    for position, pk in enumerate(ids, start=1):
        questions[pk].order = position
    ExamQuestion.objects.bulk_update(questions.values(), ["order"])
    return JsonResponse({"ok": True})


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
