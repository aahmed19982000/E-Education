from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.db import models
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.auth_utils import authenticate_by_email
from accounts.models import Profile
from articles.models import Article
from contact_us.models import ContactMessage
from courses.models import Attendance, Cohort, Course, Enrollment, EnrollmentRequest, Lesson
from team.models import WEEKDAYS, TeamMember, TeamReview, split_list
from quiz.grading import format_marks, question_marks
from django.db.models import Avg, Count
import datetime
from django.utils import timezone
from courses.models import CohortSlot
from courses import placement
from quiz.models import PlacementResult

from quiz.models import AUDIO_MAX_MB, MAX_OPTIONS, MIN_OPTIONS, Category, Question, QuizSettings

from .decorators import dashboard_required, section_required
from .forms import (
    ArticleForm, AttachmentFormSet, CategoryForm, CohortForm, CourseForm, EnrollForm, LessonForm, RequestForm, SlotFormSet, DashboardLoginForm, AvailabilityFormSet, QuestionForm, QuizSettingsForm, StaffUserCreateForm, TeamMemberForm, TeamReviewForm, StaffUserEditForm,
)
from .permissions import (
    SECTION_ARTICLES, SECTION_COURSES, SECTION_MESSAGES, SECTION_QUESTIONS, SECTION_REQUESTS, SECTION_TEAM, SECTION_USERS,
    can_access, get_dashboard_role, role_label,
)


def login_view(request):
    if request.user.is_authenticated and get_dashboard_role(request.user):
        return redirect("dashboard:index")

    error = None
    form = DashboardLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower().strip()
        password = form.cleaned_data["password"]
        user = authenticate_by_email(request, email, password)

        if user is not None and get_dashboard_role(user) is not None:
            auth_login(request, user)
            next_url = request.GET.get("next") or "dashboard:index"
            if not url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                next_url = "dashboard:index"
            return redirect(next_url)
        error = "بيانات الدخول غير صحيحة أو ليس لديك صلاحية الوصول إلى لوحة التحكم."

    return render(request, "dashboard/login.html", {"form": form, "error": error})


def logout_view(request):
    auth_logout(request)
    return redirect("dashboard:login")


def base_context(request, active=""):
    role = request.dashboard_role
    return {
        "active": active,
        "role": role,
        "role_display": role_label(role),
        "can_write_articles": can_access(role, SECTION_ARTICLES, "write"),
        "can_view_articles": can_access(role, SECTION_ARTICLES),
        "can_write_team": can_access(role, SECTION_TEAM, "write"),
        "can_view_team": can_access(role, SECTION_TEAM),
        "can_write_questions": can_access(role, SECTION_QUESTIONS, "write"),
        "can_view_questions": can_access(role, SECTION_QUESTIONS),
        "can_write_messages": can_access(role, SECTION_MESSAGES, "write"),
        "can_view_messages": can_access(role, SECTION_MESSAGES),
        "can_write_courses": can_access(role, SECTION_COURSES, "write"),
        "can_view_courses": can_access(role, SECTION_COURSES),
        "can_write_requests": can_access(role, SECTION_REQUESTS, "write"),
        "can_view_requests": can_access(role, SECTION_REQUESTS),
        "can_view_users": can_access(role, SECTION_USERS),
    }


@dashboard_required
def index(request):
    ctx = base_context(request, active="index")
    if ctx["can_view_articles"]:
        ctx["articles_count"] = Article.objects.count()
    if ctx["can_view_team"]:
        ctx["team_count"] = TeamMember.objects.count()
    if ctx["can_view_questions"]:
        ctx["questions_count"] = Question.objects.count()
    if ctx["can_view_messages"]:
        ctx["messages_count"] = ContactMessage.objects.count()
    if ctx["can_view_courses"]:
        ctx["courses_count"] = Course.objects.count()
    if ctx["can_view_requests"]:
        ctx["new_requests_count"] = EnrollmentRequest.objects.filter(status=EnrollmentRequest.STATUS_NEW).count()
        forming = Cohort.objects.filter(mode="group", confirmed_at__isnull=True).select_related("course")
        ctx["forming_cohorts"] = [c for c in forming if c.seats_taken() or c.is_ready_to_confirm]
        ctx["ready_cohorts_count"] = sum(1 for c in ctx["forming_cohorts"] if c.is_ready_to_confirm)
    if ctx["can_view_users"]:
        ctx["users_count"] = User.objects.filter(is_staff=True).count()
    return render(request, "dashboard/index.html", ctx)



# --- Articles ---------------------------------------------------------------

@section_required(SECTION_ARTICLES)
def articles_list(request):
    ctx = base_context(request, active="articles")
    ctx["articles"] = Article.objects.all()
    return render(request, "dashboard/articles_list.html", ctx)


@section_required(SECTION_ARTICLES, "write")
def article_form(request, pk=None):
    instance = get_object_or_404(Article, pk=pk) if pk else None
    if request.method == "POST":
        form = ArticleForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ المقال بنجاح.")
            return redirect("dashboard:articles_list")
    else:
        form = ArticleForm(instance=instance)
    ctx = base_context(request, active="articles")
    ctx.update({"form": form, "instance": instance, "title": "تعديل مقال" if instance else "إضافة مقال"})
    return render(request, "dashboard/article_form.html", ctx)


