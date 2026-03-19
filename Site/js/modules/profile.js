/* ===================================================
   PULSE CHAT v2.0 — Profile + Notifications
   =================================================== */

// ══════════════════════════════════════════
// PROFILE MODULE
// ══════════════════════════════════════════
const Profile = {

  async load() {
    if (!State.currentUser) return;

    try {
      const data = await API.request(`/api/profile/${State.currentUser.id}`);

      // Avatar (photo from TG or initials)
      const wrap = document.getElementById('profileAvatarWrap');
      if (wrap) {
        if (State.currentUser.photo) {
          wrap.innerHTML = `<img src="${State.currentUser.photo}" style="width:100%;height:100%;border-radius:50%;object-fit:cover" onerror="this.parentElement.innerHTML='<span id=profileInitials>${Profile._initials(data.name)}</span>'">`;
        } else {
          const el = document.getElementById('profileInitials');
          if (el) el.textContent = this._initials(data.name);
        }
      }

      // Name
      const nameEl = document.getElementById('profileName');
      if (nameEl) nameEl.textContent = data.name || 'Пользователь';

      // Username
      const userEl = document.getElementById('profileUsername');
      if (userEl) userEl.textContent = data.username ? `@${data.username}` : 'не указан';

      // TG ID
      const idEl = document.getElementById('profileTgId');
      if (idEl) idEl.textContent = data.user_id;

      // Registration date
      const dateEl = document.getElementById('profileRegDate');
      if (dateEl) {
        if (data.registered_at) {
          const d = new Date(data.registered_at);
          const months = ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек'];
          dateEl.textContent = `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
        } else {
          dateEl.textContent = 'Не указана';
        }
      }

      // Balance
      const balEl = document.getElementById('profileBalance');
      if (balEl) balEl.textContent = Math.floor(data.balance).toLocaleString('ru-RU') + ' 💎';

      // Message count
      const msgEl = document.getElementById('profileMsgCount');
      if (msgEl) msgEl.textContent = data.msg_count.toLocaleString('ru-RU');

      // Groups count
      const grpEl = document.getElementById('profileGroupsCount');
      if (grpEl) grpEl.textContent = data.groups_count;

      // Status
      const statusEl = document.getElementById('profileStatusText');
      if (statusEl) {
        if (data.status) {
          statusEl.textContent = data.status;
          statusEl.style.fontStyle = 'normal';
          statusEl.style.color = 'var(--text-0)';
        } else {
          statusEl.textContent = 'Нажмите, чтобы добавить статус...';
          statusEl.style.fontStyle = 'italic';
          statusEl.style.color = 'var(--text-2)';
        }
      }

      // Update notifications label
      Notify.updateLabel();

    } catch (err) {
      console.error('Profile load error:', err);
    }
  },

  editStatus() {
    const current = document.getElementById('profileStatusText')?.textContent || '';
    const isPlaceholder = current.includes('Нажмите');

    document.getElementById('modalEditStatus')?.remove();
    const m = document.createElement('div');
    m.id = 'modalEditStatus';
    m.className = 'modal active';
    m.onclick = e => { if (e.target === m) m.remove(); };
    m.innerHTML = `
      <div class="modal-content" style="text-align:left">
        <h3 style="text-align:center;margin-bottom:16px">Статус</h3>
        <input type="text" id="statusInput" maxlength="100" placeholder="Что у вас нового?"
          value="${isPlaceholder ? '' : escapeHTML(current)}"
          style="width:100%;padding:12px;background:var(--input-bg);border:1px solid var(--input-border);border-radius:var(--radius);color:var(--text-0);font-size:15px;margin:0">
        <div style="font-size:12px;color:var(--text-2);margin-top:6px;text-align:right"><span id="statusCharCount">${isPlaceholder ? 0 : current.length}</span>/100</div>
        <div class="modal-actions" style="margin-top:12px">
          <button class="btn-outline" onclick="document.getElementById('modalEditStatus').remove()">Отмена</button>
          <button class="btn-primary" onclick="Profile.saveStatus()">Сохранить</button>
        </div>
      </div>
    `;
    document.body.appendChild(m);

    const input = document.getElementById('statusInput');
    input.focus();
    input.addEventListener('input', () => {
      document.getElementById('statusCharCount').textContent = input.value.length;
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); Profile.saveStatus(); }
    });
  },

  async saveStatus() {
    const input = document.getElementById('statusInput');
    const status = input?.value.trim() || '';

    try {
      await API.request('/api/profile/status', {
        method: 'POST',
        body: JSON.stringify({ user_id: State.currentUser.id, status })
      });

      const el = document.getElementById('profileStatusText');
      if (el) {
        if (status) {
          el.textContent = status;
          el.style.fontStyle = 'normal';
          el.style.color = 'var(--text-0)';
        } else {
          el.textContent = 'Нажмите, чтобы добавить статус...';
          el.style.fontStyle = 'italic';
          el.style.color = 'var(--text-2)';
        }
      }
    } catch (err) {
      console.error('Status save error:', err);
    }
    document.getElementById('modalEditStatus')?.remove();
  },

  _initials(name) {
    if (!name) return 'ВЫ';
    const parts = name.split(' ');
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
  },
};

// ══════════════════════════════════════════
// NOTIFICATION MODULE
// ══════════════════════════════════════════
const Notify = {
  enabled: true,
  _audio: null,

  init() {
    this.enabled = localStorage.getItem('pulse-notif') !== 'off';
    this.updateLabel();

    // Request permission if enabled
    if (this.enabled && 'Notification' in window && Notification.permission === 'default') {
      setTimeout(() => Notification.requestPermission(), 3000);
    }
  },

  toggleEnabled() {
    this.enabled = !this.enabled;
    localStorage.setItem('pulse-notif', this.enabled ? 'on' : 'off');
    this.updateLabel();

    if (this.enabled && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  },

  updateLabel() {
    const label = document.getElementById('notifStatusLabel');
    const icon = document.getElementById('notifIcon');
    if (label) label.textContent = this.enabled ? 'Включены' : 'Выключены';
    if (icon) {
      icon.className = this.enabled ? 'fa-solid fa-bell' : 'fa-solid fa-bell-slash';
      icon.style.color = this.enabled ? '' : 'var(--text-2)';
    }
  },

  // Play sound for incoming message
  playSound() {
    if (!this.enabled) return;
    try {
      if (!this._audio) {
        // Telegram-like notification beep (short, clean)
        this._audio = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU5LjI3LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAADhAC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU5LjM3AAAAAAAAAAAAAAAAJAAAAAAAAAAAAASEYbORCwAAAAAAAAAAAAAAAAD/+0DEAAAC4ANX9AAAIN4Y6v80AABAkBcDwfB8HwfBAMf/ygIAmD+UBAEwfygf/lAQBMH8oCAJg/KAgCYPwAAAAA//tAxAAAB5QFZ/mJAAUOi25/MyAAAA//CQAAAILOl4SAAB6n3qf6gAEgTAnuWGoYjBMN0GAMYIBMF//8uCAEB3/+XP5QEATygIAm');
      }
      this._audio.volume = 0.3;
      this._audio.currentTime = 0;
      this._audio.play().catch(() => {});
    } catch (e) {}
  },

  // Show browser notification
  showBrowserNotif(title, body, tag) {
    if (!this.enabled) return;
    if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
      new Notification(title || 'Pulse Chat', {
        body: body?.substring(0, 80) || '',
        icon: '/favicon.ico',
        tag: tag || 'pulse-msg-' + Date.now(),
        silent: true, // We play our own sound
      });
    }
  },

  // Update tab title with unread count
  _unread: 0,

  addUnread() {
    if (!document.hidden) return;
    this._unread++;
    document.title = `(${this._unread}) Pulse Chat`;
  },

  clearUnread() {
    this._unread = 0;
    document.title = 'Pulse Chat';
  },
};
