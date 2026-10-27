"""Команда начального заполнения стандартных категорий оборудования Help Desk."""
from django.core.management.base import BaseCommand
from apps.tickets.models import EquipmentCategory

DEFAULT_CATEGORIES = [
    (10, "Компьютер или ноутбук", "Системный блок, моноблок, рабочий ноутбук"),
    (20, "Принтер", "Лазерный/струйный принтер или МФУ, замятие бумаги, картридж"),
    (30, "Сканер", "Планшетный или потоковый сканер"),
    (40, "Монитор и периферия", "Монитор, клавиатура, мышь, ИБП, кабели"),
    (50, "Интернет, Wi-Fi или локальная сеть", "Отсутствие доступа к сети, обрыв кабеля, сетевые папки"),
    (60, "Программное обеспечение", "Операционная система, офисные и корпоративные программы"),
    (70, "Другое", "Прочее оборудование и технические вопросы"),
]


class Command(BaseCommand):
    help = "Заполняет базу данных начальным списком категорий оборудования Help Desk"

    def handle(self, *args, **options):
        created_count = 0
        for order, name, desc in DEFAULT_CATEGORIES:
            _, created = EquipmentCategory.objects.get_or_create(
                name=name,
                defaults={"sort_order": order, "description": desc, "is_active": True},
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f"Готово. Создано новых категорий: {created_count}."))