@section_required(SECTION_ARTICLES, "write")
def article_delete(request, pk):
    instance = get_object_or_404(Article, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "تم حذف المقال.")
        return redirect("dashboard:articles_list")
    ctx = base_context(request, active="articles")
    ctx.update({"object": instance, "title": f"حذف مقال: {instance.title_ar}", "cancel_url": "dashboard:articles_list"})
    return render(request, "dashboard/confirm_delete.html", ctx)


# --- Team -------------------------------------------------------------------

@section_required(SECTION_TEAM)
def team_list(request):
    ctx = base_context(request, active="team")
    ctx["members"] = TeamMember.objects.all()
    return render(request, "dashboard/team_list.html", ctx)


@section_required(SECTION_TEAM)
def team_profile(request, pk):
    """Everything about one teacher: students, groups, sessions, schedule and availability."""
    member = get_object_or_404(TeamMember, pk=pk)
    can_write = can_access(request.dashboard_role, SECTION_TEAM, "write")
    formset = AvailabilityFormSet(request.POST or None, instance=member)
    if request.method == "POST":
        if not can_write:
            raise PermissionDenied
        if formset.is_valid():
            formset.save()
            messages.success(request, "تم حفظ الأوقات المتاحة.")
            return redirect("dashboard:team_profile", pk=member.pk)

    now = timezone.now()
    cohorts = list(member.cohorts.select_related("course").prefetch_related("slots").annotate(
        students=Count("enrollments", filter=models.Q(enrollments__status=Enrollment.STATUS_ACTIVE), distinct=True)))
    for cohort in cohorts:
        cohort.next_lesson = cohort.lessons.filter(starts_at__gte=now).first()
    enrollments = (Enrollment.objects.filter(cohort__teacher=member, status=Enrollment.STATUS_ACTIVE)
                   .select_related("user", "course", "cohort"))
    students = []
    for enrollment in enrollments:
        attended, total, percent = enrollment.progress()
        students.append({"enrollment": enrollment, "attended": attended, "total": total, "percent": percent})
    lessons = Lesson.objects.filter(cohort__teacher=member).select_related("cohort__course")
    upcoming = list(lessons.filter(starts_at__gte=now)[:8])
    past_count = lessons.filter(starts_at__lt=now).count()

    slots = CohortSlot.objects.filter(cohort__teacher=member).select_related("cohort__course")
    windows = list(member.availability.all())
    week = []
    for day, label in WEEKDAYS:
        day_windows = [w for w in windows if w.weekday == day]
        day_slots = []
        for slot in slots:
            if slot.weekday != day:
                continue
            end = (datetime.datetime.combine(datetime.date.today(), slot.start_time)
                   + datetime.timedelta(minutes=slot.duration_minutes)).time()
            covered = any(w.start_time <= slot.start_time and end <= w.end_time for w in day_windows)
            day_slots.append({"slot": slot, "end": end, "outside": bool(windows) and not covered})
        week.append({"label": label, "windows": day_windows, "slots": day_slots})

    rating = member.reviews.aggregate(avg=Avg("rating"), n=Count("id"))
    ctx = base_context(request, active="team")
    ctx.update({
        "member": member, "formset": formset, "cohorts": cohorts, "students": students,
        "upcoming": upcoming, "past_count": past_count, "week": week,
        "rating_avg": round(rating["avg"], 1) if rating["avg"] else None, "rating_n": rating["n"],
        "has_outside": any(s["outside"] for d in week for s in d["slots"]),
        "specialties": split_list(member.specialties_ar),
    })
    return render(request, "dashboard/team_profile.html", ctx)


@section_required(SECTION_TEAM, "write")
def team_form(request, pk=None):
    instance = get_object_or_404(TeamMember, pk=pk) if pk else None
    if request.method == "POST":
        form = TeamMemberForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ بيانات العضو بنجاح.")
            return redirect("dashboard:team_list")
    else:
        form = TeamMemberForm(instance=instance)
    ctx = base_context(request, active="team")
    ctx.update({"form": form, "instance": instance, "title": "تعديل عضو" if instance else "إضافة عضو"})
    return render(request, "dashboard/team_form.html", ctx)


@section_required(SECTION_TEAM, "write")
def team_delete(request, pk):
    instance = get_object_or_404(TeamMember, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "تم حذف العضو.")
        return redirect("dashboard:team_list")
    ctx = base_context(request, active="team")
    ctx.update({"object": instance, "title": f"حذف عضو: {instance.name_ar}", "cancel_url": "dashboard:team_list"})
    return render(request, "dashboard/confirm_delete.html", ctx)


@section_required(SECTION_TEAM)
def review_list(request, member_pk):
    member = get_object_or_404(TeamMember, pk=member_pk)
    ctx = base_context(request, active="team")
    ctx.update({"member": member, "reviews": member.reviews.all()})
    return render(request, "dashboard/review_list.html", ctx)


@section_required(SECTION_TEAM, "write")
def review_form(request, member_pk, pk=None):
    member = get_object_or_404(TeamMember, pk=member_pk)
    instance = get_object_or_404(TeamReview, pk=pk, member=member) if pk else None
    if request.method == "POST":
        form = TeamReviewForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            review = form.save(commit=False)
            review.member = member
            review.save()
            messages.success(request, "تم حفظ التقييم.")
            return redirect("dashboard:review_list", member_pk=member.pk)
    else:
        form = TeamReviewForm(instance=instance)
    ctx = base_context(request, active="team")
    ctx.update({"form": form, "member": member, "instance": instance, "title": "تعديل تقييم" if instance else "إضافة تقييم"})
    return render(request, "dashboard/review_form.html", ctx)


