from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.phone import whatsapp_digits
from contact_us.models import ContactMessage
from courses.models import Course, EnrollmentRequest


class WhatsappDigitsTests(SimpleTestCase):
    def test_normalises_common_formats(self):
        for raw in ("01012345678", "+20 101 234 5678", "0020-101-234-5678", "(010) 1234-5678", "201012345678", "1012345678"):
            self.assertEqual(whatsapp_digits(raw), "201012345678", raw)

    def test_keeps_other_countries_with_plus(self):
        self.assertEqual(whatsapp_digits("+966 50 123 4567"), "966501234567")

    def test_rejects_junk(self):
        for raw in ("", "   ", "abc", "0100", "12", "01012345678x", "+" + "1" * 16):
            self.assertIsNone(whatsapp_digits(raw), raw)


class RegisterWhatsappTests(TestCase):
    URL = "?mode=register"

    def post(self, phone):
        return self.client.post(reverse("accounts:login") + self.URL, {
            "mode": "register", "full_name": "منى أحمد", "email": "mona@x.com", "phone": phone,
            "password": "Str0ng-pass-99", "password2": "Str0ng-pass-99"})

    def test_whatsapp_number_is_required_to_register(self):
        for phone in ("", "abc", "0100"):
            resp = self.post(phone)
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(User.objects.filter(email="mona@x.com").exists(), phone)

    def test_registers_and_saves_the_number(self):
        resp = self.post("0101 234 5678")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(User.objects.get(email="mona@x.com").profile.phone, "0101 234 5678")

    def test_form_marks_the_field_required(self):
        page = self.client.get(reverse("accounts:login") + self.URL)
        self.assertContains(page, 'name="phone"')
        self.assertContains(page, "رقم الواتس اب")
        self.assertRegex(page.content.decode(), r'name="phone"[^>]*required')


class DashboardWhatsappLinkTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        self.client.force_login(self.admin)
        self.course = Course.objects.create(title_ar="كورس", is_published=True)
        self.student = User.objects.create_user("s", "s@x.com", "pw")
        self.student.profile.phone = "01012345678"
        self.student.profile.save()
        self.req = EnrollmentRequest.objects.create(course=self.course, user=self.student, full_name="S", email="s@x.com",
                                                    phone="01012345678")
        self.link = "https://wa.me/201012345678"

    def test_request_pages_show_whatsapp_link(self):
        self.assertContains(self.client.get(reverse("dashboard:requests_list")), self.link)
        page = self.client.get(reverse("dashboard:request_detail", args=[self.req.pk]))
        self.assertContains(page, self.link)
        self.assertContains(page, "إرسال رسالة واتس اب")
        self.assertContains(page, 'target="_blank"')

    def test_student_page_shows_whatsapp_link(self):
        self.assertContains(self.client.get(reverse("dashboard:student_detail", args=[self.student.pk])), self.link)

    def test_contact_messages_show_whatsapp_link(self):
        msg = ContactMessage.objects.create(name="N", email="n@x.com", phone="01012345678", message="hi")
        self.assertContains(self.client.get(reverse("dashboard:messages_list")), self.link)
        self.assertContains(self.client.get(reverse("dashboard:message_detail", args=[msg.pk])), self.link)

    def test_no_link_without_a_usable_number(self):
        EnrollmentRequest.objects.filter(pk=self.req.pk).update(phone="not a number")
        page = self.client.get(reverse("dashboard:request_detail", args=[self.req.pk]))
        self.assertNotContains(page, "wa.me")
