# Help Desk — развёртывание на AWS EC2

## Перед запуском

- Используйте существующий GitHub-репозиторий; не удаляйте `.git` и не создавайте новый репозиторий.
- В AWS Security Group разрешите SSH (22) только с вашего IP и HTTP (80) для первоначальной проверки. Добавьте HTTPS (443), когда настроите TLS.
- Не открывайте PostgreSQL (5432) для интернета: Compose не публикует этот порт.

## На EC2 (Ubuntu)

1. Установите Docker Engine и Compose Plugin по официальной инструкции Docker для Ubuntu.
2. Клонируйте существующий репозиторий и перейдите в папку проекта:

   ```bash
   git clone https://github.com/Ramazan101/helpes.git
   cd helpes
   cp .env.example .env
   ```

3. Сгенерируйте секрет и отредактируйте `.env`:

   ```bash
   python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
   nano .env
   ```

   Установите `DJANGO_DEBUG=False`, новый `DJANGO_SECRET_KEY`, надёжный уникальный `DB_PASSWORD`, а `DJANGO_ALLOWED_HOSTS` и `DJANGO_CSRF_TRUSTED_ORIGINS` настройте под публичный IP или домен. Убедитесь, что `DB_ENGINE=postgresql`, а `DB_HOST=db`.

4. Запустите и проверьте приложение:

   ```bash
   docker compose config
   docker compose up -d --build
   docker compose ps
   docker compose logs --tail=100 web
   curl -I http://localhost/
   docker compose exec web python manage.py createsuperuser
   ```

5. Для production обязательно настройте HTTPS (например, домен + Let's Encrypt/Nginx или TLS через AWS Application Load Balancer). После настройки HTTPS укажите `https://ваш-домен` в `DJANGO_CSRF_TRUSTED_ORIGINS` и установите `DJANGO_SECURE_COOKIES=True`, затем примените настройки:

   ```bash
   docker compose up -d --build
   ```

> Важно: HTTP подходит только для первичной проверки. Не вводите реальные учётные данные и не используйте систему с рабочими заявками до настройки HTTPS.