@section_required(SECTION_TEAM, "write")
def review_delete(request, member_pk, pk):
    instance = get_object_or_404(TeamReview, pk=pk, member_id=member_pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "تم حذف التقييم.")
        return redirect("dashboard:review_list", member_pk=member_pk)
    ctx = base_context(request, active="team")
    ctx.update({"object": instance, "title": f"حذف تقييم: {instance.student_name}", "cancel_url": "dashboard:review_list", "cancel_args": [member_pk]})
    return render(request, "dashboard/confirm_delete.html", ctx)


# --- Quiz questions -----------------------------------------------------

@section_required(SECTION_QUESTIONS)
def questions_list(request):
    ctx = base_context(request, active="questions")
    questions = list(Question.objects.select_related("category"))
    settings = QuizSettings.load()
    marks = question_marks(questions, settings)
    for q in questions:
        q.marks_display = format_marks(marks[q.pk])
    ctx.update({
        "questions": questions,
        "quiz_settings": settings,
        "total_marks": format_marks(sum(marks.values())),
    })
    return render(request, "dashboard/questions_list.html", ctx)


@section_required(SECTION_QUESTIONS, "write")
def quiz_grading(request):
    settings = QuizSettings.load()
    if request.method == "POST":
        form = QuizSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ إعدادات الدرجات والوقت.")
            return redirect("dashboard:questions_list")
    else:
        form = QuizSettingsForm(instance=settings)
    questions = list(Question.objects.all())
    ctx = base_context(request, active="quiz_settings")
    ctx.update({
        "form": form,
        "title": "الدرجات والوقت",
        "questions_count": len(questions),
        "points_sum": format_marks(sum((q.points for q in questions), 0)),
    })
    return render(request, "dashboard/quiz_grading.html", ctx)


@require_POST
@section_required(SECTION_QUESTIONS, "write")
def questions_reorder(request):
    """Save a new quiz order. Expects every question id, in the desired order."""
    try:
        ids = [int(pk) for pk in request.POST.getlist("ids")]
    except ValueError:
        return JsonResponse({"ok": False, "error": "invalid ids"}, status=400)
    questions = {q.pk: q for q in Question.objects.all()}
    if len(ids) != len(set(ids)) or set(ids) != set(questions):
        # Someone added/deleted a question since the page loaded.
        return JsonResponse({"ok": False, "error": "stale"}, status=409)
    for position, pk in enumerate(ids, start=1):
        questions[pk].order = position
    Question.objects.bulk_update(questions.values(), ["order"])
    return JsonResponse({"ok": True})


@section_required(SECTION_QUESTIONS, "write")
def question_form(request, pk=None):
    instance = get_object_or_404(Question, pk=pk) if pk else None
    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ السؤال بنجاح.")
            if "save_add_another" in request.POST:
                return redirect("dashboard:question_create")
            return redirect("dashboard:questions_list")
    else:
        form = QuestionForm(instance=instance)
    ctx = base_context(request, active="questions")
    ctx.update({
        "form": form,
        "instance": instance,
        "title": "تعديل سؤال" if instance else "إضافة سؤال",
        "option_rows": form.option_rows(),
        "max_options": MAX_OPTIONS,
        "min_options": MIN_OPTIONS,
        "audio_max_mb": AUDIO_MAX_MB,
        "quiz_settings": form.quiz_settings,
        "equal_share": _equal_share(form.quiz_settings, instance),
    })
    return render(request, "dashboard/question_form.html", ctx)



# --- Question categories ------------------------------------------------

@section_required(SECTION_QUESTIONS)
def categories_list(request):
    ctx = base_context(request, active="questions")
    ctx["categories"] = Category.objects.annotate(num_questions=Count("questions"))
    return render(request, "dashboard/categories_list.html", ctx)


@section_required(SECTION_QUESTIONS, "write")
def category_form(request, pk=None):
    instance = get_object_or_404(Category, pk=pk) if pk else None
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ التصنيف.")
            return redirect("dashboard:categories_list")
    else:
        form = CategoryForm(instance=instance)
    ctx = base_context(request, active="questions")
    ctx.update({"form": form, "instance": instance, "title": "تعديل تصنيف" if instance else "إضافة تصنيف"})
    return render(request, "dashboard/category_form.html", ctx)


@section_required(SECTION_QUESTIONS, "write")
def category_delete(request, pk):
    instance = get_object_or_404(Category, pk=pk)
    in_use = instance.questions.count()
    if in_use:
        messages.error(request, f"لا يمكن حذف التصنيف «{instance.name_ar}» لأنه مستخدم في {in_use} سؤال. انقل الأسئلة لتصنيف آخر أولًا.")
        return redirect("dashboard:categories_list")
    if request.method == "POST":
        instance.delete()
        messages.success(request, "تم حذف التصنيف.")
        return redirect("dashboard:categories_list")
    ctx = base_context(request, active="questions")
    ctx.update({"object": instance, "title": f"حذف التصنيف: {instance.name_ar}", "cancel_url": "dashboard:categories_list"})
    return render(request, "dashboard/confirm_delete.html", ctx)


@require_POST
@section_required(SECTION_QUESTIONS, "write")
def category_quick_add(request):
    """Create a category from the question form without leaving it."""
    form = CategoryForm(request.POST)
    if not form.is_valid():
        errors = [e for errs in form.errors.values() for e in errs]
        return JsonResponse({"ok": False, "error": errors[0] if errors else "بيانات غير صحيحة."}, status=400)
    category = form.save()
    return JsonResponse({"ok": True, "id": category.pk, "name": category.name_ar})


