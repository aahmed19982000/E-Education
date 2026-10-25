from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse

from articles.models import Article
from courses.models import Course
from team.models import TeamMember


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return ["core:home", "core:about", "core:teachers", "courses:list", "team:list", "articles:list",
                "quiz:intro", "contact_us:contact"]

    def location(self, item):
        return reverse(item)


class CourseSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Course.objects.filter(is_published=True, audience=Course.AUDIENCE_STUDENTS)

    def location(self, obj):
        return reverse("courses:detail", args=[obj.slug])


class ArticleSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Article.objects.all()

    def location(self, obj):
        return reverse("articles:detail", args=[obj.slug])


class TeamSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return TeamMember.objects.all()

    def location(self, obj):
        return reverse("team:detail", args=[obj.slug])


SITEMAPS = {"static": StaticSitemap, "courses": CourseSitemap, "articles": ArticleSitemap, "team": TeamSitemap}


def robots_txt(request):
    from django.conf import settings
    lines = ["User-agent: *", "Disallow: /dashboard/", "Disallow: /admin/", "Disallow: /accounts/",
             "Disallow: /exams/", "Disallow: /courses/mine/", "Disallow: /courses/checkout/",
             "Disallow: /courses/payments/", "Disallow: /courses/certificate/", "",
             f"Sitemap: {settings.SITE_URL}/sitemap.xml"]
    return HttpResponse("\n".join(lines), content_type="text/plain")
