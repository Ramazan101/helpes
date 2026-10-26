"""Корневой маршрутизатор URL для системы Helpes."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("apps.accounts.urls", namespace="accounts")),
    path("manage/locations/", include("apps.locations.urls", namespace="locations")),
    path("", include("apps.tickets.urls", namespace="tickets")),
]
