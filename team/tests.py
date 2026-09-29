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
