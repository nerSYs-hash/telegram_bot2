/* ===================================================
   PULSE CHAT v2.0 — Sidebar Module
   Real timestamps, improved rendering
   =================================================== */

const Sidebar = {

  async render() {
    const list = document.getElementById('chatList');
    if (!list) return;
    if (!State.currentUser) return;

    try {
      const chats = await API.request(`/api/chats?user_id=${State.currentUser.id}`);
      list.innerHTML = '';

      chats.forEach(chat => {
        const item = document.createElement('div');
        item.className = 'chat-item' +
          (chat.id === State.currentChatId ? ' active' : '') +
          (chat.unread > 0 ? ' unread' : '');
        item.onclick = () => Chat.open(chat.id, chat.name, chat);

        const color = chat.avatar_color || '#54a9eb';

        // Avatar: TG gradient or bot icon
        let avatarHTML;
        if (chat.is_bot) {
          avatarHTML = `<div style="background:#0088cc;width:var(--dialog-photo);height:var(--dialog-photo);display:flex;align-items:center;justify-content:center;border-radius:50%;color:#fff;font-size:20px"><i class="fa-solid fa-robot"></i></div>`;
        } else {
          avatarHTML = makeAvatarHTML(chat.name, chat.id?.charCodeAt?.(0) || 0, 54);
        }

        // Real timestamp from server (last_msg_ts) or fallback
        const timeStr = chat.last_msg_ts
          ? formatChatTime(chat.last_msg_ts)
          : '';

        // Message preview with sender
        let preview = chat.last_msg || '';
        if (chat.is_group && chat.last_msg_sender && preview) {
          preview = `<span class="sender">${chat.last_msg_sender}:</span> ${preview}`;
        }

        // Type icon
        let typeIcon = '';
        if (chat.is_bot) typeIcon = '🤖 ';
        else if (chat.is_group) typeIcon = '';

        // Group icon in name
        let namePrefix = '';
        if (chat.is_group) namePrefix = '<i class="fa-solid fa-users" style="font-size:11px;color:var(--text-2);margin-right:4px;vertical-align:1px"></i>';

        item.innerHTML = `
          <div class="chat-item-avatar">
            ${avatarHTML}
            ${chat.online ? '<div class="avatar-online"></div>' : ''}
          </div>
          <div class="chat-item-body">
            <div class="chat-item-top">
              <div class="chat-item-name">${typeIcon}${namePrefix}${escapeHTML(chat.name)}</div>
              <div class="chat-item-time">${timeStr}</div>
            </div>
            <div class="chat-item-bottom">
              <div class="chat-item-preview">${preview}</div>
              <div class="chat-item-meta">
                ${chat.muted ? '<i class="fa-solid fa-volume-xmark" style="font-size:14px;color:var(--text-2)"></i>' : ''}
                ${chat.unread > 0 ? `<span class="badge${chat.muted ? ' muted' : ''}">${chat.unread}</span>` : ''}
              </div>
            </div>
          </div>
        `;
        list.appendChild(item);
        initRipple(item);
      });

      if (chats.length === 0) {
        list.innerHTML = '<div style="padding:40px 20px;text-align:center;color:var(--text-2)"><i class="fa-regular fa-comments" style="font-size:48px;display:block;margin-bottom:12px;opacity:0.2"></i>Нет чатов</div>';
      }
    } catch (err) {
      console.error("Sidebar load error:", err);
      list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-2);opacity:0.5">Ошибка загрузки чатов</div>';
    }
  },

  toggleSearch() {
    const bar = document.getElementById('searchBar');
    bar.classList.toggle('active');
    if (bar.classList.contains('active')) document.getElementById('searchInput').focus();
  },

  async filter(query) {
    const q = query.trim().toLowerCase();
    const list = document.getElementById('chatList');

    if (q.length < 2) { this.render(); return; }

    const localItems = document.querySelectorAll('.chat-item');
    let foundLocal = false;
    localItems.forEach(item => {
      const match = item.innerText.toLowerCase().includes(q);
      item.style.display = match ? '' : 'none';
      if (match) foundLocal = true;
    });

    try {
      const results = await API.request(`/api/search?q=${q}`);
      if (results.length > 0) {
        const divider = document.createElement('div');
        divider.className = 'search-divider';
        divider.innerHTML = '<i class="fa-solid fa-magnifying-glass" style="margin-right:6px"></i>Глобальный поиск';
        list.appendChild(divider);

        results.forEach(res => {
          const item = document.createElement('div');
          item.className = 'chat-item search-result';
          item.onclick = () => {
            Chat.open(res.id, res.name);
            this.render();
          };
          const color = res.avatar_color || getAvatarColor(res.id || 0);
          item.innerHTML = `
            <div class="chat-item-avatar">
              <div style="background:${color};width:var(--dialog-photo);height:var(--dialog-photo);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600;font-size:18px">
                ${res.name.substring(0, 2).toUpperCase()}
              </div>
            </div>
            <div class="chat-item-body">
              <div class="chat-item-top">
                <div class="chat-item-name">${escapeHTML(res.name)}</div>
              </div>
              <div class="chat-item-bottom">
                <div class="chat-item-preview">${res.sub || ''}</div>
              </div>
            </div>
          `;
          list.appendChild(item);
        });
      }
    } catch (e) { console.error("Search failed", e); }
  },

  toggleMenu() {
    const slideMenu = document.getElementById('slideMenu');
    const menuOverlay = document.getElementById('menuOverlay');
    const willOpen = !slideMenu.classList.contains('active');

    // Keep side overlays mutually exclusive to avoid squeezing the center area.
    if (willOpen) {
      const infoPanel = document.getElementById('infoPanelOverlay');
      if (infoPanel) infoPanel.classList.remove('active');
      if (typeof Chat !== 'undefined') Chat._infoPanelOpen = false;
    }

    slideMenu.classList.toggle('active');
    menuOverlay.classList.toggle('active');
    // Prevent body scroll when menu is open
    document.body.style.overflow =
      slideMenu.classList.contains('active') ? 'hidden' : '';
  },

  openCreateModal() {
    document.getElementById('modalCreate').classList.add('active');
    document.getElementById('newGroupName').focus();
  },

  closeModal() {
    document.getElementById('modalCreate').classList.remove('active');
    document.getElementById('newGroupName').value = '';
  },

  async processCreateGroup() {
    const nameInput = document.getElementById('newGroupName');
    const name = nameInput.value.trim();
    if (!name) { nameInput.style.borderColor = 'var(--danger)'; return; }

    try {
      const result = await API.request('/api/chats/create', {
        method: 'POST',
        body: JSON.stringify({ owner_id: State.currentUser.id, name: name, is_group: true })
      });
      if (result.status === "success") {
        this.closeModal();
        await this.render();
        Chat.open(result.chat.id, result.chat.name);
      }
    } catch (err) { alert("Не удалось создать группу: " + err.message); }
  }
};

// Global shortcuts
function toggleSearch() { Sidebar.toggleSearch(); }
function filterChats(q) { Sidebar.filter(q); }
function toggleMenu() { Sidebar.toggleMenu(); }
function closeModal() { Sidebar.closeModal(); }
function processCreateGroup() { Sidebar.processCreateGroup(); }