def _equal_share(settings, instance):
    """Marks each question gets in whole-test mode (counting a new question being added)."""
    if settings.is_per_question:
        return None
    count = Question.objects.count() + (0 if instance else 1)
    return format_marks(settings.total_marks / count)


@section_required(SECTION_QUESTIONS, "write")
def question_delete(request, pk):
    instance = get_object_or_404(Question, pk=pk)
    if request.method == "POST":
        instance.delete()  # its audio file is removed by quiz.signals
        messages.success(request, "تم حذف السؤال.")
        return redirect("dashboard:questions_list")
    ctx = base_context(request, active="questions")
    ctx.update({"object": instance, "title": f"حذف السؤال رقم {instance.order}", "cancel_url": "dashboard:questions_list"})
    return render(request, "dashboard/confirm_delete.html", ctx)


# --- Contact messages -----------------------------------------------------

@section_required(SECTION_MESSAGES)
def messages_list(request):
    ctx = base_context(request, active="messages")
    ctx["contact_messages"] = ContactMessage.objects.all()
    return render(request, "dashboard/messages_list.html", ctx)


@section_required(SECTION_MESSAGES)
def message_detail(request, pk):
    instance = get_object_or_404(ContactMessage, pk=pk)
    ctx = base_context(request, active="messages")
    ctx["object"] = instance
    return render(request, "dashboard/message_detail.html", ctx)


@section_required(SECTION_MESSAGES, "write")
def message_delete(request, pk):
    instance = get_object_or_404(ContactMessage, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "تم حذف الرسالة.")
        return redirect("dashboard:messages_list")
    ctx = base_context(request, active="messages")
    ctx.update({"object": instance, "title": f"حذف رسالة من {instance.name}", "cancel_url": "dashboard:messages_list"})
    return render(request, "dashboard/confirm_delete.html", ctx)


# --- Users (super admin only) ---------------------------------------------

@section_required(SECTION_USERS)
def users_list(request):
    ctx = base_context(request, active="users")
    staff = User.objects.filter(is_staff=True).select_related("profile").order_by("-is_superuser", "first_name")
    ctx["admins"] = [u for u in staff if u.is_superuser or u.profile.role != Profile.ROLE_TEACHER]
    ctx["teachers"] = [u for u in staff if not u.is_superuser and u.profile.role == Profile.ROLE_TEACHER]
    ctx["staff_total"] = len(staff)
    ctx["groups"] = [("الإداريون", ctx["admins"]), ("المدرّسون", ctx["teachers"])]
    return render(request, "dashboard/users_list.html", ctx)


@section_required(SECTION_USERS, "write")
def user_create(request):
    if request.method == "POST":
        form = StaffUserCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الحساب بنجاح.")
            return redirect("dashboard:users_list")
    else:
        form = StaffUserCreateForm()
    ctx = base_context(request, active="users")
    ctx.update({"form": form, "title": "إضافة عضو فريق"})
    return render(request, "dashboard/user_form.html", ctx)


@section_required(SECTION_USERS, "write")
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk, is_staff=True, is_superuser=False)
    if request.method == "POST":
        form = StaffUserEditForm(request.POST, user=target)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث بيانات العضو.")
            return redirect("dashboard:users_list")
    else:
        form = StaffUserEditForm(user=target)
    ctx = base_context(request, active="users")
    ctx.update({"form": form, "target": target, "title": f"تعديل صلاحيات {target.get_full_name() or target.email}"})
    return render(request, "dashboard/user_form.html", ctx)


# --- Courses ----------------------------------------------------------------

@section_required(SECTION_COURSES)
def courses_list(request):
    ctx = base_context(request, active="courses")
    ctx["courses"] = Course.objects.annotate(
        cohorts_count=Count("cohorts", distinct=True), students_count=Count("enrollments", distinct=True),
    )
    return render(request, "dashboard/courses_list.html", ctx)


@section_required(SECTION_COURSES, "write")
def course_form(request, pk=None):
    instance = get_object_or_404(Course, pk=pk) if pk else None
    form = CourseForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        course = form.save()
        messages.success(request, "تم حفظ الكورس بنجاح.")
        return redirect("dashboard:course_edit", pk=course.pk)
    ctx = base_context(request, active="courses")
    ctx.update({"form": form, "instance": instance, "title": "تعديل كورس" if instance else "إضافة كورس"})
    return render(request, "dashboard/course_form.html", ctx)


@section_required(SECTION_COURSES, "write")
def course_delete(request, pk):
    instance = get_object_or_404(Course, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "تم حذف الكورس.")
        return redirect("dashboard:courses_list")
    ctx = base_context(request, active="courses")
    ctx.update({"object": instance, "title": f"حذف الكورس {instance.title_ar}", "cancel_url": "dashboard:courses_list"})
    return render(request, "dashboard/confirm_delete.html", ctx)


# --- Cohorts (a group or private student: teacher + own weekly times) ----------

