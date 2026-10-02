import math

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.translations import LEVEL_NAMES, count_phrase, get_translations

from .attempt import Attempt
from .grading import format_marks, grade, level_index, place_level
from .models import PlacementResult, Question, QuizSettings


def intro(request):
    settings = QuizSettings.load()
    lang = request.lang
    t = get_translations(lang)["test"]
    if settings.exam_time_minutes:
        time_item = t["infoExamTime"].format(n=count_phrase(settings.exam_time_minutes, "minute", lang))
    elif settings.question_time_seconds:
        time_item = t["infoQuestionTime"].format(n=count_phrase(settings.question_time_seconds, "second", lang))
    else:
        time_item = t["noTimeLimit"]
    return render(request, "quiz/intro.html", {
        "info_items": [
            t["infoItems"][0],
            count_phrase(Question.objects.count(), "question", lang),
            time_item,
            t["infoItems"][-1],
        ],
    })


@require_POST
def start(request):
    Attempt.start(request)
    return redirect("quiz:question")


def question(request):
    attempt = Attempt.load(request)
    if attempt is None:
        return redirect("quiz:intro")
    if attempt.finished:
        return redirect("quiz:result")

    attempt.tick()
    if not attempt.questions or attempt.exam_expired():
        attempt.finish()
        attempt.save()
        return redirect("quiz:result")

    if request.method == "POST":
        # The form says which question it was showing, so a stale tab can't answer the wrong one.
        shown = next((q for q in attempt.questions if str(q.pk) == request.POST.get("question")), None)
        saved = False
        if shown is not None and request.POST.get("option", "") != "":
            try:
                saved = attempt.answer(shown, int(request.POST["option"]))
            except ValueError:
                pass

        nav = request.POST.get("nav", "next")
        if nav == "save":
            # Sent in the background as soon as an option is picked, so a choice made
            # before the question's time runs out counts even if "Next" comes later.
            attempt.save()
            return JsonResponse({"saved": saved})
        if nav == "finish":
            attempt.finish()
            attempt.save()
            return redirect("quiz:result")
        if nav == "prev":
            attempt.go(attempt.index - 1)
        elif nav.startswith("goto:"):
            try:
                attempt.go(int(nav[5:]))
            except ValueError:
                pass
        else:  # "next"
            if attempt.index >= len(attempt.questions) - 1:
                attempt.finish()
                attempt.save()
                return redirect("quiz:result")
            attempt.go(attempt.index + 1)
        attempt.data["current"] = None  # nothing on screen until the next GET
        attempt.save()
        return redirect("quiz:question")

    current = attempt.current_question()
    attempt.show(current)
    attempt.save()

    lang = request.lang
    t = get_translations(lang)["test"]
    total = len(attempt.questions)
    locked = attempt.question_locked(current)
    exam_remaining = attempt.exam_remaining()
    question_remaining = attempt.question_remaining(current)
    navigator = [
        {"number": i + 1, "answered": attempt.chosen(q) is not None, "current": i == attempt.index}
        for i, q in enumerate(attempt.questions)
    ]
    return render(request, "quiz/question.html", {
        "current_question": current.localized(lang),
        "question_pk": current.pk,
        "chosen": attempt.chosen(current),
        "locked": locked,
        "question_number": attempt.index + 1,
        "total_questions": total,
        "is_first": attempt.index == 0,
        "is_last": attempt.index == total - 1,
        "progress_pct": round(sum(1 for n in navigator if n["answered"]) / total * 100),
        "navigator": navigator,
        "exam_remaining": math.ceil(exam_remaining) if exam_remaining is not None else None,
        "question_remaining": math.ceil(question_remaining) if question_remaining is not None and not locked else None,
        "question_limit": attempt.question_limit(current),
        "unanswered": attempt.unanswered_count(),
        "question_of_label": t["questionOf"].format(n=attempt.index + 1, total=total),
        # The page fills in the count client-side; ship the phrase for every possible count.
        "confirm_finish_template": t["confirmFinish"],
        "unanswered_phrases": {n: count_phrase(n, "question", lang) for n in range(1, total + 1)},
    })


def result(request):
    attempt = Attempt.load(request)
    if attempt is None:
        return redirect("quiz:intro")
    if not attempt.finished:
        attempt.tick()
        if not attempt.exam_expired():
            return redirect("quiz:question")
        attempt.finish()
        attempt.save()

    questions = attempt.questions
    lang = request.lang
    score = grade(questions, attempt.results())
    level = place_level(score["ratio"])
    if level:
        result_level_name = f"{level.code} — {level.name_en if lang == 'en' else level.name_ar}"
    else:
        # No level takes part in the test yet: fall back to equal bands over the built-in names.
        names = LEVEL_NAMES.get(lang, LEVEL_NAMES["ar"])
        result_level_name = names[level_index(score["ratio"], len(names))]

    # Remember a signed-in student's result (once per attempt) for their course pages.
    if request.user.is_authenticated and not attempt.data.get("recorded"):
        PlacementResult.objects.create(user=request.user, level=level, percent=score["percent"])
        attempt.data["recorded"] = True
        attempt.save()

    return render(request, "quiz/result.html", {
        "result_level": level,
        "level_card": level.localized(lang, "group") if level else None,
        "price_private": level.price_private if level else None,
        "result_level_name": result_level_name,
        "score": format_marks(score["earned"]),
        "total": format_marks(score["total"]),
        "percent": score["percent"],
        "answered_label": get_translations(lang)["test"]["answeredOf"].format(
            n=len(questions) - attempt.unanswered_count(), total=count_phrase(len(questions), "question", lang),
        ),
    })
