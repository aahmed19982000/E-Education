from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Answer, Exam
from .services import SubmitError, active_enrollment, can_review, state_for, submit


@login_required
def take(request, pk):
    """The student's exam page: the questions before they hand in, their result after."""
    exam = get_object_or_404(Exam.objects.select_related("cohort__course", "lesson").prefetch_related("questions"),
                             pk=pk, is_published=True)
    if active_enrollment(request.user, exam) is None:
        raise Http404
    submission = exam.submissions.filter(user=request.user).prefetch_related("answers__question").first()
    error = ""
    if submission is None:
        if not exam.is_open():
            return render(request, "exams/closed.html", {"exam": exam, "opens_at": exam.opens_at})
        if request.method == "POST":
            try:
                submission = submit(exam, request.user, request.POST, request.FILES)
                return redirect("exams:take", pk=exam.pk)
            except SubmitError as exc:
                error = str(exc)
        return render(request, "exams/take.html", {
            "exam": exam, "deadline": exam.deadline, "error": error,
            "late": bool(exam.deadline and timezone.now() > exam.deadline),
            "questions": list(exam.questions.all()),
        })
    answers = {a.question_id: a for a in submission.answers.all()}
    rows = [{"question": q, "answer": answers.get(q.pk),
             "correct": q.is_auto and answers.get(q.pk) is not None and answers[q.pk].choice_index == q.correct_index}
            for q in exam.questions.all()]
    return render(request, "exams/result.html", {
        "exam": exam, "submission": submission, "rows": rows, "state": state_for(exam, request.user, submission),
        "earned": submission.earned(), "total": submission.total(), "percent": submission.percent,
    })


@login_required
def answer_audio(request, pk):
    answer = get_object_or_404(Answer.objects.select_related("submission__exam__cohort", "submission__user"), pk=pk)
    if not answer.audio_file:
        raise Http404
    if answer.submission.user_id != request.user.pk and not can_review(request.user, answer.submission.exam):
        raise Http404  # private: don't reveal it exists
    return FileResponse(answer.audio_file.open("rb"), content_type="audio/mpeg")
