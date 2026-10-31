import json
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestPWAResources:
    def test_manifest_json_accessible_and_valid(self, client):
        url = reverse("manifest")
        response = client.get(url)
        assert response.status_code == 200
        assert "application/manifest+json" in response["Content-Type"]
        assert "public" in response.get("Cache-Control", "")

        data = json.loads(response.content.decode("utf-8"))
        assert data["name"] == "Help Desk — Кыргыз Алтын"
        assert data["short_name"] == "Help Desk"
        assert data["display"] == "standalone"
        assert data["start_url"] == "/"
        assert data["scope"] == "/"
        assert data["theme_color"] == "#1e293b"
        assert len(data["icons"]) >= 2
        icon_sizes = [icon["sizes"] for icon in data["icons"]]
        assert "192x192" in icon_sizes
        assert "512x512" in icon_sizes

    def test_service_worker_script_accessible_and_scoped(self, client):
        url = reverse("service_worker")
        response = client.get(url)
        assert response.status_code == 200
        assert "application/javascript" in response["Content-Type"]
        # Проверяем ключевой заголовок области действия PWA
        assert response.get("Service-Worker-Allowed") == "/"
        assert "no-cache" in response.get("Cache-Control", "")

        content = response.content.decode("utf-8")
        assert "CACHE_NAME" in content
        assert "NEVER_CACHE_PATTERNS" in content
        assert "/offline/" in content
        # Проверяем запретные паттерны для исключения утечек персональных данных
        assert "api" in content
        assert "accounts" in content
        assert "tech" in content
        assert "manage" in content

    def test_offline_page_accessible_with_memos(self, client):
        url = reverse("offline")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Оффлайн" in content
        assert "Кыргыз Алтын" in content
        # Проверяем памятки на русском и кыргызском языках
        assert "Нет интернета" in content
        assert "Не печатает принтер" in content
        assert "Интернет же локалдык тармак" in content
        assert "Кайра туташуу" in content
        assert "window.location.reload" in content

    def test_pwa_icons_exist_on_disk_and_valid(self):
        from django.conf import settings

        icon_192 = settings.BASE_DIR / "static" / "icons" / "icon-192.png"
        icon_512 = settings.BASE_DIR / "static" / "icons" / "icon-512.png"
        icon_svg = settings.BASE_DIR / "static" / "icons" / "icon.svg"

        assert icon_192.exists()
        assert icon_192.stat().st_size > 100
        assert icon_192.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

        assert icon_512.exists()
        assert icon_512.stat().st_size > 100
        assert icon_512.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

        assert icon_svg.exists()
        assert "<svg" in icon_svg.read_text(encoding="utf-8")

    def test_base_template_includes_pwa_manifest_and_sw_registration(self, client):
        response = client.get(reverse("tickets:public_create"))
        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert reverse("manifest") in html
        assert 'name="theme-color"' in html
        assert reverse("service_worker") in html
        assert "navigator.serviceWorker.register" in html


@pytest.mark.django_db
class TestSessionStatusAPI:
    def test_anonymous_user_returns_strictly_authenticated_false(self, client):
        url = reverse("accounts:api_session_status")
        response = client.get(url)
        assert response.status_code == 200
        assert "application/json" in response["Content-Type"]
        # Проверяем критический заголовок против кэширования сессий
        cache_control = response.get("Cache-Control", "")
        assert "no-store" in cache_control

        data = response.json()
        assert data == {"authenticated": False}
        assert "username" not in data
        assert "role" not in data

    def test_authenticated_tech_user_returns_proper_data(self, client):
        tech_user = User.objects.create_user(
            username="tech_bakyt",
            password="StrongPassword123!",
            role=User.Role.TECH,
            full_name="Бакыт Асанов",
        )
        client.login(username="tech_bakyt", password="StrongPassword123!")

        url = reverse("accounts:api_session_status")
        response = client.get(url)
        assert response.status_code == 200
        assert "no-store" in response.get("Cache-Control", "")

        data = response.json()
        assert data["authenticated"] is True
        assert data["username"] == "tech_bakyt"
        assert data["display_name"] == "Бакыт Асанов"
        assert data["role"] == "TECH"
        assert data["is_tech"] is True
        assert data["is_admin"] is False
        # Проверяем отсутствие паролей или хешей
        assert "password" not in data

    def test_authenticated_admin_user_returns_proper_data(self, client):
        admin_user = User.objects.create_user(
            username="admin_altyn",
            password="StrongPassword123!",
            role=User.Role.ADMIN,
            full_name="Администратор Системы",
        )
        client.login(username="admin_altyn", password="StrongPassword123!")

        url = reverse("accounts:api_session_status")
        response = client.get(url)
        assert response.status_code == 200

        data = response.json()
        assert data["authenticated"] is True
        assert data["username"] == "admin_altyn"
        assert data["role"] == "ADMIN"
        assert data["is_tech"] is True
        assert data["is_admin"] is True

    def test_post_and_put_methods_rejected(self, client):
        url = reverse("accounts:api_session_status")
        assert client.post(url).status_code == 405
        assert client.put(url).status_code == 405
        assert client.delete(url).status_code == 405

    def test_logout_immediately_invalidates_session_status(self, client):
        User.objects.create_user(
            username="test_tech",
            password="Password123!",
            role=User.Role.TECH,
        )
        client.login(username="test_tech", password="Password123!")

        status_url = reverse("accounts:api_session_status")
        r1 = client.get(status_url)
        assert r1.json()["authenticated"] is True

        # Выход из системы
        logout_url = reverse("accounts:logout")
        client.post(logout_url)

        # Повторная проверка статуса
        r2 = client.get(status_url)
        assert r2.json() == {"authenticated": False}
