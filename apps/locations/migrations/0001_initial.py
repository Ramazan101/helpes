import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Building",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Название здания / корпуса")),
                ("sort_order", models.PositiveIntegerField(default=10, verbose_name="Порядок сортировки")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Активно")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Здание",
                "verbose_name_plural": "Здания",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Floor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="Название этажа")),
                ("sort_order", models.IntegerField(default=1, verbose_name="Порядок сортировки")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Активен")),
                ("building", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="floors",
                    to="locations.building",
                    verbose_name="Здание (необязательно)",
                )),
            ],
            options={
                "verbose_name": "Этаж",
                "verbose_name_plural": "Этажи",
                "ordering": ["building__sort_order", "sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Location",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, verbose_name="Кабинет / Помещение")),
                ("sort_order", models.PositiveIntegerField(default=10, verbose_name="Порядок сортировки")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Доступен для выбора")),
                ("floor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="locations",
                    to="locations.floor",
                    verbose_name="Этаж",
                )),
            ],
            options={
                "verbose_name": "Кабинет / Местоположение",
                "verbose_name_plural": "Кабинеты и местоположения",
                "ordering": ["floor__building__sort_order", "floor__sort_order", "sort_order", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="floor",
            constraint=models.UniqueConstraint(fields=("building", "name"), name="unique_floor_per_building"),
        ),
        migrations.AddConstraint(
            model_name="location",
            constraint=models.UniqueConstraint(fields=("floor", "name"), name="unique_location_per_floor"),
        ),
    ]
