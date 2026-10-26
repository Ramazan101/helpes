#!/usr/bin/env python
"""Утилита командной строки Django для административных задач проекта Helpes."""
import os
import sys


def main():
    """Запуск административных задач."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Не удалось импортировать Django. Убедитесь, что Django установлен и "
            "доступен в переменной окружения PYTHONPATH, а виртуальное окружение активировано."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()