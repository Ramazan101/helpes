"""
Представления для обслуживания PWA: Service Worker, Web App Manifest и Offline-страницы.
"""
from pathlib import Path
from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "HEAD"])
def offline_view(request: HttpRequest) -> HttpResponse:
    """Оффлайн-страница fallback с автономной памяткой самопроверки."""
    response = render(request, "offline.html")
    response["Cache-Control"] = "public, max-age=86400"
    return response


@require_http_methods(["GET", "HEAD"])
def service_worker_view(request: HttpRequest) -> HttpResponse:
    """
    Отдаёт Service Worker с корневого URL (/sw.js) с областью действия scope='/'.
    Заголовок Service-Worker-Allowed гарантирует разрешение глобального scope.
    """
    sw_path = settings.BASE_DIR / "static" / "js" / "sw.js"
    if not sw_path.exists():
        raise Http404("Service worker script not found.")
    content = sw_path.read_text(encoding="utf-8")
    response = HttpResponse(content, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, must-revalidate"
    return response


@require_http_methods(["GET", "HEAD"])
def manifest_view(request: HttpRequest) -> HttpResponse:
    """Отдаёт Web App Manifest (/manifest.json)."""
    manifest_path = settings.BASE_DIR / "static" / "manifest.json"
    if not manifest_path.exists():
        raise Http404("Web app manifest not found.")
    content = manifest_path.read_text(encoding="utf-8")
    response = HttpResponse(content, content_type="application/manifest+json")
    response["Cache-Control"] = "public, max-age=86400"
    return response
