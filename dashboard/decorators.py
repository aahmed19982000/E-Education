from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .permissions import can_access, get_dashboard_role


def dashboard_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        role = get_dashboard_role(request.user)
        if role is None:
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url="dashboard:login")
            messages.error(request, "ليس لديك صلاحية الوصول إلى لوحة التحكم.")
            return redirect("core:home")
        request.dashboard_role = role
        return view_func(request, *args, **kwargs)
    return wrapper


def section_required(section, mode="read"):
    def decorator(view_func):
        @wraps(view_func)
        @dashboard_required
        def wrapper(request, *args, **kwargs):
            if not can_access(request.dashboard_role, section, mode):
                raise PermissionDenied("ليس لديك صلاحية الوصول إلى هذا القسم.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
