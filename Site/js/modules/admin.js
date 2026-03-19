/* ===================================================
   PULSE CHAT — Admin Module
   Mute, Ban, Roles, Topic Management, Audit Log
   =================================================== */

const Admin = {
  currentMembers: [],
  myRole: 'member',

  /** Open admin panel for current chat */
  async openPanel() {
    const chatId = Chat.currentTopicId ? State.currentChatId : State.currentChatId;
    if (!chatId) return;

    document.getElementById('adminPanel').classList.add('active');
    document.getElementById('adminChatName').textContent = Chat.chatMeta?.name || chatId;
    this._showTab('members');
    await this.loadMembers(chatId);
  },

  closePanel() {
    document.getElementById('adminPanel').classList.remove('active');
  },

  _showTab(tab) {
    document.querySelectorAll('.admin-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    document.querySelectorAll('.admin-tab-content').forEach(c => c.style.display = c.id === `adminTab_${tab}` ? 'block' : 'none');
  },

  /** Load members list */
  async loadMembers(chatId) {
    const list = document.getElementById('adminMembersList');
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-2)">Загрузка...</div>';

    try {
      const data = await API.request(`/api/admin/${chatId}/members?admin_id=${State.currentUser.id}`);
      this.myRole = data.your_role;
      this.currentMembers = data.members || [];

      // Update role badge
      document.getElementById('adminMyRole').textContent = this._roleName(this.myRole);

      // Show/hide admin-only controls
      const isAdmin = this.myRole === 'owner' || this.myRole === 'admin';
      document.querySelectorAll('.admin-only').forEach(el => el.style.display = isAdmin ? '' : 'none');

      this._renderMembers(list);
    } catch (e) {
      list.innerHTML = `<div style="padding:20px;text-align:center;color:var(--danger)">${e.message || 'Нет прав доступа'}</div>`;
    }
  },

  _renderMembers(container) {
    container.innerHTML = '';
    const isMod = ['owner', 'admin', 'moderator'].includes(this.myRole);

    this.currentMembers.forEach(m => {
      const isMe = m.id === State.currentUser.id;
      const color = getAvatarColor(m.id);
      const initials = (m.name || '??').substring(0, 2).toUpperCase();

      const div = document.createElement('div');
      div.className = 'admin-member-row';
      div.innerHTML = `
        <div class="admin-member-avatar" style="background:${color}">${initials}</div>
        <div class="admin-member-info">
          <div class="admin-member-name">
            ${escapeHTML(m.name)}${isMe ? ' <span style="color:var(--accent);font-size:11px">(вы)</span>' : ''}
            ${m.online ? '<span class="admin-online-dot"></span>' : ''}
          </div>
          <div class="admin-member-role ${m.role}">${this._roleName(m.role)}${m.muted ? ' · 🔇 Мут' : ''}</div>
        </div>
        ${(!isMe && isMod) ? `<button class="icon-btn" onclick="Admin.showMemberActions(${m.id}, '${escapeHTML(m.name)}', '${m.role}', ${m.muted})"><i class="fa-solid fa-ellipsis-vertical"></i></button>` : ''}
      `;
      container.appendChild(div);
    });

    if (this.currentMembers.length === 0) {
      container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-2)">Нет участников</div>';
    }
  },

  _roleName(role) {
    return { owner: '👑 Владелец', admin: '⭐ Админ', moderator: '🛡 Модератор', member: 'Участник' }[role] || role;
  },

  /** Member action dropdown */
  showMemberActions(userId, name, role, muted) {
    document.querySelector('.admin-actions-dropdown')?.remove();

    const dd = document.createElement('div');
    dd.className = 'admin-actions-dropdown';

    const chatId = State.currentChatId;
    const items = [];

    // Role management (owner only)
    if (this.myRole === 'owner') {
      if (role !== 'admin') items.push({ icon: 'fa-star', label: 'Назначить админом', action: () => this.setRole(chatId, userId, 'admin') });
      if (role !== 'moderator') items.push({ icon: 'fa-shield-halved', label: 'Назначить модератором', action: () => this.setRole(chatId, userId, 'moderator') });
      if (role !== 'member' && role !== 'owner') items.push({ icon: 'fa-user', label: 'Снять роль', action: () => this.setRole(chatId, userId, 'member') });
    }

    // Mute
    if (!muted) {
      items.push({ icon: 'fa-volume-xmark', label: 'Мут (15 мин)', action: () => this.muteUser(chatId, userId, 900) });
      items.push({ icon: 'fa-volume-xmark', label: 'Мут (1 час)', action: () => this.muteUser(chatId, userId, 3600) });
      items.push({ icon: 'fa-volume-xmark', label: 'Мут (навсегда)', action: () => this.muteUser(chatId, userId, 0) });
    } else {
      items.push({ icon: 'fa-volume-high', label: 'Снять мут', action: () => this.unmuteUser(chatId, userId) });
    }

    // Delete messages
    items.push({ icon: 'fa-trash', label: 'Удалить все сообщения', danger: true, action: () => this.deleteAllMessages(chatId, userId) });

    // Ban
    items.push({ icon: 'fa-ban', label: 'Заблокировать', danger: true, action: () => this.banUser(chatId, userId) });

    items.forEach(item => {
      const row = document.createElement('div');
      row.className = 'context-menu-item' + (item.danger ? ' danger' : '');
      row.innerHTML = `<i class="fa-solid ${item.icon}"></i><span>${item.label}</span>`;
      row.onclick = () => { item.action(); dd.remove(); };
      dd.appendChild(row);
    });

    dd.innerHTML = `<div style="padding:8px 16px;font-weight:600;font-size:13px;color:var(--text-2);border-bottom:1px solid var(--divider)">${name}</div>` + dd.innerHTML;
    document.getElementById('adminPanel').appendChild(dd);

    // Close on outside click
    setTimeout(() => document.addEventListener('click', function rm(e) {
      if (!dd.contains(e.target)) { dd.remove(); document.removeEventListener('click', rm); }
    }), 50);
  },

  /** Actions */
  async setRole(chatId, targetId, role) {
    try {
      await API.request(`/api/admin/${chatId}/set-role`, { method: 'POST', body: JSON.stringify({ admin_id: State.currentUser.id, target_id: targetId, role }) });
      await this.loadMembers(chatId);
    } catch (e) { alert(e.message); }
  },

  async muteUser(chatId, targetId, duration) {
    try {
      await API.request(`/api/admin/${chatId}/mute`, { method: 'POST', body: JSON.stringify({ admin_id: State.currentUser.id, target_id: targetId, duration }) });
      await this.loadMembers(chatId);
    } catch (e) { alert(e.message); }
  },

  async unmuteUser(chatId, targetId) {
    try {
      await API.request(`/api/admin/${chatId}/unmute`, { method: 'POST', body: JSON.stringify({ admin_id: State.currentUser.id, target_id: targetId }) });
      await this.loadMembers(chatId);
    } catch (e) { alert(e.message); }
  },

  async banUser(chatId, targetId) {
    if (!confirm('Заблокировать пользователя?')) return;
    try {
      await API.request(`/api/admin/${chatId}/ban`, { method: 'POST', body: JSON.stringify({ admin_id: State.currentUser.id, target_id: targetId }) });
      await this.loadMembers(chatId);
    } catch (e) { alert(e.message); }
  },

  async deleteAllMessages(chatId, userId) {
    if (!confirm('Удалить все сообщения этого пользователя?')) return;
    try {
      await API.request(`/api/admin/${chatId}/delete-messages`, { method: 'POST', body: JSON.stringify({ admin_id: State.currentUser.id, from_user_id: userId }) });
      Chat._loadMessages(Chat.currentTopicId || chatId);
      Chat._renderMessages();
    } catch (e) { alert(e.message); }
  },

  /** Topics management in admin */
  _renderTopicsAdmin() {
    const container = document.getElementById('adminTopicsList');
    container.innerHTML = '';
    const isMod = ['owner', 'admin', 'moderator'].includes(this.myRole);
    const isOwner = this.myRole === 'owner';

    // Import button (owner only)
    if (isOwner) {
      const importBtn = document.createElement('div');
      importBtn.style.cssText = 'padding:12px 16px';
      importBtn.innerHTML = `<button class="btn-primary" onclick="Admin.importTgTopics()" style="width:100%;padding:10px;font-size:13px"><i class="fa-brands fa-telegram" style="margin-right:6px"></i>Импорт веток из Telegram</button>`;
      container.appendChild(importBtn);
    }

    if (Chat.topics.length === 0) {
      container.innerHTML += '<div style="padding:20px;text-align:center;color:var(--text-2)">Нет веток</div>';
      return;
    }

    Chat.topics.forEach(t => {
      const div = document.createElement('div');
      div.className = 'admin-topic-row';
      div.innerHTML = `
        <div class="admin-topic-icon">${Chat._topicIcon(t.title)}</div>
        <div class="admin-topic-info">
          <div class="admin-topic-title">${escapeHTML(t.title)}</div>
          <div class="admin-topic-meta">${t.msg_count || 0} сообщ.</div>
        </div>
        ${isMod ? `
          <button class="icon-btn" onclick="Admin.renameTopic('${t.id}')" title="Переименовать"><i class="fa-solid fa-pen" style="font-size:13px"></i></button>
          <button class="icon-btn" onclick="Admin.deleteTopic('${t.id}')" title="Удалить" style="color:var(--danger)"><i class="fa-solid fa-trash" style="font-size:13px"></i></button>
        ` : ''}
      `;
      container.appendChild(div);
    });
  },

  /** Import topics from Telegram bot */
  async importTgTopics() {
    const chatId = State.currentChatId;
    if (!chatId) return;
    
    if (!confirm('Импортировать все ветки из вашего Telegram-чата?')) return;
    
    try {
      const result = await API.request(`/api/admin/${chatId}/import-tg-topics?admin_id=${State.currentUser.id}`, { method: 'POST' });
      if (result.status === 'success') {
        alert(`✅ Импортировано ${result.imported} из ${result.total_in_tg} веток!`);
        await Chat._loadTopics(chatId);
        this._renderTopicsAdmin();
      } else {
        alert('Ошибка: ' + (result.detail || 'Неизвестная ошибка'));
      }
    } catch (e) {
      alert('Ошибка импорта: ' + e.message);
    }
  },

  async renameTopic(topicId) {
    const newName = prompt('Новое название ветки:');
    if (!newName?.trim()) return;
    try {
      await API.request(`/api/admin/topics/${topicId}/rename`, { method: 'POST', body: JSON.stringify({ admin_id: State.currentUser.id, title: newName.trim() }) });
      await Chat._loadTopics(State.currentChatId);
      Chat._renderTopics();
    } catch (e) { alert(e.message); }
  },

  async deleteTopic(topicId) {
    if (!confirm('Удалить ветку и все сообщения в ней?')) return;
    try {
      await API.request(`/api/admin/topics/${topicId}/delete`, { method: 'POST', body: JSON.stringify({ admin_id: State.currentUser.id }) });
      await Chat._loadTopics(State.currentChatId);
      Chat._renderTopics();
    } catch (e) { alert(e.message); }
  },

  /** Audit log */
  async loadAuditLog() {
    const chatId = State.currentChatId;
    const container = document.getElementById('adminAuditList');
    container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-2)">Загрузка...</div>';

    try {
      const logs = await API.request(`/api/admin/${chatId}/audit-log?admin_id=${State.currentUser.id}`);
      container.innerHTML = '';

      if (logs.length === 0) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-2)">Лог пуст</div>';
        return;
      }

      logs.forEach(log => {
        const actionIcons = { mute: '🔇', unmute: '🔊', ban: '⛔', unban: '✅', delete_msg: '🗑', set_role: '👤', pin: '📌', rename_topic: '✏️', delete_topic: '❌' };
        const div = document.createElement('div');
        div.className = 'admin-audit-row';
        div.innerHTML = `
          <span class="audit-icon">${actionIcons[log.action] || '📋'}</span>
          <div class="audit-info">
            <span class="audit-action">${log.action}</span>
            ${log.details ? `<span class="audit-details">${escapeHTML(log.details)}</span>` : ''}
          </div>
          <span class="audit-time">${formatTime(log.ts)}</span>
        `;
        container.appendChild(div);
      });
    } catch (e) {
      container.innerHTML = '<div style="padding:20px;color:var(--danger)">Нет доступа</div>';
    }
  },
};
