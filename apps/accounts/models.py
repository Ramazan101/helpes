"""Модель пользователей и ролей (Технический специалист и Администратор)."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        TECH = "TECH", "Технический специалист"
        ADMIN = "ADMIN", "Администратор"

    full_name = models.CharField("ФИО сотрудника", max_length=150, blank=True)
    role = models.CharField(
        "Роль в системе",
        max_length=10,
        choices=Role.choices,
        default=Role.TECH,
        db_index=True,
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["username"]

    @property
    def display_name(self) -> str:
        return self.full_name.strip() or self.get_full_name().strip() or self.username

    @property
    def is_admin_role(self) -> bool:
        return bool(self.is_active and (self.role == self.Role.ADMIN or self.is_superuser))

    @property
    def is_tech_role(self) -> bool:
        return bool(self.is_active and (self.role in (self.Role.TECH, self.Role.ADMIN) or self.is_superuser))

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_role_display()})"
