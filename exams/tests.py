import datetime
import io
import shutil
import tempfile
import wave
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from courses.models import Cohort, Course, CourseLevel, Enrollment, Lesson
from team.models import TeamMember

from . import bulk
from .models import Answer, Exam, ExamQuestion, Submission
from .services import STATE_GRADED, STATE_LATE, STATE_NOT_OPEN, STATE_SUBMITTED, STATE_TODO, state_for

PRIVATE = tempfile.mkdtemp()


def wav_upload(name="answer.wav"):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x01" * 16000)
    return SimpleUploadedFile(name, buf.getvalue(), content_type="audio/wav")


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class ExamBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PRIVATE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        now = timezone.now()
        self.member = TeamMember.objects.create(name_ar="مدرس", role_ar="مدرس")
        self.other_member = TeamMember.objects.create(name_ar="آخر", role_ar="مدرس")
        self.course = Course.objects.create(title_ar="كورس", is_published=True)
        self.level = CourseLevel.objects.create(course=self.course, name_ar="المستوى الأول")
        self.cohort = Cohort.objects.create(course=self.course, mode="private", teacher=self.member, level=self.level)
        # session 1 ended two days ago, session 2 starts tomorrow (the deadline for exam 1), session 3 later.
        self.l1 = Lesson.objects.create(cohort=self.cohort, number=1, starts_at=now - datetime.timedelta(days=2))
        self.l2 = Lesson.objects.create(cohort=self.cohort, number=2, starts_at=now + datetime.timedelta(days=1))
        self.l3 = Lesson.objects.create(cohort=self.cohort, number=3, starts_at=now + datetime.timedelta(days=8))
        self.student = User.objects.create_user("s", "s@example.com", "pw", first_name="طالب")
        self.other_student = User.objects.create_user("o", "o@example.com", "pw")
        Enrollment.objects.create(user=self.student, course=self.course, cohort=self.cohort)
        self.teacher = self.make_teacher("t", self.member)
        self.other_teacher = self.make_teacher("t2", self.other_member)
        self.admin = User.objects.create_superuser("admin", "a@example.com", "pw")

        self.exam = Exam.objects.create(level=self.level, number=1, kind="session", is_published=True)
        self.mcq = ExamQuestion.objects.create(exam=self.exam, order=1, kind="mcq", text="2+2?",
                                               options=["3", "4"], correct_index=1, points=2)
        self.voice = ExamQuestion.objects.create(exam=self.exam, order=2, kind="voice", text="Say hello", points=3)

    def make_teacher(self, username, member):
        user = User.objects.create_user(username, f"{username}@example.com", "pw", is_staff=True)
        user.profile.role = "teacher"
        user.profile.team_member = member
        user.profile.save()
        return user

    def hand_in(self, **post):
        data = {f"q{self.mcq.pk}": "1", **post}
        data[f"q{self.voice.pk}"] = wav_upload()
        self.client.force_login(self.student)
        return self.client.post(reverse("exams:take", args=[self.exam.pk]), data)


class ExamTimingTests(ExamBase):
    def test_session_exam_opens_after_the_session_and_is_due_before_the_next(self):
        self.assertEqual(self.exam.deadline(self.cohort), self.l2.starts_at)
        self.assertTrue(self.exam.is_open(self.cohort))
        later = Exam.objects.create(level=self.level, number=2, kind="session", is_published=True)
        self.assertFalse(later.is_open(self.cohort))  # session 2 hasn't happened yet
        self.assertEqual(later.deadline(self.cohort), self.l3.starts_at)

    def test_last_session_exam_has_no_deadline_and_level_exam_opens_after_the_last_session(self):
        last = Exam.objects.create(level=self.level, number=3, kind="session", is_published=True)
        self.assertIsNone(last.deadline(self.cohort))
        level = Exam.objects.create(level=self.level, kind="level", is_published=True)
        self.assertIsNone(level.deadline(self.cohort))
        self.assertEqual(level.opens_at(self.cohort), self.l3.starts_at + datetime.timedelta(minutes=self.l3.duration_minutes))
        self.assertFalse(level.is_open(self.cohort))

    def test_unpublished_exam_is_never_open(self):
        self.exam.is_published = False
        self.assertFalse(self.exam.is_open(self.cohort))

    def test_state_todo_late_submitted_graded(self):
        now = timezone.now()
        self.assertEqual(state_for(self.exam, self.student, now=now), STATE_TODO)
        self.assertEqual(state_for(self.exam, self.student, now=self.l2.starts_at + datetime.timedelta(hours=1)), STATE_LATE)
        future = Exam.objects.create(level=self.level, number=2, kind="session", is_published=True)
        self.assertEqual(state_for(future, self.student, now=now), STATE_NOT_OPEN)
        self.hand_in()
        self.assertEqual(state_for(self.exam, self.student), STATE_SUBMITTED)
        answer = Answer.objects.get(question=self.voice)
        answer.points_awarded = Decimal("2")
        answer.save()
        sub = Submission.objects.get()
        sub.refresh_graded()
        self.assertEqual(state_for(self.exam, self.student), STATE_GRADED)


