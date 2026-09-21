from django.contrib.auth import login, logout
from django.contrib import messages
from django.shortcuts import redirect, render

from .auth_utils import authenticate_by_email
from .forms import EmailLoginForm, RegisterForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

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
                return redirect("core:home")
        else:
            login_form = EmailLoginForm(request.POST)
            if login_form.is_valid():
                email = login_form.cleaned_data["email"].lower().strip()
                password = login_form.cleaned_data["password"]
                user = authenticate_by_email(request, email, password)
                if user is not None:
                    login(request, user)
                    return redirect("core:home")
                login_form.add_error(None, "بيانات الدخول غير صحيحة / Invalid credentials.")

    return render(request, "accounts/auth.html", {
        "mode": mode,
        "login_form": login_form,
        "register_form": register_form,
    })


def logout_view(request):
    logout(request)
    return redirect("core:home")
