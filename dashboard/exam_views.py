"""Building exams, seeing who handed them in, and marking voice / written answers.

Admins create and edit exams (for any group). A teacher only reviews: they see the results of their
own groups' exams, listen to the answers and give the marks.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import Cohort, Enrollment, Lesson
from exams.models import Answer, Exam, ExamQuestion, Submission
from exams.services import STATE_LATE, STATE_TODO, state_for

from .decorators import dashboard_required
from .forms import ExamForm, ExamQuestionFormSet
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
        return member_id is not None and cohort.teacher_id == member_id
    return can_access(request.dashboard_role, SECTION_COURSES)


def _may_edit(request, cohort):
    """Creating and editing exams is the admin's job; teachers never do it."""
    return request.dashboard_role != ROLE_TEACHER and can_access(request.dashboard_role, SECTION_COURSES, "write")


def _may_grade(request, cohort):
    """Giving marks: the group's own teacher, or an admin who can edit courses."""
    if request.dashboard_role == ROLE_TEACHER:
        return _may_see(request, cohort)
    return _may_edit(request, cohort)


def _visible_cohorts(request):
    qs = Cohort.objects.select_related("course")
    if request.dashboard_role == ROLE_TEACHER:
        member_id = _teacher_member_id(request)
        return qs.filter(teacher_id=member_id) if member_id else qs.none()
    if not can_access(request.dashboard_role, SECTION_COURSES):
        raise PermissionDenied
    return qs


@dashboard_required
def exams_list(request):
    cohorts = list(_visible_cohorts(request).annotate(
        lessons_count=Count("lessons", distinct=True)).order_by("course__title_ar", "pk"))
    exams = {e.lesson_id or ("level", e.cohort_id): e for e in Exam.objects.filter(cohort__in=cohorts)
             .annotate(subs=Count("submissions", distinct=True),
                       pending=Count("submissions__answers", filter=Q(submissions__answers__points_awarded__isnull=True),
                                     distinct=True)).prefetch_related("questions")}
    groups = []
    for cohort in cohorts:
        lessons = list(cohort.lessons.all())
        rows = [{"lesson": l, "exam": exams.get(l.pk)} for l in lessons]
        groups.append({"cohort": cohort, "rows": rows, "level": exams.get(("level", cohort.pk))})
    ctx = _context(request, "exams")
    ctx.update({"groups": groups, "can_edit": request.dashboard_role != ROLE_TEACHER and can_access(
        request.dashboard_role, SECTION_COURSES, "write")})
    return render(request, "dashboard/exams_list.html", ctx)


def _save_exam(request, cohort, lesson, kind):
    exam = Exam.objects.filter(cohort=cohort, lesson=lesson, kind=kind).first() if lesson else \
        Exam.objects.filter(cohort=cohort, kind=Exam.KIND_LEVEL).first()
    instance = exam or Exam(cohort=cohort, lesson=lesson, kind=kind)
    form = ExamForm(request.POST or None, instance=instance)
    formset = ExamQuestionFormSet(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        saved = form.save()
        formset.instance = saved
        questions = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        base = saved.questions.count()
        for i, q in enumerate(questions):
            q.exam = saved
            if not q.order:
                q.order = base + i + 1
            q.save()
        messages.success(request, "تم حفظ الامتحان.")
        return redirect("dashboard:exam_results", pk=saved.pk) if saved.is_published else redirect(request.path)
    ctx = _context(request, "exams")
    ctx.update({"form": form, "formset": formset, "exam": exam, "cohort": cohort, "lesson": lesson,
                "title": instance.display_title if exam else ("اختبار نهاية المستوى" if kind == Exam.KIND_LEVEL
                                                              else f"امتحان الجلسة {lesson.number}")})
    return render(request, "dashboard/exam_form.html", ctx)


@dashboard_required
def exam_for_lesson(request, lesson_pk):
    lesson = get_object_or_404(Lesson.objects.select_related("cohort__course"), pk=lesson_pk)
    if not _may_edit(request, lesson.cohort):
        raise PermissionDenied
    return _save_exam(request, lesson.cohort, lesson, Exam.KIND_SESSION)


@dashboard_required
def exam_for_level(request, cohort_pk):
    cohort = get_object_or_404(Cohort.objects.select_related("course"), pk=cohort_pk)
    if not _may_edit(request, cohort):
        raise PermissionDenied
    return _save_exam(request, cohort, None, Exam.KIND_LEVEL)


@dashboard_required
def exam_results(request, pk):
    exam = get_object_or_404(Exam.objects.select_related("cohort__course", "lesson"), pk=pk)
    if not _may_see(request, exam.cohort):
        raise Http404 if request.dashboard_role == ROLE_TEACHER else PermissionDenied
    now = timezone.now()
    subs = {s.user_id: s for s in exam.submissions.prefetch_related("answers")}
    rows = []
    for e in exam.cohort.enrollments.filter(status=Enrollment.STATUS_ACTIVE).select_related("user"):
        sub = subs.get(e.user_id)
        rows.append({"enrollment": e, "name": _student_name(e.user), "submission": sub,
                     "state": state_for(exam, e.user, sub, now)})
    order = {"submitted": 0, "late": 1, "todo": 2, "graded": 3, "not_open": 4}
    rows.sort(key=lambda r: (order[r["state"]], r["name"]))
    ctx = _context(request, "exams")
    ctx.update({"exam": exam, "rows": rows, "total": exam.total_points(), "opens_at": exam.opens_at,
                "deadline": exam.deadline, "can_edit": _may_edit(request, exam.cohort)})
    return render(request, "dashboard/exam_results.html", ctx)


def _student_name(user):
    from .teacher import student_name
    return student_name(user)


@dashboard_required
def submission_grade(request, pk):
    submission = get_object_or_404(Submission.objects.select_related("exam__cohort__course", "user"), pk=pk)
    exam = submission.exam
    if not _may_see(request, exam.cohort):
        raise Http404 if request.dashboard_role == ROLE_TEACHER else PermissionDenied
    can_grade = _may_grade(request, exam.cohort)
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
