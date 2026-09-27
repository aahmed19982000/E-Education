import io
import shutil
import tempfile
from decimal import Decimal
from fractions import Fraction

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from levels.models import Level

from .grading import format_marks, grade, level_index, place_level, question_marks
from .models import Category, Question, QuizSettings


def make_question(order, points="1", correct=0):
    category, _ = Category.objects.get_or_create(name_ar="قواعد", defaults={"name_en": "Grammar"})
    return Question.objects.create(
        order=order, category=category, text_ar=f"q{order}", options_ar=["a", "b"], correct_index=correct, points=Decimal(points),
    )


class GradingTests(TestCase):
    def setUp(self):
        self.qs = [make_question(1, "1"), make_question(2, "3"), make_question(3, "6")]

    def settings(self, mode, total="100"):
        s = QuizSettings.load()
        s.grading_mode, s.total_marks = mode, Decimal(total)
        s.save()
        return s

    def test_total_mode_splits_equally_and_adds_up_exactly(self):
        marks = question_marks(self.qs, self.settings(QuizSettings.MODE_TOTAL, "100"))
        self.assertEqual(set(marks.values()), {Fraction(100, 3)})
        self.assertEqual(sum(marks.values()), 100)

    def test_per_question_mode_uses_points(self):
        s = self.settings(QuizSettings.MODE_PER_QUESTION)
        a, b, c = self.qs
        result = grade(self.qs, {a.pk: True, b.pk: False, c.pk: True}, s)
        self.assertEqual(result["earned"], 7)
        self.assertEqual(result["total"], 10)
        self.assertEqual(result["percent"], 70)

    def test_total_mode_ignores_points(self):
        s = self.settings(QuizSettings.MODE_TOTAL, "60")
        a, b, c = self.qs
        result = grade(self.qs, {a.pk: True, b.pk: False, c.pk: False}, s)
        self.assertEqual(result["earned"], 20)
        self.assertEqual(result["total"], 60)

    def test_level_bands_match_old_count_based_mapping(self):
        # Old behaviour with 6 equal questions: names[min(correct, 5)].
        for correct in range(7):
            self.assertEqual(level_index(Fraction(correct, 6), 6), min(correct, 5))

    def test_format_marks(self):
        self.assertEqual(format_marks(Fraction(10)), "10")
        self.assertEqual(format_marks(Fraction(15, 2)), "7.5")
        self.assertEqual(format_marks(Fraction(100, 6)), "16.67")

    def test_settings_is_a_singleton(self):
        QuizSettings.load()
        QuizSettings(grading_mode=QuizSettings.MODE_PER_QUESTION).save()
        self.assertEqual(QuizSettings.objects.count(), 1)


