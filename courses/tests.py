import datetime
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from quiz.models import PlacementResult
from team.models import TeamMember

from .models import Attendance, Cohort, CohortSlot, Course, Enrollment, Lesson, LessonAttachment

PRIVATE = tempfile.mkdtemp()


def make_course(**kw):
    defaults = dict(title_ar="كورس تجريبي", title_en="Demo", is_published=True)
    defaults.update(kw)
    return Course.objects.create(**defaults)


def make_cohort(course=None, **kw):
    # 2030-01-07 is a Monday
    defaults = dict(course=course or make_course(), start_date=datetime.date(2030, 1, 7), weeks=3)
    defaults.update(kw)
    return Cohort.objects.create(**defaults)


class GenerateLessonsTests(TestCase):
    def test_generates_one_lesson_per_slot_per_week(self):
        cohort = make_cohort()
        CohortSlot.objects.create(cohort=cohort, weekday=0, start_time=datetime.time(18, 0))
        CohortSlot.objects.create(cohort=cohort, weekday=3, start_time=datetime.time(20, 0), duration_minutes=90)
        self.assertEqual(cohort.generate_lessons(), 6)
        lessons = list(cohort.lessons.all())
        self.assertEqual([l.number for l in lessons], [1, 2, 3, 4, 5, 6])
        self.assertEqual(lessons[0].starts_at.weekday(), 0)
        self.assertEqual(lessons[1].starts_at.weekday(), 3)
        self.assertEqual(lessons[1].duration_minutes, 90)

    def test_rerun_is_idempotent_and_keeps_edits(self):
        cohort = make_cohort()
        CohortSlot.objects.create(cohort=cohort, weekday=0, start_time=datetime.time(18, 0))
        cohort.generate_lessons()
        lesson = cohort.lessons.first()
        lesson.zoom_url = "https://zoom.us/j/1"
        lesson.save()
        self.assertEqual(cohort.generate_lessons(), 0)
        self.assertEqual(cohort.lessons.count(), 3)
        lesson.refresh_from_db()
        self.assertEqual(lesson.zoom_url, "https://zoom.us/j/1")

    def test_start_date_midweek_begins_on_next_matching_day(self):
        cohort = make_cohort(start_date=datetime.date(2030, 1, 9), weeks=1)  # Wednesday
        CohortSlot.objects.create(cohort=cohort, weekday=0, start_time=datetime.time(18, 0))
        self.assertEqual(cohort.generate_lessons(), 1)
        self.assertEqual(timezone.localtime(cohort.lessons.get().starts_at).date(), datetime.date(2030, 1, 14))

    def test_no_start_date_generates_nothing(self):
        cohort = make_cohort(start_date=None)
        CohortSlot.objects.create(cohort=cohort, weekday=0, start_time=datetime.time(18, 0))
        self.assertEqual(cohort.generate_lessons(), 0)


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
        cohort = make_cohort()
        enrollment = Enrollment.objects.create(user=user, course=cohort.course, cohort=cohort)
        lessons = [Lesson.objects.create(cohort=cohort, starts_at=timezone.now() + datetime.timedelta(days=i), number=i + 1)
                   for i in range(4)]
        Attendance.objects.create(lesson=lessons[0], enrollment=enrollment, status=Attendance.PRESENT)
        Attendance.objects.create(lesson=lessons[1], enrollment=enrollment, status=Attendance.ABSENT)
        self.assertEqual(enrollment.progress(), (1, 4, 25))


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class AccessTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PRIVATE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.cohort = make_cohort()
        self.course = self.cohort.course
        self.lesson = Lesson.objects.create(
            cohort=self.cohort, number=1, starts_at=timezone.now() + datetime.timedelta(days=1),
            zoom_url="https://zoom.us/j/secret", recording_url="https://youtu.be/secret",
        )
        self.attachment = LessonAttachment.objects.create(
            lesson=self.lesson, title="Notes", file=SimpleUploadedFile("notes.pdf", b"%PDF-secret"),
        )
        self.student = User.objects.create_user("s", "s@x.com", "pw")
        self.outsider = User.objects.create_user("o", "o@x.com", "pw")
        Enrollment.objects.create(user=self.student, course=self.course, cohort=self.cohort)

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
        PlacementResult.objects.create(user=self.student, percent=64)
        second = Lesson.objects.create(cohort=self.cohort, number=2, starts_at=self.lesson.starts_at + datetime.timedelta(days=7))
        self.client.force_login(self.student)
        first_resp = self.client.get(reverse("courses:lesson", args=[self.lesson.pk]))
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

    def test_admin_creates_cohort_with_own_slots_and_generates(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:cohort_create", args=[self.course.pk]), {
            "name": "مجموعة السبت", "mode": "group", "weeks": 2, "min_students": 4, "max_students": 8, "start_date": "2030-01-07",
            "slots-TOTAL_FORMS": 2, "slots-INITIAL_FORMS": 0, "slots-MIN_NUM_FORMS": 0, "slots-MAX_NUM_FORMS": 1000,
            "slots-0-weekday": 0, "slots-0-start_time": "18:00", "slots-0-duration_minutes": 60,
            "slots-1-weekday": "", "slots-1-start_time": "", "slots-1-duration_minutes": 60,
        })
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["form"].errors)
        cohort = Cohort.objects.get(name="مجموعة السبت")
        self.assertEqual(cohort.slots.count(), 1)
        self.client.post(reverse("dashboard:lessons_generate", args=[cohort.pk]))
        self.assertEqual(cohort.lessons.count(), 2)

    def test_admin_creates_course_without_any_schedule(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:course_create"), {
            "title_ar": "كورس جديد", "audience": "students", "offers_group": "on", "is_published": "on"})
        self.assertEqual(resp.status_code, 302)

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
        cohort = make_cohort(self.course)
        enrollment = Enrollment.objects.create(user=self.student, course=self.course, cohort=cohort)
        lesson = Lesson.objects.create(cohort=cohort, number=1, starts_at=timezone.now())
        self.client.force_login(self.admin)
        url = reverse("dashboard:attendance_form", args=[cohort.pk, lesson.pk])
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
        EnrollmentRequest.objects.filter(pk=self.req.pk).update(payment_status="paid")
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


