"""REST/JSON API для технической очереди и Web Push уведомлений."""
import json
import logging
from functools import wraps
from typing import Callable

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import Ticket, WebPushSubscription

logger = logging.getLogger(__name__)


def tech_api_required(view_func: Callable) -> Callable:
    """
    Проверяет аутентификацию и права технического специалиста / администратора.
    Возвращает JSON с кодами 401 / 403 вместо HTML редиректа на страницу входа.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Требуется авторизация"}, status=401)
        if not request.user.is_active or not getattr(request.user, "is_tech_role", False):
            return JsonResponse({"error": "Доступ разрешён только технической службе"}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped


def _no_cache(response: JsonResponse) -> JsonResponse:
    """Устанавливает строгие заголовки запрета кэширования для приватных API."""
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response["Pragma"] = "no-cache"
    return response


@tech_api_required
@require_GET
def queue_summary_api(request) -> JsonResponse:
    """
    Возвращает актуальную сводку по количеству заявок и ID последней созданной заявки.
    Используется JS для in-app polling (каждые 30-60 секунд) без перезагрузки страницы.
    """
    latest_ticket = Ticket.objects.order_by("-id").first()
    data = {
        "unassigned": Ticket.objects.filter(assigned_to__isnull=True).exclude(status=Ticket.Status.DONE).count(),
        "mine": Ticket.objects.filter(assigned_to=request.user).exclude(status=Ticket.Status.DONE).count(),
        "all_open": Ticket.objects.exclude(status=Ticket.Status.DONE).count(),
        "latest_ticket_id": latest_ticket.id if latest_ticket else 0,
        "latest_ticket_number": latest_ticket.ticket_number if latest_ticket else "",
    }
    return _no_cache(JsonResponse(data))


@tech_api_required
@require_GET
def push_vapid_key_api(request) -> JsonResponse:
    """
    Возвращает публичный ключ VAPID для регистрации PushSubscription в браузере.
    Секретный ключ никогда не передаётся клиенту.
    """
    public_key = getattr(settings, "PUSH_VAPID_PUBLIC_KEY", "")
    return _no_cache(JsonResponse({"public_key": public_key}))


@tech_api_required
@require_POST
def push_subscribe_api(request) -> JsonResponse:
    """
    Регистрирует или обновляет подписку PushSubscription для текущего пользователя.
    Поддерживает несколько устройств одного пользователя (разные endpoint).
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Некорректный JSON"}, status=400)

    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return JsonResponse({"error": "Отсутствуют обязательные параметры endpoint или ключи"}, status=400)

    user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]

    subscription, created = WebPushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent,
        },
    )

    return _no_cache(JsonResponse({
        "status": "subscribed",
        "created": created,
    }))


@tech_api_required
@require_POST
def push_unsubscribe_api(request) -> JsonResponse:
    """
    Отзывает подписку Web Push по endpoint для текущего пользователя.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Некорректный JSON"}, status=400)

    endpoint = (data.get("endpoint") or "").strip()
    if not endpoint:
        return JsonResponse({"error": "Параметр endpoint обязателен"}, status=400)

    deleted_count, _ = WebPushSubscription.objects.filter(
        endpoint=endpoint,
        user=request.user,
    ).delete()

    return _no_cache(JsonResponse({
        "status": "unsubscribed",
        "deleted": deleted_count > 0,
    }))
