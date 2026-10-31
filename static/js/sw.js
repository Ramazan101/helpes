/**
 * Service Worker для Help Desk «Кыргыз Алтын» (PWA Core).
 * 
 * Безопасность кэширования:
 * - Кэшируются ТОЛЬКО публичные статические файлы, иконки, манифест и оффлайн-страница fallback.
 * - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО кэшировать API, сессии, авторизацию (/accounts/*),
 *   заявки (/tech/*, /manage/*, /success/*) и персональные данные сотрудников.
 * - Запрещено сохранять ответы с заголовками "Cache-Control: private" или "no-store".
 * - Оффлайн fallback (/offline/) используется ТОЛЬКО для навигационных GET-запросов (HTML).
 */

const CACHE_NAME = 'helpes-static-v1';

const STATIC_PRECACHE_URLS = [
  '/offline/',
  '/manifest.json',
  '/static/css/styles.css',
  '/static/css/assistant.css',
  '/static/js/assistant.js',
  '/static/js/formset.js',
  '/static/js/notifications.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
];

// Паттерны URL, которые КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО перехватывать или кэшировать
const NEVER_CACHE_PATTERNS = [
  /\/api\//,
  /\/accounts\//,
  /\/tech\//,
  /\/manage\//,
  /\/django-admin\//,
  /\/success\//,
  /\/assistant\/api\//,
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_PRECACHE_URLS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 1. Игнорируем сторонние запросы и любые методы, кроме GET
  if (req.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  // 2. Навигационные запросы (переход по страницам / HTML)
  // Применяем строгую стратегию: Network Only, fallback на /offline/.
  // КАТЕГОРИЧЕСКИ НЕ КЭШИРУЕМ HTML-ответы, чтобы исключить отображение
  // данных предыдущего пользователя или устаревших заявок после выхода из системы.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => {
        return caches.match('/offline/').then((offlineResponse) => {
          return offlineResponse || new Response(
            '<h1>Связь с сервером отсутствует</h1><p>Проверьте подключение к сети.</p>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        });
      })
    );
    return;
  }

  // 3. Запретные URL (API, сессии, закрытые кабинеты) - только прямая сеть без перехвата
  const isNeverCache = NEVER_CACHE_PATTERNS.some((pattern) => pattern.test(url.pathname));
  if (isNeverCache) {
    return;
  }

  // 4. Статические ресурсы (/static/*, /manifest.json, /offline/)
  // Стратегия: Cache First, fallback to Network
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json' || url.pathname === '/offline/') {
    event.respondWith(
      caches.match(req).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(req).then((networkResponse) => {
          // Проверяем статус и заголовки кэширования
          const cacheControl = (networkResponse.headers.get('Cache-Control') || '').toLowerCase();
          const shouldCache = (
            networkResponse.status === 200 &&
            !cacheControl.includes('no-store') &&
            !cacheControl.includes('private')
          );
          if (shouldCache) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return networkResponse;
        });
      })
    );
  }
});

// ==========================================
// 5. Обработка Web Push уведомлений (Этап 2)
// ==========================================

self.addEventListener('push', (event) => {
  let data = {
    title: 'Help Desk: Новая заявка',
    body: 'Поступила новая заявка в очередь',
    url: '/tech/queue/',
    tag: 'ticket-new',
  };

  if (event.data) {
    try {
      const parsed = event.data.json();
      data = Object.assign(data, parsed);
    } catch (e) {
      // Игнорируем ошибки парсинга, используем безопасный generic payload
    }
  }

  const options = {
    body: data.body,
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    tag: data.tag || 'hd-ticket',
    data: {
      url: data.url || '/tech/queue/',
    },
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/tech/queue/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url && client.url.includes('/tech/') && 'focus' in client) {
          if ('navigate' in client) {
            client.navigate(targetUrl);
          }
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