class StudentExamTests(ExamBase):
    def test_submit_marks_multiple_choice_and_waits_for_the_voice_answer(self):
        resp = self.hand_in()
        self.assertRedirects(resp, reverse("exams:take", args=[self.exam.pk]), fetch_redirect_response=False)
        sub = Submission.objects.get()
        self.assertFalse(sub.is_late)
        self.assertEqual(sub.earned(), Decimal("2"))
        self.assertEqual(sub.pending_count(), 1)
        self.assertTrue(Answer.objects.get(question=self.voice).audio_file)
        page = self.client.get(reverse("exams:take", args=[self.exam.pk]))
        self.assertContains(page, "ستظهر درجة الأسئلة")  # waiting for the teacher's marks

    def test_wrong_answer_and_skipped_voice_need_no_marking(self):
        self.client.force_login(self.student)
        self.client.post(reverse("exams:take", args=[self.exam.pk]), {f"q{self.mcq.pk}": "0"})
        sub = Submission.objects.get()
        self.assertEqual(sub.earned(), Decimal("0"))
        self.assertTrue(sub.is_graded)

    def test_cannot_hand_in_twice(self):
        self.hand_in()
        self.hand_in()
        self.assertEqual(Submission.objects.count(), 1)

    def test_late_submission_is_flagged(self):
        self.l2.starts_at = timezone.now() - datetime.timedelta(hours=1)
        self.l2.save()
        self.hand_in()
        self.assertTrue(Submission.objects.get().is_late)

    def test_bad_audio_is_rejected_with_a_message_and_nothing_saved(self):
        self.client.force_login(self.student)
        resp = self.client.post(reverse("exams:take", args=[self.exam.pk]), {
            f"q{self.mcq.pk}": "1", f"q{self.voice.pk}": SimpleUploadedFile("x.wav", b"not audio", content_type="audio/wav")})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "تعذّر قراءة ملف الصوت")
        self.assertFalse(Submission.objects.exists())

    def test_access_rules(self):
        url = reverse("exams:take", args=[self.exam.pk])
        self.client.force_login(self.other_student)
        self.assertEqual(self.client.get(url).status_code, 404)  # not in this group
        self.client.force_login(self.student)
        self.exam.is_published = False
        self.exam.save()
        self.assertEqual(self.client.get(url).status_code, 404)  # draft
        self.exam.is_published = True
        self.exam.save()
        future = Exam.objects.create(level=self.level, number=2, kind="session", is_published=True)
        self.assertContains(self.client.get(reverse("exams:take", args=[future.pk])), "الامتحان لم يُفتح بعد")

    def test_dashboard_lists_the_exam_as_to_do_then_late(self):
        self.client.force_login(self.student)
        row = self.client.get(reverse("courses:mine")).context["exams"][0]
        self.assertEqual(row["state"], STATE_TODO)
        self.l2.starts_at = timezone.now() - datetime.timedelta(hours=1)
        self.l2.save()
        row = self.client.get(reverse("courses:mine")).context["exams"][0]
        self.assertEqual(row["state"], STATE_LATE)
        self.assertEqual(self.client.get(reverse("courses:mine")).context["exams_due"], 1)

    def test_audio_is_private_to_the_student_their_teacher_and_admins(self):
        self.hand_in()
        url = reverse("exams:audio", args=[Answer.objects.get(question=self.voice).pk])
        for user, code in ((self.student, 200), (self.teacher, 200), (self.admin, 200),
                           (self.other_student, 404), (self.other_teacher, 404)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, code, user.username)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)


