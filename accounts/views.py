from urllib.parse import quote

from django.contrib.auth import login, logout
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .auth_utils import authenticate_by_email
from .forms import EmailLoginForm, RegisterForm


def _next_url(request):
    """The page to return to after signing in (e.g. the checkout), if it is a safe local URL."""
    url = request.GET.get("next") or request.POST.get("next") or ""
    ok = url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    return url if ok else ""


def login_view(request):
    next_url = _next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url or "core:home")

    mode = request.GET.get("mode", "login")
    if mode not in ("login", "register"):
        mode = "login"
    login_form = EmailLoginForm()
    register_form = RegisterForm()

    if request.method == "POST":
        mode = request.POST.get("mode", "login")
        if mode == "register":
            register_form = RegisterForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                success_msg = "تم إنشاء حسابك بنجاح" if request.lang == "ar" else "Your account was created successfully"
                messages.success(request, success_msg)
                return redirect(next_url or "core:home")
        else:
            login_form = EmailLoginForm(request.POST)
            if login_form.is_valid():
                email = login_form.cleaned_data["email"].lower().strip()
                password = login_form.cleaned_data["password"]
                user = authenticate_by_email(request, email, password)
                if user is not None:
                    login(request, user)
                    return redirect(next_url or "core:home")
                login_form.add_error(None, "بيانات الدخول غير صحيحة / Invalid credentials.")

    return render(request, "accounts/auth.html", {
        "mode": mode,
        "next_qs": f"&next={quote(next_url)}" if next_url else "",
        "login_form": login_form,
        "register_form": register_form,
    })


def logout_view(request):
    logout(request)
    return redirect("core:home")
