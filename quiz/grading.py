"""Exam scoring for both grading modes.

Maths is done with Fractions so an equal split (e.g. 100 marks over 6
questions) adds back up to exactly the total, and level boundaries don't
suffer from rounding.
"""
from fractions import Fraction

from core.translations import LEVEL_NAMES
from levels.models import Level

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


def level_index(ratio, levels=len(LEVEL_NAMES["ar"])):
    """Map a 0..1 score onto the level list (equal bands, the top band includes 100%)."""
    return min(int(ratio * levels), levels - 1)


def placement_levels():
    """Levels the test can assign, lowest threshold first."""
    return list(Level.objects.exclude(test_min_percent=None).order_by("test_min_percent", "order"))


def place_level(ratio, levels=None):
    """The highest level whose minimum % the score reaches.

    Compared exactly (Fraction), so 50% of the marks meets a 50% threshold.
    A score below every threshold still gets the lowest level; returns None
    only when no level takes part in the test.
    """
    levels = placement_levels() if levels is None else levels
    if not levels:
        return None
    percent = ratio * 100
    placed = levels[0]
    for level in levels:
        if percent >= level.test_min_percent:
            placed = level
    return placed


def format_marks(value):
    """Fraction -> short display string: 10, 7.5, 16.67."""
    rounded = round(float(value), 2)
    return f"{rounded:.2f}".rstrip("0").rstrip(".")