class QuizFlowTests(TestCase):
    """The student side: navigation, finishing and time limits."""

    def setUp(self):
        self.settings = QuizSettings.load()
        self.q1 = make_question(1, "2", correct=0)
        self.q2 = make_question(2, "8", correct=1)
        self.q3 = make_question(3, "1", correct=0)

    def set_settings(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self.settings, key, value)
        self.settings.save()

    def start(self):
        self.client.post(reverse("quiz:start"))
        return self.client.get(reverse("quiz:question"))

    def send(self, question, option=None, nav="next"):
        data = {"question": question.pk, "nav": nav}
        if option is not None:
            data["option"] = option
        return self.client.post(reverse("quiz:question"), data)

    def attempt(self):
        return self.client.session["quiz_attempt"]

    def edit_attempt(self, **changes):
        session = self.client.session
        session["quiz_attempt"].update(changes)
        session.save()

    def test_next_prev_keep_and_change_answers(self):
        self.start()
        self.send(self.q1, 1)                       # wrong first...
        self.client.get(reverse("quiz:question"))
        self.send(self.q2, nav="prev")              # back without answering q2
        resp = self.client.get(reverse("quiz:question"))
        self.assertEqual(resp.context["chosen"], 1)
        self.send(self.q1, 0)                       # ...then corrected
        self.assertEqual(self.attempt()["answers"], {str(self.q1.pk): 0})
        self.assertEqual(self.attempt()["index"], 1)

    def test_goto_jumps_to_question(self):
        self.start()
        self.send(self.q1, 0, nav="goto:2")
        resp = self.client.get(reverse("quiz:question"))
        self.assertEqual(resp.context["question_number"], 3)
        self.assertTrue(resp.context["is_last"])

    def test_result_only_after_finishing(self):
        self.start()
        self.assertRedirects(self.client.get(reverse("quiz:result")), reverse("quiz:question"))

    def test_finish_shows_weighted_score(self):
        self.set_settings(grading_mode=QuizSettings.MODE_PER_QUESTION)
        self.start()
        self.send(self.q1, 0)          # right: 2
        self.client.get(reverse("quiz:question"))
        self.send(self.q2, 0)          # wrong
        self.client.get(reverse("quiz:question"))
        resp = self.send(self.q3, nav="finish")  # unanswered
        self.assertRedirects(resp, reverse("quiz:result"))
        resp = self.client.get(reverse("quiz:result"))
        self.assertEqual(resp.context["score"], "2")
        self.assertEqual(resp.context["total"], "11")
        self.assertEqual(resp.context["percent"], 18)
        # Finished: going back to the questions just shows the result again.
        self.assertRedirects(self.client.get(reverse("quiz:question")), reverse("quiz:result"))

    def test_next_on_last_question_finishes(self):
        self.start()
        self.send(self.q1, nav="goto:2")
        self.client.get(reverse("quiz:question"))
        self.assertRedirects(self.send(self.q3, 0), reverse("quiz:result"))

    def test_exam_time_up_ends_test_and_ignores_late_answers(self):
        self.set_settings(exam_time_minutes=10)
        self.start()
        self.edit_attempt(deadline=1)  # long past
        resp = self.send(self.q1, 0)
        self.assertRedirects(resp, reverse("quiz:result"), fetch_redirect_response=False)
        self.assertEqual(self.attempt()["answers"], {})
        self.assertTrue(self.attempt()["finished"])

    def test_question_time_up_locks_answer_but_does_not_move_on(self):
        self.set_settings(question_time_seconds=30)
        self.start()
        self.edit_attempt(shown_at=self.attempt()["shown_at"] - 60)  # on screen for a minute
        resp = self.client.get(reverse("quiz:question"))
        self.assertTrue(resp.context["locked"])
        self.assertEqual(resp.context["question_number"], 1)       # still here until "Next"
        self.send(self.q1, 0)                                       # late answer ignored...
        self.assertEqual(self.attempt()["answers"], {})
        self.assertEqual(self.attempt()["index"], 1)                # ...but "Next" works

    def test_answer_saved_in_background_before_time_up_counts(self):
        self.set_settings(question_time_seconds=30)
        self.start()
        resp = self.send(self.q1, 0, nav="save")
        self.assertEqual(resp.json(), {"saved": True})
        self.assertEqual(self.attempt()["index"], 0)                # save doesn't navigate
        self.edit_attempt(shown_at=self.attempt()["shown_at"] - 60)  # time then runs out
        self.send(self.q1, nav="next")
        self.assertEqual(self.attempt()["answers"], {str(self.q1.pk): 0})

    def test_next_question_timer_starts_only_when_shown(self):
        self.set_settings(question_time_seconds=30)
        self.start()
        self.send(self.q1, 0)
        self.assertNotIn(str(self.q2.pk), self.attempt()["spent"])
        resp = self.client.get(reverse("quiz:question"))
        self.assertEqual(resp.context["question_remaining"], 30)

    def test_refresh_does_not_reset_question_timer(self):
        self.set_settings(question_time_seconds=30)
        self.start()
        for _ in range(3):  # three refreshes, 20s each on screen
            self.edit_attempt(shown_at=self.attempt()["shown_at"] - 20)
            resp = self.client.get(reverse("quiz:question"))
        self.assertTrue(resp.context["locked"])

    def test_per_question_override(self):
        self.set_settings(question_time_seconds=30)
        self.q1.time_limit_seconds = 0   # no limit for this one
        self.q1.save()
        self.q2.time_limit_seconds = 90
        self.q2.save()
        resp = self.start()
        self.assertIsNone(resp.context["question_remaining"])
        self.send(self.q1, 0)
        resp = self.client.get(reverse("quiz:question"))
        self.assertEqual(resp.context["question_remaining"], 90)

    def test_intro_lists_question_count_and_time(self):
        self.set_settings(exam_time_minutes=15)
        resp = self.client.get(reverse("quiz:intro"))
        self.assertIn("3 أسئلة", resp.context["info_items"])
        self.assertIn("مدة الاختبار 15 دقيقة", resp.context["info_items"])


