/* ===================================================
   PULSE CHAT v2.0 — Invite Module (Виральность)
   URL detection → join page → link creation/share
   =================================================== */

const Invite = {
  _code: null,
  _info: null,

  // ══════════════════════════════════════════
  // URL DETECTION: /join/CODE or ?invite=CODE
  // ══════════════════════════════════════════
  checkUrl() {
    const path = window.location.pathname;
    const params = new URLSearchParams(window.location.search);

    const joinMatch = path.match(/^\/join\/([A-Za-z0-9_-]+)/);
    if (joinMatch) { this._loadInvite(joinMatch[1]); return true; }

    const code = params.get('invite');
    if (code) { this._loadInvite(code); return true; }

    return false;
  },

  // ══════════════════════════════════════════
  // LOAD INVITE INFO → SHOW PAGE
  // ══════════════════════════════════════════
  async _loadInvite(code) {
    this._code = code;
    Router.navigate('invite');

    document.getElementById('inviteLoading').style.display = 'flex';
    document.getElementById('inviteContent').style.display = 'none';
    document.getElementById('inviteError').style.display = 'none';

    try {
      const info = await API.request(`/api/invites/${code}`);

      if (info.status === 'error') {
        this._showError(info.detail || 'Ссылка недействительна');
        return;
      }

      this._info = info;
      this._render(info);
    } catch (err) {
      console.error('Invite error:', err);
      this._showError('Не удалось загрузить приглашение');
    }
  },

  _render(info) {
    document.getElementById('inviteLoading').style.display = 'none';
    document.getElementById('inviteContent').style.display = 'flex';

    // Avatar
    const color = info.avatar_color || '#54a9eb';
    const initials = (info.chat_name || '??').substring(0, 2).toUpperCase();
    document.getElementById('inviteAvatar').innerHTML =
      `<div style="background:${color};width:100%;height:100%;display:flex;align-items:center;justify-content:center;border-radius:50%;color:#fff;font-weight:700;font-size:36px">${initials}</div>`;

    // Name
    document.getElementById('inviteGroupName').textContent = info.chat_name || 'Группа';

    // Meta
    const members = info.member_count || info.members || 0;
    let meta = `<i class="fa-solid fa-users" style="margin-right:5px"></i>${members} ${this._plural(members, 'участник', 'участника', 'участников')}`;
    if (info.topics > 0) {
      meta += `<span style="margin:0 8px;opacity:0.3">•</span><i class="fa-solid fa-layer-group" style="margin-right:5px"></i>${info.topics} ${this._plural(info.topics, 'ветка', 'ветки', 'веток')}`;
    }
    document.getElementById('inviteMeta').innerHTML = meta;

    // Button
    const btn = document.getElementById('inviteJoinBtn');
    btn.disabled = false;
    btn.style.background = '';
    if (State.currentUser) {
      btn.innerHTML = '<i class="fa-solid fa-right-to-bracket" style="margin-right:8px"></i>Вступить в группу';
    } else {
      btn.innerHTML = '<i class="fa-solid fa-arrow-right-to-bracket" style="margin-right:8px"></i>Войти и вступить';
    }
  },

  // ══════════════════════════════════════════
  // JOIN GROUP
  // ══════════════════════════════════════════
  async join() {
    if (!State.currentUser) {
      localStorage.setItem('pulse-pending-invite', this._code);
      Router.navigate('auth');
      return;
    }

    const btn = document.getElementById('inviteJoinBtn');
    btn.disabled = true;
    btn.innerHTML = '<div class="auth-spinner" style="width:20px;height:20px;border-width:2px;margin:0 auto"></div>';

    try {
      const res = await API.request(`/api/invites/${this._code}/join`, {
        method: 'POST',
        body: JSON.stringify({ user_id: State.currentUser.id })
      });

      if (res.status === 'error') {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-xmark" style="margin-right:8px"></i>${res.detail || 'Ошибка'}`;
        setTimeout(() => {
          btn.innerHTML = '<i class="fa-solid fa-right-to-bracket" style="margin-right:8px"></i>Попробовать снова';
          btn.disabled = false;
        }, 2500);
        return;
      }

      // Success
      btn.style.background = 'var(--success)';
      const already = res.status === 'already_member';
      btn.innerHTML = `<i class="fa-solid fa-check" style="margin-right:8px"></i>${already ? 'Вы уже участник' : 'Добро пожаловать!'}`;

      history.replaceState(null, '', '/');

      setTimeout(() => {
        Router.navigate('chat');
        Chat.open(res.chat_id, res.chat_name || this._info?.chat_name || 'Группа');
      }, 1200);
    } catch (err) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-right-to-bracket" style="margin-right:8px"></i>Попробовать снова';
    }
  },

  // ══════════════════════════════════════════
  // PENDING: After auth, check saved invite
  // ══════════════════════════════════════════
  checkPending() {
    const code = localStorage.getItem('pulse-pending-invite');
    if (code) {
      localStorage.removeItem('pulse-pending-invite');
      this._loadInvite(code);
      return true;
    }
    return false;
  },

  // ══════════════════════════════════════════
  // CREATE + COPY: For info panel button
  // ══════════════════════════════════════════
  async createAndCopy() {
    if (!State.currentChatId || !State.currentUser) return;

    try {
      const res = await API.request('/api/invites/create', {
        method: 'POST',
        body: JSON.stringify({
          chat_id: State.currentChatId,
          user_id: State.currentUser.id,
          max_uses: 0,
          expires_hours: 0
        })
      });

      if (res.status === 'error') {
        alert(res.detail || 'Ошибка создания ссылки');
        return null;
      }

      const base = location.origin || `${location.protocol}//${location.host}`;
      const link = `${base}/join/${res.code}`;

      try { await navigator.clipboard.writeText(link); }
      catch { this._fallbackCopy(link); }

      this._toast(link);
      return link;
    } catch (err) {
      alert('Ошибка сети');
      return null;
    }
  },

  // ══════════════════════════════════════════
  // SHARE: Native share API (mobile) or copy
  // ══════════════════════════════════════════
  async share(chatId, chatName) {
    const chatIdToUse = chatId || State.currentChatId;
    const nameToUse = chatName || Chat.chatMeta?.name || 'группу';

    // Generate link first
    let link;
    try {
      const res = await API.request('/api/invites/create', {
        method: 'POST',
        body: JSON.stringify({ chat_id: chatIdToUse, user_id: State.currentUser.id, max_uses: 0, expires_hours: 0 })
      });
      if (res.status !== 'success') { alert(res.detail || 'Ошибка'); return; }
      const base = location.origin || `${location.protocol}//${location.host}`;
      link = `${base}/join/${res.code}`;
    } catch { alert('Ошибка сети'); return; }

    // Try native share
    if (navigator.share) {
      try {
        await navigator.share({
          title: `Присоединяйся к «${nameToUse}» в Pulse`,
          text: `Тебя приглашают в «${nameToUse}»!`,
          url: link
        });
        return;
      } catch (e) { if (e.name === 'AbortError') return; }
    }

    // Fallback: copy
    try { await navigator.clipboard.writeText(link); } catch { this._fallbackCopy(link); }
    this._toast(link);
  },

  // ══════════════════════════════════════════
  // MANAGE: Modal with all active links
  // ══════════════════════════════════════════
  async showManagePanel() {
    if (!State.currentChatId) return;

    document.getElementById('modalInviteManage')?.remove();

    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'modalInviteManage';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
    modal.innerHTML = `
      <div class="modal-content" style="text-align:left;max-width:480px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
          <h3 style="margin:0">Ссылки-приглашения</h3>
          <button class="icon-btn" onclick="document.getElementById('modalInviteManage').remove()" style="width:32px;height:32px"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <div id="inviteManageList" style="max-height:300px;overflow-y:auto">
          <div style="text-align:center;padding:20px;color:var(--text-2)"><div class="auth-spinner" style="width:24px;height:24px;border-width:2px;margin:0 auto 8px"></div>Загрузка...</div>
        </div>
        <div style="margin-top:16px;display:flex;gap:8px">
          <button class="btn-primary" onclick="Invite._createFromManage()" style="flex:1;padding:10px">
            <i class="fa-solid fa-plus" style="margin-right:6px"></i>Создать ссылку
          </button>
          <button class="btn-outline" onclick="Invite.share()" style="padding:10px 16px">
            <i class="fa-solid fa-share-nodes"></i>
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    // Load links
    try {
      const invites = await API.request(`/api/invites/chat/${State.currentChatId}?user_id=${State.currentUser.id}`);
      const list = document.getElementById('inviteManageList');

      if (!invites || invites.length === 0) {
        list.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-2)"><i class="fa-solid fa-link" style="font-size:32px;display:block;margin-bottom:8px;opacity:0.2"></i>Нет активных ссылок</div>';
        return;
      }

      const base = location.origin || `${location.protocol}//${location.host}`;
      list.innerHTML = invites.map(inv => {
        const link = `${base}/join/${inv.code}`;
        const uses = inv.max_uses > 0 ? `${inv.uses}/${inv.max_uses}` : `${inv.uses} исп.`;
        return `
          <div class="invite-link-row">
            <div style="flex:1;min-width:0">
              <div style="font-size:13px;font-family:var(--font-mono);color:var(--accent);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">/join/${inv.code}</div>
              <div style="font-size:12px;color:var(--text-2);margin-top:2px">${uses}</div>
            </div>
            <button class="icon-btn" onclick="navigator.clipboard.writeText('${link}');this.innerHTML='<i class=\\'fa-solid fa-check\\'></i>';setTimeout(()=>this.innerHTML='<i class=\\'fa-solid fa-copy\\'></i>',1500)" style="width:36px;height:36px;font-size:14px" title="Копировать"><i class="fa-solid fa-copy"></i></button>
          </div>
        `;
      }).join('');
    } catch {
      document.getElementById('inviteManageList').innerHTML = '<div style="text-align:center;padding:20px;color:var(--danger)">Ошибка загрузки</div>';
    }
  },

  async _createFromManage() {
    const link = await this.createAndCopy();
    if (link) {
      document.getElementById('modalInviteManage')?.remove();
      this.showManagePanel();
    }
  },

  // ══════════════════════════════════════════
  // UI HELPERS
  // ══════════════════════════════════════════
  _toast(link) {
    document.querySelector('.invite-toast')?.remove();
    const t = document.createElement('div');
    t.className = 'invite-toast';
    t.innerHTML = `<i class="fa-solid fa-check-circle" style="color:var(--success);font-size:18px"></i><div style="flex:1;min-width:0"><div style="font-weight:600;font-size:14px">Ссылка скопирована!</div><div style="font-size:12px;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px">${link}</div></div>`;
    document.body.appendChild(t);
    requestAnimationFrame(() => t.classList.add('visible'));
    setTimeout(() => { t.classList.remove('visible'); setTimeout(() => t.remove(), 300); }, 3000);
  },

  _showError(text) {
    document.getElementById('inviteLoading').style.display = 'none';
    document.getElementById('inviteContent').style.display = 'none';
    document.getElementById('inviteError').style.display = 'flex';
    document.getElementById('inviteErrorText').textContent = text;
  },

  _fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); document.execCommand('copy');
    document.body.removeChild(ta);
  },

  _plural(n, a, b, c) {
    const m = n % 10, h = n % 100;
    if (m === 1 && h !== 11) return a;
    if (m >= 2 && m <= 4 && (h < 10 || h >= 20)) return b;
    return c;
  },
};
