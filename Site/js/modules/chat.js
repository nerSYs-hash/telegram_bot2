/* ===================================================
   PULSE CHAT — Chat Module (Full Feature Edition)
   Pin, Reactions, Forward, Search, Emoji, Info Panel
   =================================================== */

const REACTIONS = ['👍','❤️','😂','😮','😢','🔥','👎','🎉'];

const Chat = {
  ws: null,
  messages: [],
  topics: [],
  chatMeta: null,
  currentTopicId: null,
  currentTopicTitle: null,
  pinnedMsg: null,
  _typingTimeout: null,
  _editingMsg: null,
  _editHighlightEl: null,
  _searchOpen: false,
  _emojiOpen: false,
  _infoPanelOpen: false,
  _forwardingMsg: null,

  // ══════════════════════════════════════════
  // OPEN CHAT
  // ══════════════════════════════════════════
  async open(chatId, chatName, chatMeta) {
    State.currentChatId = chatId;
    this.currentTopicId = null;
    this.currentTopicTitle = null;
    this.pinnedMsg = null;
    this._closeAllPanels();

    const name = chatName || chatMeta?.name || chatId;
    const color = chatMeta?.avatar_color || '#54a9eb';
    const initials = name.substring(0, 2).toUpperCase();
    const isBot = chatMeta?.is_bot || false;
    const isGroup = chatMeta?.is_group || false;

    this.chatMeta = { id: chatId, name, color, isBot, isGroup, peerId: chatMeta?.peer_id || null };

    // Header
    const av = document.getElementById('chatAvatar');
    if (isBot) {
      av.innerHTML = `<div style="background:#0088cc;width:40px;height:40px;display:flex;align-items:center;justify-content:center;border-radius:50%;color:#fff;font-size:16px"><i class="fa-solid fa-robot"></i></div>`;
    } else {
      av.innerHTML = makeAvatarHTML(name, chatId?.charCodeAt?.(0) || 0, 40);
    }
    document.getElementById('chatName').textContent = name;

    // Call buttons (only for DM, non-bot)
    const showCalls = !isBot && !isGroup && chatMeta?.peer_id;
    document.getElementById('callAudioBtn').style.display = showCalls ? '' : 'none';
    document.getElementById('callVideoBtn').style.display = showCalls ? '' : 'none';

    const st = document.getElementById('chatStatus');
    if (isBot) { st.textContent = 'бот'; st.className = 'chat-header-status online'; }
    else if (isGroup) { st.textContent = 'сообщество'; st.className = 'chat-header-status'; }
    else { st.textContent = chatMeta?.online ? 'в сети' : ''; st.className = chatMeta?.online ? 'chat-header-status online' : 'chat-header-status'; }

    if (isGroup) {
      await this._loadTopics(chatId);
      this._renderTopics();
      this._hideInputArea();
    } else {
      await this._loadMessages(chatId);
      // Bot welcome message if empty
      if (isBot && this.messages.length === 0) {
        this.messages.push({
          id: 'bot_welcome', from_id: 0, from_name: 'Pulse AI Bot',
          text: '👋 Привет! Я — Pulse AI Bot.\n\nНапиши /help чтобы узнать все мои команды.\n\nПопробуй:\n💰 /balance — твой баланс\n🏆 /top — топ-5 богачей\n🎲 /dice — бросить кубик\n🪙 /daily — ежедневный бонус',
          ts: Date.now(), reactions: {},
        });
      }
      this._renderMessages();
      this._showInputArea();
      if (!isBot) this._connectWS(chatId); // No WS for bot chat
    }

    if (State.isMobile) document.getElementById('chatView').classList.add('active');
    Sidebar.render();
    if (typeof Mentions !== 'undefined') Mentions.loadMembers(chatId);
  },

  _closeAllPanels() {
    this._searchOpen = false;
    this._emojiOpen = false;
    this._infoPanelOpen = false;
    const sp = document.getElementById('chatSearchPanel');
    if (sp) sp.style.display = 'none';
    const ep = document.getElementById('emojiPicker');
    if (ep) ep.style.display = 'none';
    const ip = document.getElementById('infoPanelOverlay');
    if (ip) ip.classList.remove('active');
  },

  // ══════════════════════════════════════════
  // TOPICS
  // ══════════════════════════════════════════
  async _loadTopics(chatId) {
    try { this.topics = await API.request(`/api/topics/${chatId}`); }
    catch (e) { this.topics = []; }
  },

  _renderTopics() {
    const area = document.getElementById('messagesArea');
    if (this.topics.length === 0) {
      area.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;z-index:1;position:relative"><i class="fa-solid fa-layer-group" style="font-size:56px;color:var(--text-2);opacity:0.15"></i><div style="color:var(--text-2);font-size:15px;text-align:center;max-width:260px">Нет веток. Создайте первую!</div><button class="btn-primary" onclick="Chat.openCreateTopicModal()" style="margin-top:8px"><i class="fa-solid fa-plus" style="margin-right:6px"></i>Создать ветку</button></div>`;
      return;
    }
    let h = '<div class="topics-container"><div class="topics-header"><span class="topics-count">' + this.topics.length + ' ' + this._plural(this.topics.length,'ветка','ветки','веток') + '</span><button class="btn-primary" onclick="Chat.openCreateTopicModal()" style="padding:6px 16px;font-size:13px"><i class="fa-solid fa-plus" style="margin-right:4px"></i>Новая</button></div>';
    this.topics.forEach(t => {
      const icon = this._topicIcon(t.title);
      h += `<div class="topic-card" onclick="Chat.openTopic('${t.id}','${escapeHTML(t.title)}')"><div class="topic-icon">${icon}</div><div class="topic-info"><div class="topic-title">${escapeHTML(t.title)}</div><div class="topic-preview">${t.last_msg||'Нет сообщений'}</div></div><div class="topic-meta">${t.msg_count?'<span class="topic-count">'+t.msg_count+'</span>':''}<i class="fa-solid fa-chevron-right" style="font-size:12px;color:var(--text-2)"></i></div></div>`;
    });
    area.innerHTML = h + '</div>';
  },

  _topicIcon(title) {
    const t = title.toLowerCase();
    if (t.includes('общ')||t.includes('флуд')||t.includes('чат')) return '💬';
    if (t.includes('новост')||t.includes('анонс')) return '📢';
    if (t.includes('вопрос')||t.includes('помощ')) return '❓';
    if (t.includes('фото')||t.includes('медиа')||t.includes('мем')) return '📷';
    if (t.includes('правил')) return '📋';
    return '📑';
  },

  _plural(n,a,b,c) { const m=n%10,h=n%100; if(m===1&&h!==11)return a; if(m>=2&&m<=4&&(h<10||h>=20))return b; return c; },

  async openTopic(topicId, topicTitle) {
    this.currentTopicId = topicId;
    this.currentTopicTitle = topicTitle;
    document.getElementById('chatName').textContent = topicTitle;
    document.getElementById('chatStatus').textContent = this.chatMeta?.name || '';
    document.getElementById('chatStatus').className = 'chat-header-status';
    await this._loadMessages(topicId);
    this._renderMessages();
    this._showInputArea();
    this._connectWS(topicId);
    setTimeout(() => document.getElementById('msgInput')?.focus(), 200);
  },

  openCreateTopicModal() { document.getElementById('modalCreateTopic').classList.add('active'); document.getElementById('newTopicName').value = ''; document.getElementById('newTopicName').focus(); },
  closeTopicModal() { document.getElementById('modalCreateTopic').classList.remove('active'); },
  async processCreateTopic() {
    const input = document.getElementById('newTopicName');
    const title = input.value.trim();
    if (!title) { input.style.borderColor = 'var(--danger)'; return; }
    try {
      const r = await API.request('/api/topics/create', { method:'POST', body:JSON.stringify({ chat_id:State.currentChatId, title, created_by:State.currentUser.id }) });
      if (r.status==='success') { this.closeTopicModal(); await this._loadTopics(State.currentChatId); this._renderTopics(); }
    } catch (e) { alert('Ошибка: '+e.message); }
  },

  // ══════════════════════════════════════════
  // MESSAGES: Load + Render
  // ══════════════════════════════════════════
  async _loadMessages(chatId) {
    try {
      const data = await API.request(`/api/messages/${chatId}?user_id=${State.currentUser.id}`);
      this.messages = data.messages || [];
      this.pinnedMsg = data.pinned || null;
    } catch (e) { this.messages = []; this.pinnedMsg = null; }
  },

  _renderMessages() {
    const area = document.getElementById('messagesArea');
    let pinnedHTML = '';
    if (this.pinnedMsg) {
      pinnedHTML = `<div class="pinned-bar" onclick="Chat.scrollTo('${this.pinnedMsg.id}')">
        <div class="pinned-bar-accent"></div>
        <div class="pinned-bar-content">
          <div class="pinned-bar-label">Закреплённое сообщение</div>
          <div class="pinned-bar-text">${escapeHTML(this.pinnedMsg.text)}</div>
        </div>
        <button class="icon-btn" onclick="event.stopPropagation();Chat.unpinMsg()" style="width:30px;height:30px;font-size:13px"><i class="fa-solid fa-xmark"></i></button>
      </div>`;
    }

    area.innerHTML = pinnedHTML + '<div class="messages-container" id="messagesContainer"></div><div class="scroll-to-bottom" id="scrollBottomBtn" onclick="Chat._scrollToBottom()"><i class="fa-solid fa-chevron-down"></i><span class="scroll-badge" id="scrollBadge" style="display:none">0</span></div>';
    const mc = document.getElementById('messagesContainer');
    const myId = State.currentUser?.id;
    let lastDate = null;

    if (this.messages.length === 0) {
      mc.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-2);opacity:0.6"><i class="fa-regular fa-comment-dots" style="font-size:48px;display:block;margin-bottom:12px"></i>Начните общение!</div>';
      return;
    }

    this.messages.forEach((msg, idx) => {
      const msgDate = new Date(msg.ts).toDateString();
      if (msgDate !== lastDate) {
        const sep = document.createElement('div');
        sep.className = 'date-separator';
        sep.innerHTML = `<span>${formatDateSep(msg.ts)}</span>`;
        mc.appendChild(sep);
        lastDate = msgDate;
      }

      const isOwn = String(msg.from_id) === String(myId);
      const row = document.createElement('div');
      row.className = `msg-row ${isOwn ? 'own' : 'other'}`;
      row.dataset.msgId = msg.id;

      const prev = idx > 0 ? this.messages[idx-1] : null;
      const samePrev = prev && prev.from_id === msg.from_id && (msg.ts - prev.ts < 120000);

      let senderHTML = '';
      if (!isOwn && (this.chatMeta?.isGroup || this.currentTopicId) && !samePrev && msg.from_name)
        senderHTML = `<div class="msg-sender" style="color:${getAvatarColor(msg.from_id||0)}">${msg.from_name}</div>`;

      let replyHTML = '';
      if (msg.reply_to) {
        const rp = this.messages.find(m => m.id === msg.reply_to);
        if (rp) replyHTML = `<div class="msg-reply" onclick="Chat.scrollTo('${rp.id}')"><div class="msg-reply-name">${String(rp.from_id)===String(myId)?'Вы':(rp.from_name||'')}</div><div class="msg-reply-text">${escapeHTML(rp.text)}</div></div>`;
      }

      // Forwarded
      let fwdHTML = '';
      if (msg.forwarded_from) fwdHTML = `<div class="msg-forwarded"><i class="fa-solid fa-share" style="margin-right:4px;font-size:11px"></i>Переслано от ${escapeHTML(msg.forwarded_from)}</div>`;

      let statusHTML = '';
      if (isOwn) {
        if (msg.status==='failed') statusHTML = '<i class="fa-solid fa-exclamation-circle msg-status" style="color:var(--danger)"></i>';
        else if (msg.status==='read') statusHTML = '<i class="fa-solid fa-check-double msg-status read"></i>';
        else if (msg.status==='delivered') statusHTML = '<i class="fa-solid fa-check-double msg-status"></i>';
        else statusHTML = '<i class="fa-solid fa-check msg-status"></i>';
      }

      // Reactions
      let reactionsHTML = '';
      if (msg.reactions && Object.keys(msg.reactions).length > 0) {
        reactionsHTML = '<div class="msg-reactions">';
        for (const [emoji, users] of Object.entries(msg.reactions)) {
          const myReacted = users.includes(String(myId));
          reactionsHTML += `<span class="reaction-chip${myReacted?' my':''}" onclick="Chat.toggleReaction('${msg.id}','${emoji}')">${emoji} ${users.length}</span>`;
        }
        reactionsHTML += '</div>';
      }

      // Media content
      let mediaHTML = '';
      let isMediaOnly = false;
      if (msg.media_url) {
        if (msg.media_type === 'image') {
          // TG-style: time overlaid on image
          const timeOverlay = `<div class="msg-media-time"><span>${formatTime(msg.ts)}</span>${statusHTML}</div>`;
          mediaHTML = `<div class="msg-media"><img src="${msg.media_url}" alt="" loading="lazy" onclick="Chat.openLightbox('${msg.media_url}')">${timeOverlay}</div>`;
          // Check if image-only (no real text)
          const hasText = msg.text && !msg.text.startsWith('📎');
          if (!hasText) isMediaOnly = true;
        } else if (msg.media_type === 'video') {
          if (typeof MediaPlayer !== 'undefined') {
            mediaHTML = `<div class="msg-media">${MediaPlayer.renderVideo(msg.media_url, msg.id)}</div>`;
          } else {
            mediaHTML = `<div class="msg-media"><video src="${msg.media_url}" controls preload="metadata" style="max-width:100%;border-radius:12px"></video></div>`;
          }
        } else if (msg.media_type === 'voice') {
          const dur = msg._voiceDuration || Voice.parseDuration(msg.text) || 0;
          mediaHTML = Voice.renderPlayer(msg.media_url, msg.id, dur);
          const hasText = msg.text && !msg.text.startsWith('🎤');
          if (!hasText) isMediaOnly = false; // Voice always shows in bubble
        } else if (msg.media_type === 'audio') {
          const aTitle = (msg.media_name || 'Аудио').replace(/\.[^.]+$/, '');
          mediaHTML = `<div class="msg-audio-card" onclick="MediaPlayer.play('${msg.media_url}',${JSON.stringify(aTitle)},'')">
            <button class="voice-play-btn"><i class="fa-solid fa-play"></i></button>
            <div style="flex:1;min-width:0">
              <div style="font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHTML(aTitle)}</div>
              <div style="font-size:12px;color:var(--text-2)">Аудио</div>
            </div>
          </div>`;
        } else if (msg.media_type === 'poll') {
          // Poll - rendered async after DOM insert
          mediaHTML = `<div class="poll-container" id="poll_${msg.id}"><div style="text-align:center;padding:12px;color:var(--text-2)">Загрузка опроса...</div></div>`;
        } else {
          const icon = Chat._fileIcon(msg.media_name || 'file');
          mediaHTML = `<a href="${msg.media_url}" target="_blank" download class="msg-file-card"><i class="fa-solid ${icon}"></i><div class="msg-file-info"><div class="msg-file-name">${escapeHTML(msg.media_name || 'Файл')}</div><div class="msg-file-size">Скачать</div></div><i class="fa-solid fa-download" style="color:var(--accent);font-size:14px"></i></a>`;
        }
      }

      // Link preview (if message contains a URL and no media)
      let linkPreviewHTML = '';
      if (!msg.media_url && msg.text) {
        const url = typeof LinkPreview !== 'undefined' ? LinkPreview.extractUrl(msg.text) : null;
        if (url) {
          linkPreviewHTML = `<div class="link-preview-slot" id="lp_${msg.id}" data-url="${escapeHTML(url)}"></div>`;
        }
      }

      // Text (hide if it's just the auto-generated file caption)
      const isAutoCaption = msg.media_url && msg.text && (msg.text.startsWith('📎') || msg.text.startsWith('🎤') || msg.text.startsWith('📊'));
      const textContent = isAutoCaption ? '' : linkify(escapeHTML(msg.text));
      let textHTML = '';
      if (isMediaOnly) {
        // No text block for image-only messages (time is on the image)
        textHTML = '';
      } else {
        textHTML = textContent
          ? `<div class="msg-text">${textContent}<span class="msg-footer">${msg.edited?'<span style="font-size:11px;color:var(--text-3);margin-right:2px">ред.</span>':''}<span class="msg-time">${formatTime(msg.ts)}</span>${statusHTML}</span></div>`
          : `<div class="msg-text"><span class="msg-footer">${msg.edited?'<span style="font-size:11px;color:var(--text-3);margin-right:2px">ред.</span>':''}<span class="msg-time">${formatTime(msg.ts)}</span>${statusHTML}</span></div>`;
      }

      const bubbleClass = `msg-bubble${isMediaOnly ? ' media-only' : ''}`;
      row.innerHTML = `<div class="${bubbleClass}">${senderHTML}${fwdHTML}${replyHTML}${mediaHTML}${textHTML}${linkPreviewHTML}${reactionsHTML}</div>`;

      let tt;
      row.addEventListener('contextmenu', e => { e.preventDefault(); this._showContextMenu(e, msg); });
      row.addEventListener('touchstart', e => { tt = setTimeout(() => this._showContextMenu({ clientX:e.touches[0].clientX, clientY:e.touches[0].clientY }, msg), 500); });
      row.addEventListener('touchend', () => clearTimeout(tt));
      row.addEventListener('touchmove', () => clearTimeout(tt));

      mc.appendChild(row);
    });

    this._scrollToBottom();
    this._initScrollWatcher();

    // Post-render: load polls and link previews
    this.messages.forEach(msg => {
      if (msg.media_type === 'poll' && msg.media_url && typeof Polls !== 'undefined') {
        Polls.renderPoll(msg.media_url, msg.id);
      }
    });
    document.querySelectorAll('.link-preview-slot[data-url]').forEach(el => {
      if (typeof LinkPreview !== 'undefined') {
        LinkPreview.loadPreview(el.dataset.url, el.id);
      }
    });
  },

  _scrollToBottom() {
    const area = document.getElementById('messagesArea');
    requestAnimationFrame(() => { area.scrollTop = area.scrollHeight; });
    const btn = document.getElementById('scrollBottomBtn');
    if (btn) btn.classList.remove('visible');
  },

  _initScrollWatcher() {
    const area = document.getElementById('messagesArea');
    area.onscroll = () => {
      const btn = document.getElementById('scrollBottomBtn');
      if (!btn) return;
      const atBottom = area.scrollHeight - area.scrollTop - area.clientHeight < 120;
      btn.classList.toggle('visible', !atBottom);
    };
  },

  // ══════════════════════════════════════════
  // INPUT AREA
  // ══════════════════════════════════════════
  _hideInputArea() { const i=document.getElementById('inputArea'); if(i)i.style.display='none'; document.getElementById('replyPreview').style.display='none'; document.getElementById('voiceRecordBar').style.display='none'; },
  _showInputArea() { const i=document.getElementById('inputArea'); if(i)i.style.display='flex'; },

  showEmpty() {
    document.getElementById('messagesArea').innerHTML = '<div class="empty-state"><i class="fa-regular fa-comments"></i><span>Выберите чат для начала общения</span></div>';
    document.getElementById('chatName').textContent = 'Pulse Chat';
    document.getElementById('chatStatus').textContent = '';
    document.getElementById('chatAvatar').innerHTML = '';
    this._hideInputArea();
  },

  // ══════════════════════════════════════════
  // SEND / EDIT
  // ══════════════════════════════════════════
  async send() {
    const input = document.getElementById('msgInput');
    const text = input.value.trim();
    const hasMedia = !!this._pendingMedia;
    if (!text && !hasMedia) return;

    // Edit mode (text only)
    if (this._editingMsg) {
      if (!text) return;
      const msg = this._editingMsg;
      const old = msg.text;
      msg.text = text; msg.edited = true;
      this._renderMessages();
      this.cancelEdit();
      input.value = ''; input.style.height = 'auto'; this._updateSendBtn();
      try { await API.request(`/api/messages/${msg.id}/edit`, { method:'POST', body:JSON.stringify({ user_id:State.currentUser.id, text }) }); }
      catch (e) { msg.text = old; msg.edited = false; this._renderMessages(); }
      return;
    }

    // Normal send (with optional media)
    const targetId = this.currentTopicId || State.currentChatId;
    if (!targetId) return;
    const replyTo = State.replyTo?.id || null;
    const tempId = 'tmp_' + Date.now();

    // Upload media first if present
    let mediaUrl = null, mediaType = null, mediaName = null;
    if (hasMedia) {
      try {
        const uploadResult = await this._uploadFile(this._pendingMedia.file);
        if (uploadResult.status === 'success') {
          mediaUrl = uploadResult.url;
          mediaType = uploadResult.media_type;
          mediaName = uploadResult.original_name;
        } else {
          alert(uploadResult.detail || 'Ошибка загрузки файла');
          return;
        }
      } catch (e) {
        alert('Не удалось загрузить файл');
        return;
      }
      this.cancelMedia();
    }

    const msgText = text || (mediaName ? `📎 ${mediaName}` : '📎 Файл');
    const opt = {
      id: tempId, from_id: State.currentUser.id, from_name: State.currentUser.name,
      text: msgText, ts: Date.now(), status: 'sent', reply_to: replyTo, reactions: {},
      media_url: mediaUrl, media_type: mediaType, media_name: mediaName,
    };
    this.messages.push(opt);
    this._renderMessages();
    this.cancelReply();
    input.value = ''; input.style.height = 'auto'; this._updateSendBtn();

    try {
      // Show typing for bot chat
      const isBotChat = targetId === 'pulse_bot';
      if (isBotChat) this._showTyping('Pulse AI Bot');
      
      const r = await API.request(`/api/messages/${targetId}/send`, {
        method: 'POST',
        body: JSON.stringify({
          user_id: State.currentUser.id, text: msgText, reply_to: replyTo,
          media_url: mediaUrl, media_type: mediaType, media_name: mediaName,
        })
      });
      const i = this.messages.findIndex(m => m.id === tempId);
      if (i > -1 && r.message) {
        this.messages[i].id = r.message.id;
        this.messages[i].status = 'delivered';
      }
      // Bot reply — add with slight delay for natural feel
      if (r.bot_reply) {
        this._renderMessages();
        this._showTyping('Pulse AI Bot');
        await new Promise(res => setTimeout(res, 400 + Math.random() * 600));
        this.messages.push(r.bot_reply);
        if (typeof Notify !== 'undefined') Notify.playSound();
      }
      this._renderMessages();
    } catch (e) {
      const i = this.messages.findIndex(m => m.id === tempId);
      if (i > -1) { this.messages[i].status = 'failed'; this._renderMessages(); }
    }
    Sidebar.render();
  },

  // ══════════════════════════════════════════
  // MEDIA: Upload, Preview, Send
  // ══════════════════════════════════════════
  _pendingMedia: null,

  handleFileSelect(input) {
    const file = input.files?.[0];
    if (!file) return;
    input.value = ''; // Reset for re-select

    // Validate size
    if (file.size > 20 * 1024 * 1024) {
      alert('Файл слишком большой (макс. 20MB)');
      return;
    }

    // Store pending
    this._pendingMedia = { file, name: file.name, type: file.type };

    // Show preview
    const preview = document.getElementById('mediaPreview');
    const content = document.getElementById('mediaPreviewContent');
    preview.style.display = 'flex';

    if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file);
      content.innerHTML = `<img src="${url}" style="max-height:60px;border-radius:6px;margin-right:8px"><div><div style="font-size:13px;font-weight:600">${escapeHTML(file.name)}</div><div style="font-size:12px;color:var(--text-2)">${this._formatSize(file.size)}</div></div>`;
    } else if (file.type.startsWith('video/')) {
      content.innerHTML = `<i class="fa-solid fa-film" style="font-size:28px;color:var(--accent);margin-right:10px"></i><div><div style="font-size:13px;font-weight:600">${escapeHTML(file.name)}</div><div style="font-size:12px;color:var(--text-2)">${this._formatSize(file.size)}</div></div>`;
    } else {
      const icon = this._fileIcon(file.name);
      content.innerHTML = `<i class="fa-solid ${icon}" style="font-size:28px;color:var(--accent);margin-right:10px"></i><div><div style="font-size:13px;font-weight:600">${escapeHTML(file.name)}</div><div style="font-size:12px;color:var(--text-2)">${this._formatSize(file.size)}</div></div>`;
    }

    // Show send button
    document.getElementById('sendBtn').style.display = 'flex';
    document.getElementById('micBtn').style.display = 'none';
    document.getElementById('msgInput').focus();
  },

  cancelMedia() {
    this._pendingMedia = null;
    document.getElementById('mediaPreview').style.display = 'none';
    this._updateSendBtn();
  },

  async _uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', State.currentUser.id);

    const url = (API.baseUrl || '') + '/api/upload';
    const response = await fetch(url, { method: 'POST', body: formData });
    if (!response.ok) throw new Error('Upload failed');
    return await response.json();
  },

  _formatSize(bytes) {
    if (bytes < 1024) return bytes + ' Б';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ';
    return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
  },

  _fileIcon(name) {
    const ext = name.split('.').pop().toLowerCase();
    const map = {
      pdf: 'fa-file-pdf', doc: 'fa-file-word', docx: 'fa-file-word',
      xls: 'fa-file-excel', xlsx: 'fa-file-excel',
      zip: 'fa-file-zipper', rar: 'fa-file-zipper',
      mp3: 'fa-file-audio', ogg: 'fa-file-audio', wav: 'fa-file-audio',
      mp4: 'fa-file-video', webm: 'fa-file-video',
      txt: 'fa-file-lines',
    };
    return map[ext] || 'fa-file';
  },

  // Lightbox for images
  openLightbox(url) {
    document.getElementById('lightboxOverlay')?.remove();
    const lb = document.createElement('div');
    lb.id = 'lightboxOverlay';
    lb.className = 'lightbox-overlay';
    lb.onclick = () => lb.remove();
    lb.innerHTML = `<img src="${url}" class="lightbox-img"><button class="lightbox-close"><i class="fa-solid fa-xmark"></i></button>`;
    document.body.appendChild(lb);
  },

  // ══════════════════════════════════════════
  // REACTIONS
  // ══════════════════════════════════════════
  async toggleReaction(msgId, emoji) {
    const msg = this.messages.find(m => m.id === msgId);
    if (!msg) return;
    if (!msg.reactions) msg.reactions = {};
    const uid = String(State.currentUser.id);
    if (!msg.reactions[emoji]) msg.reactions[emoji] = [];
    const idx = msg.reactions[emoji].indexOf(uid);
    if (idx > -1) msg.reactions[emoji].splice(idx, 1);
    else msg.reactions[emoji].push(uid);
    if (msg.reactions[emoji].length === 0) delete msg.reactions[emoji];
    this._renderMessages();
    try { await API.request(`/api/messages/${msgId}/react`, { method:'POST', body:JSON.stringify({ user_id:State.currentUser.id, emoji }) }); }
    catch (e) { console.error(e); }
  },

  _showReactionPicker(e, msg) {
    document.querySelector('.reaction-picker')?.remove();
    const picker = document.createElement('div');
    picker.className = 'reaction-picker';
    REACTIONS.forEach(emoji => {
      const btn = document.createElement('span');
      btn.className = 'reaction-pick-btn';
      btn.textContent = emoji;
      btn.onclick = () => { this.toggleReaction(msg.id, emoji); picker.remove(); };
      picker.appendChild(btn);
    });
    picker.style.left = Math.min(e.clientX, innerWidth - 280) + 'px';
    picker.style.top = Math.max(e.clientY - 50, 10) + 'px';
    document.body.appendChild(picker);
    setTimeout(() => { document.addEventListener('click', function rm() { picker.remove(); document.removeEventListener('click', rm); }, { once:true }); }, 50);
  },

  // ══════════════════════════════════════════
  // PIN
  // ══════════════════════════════════════════
  async pinMsg(msg) {
    this.pinnedMsg = msg;
    this._renderMessages();
    const chatId = this.currentTopicId || State.currentChatId;
    try {
      await API.request(`/api/messages/${msg.id}/pin`, {
        method: 'POST',
        body: JSON.stringify({ chat_id: chatId, user_id: State.currentUser.id })
      });
    } catch (e) { console.error(e); }
  },

  async unpinMsg() {
    const chatId = this.currentTopicId || State.currentChatId;
    this.pinnedMsg = null;
    this._renderMessages();
    try {
      await API.request(`/api/messages/unpin`, {
        method: 'POST',
        body: JSON.stringify({ chat_id: chatId, user_id: State.currentUser.id })
      });
    } catch (e) { console.error(e); }
  },

  // ══════════════════════════════════════════
  // FORWARD
  // ══════════════════════════════════════════
  startForward(msg) {
    this._forwardingMsg = msg;
    document.getElementById('modalForward').classList.add('active');
    this._loadForwardTargets();
  },

  async _loadForwardTargets() {
    const list = document.getElementById('forwardChatList');
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-2)">Загрузка...</div>';
    try {
      const chats = await API.request(`/api/chats?user_id=${State.currentUser.id}`);
      list.innerHTML = '';
      chats.forEach(chat => {
        if (chat.id === State.currentChatId) return;
        const item = document.createElement('div');
        item.className = 'forward-chat-item';
        item.innerHTML = `<div style="width:36px;height:36px;border-radius:50%;background:${chat.avatar_color||'#54a9eb'};display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600;font-size:14px;flex-shrink:0">${chat.name.substring(0,2).toUpperCase()}</div><span style="flex:1">${chat.name}</span>`;
        item.onclick = () => this._executeForward(chat.id, chat.name);
        list.appendChild(item);
      });
      if (list.children.length === 0) list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-2)">Нет доступных чатов</div>';
    } catch (e) { list.innerHTML = '<div style="padding:20px;color:var(--danger)">Ошибка загрузки</div>'; }
  },

  async _executeForward(targetChatId, targetName) {
    if (!this._forwardingMsg) return;
    document.getElementById('modalForward').classList.remove('active');
    try {
      await API.request(`/api/messages/${targetChatId}/send`, {
        method:'POST',
        body:JSON.stringify({ user_id:State.currentUser.id, text:this._forwardingMsg.text, forwarded_from:this._forwardingMsg.from_name || 'Аноним' }),
      });
      console.log(`✅ Forwarded to ${targetName}`);
    } catch (e) { console.error('Forward failed:', e); }
    this._forwardingMsg = null;
  },

  closeForwardModal() { document.getElementById('modalForward').classList.remove('active'); this._forwardingMsg = null; },

  // ══════════════════════════════════════════
  // SEARCH IN CHAT
  // ══════════════════════════════════════════
  toggleChatSearch() {
    this._searchOpen = !this._searchOpen;
    const panel = document.getElementById('chatSearchPanel');
    panel.style.display = this._searchOpen ? 'flex' : 'none';
    if (this._searchOpen) document.getElementById('chatSearchInput').focus();
    else this._renderMessages();
  },

  searchInChat(query) {
    const q = query.toLowerCase().trim();
    if (q.length < 2) { this._renderMessages(); return; }
    document.querySelectorAll('.msg-row').forEach(row => {
      const text = row.querySelector('.msg-text')?.textContent.toLowerCase() || '';
      if (text.includes(q)) { row.style.display = ''; row.querySelector('.msg-bubble').style.boxShadow = '0 0 0 2px var(--accent)'; }
      else { row.style.display = 'none'; }
    });
  },

  // ══════════════════════════════════════════
  // EMOJI PICKER
  // ══════════════════════════════════════════
  toggleEmoji() {
    this._emojiOpen = !this._emojiOpen;
    const picker = document.getElementById('emojiPicker');
    picker.style.display = this._emojiOpen ? 'flex' : 'none';
  },

  // Attach menu (file + poll)
  showAttachMenu(e) {
    document.querySelector('.attach-menu')?.remove();
    const menu = document.createElement('div');
    menu.className = 'attach-menu';
    const isGroup = this.chatMeta?.isGroup || this.currentTopicId;
    menu.innerHTML = `
      <div class="attach-menu-item" onclick="document.querySelector('.attach-menu')?.remove();document.getElementById('fileInput').click()">
        <i class="fa-solid fa-image" style="color:#7bc862"></i><span>Фото / Видео</span>
      </div>
      <div class="attach-menu-item" onclick="document.querySelector('.attach-menu')?.remove();document.getElementById('fileInput').click()">
        <i class="fa-solid fa-file" style="color:#65aadd"></i><span>Документ</span>
      </div>
      ${isGroup || true ? `
        <div class="attach-menu-item" onclick="document.querySelector('.attach-menu')?.remove();Polls.openCreateModal()">
          <i class="fa-solid fa-chart-bar" style="color:#a695e7"></i><span>Опрос</span>
        </div>
      ` : ''}
    `;
    
    // Position above the attach button
    const btn = document.getElementById('attachBtn');
    const rect = btn.getBoundingClientRect();
    menu.style.left = Math.max(rect.left - 100, 8) + 'px';
    menu.style.bottom = (window.innerHeight - rect.top + 8) + 'px';
    document.body.appendChild(menu);
    
    setTimeout(() => {
      document.addEventListener('click', function rm(ev) {
        if (!menu.contains(ev.target)) { menu.remove(); document.removeEventListener('click', rm); }
      });
    }, 50);
  },

  insertEmoji(emoji) {
    const input = document.getElementById('msgInput');
    input.value += emoji;
    input.focus();
    this._updateSendBtn();
  },

  // ══════════════════════════════════════════
  // INFO PANEL
  // ══════════════════════════════════════════
  toggleInfoPanel() {
    this._infoPanelOpen = !this._infoPanelOpen;
    document.getElementById('infoPanelOverlay').classList.toggle('active', this._infoPanelOpen);
    if (this._infoPanelOpen) this._renderInfoPanel();
  },

  _renderInfoPanel() {
    const content = document.getElementById('infoPanelContent');
    const meta = this.chatMeta;
    const pinText = this.pinnedMsg ? escapeHTML(this.pinnedMsg.text).substring(0,60) : null;
    const typeLabel = meta.isBot ? 'бот' : meta.isGroup ? 'сообщество' : 'в сети';
    const typeClass = (meta.isBot || (!meta.isGroup && meta.online)) ? ' online' : '';

    content.innerHTML = `
      <div class="info-panel-avatar-section">
        <div class="info-panel-avatar" style="background:${meta.color}">
          ${meta.isBot ? '🤖' : escapeHTML(meta.name.substring(0,2).toUpperCase())}
        </div>
        <div class="info-panel-name">${escapeHTML(meta.name)}</div>
        <div class="info-panel-status${typeClass}">${typeLabel}</div>
      </div>

      <div style="border-bottom:1px solid var(--divider)">
        ${meta.isGroup ? `
          <div class="info-row" onclick="Chat.toggleInfoPanel();Chat._renderTopics()">
            <div class="info-row-icon"><i class="fa-solid fa-layer-group"></i></div>
            <div class="info-row-content">
              <div class="info-row-value">${this.topics.length} ${this._plural(this.topics.length,'ветка','ветки','веток')}</div>
              <div class="info-row-label">Темы для обсуждения</div>
            </div>
          </div>
        ` : ''}
        <div class="info-row">
          <div class="info-row-icon"><i class="fa-solid fa-comment"></i></div>
          <div class="info-row-content">
            <div class="info-row-value">${formatNumber(this.messages.length)}</div>
            <div class="info-row-label">Сообщений</div>
          </div>
        </div>
        ${pinText ? `
          <div class="info-row" onclick="Chat.toggleInfoPanel();Chat.scrollTo('${this.pinnedMsg.id}')">
            <div class="info-row-icon"><i class="fa-solid fa-thumbtack"></i></div>
            <div class="info-row-content">
              <div class="info-row-value" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${pinText}</div>
              <div class="info-row-label">Закреплённое сообщение</div>
            </div>
          </div>
        ` : ''}
      </div>

      ${meta.isGroup ? `
        <div style="border-bottom:1px solid var(--divider)">
          <div class="info-row" onclick="Chat.toggleInfoPanel();Invite.createAndCopy()">
            <div class="info-row-icon"><i class="fa-solid fa-link" style="color:var(--accent)"></i></div>
            <div class="info-row-content">
              <div class="info-row-value" style="color:var(--accent)">Скопировать ссылку-приглашение</div>
              <div class="info-row-label">Создать ссылку и скопировать</div>
            </div>
          </div>
          <div class="info-row" onclick="Chat.toggleInfoPanel();Invite.share('${meta.id}','${escapeHTML(meta.name)}')">
            <div class="info-row-icon"><i class="fa-solid fa-share-nodes"></i></div>
            <div class="info-row-content">
              <div class="info-row-value">Поделиться ссылкой</div>
              <div class="info-row-label">Отправить через мессенджер</div>
            </div>
          </div>
          <div class="info-row" onclick="Chat.toggleInfoPanel();Invite.showManagePanel()">
            <div class="info-row-icon"><i class="fa-solid fa-list"></i></div>
            <div class="info-row-content">
              <div class="info-row-value">Управление ссылками</div>
              <div class="info-row-label">Все активные приглашения</div>
            </div>
          </div>
        </div>
        <div style="padding:16px">
          <button class="btn-outline" onclick="Chat.toggleInfoPanel();Admin.openPanel()" style="width:100%;padding:12px;font-size:14px;border-radius:var(--radius);margin-bottom:8px">
            <i class="fa-solid fa-shield-halved" style="margin-right:8px"></i>Управление сообществом
          </button>
          <button class="btn-outline" onclick="Chat.toggleInfoPanel();Chat.importTopicsModal()" style="width:100%;padding:12px;font-size:14px;border-radius:var(--radius)">
            <i class="fa-solid fa-file-import" style="margin-right:8px"></i>Импорт веток
          </button>
        </div>
      ` : ''}
    `;
  },

  // ══════════════════════════════════════════
  // IMPORT TOPICS
  // ══════════════════════════════════════════
  importTopicsModal() {
    const modal = document.getElementById('modalImportTopics');
    if (modal) { modal.classList.add('active'); return; }
    // Create modal dynamically
    const m = document.createElement('div');
    m.id = 'modalImportTopics';
    m.className = 'modal active';
    m.innerHTML = `
      <div class="modal-content" style="text-align:left">
        <h3 style="margin-bottom:4px">Импорт веток</h3>
        <p style="font-size:13px;color:var(--text-2);margin-bottom:16px">Введите названия веток, каждое с новой строки. Можно использовать эмодзи в начале.</p>
        <textarea id="importTopicsText" style="width:100%;height:160px;background:var(--input-bg);border:1px solid var(--input-border);border-radius:10px;padding:12px;font-size:14px;color:var(--text-0);resize:vertical;font-family:inherit" placeholder="💬 Общий чат\n📢 Новости\n❓ Вопросы и ответы\n📷 Медиа"></textarea>
        <div class="modal-actions" style="margin-top:16px">
          <button class="btn-outline" onclick="document.getElementById('modalImportTopics').classList.remove('active')">Отмена</button>
          <button class="btn-primary" onclick="Chat._processImportTopics()">Импортировать</button>
        </div>
      </div>
    `;
    document.body.appendChild(m);
  },

  async _processImportTopics() {
    const textarea = document.getElementById('importTopicsText');
    const lines = textarea.value.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length === 0) return;

    const modal = document.getElementById('modalImportTopics');
    const btn = modal.querySelector('.btn-primary');
    btn.textContent = 'Создаём...';
    btn.disabled = true;

    let created = 0;
    for (const title of lines) {
      try {
        await API.request('/api/topics/create', {
          method: 'POST',
          body: JSON.stringify({ chat_id: State.currentChatId, title, created_by: State.currentUser.id })
        });
        created++;
      } catch (e) { console.error('Import topic failed:', title, e); }
    }

    modal.classList.remove('active');
    btn.textContent = 'Импортировать';
    btn.disabled = false;

    if (created > 0) {
      await this._loadTopics(State.currentChatId);
      this._renderTopics();
    }
    console.log(`✅ Imported ${created}/${lines.length} topics`);
  },

  // ══════════════════════════════════════════
  // WEBSOCKET (stable: ping/pong + reconnect + online)
  // ══════════════════════════════════════════
  _wsRetries: 0,
  _pingInterval: null,
  onlineUsers: {},

  _connectWS(chatId) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.close();
    clearInterval(this._pingInterval);

    const wsP = location.protocol==='https:'?'wss:':'ws:';
    const wsH = API.baseUrl.replace(/^https?:\/\//,'') || location.host;
    const url = `${wsP}//${wsH}/ws/${chatId}?user_id=${State.currentUser.id}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('🔗 WS connected:', chatId);
        this._wsRetries = 0;
        // Ping every 25s to keep connection alive
        this._pingInterval = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25000);
      };

      this.ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data);

          if (d.type === 'message' && d.from_id !== State.currentUser.id) {
            d.reactions = d.reactions || {};
            this.messages.push(d);
            this._renderMessages();
            // Play notification sound (optional)
            this._notifyNewMessage(d);
          }
          else if (d.type === 'edit') {
            const m = this.messages.find(x => x.id === d.id);
            if (m) { m.text = d.text; m.edited = true; this._renderMessages(); }
          }
          else if (d.type === 'typing' && d.user_id !== State.currentUser.id) {
            this._showTyping(d.user_name || 'Кто-то');
          }
          else if (d.type === 'online') {
            this.onlineUsers[d.user_id] = d.online;
            // Update status if viewing this user's chat
            if (!this.chatMeta?.isGroup && !this.chatMeta?.isBot) {
              const st = document.getElementById('chatStatus');
              if (d.online) { st.textContent = 'в сети'; st.className = 'chat-header-status online'; }
              else { st.textContent = 'был(а) только что'; st.className = 'chat-header-status'; }
            }
          }
          else if (d.type === 'system') {
            this.messages.push({
              id: 'sys_' + Date.now(), from_id: 0, from_name: 'Система',
              text: d.text, ts: Date.now(), status: 'delivered', reactions: {},
            });
            this._renderMessages();
          }
          else if (d.type === 'pin') {
            // Another user pinned a message
            const pinned = this.messages.find(m => m.id === d.msg_id);
            if (pinned) { this.pinnedMsg = pinned; }
            else { this.pinnedMsg = { id: d.msg_id, text: d.text, from_name: d.from_name }; }
            this._renderMessages();
          }
          else if (d.type === 'unpin') {
            this.pinnedMsg = null;
            this._renderMessages();
          }
          else if (d.type === 'poll_update' && typeof Polls !== 'undefined') {
            // Re-render the poll that was updated
            const pollMsg = this.messages.find(m => m.media_url === d.poll_id);
            if (pollMsg) Polls.renderPoll(d.poll_id, pollMsg.id);
          }
          else if (d.type === 'call_incoming' && typeof Calls !== 'undefined') {
            Calls.handleIncoming(d.caller_id, d.caller_name, d.video);
          }
          else if (d.type === 'call_signal' && typeof Calls !== 'undefined') {
            Calls.handleSignal(d.signal_type, d.from_id, d.data);
          }
          else if (d.type === 'pong') {
            // Keepalive confirmed
          }
        } catch(e) { console.warn('WS parse:', e); }
      };

      this.ws.onclose = (event) => {
        clearInterval(this._pingInterval);
        const target = this.currentTopicId || State.currentChatId;

        if (event.code === 4003) {
          // Banned
          alert('Вы заблокированы в этом чате');
          return;
        }

        // Exponential backoff reconnect
        this._wsRetries++;
        const delay = Math.min(1000 * Math.pow(2, this._wsRetries), 30000);
        console.log(`🔌 WS closed, reconnect in ${delay}ms (attempt ${this._wsRetries})`);
        setTimeout(() => {
          if (target === chatId && (this.currentTopicId || State.currentChatId) === target) {
            this._connectWS(chatId);
          }
        }, delay);
      };

      this.ws.onerror = () => {}; // Handled by onclose

    } catch(e) { console.warn('WS failed:', e); }
  },

  _notifyNewMessage(msg) {
    if (typeof Notify !== 'undefined') {
      Notify.playSound();
      Notify.showBrowserNotif(msg.from_name || 'Pulse Chat', msg.text, 'pulse-msg-' + msg.id);
      Notify.addUnread();
    }
  },

  _showTyping(name) {
    const el = document.getElementById('chatStatus');
    el.textContent = `${name} печатает...`; el.className = 'chat-header-status online';
    clearTimeout(this._typingTimeout);
    this._typingTimeout = setTimeout(() => {
      if (this.currentTopicId) { el.textContent=this.chatMeta?.name||''; el.className='chat-header-status'; }
      else if (this.chatMeta) { el.textContent=this.chatMeta.isBot?'бот':(this.chatMeta.isGroup?'сообщество':''); el.className='chat-header-status'; }
    }, 3000);
  },

  // ══════════════════════════════════════════
  // INPUT HELPERS
  // ══════════════════════════════════════════
  handleKey(e) { if(typeof Mentions!=='undefined'&&Mentions.handleKey(e))return; if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();this.send();} if(this.ws?.readyState===WebSocket.OPEN)this.ws.send(JSON.stringify({type:'typing'})); },
  autoResize(ta) { ta.style.height='auto'; ta.style.height=Math.min(ta.scrollHeight,150)+'px'; this._updateSendBtn(); if(typeof Mentions!=='undefined')Mentions.check(ta); },
  _updateSendBtn() { const i=document.getElementById('msgInput'),s=document.getElementById('sendBtn'),m=document.getElementById('micBtn'); if((i?.value.trim()) || this._pendingMedia){s.style.display='flex';m.style.display='none';}else{s.style.display='none';m.style.display='flex';} },

  setReply(msg) { this.cancelEdit(); State.replyTo=msg; document.getElementById('replyName').textContent=String(msg.from_id)===String(State.currentUser?.id)?'Вы':(msg.from_name||''); document.getElementById('replyText').textContent=msg.text; document.getElementById('replyPreview').style.display='flex'; document.getElementById('msgInput').focus(); },
  cancelReply() { State.replyTo=null; document.getElementById('replyPreview').style.display='none'; },

  _startEdit(msg) { this.cancelReply(); this._editingMsg=msg; document.getElementById('msgInput').value=msg.text; document.getElementById('msgInput').focus(); this.autoResize(document.getElementById('msgInput')); document.getElementById('replyName').textContent='✏️ Редактирование'; document.getElementById('replyText').textContent=msg.text.substring(0,50); document.getElementById('replyPreview').style.display='flex'; const el=document.querySelector(`[data-msg-id="${msg.id}"]`); if(el){const b=el.querySelector('.msg-bubble');b.style.background='var(--accent-soft)';this._editHighlightEl=b;} },
  cancelEdit() { this._editingMsg=null; document.getElementById('replyPreview').style.display='none'; if(this._editHighlightEl){this._editHighlightEl.style.background='';this._editHighlightEl=null;} },

  scrollTo(msgId) { const el=document.querySelector(`[data-msg-id="${msgId}"]`); if(el){el.scrollIntoView({behavior:'smooth',block:'center'});const b=el.querySelector('.msg-bubble');b.style.background='var(--accent-soft)';setTimeout(()=>b.style.background='',1500);} },

  // ══════════════════════════════════════════
  // CONTEXT MENU (full featured)
  // ══════════════════════════════════════════
  _showContextMenu(e, msg) {
    document.querySelector('.context-menu')?.remove();
    document.querySelector('.reaction-picker')?.remove();
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    const isOwn = String(msg.from_id) === String(State.currentUser?.id);
    const items = [
      { i:'fa-face-smile', l:'Реакция', a:()=>this._showReactionPicker(e, msg) },
      { i:'fa-reply', l:'Ответить', a:()=>this.setReply(msg) },
      { i:'fa-copy', l:'Копировать', a:()=>navigator.clipboard?.writeText(msg.text) },
      { i:'fa-share', l:'Переслать', a:()=>this.startForward(msg) },
      { i:'fa-thumbtack', l:this.pinnedMsg?.id===msg.id?'Открепить':'Закрепить', a:()=>this.pinnedMsg?.id===msg.id?this.unpinMsg():this.pinMsg(msg) },
    ];
    if (isOwn) items.push({ i:'fa-pen', l:'Редактировать', a:()=>this._startEdit(msg) });
    items.push({ i:'fa-trash', l:'Удалить', d:true, a:async()=>{try{await API.request(`/api/messages/${msg.id}/delete`,{method:'POST',body:JSON.stringify({user_id:State.currentUser.id})});this.messages=this.messages.filter(m=>m.id!==msg.id);this._renderMessages();}catch(e){}} });

    items.forEach(item => { const div=document.createElement('div'); div.className='context-menu-item'+(item.d?' danger':''); div.innerHTML=`<i class="fa-solid ${item.i}"></i><span>${item.l}</span>`; div.onclick=()=>{item.a();menu.remove();}; menu.appendChild(div); });
    menu.style.left=Math.min(e.clientX,innerWidth-200)+'px';
    menu.style.top=Math.min(e.clientY,innerHeight-items.length*42-12)+'px';
    document.body.appendChild(menu);
  },
};

// GLOBALS
function sendMessage(){Chat.send()} function handleKey(e){Chat.handleKey(e)} function autoResize(ta){Chat.autoResize(ta)}
function cancelReply(){Chat.cancelEdit();Chat.cancelReply()}
function closeTopicModal(){Chat.closeTopicModal()} function processCreateTopic(){Chat.processCreateTopic()}
function closeForwardModal(){Chat.closeForwardModal()}
function goBack(){
  if(Chat.currentTopicId){Chat.currentTopicId=null;Chat.currentTopicTitle=null;document.getElementById('chatName').textContent=Chat.chatMeta?.name||'';document.getElementById('chatStatus').textContent='сообщество';document.getElementById('chatStatus').className='chat-header-status';Chat._renderTopics();Chat._hideInputArea();if(Chat.ws)Chat.ws.close();return;}
  if(State.isMobile){document.getElementById('chatView').classList.remove('active');State.currentChatId=null;Sidebar.render();}
}