@section_required(SECTION_COURSES)
def cohorts_list(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    ctx = base_context(request, active="courses")
    ctx.update({"course": course, "cohorts": course.cohorts.select_related("teacher").annotate(
        lessons_count=Count("lessons", distinct=True), students_count=Count("enrollments", distinct=True))
        .prefetch_related("requests", "enrollments__user")})
    return render(request, "dashboard/cohorts_list.html", ctx)


def _student_facts(user_ids, course_ids=None):
    """Level-test result and payment per student, fetched in two queries.

    Returns ({user_id: latest PlacementResult}, {(user_id, course_id): True when a request is paid}).
    """
    results = {}
    for r in PlacementResult.objects.filter(user_id__in=user_ids).order_by("created_at"):
        results[r.user_id] = r  # ascending, so the latest wins
    paid = {}
    reqs = EnrollmentRequest.objects.filter(user_id__in=user_ids, payment_status=EnrollmentRequest.PAYMENT_PAID)
    for user_id, course_id in reqs.values_list("user_id", "course_id"):
        paid[(user_id, course_id)] = True
    return results, paid


def _cohort_stage(c):
    """(key, label) of where a cohort is in its life, used for the pill and the filters."""
    if c.mode == "private":
        return "private", "خصوصي"
    if c.is_locked:
        return "launched", "مُطلقة"
    if c.confirmed_at:
        return "launched", "مُطلقة (بلا مدرس)"
    if c.is_ready_to_confirm:
        return "ready", "اكتمل العدد"
    return "forming", "قيد التكوين"


@section_required(SECTION_COURSES)
def all_cohorts(request):
    """Every group of every course in one place, filterable by where it is in its life."""
    current = request.GET.get("status", "all")
    query = request.GET.get("q", "").strip()
    qs = Cohort.objects.select_related("course", "teacher").prefetch_related("requests", "enrollments", "slots").annotate(
        lessons_count=Count("lessons", distinct=True))
    if query:
        qs = qs.filter(models.Q(name__icontains=query) | models.Q(course__title_ar__icontains=query)
                       | models.Q(teacher__name_ar__icontains=query))
    cohorts = list(qs)
    for c in cohorts:
        c.stage, c.stage_label = _cohort_stage(c)
        c.taken = c.seats_taken()
        c.percent = min(round(c.taken / c.min_students * 100), 100) if c.mode == "group" and c.min_students else 100
    counts = {key: sum(1 for c in cohorts if c.stage == key) for key in ("forming", "ready", "launched", "private")}
    counts["all"] = len(cohorts)
    if current in counts and current != "all":
        cohorts = [c for c in cohorts if c.stage == current]
    ctx = base_context(request, active="cohorts")
    ctx.update({"cohorts": cohorts, "current": current, "query": query, "counts": counts, "filters": [
        ("all", "الكل"), ("forming", "قيد التكوين"), ("ready", "اكتمل العدد"),
        ("launched", "مُطلقة"), ("private", "خصوصي")]})
    return render(request, "dashboard/cohorts_all.html", ctx)


@section_required(SECTION_COURSES)
def cohort_detail(request, pk):
    cohort = get_object_or_404(Cohort.objects.select_related("course", "teacher"), pk=pk)
    course = cohort.course
    enrollments = list(cohort.enrollments.select_related("user", "user__profile"))
    waiting = list(cohort.waiting_requests().select_related("user", "user__profile"))
    results, paid = _student_facts([e.user_id for e in enrollments] + [r.user_id for r in waiting])
    rows = []
    for e in enrollments:
        rows.append({"kind": "enrollment", "obj": e, "user": e.user, "name": e.user.get_full_name() or e.user.email,
                     "active": e.is_active, "result": results.get(e.user_id),
                     "paid": paid.get((e.user_id, course.pk), False), "since": e.created_at})
    for r in waiting:
        rows.append({"kind": "request", "obj": r, "user": r.user, "name": r.full_name, "active": True, "waiting": True,
                     "result": results.get(r.user_id), "paid": r.is_paid or paid.get((r.user_id, course.pk), False),
                     "since": r.created_at})
    others = [c for c in course.cohorts.exclude(pk=cohort.pk) if not c.is_locked and (c.mode == "private" or c.seats_left)]
    # Students of this course not in any group yet, who can be added here.
    placed = set(course.enrollments.exclude(cohort=None).values_list("user_id", flat=True))
    placed |= set(course.requests.filter(status=EnrollmentRequest.STATUS_WAITING).values_list("user_id", flat=True))
    addable = []
    for e in course.enrollments.filter(cohort=None, status=Enrollment.STATUS_ACTIVE).select_related("user"):
        addable.append(("enrollment", e.pk, e.user.get_full_name() or e.user.email))
    for r in course.requests.filter(user__isnull=False, kind=EnrollmentRequest.KIND_STUDENT,
                                    status__in=[EnrollmentRequest.STATUS_NEW, EnrollmentRequest.STATUS_CONTACTED,
                                                EnrollmentRequest.STATUS_TEACHER_ASSIGNED]).select_related("user"):
        if r.user_id not in placed and not course.enrollments.filter(user_id=r.user_id).exists():
            addable.append(("request", r.pk, r.full_name))
    stage, stage_label = _cohort_stage(cohort)
    taken = cohort.seats_taken()
    ctx = base_context(request, active="cohorts")
    ctx.update({"cohort": cohort, "course": course, "rows": rows, "others": others, "addable": addable,
                "stage": stage, "stage_label": stage_label, "taken": taken,
                "percent": min(round(taken / cohort.min_students * 100), 100) if cohort.min_students else 100,
                "lessons_count": cohort.lessons.count(), "students_total": len(rows),
                "tested": sum(1 for r in rows if r["result"]), "paid_count": sum(1 for r in rows if r["paid"])})
    return render(request, "dashboard/cohort_detail.html", ctx)


def _safe_next(request, default):
    target = request.POST.get("next") or ""
    return target if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}) else default


