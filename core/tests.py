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
