from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.auth_utils import authenticate_by_email
from articles.models import Article
from contact_us.models import ContactMessage
from levels.models import Level
from quiz.grading import format_marks, question_marks
from django.db.models import Count

from quiz.models import AUDIO_MAX_MB, MAX_OPTIONS, MIN_OPTIONS, Category, Question, QuizSettings

from .decorators import dashboard_required, section_required
from .forms import (
    ArticleForm, CategoryForm, DashboardLoginForm, LevelForm, PlacementForm, QuestionForm, QuizSettingsForm, StaffUserCreateForm, StaffUserEditForm,
)
from .permissions import (
    SECTION_ARTICLES, SECTION_LEVELS, SECTION_MESSAGES, SECTION_QUESTIONS, SECTION_USERS,
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
        "can_write_levels": can_access(role, SECTION_LEVELS, "write"),
        "can_view_levels": can_access(role, SECTION_LEVELS),
        "can_write_articles": can_access(role, SECTION_ARTICLES, "write"),
        "can_view_articles": can_access(role, SECTION_ARTICLES),
        "can_write_questions": can_access(role, SECTION_QUESTIONS, "write"),
        "can_view_questions": can_access(role, SECTION_QUESTIONS),
        "can_write_messages": can_access(role, SECTION_MESSAGES, "write"),
        "can_view_messages": can_access(role, SECTION_MESSAGES),
        "can_view_users": can_access(role, SECTION_USERS),
    }


@dashboard_required
def index(request):
    ctx = base_context(request, active="index")
    if ctx["can_view_levels"]:
        ctx["levels_count"] = Level.objects.count()
    if ctx["can_view_articles"]:
        ctx["articles_count"] = Article.objects.count()
    if ctx["can_view_questions"]:
        ctx["questions_count"] = Question.objects.count()
    if ctx["can_view_messages"]:
        ctx["messages_count"] = ContactMessage.objects.count()
    if ctx["can_view_users"]:
        ctx["users_count"] = User.objects.filter(is_staff=True).count()
    return render(request, "dashboard/index.html", ctx)


# --- Levels ---------------------------------------------------------------

@section_required(SECTION_LEVELS)
def levels_list(request):
    ctx = base_context(request, active="levels")
    ctx["levels"] = Level.objects.all()
    return render(request, "dashboard/levels_list.html", ctx)


@section_required(SECTION_LEVELS, "write")
def level_form(request, pk=None):
    instance = get_object_or_404(Level, pk=pk) if pk else None
    if request.method == "POST":
        form = LevelForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ المستوى بنجاح.")
            return redirect("dashboard:levels_list")
    else:
        form = LevelForm(instance=instance)
    ctx = base_context(request, active="levels")
    ctx.update({"form": form, "instance": instance, "title": "تعديل مستوى" if instance else "إضافة مستوى"})
    return render(request, "dashboard/level_form.html", ctx)


@section_required(SECTION_LEVELS, "write")
def level_delete(request, pk):
    instance = get_object_or_404(Level, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "تم حذف المستوى.")
        return redirect("dashboard:levels_list")
    ctx = base_context(request, active="levels")
    ctx.update({"object": instance, "title": f"حذف المستوى {instance.code}", "cancel_url": "dashboard:levels_list"})
    return render(request, "dashboard/confirm_delete.html", ctx)


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


@section_required(SECTION_QUESTIONS, "write")
def quiz_placement(request):
    levels = Level.objects.all()
    form = PlacementForm(request.POST or None, levels=levels)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم حفظ قواعد تحديد المستوى.")
        return redirect("dashboard:quiz_placement")
    settings = QuizSettings.load()
    total = question_marks(Question.objects.all(), settings)
    ctx = base_context(request, active="questions")
    ctx.update({
        "form": form,
        "title": "تحديد مستوى الطالب",
        "total_marks": float(sum(total.values())) if total else 0,
    })
    return render(request, "dashboard/quiz_placement.html", ctx)


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
    ctx["staff_users"] = User.objects.filter(is_staff=True).select_related("profile").order_by("-is_superuser", "first_name")
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
