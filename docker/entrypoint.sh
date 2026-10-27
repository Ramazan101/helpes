#!/bin/sh
set -eu

if [ "${DB_ENGINE:-sqlite}" = "postgresql" ] || [ "${DB_ENGINE:-sqlite}" = "postgres" ] || [ "${DB_ENGINE:-sqlite}" = "pgsql" ]; then
    echo "Ожидание PostgreSQL (${DB_HOST:-db}:${DB_PORT:-5432})..."
    until nc -z "${DB_HOST:-db}" "${DB_PORT:-5432}"; do
        sleep 1
    done
    echo "PostgreSQL доступен."
fi

python manage.py migrate --noinput
python manage.py seed_initial_data
python manage.py collectstatic --noinput
exec "$@"
