# Help Desk «Кыргыз Алтын» — Регламент развёртывания на AWS EC2 (Elastic IP 15.135.104.47)

Данное руководство описывает безопасный процесс боевого развёртывания системы Help Desk компании «Кыргыз Алтын» на виртуальном сервере **AWS EC2** по привязанному адресу **Elastic IPv4 (`15.135.104.47`)** с использованием **HTTPS** и официального доверенного сертификата **Let's Encrypt IP SAN Certificate** (без необходимости покупки доменного имени).

---

## 1. Параметры инфраструктуры AWS

- **Public Elastic IP:** `15.135.104.47` *(динамический адрес `3.107.100.221` освобождён)*
- **Instance ID:** `i-0fbbaec369c0e1c7c`
- **Private IP:** `172.31.34.209`
- **Region:** `ap-southeast-2` (Сидней)
- **Allocation ID:** `eipalloc-085be1aed57b641a3`
- **Association ID:** `eipassoc-00b244f83f4213188`

### Правила безопасности (Security Group)
Убедитесь в наличии входящих правил (Inbound Rules):

| Тип | Протокол | Диапазон портов | Источник (Source) | Назначение |
| :--- | :---: | :---: | :---: | :--- |
| **SSH** | TCP | `22` | `My IP` (ваш IP-адрес) | Защищённое управление сервером |
| **HTTP** | TCP | `80` | `0.0.0.0/0` (Любой) | ACME-челлендж Let's Encrypt + редирект на HTTPS |
| **HTTPS** | TCP | `443` | `0.0.0.0/0` (Любой) | Защищённый доступ сотрудников к Help Desk |

> [!CAUTION]
> Порты `8000` (Gunicorn) и `5432` (PostgreSQL) **ни в коем случае не должны быть открыты** в Security Group. Контейнеры взаимодействуют исключительно во внутренней изолированной сети Docker (`backend`).

---

## 2. Локальная подготовка и передача актуальной версии на сервер

Так как рабочая версия содержит незакоммиченные доработки (PWA, Web Push, AI-помощник, миграции `0002_webpushsubscription.py`, скрипты), передача осуществляется через проверенный архив с манифестом SHA256 (без использования устаревшего `git clone`).

### 2.1. Сборка архива на локальной машине
Выполните локально в корне проекта:
```bash
./scripts/package_release.sh
```
Скрипт выполнит:
1. Упаковку всех рабочих файлов в `helpes-deployment-latest.tar.gz`;
2. Строгий аудит: исключит `.env`, `db.sqlite3`, `.git`, `.venv`, кэши и приватные ключи;
3. Формирование манифеста контрольных сумм `release_manifest.sha256`.

### 2.2. Передача архива и манифеста по SCP на EC2
```bash
export HELPDESK_PUBLIC_IP="15.135.104.47"
scp -i /path/to/your-key.pem helpes-deployment-latest.tar.gz release_manifest.sha256 ubuntu@${HELPDESK_PUBLIC_IP}:/home/ubuntu/
```

---

## 3. Подключение и подготовка сервера EC2 (Ubuntu 22.04 / 24.04)

### 3.1. Подключение по SSH
```bash
export HELPDESK_PUBLIC_IP="15.135.104.47"
ssh -i /path/to/your-key.pem ubuntu@${HELPDESK_PUBLIC_IP}
```

### 3.2. Распаковка проекта и проверка целостности SHA256
```bash
mkdir -p /home/ubuntu/helpes
tar -xzf /home/ubuntu/helpes-deployment-latest.tar.gz -C /home/ubuntu/helpes
cd /home/ubuntu/helpes

# Сверка контрольных сумм всех переданных файлов:
sha256sum -c /home/ubuntu/release_manifest.sha256
```
*(Все файлы должны получить статус `OK`)*.

### 3.3. Настройка Swapfile (Рекомендация для t3.small / 2 GB RAM)
Для предотвращения срабатывания OOM-killer при сборке Docker-образов рекомендуется активировать 2 GB файла подкачки:
```bash
if [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
free -h
```

### 3.4. Установка Docker Engine и Compose Plugin
Если Docker ещё не установлен на сервере:
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker ubuntu
newgrp docker
```

### 3.5. Установка Certbot (v5.4+ через snap)
```bash
sudo snap install core && sudo snap refresh core
sudo snap install --classic certbot
sudo ln -sf /snap/bin/certbot /usr/bin/certbot
certbot --version  # Проверьте: версия должна быть >= 5.4
```

---

## 4. Конфигурация `.env` на сервере

Перейдите в директорию проекта и создайте боевой `.env`:
```bash
cd /home/ubuntu/helpes
cp .env.example .env
nano .env
```

Заполните боевые переменные:
```ini
# Генерация ключа: python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
DJANGO_SECRET_KEY=ВАШ_СГЕНЕРИРОВАННЫЙ_СЕКРЕТНЫЙ_КЛЮЧ

