"""Exam scoring for both grading modes.

Maths is done with Fractions so an equal split (e.g. 100 marks over 6
questions) adds back up to exactly the total.
"""
from fractions import Fraction


from .models import QuizSettings


def question_marks(questions, settings=None):
    """{question pk: Fraction marks} under the current grading mode."""
    settings = settings or QuizSettings.load()
    questions = list(questions)
    if settings.is_per_question:
        return {q.pk: Fraction(q.points) for q in questions}
    if not questions:
        return {}
    share = Fraction(settings.total_marks) / len(questions)
    return {q.pk: share for q in questions}


def grade(questions, results, settings=None):
    """Score a finished attempt.

    `results` maps question pk -> answered correctly (bool). Questions deleted
    since the attempt started simply don't count.
    """
    marks = question_marks(questions, settings)
    total = sum(marks.values(), Fraction(0))
    earned = sum((m for pk, m in marks.items() if results.get(pk)), Fraction(0))
    ratio = earned / total if total else Fraction(0)
    return {"earned": earned, "total": total, "ratio": ratio, "percent": round(ratio * 100)}


def format_marks(value):
    """Fraction -> short display string: 10, 7.5, 16.67."""
    rounded = round(float(value), 2)
    return f"{rounded:.2f}".rstrip("0").rstrip(".")