class AudienceAndModeTests(TestCase):
    def setUp(self):
        self.students = make_course(title_ar="كورس طلاب", audience=Course.AUDIENCE_STUDENTS)
        self.teachers = make_course(title_ar="كورس مدرسين", audience=Course.AUDIENCE_TEACHERS)
        self.group_only = make_course(title_ar="كورس جروب فقط", offers_private=False, price_group=900)

    def test_public_pages_show_student_courses_only(self):
        url = reverse("courses:list")
        resp = self.client.get(url)
        self.assertContains(resp, "كورس طلاب")
        self.assertNotContains(resp, "كورس مدرسين")
        self.assertEqual(self.client.get(reverse("courses:detail", args=[self.teachers.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse("courses:apply", args=[self.teachers.slug])).status_code, 404)

    def test_apply_rejects_mode_the_course_does_not_offer(self):
        resp = self.client.post(reverse("courses:apply", args=[self.group_only.slug]), {**APPLY, "mode": "private"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(EnrollmentRequest.objects.exists())
        resp = self.client.post(reverse("courses:apply", args=[self.group_only.slug]), {**APPLY, "mode": "group"})
        self.assertEqual(resp.status_code, 302)

    def test_price_is_the_courses_own_per_mode(self):
        self.assertEqual(self.group_only.price_for("group"), 900)
        self.assertIsNone(self.group_only.price_for("private"))

    def test_public_pages_show_no_level_or_schedule(self):
        resp = self.client.get(reverse("courses:detail", args=[self.students.slug]))
        self.assertFalse(hasattr(Course, "level"))
        self.assertNotContains(resp, "المواعيد الأسبوعية")

    def test_detail_shows_only_offered_modes(self):
        resp = self.client.get(reverse("courses:detail", args=[self.group_only.slug]))
        self.assertContains(resp, "900")
        self.assertContains(resp, 'class="c-plan"', count=1)  # group only; private is not offered

    def test_dashboard_requires_at_least_one_mode(self):
        admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        self.client.force_login(admin)
        resp = self.client.post(reverse("dashboard:course_create"), {
            "title_ar": "x", "audience": "students",
            "slots-TOTAL_FORMS": 0, "slots-INITIAL_FORMS": 0, "slots-MIN_NUM_FORMS": 0, "slots-MAX_NUM_FORMS": 1000,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "اختر نوعًا واحدًا على الأقل")


class PerStudentTimesTests(TestCase):
    """Times differ per group/student: each cohort has its own teacher, slots and sessions."""

    def setUp(self):
        self.course = make_course()
        self.cohort_a = make_cohort(self.course)
        self.cohort_b = make_cohort(self.course, start_date=datetime.date(2030, 2, 4))
        CohortSlot.objects.create(cohort=self.cohort_a, weekday=0, start_time=datetime.time(18, 0))
        CohortSlot.objects.create(cohort=self.cohort_b, weekday=2, start_time=datetime.time(21, 0))
        self.cohort_a.generate_lessons()
        self.cohort_b.generate_lessons()
        self.ann = User.objects.create_user("ann", "ann@x.com", "pw")
        self.bob = User.objects.create_user("bob", "bob@x.com", "pw")
        self.cara = User.objects.create_user("cara", "cara@x.com", "pw")
        Enrollment.objects.create(user=self.ann, course=self.course, cohort=self.cohort_a)
        Enrollment.objects.create(user=self.bob, course=self.course, cohort=self.cohort_b)
        Enrollment.objects.create(user=self.cara, course=self.course)  # not placed yet

    def test_cohorts_have_independent_schedules(self):
        self.assertEqual(self.cohort_a.lessons.first().starts_at.weekday(), 0)
        self.assertEqual(self.cohort_b.lessons.first().starts_at.weekday(), 2)

    def test_student_cannot_open_another_cohorts_lesson(self):
        mine, theirs = self.cohort_a.lessons.first(), self.cohort_b.lessons.first()
        self.client.force_login(self.ann)
        self.assertEqual(self.client.get(reverse("courses:lesson", args=[mine.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("courses:lesson", args=[theirs.pk])).status_code, 404)

    def test_unplaced_student_sees_waiting_message_and_no_lessons(self):
        self.client.force_login(self.cara)
        resp = self.client.get(reverse("courses:detail", args=[self.course.slug]))
        self.assertContains(resp, "سيتواصل معك فريقنا")
        self.assertEqual(self.client.get(reverse("courses:lesson", args=[self.cohort_a.lessons.first().pk])).status_code, 404)
        self.assertContains(self.client.get(reverse("courses:mine")), "سيتواصل معك فريقنا")

    def test_course_page_shows_only_own_sessions(self):
        self.client.force_login(self.ann)
        resp = self.client.get(reverse("courses:detail", args=[self.course.slug]))
        self.assertEqual(len(resp.context["lessons"]), self.cohort_a.lessons.count())
        self.assertNotContains(resp, self.cohort_b.lessons.first().starts_at.strftime("%Y-%m-%d"))

    def test_admin_assigns_student_to_cohort_of_the_same_course_only(self):
        admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        self.client.force_login(admin)
        enrollment = Enrollment.objects.get(user=self.cara)
        url = reverse("dashboard:enrollment_action", args=[self.course.pk, enrollment.pk, "assign"])
        self.client.post(url, {"cohort": self.cohort_b.pk})
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.cohort, self.cohort_b)
        other = make_cohort(make_course(title_ar="غيره"))
        resp = self.client.post(url, {"cohort": other.pk})
        self.assertEqual(resp.status_code, 404)

    def test_enroll_from_request_with_cohort(self):
        admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        req = EnrollmentRequest.objects.create(course=self.course, user=User.objects.create_user("n", "n@x.com", "pw"),
                                               full_name="N", email="n@x.com", phone="1", payment_status="paid")
        self.cohort_a.confirmed_at = timezone.now()
        self.cohort_a.save()
        self.client.force_login(admin)
        self.client.post(reverse("dashboard:request_enroll", args=[req.pk]), {"cohort": self.cohort_a.pk})
        self.assertEqual(Enrollment.objects.get(user=req.user).cohort, self.cohort_a)


class WaitingGroupTests(TestCase):
    """Group cohorts collect students on a staff-only waiting list until the minimum is reached."""

    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        self.teacher = TeamMember.objects.create(name_ar="أ. منى", role_ar="مدرسة", specialties_ar="IELTS")
        self.cohort = make_cohort(mode="group", min_students=2, max_students=3, teacher=self.teacher)
        self.course = self.cohort.course
        CohortSlot.objects.create(cohort=self.cohort, weekday=0, start_time=datetime.time(18, 0))
        self.client.force_login(self.admin)

    def place(self, n):
        user = User.objects.create_user(f"w{n}", f"w{n}@x.com", "pw")
        req = EnrollmentRequest.objects.create(course=self.course, user=user, full_name=f"W{n}", email=user.email, phone="1",
                                               payment_status="paid")
        resp = self.client.post(reverse("dashboard:request_enroll", args=[req.pk]), {"cohort": self.cohort.pk})
        req.refresh_from_db()
        return req, resp

    def test_student_waits_without_enrollment_until_confirmed(self):
        req, _ = self.place(1)
        self.assertEqual(req.status, EnrollmentRequest.STATUS_WAITING)
        self.assertFalse(Enrollment.objects.exists())
        self.assertFalse(self.cohort.is_ready_to_confirm)

    def test_confirm_needs_minimum_then_enrols_everyone_and_makes_sessions(self):
        confirm = reverse("dashboard:cohort_confirm", args=[self.course.pk, self.cohort.pk])
        self.place(1)
        self.client.post(confirm)
        self.cohort.refresh_from_db()
        self.assertIsNone(self.cohort.confirmed_at)
        self.place(2)
        self.assertTrue(Cohort.objects.get(pk=self.cohort.pk).is_ready_to_confirm)
        self.client.post(confirm)
        self.cohort.refresh_from_db()
        self.assertIsNotNone(self.cohort.confirmed_at)
        self.assertEqual(Enrollment.objects.filter(cohort=self.cohort, status="active").count(), 2)
        self.assertEqual(EnrollmentRequest.objects.filter(status=EnrollmentRequest.STATUS_ENROLLED).count(), 2)
        self.assertTrue(self.cohort.lessons.exists())

    def test_launched_group_is_frozen_for_adding_and_removing(self):
        self.place(1); self.place(2)
        self.client.post(reverse("dashboard:cohort_confirm", args=[self.course.pk, self.cohort.pk]))
        self.assertTrue(Cohort.objects.get(pk=self.cohort.pk).is_locked)
        req, _ = self.place(3)  # cannot join
        self.assertNotEqual(req.status, EnrollmentRequest.STATUS_ENROLLED)
        self.assertEqual(Enrollment.objects.filter(cohort=self.cohort).count(), 2)
        member = Enrollment.objects.filter(cohort=self.cohort).first()  # cannot leave, by any route
        other = make_cohort(course=self.course, mode="private")
        self.client.post(reverse("dashboard:student_action"), {"kind": "enrollment", "id": member.pk, "action": "remove"})
        self.client.post(reverse("dashboard:student_action"), {"kind": "enrollment", "id": member.pk, "action": "move", "cohort": other.pk})
        self.client.post(reverse("dashboard:enrollment_action", args=[self.course.pk, member.pk, "assign"]), {"cohort": other.pk})
        self.client.post(reverse("dashboard:enrollment_action", args=[self.course.pk, member.pk, "delete"]))
        member.refresh_from_db()
        self.assertEqual(member.cohort_id, self.cohort.pk)

    def test_cannot_launch_without_a_teacher(self):
        self.cohort.teacher = None
        self.cohort.save()
        self.place(1); self.place(2)
        self.client.post(reverse("dashboard:cohort_confirm", args=[self.course.pk, self.cohort.pk]))
        self.assertIsNone(Cohort.objects.get(pk=self.cohort.pk).confirmed_at)

    def test_unpaid_request_cannot_be_added_to_a_group(self):
        user = User.objects.create_user("u", "u@x.com", "pw")
        req = EnrollmentRequest.objects.create(course=self.course, user=user, full_name="U", email="u@x.com", phone="1")
        self.client.post(reverse("dashboard:request_enroll", args=[req.pk]), {"cohort": self.cohort.pk})
        req.refresh_from_db()
        self.assertNotEqual(req.status, EnrollmentRequest.STATUS_WAITING)
        self.assertFalse(Enrollment.objects.exists())
        page = self.client.get(reverse("dashboard:request_detail", args=[req.pk]))
        self.assertContains(page, "لم يدفع بعد")
        self.assertNotContains(page, "request_enroll")
        EnrollmentRequest.objects.filter(pk=req.pk).update(payment_status="paid")
        page = self.client.get(reverse("dashboard:request_detail", args=[req.pk]))
        self.assertContains(page, reverse("dashboard:request_enroll", args=[req.pk]))
        self.client.post(reverse("dashboard:request_enroll", args=[req.pk]), {"cohort": self.cohort.pk})
        req.refresh_from_db()
        self.assertEqual(req.status, EnrollmentRequest.STATUS_WAITING)

    def test_create_account_for_guest_request_then_add_to_group(self):
        req = EnrollmentRequest.objects.create(course=self.course, full_name="سلمى أحمد", email="Salma@X.com",
                                               phone="0100", payment_status="paid")
        page = self.client.get(reverse("dashboard:request_detail", args=[req.pk]))
        self.assertContains(page, "إنشاء حساب للطالب")
        resp = self.client.post(reverse("dashboard:request_create_account", args=[req.pk]), follow=True)
        req.refresh_from_db()
        self.assertEqual(req.user.email, "salma@x.com")
        self.assertEqual(req.user.profile.phone, "0100")
        self.assertTrue(req.user.has_usable_password())
        self.assertContains(resp, "كلمة المرور المؤقتة")
        self.client.post(reverse("dashboard:request_enroll", args=[req.pk]), {"cohort": self.cohort.pk})
        req.refresh_from_db()
        self.assertEqual(req.status, EnrollmentRequest.STATUS_WAITING)

    def test_create_account_reuses_existing_account_with_same_email(self):
        existing = User.objects.create_user("old", "same@x.com", "pw")
        req = EnrollmentRequest.objects.create(course=self.course, full_name="S", email="SAME@x.com", phone="1")
        self.client.post(reverse("dashboard:request_create_account", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.user, existing)
        self.assertEqual(User.objects.filter(email__iexact="same@x.com").count(), 1)

    def test_launch_early_with_force(self):
        self.place(1)
        self.client.post(reverse("dashboard:cohort_confirm", args=[self.course.pk, self.cohort.pk]), {"force": "1"})
        self.assertIsNotNone(Cohort.objects.get(pk=self.cohort.pk).confirmed_at)

    def test_move_and_remove_students_before_launch(self):
        req1, _ = self.place(1)
        second = make_cohort(course=self.course, mode="group", min_students=2, max_students=3)
        act = reverse("dashboard:student_action")
        self.client.post(act, {"kind": "request", "id": req1.pk, "action": "move", "cohort": second.pk})
        req1.refresh_from_db()
        self.assertEqual(req1.cohort_id, second.pk)
        self.client.post(act, {"kind": "request", "id": req1.pk, "action": "remove"})
        req1.refresh_from_db()
        self.assertIsNone(req1.cohort_id)
        self.assertEqual(req1.status, EnrollmentRequest.STATUS_CONTACTED)

    def test_enrolled_student_moves_between_open_cohorts(self):
        private = make_cohort(course=self.course, mode="private")
        user = User.objects.create_user("e", "e@x.com", "pw")
        enrollment = Enrollment.objects.create(user=user, course=self.course, cohort=private)
        target = make_cohort(course=self.course, mode="group", min_students=2, max_students=3)
        self.client.post(reverse("dashboard:student_action"), {"kind": "enrollment", "id": enrollment.pk, "action": "move", "cohort": target.pk})
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.cohort_id, target.pk)

    def test_cohort_and_student_pages_show_status_test_and_payment(self):
        req1, _ = self.place(1)
        PlacementResult.objects.create(user=req1.user, percent=64)
        req2, _ = self.place(2)
        EnrollmentRequest.objects.filter(pk=req2.pk).update(payment_status="paid")
        resp = self.client.get(reverse("dashboard:cohort_detail", args=[self.cohort.pk]))
        self.assertContains(resp, "64%")
        self.assertContains(resp, "لم يُنهِه")
        self.assertContains(resp, "دفع")
        user = User.objects.get(username="w1")
        self.assertContains(resp, reverse("dashboard:student_detail", args=[user.pk]))
        page = self.client.get(reverse("dashboard:student_detail", args=[user.pk]))
        self.assertContains(page, "64%")
        self.assertContains(page, self.course.title_ar)

    def test_student_page_hides_actions_when_locked(self):
        self.place(1); self.place(2)
        self.client.post(reverse("dashboard:cohort_confirm", args=[self.course.pk, self.cohort.pk]))
        user = User.objects.get(username="w1")
        self.assertContains(self.client.get(reverse("dashboard:student_detail", args=[user.pk])), "مُطلقة ومُسندة")

    def test_full_group_rejects_more(self):
        for i in range(1, 4):
            self.place(i)
        req, _ = self.place(4)
        self.assertNotEqual(req.status, EnrollmentRequest.STATUS_WAITING)
        self.assertEqual(self.cohort.seats_taken(), 3)

    def test_private_cohort_enrols_immediately(self):
        private = make_cohort(course=self.course, mode="private")
        user = User.objects.create_user("p", "p@x.com", "pw")
        req = EnrollmentRequest.objects.create(course=self.course, user=user, full_name="P", email="p@x.com", phone="1",
                                               payment_status="paid")
        self.client.post(reverse("dashboard:request_enroll", args=[req.pk]), {"cohort": private.pk})
        self.assertTrue(Enrollment.objects.filter(user=user, cohort=private).exists())

    def test_all_cohorts_page_filters(self):
        self.place(1); self.place(2)
        url = reverse("dashboard:all_cohorts")
        self.assertContains(self.client.get(url), "اكتمل العدد")
        self.assertContains(self.client.get(url, {"status": "ready"}), "اكتمل العدد — تحتاج إطلاق")
        self.assertNotContains(self.client.get(url, {"status": "launched"}), f"/dashboard/cohorts/{self.cohort.pk}/")
        self.assertContains(self.client.get(url, {"q": "zzz"}), "لا توجد مجموعات")
        self.assertContains(self.client.get(reverse("dashboard:cohort_detail", args=[self.cohort.pk])), "W1")

    def test_pages_render(self):
        self.place(1); self.place(2)
        self.assertContains(self.client.get(reverse("dashboard:cohorts_list", args=[self.course.pk])), "اكتمل العدد")
        self.assertContains(self.client.get(reverse("dashboard:index")), "مجموعات تنتظر اكتمال العدد")


class ArabicSlugTests(TestCase):
    def test_arabic_titled_course_pages_resolve(self):
        course = make_course(title_ar="إنجليزي للمبتدئين", title_en="")
        self.assertEqual(self.client.get(reverse("courses:detail", args=[course.slug])).status_code, 200)
        self.assertEqual(self.client.get(reverse("courses:apply", args=[course.slug])).status_code, 200)
        self.assertContains(self.client.get(reverse("courses:list")), course.title_ar)

    def test_reserved_words_are_not_used_as_slugs(self):
        self.assertNotEqual(make_course(title_ar="mine", title_en="").slug, "mine")


class WorkshopBookingTests(TestCase):
    def test_booking_lands_in_requests_marked_as_teacher(self):
        resp = self.client.post(reverse("core:teachers"), {"full_name": "Mona", "email": "m@x.com", "phone": "0100", "mode": "private", "payment_method": "online"})
        self.assertContains(resp, "تم استلام طلب الحجز")
        req = EnrollmentRequest.objects.get()
        self.assertEqual(req.kind, EnrollmentRequest.KIND_TEACHER)
        self.assertIsNone(req.course)
        self.assertEqual((req.mode, req.payment_method), ("private", "online"))

    def test_phone_is_required(self):
        resp = self.client.post(reverse("core:teachers"), {"full_name": "Mona", "email": "m@x.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(EnrollmentRequest.objects.exists())

    def test_dashboard_lists_and_filters_by_kind(self):
        admin = User.objects.create_superuser("adm2", "adm2@x.com", "pw")
        EnrollmentRequest.objects.create(full_name="Teacher T", email="t@x.com", phone="1", kind=EnrollmentRequest.KIND_TEACHER)
        EnrollmentRequest.objects.create(full_name="Student S", email="s@x.com", phone="2")
        self.client.force_login(admin)
        url = reverse("dashboard:requests_list")
        resp = self.client.get(url + "?kind=teacher")
        self.assertContains(resp, "Teacher T")
        self.assertNotContains(resp, "Student S")
        self.assertContains(self.client.get(url + "?q=Student"), "Student S")
        detail = self.client.get(reverse("dashboard:request_detail", args=[EnrollmentRequest.objects.get(full_name="Teacher T").pk]))
        self.assertContains(detail, "ورشة المدرّسين")


class SemiPrivateTests(TestCase):
    """Course types are Group, Semi private and Private; semi private fills up and launches like a group."""

    def setUp(self):
        self.course = make_course(offers_semi_private=True, price_semi_private=900, price_group=600, price_private=1500)

    def test_course_offers_three_modes_with_prices(self):
        self.assertEqual(self.course.allowed_modes(), ["group", "semi_private", "private"])
        self.assertEqual(self.course.price_for("semi_private"), 900)
        self.assertEqual(self.course.price_for("group"), 600)
        self.assertEqual(self.course.price_for("private"), 1500)

    def test_semi_private_off_by_default(self):
        self.assertEqual(make_course(title_ar="x").allowed_modes(), ["group", "private"])

    def test_public_pages_show_all_three_types(self):
        self.course.is_published = True
        self.course.save()
        listing = self.client.get(reverse("courses:list"))
        self.assertContains(listing, "Semi private")
        self.assertContains(listing, "?mode=semi_private")
        apply_page = self.client.get(reverse("courses:apply", args=[self.course.slug]) + "?mode=semi_private")
        self.assertContains(apply_page, 'value="semi_private"')
        self.assertContains(apply_page, "900")

    def test_apply_with_semi_private_saves_request_and_price(self):
        self.course.is_published = True
        self.course.save()
        resp = self.client.post(reverse("courses:apply", args=[self.course.slug]), {
            "full_name": "A B", "email": "a@x.com", "phone": "1", "mode": "semi_private"})
        self.assertEqual(resp.status_code, 302)
        req = EnrollmentRequest.objects.get(email="a@x.com")
        self.assertEqual(req.mode, "semi_private")
        self.assertEqual(req.price, 900)

    def test_apply_rejects_unoffered_mode(self):
        course = make_course(title_ar="بدون semi", is_published=True)
        resp = self.client.post(reverse("courses:apply", args=[course.slug]), {
            "full_name": "A B", "email": "a@x.com", "phone": "1", "mode": "semi_private"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(EnrollmentRequest.objects.exists())

    def test_workshop_form_keeps_only_group_and_private(self):
        from .forms import WorkshopBookingForm
        self.assertEqual([c[0] for c in WorkshopBookingForm().fields["mode"].choices], ["group", "private"])

    def test_semi_private_cohort_waits_launches_and_freezes_like_a_group(self):
        teacher = TeamMember.objects.create(name_ar="م", role_ar="مدرس", specialties_ar="x")
        cohort = make_cohort(course=self.course, mode="semi_private", min_students=2, max_students=3, teacher=teacher)
        self.assertTrue(cohort.is_forming)
        admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        self.client.force_login(admin)
        for n in (1, 2):
            user = User.objects.create_user(f"s{n}", f"s{n}@x.com", "pw")
            req = EnrollmentRequest.objects.create(course=self.course, user=user, full_name=f"S{n}", email=user.email,
                                                   phone="1", mode="semi_private", payment_status="paid")
            self.client.post(reverse("dashboard:request_enroll", args=[req.pk]), {"cohort": cohort.pk})
        self.assertFalse(Enrollment.objects.exists())  # waiting, not enrolled
        self.client.post(reverse("dashboard:cohort_confirm", args=[self.course.pk, cohort.pk]))
        cohort.refresh_from_db()
        self.assertTrue(cohort.is_locked)
        self.assertEqual(Enrollment.objects.filter(cohort=cohort).count(), 2)

    def test_dashboard_course_form_accepts_semi_private_only(self):
        admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        self.client.force_login(admin)
        resp = self.client.post(reverse("dashboard:course_create"), {
            "title_ar": "كورس semi", "audience": "students", "offers_semi_private": "on",
            "price_semi_private": "800", "is_published": "on"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Course.objects.get(title_ar="كورس semi").allowed_modes(), ["semi_private"])
        resp = self.client.post(reverse("dashboard:course_create"), {"title_ar": "لا شيء", "audience": "students"})
        self.assertEqual(resp.status_code, 200)
