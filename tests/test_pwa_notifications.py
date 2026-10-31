"""Тесты для Этапа 2: Система уведомлений PWA о новых заявках."""
import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.accounts.models import User
from apps.locations.models import Floor, Location
from apps.tickets.models import EquipmentCategory, Ticket, WebPushSubscription
from apps.tickets.push_service import (
    get_recipients_for_ticket,
    notify_technicians_new_ticket,
    send_web_push,
)
from apps.tickets.services import (
    add_ticket_comment,
    claim_ticket,
    create_public_ticket,
    return_ticket_to_queue,
    update_ticket_status,
)
from django.test import TestCase


@pytest.fixture
def notify_setup(db):
    cache.clear()
    floor1 = Floor.objects.create(name="1 этаж", sort_order=1)
    room101 = Location.objects.create(floor=floor1, name="Кабинет 101", sort_order=1)
    cat_pc = EquipmentCategory.objects.create(name="Компьютер или ноутбук", sort_order=10)

    tech1 = User.objects.create_user(
        username="tech1", password="password123", full_name="Техник Один", role=User.Role.TECH
    )
    tech2 = User.objects.create_user(
        username="tech2", password="password123", full_name="Техник Два", role=User.Role.TECH
    )
    admin = User.objects.create_user(
        username="admin1", password="password123", full_name="Администратор", role=User.Role.ADMIN
    )
    regular_user = User.objects.create_user(
        username="employee1", password="password123", full_name="Обычный Сотрудник"
    )
    # Сбрасываем у обычного пользователя роль техника, если по умолчанию встала роль
    regular_user.role = ""
    regular_user.save()

    return {
        "floor1": floor1,
        "room101": room101,
        "cat_pc": cat_pc,
        "tech1": tech1,
        "tech2": tech2,
        "admin": admin,
        "regular_user": regular_user,
    }


# ==============================================================
# 1. Тесты API сводки очереди: GET /tech/api/queue/summary/
# ==============================================================

@pytest.mark.django_db
class TestQueueSummaryAPI:
    def test_queue_summary_anonymous_returns_401(self, client):
        url = reverse("tickets:tech_api_queue_summary")
        response = client.get(url)
        assert response.status_code == 401
        data = response.json()
        assert "error" in data

    def test_queue_summary_non_tech_returns_403(self, client, notify_setup):
        client.force_login(notify_setup["regular_user"])
        url = reverse("tickets:tech_api_queue_summary")
        response = client.get(url)
        assert response.status_code == 403
        data = response.json()
        assert "error" in data

    def test_queue_summary_tech_returns_200_and_no_cache(self, client, notify_setup):
        client.force_login(notify_setup["tech1"])
        url = reverse("tickets:tech_api_queue_summary")
        response = client.get(url)
        assert response.status_code == 200
        assert "no-store" in response.get("Cache-Control", "")

        data = response.json()
        assert "unassigned" in data
        assert "mine" in data
        assert "all_open" in data
        assert "latest_ticket_id" in data
        assert "latest_ticket_number" in data

    def test_queue_summary_counts_accuracy(self, client, notify_setup):
        # Создаём заявку
        t1 = create_public_ticket(
            employee_name="Асанов Б.",
            location=notify_setup["room101"],
            custom_location="",
            short_description="Не включается монитор",
            detailed_description="",
            items_data=[{"category": notify_setup["cat_pc"], "quantity": 1}],
        )

        client.force_login(notify_setup["tech1"])
        url = reverse("tickets:tech_api_queue_summary")
        res1 = client.get(url).json()
        assert res1["unassigned"] == 1
        assert res1["mine"] == 0
        assert res1["all_open"] == 1
        assert res1["latest_ticket_id"] == t1.id
        assert res1["latest_ticket_number"] == t1.ticket_number

        # Техник 1 берёт заявку в работу
        claim_ticket(ticket_number=t1.ticket_number, tech_user=notify_setup["tech1"])

        res2 = client.get(url).json()
        assert res2["unassigned"] == 0
        assert res2["mine"] == 1
        assert res2["all_open"] == 1


