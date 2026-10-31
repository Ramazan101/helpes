/**
 * Help Desk «Кыргыз Алтын» — Управление уведомлениями очереди и Web Push.
 * 
 * Возможности:
 * 1. In-App Polling: периодический опрос GET /tech/api/queue/summary/ (каждые 35 секунд).
 * 2. Межвкладочная дедупликация: синхронизация через localStorage и BroadcastChannel.
 * 3. Динамическое обновление счётчиков очереди в DOM без перезагрузки.
 * 4. Управление Web Push: кнопка «Включить/Отключить уведомления» с запросом разрешения только по клику.
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'hd_last_notified_ticket_id';
  const POLL_INTERVAL_MS = 35000;
  const CHANNEL_NAME = 'hd_queue_notifications';

  let broadcastChannel = null;
  if ('BroadcastChannel' in window) {
    try {
      broadcastChannel = new BroadcastChannel(CHANNEL_NAME);
    } catch (e) {
      console.debug('BroadcastChannel not available:', e);
    }
  }

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function getLastNotifiedId() {
    const val = localStorage.getItem(STORAGE_KEY);
    return val ? parseInt(val, 10) : 0;
  }

  function setLastNotifiedId(id) {
    localStorage.setItem(STORAGE_KEY, String(id));
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function updateDomCounts(data) {
    if (!data) return;
    const unassignedEl = document.getElementById('count-unassigned');
    if (unassignedEl && typeof data.unassigned === 'number') {
      unassignedEl.textContent = data.unassigned;
    }
    const mineEl = document.getElementById('count-mine');
    if (mineEl && typeof data.mine === 'number') {
      mineEl.textContent = data.mine;
    }
    const allOpenEl = document.getElementById('count-all-open');
    if (allOpenEl && typeof data.all_open === 'number') {
      allOpenEl.textContent = data.all_open;
    }
  }

  function triggerInAppNotification(data) {
    const lastId = getLastNotifiedId();
    const newId = data.latest_ticket_id || 0;

    // Обновляем счётчики в DOM в любом случае
    updateDomCounts(data);

    // Если это первая инициализация на клиенте — просто запоминаем текущий ID
    if (lastId === 0) {
      if (newId > 0) setLastNotifiedId(newId);
      return;
    }

    // Если появилась действительно новая заявка и мы её ещё не нотифицировали
    if (newId > lastId) {
      setLastNotifiedId(newId);

      // Оповещаем другие открытые вкладки, чтобы они не дублировали системное уведомление
      if (broadcastChannel) {
        broadcastChannel.postMessage({
          type: 'ticket_notified',
          ticket_id: newId,
          data: data,
        });
      }

      // Показываем браузерное уведомление, если есть разрешение
      if ('Notification' in window && Notification.permission === 'granted') {
        try {
          new Notification('Help Desk: Новая заявка', {
            body: 'Поступила новая заявка в очередь',
            icon: '/static/icons/icon-192.png',
            tag: 'ticket-' + newId,
          });
        } catch (e) {
          console.debug('Notification error:', e);
        }
      }
    }
  }

  // Слушаем события от других вкладок через BroadcastChannel
  if (broadcastChannel) {
    broadcastChannel.onmessage = function (event) {
      if (event.data && event.data.type === 'ticket_notified') {
        const id = event.data.ticket_id;
        if (id > getLastNotifiedId()) {
          setLastNotifiedId(id);
        }
        if (event.data.data) {
          updateDomCounts(event.data.data);
        }
      }
    };
  }

  // Слушаем изменения localStorage от других окон
  window.addEventListener('storage', function (e) {
    if (e.key === STORAGE_KEY && e.newValue) {
      const newId = parseInt(e.newValue, 10);
      if (newId > 0) {
        // Синхронизируем счётчик без повторного показа уведомления
      }
    }
  });

  // Периодический опрос очереди (In-App Polling)
  function pollQueueSummary() {
    fetch('/tech/api/queue/summary/', {
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      cache: 'no-store',
    })
      .then((res) => {
        if (!res.ok) {
          if (res.status === 401 || res.status === 403) {
            // Сессия истекла или нет прав
            return null;
          }
          throw new Error('HTTP ' + res.status);
        }
        return res.json();
      })
      .then((data) => {
        if (data) {
          triggerInAppNotification(data);
        }
      })
      .catch((err) => {
        console.debug('Queue summary poll error:', err);
      });
  }

  // ===============================================
  // Управление кнопкой «Включить / Отключить уведомления»
  // ===============================================

  function setupPushButton() {
    const btn = document.getElementById('pwa-push-toggle-btn');
    const statusText = document.getElementById('pwa-push-status-text');
    const statusIcon = document.getElementById('pwa-push-status-icon');

    if (!btn) return;

    // Проверяем поддержку Service Worker и PushManager
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      btn.style.display = 'none';
      return;
    }

    btn.style.display = 'inline-flex';

    function setBtnState(isEnabled, isPending) {
      btn.disabled = !!isPending;
      if (isPending) {
        if (statusText) statusText.textContent = 'Обработка...';
        return;
      }
      if (isEnabled) {
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-outline-success');
        if (statusIcon) statusIcon.textContent = '🔕';
        if (statusText) statusText.textContent = 'Уведомления: Вкл';
        btn.setAttribute('title', 'Нажмите, чтобы отключить уведомления');
      } else {
        btn.classList.remove('btn-outline-success');
        btn.classList.add('btn-outline-primary');
        if (statusIcon) statusIcon.textContent = '🔔';
        if (statusText) statusText.textContent = 'Включить уведомления';
        btn.setAttribute('title', 'Включить браузерные уведомления о новых заявках');
      }
    }

    async function checkCurrentSubscription() {
      try {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        const isGranted = Notification.permission === 'granted';
        setBtnState(Boolean(sub && isGranted), false);
      } catch (e) {
        console.debug('Error checking push subscription:', e);
        setBtnState(false, false);
      }
    }

    async function handleToggleClick() {
      try {
        const reg = await navigator.serviceWorker.ready;
        const currentSub = await reg.pushManager.getSubscription();

        if (currentSub && Notification.permission === 'granted') {
          // Отключение подписки
          setBtnState(true, true);
          await currentSub.unsubscribe();
          await fetch('/tech/api/push/unsubscribe/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCsrfToken(),
              'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ endpoint: currentSub.endpoint }),
          });
          setBtnState(false, false);
        } else {
          // Включение подписки
          setBtnState(false, true);

          // Запрос разрешения строго по клику
          const perm = await Notification.requestPermission();
          if (perm !== 'granted') {
            alert('Разрешение на отправку уведомлений не предоставлено в настройках браузера.');
            setBtnState(false, false);
            return;
          }

          // Получаем VAPID публичный ключ
          const vapidRes = await fetch('/tech/api/push/vapid-key/', {
            headers: {
              'Accept': 'application/json',
              'X-Requested-With': 'XMLHttpRequest',
            },
            cache: 'no-store',
          });

          if (!vapidRes.ok) {
            throw new Error('Не удалось получить ключ сервера');
          }

          const vapidData = await vapidRes.json();
          if (!vapidData.public_key) {
            alert('Push-сервер не сконфигурирован на стороне сервера (отсутствует VAPID ключ). Включены только внутренние уведомления страницы.');
            setBtnState(false, false);
            return;
          }

          const appServerKey = urlBase64ToUint8Array(vapidData.public_key);
          const newSub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: appServerKey,
          });

          const subJson = newSub.toJSON();
          const subscribeRes = await fetch('/tech/api/push/subscribe/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCsrfToken(),
              'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({
              endpoint: newSub.endpoint,
              keys: subJson.keys,
            }),
          });

          if (!subscribeRes.ok) {
            throw new Error('Ошибка регистрации подписки на сервере');
          }

          setBtnState(true, false);
        }
      } catch (err) {
        console.error('Push toggle error:', err);
        alert('Не удалось изменить состояние уведомлений: ' + err.message);
        checkCurrentSubscription();
      }
    }

    btn.addEventListener('click', handleToggleClick);
    checkCurrentSubscription();
  }

  // Инициализация при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    setupPushButton();
    // Первый опрос сразу для инициализации
    pollQueueSummary();
    // Запуск регулярного таймера
    setInterval(pollQueueSummary, POLL_INTERVAL_MS);
  }
})();
