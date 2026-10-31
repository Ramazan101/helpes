/**
 * Клиентский контроллер ИТ-помощника Helpes (для страницы /assistant/ и плавающего виджета).
 * Вся бизнес-логика выполняется на сервере (/assistant/api/chat/).
 * Вывод текста защищён через textContent (без вставки сырого HTML).
 */
(function () {
  "use strict";

  if (window.__helpesAssistantInitialized) {
    return;
  }
  window.__helpesAssistantInitialized = true;

  var STORAGE_KEY = "helpes_assistant_history_v1";
  var MAX_STORED_MESSAGES = 6;

  function getCsrfToken(formEl) {
    if (formEl) {
      var input = formEl.querySelector('input[name="csrfmiddlewaretoken"]');
      if (input && input.value) {
        return input.value;
      }
    }
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function loadHistory() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.slice(-MAX_STORED_MESSAGES) : [];
    } catch (e) {
      return [];
    }
  }

  function saveHistory(history) {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(history.slice(-MAX_STORED_MESSAGES))
      );
    } catch (e) {
      // Игнорируем ошибки переполнения sessionStorage
    }
  }

  function appendMessageBubble(messagesBox, role, text) {
    var wrapper = document.createElement("div");
    wrapper.className =
      "assistant-msg " +
      (role === "user" ? "assistant-msg-user" : "assistant-msg-bot");

    var bubble = document.createElement("div");
    bubble.className = "assistant-msg-bubble";
    bubble.textContent = text;

    wrapper.appendChild(bubble);
    messagesBox.appendChild(wrapper);
    messagesBox.scrollTop = messagesBox.scrollHeight;
    return wrapper;
  }

  function createTypingIndicator(messagesBox) {
    var wrapper = document.createElement("div");
    wrapper.className = "assistant-msg assistant-msg-bot assistant-typing";
    var bubble = document.createElement("div");
    bubble.className = "assistant-msg-bubble text-muted small";
    bubble.textContent = "Помощник формирует ответ...";
    wrapper.appendChild(bubble);
    messagesBox.appendChild(wrapper);
    messagesBox.scrollTop = messagesBox.scrollHeight;
    return wrapper;
  }

  function initContainer(container) {
    var apiUrl = container.getAttribute("data-api-url") || "/assistant/api/chat/";
    var maxLength = parseInt(container.getAttribute("data-max-length") || "1000", 10);
    var messagesBox = container.querySelector("[data-assistant-messages]");
    var form = container.querySelector("[data-assistant-form]");
    var input = container.querySelector("[data-assistant-input]");
    var submitBtn = container.querySelector("[data-assistant-submit]");
    var counterEl = container.querySelector("[data-assistant-counter]");
    var escalationBar = container.querySelector("[data-assistant-escalation]");
    var errorBar = container.querySelector("[data-assistant-error-bar]");
    var errorTextEl = container.querySelector("[data-assistant-error-text]");
    var retryBtn = container.querySelector("[data-assistant-retry]");
    var clearBtn = container.querySelector("[data-assistant-clear]");

    if (!messagesBox || !form || !input || !submitBtn) {
      return;
    }

    var history = loadHistory();
    var isPending = false;
    var lastFailedMessage = null;

    // Восстановление истории сессии
    history.forEach(function (item) {
      if (item && (item.role === "user" || item.role === "assistant") && item.content) {
        appendMessageBubble(messagesBox, item.role, item.content);
      }
    });

    function updateCounter() {
      if (counterEl) {
        counterEl.textContent = input.value.length + " / " + maxLength;
      }
    }

    function setLoadingState(loading) {
      isPending = loading;
      submitBtn.disabled = loading;
      input.disabled = loading;
    }

    function hideError() {
      if (errorBar) {
        errorBar.classList.add("d-none");
      }
    }

    function showError(msg) {
      if (errorBar && errorTextEl) {
        errorTextEl.textContent = msg;
        errorBar.classList.remove("d-none");
      }
    }

    function sendPrompt(text, appendUserBubble) {
      var trimmed = (text || "").trim();
      if (!trimmed || isPending) {
        return;
      }
      if (trimmed.length > maxLength) {
        showError("Сообщение превышает допустимую длину (" + maxLength + " символов).");
        return;
      }

      hideError();
      if (appendUserBubble !== false) {
        appendMessageBubble(messagesBox, "user", trimmed);
      }

      var typingEl = createTypingIndicator(messagesBox);
      setLoadingState(true);

      fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(form),
          "Accept": "application/json"
        },
        credentials: "same-origin",
        body: JSON.stringify({
          message: trimmed,
          history: history.slice(-MAX_STORED_MESSAGES)
        })
      })
        .then(function (response) {
          return response
            .json()
            .catch(function () {
              return {};
            })
            .then(function (data) {
              return { status: response.status, ok: response.ok, data: data };
            });
        })
        .then(function (res) {
          if (typingEl && typingEl.parentNode) {
            typingEl.parentNode.removeChild(typingEl);
          }
          setLoadingState(false);

          if (res.data && res.data.reply) {
            appendMessageBubble(messagesBox, "assistant", res.data.reply);

            // Сохраняем в историю диалога ТОЛЬКО успешные ответы модели ИИ (исключая сервисные сообщения и ошибки)
            if (res.data.mode === "ai") {
              history.push({ role: "user", content: trimmed });
              history.push({ role: "assistant", content: res.data.reply });
              history = history.slice(-MAX_STORED_MESSAGES);
              saveHistory(history);
              lastFailedMessage = null;
              hideError();
            } else if (res.data.error_code && res.data.error_code !== "ai_not_configured") {
              // Временный сбой сервиса ИИ (таймаут, лимит, недоступность) — даём возможность повторить
              lastFailedMessage = trimmed;
              showError("Сервис ИИ временно недоступен. Вы можете повторить запрос или оформить заявку.");
            } else {
              lastFailedMessage = null;
              hideError();
            }

            if (escalationBar) {
              if (res.data.suggest_ticket) {
                escalationBar.classList.remove("d-none");
              } else {
                escalationBar.classList.add("d-none");
              }
            }
            input.focus();
            return;
          }

          lastFailedMessage = trimmed;
          var errMsg =
            (res.data && res.data.error) ||
            "Не удалось получить ответ от сервера. Попробуйте ещё раз или создайте заявку.";
          showError(errMsg);
          if (escalationBar) {
            escalationBar.classList.remove("d-none");
          }
        })
        .catch(function () {
          if (typingEl && typingEl.parentNode) {
            typingEl.parentNode.removeChild(typingEl);
          }
          setLoadingState(false);
          lastFailedMessage = trimmed;
          showError("Сбой сети при обращении к помощнику. Проверьте подключение или оформите заявку.");
          if (escalationBar) {
            escalationBar.classList.remove("d-none");
          }
        });
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var val = input.value;
      if (!val.trim()) return;
      input.value = "";
      updateCounter();
      sendPrompt(val, true);
    });

    if (input.tagName === "TEXTAREA") {
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          form.dispatchEvent(new Event("submit", { cancelable: true }));
        }
      });
    }

    input.addEventListener("input", updateCounter);

    if (retryBtn) {
      retryBtn.addEventListener("click", function () {
        if (lastFailedMessage) {
          sendPrompt(lastFailedMessage, false);
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        history = [];
        saveHistory([]);
        messagesBox.innerHTML = "";
        appendMessageBubble(
          messagesBox,
          "assistant",
          "История диалога очищена. Задайте новый вопрос!"
        );
        hideError();
      });
    }

    container.__sendAssistantPrompt = function (promptText) {
      sendPrompt(promptText, true);
    };
  }

  document.addEventListener("DOMContentLoaded", function () {
    var containers = document.querySelectorAll("[data-assistant-container]");
    containers.forEach(initContainer);

    // Обработка быстрых подсказок (на странице и в виджете)
    var quickButtons = document.querySelectorAll("[data-assistant-prompt]");
    quickButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var promptText = btn.getAttribute("data-assistant-prompt");
        var widgetSection = btn.closest("[data-assistant-container]");
        var targetContainer =
          widgetSection || document.querySelector("[data-assistant-container]");
        if (targetContainer && typeof targetContainer.__sendAssistantPrompt === "function") {
          targetContainer.__sendAssistantPrompt(promptText);
        }
      });
    });

    // Управление плавающим виджетом
    var widgetRoot = document.querySelector("[data-assistant-widget]");
    if (widgetRoot) {
      var toggleBtn = widgetRoot.querySelector("[data-assistant-toggle]");
      var closeBtn = widgetRoot.querySelector("[data-assistant-close]");
      var panel = widgetRoot.querySelector(".assistant-widget-panel");
      var widgetInput = widgetRoot.querySelector("[data-assistant-input]");
      var focusTicketBtn = widgetRoot.querySelector("[data-assistant-focus-ticket]");

      function openWidget() {
        panel.classList.remove("d-none");
        toggleBtn.setAttribute("aria-expanded", "true");
        if (widgetInput) {
          setTimeout(function () {
            widgetInput.focus();
          }, 50);
        }
      }

      function closeWidget() {
        panel.classList.add("d-none");
        toggleBtn.setAttribute("aria-expanded", "false");
        toggleBtn.focus();
      }

      if (toggleBtn && panel) {
        toggleBtn.addEventListener("click", function () {
          if (panel.classList.contains("d-none")) {
            openWidget();
          } else {
            closeWidget();
          }
        });
      }

      if (closeBtn) {
        closeBtn.addEventListener("click", closeWidget);
      }

      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && panel && !panel.classList.contains("d-none")) {
          closeWidget();
        }
      });

      if (focusTicketBtn) {
        focusTicketBtn.addEventListener("click", function () {
          closeWidget();
          var firstField = document.querySelector('form input[type="text"], form select');
          if (firstField) {
            firstField.focus();
          }
        });
      }
    }
  });
})();
