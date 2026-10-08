from django.test import TestCase

# Create your tests here.


from django.contrib.auth.models import User  # noqa: E402
from django.urls import reverse  # noqa: E402

from accounts.models import Profile  # noqa: E402

from .models import SiteSettings  # noqa: E402


class WhatsappFloatTests(TestCase):
    def test_hidden_until_a_number_is_set(self):
        self.assertNotContains(self.client.get(reverse("core:home")), "wa-float")

    def test_shows_on_every_public_page_with_the_chat_link(self):
        SiteSettings.objects.update_or_create(pk=1, defaults={"whatsapp_number": "01012345678"})
        for name in ("core:home", "core:about", "contact:contact", "courses:list", "articles:list", "team:list"):
            page = self.client.get(reverse(name))
            self.assertContains(page, 'class="wa-float"', msg_prefix=name)
            self.assertContains(page, "https://wa.me/201012345678", msg_prefix=name)

    def test_prefilled_message_is_url_encoded(self):
        s = SiteSettings.objects.create(pk=1, whatsapp_number="+20 101 234 5678", whatsapp_message="مرحبًا، أريد كورس")
        self.assertTrue(s.whatsapp_url.startswith("https://wa.me/201012345678?text="))
        self.assertNotIn(" ", s.whatsapp_url)

    def test_unusable_number_hides_the_button(self):
        SiteSettings.objects.update_or_create(pk=1, defaults={"whatsapp_number": "nope"})
        self.assertNotContains(self.client.get(reverse("core:home")), "wa-float")

    def test_not_on_the_dashboard(self):
        SiteSettings.objects.update_or_create(pk=1, defaults={"whatsapp_number": "01012345678"})
        admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        self.client.force_login(admin)
        self.assertNotContains(self.client.get(reverse("dashboard:index")), "wa-float")


class SiteSettingsDashboardTests(TestCase):
    def login(self, role=None, superuser=False):
        user = (User.objects.create_superuser if superuser else User.objects.create_user)("u", "u@x.com", "pw")
        if not superuser:
            user.is_staff = True
            user.save()
            user.profile.role = role
            user.profile.save()
        self.client.force_login(user)

    def test_admin_saves_the_number_and_the_site_shows_it(self):
        self.login(superuser=True)
        resp = self.client.post(reverse("dashboard:site_settings"), {"whatsapp_number": "01012345678", "whatsapp_message": ""})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(SiteSettings.load().whatsapp_number, "01012345678")
        self.assertContains(self.client.get(reverse("core:home")), "https://wa.me/201012345678")

    def test_invalid_number_is_rejected_and_empty_hides_the_icon(self):
        self.login(superuser=True)
        resp = self.client.post(reverse("dashboard:site_settings"), {"whatsapp_number": "abc", "whatsapp_message": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SiteSettings.load().whatsapp_number, "")
        self.client.post(reverse("dashboard:site_settings"), {"whatsapp_number": "01012345678", "whatsapp_message": ""})
        self.client.post(reverse("dashboard:site_settings"), {"whatsapp_number": "", "whatsapp_message": ""})
        self.assertNotContains(self.client.get(reverse("core:home")), "wa-float")

    def test_manager_can_but_support_and_teacher_cannot(self):
        self.login(Profile.ROLE_MANAGER)
        self.assertEqual(self.client.get(reverse("dashboard:site_settings")).status_code, 200)
        self.client.logout()
        User.objects.all().delete()
        self.login(Profile.ROLE_SUPPORT)
        self.assertEqual(self.client.get(reverse("dashboard:site_settings")).status_code, 403)
        self.client.logout()
        User.objects.all().delete()
        self.login(Profile.ROLE_TEACHER)
        self.assertEqual(self.client.get(reverse("dashboard:site_settings")).status_code, 403)

    def test_nav_link_only_for_those_with_access(self):
        self.login(Profile.ROLE_SUPPORT)
        self.assertNotContains(self.client.get(reverse("dashboard:index")), reverse("dashboard:site_settings"))


from courses.models import Course  # noqa: E402


class PlanFeaturesTests(TestCase):
    """Visitors see what Group, Semi private and Private include before they register."""

    def setUp(self):
        self.course = Course.objects.create(title_ar="كورس", is_published=True, offers_semi_private=True,
                                            price_group=600, price_semi_private=900, price_private=1500)

    def test_defaults_show_on_list_detail_and_apply_pages(self):
        for url in (reverse("courses:list"), reverse("courses:detail", args=[self.course.slug]),
                    reverse("courses:apply", args=[self.course.slug])):
            page = self.client.get(url)
            for text in ("الأقل تكلفة للفرد", "مجموعة صغيرة (2 إلى 3 طلاب)", "مدرس لك وحدك"):
                self.assertContains(page, text, msg_prefix=url)

    def test_unoffered_plan_does_not_advertise_its_features(self):
        course = Course.objects.create(title_ar="بلا خصوصي", is_published=True, offers_private=False)
        page = self.client.get(reverse("courses:list"))
        self.assertEqual(page.content.decode().count("مدرس لك وحدك"), 1)  # only the first course offers Private

    def test_dashboard_text_replaces_the_default_for_that_plan_only(self):
        SiteSettings.objects.update_or_create(pk=1, defaults={"features_private_ar": "ميزة أولى\n\n  ميزة ثانية  "})
        page = self.client.get(reverse("courses:list"))
        self.assertContains(page, "<li>ميزة أولى</li>")
        self.assertContains(page, "<li>ميزة ثانية</li>")
        self.assertNotContains(page, "مدرس لك وحدك")
        self.assertContains(page, "الأقل تكلفة للفرد")  # other plans keep their defaults

    def test_english_pages_use_english_text(self):
        SiteSettings.objects.update_or_create(pk=1, defaults={"features_group_ar": "عربي فقط"})
        self.client.get("/lang/en/")
        page = self.client.get(reverse("courses:list"))
        self.assertContains(page, "Lowest cost per person")
        self.assertNotContains(page, "عربي فقط")

    def test_admin_edits_features_from_the_settings_page(self):
        admin = User.objects.create_superuser("adm", "adm@x.com", "pw")
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse("dashboard:site_settings")), "Semi private — بالعربية")
        self.client.post(reverse("dashboard:site_settings"), {
            "whatsapp_number": "", "whatsapp_message": "", "features_semi_private_ar": "ميزة من الأدمن"})
        self.assertEqual(SiteSettings.load().features_semi_private_ar, "ميزة من الأدمن")
        self.client.logout()
        self.assertContains(self.client.get(reverse("courses:list")), "ميزة من الأدمن")


class OffersLayoutTests(TestCase):
    """/courses/: one tab and one panel per plan, the first offered plan active, unoffered plans marked."""

    def test_each_course_has_three_tabs_and_panels_with_the_first_offered_active(self):
        Course.objects.create(title_ar="بلا جروب", is_published=True, offers_group=False, offers_private=True,
                              price_private=1500)
        page = self.client.get(reverse("courses:list"))
        html = page.content.decode()
        self.assertEqual(html.count('class="c-plan-tab '), 3)
        self.assertEqual(html.count('role="tabpanel"'), 3)
        offer = page.context["offers"][0]
        self.assertEqual(offer["default"], "private")
        self.assertEqual([p["offered"] for p in offer["plans"]], [False, False, True])
        self.assertContains(page, "غير متاح لهذا الكورس", count=2)
        self.assertEqual(html.count("c-plan-tab is-active"), 1)
        self.assertNotIn("c-plan-tab is-active is-off", html)