# ==============================================================
# 2. Тесты VAPID публичного ключа: GET /tech/api/push/vapid-key/
# ==============================================================

@pytest.mark.django_db
class TestPushVapidKeyAPI:
    def test_vapid_key_anonymous_returns_401(self, client):
        url = reverse("tickets:tech_api_push_vapid_key")
        response = client.get(url)
        assert response.status_code == 401

    def test_vapid_key_tech_returns_configured_key(self, client, notify_setup, settings):
        settings.PUSH_VAPID_PUBLIC_KEY = "test-public-vapid-key-12345"
        client.force_login(notify_setup["tech1"])
        url = reverse("tickets:tech_api_push_vapid_key")
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["public_key"] == "test-public-vapid-key-12345"


# ==============================================================
# 3. Тесты регистрации и отзыва подписки: subscribe / unsubscribe
# ==============================================================

@pytest.mark.django_db
class TestPushSubscriptionLifecycle:
    def test_subscribe_anonymous_returns_401(self, client):
        url = reverse("tickets:tech_api_push_subscribe")
        response = client.post(
            url,
            data=json.dumps({"endpoint": "https://push.example.com/sub/1"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_subscribe_success_creates_model(self, client, notify_setup):
        client.force_login(notify_setup["tech1"])
        url = reverse("tickets:tech_api_push_subscribe")
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/device123",
            "keys": {
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QT9h0qvqKEA1fZScW9Twgj0vgSD5y7Z50n80f3",
                "auth": "tBHItJI5svbpez7KI4CCXg",
            },
        }
        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 200
        assert response.json()["status"] == "subscribed"

        sub = WebPushSubscription.objects.get(endpoint=payload["endpoint"])
        assert sub.user == notify_setup["tech1"]
        assert sub.p256dh == payload["keys"]["p256dh"]
        assert sub.auth == payload["keys"]["auth"]

    def test_subscribe_same_endpoint_updates_without_duplicates(self, client, notify_setup):
        client.force_login(notify_setup["tech1"])
        url = reverse("tickets:tech_api_push_subscribe")
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/device_same",
            "keys": {"p256dh": "key_old", "auth": "auth_old"},
        }
        client.post(url, data=json.dumps(payload), content_type="application/json")
        assert WebPushSubscription.objects.count() == 1

        # Повторная регистрация с обновлёнными ключами
        payload["keys"]["p256dh"] = "key_new"
        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 200
        assert WebPushSubscription.objects.count() == 1
        sub = WebPushSubscription.objects.get(endpoint=payload["endpoint"])
        assert sub.p256dh == "key_new"

    def test_multiple_devices_for_single_user(self, client, notify_setup):
        client.force_login(notify_setup["tech1"])
        url = reverse("tickets:tech_api_push_subscribe")

        for i in (1, 2):
            payload = {
                "endpoint": f"https://fcm.googleapis.com/fcm/send/device_{i}",
                "keys": {"p256dh": f"p256_{i}", "auth": f"auth_{i}"},
            }
            client.post(url, data=json.dumps(payload), content_type="application/json")

        assert WebPushSubscription.objects.filter(user=notify_setup["tech1"]).count() == 2

    def test_subscribe_missing_keys_returns_400(self, client, notify_setup):
        client.force_login(notify_setup["tech1"])
        url = reverse("tickets:tech_api_push_subscribe")
        response = client.post(
            url,
            data=json.dumps({"endpoint": "https://push.example.com/sub/only"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_unsubscribe_removes_subscription(self, client, notify_setup):
        sub = WebPushSubscription.objects.create(
            user=notify_setup["tech1"],
            endpoint="https://fcm.googleapis.com/fcm/send/to_delete",
            p256dh="key",
            auth="auth",
        )
        client.force_login(notify_setup["tech1"])
        url = reverse("tickets:tech_api_push_unsubscribe")
        response = client.post(
            url,
            data=json.dumps({"endpoint": sub.endpoint}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "unsubscribed"
        assert not WebPushSubscription.objects.filter(id=sub.id).exists()


# ==============================================================
# 4. Тесты триггеров: создание заявки vs редактирование
# ==============================================================

@pytest.mark.django_db
class TestPushTriggersAndDedup:
    def test_create_public_ticket_triggers_push_on_commit(self, notify_setup):
        with patch("apps.tickets.push_service.notify_technicians_new_ticket") as mock_notify:
            with TestCase.captureOnCommitCallbacks(execute=True):
                ticket = create_public_ticket(
                    employee_name="Иванов И.И.",
                    location=notify_setup["room101"],
                    custom_location="",
                    short_description="Не работает клавиатура",
                    detailed_description="Залита чаем",
                    items_data=[{"category": notify_setup["cat_pc"], "quantity": 1}],
                )
            assert mock_notify.called
            args, _ = mock_notify.call_args
            assert args[0].id == ticket.id

    def test_ticket_updates_do_not_trigger_new_ticket_push(self, notify_setup):
        ticket = create_public_ticket(
            employee_name="Иванов И.И.",
            location=notify_setup["room101"],
            custom_location="",
            short_description="Не работает клавиатура",
            detailed_description="",
            items_data=[{"category": notify_setup["cat_pc"], "quantity": 1}],
        )

        with patch("apps.tickets.push_service.notify_technicians_new_ticket") as mock_notify:
            with TestCase.captureOnCommitCallbacks(execute=True):
                # 1. Взятие в работу
                claim_ticket(ticket_number=ticket.ticket_number, tech_user=notify_setup["tech1"])
                assert not mock_notify.called

                # 2. Добавление комментария
                add_ticket_comment(ticket_number=ticket.ticket_number, author=notify_setup["tech1"], body="Диагностика")
                assert not mock_notify.called

                # 3. Смена статуса (при WAITING требуется comment_text)
                update_ticket_status(
                    ticket_number=ticket.ticket_number,
                    actor=notify_setup["tech1"],
                    new_status=Ticket.Status.WAITING,
                    comment_text="Ожидание комплектующих со склада",
                )
                assert not mock_notify.called

                # 4. Возврат в очередь
                return_ticket_to_queue(
                    ticket_number=ticket.ticket_number,
                    actor=notify_setup["tech1"],
                    reason="Нужна замена комплектующих",
                )
                assert not mock_notify.called



# ==============================================================
# 5. Тесты безопасности, PII и автоматической очистки подписок
# ==============================================================

@pytest.mark.django_db
class TestPushSecurityAndCleanup:
    def test_push_payload_strictly_excludes_pii(self, notify_setup, settings):
        settings.PUSH_VAPID_PRIVATE_KEY = "dummy-private-key"

        WebPushSubscription.objects.create(
            user=notify_setup["tech1"],
            endpoint="https://fcm.googleapis.com/fcm/send/secret-device",
            p256dh="p256",
            auth="auth",
        )

        ticket = Ticket.objects.create(
            ticket_number="HELP-999999",
            employee_name="Секретный Сотрудник 123",
            location=notify_setup["room101"],
            custom_location="Секретный кабинет 999",
            short_description="Очень секретная поломка сервера бухгалтерии",
            detailed_description="Пароль от сейфа 12345",
            status=Ticket.Status.NEW,
        )

        sent_payloads = []

        def fake_send(sub, payload):
            sent_payloads.append(payload)
            return True

        with patch("apps.tickets.push_service.send_web_push", side_effect=fake_send):
            notify_technicians_new_ticket(ticket)

        assert len(sent_payloads) == 1
        payload = sent_payloads[0]

        # Проверяем стандартное generic содержимое
        assert payload["title"] == "Help Desk: Новая заявка"
        assert payload["body"] == "Поступила новая заявка в очередь"
        assert payload["url"] == "/tech/queue/"
        assert payload["tag"] == f"ticket-{ticket.id}"

        # Проверяем КАТЕГОРИЧЕСКОЕ отсутствие PII
        payload_str = json.dumps(payload, ensure_ascii=False)
        assert "Секретный Сотрудник" not in payload_str
        assert "Секретный кабинет" not in payload_str
        assert "поломка сервера" not in payload_str
        assert "12345" not in payload_str

    def test_missing_vapid_keys_safe_degradation(self, notify_setup, settings):
        settings.PUSH_VAPID_PRIVATE_KEY = ""
        ticket = Ticket.objects.create(
            ticket_number="HELP-888888",
            employee_name="Тест",
            short_description="Тест",
            status=Ticket.Status.NEW,
        )
        # При отсутствии ключа функция возвращает 0 и не вызывает исключений
        sent = notify_technicians_new_ticket(ticket)
        assert sent == 0

    def test_expired_subscription_deleted_on_410_gone(self, notify_setup, settings):
        settings.PUSH_VAPID_PRIVATE_KEY = "dummy-private-key"
        sub = WebPushSubscription.objects.create(
            user=notify_setup["tech1"],
            endpoint="https://fcm.googleapis.com/fcm/send/expired-device",
            p256dh="p256",
            auth="auth",
        )

        class FakeWebPushException(Exception):
            def __init__(self, status_code):
                self.response = MagicMock(status_code=status_code)

        with patch("apps.tickets.push_service.webpush", side_effect=FakeWebPushException(410)):
            with patch("apps.tickets.push_service.WebPushException", FakeWebPushException):
                result = send_web_push(sub, {"title": "Test", "body": "Test"})
                assert result is False

        # Подписка должна быть автоматически удалена
        assert not WebPushSubscription.objects.filter(id=sub.id).exists()

    def test_temporary_error_500_does_not_delete_subscription(self, notify_setup, settings):
        settings.PUSH_VAPID_PRIVATE_KEY = "dummy-private-key"
        sub = WebPushSubscription.objects.create(
            user=notify_setup["tech1"],
            endpoint="https://fcm.googleapis.com/fcm/send/temp-err-device",
            p256dh="p256",
            auth="auth",
        )

        class FakeWebPushException(Exception):
            def __init__(self, status_code):
                self.response = MagicMock(status_code=status_code)

        with patch("apps.tickets.push_service.webpush", side_effect=FakeWebPushException(500)):
            with patch("apps.tickets.push_service.WebPushException", FakeWebPushException):
                result = send_web_push(sub, {"title": "Test", "body": "Test"})
                assert result is False

        # Подписка НЕ должна удаляться при временных сбоях сервера
        assert WebPushSubscription.objects.filter(id=sub.id).exists()

    def test_recipient_distribution_logic(self, notify_setup):
        unassigned_ticket = Ticket.objects.create(
            ticket_number="HELP-111111",
            employee_name="Тест",
            short_description="Свободная",
            status=Ticket.Status.NEW,
        )
        recipients = list(get_recipients_for_ticket(unassigned_ticket))
        assert notify_setup["tech1"] in recipients
        assert notify_setup["tech2"] in recipients
        assert notify_setup["admin"] in recipients
        assert notify_setup["regular_user"] not in recipients

        assigned_ticket = Ticket.objects.create(
            ticket_number="HELP-222222",
            employee_name="Тест",
            short_description="Назначенная",
            status=Ticket.Status.IN_PROGRESS,
            assigned_to=notify_setup["tech1"],
        )
        assigned_recipients = list(get_recipients_for_ticket(assigned_ticket))
        assert notify_setup["tech1"] in assigned_recipients
        assert notify_setup["admin"] in assigned_recipients
        assert notify_setup["tech2"] not in assigned_recipients
