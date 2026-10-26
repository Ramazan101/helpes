import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("locations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EquipmentCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Категория оборудования / неисправности")),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="Краткое пояснение")),
                ("sort_order", models.PositiveIntegerField(default=10, verbose_name="Порядок сортировки")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Активна")),
            ],
            options={
                "verbose_name": "Категория оборудования",
                "verbose_name_plural": "Категории оборудования",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Ticket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ticket_number", models.CharField(db_index=True, max_length=20, unique=True, verbose_name="Номер заявки")),
                ("employee_name", models.CharField(max_length=150, verbose_name="Имя сотрудника")),
                ("custom_location", models.CharField(blank=True, max_length=255, verbose_name="Уточнение местоположения (если нет в списке)")),
                ("short_description", models.CharField(max_length=255, verbose_name="Краткое описание неисправности")),
                ("detailed_description", models.TextField(blank=True, verbose_name="Подробное описание")),
                ("status", models.CharField(
                    choices=[("NEW", "Новая"), ("IN_PROGRESS", "В работе"), ("WAITING", "Ожидает"), ("DONE", "Выполнена")],
                    db_index=True,
                    default="NEW",
                    max_length=20,
                    verbose_name="Статус",
                )),
                ("resolution_summary", models.TextField(blank=True, verbose_name="Выполненные действия и результат ремонта")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Создана")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, verbose_name="Обновлена")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="Завершена")),
                ("assigned_to", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="assigned_tickets",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Назначенный специалист",
                )),
                ("location", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="tickets",
                    to="locations.location",
                    verbose_name="Кабинет / Помещение",
                )),
            ],
            options={
                "verbose_name": "Техническая заявка",
                "verbose_name_plural": "Технические заявки",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="TicketItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(
                    default=1,
                    validators=[django.core.validators.MinValueValidator(1)],
                    verbose_name="Количество устройств",
                )),
                ("category", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="ticket_items",
                    to="tickets.equipmentcategory",
                    verbose_name="Оборудование / Категория",
                )),
                ("ticket", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="items",
                    to="tickets.ticket",
                    verbose_name="Заявка",
                )),
            ],
            options={
                "verbose_name": "Позиция оборудования",
                "verbose_name_plural": "Позиции оборудования",
            },
        ),
        migrations.CreateModel(
            name="TicketComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField(verbose_name="Комментарий / ход диагностики")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата и время")),
                ("author", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="ticket_comments",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Автор",
                )),
                ("ticket", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="comments",
                    to="tickets.ticket",
                    verbose_name="Заявка",
                )),
            ],
            options={
                "verbose_name": "Комментарий к заявке",
                "verbose_name_plural": "Комментарии к заявкам",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="TicketHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(
                    choices=[
                        ("CREATED", "Заявка создана"),
                        ("CLAIMED", "Взята в работу специалистом"),
                        ("ASSIGNED", "Назначен / изменён исполнитель"),
                        ("RETURNED_TO_QUEUE", "Возвращена в общую очередь"),
                        ("STATUS_CHANGED", "Изменён статус"),
                        ("COMPLETED", "Заявка выполнена"),
                        ("REOPENED", "Повторно открыта администратором"),
                        ("COMMENT_ADDED", "Добавлен комментарий"),
                    ],
                    max_length=40,
                    verbose_name="Действие",
                )),
                ("old_status", models.CharField(blank=True, max_length=20, verbose_name="Старый статус")),
                ("new_status", models.CharField(blank=True, max_length=20, verbose_name="Новый статус")),
                ("note", models.TextField(blank=True, verbose_name="Подробности / примечание")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата и время")),
                ("actor", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="ticket_actions",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Кто выполнил действие",
                )),
                ("new_assignee", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Новый исполнитель",
                )),
                ("old_assignee", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Прежний исполнитель",
                )),
                ("ticket", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="history",
                    to="tickets.ticket",
                    verbose_name="Заявка",
                )),
            ],
            options={
                "verbose_name": "Запись истории заявки",
                "verbose_name_plural": "История заявок",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="ticketitem",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gte", 1)), name="ticket_item_quantity_gte_1"),
        ),
        migrations.AddConstraint(
            model_name="ticketitem",
            constraint=models.UniqueConstraint(fields=("ticket", "category"), name="unique_category_per_ticket"),
        ),
    ]
