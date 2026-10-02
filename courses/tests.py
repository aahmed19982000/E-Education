import datetime
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from levels.models import Level
from quiz.models import PlacementResult

from .models import Attendance, Course, CourseSlot, Enrollment, Lesson, LessonAttachment

PRIVATE = tempfile.mkdtemp()


def make_course(**kw):
    defaults = dict(title_ar="كورس تجريبي", title_en="Demo", is_published=True,
                    start_date=datetime.date(2030, 1, 7), weeks=3)  # 2030-01-07 is a Monday
    defaults.update(kw)
    return Course.objects.create(**defaults)


class GenerateLessonsTests(TestCase):
    def test_generates_one_lesson_per_slot_per_week(self):
        course = make_course()
        CourseSlot.objects.create(course=course, weekday=0, start_time=datetime.time(18, 0))
        CourseSlot.objects.create(course=course, weekday=3, start_time=datetime.time(20, 0), duration_minutes=90)
        self.assertEqual(course.generate_lessons(), 6)
        lessons = list(course.lessons.all())
        self.assertEqual([l.number for l in lessons], [1, 2, 3, 4, 5, 6])
        self.assertEqual(lessons[0].starts_at.weekday(), 0)
        self.assertEqual(lessons[1].starts_at.weekday(), 3)
        self.assertEqual(lessons[1].duration_minutes, 90)

    def test_rerun_is_idempotent_and_keeps_edits(self):
        course = make_course()
        CourseSlot.objects.create(course=course, weekday=0, start_time=datetime.time(18, 0))
        course.generate_lessons()
        lesson = course.lessons.first()
        lesson.zoom_url = "https://zoom.us/j/1"
        lesson.save()
        self.assertEqual(course.generate_lessons(), 0)
        self.assertEqual(course.lessons.count(), 3)
        lesson.refresh_from_db()
        self.assertEqual(lesson.zoom_url, "https://zoom.us/j/1")

    def test_start_date_midweek_begins_on_next_matching_day(self):
        course = make_course(start_date=datetime.date(2030, 1, 9), weeks=1)  # Wednesday
        CourseSlot.objects.create(course=course, weekday=0, start_time=datetime.time(18, 0))
        self.assertEqual(course.generate_lessons(), 1)
        self.assertEqual(timezone.localtime(course.lessons.get().starts_at).date(), datetime.date(2030, 1, 14))

    def test_no_start_date_generates_nothing(self):
        course = make_course(start_date=None)
        CourseSlot.objects.create(course=course, weekday=0, start_time=datetime.time(18, 0))
        self.assertEqual(course.generate_lessons(), 0)


