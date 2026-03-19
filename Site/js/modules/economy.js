/* ===================================================
   PULSE CHAT v2.0 — Economy Module
   Wallet, TOP-5, Lottery — real data from bot DB
   =================================================== */

const Economy = {

  // ══════════════════════════════════════════
  // WALLET PAGE
  // ══════════════════════════════════════════
  async loadWallet() {
    if (!State.currentUser) return;

    const balanceEl = document.querySelector('.economy-balance-amount');
    const txList = document.getElementById('economyTransactions');
    const rateEl = document.getElementById('economyRate');

    if (balanceEl) balanceEl.textContent = '...';

    try {
      const data = await API.request(`/api/economy/balance?user_id=${State.currentUser.id}`);

      // Balance
      if (balanceEl) {
        balanceEl.textContent = Math.floor(data.balance).toLocaleString('ru-RU');
      }

      // Rate
      if (rateEl && data.rate) {
        rateEl.textContent = `1 💎 = ${data.rate.toFixed(2)} ₽`;
      }

      // Transactions
      if (txList) {
        if (!data.transactions || data.transactions.length === 0) {
          txList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-2)">Нет операций</div>';
        } else {
          txList.innerHTML = data.transactions.map(tx => {
            const sign = tx.income ? '+' : '−';
            const color = tx.income ? 'var(--success)' : 'var(--danger)';
            const desc = tx.description || tx.type || 'Операция';
            return `<div class="stat-row">
              <span class="stat-label">${Economy._txLabel(desc)}</span>
              <span class="stat-value" style="color:${color}">${sign}${Math.floor(tx.amount).toLocaleString('ru-RU')} 💎</span>
            </div>`;
          }).join('');
        }
      }
    } catch (err) {
      console.error('Wallet load error:', err);
      if (balanceEl) balanceEl.textContent = '—';
    }
  },

  _txLabel(desc) {
    const map = {
      'mining': '⛏ Майнинг сообщения',
      'transfer_out': '📤 Перевод',
      'transfer_in': '📥 Получен перевод',
      'lottery_buy': '🎰 Лотерея (билет)',
      'lottery_win': '🎉 Выигрыш лотереи',
      'donation': '🎁 Донат',
      'bonus': '🎁 Бонус',
      'referral': '👥 Реферальный бонус',
    };
    return map[desc] || desc;
  },

  // ══════════════════════════════════════════
  // TRANSFER MODAL
  // ══════════════════════════════════════════
  openTransferModal() {
    document.getElementById('modalTransfer')?.remove();
    const m = document.createElement('div');
    m.id = 'modalTransfer';
    m.className = 'modal active';
    m.onclick = e => { if (e.target === m) m.remove(); };
    m.innerHTML = `
      <div class="modal-content" style="text-align:left">
        <h3 style="text-align:center;margin-bottom:16px">
          <i class="fa-solid fa-paper-plane" style="color:var(--accent);margin-right:8px"></i>Перевод 💎
        </h3>
        <div class="form-field" style="margin-bottom:12px">
          <label>Telegram ID получателя</label>
          <input type="number" id="transferToId" placeholder="Например: 123456789">
        </div>
        <div class="form-field" style="margin-bottom:16px">
          <label>Сумма</label>
          <input type="number" id="transferAmount" placeholder="100" min="1">
        </div>
        <div id="transferStatus" style="display:none;padding:8px 12px;border-radius:var(--radius);margin-bottom:12px;font-size:14px"></div>
        <div class="modal-actions">
          <button class="btn-outline" onclick="document.getElementById('modalTransfer').remove()">Отмена</button>
          <button class="btn-primary" id="transferBtn" onclick="Economy.executeTransfer()">Перевести</button>
        </div>
      </div>
    `;
    document.body.appendChild(m);
    document.getElementById('transferToId').focus();
  },

  async executeTransfer() {
    const toId = parseInt(document.getElementById('transferToId').value);
    const amount = parseFloat(document.getElementById('transferAmount').value);
    const status = document.getElementById('transferStatus');
    const btn = document.getElementById('transferBtn');

    if (!toId || toId < 1) { status.style.display = 'block'; status.style.background = 'rgba(229,87,87,0.1)'; status.style.color = 'var(--danger)'; status.textContent = 'Введите ID получателя'; return; }
    if (!amount || amount < 1) { status.style.display = 'block'; status.style.background = 'rgba(229,87,87,0.1)'; status.style.color = 'var(--danger)'; status.textContent = 'Введите сумму'; return; }

    btn.disabled = true;
    btn.textContent = 'Отправка...';

    try {
      const res = await API.request('/api/economy/transfer', {
        method: 'POST',
        body: JSON.stringify({ from_id: State.currentUser.id, to_id: toId, amount })
      });

      if (res.status === 'success') {
        status.style.display = 'block';
        status.style.background = 'rgba(77,205,94,0.1)';
        status.style.color = 'var(--success)';
        status.textContent = `✅ Переведено ${amount} 💎 → ${res.receiver_name}`;
        // Update local balance
        State.currentUser.balance = res.new_balance;
        setTimeout(() => {
          document.getElementById('modalTransfer')?.remove();
          this.loadWallet();
        }, 1500);
      } else {
        status.style.display = 'block';
        status.style.background = 'rgba(229,87,87,0.1)';
        status.style.color = 'var(--danger)';
        status.textContent = res.detail || 'Ошибка';
        btn.disabled = false;
        btn.textContent = 'Перевести';
      }
    } catch (err) {
      status.style.display = 'block';
      status.style.color = 'var(--danger)';
      status.textContent = 'Ошибка сети';
      btn.disabled = false;
      btn.textContent = 'Перевести';
    }
  },

  // ══════════════════════════════════════════
  // TOP-5 PAGE
  // ══════════════════════════════════════════
  currentTopTab: 'rich',

  async loadTop(tab) {
    this.currentTopTab = tab || 'rich';
    const list = document.getElementById('topList');
    if (!list) return;

    // Update tabs
    document.querySelectorAll('.top-tab').forEach((t, i) => {
      t.classList.toggle('active', (i === 0 && this.currentTopTab === 'rich') || (i === 1 && this.currentTopTab === 'active'));
    });

    list.innerHTML = '<div style="text-align:center;padding:30px"><div class="auth-spinner" style="width:24px;height:24px;border-width:2px;margin:0 auto"></div></div>';

    try {
      const endpoint = this.currentTopTab === 'rich' ? '/api/top/rich' : '/api/top/active';
      const data = await API.request(endpoint);

      if (!data || data.length === 0) {
        list.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-2)">Нет данных</div>';
        return;
      }

      const unit = this.currentTopTab === 'rich' ? '💎' : 'сообщ.';
      const medals = ['🥇', '🥈', '🥉'];
      const rankClass = ['gold', 'silver', 'bronze'];

      list.innerHTML = data.map((u, i) => {
        const medal = i < 3 ? `<div class="top-value">${medals[i]}</div>` : '';
        const rc = i < 3 ? ` ${rankClass[i]}` : '';
        const val = this.currentTopTab === 'rich'
          ? Math.floor(u.value).toLocaleString('ru-RU') + ' 💎'
          : u.value + ' ' + unit;
        const isMe = u.user_id === State.currentUser?.id;

        return `<div class="top-item${isMe ? ' top-item-me' : ''}">
          <div class="top-rank${rc}">${u.rank}</div>
          <div class="top-avatar" style="background:${u.color}">${u.initials}</div>
          <div class="top-info">
            <div class="top-name">${escapeHTML(u.name)}${isMe ? ' <span style="font-size:11px;color:var(--accent)">(вы)</span>' : ''}</div>
            <div class="top-subtitle">${val}</div>
          </div>
          ${medal}
        </div>`;
      }).join('');
    } catch (err) {
      console.error('Top load error:', err);
      list.innerHTML = '<div style="text-align:center;padding:30px;color:var(--danger)">Ошибка загрузки</div>';
    }
  },

  // ══════════════════════════════════════════
  // LOTTERY PAGE
  // ══════════════════════════════════════════
  async loadLottery() {
    if (!State.currentUser) return;

    try {
      const data = await API.request(`/api/lottery/info?user_id=${State.currentUser.id}`);

      const jp = document.getElementById('lotteryJackpot');
      if (jp) jp.textContent = Math.floor(data.jackpot).toLocaleString('ru-RU') + ' 💎';

      const stats = document.getElementById('lotteryStats');
      if (stats) {
        stats.innerHTML = `
          <div class="stat-row"><span class="stat-label">Ваши билеты</span><span class="stat-value">${data.my_tickets}</span></div>
          <div class="stat-row"><span class="stat-label">Участников</span><span class="stat-value">${data.participants}</span></div>
          <div class="stat-row"><span class="stat-label">Всего билетов</span><span class="stat-value">${data.total_tickets}</span></div>
          <div class="stat-row"><span class="stat-label">Ваш шанс</span><span class="stat-value">${data.chance}%</span></div>
        `;
      }
    } catch (err) {
      console.error('Lottery load error:', err);
    }
  },

  async buyTicket(count) {
    if (!State.currentUser) return;
    try {
      const res = await API.request('/api/lottery/buy', {
        method: 'POST',
        body: JSON.stringify({ user_id: State.currentUser.id, count })
      });

      if (res.status === 'success') {
        // Update balance
        State.currentUser.balance = res.new_balance;
        // Refresh
        this.loadLottery();
        // Toast
        Economy._toast(`🎰 Куплено ${count} ${Economy._plural(count,'билет','билета','билетов')}!`);
      } else {
        alert(res.detail || 'Ошибка покупки');
      }
    } catch (err) {
      alert('Ошибка сети');
    }
  },

  // ══════════════════════════════════════════
  // UTILS
  // ══════════════════════════════════════════
  _toast(text) {
    const t = document.createElement('div');
    t.className = 'invite-toast';
    t.innerHTML = `<i class="fa-solid fa-check-circle" style="color:var(--success);font-size:18px"></i><div style="font-weight:600;font-size:14px">${text}</div>`;
    document.body.appendChild(t);
    requestAnimationFrame(() => t.classList.add('visible'));
    setTimeout(() => { t.classList.remove('visible'); setTimeout(() => t.remove(), 300); }, 2500);
  },

  _plural(n, a, b, c) {
    const m = n % 10, h = n % 100;
    if (m === 1 && h !== 11) return a;
    if (m >= 2 && m <= 4 && (h < 10 || h >= 20)) return b;
    return c;
  },
};
