"""Модели зданий, этажей и кабинетов с поддержкой архивации (is_active)."""
from django.db import models


class Building(models.Model):
    name = models.CharField("Название здания / корпуса", max_length=120, unique=True)
    sort_order = models.PositiveIntegerField("Порядок сортировки", default=10)
    is_active = models.BooleanField("Активно", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Здание"
        verbose_name_plural = "Здания"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Floor(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="floors",
        verbose_name="Здание (необязательно)",
    )
    name = models.CharField("Название этажа", max_length=100)
    sort_order = models.IntegerField("Порядок сортировки", default=1)
    is_active = models.BooleanField("Активен", default=True, db_index=True)

    class Meta:
        verbose_name = "Этаж"
        verbose_name_plural = "Этажи"
        ordering = ["building__sort_order", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["building", "name"], name="unique_floor_per_building"),
        ]

    @property
    def full_name(self) -> str:
        if self.building_id:
            return f"{self.building.name} — {self.name}"
        return self.name

    def __str__(self) -> str:
        return self.full_name


class Location(models.Model):
    floor = models.ForeignKey(
        Floor,
        on_delete=models.PROTECT,
        related_name="locations",
        verbose_name="Этаж",
    )
    name = models.CharField("Кабинет / Помещение", max_length=120)
    sort_order = models.PositiveIntegerField("Порядок сортировки", default=10)
    is_active = models.BooleanField("Доступен для выбора", default=True, db_index=True)

    class Meta:
        verbose_name = "Кабинет / Местоположение"
        verbose_name_plural = "Кабинеты и местоположения"
        ordering = ["floor__building__sort_order", "floor__sort_order", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["floor", "name"], name="unique_location_per_floor"),
        ]

    @property
    def full_title(self) -> str:
        if self.floor_id:
            return f"{self.floor.full_name} — {self.name}"
        return self.name

    def __str__(self) -> str:
        return self.full_title
