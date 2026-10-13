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

from courses.models import Cohort, Course, Enrollment, Lesson
from team.models import TeamMember

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
        self.cohort = Cohort.objects.create(course=self.course, mode="private", teacher=self.member)
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

        self.exam = Exam.objects.create(cohort=self.cohort, lesson=self.l1, kind="session", is_published=True)
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
        self.assertEqual(self.exam.deadline, self.l2.starts_at)
        self.assertTrue(self.exam.is_open())
        later = Exam.objects.create(cohort=self.cohort, lesson=self.l2, kind="session", is_published=True)
        self.assertFalse(later.is_open())  # session 2 hasn't happened yet
        self.assertEqual(later.deadline, self.l3.starts_at)

    def test_last_session_exam_has_no_deadline_and_level_exam_opens_after_the_last_session(self):
        last = Exam.objects.create(cohort=self.cohort, lesson=self.l3, kind="session", is_published=True)
        self.assertIsNone(last.deadline)
        level = Exam.objects.create(cohort=self.cohort, kind="level", is_published=True)
        self.assertIsNone(level.deadline)
        self.assertEqual(level.opens_at, self.l3.starts_at + datetime.timedelta(minutes=self.l3.duration_minutes))
        self.assertFalse(level.is_open())

    def test_unpublished_exam_is_never_open(self):
        self.exam.is_published = False
        self.assertFalse(self.exam.is_open())

    def test_state_todo_late_submitted_graded(self):
        now = timezone.now()
        self.assertEqual(state_for(self.exam, self.student, now=now), STATE_TODO)
        self.assertEqual(state_for(self.exam, self.student, now=self.l2.starts_at + datetime.timedelta(hours=1)), STATE_LATE)
        future = Exam.objects.create(cohort=self.cohort, lesson=self.l2, kind="session", is_published=True)
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
        future = Exam.objects.create(cohort=self.cohort, lesson=self.l2, kind="session", is_published=True)
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


class TeacherExamTests(ExamBase):
    def formset(self, **extra):
        data = {"title": "Quiz", "instructions": "", "is_published": "on",
                "questions-TOTAL_FORMS": 2, "questions-INITIAL_FORMS": 0, "questions-MIN_NUM_FORMS": 0, "questions-MAX_NUM_FORMS": 1000,
                "questions-0-kind": "mcq", "questions-0-text": "Capital of Egypt?", "questions-0-points": "1",
                "questions-0-options_text": "Cairo\nGiza", "questions-0-correct_number": "1",
                "questions-1-kind": "voice", "questions-1-text": "Describe your day", "questions-1-points": "4"}
        data.update(extra)
        return data

    def test_teacher_builds_a_session_exam_for_their_own_session(self):
        self.client.force_login(self.teacher)
        url = reverse("dashboard:exam_for_lesson", args=[self.l2.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, self.formset())
        self.assertEqual(resp.status_code, 302)
        exam = Exam.objects.get(lesson=self.l2)
        self.assertTrue(exam.is_published)
        qs = list(exam.questions.all())
        self.assertEqual([q.kind for q in qs], ["mcq", "voice"])
        self.assertEqual((qs[0].options, qs[0].correct_index), (["Cairo", "Giza"], 0))
        self.assertEqual(exam.total_points(), Decimal("5"))

    def test_multiple_choice_needs_options_and_a_valid_correct_number(self):
        self.client.force_login(self.teacher)
        url = reverse("dashboard:exam_for_lesson", args=[self.l2.pk])
        resp = self.client.post(url, self.formset(**{"questions-0-options_text": "only one"}))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(url, self.formset(**{"questions-0-correct_number": "5"}))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Exam.objects.filter(lesson=self.l2).exists())

    def test_teacher_cannot_touch_another_teachers_group(self):
        self.client.force_login(self.other_teacher)
        for name, args in (("dashboard:exam_for_lesson", [self.l1.pk]), ("dashboard:exam_for_level", [self.cohort.pk]),
                           ("dashboard:exam_results", [self.exam.pk])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404, name)

    def test_one_level_exam_per_group(self):
        self.client.force_login(self.teacher)
        url = reverse("dashboard:exam_for_level", args=[self.cohort.pk])
        self.client.post(url, self.formset())
        self.client.post(url, self.formset(title="Edited"))
        self.assertEqual(Exam.objects.filter(cohort=self.cohort, kind="level").count(), 1)
        self.assertEqual(Exam.objects.get(kind="level").title, "Edited")

    def test_admin_can_open_any_groups_exam_tools(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:exam_for_lesson", args=[self.l1.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:exams_list")).status_code, 200)

    def test_results_list_shows_who_handed_in_late_or_not_at_all(self):
        self.hand_in()
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse("dashboard:exam_results", args=[self.exam.pk]))
        self.assertEqual(resp.context["rows"][0]["state"], STATE_SUBMITTED)
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