QUESTIONS = """Capital of Egypt?  [1]
+ Cairo
- Giza

[صوت] Describe your day  [4]"""


class TeacherExamTests(ExamBase):
    def post_data(self, text=QUESTIONS, **extra):
        data = {"title": "Quiz", "instructions": "", "is_published": "on", "questions_text": text}
        data.update(extra)
        return data

    def session_url(self, number=2, level=None):
        return reverse("dashboard:exam_for_session", args=[(level or self.level).pk, number])

    def test_admin_builds_a_session_exam_in_one_save(self):
        self.client.force_login(self.admin)
        url = self.session_url(2)
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, self.post_data())
        self.assertEqual(resp.status_code, 302)
        exam = Exam.objects.get(level=self.level, number=2)
        self.assertTrue(exam.is_published)
        qs = list(exam.questions.all())
        self.assertEqual([q.kind for q in qs], ["mcq", "voice"])
        self.assertEqual((qs[0].options, qs[0].correct_index), (["Cairo", "Giza"], 0))
        self.assertEqual(exam.total_points(), Decimal("5"))

    def test_editing_shows_the_saved_questions_as_text_and_saving_keeps_them(self):
        self.client.force_login(self.admin)
        url = self.session_url(1)
        text = self.client.get(url).context["form"].fields["questions_text"].initial
        self.assertIn("+ 4", text)
        self.assertIn("[صوت] Say hello  [3]", text)
        self.client.post(url, self.post_data(text))
        self.assertEqual(Exam.objects.filter(level=self.level, number=1).count(), 1)
        self.assertEqual(self.exam.questions.count(), 2)

    def test_bad_questions_are_reported_and_nothing_is_saved(self):
        self.client.force_login(self.admin)
        url = self.session_url(2)
        for text in ("Only one choice?\n+ yes", "No right answer?\n- a\n- b", "Two right?\n+ a\n+ b"):
            resp = self.client.post(url, self.post_data(text))
            self.assertEqual(resp.status_code, 200, text)
        self.assertFalse(Exam.objects.filter(level=self.level, number=2).exists())

    def test_cannot_publish_an_exam_without_questions(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.session_url(2), self.post_data("")).status_code, 200)
        self.assertFalse(Exam.objects.filter(number=2).exists())

    def test_editing_keeps_students_answers_and_refuses_to_delete_answered_questions(self):
        self.hand_in()
        self.client.force_login(self.admin)
        url = self.session_url(1)
        text = "2+2?\n- 3\n+ 4\n\n[صوت] Say hello  [3]"
        self.client.post(url, self.post_data(text))
        self.assertEqual(Answer.objects.count(), 2)  # same positions: answers survive
        self.client.post(url, self.post_data("2+2?\n- 3\n+ 4"))  # would drop the answered voice question
        self.assertEqual(self.exam.questions.count(), 2)
        self.assertEqual(Answer.objects.count(), 2)

    def test_changing_the_right_answer_re_marks_handed_in_choices(self):
        self.hand_in()  # picked option index 1 ("4")
        self.assertEqual(Answer.objects.get(question=self.mcq).points_awarded, Decimal("2"))
        self.client.force_login(self.admin)
        self.client.post(self.session_url(1), self.post_data("2+2?  [2]\n+ 3\n- 4\n\n[صوت] Say hello  [3]"))
        self.assertEqual(Answer.objects.get(question=self.mcq).points_awarded, Decimal("0"))

    def test_every_group_at_a_level_shares_its_exam_but_other_levels_do_not(self):
        other_cohort = Cohort.objects.create(course=self.course, mode="private", level=self.level)
        Lesson.objects.create(cohort=other_cohort, number=1, starts_at=timezone.now() - datetime.timedelta(days=1))
        buddy = User.objects.create_user("b", "b@example.com", "pw")
        Enrollment.objects.create(user=buddy, course=self.course, cohort=other_cohort)
        level_b = CourseLevel.objects.create(course=self.course, name_ar="المستوى الثاني")
        advanced = Cohort.objects.create(course=self.course, mode="private", level=level_b)
        Lesson.objects.create(cohort=advanced, number=1, starts_at=timezone.now() - datetime.timedelta(days=1))
        adv_student = User.objects.create_user("a", "a@example.com", "pw")
        Enrollment.objects.create(user=adv_student, course=self.course, cohort=advanced)
        url = reverse("exams:take", args=[self.exam.pk])
        for user, code in ((self.student, 200), (buddy, 200), (adv_student, 404)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, code, user.username)
        # the second group's own session dates decide when it opens
        self.assertEqual(self.exam.opens_at(other_cohort),
                         other_cohort.lessons.get().starts_at + datetime.timedelta(minutes=other_cohort.lessons.get().duration_minutes))
        exam_b = Exam.objects.create(level=level_b, number=1, kind="session", is_published=True)
        self.client.force_login(adv_student)
        self.assertEqual(self.client.get(reverse("exams:take", args=[exam_b.pk])).status_code, 200)

    def test_levels_page_adds_levels_to_a_course(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:course_levels", args=[self.course.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        existing = self.level
        data = {"levels-TOTAL_FORMS": 3, "levels-INITIAL_FORMS": 1, "levels-MIN_NUM_FORMS": 0, "levels-MAX_NUM_FORMS": 1000,
                "levels-0-id": existing.pk, "levels-0-course": self.course.pk, "levels-0-name_ar": "المستوى الأول",
                "levels-1-name_ar": "المستوى الثاني", "levels-2-name_ar": ""}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(list(self.course.levels.values_list("name_ar", flat=True)), ["المستوى الأول", "المستوى الثاني"])

    def test_new_course_is_created_together_with_its_levels(self):
        self.client.force_login(self.admin)
        data = {"title_ar": "كورس جديد", "audience": "students", "offers_group": "on", "offers_private": "on",
                "levels-TOTAL_FORMS": 3, "levels-INITIAL_FORMS": 0, "levels-MIN_NUM_FORMS": 0, "levels-MAX_NUM_FORMS": 1000,
                "levels-0-name_ar": "المستوى الأول", "levels-1-name_ar": "المستوى A", "levels-2-name_ar": ""}
        resp = self.client.post(reverse("dashboard:course_create"), data)
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["form"].errors)
        course = Course.objects.get(title_ar="كورس جديد")
        self.assertEqual(list(course.levels.values_list("name_ar", flat=True)), ["المستوى الأول", "المستوى A"])

    def test_cohort_form_offers_only_its_courses_levels(self):
        other_course = Course.objects.create(title_ar="آخر")
        CourseLevel.objects.create(course=other_course, name_ar="غريب")
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:cohort_edit", args=[self.course.pk, self.cohort.pk]))
        self.assertEqual(list(resp.context["form"].fields["level"].queryset), [self.level])

    def test_teachers_cannot_create_or_edit_exams(self):
        for teacher in (self.teacher, self.other_teacher):
            self.client.force_login(teacher)
            for name, args in (("dashboard:exam_for_session", [self.level.pk, 1]), ("dashboard:exam_for_final", [self.level.pk]),
                               ("dashboard:course_levels", [self.course.pk])):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403, name)
                self.assertEqual(self.client.post(reverse(name, args=args), self.post_data()).status_code, 403, name)
        self.assertEqual(Exam.objects.count(), 1)

    def test_teacher_sees_only_their_own_groups_results(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("dashboard:exam_results", args=[self.exam.pk])).status_code, 200)
        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.get(reverse("dashboard:exam_results", args=[self.exam.pk])).status_code, 404)

    def test_teacher_pages_offer_no_create_or_edit_buttons(self):
        self.client.force_login(self.teacher)
        listing = self.client.get(reverse("dashboard:exams_list")).content.decode()
        self.assertNotIn(reverse("dashboard:exam_for_session", args=[self.level.pk, 1]), listing)
        self.assertNotIn(reverse("dashboard:exam_for_final", args=[self.level.pk]), listing)
        results = self.client.get(reverse("dashboard:exam_results", args=[self.exam.pk])).content.decode()
        self.assertNotIn(reverse("dashboard:exam_for_session", args=[self.level.pk, 1]), results)
        self.client.force_login(self.admin)
        self.assertIn(reverse("dashboard:exam_for_session", args=[self.level.pk, 1]),
                      self.client.get(reverse("dashboard:exams_list")).content.decode())

    def test_one_final_exam_per_level(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:exam_for_final", args=[self.level.pk])
        self.client.post(url, self.post_data())
        self.client.post(url, self.post_data(title="Edited"))
        self.assertEqual(Exam.objects.filter(level=self.level, kind="level").count(), 1)
        self.assertEqual(Exam.objects.get(kind="level").title, "Edited")

    def test_admin_can_open_any_levels_exam_tools(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:exam_for_session", args=[self.level.pk, 1])).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:exams_list")).status_code, 200)

    def test_results_list_shows_who_handed_in_late_or_not_at_all(self):
        self.hand_in()
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse("dashboard:exam_results", args=[self.exam.pk]))
        self.assertEqual(resp.context["groups"][0]["rows"][0]["state"], STATE_SUBMITTED)
        self.assertContains(resp, "بانتظار التقييم")

    def test_teacher_grades_a_voice_answer_within_the_question_points(self):
        self.hand_in()
        sub = Submission.objects.get()
        answer = Answer.objects.get(question=self.voice)
        self.client.force_login(self.teacher)
        url = reverse("dashboard:submission_grade", args=[sub.pk])
        self.assertContains(self.client.get(url), reverse("exams:audio", args=[answer.pk]))
        self.client.post(url, {f"pts-{answer.pk}": "9", "feedback": ""})  # more than the 3 marks it is worth
        answer.refresh_from_db()
        self.assertIsNone(answer.points_awarded)
        self.client.post(url, {f"pts-{answer.pk}": "2.5", f"fb-{answer.pk}": "Good pronunciation", "feedback": "Well done"})
        answer.refresh_from_db()
        sub.refresh_from_db()
        self.assertEqual(answer.points_awarded, Decimal("2.5"))
        self.assertIsNotNone(sub.graded_at)
        self.assertEqual(sub.earned(), Decimal("4.5"))
        self.client.force_login(self.student)
        page = self.client.get(reverse("exams:take", args=[self.exam.pk]))
        self.assertContains(page, "Good pronunciation")
        self.assertContains(page, "Well done")

    def test_other_teacher_and_students_cannot_open_the_grading_page(self):
        self.hand_in()
        url = reverse("dashboard:submission_grade", args=[Submission.objects.get().pk])
        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(url).status_code, 302)  # not a dashboard user

    def test_teacher_home_lists_submissions_waiting_for_marks(self):
        self.hand_in()
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse("dashboard:index"))
        self.assertEqual(resp.context["to_grade_count"], 1)
        self.assertNotContains(resp, "s@example.com")


