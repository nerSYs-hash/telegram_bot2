/* ===================================================
   PULSE CHAT — Global State
   =================================================== */
const State = {
  currentUser: null,
  currentChatId: null,
  isMobile: window.innerWidth <= 768,
  replyTo: null,

 setUser(user) {
    this.currentUser = user;
    
    // Элементы UI, которые нужно обновить
    const els = {
      menuAvatarCircle: document.getElementById('menuAvatarCircle'),
      menuUserName: document.getElementById('menuUserName'),
      profileName: document.getElementById('profileName'),
      profileInitials: document.getElementById('profileInitials'),
      // Добавляем элемент баланса из страницы кошелька
      economyBalance: document.querySelector('.economy-balance-amount')
    };

    if (user) {
      // 1. Имя и инициалы
      const displayName = user.name || user.username || 'Пользователь';
      const initials = typeof getInitials === 'function' ? getInitials(displayName) : displayName.substring(0,2).toUpperCase();
      
      if (els.menuAvatarCircle) els.menuAvatarCircle.textContent = initials;
      if (els.menuUserName) els.menuUserName.textContent = displayName;
      if (els.profileName) els.profileName.textContent = displayName;
      if (els.profileInitials) els.profileInitials.textContent = initials;

      // 2. БАЛАНС (Тот самый момент из базы бота)
      if (els.economyBalance && user.balance !== undefined) {
        // Форматируем число (например, 12450.5 -> 12 450)
        els.economyBalance.textContent = Math.floor(user.balance).toLocaleString('ru-RU');
      }
      
      console.log(`✅ State: Пользователь ${displayName} загружен. Баланс: ${user.balance}`);
    }
  },
};

window.addEventListener('resize', () => {
  State.isMobile = window.innerWidth <= 768;
});

/* ===================================================
   PULSE CHAT — Theme Manager
   =================================================== */
const Theme = {
  init() {
    const saved = localStorage.getItem('pulse-theme') || 'dark';
    document.body.setAttribute('data-theme', saved);
    this.updateLabel();
  },

  toggle() {
    const current = document.body.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.body.setAttribute('data-theme', next);
    localStorage.setItem('pulse-theme', next);
    this.updateLabel();
  },

  updateLabel() {
    const label = document.getElementById('themeLabel');
    if (label) {
      label.textContent = document.body.getAttribute('data-theme') === 'dark' ? 'Тёмная' : 'Светлая';
    }
  },
};

/* ===================================================
   PULSE CHAT — SPA Router
   =================================================== */
const Router = {
  currentPage: 'landing',
  history: [],

  navigate(pageId, addToHistory = true) {
    // Don't navigate to current page
    if (pageId === this.currentPage) return;

    // Save current page to history stack (except for initial load)
    if (addToHistory && this.currentPage && this.currentPage !== 'landing' && this.currentPage !== 'auth') {
      // Avoid duplicates in history
      if (this.history[this.history.length - 1] !== this.currentPage) {
        this.history.push(this.currentPage);
      }
      // Keep history manageable
      if (this.history.length > 10) this.history.shift();
    }

    // Switch page
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const page = document.getElementById('page-' + pageId);
    if (page) {
      page.classList.add('active');
      this.currentPage = pageId;
    }

    // Page-specific init
    if (pageId === 'chat') {
      Sidebar.render();
      if (!State.currentChatId) Chat.showEmpty();
    }
    else if (pageId === 'economy' && typeof Economy !== 'undefined') {
      Economy.loadWallet();
    }
    else if (pageId === 'top' && typeof Economy !== 'undefined') {
      Economy.loadTop('rich');
    }
    else if (pageId === 'lottery' && typeof Economy !== 'undefined') {
      Economy.loadLottery();
    }
    else if (pageId === 'profile' && typeof Profile !== 'undefined') {
      Profile.load();
    }
  },

  back() {
    if (this.history.length > 0) {
      const prev = this.history.pop();
      this.navigate(prev, false); // Don't add to history when going back
    } else {
      this.navigate('chat', false);
    }
  },
};

// Expose global shortcuts
function showPage(id) { Router.navigate(id); }
function goBackPage() { Router.back(); }
function toggleTheme() { Theme.toggle(); }
