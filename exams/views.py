from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.phone import whatsapp_digits

from .models import Answer, Exam
from .services import SubmitError, active_enrollment, can_review, state_for, submit


@login_required
def take(request, pk):
    """The student's exam page: the questions before they hand in, their result after."""
    exam = get_object_or_404(Exam.objects.select_related("level__course").prefetch_related("questions"),
                             pk=pk, is_published=True)
    enrollment = active_enrollment(request.user, exam)
    if enrollment is None:
        raise Http404
    cohort = enrollment.cohort
    submission = exam.submissions.filter(user=request.user).prefetch_related("answers__question").first()
    error = ""
    if submission is None:
        if not exam.is_open(cohort):
            return render(request, "exams/closed.html", {"exam": exam, "opens_at": exam.opens_at(cohort)})
        deadline = exam.deadline(cohort)
        if request.method == "POST":
            try:
                submission = submit(exam, request.user, request.POST, request.FILES, cohort)
                return redirect("exams:take", pk=exam.pk)
            except SubmitError as exc:
                error = str(exc)
        teacher = cohort.teacher if cohort else None
        name = request.user.get_full_name() or request.user.email or request.user.username
        return render(request, "exams/take.html", {
            "exam": exam, "deadline": deadline, "error": error,
            "late": bool(deadline and timezone.now() > deadline),
            "questions": list(exam.questions.all()),
            # Voice answers are sent to the group's teacher on WhatsApp instead of being recorded here.
            "teacher_whatsapp": whatsapp_digits(teacher.whatsapp) if teacher else None,
            "teacher_phone": teacher.whatsapp if teacher else "",
            "whatsapp_intro": f"{name} — {exam.course.title_ar} / {exam.level.name_ar} — {exam.display_title}",
        })
    answers = {a.question_id: a for a in submission.answers.all()}
    rows = [{"question": q, "answer": answers.get(q.pk),
             "correct": q.is_auto and answers.get(q.pk) is not None and answers[q.pk].choice_index == q.correct_index}
            for q in exam.questions.all()]
    return render(request, "exams/result.html", {
        "exam": exam, "submission": submission, "rows": rows,
        "state": state_for(exam, request.user, submission, cohort=cohort),
        "earned": submission.earned(), "total": submission.total(), "percent": submission.percent,
    })


@login_required
def answer_audio(request, pk):
    answer = get_object_or_404(Answer.objects.select_related("submission__cohort", "submission__user"), pk=pk)
    if not answer.audio_file:
        raise Http404
    if answer.submission.user_id != request.user.pk and not can_review(request.user, answer.submission):
        raise Http404  # private: don't reveal it exists
    return FileResponse(answer.audio_file.open("rb"), content_type="audio/mpeg")
