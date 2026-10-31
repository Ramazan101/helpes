"""Тесты для серверной поддержки десктопного виджета (Этап 3)."""
import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
class TestTauriWidgetBackend:
    def test_widget_window_accessible_anonymously(self, client):
        url = reverse("assistant:widget_window")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Help Desk ИТ-помощник" in content
        assert "data-assistant-container" in content
        assert "data-tauri-drag-region" in content
        assert "btn-pin" in content
        assert "btn-close" in content
        assert "csrftoken" in response.cookies

    def test_widget_window_shows_authenticated_technician(self, client):
        tech = User.objects.create_user(
            username="widget_tech",
            password="password123",
            full_name="Служба Поддержки",
            role=User.Role.TECH,
        )
        client.force_login(tech)

        url = reverse("assistant:widget_window")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Служба Поддержки" in content
        assert "Очередь" in content

    def test_widget_window_allows_get_and_head_but_rejects_post(self, client):
        url = reverse("assistant:widget_window")
        head_response = client.head(url)
        assert head_response.status_code == 200

        post_response = client.post(url, data={})
        assert post_response.status_code == 405
