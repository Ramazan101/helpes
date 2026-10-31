"""Модели категорий оборудования, заявок, позиций, комментариев и истории."""
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.locations.models import Location


class EquipmentCategory(models.Model):
    name = models.CharField("Категория оборудования / неисправности", max_length=120, unique=True)
    description = models.CharField("Краткое пояснение", max_length=255, blank=True)
    sort_order = models.PositiveIntegerField("Порядок сортировки", default=10)
    is_active = models.BooleanField("Активна", default=True, db_index=True)

    class Meta:
        verbose_name = "Категория оборудования"
        verbose_name_plural = "Категории оборудования"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Ticket(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "Новая"
        IN_PROGRESS = "IN_PROGRESS", "В работе"
        WAITING = "WAITING", "Ожидает"
        DONE = "DONE", "Выполнена"

    ticket_number = models.CharField("Номер заявки", max_length=20, unique=True, db_index=True)
    employee_name = models.CharField("Имя сотрудника", max_length=150)
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
        verbose_name="Кабинет / Помещение",
    )
    custom_location = models.CharField(
        "Уточнение местоположения (если нет в списке)",
        max_length=255,
        blank=True,
    )
    short_description = models.CharField("Краткое описание неисправности", max_length=255)
    detailed_description = models.TextField("Подробное описание", blank=True)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        verbose_name="Назначенный специалист",
    )
    resolution_summary = models.TextField("Выполненные действия и результат ремонта", blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True, db_index=True)
    completed_at = models.DateTimeField("Завершена", null=True, blank=True)

    class Meta:
        verbose_name = "Техническая заявка"
        verbose_name_plural = "Технические заявки"
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if not self.location_id and not (self.custom_location and self.custom_location.strip()):
            raise ValidationError("Укажите кабинет из списка или введите местоположение вручную.")

    @property
    def location_display(self) -> str:
        parts = []
        if self.location_id:
            parts.append(self.location.full_title)
        if self.custom_location and self.custom_location.strip():
            parts.append(self.custom_location.strip())
        return " / ".join(parts) if parts else "Не указано"

    @property
    def total_equipment_count(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def is_stale(self) -> bool:
        if self.status == self.Status.DONE:
            return False
        hours = getattr(settings, "STALE_TICKET_HOURS", 24)
        return timezone.now() - self.updated_at > timedelta(hours=hours)

    def __str__(self) -> str:
        return f"{self.ticket_number} ({self.get_status_display()})"


class TicketItem(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заявка",
    )
    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.PROTECT,
        related_name="ticket_items",
        verbose_name="Оборудование / Категория",
    )
    quantity = models.PositiveIntegerField(
        "Количество устройств",
        default=1,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = "Позиция оборудования"
        verbose_name_plural = "Позиции оборудования"
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="ticket_item_quantity_gte_1"),
            models.UniqueConstraint(fields=["ticket", "category"], name="unique_category_per_ticket"),
        ]

    def __str__(self) -> str:
        return f"{self.category.name} — {self.quantity} шт."


class TicketComment(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Заявка",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_comments",
        verbose_name="Автор",
    )
    body = models.TextField("Комментарий / ход диагностики")
    created_at = models.DateTimeField("Дата и время", auto_now_add=True)

    class Meta:
        verbose_name = "Комментарий к заявке"
        verbose_name_plural = "Комментарии к заявкам"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Комментарий {self.author} к {self.ticket.ticket_number}"


class TicketHistory(models.Model):
    class Action(models.TextChoices):
        CREATED = "CREATED", "Заявка создана"
        CLAIMED = "CLAIMED", "Взята в работу специалистом"
        ASSIGNED = "ASSIGNED", "Назначен / изменён исполнитель"
        RETURNED_TO_QUEUE = "RETURNED_TO_QUEUE", "Возвращена в общую очередь"
        STATUS_CHANGED = "STATUS_CHANGED", "Изменён статус"
        COMPLETED = "COMPLETED", "Заявка выполнена"
        REOPENED = "REOPENED", "Повторно открыта администратором"
        COMMENT_ADDED = "COMMENT_ADDED", "Добавлен комментарий"

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="history",
        verbose_name="Заявка",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ticket_actions",
        verbose_name="Кто выполнил действие",
    )
    action = models.CharField("Действие", max_length=40, choices=Action.choices)
    old_status = models.CharField("Старый статус", max_length=20, blank=True)
    new_status = models.CharField("Новый статус", max_length=20, blank=True)
    old_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Прежний исполнитель",
    )
    new_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Новый исполнитель",
    )
    note = models.TextField("Подробности / примечание", blank=True)
    created_at = models.DateTimeField("Дата и время", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запись истории заявки"
        verbose_name_plural = "История заявок"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.ticket.ticket_number}: {self.get_action_display()}"


class WebPushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="web_push_subscriptions",
        verbose_name="Пользователь",
    )
    endpoint = models.URLField("Push Endpoint", max_length=1000, unique=True, db_index=True)
    p256dh = models.CharField("Ключ p256dh", max_length=255)
    auth = models.CharField("Ключ auth", max_length=255)
    user_agent = models.CharField("User-Agent устройства", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("Создана", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Подписка Web Push"
        verbose_name_plural = "Подписки Web Push"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PushSubscription({self.user.username}, {self.endpoint[:40]}...)"
