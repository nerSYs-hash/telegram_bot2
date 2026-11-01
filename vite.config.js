import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

function apiMockPlugin() {
  const mockWorkspaces = [
    {
      id: 1,
      name: 'Puls Chat (Основной)',
      owner_id: 1,
      is_main: true,
      members_count: 1420,
      bot_username: 'Puls_ON_bot',
      bot_token_set: true,
      created_at: '2026-05-01',
    },
    {
      id: 2,
      name: 'Puls Community Beta',
      owner_id: 1,
      is_main: false,
      members_count: 280,
      bot_username: 'Puls_Beta_bot',
      bot_token_set: true,
      created_at: '2026-05-15',
    }
  ];

  const mockStaff = [
    { user_id: 1, name: 'Илья Сергеев', username: 'ilya_dev', role: 'owner', added_at: '2026-05-01' },
    { user_id: 2, name: 'Алексей Петров', username: 'alex_petrov', role: 'admin', added_at: '2026-05-10' },
    { user_id: 3, name: 'Дмитрий Козлов', username: 'dima_kozlov', role: 'moderator', added_at: '2026-05-15' },
  ];

  const mockChats = [
    { id: -1001234567, title: 'Puls Chat — Главная группа', role: 'main' },
    { id: -1009876543, title: 'Puls Chat — Админка и Логи', role: 'admin' },
    { id: -1005544332, title: 'Puls Chat — Журнал событий', role: 'journal' },
  ];

  const mockMetrics = {
    pulse_rate: 1.25,
    bank_balance: 816904,
    users_balance: 1248000,
    total_supply: 2184320,
    emission_24h: 34120,
    emission_7d: 210000,
  };

  const mockCategories = [
    {
      id: 1,
      category: 'mining',
      name: 'Майнинг и награды',
      description: 'Параметры начисления валюты за активность в беседах',
      is_active: true,
      items: [
        { key: 'msg_reward', label: 'Награда за сообщение', value: '0.5', unit: '💎', type: 'number', is_active: true, description: 'Начисляется за каждое содержательное сообщение' },
        { key: 'daily_cap', label: 'Дневной лимит сбора', value: '500', unit: '💎', type: 'number', is_active: true, description: 'Максимальный объём добычи в сутки' },
        { key: 'reaction_reward', label: 'Награда за реакции', value: '0.1', unit: '💎', type: 'number', is_active: true, description: 'Бонус за поставленные и полученные реакции' }
      ]
    },
    {
      id: 2,
      category: 'lottery',
      name: 'Лотерея и Синдикаты',
      description: 'Параметры тиражей, стоимость билетов и призовой фонд',
      is_active: true,
      items: [
        { key: 'ticket_price', label: 'Стоимость билета', value: '100', unit: '💎', type: 'number', is_active: true, description: 'Цена одного лотерейного билета' },
        { key: 'jackpot_tax', label: 'Отчисление в Джекпот', value: '20', unit: '%', type: 'number', is_active: true, description: 'Процент от продаж билетов, идущий в суперприз' },
        { key: 'draw_interval', label: 'Интервал тиражей', value: '2', unit: 'ч', type: 'number', is_active: true, description: 'Частота проведения розыгрышей' }
      ]
    },
    {
      id: 3,
      category: 'transfers',
      name: 'P2P Переводы и Комиссии',
      description: 'Правила прямых переводов между участниками сообщества',
      is_active: true,
      items: [
        { key: 'transfer_fee', label: 'Комиссия за перевод', value: '0', unit: '%', type: 'number', is_active: true, description: 'Комиссия платформы при P2P отправке' },
        { key: 'min_transfer', label: 'Минимальный перевод', value: '10', unit: '💎', type: 'number', is_active: true, description: 'Минимальная сумма для одной транзакции' },
        { key: 'max_transfer_daily', label: 'Суточный лимит переводов', value: '50000', unit: '💎', type: 'number', is_active: true, description: 'Максимальная сумма переводов в день' }
      ]
    },
    {
      id: 4,
      category: 'referrals',
      name: 'Реферальная система',
      description: 'Бонусы за приглашение новых участников в чат',
      is_active: true,
      items: [
        { key: 'invite_bonus', label: 'Бонус за приглашённого', value: '250', unit: '💎', type: 'number', is_active: true, description: 'Единовременная выплата за верификацию друга' },
        { key: 'revshare_percent', label: 'Процент от майнинга реферала', value: '5', unit: '%', type: 'number', is_active: true, description: 'Пассивный доход от активности рефералов' }
      ]
    }
  ];

  const mockFeatures = [
    { id: 'economy', name: 'Pulse Economy & Кошелёк', enabled: true, category: 'core', desc: 'Управление балансами, майнинг, переводы валюты 💎' },
    { id: 'lottery', name: 'Pulse Лотерея', enabled: true, category: 'economy', desc: 'Розыгрыш джекпотов и покупка счастливых билетов' },
    { id: 'bbs', name: 'Pulse BBS (Анкеты и Знакомства)', enabled: true, category: 'social', desc: 'Сервис знакомств и объявлений внутри сообщества' },
    { id: 'stats', name: 'Аналитика и ТОП-5', enabled: true, category: 'social', desc: 'Рейтинги богатства, активности и статистика сообщений' },
    { id: 'calls', name: 'Голосовые и видеозвонки', enabled: true, category: 'core', desc: 'WebRTC P2P защищенные вызовы между участниками' },
    { id: 'press_release', name: 'Пресс-релизы и Вещание', enabled: true, category: 'tools', desc: 'Официальные рассылки и системные анонсы в каналы' },
    { id: 'titles', name: 'Система титулов и бейджей', enabled: true, category: 'tools', desc: 'Кастомные роли и префиксы над именами участников' },
    { id: 'moderation', name: 'Авто-модератор и фильтры', enabled: true, category: 'core', desc: 'Защита от спама, мут нарушителей, аудит действий' },
  ];

  const mockTriggers = [
    { id: 1, name: 'Приветствие новичков', trigger_type: 'member_join', is_active: true, response_text: 'Добро пожаловать в Puls Chat! Ознакомьтесь с правилами в закрепе.' },
    { id: 2, name: 'Фильтр внешних ссылок', trigger_type: 'link_filter', is_active: true, response_text: 'Публикация ссылок разрешена только верифицированным участникам.' },
    { id: 3, name: 'Награда за 100 сообщений', trigger_type: 'message_count', is_active: true, response_text: 'Поздравляем с достижением 100 сообщений! Вам начислено 50 💎!' },
  ];

  const mockJournal = [
    { id: 101, timestamp: '15 окт 2026, 14:10', admin_name: 'Илья Сергеев', action: 'Обновление параметров модуля Экономика', details: 'Курс 1💎 = 1.25₽' },
    { id: 102, timestamp: '15 окт 2026, 13:45', admin_name: 'Алексей Петров', action: 'Публикация пресс-релиза', details: 'Релиз версии 2.0' },
    { id: 103, timestamp: '15 окт 2026, 12:30', admin_name: 'Система', action: 'Выплата тиража лотереи #42', details: 'Победитель получил 25 000 💎' },
    { id: 104, timestamp: '14 окт 2026, 18:20', admin_name: 'Дмитрий Козлов', action: 'Блокировка спамера @spambot_33', details: 'Нарушение правил общения' },
  ];

  const handler = (req, res, next) => {
    if (!req.url.startsWith('/api/')) return next();

    const sendJson = (data) => {
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.end(JSON.stringify(data));
    };

    const url = req.url;
    if (/\/api\/auth\/me(\?|$)/.test(url)) {
      return sendJson({
        user_id: 1, first_name: 'Илья', last_name: 'Сергеев', username: 'ilya_dev',
        is_admin: true, is_owner: true, role: 'owner'
      });
    }
    if (/\/api\/admin\/profile\/me(\?|$)/.test(url)) {
      return sendJson({ user_id: 1, name: 'Илья Сергеев', role_raw: 'owner', permissions: ['*'], is_owner: true });
    }
    if (/\/api\/workspaces\/[0-9]+(\?|$)/.test(url)) {
      return sendJson({ workspace: mockWorkspaces[0], members: mockStaff, chats: mockChats });
    }
    if (/\/api\/workspaces(\?|$)/.test(url)) {
      return sendJson({ workspaces: mockWorkspaces });
    }
    if (/\/api\/economy\/metrics(\?|$)/.test(url)) {
      return sendJson(mockMetrics);
    }
    if (/\/api\/economy\/categories(\?|$)/.test(url)) {
      return sendJson(mockCategories);
    }
    if (/\/api\/features(\?|$)/.test(url) || /\/api\/modules(\?|$)/.test(url)) {
      return sendJson(mockFeatures);
    }
    if (/\/api\/triggers(\?|$)/.test(url)) {
      return sendJson(mockTriggers);
    }
    if (/\/api\/staff(\?|$)/.test(url)) {
      return sendJson(mockStaff);
    }
    if (/\/api\/journal(\?|$)/.test(url)) {
      return sendJson(mockJournal);
    }
    if (/\/api\/ui_settings(\?|$)/.test(url)) {
      return sendJson({ theme: 'light', brand_color: '#3390ec', chat_title: 'Puls Chat', show_widgets: true });
    }
    if (/\/api\/topics(\?|$)/.test(url)) {
      return sendJson([
        { id: 1, name: 'Общий чат' }, { id: 2, name: 'Разработка и баги' },
        { id: 3, name: 'Идеи и предложения' }, { id: 4, name: 'Официальные новости' }
      ]);
    }
    if (/\/api\/stats\/heatmap(\?|$)/.test(url)) {
      const heatHours = Array.from({ length: 7 }, (_, d) =>
        Array.from({ length: 24 }, (_, h) => Math.floor(Math.sin((h + d) / 3) * 20 + 25))
      );
      return sendJson({
        active: heatHours,
        messages: heatHours.map(row => row.map(v => v * 4)),
        daily: [
          { date: '2026-10-10', active: 140, messages: 890 },
          { date: '2026-10-11', active: 165, messages: 1120 },
          { date: '2026-10-12', active: 180, messages: 1250 },
          { date: '2026-10-13', active: 195, messages: 1420 },
          { date: '2026-10-14', active: 210, messages: 1580 },
          { date: '2026-10-15', active: 230, messages: 1750 },
        ]
      });
    }
    if (/\/api\/stats\/series(\?|$)/.test(url)) {
      const mockDays = ['10 окт', '11 окт', '12 окт', '13 окт', '14 окт', '15 окт'];
      return sendJson({
        users: mockDays.map((d, i) => ({ day: d, joined: 20 + i * 5, left: 3 + i, total: 1350 + i * 20 })),
        messages: mockDays.map((d, i) => ({ day: d, count: 1200 + i * 150, text: 1000 + i * 120, media: 200 + i * 30 })),
        engagement: mockDays.map((d, i) => ({ day: d, rate: 68 + i * 2 })),
        first_message: mockDays.map((d, i) => ({ day: d, count: 15 + i * 2 })),
        active_summary: mockDays.map((d, i) => ({ day: d, dau: 340 + i * 25, wau: 920 + i * 30, mau: 1420 })),
        new_returning: mockDays.map((d, i) => ({ day: d, new_users: 18 + i * 3, returning: 320 + i * 20 })),
        message_stats: mockDays.map((d, i) => ({ day: d, text: 850 + i * 50, photo: 120 + i * 10, voice: 90 + i * 15, video: 40 + i * 5 })),
        user_activity: mockDays.map((d, i) => ({ day: d, active_1_plus: 290 + i * 15, active_5_plus: 140 + i * 10, active_20_plus: 65 + i * 5 })),
      });
    }
    if (/\/api\/titles/.test(url)) {
      return sendJson({
        packages: [
          { id: 1, name: 'Премиум Титул «Магнат 💎»', price: 5000, active_users: 14 },
          { id: 2, name: 'Титул «Активист ⚡»', price: 1500, active_users: 48 },
          { id: 3, name: 'Титул «Легенда Чаттинга 👑»', price: 12000, active_users: 5 }
        ],
        settings: { enabled: true, prefix_enabled: true }
      });
    }
    if (/\/api\/admin\/permissions\/catalog(\?|$)/.test(url)) {
      return sendJson({
        modules: ['economy', 'lottery', 'bbs', 'stats', 'calls', 'press', 'titles', 'moderation'],
        permissions: ['economy.view', 'economy.edit', 'stats.view', 'modules.toggle', 'press.publish', 'staff.manage', 'workspaces.manage']
      });
    }
    if (/\/api\/admin\/permissions\/roles(\?|$)/.test(url)) {
      return sendJson({
        roles: [
          { role: 'owner', name: 'Владелец', permissions: ['*'] },
          { role: 'admin', name: 'Администратор', permissions: ['economy.view', 'economy.edit', 'stats.view', 'modules.toggle', 'press.publish'] },
          { role: 'moderator', name: 'Модератор', permissions: ['stats.view', 'moderation.mute'] }
        ]
      });
    }

    if (/\/api\/press-releases(\?|$)/.test(url)) {
      return sendJson([
        {
          id: 1,
          title: 'Запуск масштабного обновления Puls Chat 2.0',
          text: 'Мы рады представить полностью переработанную экосистему Puls Chat: новые воркспейсы, обновлённая экономика и расширенные возможности администрирования.',
          status: 'scheduled',
          scheduled_for: '2026-10-20T12:00:00Z',
          chats: [-1001234567],
          author_id: 1,
          created_at: '2026-10-15T10:00:00Z',
        },
        {
          id: 2,
          title: 'Еженедельный дайджест сообщества',
          text: 'Итоги недели: статистика активности участников, победители синдиката и топ майнеров.',
          status: 'draft',
          chats: [],
          author_id: 1,
          created_at: '2026-10-14T15:30:00Z',
        },
        {
          id: 3,
          title: 'Технические работы завершены',
          text: 'Все сервисы работают в штатном режиме.',
          status: 'sent',
          sent_at: '2026-10-12T08:00:00Z',
          chats: [-1001234567],
          author_id: 1,
          created_at: '2026-10-12T07:45:00Z',
        }
      ]);
    }
    if (/\/api\/bot-chats/.test(url)) {
      return sendJson([
        { id: -1001234567, title: 'Puls Chat — Главная группа', type: 'supergroup', member_count: 1420 },
        { id: -1009876543, title: 'Puls Chat — Админка и Логи', type: 'supergroup', member_count: 12 },
      ]);
    }
    if (/\/api\/press-release-templates/.test(url)) {
      return sendJson([]);
    }
    if (/\/api\/branding/.test(url)) {
      return sendJson({
        signature_enabled: true,
        signature_text: '— Команда Puls Chat',
        button_text: 'Присоединиться к Puls',
        button_url: 'https://t.me/Puls_ON_bot',
      });
    }

    return sendJson({ ok: true, status: 'success', message: 'OK' });
  };

  return {
    name: 'api-mock-plugin',
    configureServer(server) {
      server.middlewares.use(handler);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler);
    }
  };
}

export default defineConfig({
  plugins: [
    react({
      fastRefresh: false,
    }),
    apiMockPlugin(),
  ],
  build: {
    outDir: 'dist',
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    hmr: false,
  },
  preview: {
    host: '0.0.0.0',
    port: 3000,
  },
});
