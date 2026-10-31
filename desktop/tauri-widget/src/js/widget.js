/**
 * Контроллер плавающего десктопного виджета Help Desk «Кыргыз Алтын».
 */
(function() {
  'use strict';

  const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';
  let backendUrl = DEFAULT_BACKEND_URL;
  let isAlwaysOnTop = true;

  const btnPin = document.getElementById('btn-pin');
  const btnMin = document.getElementById('btn-min');
  const btnClose = document.getElementById('btn-close');
  const contentFrame = document.getElementById('content-frame');
  const offlineView = document.getElementById('offline-view');
  const btnRetry = document.getElementById('btn-retry');

  // Проверяем доступность Tauri IPC
  const tauri = window.__TAURI__;

  async function initTauri() {
    if (tauri && tauri.core) {
      try {
        const info = await tauri.core.invoke('get_desktop_info');
        if (info && info.backend_url) {
          backendUrl = info.backend_url;
        }
        console.log('Tauri desktop info:', info);
      } catch (e) {
        console.debug('Could not get desktop info:', e);
      }
    }

    if (tauri && tauri.window) {
      const currentWin = tauri.window.getCurrentWindow();

      if (btnClose) {
        btnClose.addEventListener('click', () => {
          currentWin.hide().catch(console.error);
        });
      }

      if (btnMin) {
        btnMin.addEventListener('click', () => {
          currentWin.minimize().catch(console.error);
        });
      }

      if (btnPin) {
        btnPin.addEventListener('click', async () => {
          try {
            isAlwaysOnTop = !isAlwaysOnTop;
            await currentWin.setAlwaysOnTop(isAlwaysOnTop);
            if (isAlwaysOnTop) {
              btnPin.classList.add('pin-active');
              btnPin.setAttribute('title', 'Открепить (Always-on-top выключен)');
            } else {
              btnPin.classList.remove('pin-active');
              btnPin.setAttribute('title', 'Закрепить поверх всех окон (Always-on-top включен)');
            }
          } catch (err) {
            console.debug('Always-on-top toggle error:', err);
          }
        });
      }
    }

    loadWidgetContent();
  }

  function showOffline() {
    if (contentFrame) contentFrame.style.display = 'none';
    if (offlineView) offlineView.style.display = 'flex';
  }

  function showOnline() {
    if (offlineView) offlineView.style.display = 'none';
    if (contentFrame) contentFrame.style.display = 'block';
  }

  async function checkServerHealth() {
    try {
      const res = await fetch(`${backendUrl}/assistant/widget/`, {
        method: 'HEAD',
        cache: 'no-store',
      });
      return res.ok || res.status === 200 || res.status === 405;
    } catch (e) {
      return false;
    }
  }

  async function loadWidgetContent() {
    const isHealthy = await checkServerHealth();
    if (isHealthy) {
      showOnline();
      if (contentFrame && (!contentFrame.src || contentFrame.src === 'about:blank')) {
        contentFrame.src = `${backendUrl}/assistant/widget/`;
      }
    } else {
      showOffline();
    }
  }

  if (btnRetry) {
    btnRetry.addEventListener('click', async () => {
      btnRetry.textContent = 'Проверка связи...';
      btnRetry.disabled = true;
      await loadWidgetContent();
      btnRetry.textContent = 'Повторить подключение';
      btnRetry.disabled = false;
    });
  }

  // Автоматический мониторинг сети
  window.addEventListener('online', loadWidgetContent);
  window.addEventListener('offline', showOffline);
  setInterval(async () => {
    if (offlineView && offlineView.style.display === 'flex') {
      const ok = await checkServerHealth();
      if (ok) showOnline();
    }
  }, 10000);

  // Старт инициализации
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTauri);
  } else {
    initTauri();
  }
})();
