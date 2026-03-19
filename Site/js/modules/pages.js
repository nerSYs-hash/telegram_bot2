/* ===================================================
   PULSE CHAT v2.0 — Pages Module
   Economy, TOP-5, Lottery, BBS, Profile — live data
   =================================================== */

const Pages = {

  // ══════════════════════════════════════════
  // ECONOMY / WALLET
  // ══════════════════════════════════════════
  async loadEconomy() {
    if (!State.currentUser) return;
    const balEl = document.getElementById('economyBalance');
    const rateEl = document.getElementById('economyRate');
    const txList = document.getElementById('economyTxList');

    // Show loading
    if (balEl) balEl.textContent = '...';
    if (txList) txList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-2)"><div class="auth-spinner" style="width:20px;height:20px;border-width:2px;margin:0 auto"></div></div>';

    try {
      const data = await API.request(`/api/economy/balance?user_id=${State.currentUser.id}`);

      // Balance
      if (balEl) balEl.textContent = Math.floor(data.balance).toLocaleString('ru-RU');

      // Rate
      if (rateEl) rateEl.textContent = `1💎 = ${data.rate.toFixed(2)}₽`;

      // Transactions
      if (txList) {
        if (!data.transactions || data.transactions.length === 0) {
          txList.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-2);opacity:0.6">Нет операций</div>';
          return;
        }
        txList.innerHTML = data.transactions.map(tx => {
          const isIncoming = tx.to_id === State.currentUser.id;
          const amount = tx.amount || 0;
          const sign = isIncoming ? '+' : '−';
          const color = isIncoming ? 'var(--success)' : 'var(--danger)';
          const type = tx.type || tx.description || (isIncoming ? 'Получено' : 'Отправлено');
          return `<div class="stat-row"><span class="stat-label">${escapeHTML(type)}</span><span class="stat-value" style="color:${color}">${sign}${Math.abs(amount).toLocaleString('ru-RU')} 💎</span></div>`;
        }).join('');
      }
    } catch (e) {
      console.error('Economy load error:', e);
      if (balEl) balEl.textContent = '—';
      if (txList) txList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--danger)">Ошибка загрузки</div>';
    }
  },

  // Transfer modal
  showTransferModal() {
    document.getElementById('modalTransfer')?.remove();
    const m = document.createElement('div');
    m.id = 'modalTransfer';
    m.className = 'modal active';
    m.onclick = (e) => { if (e.target === m) m.remove(); };
    m.innerHTML = `
      <div class="modal-content" style="text-align:left">
        <h3 style="text-align:center;margin-bottom:16px">💎 Перевод Пульсов</h3>
        <div style="margin-bottom:12px">
          <label style="font-size:13px;color:var(--text-2);display:block;margin-bottom:4px">Telegram ID получателя</label>
          <input type="number" id="transferToId" placeholder="123456789" style="width:100%;padding:12px;background:var(--input-bg);border:1px solid var(--input-border);border-radius:var(--radius);color:var(--text-0);font-size:15px;margin:0">
        </div>
        <div style="margin-bottom:16px">
          <label style="font-size:13px;color:var(--text-2);display:block;margin-bottom:4px">Сумма</label>
          <input type="number" id="transferAmount" placeholder="100" min="1" style="width:100%;padding:12px;background:var(--input-bg);border:1px solid var(--input-border);border-radius:var(--radius);color:var(--text-0);font-size:15px;margin:0">
        </div>
        <div class="modal-actions">
          <button class="btn-outline" onclick="document.getElementById('modalTransfer').remove()">Отмена</button>
          <button class="btn-primary" id="transferBtn" onclick="Pages._doTransfer()">Отправить</button>
        </div>
      </div>
    `;
    document.body.appendChild(m);
    document.getElementById('transferToId').focus();
  },

  async _doTransfer() {
    const toId = parseInt(document.getElementById('transferToId').value);
    const amount = parseFloat(document.getElementById('transferAmount').value);
    const btn = document.getElementById('transferBtn');
    if (!toId || !amount || amount <= 0) { alert('Заполните все поля'); return; }

    btn.disabled = true;
    btn.textContent = 'Отправка...';
    try {
      const res = await API.request('/api/economy/transfer', {
        method: 'POST',
        body: JSON.stringify({ from_id: State.currentUser.id, to_id: toId, amount })
      });
      if (res.status === 'success') {
        document.getElementById('modalTransfer').remove();
        this.loadEconomy();
      } else {
        alert(res.detail || 'Ошибка перевода');
        btn.disabled = false;
        btn.textContent = 'Отправить';
      }
    } catch (e) {
      alert('Ошибка сети');
      btn.disabled = false;
      btn.textContent = 'Отправить';
    }
  },

  // ══════════════════════════════════════════
  // TOP-5
  // ══════════════════════════════════════════
  _topTab: 'rich',

  async loadTop(tab) {
    this._topTab = tab || this._topTab;
    const list = document.getElementById('topList');
    if (!list) return;

    // Update tab UI
    document.querySelectorAll('#page-top .top-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`#page-top .top-tab[data-tab="${this._topTab}"]`)?.classList.add('active');

    list.innerHTML = '<div style="text-align:center;padding:40px"><div class="auth-spinner" style="width:24px;height:24px;border-width:2px;margin:0 auto"></div></div>';

    try {
      const endpoint = this._topTab === 'rich' ? '/api/top/rich' : '/api/top/active';
      const users = await API.request(`${endpoint}?limit=10`);

      if (!users || users.length === 0) {
        list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-2)">Нет данных</div>';
        return;
      }

      const medals = ['🥇', '🥈', '🥉'];
      const rankClasses = ['gold', 'silver', 'bronze'];

      list.innerHTML = users.map((u, i) => {
        const initials = getInitials(u.name);
        const color = getAvatarColor(u.tg_id || i);
        const valueText = this._topTab === 'rich'
          ? `${Math.floor(u.balance).toLocaleString('ru-RU')} 💎`
          : `${(u.msg_count || 0).toLocaleString('ru-RU')} сообщ.`;
        const rankClass = i < 3 ? ` ${rankClasses[i]}` : '';
        const medal = i < 3 ? `<div class="top-value">${medals[i]}</div>` : '';

        return `
          <div class="top-item">
            <div class="top-rank${rankClass}">${i + 1}</div>
            <div class="top-avatar" style="background:${color}">${initials}</div>
            <div class="top-info">
              <div class="top-name">${escapeHTML(u.name)}</div>
              <div class="top-subtitle">${valueText}</div>
            </div>
            ${medal}
          </div>
        `;
      }).join('');
    } catch (e) {
      console.error('Top load error:', e);
      list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--danger)">Ошибка загрузки</div>';
    }
  },

  // ══════════════════════════════════════════
  // LOTTERY
  // ══════════════════════════════════════════
  async loadLottery() {
    if (!State.currentUser) return;
    const jackpotEl = document.getElementById('lotteryJackpot');
    const ticketsEl = document.getElementById('lotteryMyTickets');
    const statsEl = document.getElementById('lotteryStats');

    try {
      const data = await API.request(`/api/lottery?user_id=${State.currentUser.id}`);

      if (jackpotEl) jackpotEl.textContent = `${Math.floor(data.jackpot || 0).toLocaleString('ru-RU')} 💎`;
      if (ticketsEl) ticketsEl.textContent = `Ваши билеты: ${data.my_tickets || 0}`;

      if (statsEl) {
        let statsHTML = '';
        if (data.next_draw) statsHTML += `<div class="stat-row"><span class="stat-label">Розыгрыш</span><span class="stat-value">${data.next_draw}</span></div>`;
        if (data.participants) statsHTML += `<div class="stat-row"><span class="stat-label">Участников</span><span class="stat-value">${data.participants}</span></div>`;
        if (data.total_tickets && data.my_tickets) {
          const chance = ((data.my_tickets / data.total_tickets) * 100).toFixed(1);
          statsHTML += `<div class="stat-row"><span class="stat-label">Шанс победы</span><span class="stat-value">${chance}%</span></div>`;
        }
        statsEl.innerHTML = statsHTML || '<div style="color:var(--text-2);padding:8px 0">Нет активной лотереи</div>';
      }

      if (!data.active) {
        if (jackpotEl) jackpotEl.textContent = 'Нет розыгрыша';
        document.querySelectorAll('.lottery-ticket').forEach(t => {
          t.style.opacity = '0.5';
          t.style.pointerEvents = 'none';
        });
      }
    } catch (e) {
      console.error('Lottery load error:', e);
      if (jackpotEl) jackpotEl.textContent = '—';
    }
  },

  async buyTickets(count, price) {
    if (!State.currentUser) return;
    if (!confirm(`Купить ${count} билет(ов) за ${price} 💎?`)) return;

    try {
      const res = await API.request('/api/lottery/buy', {
        method: 'POST',
        body: JSON.stringify({ user_id: State.currentUser.id, count })
      });
      if (res.status === 'success') {
        this.loadLottery();
        this.loadEconomy(); // Refresh balance
      } else {
        alert(res.detail || 'Ошибка покупки');
      }
    } catch (e) { alert('Ошибка сети'); }
  },

  // ══════════════════════════════════════════
  // BBS (Знакомства)
  // ══════════════════════════════════════════
  async loadBBS() {
    const list = document.getElementById('bbsList');
    if (!list) return;

    list.innerHTML = '<div style="text-align:center;padding:40px"><div class="auth-spinner" style="width:24px;height:24px;border-width:2px;margin:0 auto"></div></div>';

    try {
      const userId = State.currentUser?.id || 0;
      const profiles = await API.request(`/api/bbs?user_id=${userId}&limit=20`);

      if (!profiles || profiles.length === 0) {
        list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-2)"><i class="fa-solid fa-heart-crack" style="font-size:40px;opacity:0.2;display:block;margin-bottom:12px"></i>Нет анкет</div>';
        return;
      }

      list.innerHTML = profiles.map(p => {
        const name = p.username || p.first_name || 'Аноним';
        const color = getAvatarColor(p.user_id || 0);
        const initials = getInitials(name);
        const age = p.age ? `, ${p.age}` : '';
        const city = p.city || '';
        const meta = [city, p.height ? `${p.height}/${p.weight||''}` : ''].filter(Boolean).join(' · ');
        return `
          <div class="bbs-card">
            <div class="bbs-card-header">
              <div class="bbs-card-avatar" style="background:${color}">${initials}</div>
              <div>
                <div class="bbs-card-name">${escapeHTML(name)}${age}</div>
                ${meta ? `<div class="bbs-card-meta">${escapeHTML(meta)}</div>` : ''}
              </div>
            </div>
            <div class="bbs-card-body">${escapeHTML(p.description || p.bio || 'Без описания')}</div>
            <div class="bbs-card-actions">
              <div class="bbs-action">👎</div>
              <div class="bbs-action" onclick="Chat.open('dm_${p.user_id}','${escapeHTML(name)}')">💬</div>
              <div class="bbs-action">❤️</div>
            </div>
          </div>
        `;
      }).join('');
    } catch (e) {
      console.error('BBS load error:', e);
      list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--danger)">Ошибка загрузки</div>';
    }
  },

  // ══════════════════════════════════════════
  // PROFILE (extended)
  // ══════════════════════════════════════════
  async loadProfile() {
    if (!State.currentUser) return;

    try {
      const p = await API.request(`/api/user/profile?user_id=${State.currentUser.id}`);
      if (!p || p.status === 'error') return;

      const displayName = p.username || p.first_name || 'Пользователь';
      const initials = getInitials(displayName);

      // Update profile page
      const nameEl = document.getElementById('profileName');
      const initialsEl = document.getElementById('profileInitials');
      const usernameEl = document.getElementById('profileUsername');
      const balanceEl = document.getElementById('profileBalance');
      const msgsEl = document.getElementById('profileMsgCount');
      const dateEl = document.getElementById('profileDate');

      if (nameEl) nameEl.textContent = displayName;
      if (initialsEl) initialsEl.textContent = initials;
      if (usernameEl) usernameEl.textContent = p.username ? `@${p.username}` : '';
      if (balanceEl) balanceEl.textContent = `${Math.floor(p.balance || 0).toLocaleString('ru-RU')} 💎`;
      if (msgsEl) msgsEl.textContent = (p.msg_count || 0).toLocaleString('ru-RU');
      if (dateEl && p.created_at) {
        const d = new Date(p.created_at);
        dateEl.textContent = d.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric' });
      }
    } catch (e) {
      console.error('Profile load error:', e);
    }
  },
};
