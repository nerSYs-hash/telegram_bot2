/* ===================================================
   PULSE CHAT — Auth Module (Telegram OAuth)
   =================================================== */

/**
 * Глобальный callback — вызывается виджетом Telegram
 * Telegram передаёт: { id, first_name, last_name, username, photo_url, auth_date, hash }
 */
function onTelegramAuth(user) {
  console.log('📱 Telegram Auth callback:', user);
  Auth.processLogin(user);
}

const Auth = {

  /**
   * Главный метод — отправляет данные на бэкенд для верификации
   */
  async processLogin(tgUser) {
    const statusEl = document.getElementById('authStatus');
    statusEl.style.display = 'block';

    try {
      const result = await API.request('/api/auth/telegram', {
        method: 'POST',
        body: JSON.stringify(tgUser),
      });

      if (result.status === 'success') {
        // Сохраняем данные для автологина
        localStorage.setItem('pulse-user', JSON.stringify({
          id: result.user.id,
          name: result.user.username || tgUser.first_name,
          photo: tgUser.photo_url || null,
          balance: result.user.balance || 0,
          is_admin: result.user.is_admin || false,
          is_new: result.is_new,
        }));

        // Обновляем State
        State.setUser({
          id: result.user.id,
          name: result.user.username || tgUser.first_name,
          photo: tgUser.photo_url || null,
          balance: result.user.balance || 0,
          is_admin: result.user.is_admin || false,
        });

        console.log(result.is_new
          ? '🆕 Новый пользователь!'
          : `✅ С возвращением! Баланс: ${result.user.balance}`
        );

        // Переходим в чат
        // Check if there's a pending invite
        if (typeof Invite !== 'undefined' && Invite.checkPending()) {
          console.log('🔗 Redirecting to pending invite');
        } else {
          Router.navigate('chat');
        }
      } else {
        throw new Error(result.detail || 'Неизвестная ошибка');
      }
    } catch (error) {
      statusEl.style.display = 'none';
      alert('Ошибка авторизации: ' + error.message);
      console.error('Auth error:', error);
    }
  },

  /**
   * Fallback: ручной вход по Telegram ID (для тестов или если виджет не грузится)
   */
  async manualLogin() {
    const idInput = document.getElementById('manualTgId');
    const tgId = parseInt(idInput.value);
    if (!tgId || tgId < 1) {
      idInput.style.borderColor = 'var(--danger)';
      return;
    }
    this.processLogin({ id: tgId, first_name: 'User', username: null });
  },

  /**
   * Автологин при загрузке страницы (если уже входил)
   */
  tryAutoLogin() {
    const saved = localStorage.getItem('pulse-user');
    if (saved) {
      try {
        const user = JSON.parse(saved);
        if (user.id) {
          State.setUser(user);
          Router.navigate('chat');
          return true;
        }
      } catch (e) { localStorage.removeItem('pulse-user'); }
    }
    return false;
  },

  /**
   * Выход
   */
  logout() {
    localStorage.removeItem('pulse-user');
    State.currentUser = null;
    State.currentChatId = null;
    Router.navigate('landing');
  },
};

function showAuthFallback(message) {
  const widgetWrap = document.getElementById('tgWidgetContainer');
  const fb = document.getElementById('tgFallback');
  const note = document.getElementById('tgDomainNotice');

  if (widgetWrap) widgetWrap.style.display = 'none';
  if (fb) fb.style.display = 'block';
  if (note) {
    note.style.display = 'block';
    note.innerHTML = message;
  }
}

function initTelegramAuthWidget() {
  const host = window.location.hostname;
  const protocol = window.location.protocol;
  const allowedHosts = new Set(['puls-chat.ru', 'www.puls-chat.ru']);
  const isProdDomain = allowedHosts.has(host);

  if (protocol !== 'https:' || !isProdDomain) {
    showAuthFallback(
      '<strong>Режим предпросмотра:</strong> Telegram-виджет отключен для локального запуска/IP. Используйте вход по Telegram ID ниже.'
    );
    return;
  }

  // Показать fallback, если виджет не загрузился за 5 секунд
  setTimeout(() => {
    const widget = document.querySelector('#tgWidgetContainer iframe');
    if (!widget) {
      showAuthFallback(
        '<strong>Виджет недоступен:</strong> Telegram Login не загрузился. Проверьте домен в BotFather (/setdomain) и попробуйте снова.'
      );
      console.warn('⚠️ Telegram widget не загрузился — показан fallback');
    }
  }, 5000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTelegramAuthWidget);
} else {
  initTelegramAuthWidget();
}
