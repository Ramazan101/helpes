"""
API эндпоинты для проверки сессий и учётных записей Help Desk.
"""
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "HEAD"])
def session_status_api(request: HttpRequest) -> JsonResponse:
    """
    Возвращает статус текущей сессии для десктопных клиентов, PWA и виджетов.
    - Для анонимного пользователя: строго {"authenticated": False}
    - Для авторизованного: данные текущего пользователя (username, display_name, role, is_admin, is_tech)
    - Обязательно устанавливает Cache-Control: no-store во избежание утечки или отображения
      сессионных данных предыдущего пользователя после выхода.
    """
    user = request.user
    if not user.is_authenticated:
        data = {"authenticated": False}
    else:
        data = {
            "authenticated": True,
            "username": user.username,
            "display_name": getattr(user, "display_name", user.username),
            "role": getattr(user, "role", ""),
            "is_admin": getattr(user, "is_admin_role", False),
            "is_tech": getattr(user, "is_tech_role", False),
        }

    response = JsonResponse(data)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response
