"""Инициализация конфигурации проекта Helpes и патч совместимости Django 5.1 с Python 3.14."""


def _patch_django_context_copy_for_py314() -> None:
    """Устраняет AttributeError: 'super' object has no attribute 'dicts' в django.test.Client на Python 3.14."""
    try:
        from django.template.context import BaseContext
    except ImportError:
        return

    def _py314_base_context_copy(self):
        duplicate = BaseContext.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = _py314_base_context_copy


_patch_django_context_copy_for_py314()
