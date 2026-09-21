from django.shortcuts import render

from .models import Level


def levels_view(request):
    mode = request.GET.get("mode", "group")
    if mode not in ("group", "private"):
        mode = "group"
    lang = request.lang
    level_cards = [lvl.localized(lang, mode) for lvl in Level.objects.all()]
    return render(request, "levels/levels.html", {
        "level_cards": level_cards,
        "mode": mode,
    })
