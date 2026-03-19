/* ===================================================
   PULSE CHAT — Polls, Link Preview, @Mentions
   Day 10 features
   =================================================== */

// ══════════════════════════════════════════
// POLLS
// ══════════════════════════════════════════
const Polls = {

  openCreateModal() {
    document.getElementById('modalPoll')?.remove();
    const m = document.createElement('div');
    m.id = 'modalPoll';
    m.className = 'modal active';
    m.onclick = e => { if (e.target === m) m.remove(); };
    m.innerHTML = `
      <div class="modal-content" style="text-align:left;max-width:460px">
        <h3 style="text-align:center;margin-bottom:16px">📊 Создать опрос</h3>
        <input type="text" id="pollQuestion" placeholder="Вопрос..." maxlength="200"
          style="width:100%;padding:12px;background:var(--input-bg);border:1px solid var(--input-border);border-radius:var(--radius);color:var(--text-0);font-size:15px;margin-bottom:12px">
        <div id="pollOptionsContainer">
          <input type="text" class="poll-option-input" placeholder="Вариант 1" maxlength="100"
            style="width:100%;padding:10px;background:var(--input-bg);border:1px solid var(--input-border);border-radius:var(--radius);color:var(--text-0);font-size:14px;margin-bottom:8px">
          <input type="text" class="poll-option-input" placeholder="Вариант 2" maxlength="100"
            style="width:100%;padding:10px;background:var(--input-bg);border:1px solid var(--input-border);border-radius:var(--radius);color:var(--text-0);font-size:14px;margin-bottom:8px">
        </div>
        <button class="btn-outline" onclick="Polls._addOption()" style="width:100%;padding:8px;font-size:13px;margin-bottom:16px">
          <i class="fa-solid fa-plus" style="margin-right:6px"></i>Добавить вариант
        </button>
        <label style="display:flex;align-items:center;gap:8px;font-size:14px;color:var(--text-2);margin-bottom:16px;cursor:pointer">
          <input type="checkbox" id="pollAnonymous" checked style="width:18px;height:18px"> Анонимный опрос
        </label>
        <div class="modal-actions">
          <button class="btn-outline" onclick="document.getElementById('modalPoll').remove()">Отмена</button>
          <button class="btn-primary" onclick="Polls.create()">Создать</button>
        </div>
      </div>
    `;
    document.body.appendChild(m);
    document.getElementById('pollQuestion').focus();
  },

  _addOption() {
    const container = document.getElementById('pollOptionsContainer');
    const count = container.querySelectorAll('.poll-option-input').length;
    if (count >= 10) return;
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'poll-option-input';
    input.placeholder = `Вариант ${count + 1}`;
    input.maxLength = 100;
    input.style = 'width:100%;padding:10px;background:var(--input-bg);border:1px solid var(--input-border);border-radius:var(--radius);color:var(--text-0);font-size:14px;margin-bottom:8px';
    container.appendChild(input);
    input.focus();
  },

  async create() {
    const question = document.getElementById('pollQuestion')?.value.trim();
    if (!question) return alert('Введите вопрос');
    
    const inputs = document.querySelectorAll('.poll-option-input');
    const options = Array.from(inputs).map(i => i.value.trim()).filter(v => v);
    if (options.length < 2) return alert('Минимум 2 варианта');
    
    const anonymous = document.getElementById('pollAnonymous')?.checked ?? true;
    const chatId = Chat.currentTopicId || State.currentChatId;
    if (!chatId) return;

    try {
      const r = await API.request('/api/polls/create', {
        method: 'POST',
        body: JSON.stringify({ chat_id: chatId, user_id: State.currentUser.id, question, options, anonymous })
      });
      if (r.status === 'success') {
        document.getElementById('modalPoll')?.remove();
        if (r.message) {
          Chat.messages.push(r.message);
          Chat._renderMessages();
        }
        Sidebar.render();
      } else {
        alert(r.detail || 'Ошибка');
      }
    } catch (e) {
      alert('Ошибка создания опроса');
    }
  },

  // Render poll inside message bubble
  async renderPoll(pollId, msgId) {
    const container = document.getElementById(`poll_${msgId}`);
    if (!container) return;
    container.innerHTML = '<div style="text-align:center;padding:12px;color:var(--text-2)"><div class="auth-spinner" style="width:20px;height:20px;border-width:2px;margin:0 auto"></div></div>';

    try {
      const poll = await API.request(`/api/polls/${pollId}?user_id=${State.currentUser.id}`);
      if (poll.status === 'error') { container.innerHTML = '❌ Опрос не найден'; return; }

      const hasVoted = poll.my_votes.length > 0;
      let html = `<div class="poll-question">${escapeHTML(poll.question)}</div>`;
      
      poll.options.forEach(opt => {
        const isMyVote = poll.my_votes.includes(opt.id);
        const pct = hasVoted ? opt.percent : 0;
        html += `
          <div class="poll-option ${isMyVote ? 'voted' : ''} ${hasVoted ? 'show-results' : ''}" onclick="Polls.vote('${pollId}', ${opt.id}, '${msgId}')">
            <div class="poll-option-fill" style="width:${pct}%"></div>
            <div class="poll-option-text">${escapeHTML(opt.text)}</div>
            ${hasVoted ? `<div class="poll-option-pct">${pct}%</div>` : ''}
            ${isMyVote ? '<i class="fa-solid fa-check poll-option-check"></i>' : ''}
          </div>
        `;
      });
      
      html += `<div class="poll-footer">${poll.anonymous ? '👤 Анонимный · ' : ''}${poll.total_votes} голос${Polls._plural(poll.total_votes)}</div>`;
      container.innerHTML = html;
    } catch (e) {
      container.innerHTML = '<div style="color:var(--danger);padding:8px">Ошибка загрузки</div>';
    }
  },

  async vote(pollId, optionId, msgId) {
    try {
      await API.request(`/api/polls/${pollId}/vote`, {
        method: 'POST',
        body: JSON.stringify({ user_id: State.currentUser.id, option_id: optionId })
      });
      // Refresh poll display
      this.renderPoll(pollId, msgId);
    } catch (e) {
      console.error('Vote error:', e);
    }
  },

  _plural(n) {
    const m = n % 10, h = n % 100;
    if (m === 1 && h !== 11) return '';
    if (m >= 2 && m <= 4 && (h < 10 || h >= 20)) return 'а';
    return 'ов';
  },
};

