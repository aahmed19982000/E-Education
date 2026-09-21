from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from articles.models import Article


def home(request):
    lang = request.lang
    home_articles = [a.localized(lang) for a in Article.objects.all()[:3]]
    return render(request, "core/home.html", {"home_articles": home_articles})


def about(request):
    return render(request, "core/about.html")


def teachers(request):
    return render(request, "core/teachers.html")


def set_language(request, lang_code):
    if lang_code in ("ar", "en"):
        request.session["lang"] = lang_code
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = "/"
    return redirect(next_url)
