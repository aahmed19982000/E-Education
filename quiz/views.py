from django.shortcuts import redirect, render

from core.translations import LEVEL_NAMES

from .models import Question

SESSION_IDX = "quiz_idx"
SESSION_ANSWERS = "quiz_answers"


def intro(request):
    return render(request, "quiz/intro.html")


def start(request):
    request.session[SESSION_IDX] = 0
    request.session[SESSION_ANSWERS] = []
    return redirect("quiz:question")


def question(request):
    questions = list(Question.objects.all())
    total = len(questions)
    idx = request.session.get(SESSION_IDX)

    if idx is None:
        return redirect("quiz:intro")

    if request.method == "POST":
        try:
            chosen = int(request.POST.get("option", "-1"))
        except ValueError:
            chosen = -1
        if 0 <= idx < total:
            answers = request.session.get(SESSION_ANSWERS, [])
            answers.append(chosen == questions[idx].correct_index)
            request.session[SESSION_ANSWERS] = answers
            idx += 1
            request.session[SESSION_IDX] = idx
        if idx >= total:
            return redirect("quiz:result")
        return redirect("quiz:question")

    if idx >= total:
        return redirect("quiz:result")

    lang = request.lang
    current = questions[idx].localized(lang)
    progress_pct = round((idx / total) * 100) if total else 0

    return render(request, "quiz/question.html", {
        "current_question": current,
        "progress_pct": progress_pct,
        "question_number": idx + 1,
        "total_questions": total,
    })


def result(request):
    questions = list(Question.objects.all())
    total = len(questions)
    answers = request.session.get(SESSION_ANSWERS)
    idx = request.session.get(SESSION_IDX)

    if answers is None or idx is None or idx < total:
        return redirect("quiz:intro")

    lang = request.lang
    score = sum(1 for a in answers if a)
    names = LEVEL_NAMES.get(lang, LEVEL_NAMES["ar"])
    result_level_name = names[min(score, len(names) - 1)]

    return render(request, "quiz/result.html", {
        "result_level_name": result_level_name,
        "score": score,
        "total": total,
    })