# Режим отладки строго выключен
DJANGO_DEBUG=False

# Публичный Elastic IP сервера
DJANGO_ALLOWED_HOSTS=15.135.104.47,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://15.135.104.47

# Передача кук строго по HTTPS
DJANGO_SECURE_COOKIES=True

# База данных PostgreSQL в Docker
DB_ENGINE=postgresql
DB_NAME=helpes_db
DB_USER=helpes_user
DB_PASSWORD=УКАЖИТЕ_НАДЁЖНЫЙ_СЛУЧАЙНЫЙ_ПАРОЛЬ_БД
DB_HOST=db
DB_PORT=5432

# Пути к сертификатам и вебруту на хосте (передаются в docker-compose)
CERTBOT_CONF_DIR=/etc/letsencrypt
CERTBOT_WWW_DIR=/var/www/certbot

# AI-помощник (OpenRouter API-ключ строго на сервере)
AI_ASSISTANT_ENABLED=True
AI_API_KEY=sk-or-v1-ВАШ_КЛЮЧ_OPENROUTER

# Web Push (VAPID)
PUSH_VAPID_PUBLIC_KEY=ВАШ_ПУБЛИЧНЫЙ_VAPID_КЛЮЧ
PUSH_VAPID_PRIVATE_KEY=ВАШ_ПРИВАТНЫЙ_VAPID_КЛЮЧ
PUSH_VAPID_CLAIMS_EMAIL=mailto:ryskulovramazan8@gmail.com
```

---

## 5. Двухэтапная процедура TLS (Чистый запуск без конфликтов в каталогах Certbot)

> [!IMPORTANT]
> Каталоги `/etc/letsencrypt/live/`, `/archive/` и `/renewal/` управляются исключительно утилитой Certbot. В них **не создаются** временные файлы вручную.

### Этап 5.1. Подготовка вебрута и старт Nginx в режиме Bootstrap HTTP (:80)
```bash
sudo mkdir -p /var/www/certbot/.well-known/acme-challenge
sudo chmod 755 /var/www/certbot

cd /home/ubuntu/helpes

# Запуск стека с Nginx только на HTTP :80
NGINX_CONF_FILE=./docker/nginx/bootstrap-http.conf docker compose up -d --build
docker compose ps
```
Проверьте доступность HTTP:
```bash
curl -I http://15.135.104.47/
```
*(Должен возвращаться ответ HTTP 200/302)*.

### Этап 5.2. Тестовый запрос (Let's Encrypt Staging)
Проверьте связность и прохождение `http-01` челленджа на тестовом сервере Let's Encrypt (сертификат изолируется под именем `helpes-ip-staging`):
```bash
sudo certbot certonly \
  --staging \
  --preferred-profile shortlived \
  --webroot \
  -w /var/www/certbot \
  --cert-name helpes-ip-staging \
  --ip-address 15.135.104.47 \
  --non-interactive \
  --agree-tos \
  -m ryskulovramazan8@gmail.com
```

Проверьте наличие расширения **Subject Alternative Name** с вашим IP в staging-сертификате:
```bash
sudo openssl x509 -in /etc/letsencrypt/live/helpes-ip-staging/fullchain.pem -text -noout | grep -A 2 "Subject Alternative Name"
```
*(В выводе должно присутствовать: `IP Address:15.135.104.47`)*.

> [!NOTE]
> Тестовый сертификат сохраняется в изолированном каталоге `/etc/letsencrypt/live/helpes-ip-staging/` и не затрагивает production-конфигурацию Nginx.

### Этап 5.3. Выпуск боевого сертификата (Production)
Запросите боевой сертификат под именем `helpes-ip`:
```bash
sudo certbot certonly \
  --preferred-profile shortlived \
  --webroot \
  -w /var/www/certbot \
  --cert-name helpes-ip \
  --ip-address 15.135.104.47 \
  --non-interactive \
  --agree-tos \
  -m ryskulovramazan8@gmail.com
```

Проверьте срок действия боевого сертификата (160 часов / ~6 дней) и IP SAN в production-каталоге:
```bash
sudo openssl x509 -in /etc/letsencrypt/live/helpes-ip/fullchain.pem -text -noout | grep -E "Not After|IP Address"
```

### Этап 5.4. Переключение Nginx на боевую HTTPS-конфигурацию
Nginx в production-режиме (`docker/nginx/default.conf`) ссылается **исключительно на боевой сертификат** `/etc/letsencrypt/live/helpes-ip/`.

Перезапустите Nginx без переменной `NGINX_CONF_FILE` — автоматически загрузится боевой `default.conf` с поддержкой HTTPS:
```bash
docker compose up -d nginx
```
Проверьте работу HTTPS:
```bash
curl -I https://15.135.104.47/
```

### Этап 5.5. Настройка хука автообновления Nginx для Snap Timer
Certbot, установленный через Snap, автоматически активирует системный таймер `snap.certbot.renew.timer`, запускающийся каждые 12 часов. Проверьте его статус:
```bash
systemctl list-timers | grep certbot
```
Чтобы при каждом успешном автоматическом продлении Nginx перечитывал сертификат без добавления лишних cron-задач, создайте официальный deploy-hook:
```bash
sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh > /dev/null << 'EOF'
#!/bin/sh
docker compose -f /home/ubuntu/helpes/docker-compose.yml exec -T nginx nginx -s reload
EOF

sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

Проверьте тестовый прогон обновления:
```bash
sudo certbot renew --dry-run
```

---

## 6. Безопасный перенос данных: SQLite → PostgreSQL

> [!IMPORTANT]
> Исходный файл `db.sqlite3` на локальной машине **ни в коем случае не удаляется и не изменяется**.
> Всегда выполняется резервное копирование PostgreSQL до и после импорта данных.

### Шаг 6.1. Резервная копия чистой базы PostgreSQL на сервере
Сделайте скрипт исполняемым и создайте базовую копию:
```bash
chmod +x /home/ubuntu/helpes/scripts/backup_db.sh
/home/ubuntu/helpes/scripts/backup_db.sh
```

### Шаг 6.2. Экспорт данных из SQLite (на локальной машине)
Выполните на вашем рабочем компьютере:
```bash
python manage.py dumpdata \
  --natural-foreign \
  --natural-primary \
  -e contenttypes \
  -e auth.Permission \
  --indent 2 > sqlite_data_export.json
```

Передайте дамп на сервер по SCP:
```bash
scp -i /path/to/your-key.pem sqlite_data_export.json ubuntu@15.135.104.47:/home/ubuntu/helpes/
```

### Шаг 6.3. Загрузка данных в PostgreSQL (на сервере)
```bash
cd /home/ubuntu/helpes

# Загрузка дампа в контейнер web
docker compose cp sqlite_data_export.json web:/app/sqlite_data_export.json
docker compose exec -T web python manage.py loaddata /app/sqlite_data_export.json
docker compose exec -T web rm -f /app/sqlite_data_export.json
rm -f /home/ubuntu/helpes/sqlite_data_export.json
```

### Шаг 6.4. Контроль количества записей и повторный бэкап
Проверьте количество перенесённых записей:
```bash
docker compose exec -T web python manage.py shell -c '
from apps.accounts.models import User
from apps.tickets.models import Ticket
from apps.locations.models import Location
print("Пользователей:", User.objects.count())
print("Локаций:", Location.objects.count())
print("Заявок:", Ticket.objects.count())
'
```
Создайте контрольную резервную копию после успешной миграции:
```bash
/home/ubuntu/helpes/scripts/backup_db.sh
```

### Шаг 6.5. Настройка ежедневного бэкапа в cron
Откройте `sudo crontab -e` и добавьте строку для бэкапа PostgreSQL в 02:00 ночи:
```cron
0 2 * * * /home/ubuntu/helpes/scripts/backup_db.sh >> /var/log/helpes_backup.log 2>&1
```

---

## 7. Проверка импортированных данных, суперпользователя и финальная верификация

### Шаг 7.1. Проверка наличия суперпользователя и импортированных данных
Перед ручным созданием суперпользователя проверьте, не перенесён ли он уже из SQLite-базы, и убедитесь в целостности данных:
```bash
docker compose exec -T web python manage.py shell -c '
from apps.accounts.models import User
from apps.tickets.models import Ticket

superusers = User.objects.filter(is_superuser=True)
if superusers.exists():
    print(f"Суперпользователь уже существует в импортированной базе: {[u.username for u in superusers]}")
    print("Создание нового суперпользователя через createsuperuser не требуется.")
else:
    print("Суперпользователи в базе отсутствуют. Выполните createsuperuser.")
print("Всего пользователей:", User.objects.count())
print("Всего заявок:", Ticket.objects.count())
'
```

### Шаг 7.2. Создание администратора (только при необходимости)
Если база разворачивается с нуля или среди импортированных пользователей нет администратора:
```bash
docker compose exec -it web python manage.py createsuperuser
```

### Шаг 7.3. Финальная проверка работоспособности сервиса
Откройте в браузере: `https://15.135.104.47/`
- **Замок:** зелёный замок, безопасное TLS-соединение без предупреждений (валидный Let's Encrypt IP SAN);
- **Редирект:** обращение по `http://15.135.104.47/` автоматически перенаправляет на `https://15.135.104.47/`;
- **PWA:** в DevTools (Application → Service Workers) статус Service Worker `sw.js` — `Activated and running`;
- **Web Push:** в интерфейсе техника (`/tech/queue/`) нажмите `🔔 Включить уведомления` — браузер должен запросить разрешение и зарегистрировать подписку;
- **AI-помощник:** отправьте тестовый запрос в чат — ответ поступает через серверный слой OpenRouter без раскрытия ключей.
