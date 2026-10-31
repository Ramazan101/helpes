#!/usr/bin/env bash
# ==============================================================================
# Скрипт автоматического резервного копирования базы данных PostgreSQL (Docker)
# Help Desk «Кыргыз Алтын»
# ==============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/helpes}"
DAYS_TO_KEEP="${DAYS_TO_KEEP:-14}"
DATE_STR="$(date +%Y%m%d_%H%M%S)"
COMPOSE_FILE="${COMPOSE_FILE:-/home/ubuntu/helpes/docker-compose.yml}"
DB_CONTAINER="db"
DB_NAME="${DB_NAME:-helpes_db}"
DB_USER="${DB_USER:-helpes_user}"

mkdir -p "${BACKUP_DIR}"

BACKUP_FILE="${BACKUP_DIR}/helpes_db_${DATE_STR}.sql.gz"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Создание резервной копии базы данных ${DB_NAME}..."

# Выполняем pg_dump внутри контейнера db без публикации порта наружу
docker compose -f "${COMPOSE_FILE}" exec -T "${DB_CONTAINER}" \
  pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists | gzip > "${BACKUP_FILE}"

# Проверяем, что файл создан и не пуст
if [ -s "${BACKUP_FILE}" ]; then
  FILE_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Резервная копия успешно создана: ${BACKUP_FILE} (${FILE_SIZE})"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ОШИБКА: Файл резервной копии пуст!" >&2
  exit 1
fi

# Ротация: удаление резервных копий старше DAYS_TO_KEEP дней
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Очистка резервных копий старше ${DAYS_TO_KEEP} дней..."
find "${BACKUP_DIR}" -type f -name "helpes_db_*.sql.gz" -mtime +"${DAYS_TO_KEEP}" -delete

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Резервное копирование завершено успешно."
