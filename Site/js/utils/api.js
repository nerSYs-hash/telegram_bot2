/* ===================================================
   PULSE CHAT — API Client
   Handles communication with Python (FastAPI) backend
   =================================================== */

function resolveApiBaseUrl() {
  const host = window.location.hostname;
  const protocol = window.location.protocol;
  const localHosts = new Set(['localhost', '127.0.0.1']);
  const prodHosts = new Set(['puls-chat.ru', 'www.puls-chat.ru']);

  // Локальный предпросмотр: фронт на 8080, API на 8000.
  if (localHosts.has(host)) {
    return 'http://127.0.0.1:8000';
  }

  // Предпросмотр по IP/кастомному хосту: ожидаем API на том же хосте, порт 8000.
  if (!prodHosts.has(host)) {
    return `${protocol}//${host}:8000`;
  }

  // Прод через nginx/proxy: API доступен на том же origin.
  return '';
}

const API = {
  // Базовый URL API выбирается автоматически по окружению.
  baseUrl: resolveApiBaseUrl(),
  token: null,

  /**
   * Set auth token after login
   */
  setToken(token) {
    this.token = token;
    localStorage.setItem('pulse-token', token);
  },

  getToken() {
    if (!this.token) {
      this.token = localStorage.getItem('pulse-token');
    }
    return this.token;
  },

  /**
   * Generic request method
   */
  async request(endpoint, options = {}) {
    const url = this.baseUrl + endpoint; // Теперь url будет http://127.0.0.1:8000/api/...
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error);
      throw error;
    }
  },

  // ===== AUTH =====
  async authViaTelegram(tgData) {
    return this.request('/api/auth/telegram', {
      method: 'POST',
      body: JSON.stringify(tgData),
    });
  },

  async register(name, phone, password) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, phone, password }),
    });
  },

  // ===== USER =====
  async getProfile() { return this.request('/user/profile'); },
  async updateProfile(data) { return this.request('/user/profile', { method: 'PATCH', body: JSON.stringify(data) }); },

  // ===== ECONOMY =====
  async getBalance() { return this.request('/economy/balance'); },
  async transfer(toUserId, amount) { return this.request('/economy/transfer', { method: 'POST', body: JSON.stringify({ to_user_id: toUserId, amount }) }); },
  async getCourse() { return this.request('/economy/course'); },
  async getTransactions(page = 1) { return this.request(`/economy/transactions?page=${page}`); },

  // ===== TOP =====
  async getTopRich() { return this.request('/top/rich'); },
  async getTopActive() { return this.request('/top/active'); },

  // ===== LOTTERY =====
  async getLotteries() { return this.request('/lottery/list'); },
  async buyTicket(lotteryId, count) { return this.request(`/lottery/${lotteryId}/buy`, { method: 'POST', body: JSON.stringify({ count }) }); },

  // ===== BBS =====
  async getBBSProfiles() { return this.request('/bbs/profiles'); },
  async createBBSProfile(data) { return this.request('/bbs/profile', { method: 'POST', body: JSON.stringify(data) }); },

  // ===== CHAT =====
  async getChats() { return this.request('/chat/list'); },
  async getMessages(chatId, before) { return this.request(`/chat/${chatId}/messages${before ? '?before=' + before : ''}`); },
  async sendMessage(chatId, text, replyTo) { return this.request(`/chat/${chatId}/send`, { method: 'POST', body: JSON.stringify({ text, reply_to: replyTo }) }); },

  // ===== STATS =====
  async getStats(period) { return this.request(`/stats?period=${period}`); },
};
