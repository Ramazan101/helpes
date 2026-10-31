import json
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .knowledge_base import KNOWLEDGE_BASE
from .services import (
    AssistantValidationError,
    generate_assistant_response,
    is_ai_configured,
)


QUICK_PROMPTS: tuple[dict[str, str], ...] = (
    {
        "label": "Не печатает принтер",
        "prompt": "Не печатает принтер в кабинете, что можно проверить самостоятельно?",
    },
    {
        "label": "Нет интернета",
        "prompt": "На компьютере пропал интернет и не открываются сайты. Что проверить?",
    },
    {
        "label": "Компьютер не включается",
        "prompt": "Нажимаю кнопку включения на компьютере, но экран чёрный и он не включается.",
    },
    {
        "label": "Не открывается программа",
        "prompt": "Не открывается рабочая программа или зависло окно, что делать?",
    },
)


def _get_client_identifier(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "unknown")
    if not request.session.session_key:
        request.session.save()
    session_part = request.session.session_key or "nosession"
    return f"assistant_rl:{ip}:{session_part}"


def _is_rate_limited(request: HttpRequest) -> bool:
    limit = int(getattr(settings, "AI_ASSISTANT_RATE_LIMIT", 15))
    if limit <= 0:
        return False
    cache_key = _get_client_identifier(request)
    current = cache.get(cache_key, 0)
    if current >= limit:
        return True
    if current == 0:
        cache.set(cache_key, 1, timeout=60)
    else:
        try:
            cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=60)
    return False


@require_GET
@ensure_csrf_cookie
def assistant_chat_page(request: HttpRequest) -> HttpResponse:
    """Полноэкранная страница AI-помощника (/assistant/) для Desktop, планшетов и смартфонов."""
    context = {
        "ai_configured": is_ai_configured(),
        "quick_prompts": QUICK_PROMPTS,
        "knowledge_topics": KNOWLEDGE_BASE,
        "max_message_length": getattr(settings, "AI_ASSISTANT_MAX_MESSAGE_LENGTH", 1000),
    }
    return render(request, "assistant/chat_page.html", context)


@require_http_methods(["GET", "HEAD"])
@ensure_csrf_cookie
def assistant_widget_view(request: HttpRequest) -> HttpResponse:
    """Компактное окно виджета (/assistant/widget/) для плавающего десктопного приложения Tauri."""
    context = {
        "ai_configured": is_ai_configured(),
        "quick_prompts": QUICK_PROMPTS,
        "knowledge_topics": KNOWLEDGE_BASE,
        "max_message_length": getattr(settings, "AI_ASSISTANT_MAX_MESSAGE_LENGTH", 1000),
    }
    return render(request, "assistant/widget_window.html", context)



@require_POST
def assistant_chat_api(request: HttpRequest) -> JsonResponse:
    """
    POST JSON API (/assistant/api/chat/).
    Принимает {"message": "...", "history": [{"role": "user"|"assistant", "content": "..."}]}
    и возвращает структурированный JSON-ответ.
    """
    if _is_rate_limited(request):
        return JsonResponse(
            {
                "error": "Слишком много запросов. Пожалуйста, подождите минуту или оформите заявку напрямую.",
                "error_code": "rate_limited",
                "suggest_ticket": True,
            },
            status=429,
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {
                "error": "Некорректный формат запроса (ожидается валидный JSON).",
                "error_code": "invalid_json",
            },
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {
                "error": "Тело запроса должно быть JSON-объектом.",
                "error_code": "invalid_payload",
            },
            status=400,
        )

    try:
        result = generate_assistant_response(
            raw_message=payload.get("message"),
            raw_history=payload.get("history", []),
        )
    except AssistantValidationError as exc:
        return JsonResponse(
            {
                "error": str(exc),
                "error_code": "validation_error",
            },
            status=400,
        )

    if result.error_code in ("auth_error", "quota_exceeded", "provider_unavailable", "provider_error"):
        status_code = 503
    elif result.error_code == "timeout":
        status_code = 504
    elif result.error_code == "rate_limited":
        status_code = 429
    else:
        status_code = 200
    return JsonResponse(result.to_dict(), status=status_code)

