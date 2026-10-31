"""Корневой маршрутизатор URL для системы Helpes."""
from django.contrib import admin
from django.urls import include, path

from apps.tickets import views_pwa

urlpatterns = [
    # PWA Core: Service Worker (scope='/'), Manifest и Offline-страница
    path("sw.js", views_pwa.service_worker_view, name="service_worker"),
    path("manifest.json", views_pwa.manifest_view, name="manifest"),
    path("offline/", views_pwa.offline_view, name="offline"),

    path("django-admin/", admin.site.urls),
    path("", include("apps.accounts.urls", namespace="accounts")),
    path("manage/locations/", include("apps.locations.urls", namespace="locations")),
    path("assistant/", include("apps.assistant.urls", namespace="assistant")),
    path("", include("apps.tickets.urls", namespace="tickets")),
]