class ModelTests(TestCase):
    def test_slug_unique(self):
        a = make_course(title_ar="كورس", title_en="")
        b = make_course(title_ar="كورس", title_en="")
        self.assertNotEqual(a.slug, b.slug)

    def test_enrollment_unique_per_user_course(self):
        user = User.objects.create_user("u", "u@x.com", "pw")
        course = make_course()
        Enrollment.objects.create(user=user, course=course)
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(user=user, course=course)

    def test_progress_counts_present_only(self):
        user = User.objects.create_user("u", "u@x.com", "pw")
        course = make_course()
        enrollment = Enrollment.objects.create(user=user, course=course)
        lessons = [Lesson.objects.create(course=course, starts_at=timezone.now() + datetime.timedelta(days=i), number=i + 1)
                   for i in range(4)]
        Attendance.objects.create(lesson=lessons[0], enrollment=enrollment, status=Attendance.PRESENT)
        Attendance.objects.create(lesson=lessons[1], enrollment=enrollment, status=Attendance.ABSENT)
        self.assertEqual(course.progress_for(enrollment), (1, 4, 25))


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class AccessTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PRIVATE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.course = make_course()
        self.lesson = Lesson.objects.create(
            course=self.course, number=1, starts_at=timezone.now() + datetime.timedelta(days=1),
            zoom_url="https://zoom.us/j/secret", recording_url="https://youtu.be/secret",
        )
        self.attachment = LessonAttachment.objects.create(
            lesson=self.lesson, title="Notes", file=SimpleUploadedFile("notes.pdf", b"%PDF-secret"),
        )
        self.student = User.objects.create_user("s", "s@x.com", "pw")
        self.outsider = User.objects.create_user("o", "o@x.com", "pw")
        Enrollment.objects.create(user=self.student, course=self.course)

    def test_public_course_page_hides_private_links(self):
        resp = self.client.get(reverse("courses:detail", args=[self.course.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "zoom.us/j/secret")
        self.assertNotContains(resp, "youtu.be/secret")

    def test_unpublished_course_hidden_from_public(self):
        self.course.is_published = False
        self.course.save()
        self.assertEqual(self.client.get(reverse("courses:detail", args=[self.course.slug])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("courses:list")), self.course.title_ar)

    def test_lesson_requires_login(self):
        resp = self.client.get(reverse("courses:lesson", args=[self.lesson.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    def test_outsider_cannot_see_lesson_or_file(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("courses:lesson", args=[self.lesson.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("courses:attachment", args=[self.attachment.pk])).status_code, 404)

    def test_enrolled_student_sees_zoom_recording_and_downloads(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse("courses:lesson", args=[self.lesson.pk]))
        self.assertContains(resp, "https://zoom.us/j/secret")
        self.assertContains(resp, "https://youtu.be/secret")
        file_resp = self.client.get(reverse("courses:attachment", args=[self.attachment.pk]))
        self.assertEqual(file_resp.status_code, 200)
        self.assertEqual(b"".join(file_resp.streaming_content), b"%PDF-secret")

    def test_cancelled_enrollment_loses_access(self):
        Enrollment.objects.filter(user=self.student).update(status=Enrollment.STATUS_CANCELLED)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("courses:lesson", args=[self.lesson.pk])).status_code, 404)

    def test_my_courses_lists_only_own_active(self):
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse("courses:mine")), self.course.title_ar)
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(reverse("courses:mine")), self.course.title_ar)

    def test_placement_result_shown_on_first_lesson_only(self):
        level = Level.objects.create(code="B1", order=1, name_ar="متوسط", name_en="Intermediate",
                                     description_ar="d", description_en="d", duration_ar="1", duration_en="1",
                                     price_group=1, price_private=2)
        PlacementResult.objects.create(user=self.student, level=level, percent=64)
        second = Lesson.objects.create(course=self.course, number=2, starts_at=self.lesson.starts_at + datetime.timedelta(days=7))
        self.client.force_login(self.student)
        first_resp = self.client.get(reverse("courses:lesson", args=[self.lesson.pk]))
        self.assertContains(first_resp, "B1")
        self.assertContains(first_resp, "64%")
        self.assertNotContains(self.client.get(reverse("courses:lesson", args=[second.pk])), "64%")


class DashboardCourseTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "a@x.com", "pw")
        self.teacher = User.objects.create_user("t", "t@x.com", "pw", is_staff=True)
        self.teacher.profile.role = "teacher"
        self.teacher.profile.save()
        self.student = User.objects.create_user("s", "s@x.com", "pw")
        self.course = make_course()

    def test_student_cannot_open_dashboard_courses(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("dashboard:courses_list")).status_code, 302)

    def test_teacher_is_read_only(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("dashboard:courses_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:course_create")).status_code, 403)
        resp = self.client.post(reverse("dashboard:enrollments_list", args=[self.course.pk]), {"email": "s@x.com"})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Enrollment.objects.exists())

    def test_admin_creates_course_with_slots_and_generates(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:course_create"), {
            "title_ar": "كورس جديد", "weeks": 2, "start_date": "2030-01-07", "is_published": "on",
            "slots-TOTAL_FORMS": 2, "slots-INITIAL_FORMS": 0, "slots-MIN_NUM_FORMS": 0, "slots-MAX_NUM_FORMS": 1000,
            "slots-0-weekday": 0, "slots-0-start_time": "18:00", "slots-0-duration_minutes": 60,
            "slots-1-weekday": "", "slots-1-start_time": "", "slots-1-duration_minutes": 60,
        })
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["form"].errors)
        course = Course.objects.get(title_ar="كورس جديد")
        self.assertEqual(course.slots.count(), 1)
        self.client.post(reverse("dashboard:lessons_generate", args=[course.pk]))
        self.assertEqual(course.lessons.count(), 2)

    def test_enroll_by_email_and_toggle(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:enrollments_list", args=[self.course.pk])
        self.client.post(url, {"email": "S@X.com"})
        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        self.assertTrue(enrollment.is_active)
        self.client.post(reverse("dashboard:enrollment_action", args=[self.course.pk, enrollment.pk, "toggle"]))
        enrollment.refresh_from_db()
        self.assertFalse(enrollment.is_active)
        resp = self.client.post(url, {"email": "nobody@x.com"})
        self.assertContains(resp, "لا يوجد طالب")

    def test_attendance_marking(self):
        enrollment = Enrollment.objects.create(user=self.student, course=self.course)
        lesson = Lesson.objects.create(course=self.course, number=1, starts_at=timezone.now())
        self.client.force_login(self.admin)
        url = reverse("dashboard:attendance_form", args=[self.course.pk, lesson.pk])
        self.client.post(url, {"present": [enrollment.pk]})
        self.assertEqual(Attendance.objects.get().status, Attendance.PRESENT)
        self.client.post(url, {})
        self.assertEqual(Attendance.objects.get().status, Attendance.ABSENT)


class PlacementRecordingTests(TestCase):
    def test_result_saved_once_for_logged_in_student(self):
        from quiz.models import Category, Question
        cat = Category.objects.create(name_ar="قواعد")
        Question.objects.create(category=cat, text_ar="q", options_ar=["a", "b"], correct_index=0)
        user = User.objects.create_user("s", "s@x.com", "pw")
        self.client.force_login(user)
        self.client.post(reverse("quiz:start"))
        self.client.post(reverse("quiz:question"), {"nav": "finish"})
        self.client.get(reverse("quiz:result"))
        self.client.get(reverse("quiz:result"))
        self.assertEqual(PlacementResult.objects.filter(user=user).count(), 1)


from .models import EnrollmentRequest  # noqa: E402

APPLY = {"full_name": "منى أحمد", "email": "mona@x.com", "phone": "0100", "mode": "private",
         "preferred_times": "مساءً", "notes": ""}


class ApplyFlowTests(TestCase):
    def setUp(self):
        self.course = make_course()

    def test_guest_request_is_saved_then_sent_to_register_with_checkout_next(self):
        resp = self.client.post(reverse("courses:apply", args=[self.course.slug]), APPLY)
        req = EnrollmentRequest.objects.get()
        self.assertIsNone(req.user)
        self.assertEqual(req.status, EnrollmentRequest.STATUS_NEW)
        checkout = reverse("courses:checkout", args=[req.pk])
        self.assertEqual(resp.status_code, 302)
        self.assertIn("mode=register", resp["Location"])
        self.assertIn(f"next={checkout}", resp["Location"])

    def test_guest_registering_claims_the_request_and_lands_on_checkout(self):
        self.client.post(reverse("courses:apply", args=[self.course.slug]), APPLY)
        req = EnrollmentRequest.objects.get()
        checkout = reverse("courses:checkout", args=[req.pk])
        resp = self.client.post(f"{reverse('accounts:login')}?mode=register&next={checkout}", {
            "mode": "register", "full_name": "منى أحمد", "email": "mona@x.com", "phone": "0100",
            "password": "Str0ng-pass-93", "password2": "Str0ng-pass-93",
        })
        self.assertRedirects(resp, checkout, fetch_redirect_response=False)
        self.assertEqual(self.client.get(checkout).status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.user.email, "mona@x.com")

    def test_logged_in_user_goes_straight_to_checkout_with_prefill(self):
        user = User.objects.create_user("m", "m@x.com", "pw", first_name="Mona")
        self.client.force_login(user)
        page = self.client.get(reverse("courses:apply", args=[self.course.slug]))
        self.assertContains(page, "m@x.com")
        resp = self.client.post(reverse("courses:apply", args=[self.course.slug]), APPLY)
        req = EnrollmentRequest.objects.get()
        self.assertEqual(req.user, user)
        self.assertRedirects(resp, reverse("courses:checkout", args=[req.pk]))

    def test_other_users_cannot_open_or_claim_a_checkout(self):
        self.client.post(reverse("courses:apply", args=[self.course.slug]), APPLY)  # guest, in this session
        req = EnrollmentRequest.objects.get()
        other = User.objects.create_user("x", "x@x.com", "pw")
        from django.test import Client
        stranger = Client()
        stranger.force_login(other)
        self.assertEqual(stranger.get(reverse("courses:checkout", args=[req.pk])).status_code, 404)

    def test_unsafe_next_is_ignored(self):
        User.objects.create_user("m", "m@x.com", "pw")
        resp = self.client.post(f"{reverse('accounts:login')}?next=https://evil.example/", {
            "mode": "login", "email": "m@x.com", "password": "pw"})
        self.assertRedirects(resp, reverse("core:home"), fetch_redirect_response=False)

    def test_unpublished_course_cannot_be_applied_to(self):
        self.course.is_published = False
        self.course.save()
        self.assertEqual(self.client.get(reverse("courses:apply", args=[self.course.slug])).status_code, 404)


class DashboardRequestTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "a@x.com", "pw")
        self.course = make_course()
        self.student = User.objects.create_user("s", "s@x.com", "pw")
        self.req = EnrollmentRequest.objects.create(course=self.course, user=self.student, full_name="S",
                                                    email="s@x.com", phone="1")

    def test_admin_sees_unpaid_request_with_contact_details(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:requests_list") + "?paid=unpaid")
        self.assertContains(resp, "S")
        self.assertContains(self.client.get(reverse("dashboard:request_detail", args=[self.req.pk])), "s@x.com")

    def test_enroll_from_request(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:request_enroll", args=[self.req.pk]))
        self.assertTrue(Enrollment.objects.filter(user=self.student, course=self.course).exists())
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, EnrollmentRequest.STATUS_ENROLLED)

    def test_guest_request_cannot_be_enrolled(self):
        self.req.user = None
        self.req.save()
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:request_enroll", args=[self.req.pk]))
        self.assertFalse(Enrollment.objects.exists())
