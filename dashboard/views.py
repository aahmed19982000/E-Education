from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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


@section_required(SECTION_COURSES)
def all_cohorts(request):
    """Every group of every course in one place, filterable by where it is in its life."""
    current = request.GET.get("status", "all")
    qs = Cohort.objects.select_related("course", "teacher").annotate(
        lessons_count=Count("lessons", distinct=True), students_count=Count("enrollments", distinct=True),
    ).prefetch_related("requests", "enrollments__user")
    if current == "private":
        qs = qs.filter(mode="private")
    elif current in ("forming", "ready", "confirmed"):
        qs = qs.filter(mode="group", confirmed_at__isnull=current != "confirmed")
    cohorts = list(qs)
    if current == "ready":
        cohorts = [c for c in cohorts if c.is_ready_to_confirm]
    elif current == "forming":
        cohorts = [c for c in cohorts if not c.is_ready_to_confirm]
    ctx = base_context(request, active="cohorts")
    ctx.update({"cohorts": cohorts, "course": None, "current": current, "filters": [
        ("all", "الكل"), ("forming", "قيد التكوين"), ("ready", "اكتمل العدد"),
        ("confirmed", "مؤكدة"), ("private", "خصوصي")]})
    return render(request, "dashboard/cohorts_list.html", ctx)


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
    enrollment = get_object_or_404(Enrollment, pk=pk, course_id=course_pk)
    if action == "delete":
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
        enrollment.cohort = cohort
        enrollment.save(update_fields=["cohort"])
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
    ctx.update({"obj": obj, "form": form, "cohorts": obj.course.cohorts.all() if obj.course else [], "can_enroll": bool(obj.user and obj.course),
                "enrolled": bool(obj.user and obj.course and Enrollment.objects.filter(user=obj.user, course=obj.course).exists())})
    return render(request, "dashboard/request_detail.html", ctx)


def _already_in(req, cohort):
    """True when the request's student already holds a seat in this cohort (waiting or enrolled)."""
    return (req.cohort_id == cohort.pk and req.status == EnrollmentRequest.STATUS_WAITING) or \
        Enrollment.objects.filter(user=req.user, course=req.course, cohort=cohort).exists()


@section_required(SECTION_REQUESTS, "write")
@require_POST
def request_enroll(request, pk):
    """Once the teacher and times are agreed, place the student.

    A forming group only collects the student on its waiting list (staff-only);
    they are enrolled, and see the course, when the group is confirmed.
    """
    obj = get_object_or_404(EnrollmentRequest, pk=pk)
    cohort = None
    if request.POST.get("cohort"):
        cohort = get_object_or_404(Cohort, pk=request.POST["cohort"], course=obj.course)
    if not (obj.user and obj.course):
        messages.error(request, "لا يمكن التسجيل: الطالب لم ينشئ حسابًا بعد.")
    elif cohort and cohort.mode == "group" and cohort.seats_left == 0 and not _already_in(obj, cohort):
        messages.error(request, "المجموعة مكتملة العدد.")
    elif cohort and cohort.is_forming:
        obj.cohort = cohort
        obj.status = EnrollmentRequest.STATUS_WAITING
        obj.save(update_fields=["cohort", "status"])
        messages.success(request, f"أُضيف الطالب إلى قائمة انتظار المجموعة ({cohort.seats_taken()} / {cohort.min_students}).")
    else:
        enrollment, _ = Enrollment.objects.get_or_create(user=obj.user, course=obj.course)
        if not enrollment.is_active:
            enrollment.status = Enrollment.STATUS_ACTIVE
        if cohort:
            enrollment.cohort = cohort
        enrollment.save()
        obj.status = EnrollmentRequest.STATUS_ENROLLED
        obj.save(update_fields=["status"])
        messages.success(request, "تم تسجيل الطالب في الكورس.")
    return redirect("dashboard:request_detail", pk=obj.pk)


@section_required(SECTION_COURSES, "write")
@require_POST
def cohort_confirm(request, course_pk, pk):
    """Staff start a group whose waiting list reached the minimum: enrol everyone and make the sessions."""
    cohort = get_object_or_404(Cohort, pk=pk, course_id=course_pk)
    if not cohort.is_forming:
        messages.error(request, "هذه المجموعة مؤكدة بالفعل.")
    elif not cohort.is_ready_to_confirm and not request.POST.get("force"):
        messages.error(request, f"العدد لم يكتمل بعد ({cohort.seats_taken()} / {cohort.min_students}).")
    else:
        count = cohort.confirm()
        messages.success(request, f"تم تأكيد المجموعة وتسجيل {count} طالب.")
    return redirect("dashboard:cohorts_list", course_pk=course_pk)