@section_required(SECTION_COURSES, "write")
@require_POST
def student_action(request, pk=None):
    """Move a student to another group, take them out, or add them to one (cohort page and student page).

    `kind` is the enrollment (already in the course) or the request (waiting / not yet placed).
    All rules, including the freeze on launched groups, live in `courses.placement`.
    """
    kind, obj_pk, action = request.POST.get("kind"), request.POST.get("id"), request.POST.get("action")
    target = None
    if request.POST.get("cohort"):
        target = get_object_or_404(Cohort, pk=request.POST["cohort"])
    if kind == "enrollment":
        obj = get_object_or_404(Enrollment.objects.select_related("cohort", "course"), pk=obj_pk)
    elif kind == "request":
        obj = get_object_or_404(EnrollmentRequest.objects.select_related("cohort", "course", "user"), pk=obj_pk)
    else:
        raise Http404
    course_id = obj.course_id
    if action == "remove":
        error = placement.remove_enrollment(obj) if kind == "enrollment" else placement.remove_waiting(obj)
    elif target is None or target.course_id != course_id:
        error = "اختر مجموعة تابعة لنفس الكورس."
    elif kind == "enrollment":
        error = placement.move_enrollment(obj, target)
    else:
        error = placement.place_request(obj, target)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, "تم إخراج الطالب من المجموعة." if action == "remove" else "تم نقل الطالب إلى المجموعة.")
    return redirect(_safe_next(request, reverse("dashboard:all_cohorts")))


@section_required(SECTION_COURSES)
def student_detail(request, user_pk):
    student = get_object_or_404(User.objects.select_related("profile"), pk=user_pk)
    enrollments = list(student.enrollments.select_related("course", "cohort", "cohort__teacher"))
    requests_ = list(student.enrollment_requests.select_related("course", "cohort"))
    results, paid = _student_facts([student.pk])
    if not (enrollments or requests_ or PlacementResult.objects.filter(user=student).exists()):
        raise Http404
    items = []
    seen = set()
    for e in enrollments:
        seen.add(e.course_id)
        attended, total, pct = e.progress()
        items.append({"kind": "enrollment", "obj": e, "course": e.course, "cohort": e.cohort,
                      "paid": paid.get((student.pk, e.course_id), False),
                      "attended": attended, "total": total, "percent": pct})
    for r in requests_:
        if r.course_id in seen or not r.course_id or r.kind != EnrollmentRequest.KIND_STUDENT:
            continue
        items.append({"kind": "request", "obj": r, "course": r.course, "cohort": r.cohort, "paid": r.is_paid})
    for item in items:
        locked = item["cohort"] is not None and item["cohort"].is_locked
        item["locked"] = locked
        item["options"] = [] if locked else [
            c for c in item["course"].cohorts.all()
            if c.pk != (item["cohort"].pk if item["cohort"] else None) and not c.is_locked
            and (c.mode == "private" or c.seats_left)]
    ctx = base_context(request, active="cohorts")
    ctx.update({"student": student, "phone": getattr(getattr(student, "profile", None), "phone", ""),
                "items": items, "placements": student.placement_results.all(), "latest": results.get(student.pk)})
    return render(request, "dashboard/student_detail.html", ctx)


