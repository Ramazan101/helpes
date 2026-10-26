"""Серверные декораторы проверки ролей доступа."""
from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def tech_required(view_func):
    """Разрешает доступ активным техникам и администраторам."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user.is_active or not getattr(user, "is_tech_role", False):
            raise PermissionDenied("Недостаточно прав для доступа к панели технической службы.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def admin_required(view_func):
    """Разрешает доступ только активным администраторам."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user.is_active or not getattr(user, "is_admin_role", False):
            raise PermissionDenied("Доступ разрешён только администраторам системы.")
        return view_func(request, *args, **kwargs)
    return _wrapped