// ══════════════════════════════════════════
// LINK PREVIEW
// ══════════════════════════════════════════
const LinkPreview = {
  _cache: {},

  // Extract first URL from text
  extractUrl(text) {
    const match = text?.match(/(https?:\/\/[^\s<]+)/);
    return match ? match[1] : null;
  },

  // Fetch and render preview card below message
  async loadPreview(url, containerId) {
    if (this._cache[url]) {
      this._renderCard(this._cache[url], containerId);
      return;
    }

    try {
      const data = await API.request(`/api/link-preview?url=${encodeURIComponent(url)}`);
      if (data.status === 'success' && data.title) {
        this._cache[url] = data;
        this._renderCard(data, containerId);
      }
    } catch (e) {}
  },

  _renderCard(data, containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
      <a href="${escapeHTML(data.url)}" target="_blank" rel="noopener" class="link-preview-card">
        ${data.image ? `<div class="link-preview-img"><img src="${escapeHTML(data.image)}" alt="" loading="lazy"></div>` : ''}
        <div class="link-preview-body">
          <div class="link-preview-site">${escapeHTML(data.site_name || '')}</div>
          <div class="link-preview-title">${escapeHTML(data.title)}</div>
          ${data.description ? `<div class="link-preview-desc">${escapeHTML(data.description)}</div>` : ''}
        </div>
      </a>
    `;
  },
};

// ══════════════════════════════════════════
// @MENTIONS AUTOCOMPLETE
// ══════════════════════════════════════════
const Mentions = {
  _members: [],
  _visible: false,
  _selectedIdx: 0,

  async loadMembers(chatId) {
    try {
      this._members = await API.request(`/api/members/${chatId}`);
    } catch (e) {
      this._members = [];
    }
  },

  // Called on every input change
  check(textarea) {
    const text = textarea.value;
    const cursorPos = textarea.selectionStart;
    
    // Find @word at cursor
    const beforeCursor = text.substring(0, cursorPos);
    const match = beforeCursor.match(/@(\w*)$/);
    
    if (!match) {
      this.hide();
      return;
    }

    const query = match[1].toLowerCase();
    const filtered = this._members.filter(m => 
      m.name.toLowerCase().includes(query) || 
      m.username.toLowerCase().includes(query)
    ).slice(0, 6);

    if (filtered.length === 0) {
      this.hide();
      return;
    }

    this._showDropdown(filtered, textarea, match.index);
  },

  _showDropdown(members, textarea, atIndex) {
    let dropdown = document.getElementById('mentionDropdown');
    if (!dropdown) {
      dropdown = document.createElement('div');
      dropdown.id = 'mentionDropdown';
      dropdown.className = 'mention-dropdown';
      textarea.parentElement.appendChild(dropdown);
    }

    this._visible = true;
    this._selectedIdx = 0;

    dropdown.innerHTML = members.map((m, i) => `
      <div class="mention-item ${i === 0 ? 'active' : ''}" onmousedown="Mentions.select(${i})" data-idx="${i}">
        <div class="mention-avatar" style="background:${AVATAR_COLORS[m.user_id % AVATAR_COLORS.length]}">${m.name.substring(0,1).toUpperCase()}</div>
        <div class="mention-name">${escapeHTML(m.name)}</div>
        ${m.username ? `<div class="mention-username">@${escapeHTML(m.username)}</div>` : ''}
      </div>
    `).join('');
    dropdown.style.display = 'block';
    dropdown._members = members;
    dropdown._atIndex = atIndex;
  },

  hide() {
    const dropdown = document.getElementById('mentionDropdown');
    if (dropdown) dropdown.style.display = 'none';
    this._visible = false;
  },

  select(idx) {
    const dropdown = document.getElementById('mentionDropdown');
    if (!dropdown || !dropdown._members) return;
    
    const member = dropdown._members[idx];
    if (!member) return;

    const textarea = document.getElementById('msgInput');
    const text = textarea.value;
    const atIndex = dropdown._atIndex;
    const cursorPos = textarea.selectionStart;
    
    // Replace @partial with @username
    const mention = `@${member.username || member.name} `;
    const newText = text.substring(0, atIndex) + mention + text.substring(cursorPos);
    textarea.value = newText;
    textarea.selectionStart = textarea.selectionEnd = atIndex + mention.length;
    textarea.focus();
    
    this.hide();
    Chat._updateSendBtn();
  },

  // Handle keyboard navigation in dropdown
  handleKey(e) {
    if (!this._visible) return false;
    const dropdown = document.getElementById('mentionDropdown');
    if (!dropdown?._members) return false;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this._selectedIdx = Math.min(this._selectedIdx + 1, dropdown._members.length - 1);
      this._highlightItem(dropdown);
      return true;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      this._selectedIdx = Math.max(this._selectedIdx - 1, 0);
      this._highlightItem(dropdown);
      return true;
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      this.select(this._selectedIdx);
      return true;
    }
    if (e.key === 'Escape') {
      this.hide();
      return true;
    }
    return false;
  },

  _highlightItem(dropdown) {
    dropdown.querySelectorAll('.mention-item').forEach((item, i) => {
      item.classList.toggle('active', i === this._selectedIdx);
    });
  },
};
