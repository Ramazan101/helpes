"""Сервис безопасной отправки Web Push уведомлений техническому персоналу."""
import json
import logging
from typing import Any

from django.conf import settings
from django.db.models import Q

from apps.accounts.models import User
from .models import Ticket, WebPushSubscription

logger = logging.getLogger(__name__)

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None
    WebPushException = Exception


def send_web_push(subscription: WebPushSubscription, payload: dict[str, Any]) -> bool:
    """
    Отправляет одно push-уведомление через RFC 8292.
    При получении HTTP 404 (Not Found) или HTTP 410 (Gone) удаляет недействительную подписку.
    Никогда не выводит endpoint или секретные ключи в логи.
    """
    if not webpush:
        logger.warning("pywebpush не установлен. Отправка Web Push пропущена.")
        return False

    vapid_private_key = getattr(settings, "PUSH_VAPID_PRIVATE_KEY", "")
    if not vapid_private_key:
        logger.info("PUSH_VAPID_PRIVATE_KEY не задан. Отправка Web Push пропущена.")
        return False

    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        },
    }

    claims = {
        "sub": getattr(settings, "PUSH_VAPID_CLAIMS_EMAIL", "mailto:admin@kyrgyzaltyn.kg")
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=vapid_private_key,
            vapid_claims=claims,
            timeout=10,
        )
        return True
    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code in (404, 410):
            logger.info("Подписка Web Push ID %s устарела (HTTP %s) и была удалена.", subscription.id, status_code)
            subscription.delete()
        else:
            logger.warning("Ошибка доставки Web Push для подписки ID %s: HTTP %s", subscription.id, status_code)
        return False
    except Exception as exc:
        logger.warning("Непредвиденная ошибка отправки Web Push для подписки ID %s: %s", subscription.id, type(exc).__name__)
        return False


def get_recipients_for_ticket(ticket: Ticket):
    """
    Определяет пользователей, которым разрешено получить уведомление по заявке:
    - если заявка не назначена: все активные техники и администраторы;
    - если заявка назначена: назначенный специалист и администраторы.
    """
    if ticket.assigned_to_id:
        return User.objects.filter(
            Q(id=ticket.assigned_to_id) | Q(role=User.Role.ADMIN) | Q(is_superuser=True),
            is_active=True,
        ).distinct()
    return User.objects.filter(
        Q(role__in=[User.Role.TECH, User.Role.ADMIN]) | Q(is_superuser=True),
        is_active=True,
    ).distinct()


def notify_technicians_new_ticket(ticket: Ticket) -> int:
    """
    Рассылает Web Push уведомления о новой заявке уполномоченным техническим специалистам.
    Строго исключает PII (имя сотрудника, кабинет, описание неисправности).
    Возвращает количество успешно отправленных уведомлений.
    """
    vapid_private_key = getattr(settings, "PUSH_VAPID_PRIVATE_KEY", "")
    if not vapid_private_key:
        logger.info("PUSH_VAPID_PRIVATE_KEY не задан. Push-уведомление о новой заявке пропущено.")
        return 0

    # Формируем обезличенный payload без персональных данных
    payload = {
        "title": "Help Desk: Новая заявка",
        "body": "Поступила новая заявка в очередь",
        "url": "/tech/queue/",
        "tag": f"ticket-{ticket.id}",
    }

    recipients = get_recipients_for_ticket(ticket)
    subscriptions = WebPushSubscription.objects.filter(user__in=recipients).select_related("user")

    sent_count = 0
    for sub in subscriptions:
        if send_web_push(sub, payload):
            sent_count += 1

    return sent_count