@section_required(SECTION_COURSES, "write")
def cohort_form(request, course_pk, pk=None):
    course = get_object_or_404(Course, pk=course_pk)
    instance = get_object_or_404(Cohort, pk=pk, course=course) if pk else None
    form = CohortForm(request.POST or None, instance=instance)
    slots = SlotFormSet(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid() and slots.is_valid():
        cohort = form.save(commit=False)
        cohort.course = course
        cohort.save()
        slots.instance = cohort
        slots.save()
        messages.success(request, "تم حفظ المجموعة بنجاح.")
        return redirect("dashboard:cohort_edit", course_pk=course.pk, pk=cohort.pk)
    ctx = base_context(request, active="courses")
    ctx.update({"form": form, "slots": slots, "course": course, "instance": instance,
                "title": "تعديل مجموعة" if instance else "إضافة مجموعة"})
    return render(request, "dashboard/cohort_form.html", ctx)


@section_required(SECTION_COURSES, "write")
def cohort_delete(request, course_pk, pk):
    instance = get_object_or_404(Cohort, pk=pk, course_id=course_pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "تم حذف المجموعة.")
        return redirect("dashboard:cohorts_list", course_pk=course_pk)
    ctx = base_context(request, active="courses")
    ctx.update({"object": instance, "title": f"حذف {instance}", "cancel_url": "dashboard:cohorts_list",
                "cancel_args": [course_pk]})
    return render(request, "dashboard/confirm_delete.html", ctx)


@section_required(SECTION_COURSES)
def lessons_list(request, cohort_pk):
    cohort = get_object_or_404(Cohort.objects.select_related("course"), pk=cohort_pk)
    ctx = base_context(request, active="courses")
    ctx.update({"cohort": cohort, "course": cohort.course, "lessons": cohort.lessons.all()})
    return render(request, "dashboard/lessons_list.html", ctx)


@section_required(SECTION_COURSES, "write")
@require_POST
def lessons_generate(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)
    if not cohort.start_date or not cohort.slots.exists():
        messages.error(request, "حدد تاريخ البداية وموعدًا أسبوعيًا واحدًا على الأقل أولًا.")
    else:
        n = cohort.generate_lessons()
        messages.success(request, f"تم توليد {n} جلسة." if n else "كل الجلسات موجودة بالفعل.")
    return redirect("dashboard:lessons_list", cohort_pk=cohort.pk)


@section_required(SECTION_COURSES, "write")
def lesson_form(request, cohort_pk, pk=None):
    cohort = get_object_or_404(Cohort.objects.select_related("course"), pk=cohort_pk)
    instance = get_object_or_404(Lesson, pk=pk, cohort=cohort) if pk else None
    form = LessonForm(request.POST or None, instance=instance)
    files = AttachmentFormSet(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid() and files.is_valid():
        lesson = form.save(commit=False)
        lesson.cohort = cohort
        lesson.save()
        files.instance = lesson
        files.save()
        cohort._renumber()
        messages.success(request, "تم حفظ الجلسة بنجاح.")
        return redirect("dashboard:lessons_list", cohort_pk=cohort.pk)
    ctx = base_context(request, active="courses")
    ctx.update({"form": form, "files": files, "cohort": cohort, "course": cohort.course, "instance": instance,
                "title": "تعديل جلسة" if instance else "إضافة جلسة"})
    return render(request, "dashboard/lesson_form.html", ctx)


@section_required(SECTION_COURSES, "write")
def lesson_delete(request, cohort_pk, pk):
    instance = get_object_or_404(Lesson.objects.select_related("cohort"), pk=pk, cohort_id=cohort_pk)
    if request.method == "POST":
        cohort = instance.cohort
        instance.delete()
        cohort._renumber()
        messages.success(request, "تم حذف الجلسة.")
        return redirect("dashboard:lessons_list", cohort_pk=cohort_pk)
    ctx = base_context(request, active="courses")
    ctx.update({"object": instance, "title": f"حذف {instance}", "cancel_url": "dashboard:lessons_list",
                "cancel_args": [cohort_pk]})
    return render(request, "dashboard/confirm_delete.html", ctx)


@section_required(SECTION_COURSES)
def enrollments_list(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    can_write = can_access(request.dashboard_role, SECTION_COURSES, "write")
    form = EnrollForm(request.POST or None, course=course)
    if request.method == "POST":
        if not can_write:
            raise PermissionDenied
        if form.is_valid():
            _, created = form.save()
            messages.success(request, "تم تسجيل الطالب." if created else "الطالب مسجل بالفعل (تم تفعيل اشتراكه).")
            return redirect("dashboard:enrollments_list", course_pk=course.pk)
    ctx = base_context(request, active="courses")
    ctx.update({"course": course, "form": form, "cohorts": course.cohorts.all(),
                "enrollments": course.enrollments.select_related("user", "cohort")})
    return render(request, "dashboard/enrollments_list.html", ctx)


@section_required(SECTION_COURSES, "write")
@require_POST
def enrollment_action(request, course_pk, pk, action):
    enrollment = get_object_or_404(Enrollment.objects.select_related("cohort"), pk=pk, course_id=course_pk)
    if action in ("delete", "toggle") and enrollment.cohort_id and enrollment.cohort.is_locked and enrollment.is_active:
        messages.error(request, placement.LOCKED)
    elif action == "delete":
        enrollment.delete()
        messages.success(request, "تم حذف التسجيل.")
    elif action == "toggle":
        enrollment.status = Enrollment.STATUS_CANCELLED if enrollment.is_active else Enrollment.STATUS_ACTIVE
        enrollment.save(update_fields=["status"])
        messages.success(request, "تم تحديث حالة الاشتراك.")
    elif action == "assign":
        # Put the student in a group (teacher + times); empty = unassigned.
        cohort_id = request.POST.get("cohort") or None
        cohort = get_object_or_404(Cohort, pk=cohort_id, course_id=course_pk) if cohort_id else None
        error = placement.move_enrollment(enrollment, cohort) if cohort else placement.remove_enrollment(enrollment)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, "تم تحديث مجموعة الطالب.")
    return redirect("dashboard:enrollments_list", course_pk=course_pk)


@section_required(SECTION_COURSES, "write")
def attendance_form(request, cohort_pk, pk):
    lesson = get_object_or_404(Lesson.objects.select_related("cohort__course"), pk=pk, cohort_id=cohort_pk)
    enrollments = list(lesson.cohort.enrollments.filter(status=Enrollment.STATUS_ACTIVE).select_related("user"))
    if request.method == "POST":
        present_ids = set(request.POST.getlist("present"))
        for e in enrollments:
            status = Attendance.PRESENT if str(e.pk) in present_ids else Attendance.ABSENT
            Attendance.objects.update_or_create(lesson=lesson, enrollment=e, defaults={"status": status})
        messages.success(request, "تم حفظ الحضور.")
        return redirect("dashboard:lessons_list", cohort_pk=cohort_pk)
    marked = {a.enrollment_id: a.status for a in lesson.attendance.all()}
    rows = [{"enrollment": e, "present": marked.get(e.pk) == Attendance.PRESENT} for e in enrollments]
    ctx = base_context(request, active="courses")
    ctx.update({"lesson": lesson, "cohort": lesson.cohort, "course": lesson.cohort.course, "rows": rows})
    return render(request, "dashboard/attendance_form.html", ctx)


# --- Enrollment requests -----------------------------------------------------

@section_required(SECTION_REQUESTS)
def requests_list(request):
    everything = EnrollmentRequest.objects.all()
    stats = {
        "total": everything.count(),
        "new": everything.filter(status=EnrollmentRequest.STATUS_NEW).count(),
        "teachers": everything.filter(kind=EnrollmentRequest.KIND_TEACHER).count(),
        "unpaid": everything.filter(kind=EnrollmentRequest.KIND_STUDENT,
                                    payment_status=EnrollmentRequest.PAYMENT_UNPAID).count(),
    }
    qs = everything.select_related("course")
    kind = request.GET.get("kind", "")
    if kind in dict(EnrollmentRequest.KIND_CHOICES):
        qs = qs.filter(kind=kind)
    status = request.GET.get("status", "")
    if status in dict(EnrollmentRequest.STATUS_CHOICES):
        qs = qs.filter(status=status)
    paid = request.GET.get("paid", "")
    if paid in dict(EnrollmentRequest.PAYMENT_CHOICES):
        qs = qs.filter(payment_status=paid)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(models.Q(full_name__icontains=q) | models.Q(phone__icontains=q) | models.Q(email__icontains=q))
    ctx = base_context(request, active="requests")
    ctx.update({"requests": qs, "kind": kind, "status": status, "paid": paid, "q": q, "stats": stats,
                "kind_choices": EnrollmentRequest.KIND_CHOICES,
                "status_choices": EnrollmentRequest.STATUS_CHOICES,
                "payment_choices": EnrollmentRequest.PAYMENT_CHOICES})
    return render(request, "dashboard/requests_list.html", ctx)


@section_required(SECTION_REQUESTS)
def request_detail(request, pk):
    obj = get_object_or_404(EnrollmentRequest.objects.select_related("course", "user"), pk=pk)
    can_write = can_access(request.dashboard_role, SECTION_REQUESTS, "write")
    form = RequestForm(request.POST or None, instance=obj)
    if request.method == "POST":
        if not can_write:
            raise PermissionDenied
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ الطلب.")
            return redirect("dashboard:request_detail", pk=obj.pk)
    ctx = base_context(request, active="requests")
    cohorts = []
    if obj.course:
        # Only groups the student can actually join: not launched, and with a free seat (or the one they hold).
        cohorts = [c for c in obj.course.cohorts.select_related("teacher")
                   if not c.is_locked and (c.mode == "private" or c.seats_left or c.pk == obj.cohort_id)]
    ctx.update({"obj": obj, "form": form, "cohorts": cohorts, "can_enroll": bool(obj.user and obj.course and obj.is_paid),
                "needs_payment": bool(obj.course and not obj.is_paid), "needs_account": bool(obj.course and obj.is_paid and not obj.user),
                "enrolled": bool(obj.user and obj.course and Enrollment.objects.filter(user=obj.user, course=obj.course).exists())})
    return render(request, "dashboard/request_detail.html", ctx)


@section_required(SECTION_REQUESTS, "write")
@require_POST
def request_enroll(request, pk):
    """Once the teacher and times are agreed, place the student.

    A forming group only collects the student on its waiting list (staff-only);
    they are enrolled, and see the course, when the group is launched.
    """
    obj = get_object_or_404(EnrollmentRequest.objects.select_related("user", "course", "cohort"), pk=pk)
    cohort = None
    if request.POST.get("cohort"):
        cohort = get_object_or_404(Cohort, pk=request.POST["cohort"], course=obj.course)
    if not (obj.user and obj.course):
        messages.error(request, "لا يمكن التسجيل: الطالب لم ينشئ حسابًا بعد.")
    elif not obj.is_paid:
        messages.error(request, placement.UNPAID)
    elif cohort:
        error = placement.place_request(obj, cohort)
        if error:
            messages.error(request, error)
        elif obj.status == EnrollmentRequest.STATUS_WAITING:
            messages.success(request, f"أُضيف الطالب إلى قائمة انتظار المجموعة ({cohort.seats_taken()} / {cohort.min_students}).")
        else:
            messages.success(request, "تم تسجيل الطالب في الكورس.")
    else:
        enrollment, _ = Enrollment.objects.get_or_create(user=obj.user, course=obj.course)
        enrollment.status = Enrollment.STATUS_ACTIVE
        enrollment.save()
        obj.status = EnrollmentRequest.STATUS_ENROLLED
        obj.save(update_fields=["status"])
        messages.success(request, "تم تسجيل الطالب في الكورس.")
    return redirect("dashboard:request_detail", pk=obj.pk)


@section_required(SECTION_COURSES, "write")
@require_POST
def cohort_confirm(request, course_pk, pk):
    """Launch a group: enrol everyone waiting and make the sessions. Needs a teacher.

    Normally waits for the minimum; staff can launch earlier on purpose (`force`).
    After this the group is frozen (see `Cohort.is_locked`).
    """
    cohort = get_object_or_404(Cohort, pk=pk, course_id=course_pk)
    if not cohort.is_forming:
        messages.error(request, "هذه المجموعة مُطلقة بالفعل.")
    elif not cohort.teacher_id:
        messages.error(request, "عيّن مدرسًا للمجموعة أولًا قبل إطلاقها.")
    elif not cohort.is_ready_to_confirm and not request.POST.get("force"):
        messages.error(request, f"العدد لم يكتمل بعد ({cohort.seats_taken()} / {cohort.min_students}).")
    else:
        count = cohort.confirm()
        messages.success(request, f"تم إطلاق المجموعة وتسجيل {count} طالب. لم يعد ممكنًا إدخال طلاب أو إخراجهم.")
    return redirect("dashboard:cohort_detail", pk=cohort.pk)
