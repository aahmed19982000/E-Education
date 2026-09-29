from django.shortcuts import get_object_or_404, render

from .models import TeamMember


def team_list(request):
    lang = request.lang
    members = [m.localized(lang) for m in TeamMember.objects.all()]
    owner = next((m for m in members if m["is_owner"]), None)
    others = [m for m in members if not m["is_owner"]]
    return render(request, "team/list.html", {"owner": owner, "members": others})


def team_detail(request, slug):
    member = get_object_or_404(TeamMember, slug=slug)
    reviews = list(member.reviews.all())
    avg = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else None
    return render(request, "team/detail.html", {
        "member": member.localized(request.lang),
        "reviews": [r.as_dict() for r in reviews],
        "avg_rating": avg,
    })
