from django.shortcuts import get_object_or_404, render

from .models import Article


def article_list(request):
    lang = request.lang
    articles = [a.localized(lang) for a in Article.objects.all()]
    return render(request, "articles/list.html", {"articles": articles})


def article_detail(request, slug):
    lang = request.lang
    article = get_object_or_404(Article, slug=slug)
    return render(request, "articles/detail.html", {"article": article.localized(lang)})
