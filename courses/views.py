from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.translations import get_translations
from quiz.models import PlacementResult

from .access import can_view_lesson_material, has_active_enrollment, is_staff_user
from .forms import ApplyForm
from .models import Attendance, Course, Enrollment, EnrollmentRequest, Lesson, LessonAttachment


def course_list(request):
    mode = request.GET.get("mode", "group")
    if mode not in ("group", "private"):
        mode = "group"
    courses = Course.objects.filter(is_published=True, audience=Course.AUDIENCE_STUDENTS)
    offers = []
    for course in courses:
        if mode in course.allowed_modes():
            offers.append({**course.localized(request.lang), "price": course.price_for(mode)})
    return render(request, "courses/list.html", {"offers": offers, "mode": mode})


def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug, audience=Course.AUDIENCE_STUDENTS)
    if not course.is_published and not is_staff_user(request.user):
        raise Http404
    lang = request.lang
    # Times differ per group/student, so the page shows only the viewer's own sessions
    # (dates only; Zoom / recordings live on the lesson page).
    enrollment = None
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(
            user=request.user, course=course, status=Enrollment.STATUS_ACTIVE).select_related("cohort").first()
    my_lessons = enrollment.cohort.lessons.all() if enrollment and enrollment.cohort_id else []
    return render(request, "courses/detail.html", {
        "course": course.localized(lang),
        "prices": {m: course.price_for(m) for m in course.allowed_modes()},
        "lessons": [l.localized(lang) for l in my_lessons],
        "placed": bool(enrollment and enrollment.cohort_id),
        "enrolled": has_active_enrollment(request.user, course),
    })


@login_required
def my_courses(request):
    lang = request.lang
    now = timezone.now()
    cards = []
    enrollments = (Enrollment.objects.filter(user=request.user, status=Enrollment.STATUS_ACTIVE)
                   .select_related("course", "cohort__teacher"))
    for enrollment in enrollments:
        course = enrollment.course
        attended, total, percent = enrollment.progress()
        cohort = enrollment.cohort
        nxt = cohort.lessons.filter(starts_at__gte=now).first() if cohort else None
        cards.append({
            "course": course.localized(lang), "teacher": cohort.teacher.localized(lang) if cohort and cohort.teacher else None,
            "placed": cohort is not None, "attended": attended, "total": total, "percent": percent,
            "attended_label": get_translations(lang)["courses"]["attended"].format(a=attended, t=total),
            "next": nxt.localized(lang) if nxt else None,
        })
    return render(request, "courses/mine.html", {"cards": cards})


@login_required
def lesson_detail(request, pk):
    lesson = get_object_or_404(Lesson.objects.select_related("cohort__course"), pk=pk)
    course = lesson.cohort.course
    if not can_view_lesson_material(request.user, lesson):
        raise Http404  # private material: don't reveal it exists
    enrollment = Enrollment.objects.filter(user=request.user, cohort=lesson.cohort).first()
    attendance = None
    placement = None
    if enrollment:
        attendance = Attendance.objects.filter(lesson=lesson, enrollment=enrollment).first()
        # The test result is surfaced on the student's first session only.
        if lesson.cohort.lessons.first() == lesson:
            placement = PlacementResult.objects.filter(user=request.user).first()
    lang = request.lang
    return render(request, "courses/lesson.html", {
        "course": course.localized(lang),
        "lesson": lesson.localized(lang),
        "zoom_url": lesson.zoom_url,
        "recording_url": lesson.recording_url,
        "files": lesson.attachments.filter(kind=LessonAttachment.KIND_FILE),
        "homework": lesson.attachments.filter(kind=LessonAttachment.KIND_HOMEWORK),
        "attendance": attendance,
        "placement": placement,
    })


@login_required
def attachment_download(request, pk):
    attachment = get_object_or_404(LessonAttachment.objects.select_related("lesson__cohort"), pk=pk)
    if not can_view_lesson_material(request.user, attachment.lesson):
        raise Http404
    return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.file.name.rsplit("/", 1)[-1])


SESSION_REQUESTS = "enrollment_request_ids"


def apply(request, slug):
    """Step 1: the visitor picks a course and fills in their details."""
    course = get_object_or_404(Course, slug=slug, is_published=True, audience=Course.AUDIENCE_STUDENTS)
    lang = request.lang
    initial = {}
    if request.user.is_authenticated:
        initial = {
            "full_name": request.user.get_full_name(), "email": request.user.email,
            "phone": getattr(getattr(request.user, "profile", None), "phone", ""),
        }
    mode = request.GET.get("mode")
    form = ApplyForm(request.POST or None, initial=initial, course=course)
    if mode in course.allowed_modes():
        form.fields["mode"].initial = mode
    for name, label in get_translations(lang)["courses"]["f"].items():
        form.fields[name].label = label
    if request.method == "POST" and form.is_valid():
        enrollment_request = form.save(commit=False)
        enrollment_request.course = course
        if request.user.is_authenticated:
            enrollment_request.user = request.user
        enrollment_request.save()
        # Remember it so a guest who signs in next can claim it at checkout.
        request.session[SESSION_REQUESTS] = request.session.get(SESSION_REQUESTS, []) + [enrollment_request.pk]
        checkout_url = reverse("courses:checkout", args=[enrollment_request.pk])
        if request.user.is_authenticated:
            return redirect(checkout_url)
        messages.info(request, get_translations(lang)["courses"]["loginToPay"])
        return redirect(f"{reverse('accounts:login')}?mode=register&next={checkout_url}")
    return render(request, "courses/apply.html", {
        "course": course.localized(lang), "form": form,
        "prices": {m: course.price_for(m) for m in course.allowed_modes()},
    })


@login_required
def checkout(request, pk):
    """Step 2 (signed-in only): payment. Paid or not, the request is already with the admin."""
    enrollment_request = get_object_or_404(EnrollmentRequest.objects.select_related("course"), pk=pk)
    if enrollment_request.user_id is None and pk in request.session.get(SESSION_REQUESTS, []):
        enrollment_request.user = request.user
        enrollment_request.save(update_fields=["user"])
    if enrollment_request.user_id != request.user.pk:
        raise Http404
    return render(request, "courses/checkout.html", {
        "req": enrollment_request,
        "course": enrollment_request.course.localized(request.lang) if enrollment_request.course else None,
        "payments_enabled": settings.PAYMENTS_ENABLED,
    })
