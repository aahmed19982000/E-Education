from django.test import TestCase
from django.urls import reverse

from .models import TeamMember, youtube_id


class YoutubeIdTests(TestCase):
    def test_extracts_from_common_urls(self):
        for url in (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?t=5",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        ):
            self.assertEqual(youtube_id(url), "dQw4w9WgXcQ")

    def test_rejects_other_urls(self):
        self.assertEqual(youtube_id("https://example.com/watch?v=dQw4w9WgXcQ"), "")


class TeamPageTests(TestCase):
    def setUp(self):
        self.teacher = TeamMember.objects.create(
            name_ar="سارة", name_en="Sara", role_ar="مدرسة", role_en="Teacher",
            specialties_ar="IELTS، محادثة", specialties_en="IELTS, Speaking",
            youtube_url="https://youtu.be/dQw4w9WgXcQ", order=1,
        )
        self.owner = TeamMember.objects.create(
            name_ar="محمد عزت", name_en="Mohamed Ezzat", role_ar="المالك", role_en="Owner", is_owner=True, order=5,
        )

    def test_owner_is_first_even_with_higher_order(self):
        self.assertEqual(list(TeamMember.objects.all()), [self.owner, self.teacher])
        r = self.client.get(reverse("team:list"))
        self.assertEqual(r.context["owner"]["name"], "محمد عزت")
        self.assertEqual([m["name"] for m in r.context["members"]], ["سارة"])

    def test_detail_embeds_video_and_specialties(self):
        r = self.client.get(reverse("team:detail", args=[self.teacher.slug]))
        self.assertContains(r, "youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertEqual(r.context["member"]["specialties"], ["IELTS", "محادثة"])

    def test_detail_404(self):
        self.assertEqual(self.client.get(reverse("team:detail", args=["nope"])).status_code, 404)


class EnglishFallbackTests(TestCase):
    def test_empty_english_falls_back_to_arabic(self):
        m = TeamMember.objects.create(name_ar="أحمد", role_ar="مدرس", specialties_ar="نحو، محادثة", bio_ar="نبذة")
        en = m.localized("en")
        self.assertEqual((en["name"], en["role"], en["bio"]), ("أحمد", "مدرس", "نبذة"))
        self.assertEqual(en["specialties"], ["نحو", "محادثة"])
        self.assertTrue(m.slug)


class ReviewTests(TestCase):
    def setUp(self):
        self.member = TeamMember.objects.create(name_ar="سارة", role_ar="مدرسة")

    def test_needs_text_or_video(self):
        from django.core.exceptions import ValidationError
        from .models import TeamReview
        with self.assertRaises(ValidationError):
            TeamReview(member=self.member, student_name="علي").full_clean()

    def test_detail_shows_reviews_and_average(self):
        from .models import TeamReview
        TeamReview.objects.create(member=self.member, student_name="علي", rating=5, text="ممتازة")
        TeamReview.objects.create(member=self.member, student_name="منى", rating=4, youtube_url="https://youtu.be/dQw4w9WgXcQ")
        r = self.client.get(reverse("team:detail", args=[self.member.slug]))
        self.assertContains(r, "ممتازة")
        self.assertContains(r, "youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertEqual(r.context["avg_rating"], 4.5)


class ReviewDashboardTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.member = TeamMember.objects.create(name_ar="سارة", role_ar="مدرسة")
        self.client.force_login(User.objects.create_superuser("admin", "a@example.com", "x"))

    def test_create_text_review_and_delete(self):
        from .models import TeamReview
        url = reverse("dashboard:review_create", args=[self.member.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(url, {"student_name": "علي", "rating": 5, "text": "رائعة", "order": 0})
        self.assertEqual(r.status_code, 302)
        review = TeamReview.objects.get()
        self.assertEqual(self.client.get(reverse("dashboard:review_list", args=[self.member.pk])).status_code, 200)
        del_url = reverse("dashboard:review_delete", args=[self.member.pk, review.pk])
        self.assertEqual(self.client.get(del_url).status_code, 200)
        self.client.post(del_url)
        self.assertFalse(TeamReview.objects.exists())

    def test_empty_review_rejected(self):
        from .models import TeamReview
        self.client.post(reverse("dashboard:review_create", args=[self.member.pk]), {"student_name": "علي", "rating": 5})
        self.assertFalse(TeamReview.objects.exists())
