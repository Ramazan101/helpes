#!/usr/bin/env bash
# ==============================================================================
# Скрипт сборки безопасного deployment-пакета актуальной версии Help Desk
# Включает все modified и untracked файлы текущей рабочей ветки.
# Строго исключает секреты, .env, SQLite, .git, .venv, кэши и артефакты сборки.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
ARCHIVE_NAME="helpes-deployment-latest.tar.gz"
MANIFEST_NAME="release_manifest.sha256"
TARGET_ARCHIVE="${PROJECT_ROOT}/${ARCHIVE_NAME}"
TARGET_MANIFEST="${PROJECT_ROOT}/${MANIFEST_NAME}"

cd "${PROJECT_ROOT}"

echo "======================================================================"
echo "Сборка пакета развёртывания Help Desk «Кыргыз Алтын»"
echo "======================================================================"

# 1. Удаление предыдущих временных файлов сборки
rm -f "${TARGET_ARCHIVE}" "${TARGET_MANIFEST}"

# 2. Формирование списка исключений
EXCLUDES=(
  --exclude='.env'
  --exclude='.env.*'
  --exclude='*.sqlite3'
  --exclude='*.sqlite3-journal'
  --exclude='db.sqlite3'
  --exclude='db.sqlite3-journal'
  --exclude='*.backup*'
  --exclude='.git'
  --exclude='.gitignore'
  --exclude='.venv'
  --exclude='env'
  --exclude='venv'
  --exclude='__pycache__'
  --exclude='*.pyc'
  --exclude='*.pyo'
  --exclude='.pytest_cache'
  --exclude='.coverage'
  --exclude='htmlcov'
  --exclude='node_modules'
  --exclude='desktop/tauri-widget/src-tauri/target'
  --exclude='desktop/tauri-widget/node_modules'
  --exclude='*.pem'
  --exclude='*.key'
  --exclude='docker/ssl/live'
  --exclude='docker/certbot/.well-known'
  --exclude="${ARCHIVE_NAME}"
  --exclude="${MANIFEST_NAME}"
  --exclude='*.tar.gz'
  --exclude='sqlite_data_export.json'
)

echo "[1/4] Архивация рабочей версии проекта..."
tar "${EXCLUDES[@]}" -czf "${TARGET_ARCHIVE}" .

# 3. Аудит содержимого архива на отсутствие секретов
echo "[2/4] Проверка архива на отсутствие конфиденциальных данных..."
FORBIDDEN_FILES=$(tar -ztf "${TARGET_ARCHIVE}" | grep -E "(^|/)(\.env|db\.sqlite3|\.git|\.venv|.*\.pem|.*\.key|__pycache__|target/)($|/)" || true)

if [ -n "${FORBIDDEN_FILES}" ]; then
  echo "КРИТИЧЕСКАЯ ОШИБКА: Архив содержит запрещённые файлы:" >&2
  echo "${FORBIDDEN_FILES}" >&2
  rm -f "${TARGET_ARCHIVE}"
  exit 1
fi
echo "      Проверка безопасности пройдена успешно (секреты и SQLite отсутствуют)."

# 4. Проверка наличия ключевых файлов в архиве
echo "[3/4] Проверка наличия критически важных компонентов..."
REQUIRED_ITEMS=(
  "apps/accounts/models.py"
  "apps/tickets/models.py"
  "apps/tickets/services.py"
  "apps/tickets/migrations/0002_webpushsubscription.py"
  "apps/assistant/services.py"
  "apps/assistant/views.py"
  "static/js/sw.js"
  "static/js/notifications.js"
  "static/manifest.json"
  "templates/assistant/widget_window.html"
  "docker/nginx/bootstrap-http.conf"
  "docker/nginx/default.conf"
  "docker-compose.yml"
  "requirements.txt"
)

TAR_CONTENTS=$(tar -ztf "${TARGET_ARCHIVE}")
for item in "${REQUIRED_ITEMS[@]}"; do
  # Проверяем наличие с префиксом ./ или без него
  if ! echo "${TAR_CONTENTS}" | grep -qE "(^|\./)${item}$"; then
    echo "ОШИБКА: В архиве отсутствует обязательный файл: ${item}" >&2
    rm -f "${TARGET_ARCHIVE}"
    exit 1
  fi
done
echo "      Все необходимые компоненты и миграции присутствуют в архиве."

# 5. Формирование манифеста контрольных сумм SHA256
echo "[4/4] Генерация манифеста SHA256..."
TMP_DIR=$(mktemp -d)
tar -xzf "${TARGET_ARCHIVE}" -C "${TMP_DIR}"

(
  cd "${TMP_DIR}"
  find . -type f | sort | while read -r file; do
    sha256sum "${file}"
  done
) > "${TARGET_MANIFEST}"
rm -rf "${TMP_DIR}"

ARCHIVE_SIZE=$(du -h "${TARGET_ARCHIVE}" | cut -f1)
ARCHIVE_SHA256=$(sha256sum "${TARGET_ARCHIVE}" | cut -d' ' -f1)
FILES_COUNT=$(wc -l < "${TARGET_MANIFEST}")

echo "======================================================================"
echo "Пакет развёртывания готов!"
echo "Файл архива:     ${ARCHIVE_NAME} (${ARCHIVE_SIZE})"
echo "SHA256 архива:   ${ARCHIVE_SHA256}"
echo "Файлов в пакете: ${FILES_COUNT}"
echo "Манифест:        ${MANIFEST_NAME}"
echo "======================================================================"
echo "Команда передачи на EC2 (Elastic IP 15.135.104.47):"
echo "  scp -i /path/to/your-key.pem ${ARCHIVE_NAME} ${MANIFEST_NAME} ubuntu@15.135.104.47:/home/ubuntu/"
echo "======================================================================"