class CategoryTests(TestCase):
    def test_localized_name_falls_back_to_arabic(self):
        self.assertEqual(Category(name_ar="قواعد", name_en="Grammar").localized_name("en"), "Grammar")
        self.assertEqual(Category(name_ar="محادثة").localized_name("en"), "محادثة")

    def test_question_tag_comes_from_category(self):
        q = make_question(1)
        self.assertEqual(q.localized("en")["tag"], "Grammar")
        self.assertEqual(q.localized("ar")["tag"], "قواعد")


def make_level(order, code, min_percent):
    return Level.objects.create(
        code=code, order=order, name_ar=f"مستوى {code}", name_en=f"Level {code}",
        description_ar="-", description_en="-", duration_ar="-", duration_en="-",
        price_group=100 * order, price_private=200 * order, test_min_percent=min_percent,
    )


class PlacementTests(TestCase):
    def setUp(self):
        self.a1 = make_level(1, "A1", 0)
        self.a2 = make_level(2, "A2", 40)
        self.b1 = make_level(3, "B1", 75)
        self.teachers = make_level(4, "T1", None)  # not assigned by the test

    def test_highest_reached_level(self):
        self.assertEqual(place_level(Fraction(0)), self.a1)
        self.assertEqual(place_level(Fraction(39, 100)), self.a1)
        self.assertEqual(place_level(Fraction(40, 100)), self.a2)  # threshold is inclusive
        self.assertEqual(place_level(Fraction(3, 4)), self.b1)
        self.assertEqual(place_level(Fraction(1)), self.b1)

    def test_below_every_threshold_gets_lowest_level(self):
        self.a1.test_min_percent = 10
        self.a1.save()
        self.assertEqual(place_level(Fraction(5, 100)), self.a1)

    def test_no_levels_in_test(self):
        Level.objects.update(test_min_percent=None)
        self.assertIsNone(place_level(Fraction(1, 2)))

    def test_result_page_recommends_level(self):
        q1 = make_question(1, correct=0)
        q2 = make_question(2, correct=0)
        self.client.post(reverse("quiz:start"))
        self.client.post(reverse("quiz:question"), {"question": q1.pk, "option": "0", "nav": "next"})
        self.client.post(reverse("quiz:question"), {"question": q2.pk, "option": "1", "nav": "finish"})  # 50%
        resp = self.client.get(reverse("quiz:result"))
        self.assertEqual(resp.context["result_level"], self.a2)
        self.assertContains(resp, "مستوى A2")
        self.assertContains(resp, "#level-A2")


class CountPhraseTests(TestCase):
    def test_arabic_forms(self):
        from core.translations import count_phrase
        self.assertEqual(count_phrase(1, "question", "ar"), "سؤال واحد")
        self.assertEqual(count_phrase(2, "question", "ar"), "سؤالان")
        self.assertEqual(count_phrase(6, "question", "ar"), "6 أسئلة")
        self.assertEqual(count_phrase(15, "minute", "ar"), "15 دقيقة")
        self.assertEqual(count_phrase(5, "minute", "ar"), "5 دقائق")
        self.assertEqual(count_phrase(1, "minute", "en"), "1 minute")
        self.assertEqual(count_phrase(6, "question", "en"), "6 questions")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PlacementTestCommandTests(TestCase):
    def tearDown(self):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def test_loads_30_questions_with_audio(self):
        call_command("load_placement_test", stdout=io.StringIO())
        questions = list(Question.objects.all())
        self.assertEqual(len(questions), 30)
        self.assertEqual([q.order for q in questions], list(range(1, 31)))
        listening = [q for q in questions if q.audio_file]
        self.assertEqual(len(listening), 4)
        self.assertTrue(all(q.audio_file.storage.exists(q.audio_file.name) for q in listening))
        for q in questions:  # every correct index points at a real option
            self.assertLess(q.correct_index, len(q.options_ar))
        self.assertEqual(Category.objects.count(), 4)

    def test_refuses_to_overwrite_without_replace(self):
        make_question(1)
        with self.assertRaises(CommandError):
            call_command("load_placement_test", stdout=io.StringIO())
        self.assertEqual(Question.objects.count(), 1)

    def test_replace_removes_old_questions(self):
        make_question(1)
        with self.captureOnCommitCallbacks(execute=True):
            call_command("load_placement_test", replace=True, stdout=io.StringIO())
        self.assertEqual(Question.objects.count(), 30)
        self.assertFalse(Question.objects.filter(text_ar="q1").exists())
