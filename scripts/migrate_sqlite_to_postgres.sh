#!/usr/bin/env bash
# ==============================================================================
# Скрипт безопасного переноса данных из SQLite в PostgreSQL
# Help Desk «Кыргыз Алтын»
# Исходный файл db.sqlite3 остаётся нетронутым!
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
DUMP_FILE="${PROJECT_DIR}/sqlite_data_export.json"

echo "=== Безопасный перенос данных: SQLite -> PostgreSQL ==="

# 1. Проверка наличия исходного файла SQLite
if [ ! -f "${PROJECT_DIR}/db.sqlite3" ]; then
  echo "ОШИБКА: Файл ${PROJECT_DIR}/db.sqlite3 не найден!" >&2
  exit 1
fi

echo "[1/3] Экспорт данных из SQLite (без contenttypes и permissions)..."
# Выгружаем данные через локальный Python/Django
python manage.py dumpdata \
  --natural-foreign \
  --natural-primary \
  -e contenttypes \
  -e auth.Permission \
  --indent 2 > "${DUMP_FILE}"

EXPORT_SIZE="$(du -h "${DUMP_FILE}" | cut -f1)"
echo "      Данные успешно выгружены в ${DUMP_FILE} (${EXPORT_SIZE})"

echo "[2/3] Проверка готовности контейнеров PostgreSQL..."
if ! docker compose ps web | grep -q "Up"; then
  echo "ВНИМАНИЕ: Контейнер web не запущен."
  echo "Для загрузки в PostgreSQL запустите контейнеры:"
  echo "  docker compose up -d"
  echo "Затем выполните импорт командой:"
  echo "  docker compose exec -T web python manage.py loaddata sqlite_data_export.json"
  exit 0
fi

echo "[3/3] Импорт данных в PostgreSQL..."
docker compose cp "${DUMP_FILE}" web:/app/sqlite_data_export.json
docker compose exec -T web python manage.py loaddata /app/sqlite_data_export.json
docker compose exec -T web rm -f /app/sqlite_data_export.json

echo "=== Перенос данных успешно завершён! Исходный db.sqlite3 сохранён. ==="
