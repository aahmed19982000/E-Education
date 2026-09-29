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
    return render(request, "team/detail.html", {"member": member.localized(request.lang)})