class BulkParseTests(TestCase):
    def test_reads_all_three_question_kinds_with_marks(self):
        qs = bulk.parse("1. Pick one  [2]\n- a\n+ b\n\nWrite a line\n\n[voice] Say hi [3]")
        self.assertEqual([(q["kind"], q["points"]) for q in qs], [("mcq", 2), ("text", 1), ("voice", 3)])
        self.assertEqual((qs[0]["text"], qs[0]["options"], qs[0]["correct_index"]), ("Pick one", ["a", "b"], 1))

    def test_lettered_options_and_star_marker(self):
        qs = bulk.parse("Pick\nA) one\nB) *two\nC) three")
        self.assertEqual((qs[0]["options"], qs[0]["correct_index"]), (["one", "two", "three"], 1))

    def test_errors_name_the_question(self):
        with self.assertRaises(bulk.BulkError) as ctx:
            bulk.parse("Fine?\n+ a\n- b\n\nBroken?\n- a\n- b")
        self.assertIn("السؤال 2", ctx.exception.errors[0])

    def test_dump_and_parse_round_trip(self):
        text = "Pick  [2]\n- a\n+ b\n\n[صوت] Say hi  [3]\n\nWrite"
        qs = bulk.parse(text)
        self.assertEqual(bulk.parse(text), qs)
