import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Brush
} from 'recharts';
import { 
  Home, Users, Settings, Send, Power, Menu, X, Calendar, Heart, 
  ShieldAlert, ScrollText, PieChart, Trash2, PlusCircle, AlertOctagon, 
  CheckCircle2, Info, Edit, ShieldBan, Clock, MessageSquareX, 
  Zap, Bot, Sparkles, Loader2, Download, FileSpreadsheet,
  FileText, TrendingUp, TrendingDown, Activity, ChevronRight,
  Wallet, Ghost, MessageCircle, UserSearch, UserCheck,
  ChevronDown, ChevronUp, Globe, User, Image as ImageIcon, Video, Smile, Link2,
  Flame, HeartHandshake, Dices, Coins, ShieldCheck, UserMinus, Percent,
  Megaphone, PartyPopper, Wrench, Bug,
  GripVertical, Play, Square, Copy, Search
} from 'lucide-react';

// ═══════════════════════════════════════════
//  СПИСОК ОБНОВЛЕНИЙ — добавляй сюда при каждом релизе
//  type: 'new' | 'fix' | 'improve'
// ═══════════════════════════════════════════
const UPDATES = [
  {
    version: 'V1.11',
    date: '15 апреля 2026',
    title: '🚀 Запуск веб-панели управления',
    items: [
      { type: 'new',     tag: 'site',       text: 'Веб-сайт puls-chat.ru — теперь можно управлять ботом прямо из браузера' },
      { type: 'new',     tag: 'statistics', text: 'Статистика чата: графики активности, периоды (сегодня / неделя / месяц / год), экспорт в Excel' },
      { type: 'new',     tag: 'journal',    text: 'Журнал событий: все входы, нарушения триггеров, муты и баны в одном месте с фильтрами' },
      { type: 'new',     tag: 'triggers',   text: 'Управление триггерами: создание и редактирование через удобный 4-шаговый мастер' },
      { type: 'new',     tag: 'site',       text: 'Раздел Обновления — история изменений с тегами разделов и анимацией по клику' },
      { type: 'improve', tag: 'journal',    text: 'Ссылки в журнале кликабельны — переход прямо к сообщению в Telegram' },
      { type: 'improve', tag: 'journal',    text: 'Текст нарушения выделяется рамкой-цитатой для удобства чтения' },
      { type: 'improve', tag: 'journal',    text: 'Записи журнала хранят до 2000 символов вместо 200 — больше не обрезается' },
      { type: 'improve', tag: 'site',       text: 'Иконки в меню дёргаются при нажатии — приятная обратная связь' },
      { type: 'fix',     tag: 'site',       text: 'При обновлении страницы остаёшься на той же вкладке' },
      { type: 'fix',     tag: 'journal',    text: 'Фильтры журнала работают корректно для всех типов событий' },
    ],
  },
];

const LATEST_VERSION = UPDATES[0].version;

export default function App() {
  const [activeTab, setActiveTab] = useState(() => window.location.hash.slice(1) || 'statistics');
  const navigateTo = (id) => {
    setActiveTab(id);
    window.location.hash = id;
    if (id === 'updates') {
      localStorage.setItem('lastSeenUpdate', LATEST_VERSION);
      setHasNewUpdate(false);
    }
  };
  const [hasNewUpdate, setHasNewUpdate] = useState(
    () => localStorage.getItem('lastSeenUpdate') !== LATEST_VERSION
  );
  const [jigglingTag, setJigglingTag] = useState(null);
  const triggerJiggle = (key) => { setJigglingTag(key); };
  const [jigglingNav, setJigglingNav] = useState(null);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [showDetailedIndices, setShowDetailedIndices] = useState(false);
  const [activeIndexTooltip, setActiveIndexTooltip] = useState(null);
  const [showHealthTooltip, setShowHealthTooltip] = useState(false);

  // ================= СОСТОЯНИЯ: ТРИГГЕРЫ =================
  // editingTrigger !== null → показываем страницу редактора вместо списка
  const [editingTrigger, setEditingTrigger] = useState(null);
  const [triggers, setTriggers] = useState([]);
  const [triggersLoading, setTriggersLoading] = useState(false);
  const [showMediaPicker, setShowMediaPicker] = useState(false);
  const [showConditionPicker, setShowConditionPicker] = useState(false);
  const [showActionPicker, setShowActionPicker] = useState(false);
  const [condSignalTab, setCondSignalTab] = useState('message');
  const [showTriggerEditMenu, setShowTriggerEditMenu] = useState(false);
  const [triggerSearch, setTriggerSearch] = useState('');
  const [showTriggerMenu, setShowTriggerMenu] = useState(false);
  const [togglingTrigger, setTogglingTrigger] = useState(null);
  const [copyingTrigger, setCopyingTrigger] = useState(null);
  const [dragId, setDragId] = useState(null);

  const fetchTriggers = () => {
    setTriggersLoading(true);
    fetch('/api/triggers')
      .then(r => r.json())
      .then(data => { setTriggers(Array.isArray(data) ? data : []); setTriggersLoading(false); })
      .catch(() => setTriggersLoading(false));
  };

  const toggleTrigger = async (id) => {
    setTogglingTrigger(id);
    try {
      const r = await fetch(`/api/triggers/${id}/toggle`, { method: 'PATCH' });
      const data = await r.json();
      setTriggers(prev => prev.map(t => t.id === id ? { ...t, is_enabled: data.is_enabled } : t));
    } catch {}
    setTogglingTrigger(null);
  };

  const copyTrigger = async (id) => {
    setCopyingTrigger(id);
    try {
      await fetch(`/api/triggers/${id}/copy`, { method: 'POST' });
      fetchTriggers();
    } catch {}
    setCopyingTrigger(null);
  };

  // Drag & drop для активных триггеров
  const handleDragStart = (id) => setDragId(id);
  const handleDrop = (targetId) => {
    if (!dragId || dragId === targetId) return;
    setTriggers(prev => {
      const active = prev.filter(t => t.is_enabled);
      const inactive = prev.filter(t => !t.is_enabled);
      const fromIdx = active.findIndex(t => t.id === dragId);
      const toIdx   = active.findIndex(t => t.id === targetId);
      if (fromIdx === -1 || toIdx === -1) return prev;
      const reordered = [...active];
      const [moved] = reordered.splice(fromIdx, 1);
      reordered.splice(toIdx, 0, moved);
      return [...reordered, ...inactive];
    });
    setDragId(null);
  };

  useEffect(() => { fetchTriggers(); }, []);
  useEffect(() => { if (activeTab === 'journal') fetchJournal(); }, [activeTab]);

  // ================= СОСТОЯНИЯ: ШИППЕР =================
  const [shipperSettings, setShipperSettings] = useState({
    enabled: true,
    minHours: 2,
    maxHours: 5,
    mode: 'active_48',
    categories: [
      { id: 'hot18', name: '🔥 Горячие / 18+', count: 42, active: true },
      { id: 'funny', name: '😂 Смешные / Подколы', count: 28, active: true },
      { id: 'romantic', name: '💘 Милые / Романтика', count: 15, active: false }
    ]
  });

  // ================= СОСТОЯНИЯ: СИСТЕМА =================
  const [systemStats, setSystemStats] = useState({
    pulseRate: 1.42,
    bankBalance: 12500450.20,
    difficultyK: 5.0,
  });

  // ── Стафф (администраторы) ──
  const [staffList, setStaffList] = useState([]);
  const [staffLoading, setStaffLoading] = useState(false);
  const [newAdminId, setNewAdminId] = useState('');
  const [staffError, setStaffError] = useState('');
  const [staffAdding, setStaffAdding] = useState(false);
  const [staffRemoving, setStaffRemoving] = useState(null);

  const fetchStaff = () => {
    setStaffLoading(true);
    fetch('/api/staff')
      .then(r => r.json())
      .then(data => { setStaffList(Array.isArray(data) ? data : []); setStaffLoading(false); })
      .catch(() => setStaffLoading(false));
  };

  const addAdmin = async () => {
    const uid = newAdminId.trim().replace('@', '');
    if (!uid) return;
    setStaffAdding(true); setStaffError('');
    try {
      const r = await fetch('/api/staff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: uid }),
      });
      const data = await r.json();
      if (!r.ok) { setStaffError(data.detail || 'Ошибка'); }
      else { setNewAdminId(''); fetchStaff(); }
    } catch { setStaffError('Сетевая ошибка'); }
    setStaffAdding(false);
  };

  const removeAdmin = async (userId) => {
    setStaffRemoving(userId);
    try {
      const r = await fetch(`/api/staff/${userId}`, { method: 'DELETE' });
      const data = await r.json();
      if (!r.ok) { setStaffError(data.detail || 'Ошибка'); }
      else { fetchStaff(); }
    } catch { setStaffError('Сетевая ошибка'); }
    setStaffRemoving(null);
  };

  useEffect(() => { if (activeTab === 'system') fetchStaff(); }, [activeTab]);

  // ================= СОСТОЯНИЯ: ЖУРНАЛ =================
  const logTags = [
    { id: 'all',          label: 'Все' },
    { id: 'trigger',      label: '#Триггер' },
    { id: 'mute',         label: '#Мут' },
    { id: 'unmute',       label: '#Размут' },
    { id: 'ban',          label: '#Бан' },
    { id: 'unban',        label: '#Разбан' },
    { id: 'kick',         label: '#Исключен' },
    { id: 'warn',         label: '#Варн' },
    { id: 'join',         label: '#Вход' },
    { id: 'leave',        label: '#Выход' },
    { id: 'blacklist',    label: '#Блокировка' },
    { id: 'admin',        label: '#Админ' },
    { id: 'survey',       label: '#Опрос' },
    { id: 'profile',      label: '#Профиль' },
    { id: 'activity',     label: '#Активность' },
    { id: 'photo',        label: '#Фото' },
  ];
  const [logFilter, setLogFilter] = useState('all');
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const fetchJournal = () => {
    setLogsLoading(true);
    fetch('/api/journal')
      .then(r => r.json())
      .then(data => { setLogs(Array.isArray(data) ? data : []); setLogsLoading(false); })
      .catch(() => setLogsLoading(false));
  };
  
  // ================= СОСТОЯНИЯ: ФУНКЦИИ БОТА =================
  const [botFeatures, setBotFeatures] = useState([]);
  const [featuresLoading, setFeaturesLoading] = useState(false);
  const [togglingFeature, setTogglingFeature] = useState(null);

  const fetchFeatures = () => {
    setFeaturesLoading(true);
    fetch('/api/features')
      .then(r => r.json())
      .then(data => { setBotFeatures(Array.isArray(data) ? data : []); setFeaturesLoading(false); })
      .catch(() => setFeaturesLoading(false));
  };

  const toggleFeature = async (featureId) => {
    setTogglingFeature(featureId);
    try {
      const r = await fetch(`/api/features/${featureId}/toggle`, { method: 'POST' });
      const data = await r.json();
      setBotFeatures(prev => prev.map(f => f.id === featureId ? { ...f, enabled: data.enabled } : f));
    } catch { }
    setTogglingFeature(null);
  };

  useEffect(() => { fetchFeatures(); }, []);

  // ================= СОСТОЯНИЯ: СТАТИСТИКА =================
  const PERIODS = [
    { id: 'today',     label: 'Сегодня' },
    { id: 'yesterday', label: 'Вчера'   },
    { id: 'week',      label: 'Неделя'  },
    { id: 'month',     label: 'Месяц'   },
    { id: 'year',      label: 'Год'     },
  ];
  const [statsPeriod, setStatsPeriod] = useState('today');
  const [liveStats, setLiveStats]     = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const fetchStats = useCallback((period) => {
    setStatsLoading(true);
    fetch(`/api/stats?period=${period}`)
      .then(r => r.json())
      .then(data => { setLiveStats(data); setStatsLoading(false); })
      .catch(() => setStatsLoading(false));
  }, []);

  useEffect(() => { fetchStats('today'); }, []);

  const handlePeriodChange = (period) => {
    setStatsPeriod(period);
    fetchStats(period);
    setShowDetailedIndices(false);
    setActiveIndexTooltip(null);
    setShowHealthTooltip(false);
  };

  const exportExcel = () => {
    window.open(`/api/stats/export?period=${statsPeriod}`, '_blank');
  };

  // ================= ФУНКЦИИ =================
  const openTriggerModal = (t = null) => {
    if (t) {
      // конвертируем старый формат → новый (conditions/actions arrays)
      setEditingTrigger({
        ...t,
        conditions: t.keyword ? [{
          id: 1, signal: 'message', type: 'keyword',
          condition: t.condition || 'contains', keyword: t.keyword || ''
        }] : [],
        actions: [{
          id: 1, type: t.action || 'send_text',
          reply_text: t.reply_text || '',
          media_type: t.media_type || 'none',
          reply_target: t.reply_target || 'none',
          bot_msg_delete: t.bot_msg_delete || 'no',
          bot_msg_delete_after: t.bot_msg_delete_after || 60,
          duration: t.duration || '',
          emoji: t.emoji || ''
        }]
      });
    } else {
      setEditingTrigger({
        id: null, name: '', probability: 100,
        where: 'chat', from: 'all',
        conditions: [], actions: []
      });
    }
    setShowConditionPicker(false);
    setShowActionPicker(false);
    setShowTriggerEditMenu(false);
    setCondSignalTab('message');
    setShowMediaPicker(false);
    navigateTo('triggers');
  };

  const saveTrigger = () => {
    const firstCond   = (editingTrigger.conditions || [])[0] || {};
    const firstAction = (editingTrigger.actions    || [])[0] || {};
    const body = {
      name:                 editingTrigger.name,
      condition:            firstCond.condition    || 'contains',
      keyword:              firstCond.keyword      || '',
      probability:          editingTrigger.probability,
      where:                editingTrigger.where   || 'chat',
      from_who:             editingTrigger.from    || 'all',
      action:               firstAction.type       || 'send_text',
      duration:             firstAction.duration   || '',
      reply_text:           firstAction.reply_text || '',
      media_type:           firstAction.media_type || 'none',
      bot_msg_delete:       firstAction.bot_msg_delete       || 'no',
      bot_msg_delete_after: firstAction.bot_msg_delete_after || 60,
    };
    const isEdit = !!editingTrigger.id;
    const url    = isEdit ? `/api/triggers/${editingTrigger.id}` : '/api/triggers';
    const method = isEdit ? 'PUT' : 'POST';
    fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(r => r.json())
      .then(() => { fetchTriggers(); setEditingTrigger(null); })
      .catch(() => setEditingTrigger(null));
  };

  const deleteTrigger = (id) => {
    fetch(`/api/triggers/${id}`, { method: 'DELETE' })
      .then(() => fetchTriggers());
  };

  const ChartTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-gray-900 text-white px-4 py-3 rounded-2xl shadow-2xl border border-gray-700">
        <p className="text-[10px] font-black text-gray-400 uppercase mb-1">{label}</p>
        <p className="text-2xl font-black leading-none">{(payload[0].value || 0).toLocaleString()}</p>
        <p className="text-[9px] text-blue-400 font-bold mt-1">сообщений</p>
      </div>
    );
  };

  const navigation = [
    { id: 'updates',   name: 'Обновления', icon: Megaphone, group: 'top' },
    { id: 'statistics', name: 'Статистика', icon: PieChart, group: 'main' },
    { id: 'journal', name: 'Журнал', icon: ScrollText, group: 'main' },
    { id: 'triggers', name: 'Триггеры', icon: ShieldAlert, group: 'modules' },
    { id: 'shipper', name: 'Шиппер', icon: HeartHandshake, group: 'modules' },
    { id: 'system', name: 'Система', icon: Settings, group: 'main' },
    { id: 'broadcast', name: 'Рассылка', icon: Send, group: 'features' },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'statistics':
        return (
          <div className="space-y-4 pb-24">

            {/* ── Period switcher ── */}
            <div className="flex space-x-2 overflow-x-auto pb-1 -mx-4 px-4 scrollbar-hide">
              {PERIODS.map(p => (
                <button key={p.id} onClick={() => handlePeriodChange(p.id)}
                  className={`flex-shrink-0 px-5 py-2.5 rounded-2xl font-black text-[11px] uppercase tracking-wide transition-all duration-300 ${
                    statsPeriod === p.id
                      ? 'bg-gray-900 text-white shadow-lg scale-105'
                      : 'bg-white text-gray-400 border border-gray-100'
                  }`}>
                  {p.label}
                </button>
              ))}
            </div>

            {/* ── Hero: Health index ── */}
            {(() => {
              const INDEX_META = {
                oksp:   { label: 'Общая активность',      desc: 'Среднее кол-во сообщений на одного активного участника × 10. Показывает насколько активно общается каждый.' },
                sdsp:   { label: 'Диалоговость',          desc: 'Доля сообщений с ответами (reply) от общего числа сообщений. Высокое значение = живое общение, не монологи.' },
                cho:    { label: 'Эмоциональность',       desc: 'Доля сообщений, получивших реакции. Чем больше — тем сильнее люди реагируют на контент.' },
                media:  { label: 'Медиаактивность',       desc: 'Доля медиафайлов (фото, видео, GIF) от всех сообщений. Отражает разнообразие контента.' },
                korp:   { label: 'Вовлечённость',         desc: 'Суммарный отклик (ответы + реакции) к числу сообщений. Главный показатель живости чата.' },
                kopyup: { label: 'Прирост участников',    desc: '(Вступили − Вышли) / Всего участников. Положительное значение = чат растёт.' },
              };
              const idxData = liveStats?.indices || {};
              return (
                <div className={`bg-gradient-to-br from-indigo-700 via-blue-700 to-blue-500 rounded-[3rem] p-8 text-white shadow-xl relative overflow-hidden border border-white/10 transition-all duration-500 ${statsLoading ? 'opacity-60' : 'opacity-100'}`}>
                  <div className="absolute -top-10 -right-10 opacity-10 scale-150 rotate-12"><Activity size={200} /></div>
                  <div className="relative z-10">
                    {/* Строка 1: бейдж + период */}
                    <div className="flex items-center justify-between mb-5">
                      <div className="flex items-center space-x-2 bg-white/20 px-4 py-1.5 rounded-full backdrop-blur-md">
                        <Zap size={14} className="text-yellow-300 fill-yellow-300" />
                        <span className="text-[10px] font-black uppercase tracking-widest">Индекс здоровья</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] font-black bg-white/10 px-3 py-1 rounded-full uppercase">
                          {liveStats?.periodLabel || 'Сегодня'}
                        </span>
                        {/* ℹ кнопка — вверху справа */}
                        <div className="relative">
                          <button
                            onClick={() => setShowHealthTooltip(v => !v)}
                            className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-xs font-black hover:bg-white/30 transition-all"
                          >ℹ</button>
                          {showHealthTooltip && (
                            <div className="absolute top-9 right-0 w-64 bg-gray-900 text-white text-xs rounded-2xl p-4 z-50 shadow-2xl">
                              <p className="font-black mb-2">Формула индекса здоровья:</p>
                              <p className="opacity-80 leading-relaxed">Общая акт.×25% + Диалоговость×15% + Эмоц.×15% + Медиа×10% + Вовлечённость×20% + Прирост×15%</p>
                              <p className="opacity-60 mt-2 text-[10px]">Каждый субиндекс — реальные данные за выбранный период.</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    {/* Строка 2: большое число */}
                    <div className="text-8xl font-black tracking-tighter leading-none mb-6">
                      {statsLoading ? <Loader2 size={48} className="animate-spin opacity-50" /> : (liveStats?.healthIndex ?? 0)}
                      {!statsLoading && <span className="text-2xl ml-1 opacity-50">%</span>}
                    </div>
                    {/* Кнопка раскрытия субиндексов */}
                    <button onClick={() => setShowDetailedIndices(!showDetailedIndices)}
                      className="w-full flex justify-between items-center text-[10px] font-black uppercase tracking-widest border-t border-white/10 pt-4">
                      <span>Детальные показатели</span>
                      {showDetailedIndices ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    {showDetailedIndices && (
                      <div className="space-y-1 pt-3 animate-in slide-in-from-top-2 duration-300">
                        {Object.entries(INDEX_META).map(([k, meta]) => (
                          <div key={k}>
                            <div className="flex items-center justify-between py-2 px-3 rounded-xl">
                              <span className="text-xs font-bold opacity-75">{meta.label}</span>
                              <div className="flex items-center space-x-2 flex-shrink-0">
                                <span className="text-sm font-black">{idxData[k] !== undefined ? idxData[k] : '—'}</span>
                                <button
                                  onClick={() => setActiveIndexTooltip(activeIndexTooltip === k ? null : k)}
                                  className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center text-[10px] font-black hover:bg-white/30 transition-all flex-shrink-0"
                                >ℹ</button>
                              </div>
                            </div>
                            {activeIndexTooltip === k && (
                              <div className="mx-3 mb-2 bg-white/15 backdrop-blur-sm text-white text-[10px] rounded-xl p-3 leading-relaxed border border-white/10 animate-in slide-in-from-top-1 duration-200">
                                {meta.desc}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* ── Recharts AreaChart ── */}
            <div className={`bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm transition-all duration-500 ${statsLoading ? 'opacity-40' : 'opacity-100'}`}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-widest flex items-center">
                  <Activity size={14} className="mr-2 text-blue-500" /> Пульс активности
                </h3>
                <span className="text-[10px] font-black text-blue-500 bg-blue-50 px-3 py-1 rounded-full">
                  {(liveStats?.history || []).reduce((s, d) => s + d.val, 0).toLocaleString()} сообщ.
                </span>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={liveStats?.history || []} margin={{ top: 5, right: 5, left: -30, bottom: 0 }}>
                  <defs>
                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 10, fontWeight: 900, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: '#d1d5db' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#e2e8f0', strokeWidth: 2 }} />
                  <Area type="monotone" dataKey="val" stroke="#3b82f6" strokeWidth={3}
                    fill="url(#areaGrad)" dot={false} activeDot={{ r: 6, fill: '#3b82f6', stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={600} animationEasing="ease-out" />
                  <Brush
                    dataKey="day"
                    height={38}
                    stroke="#3b82f6"
                    fill="#dbeafe"
                    travellerWidth={14}
                    tickFormatter={() => ''}
                    startIndex={Math.max(0, (liveStats?.history?.length || 0) - 10)}
                    traveller={({ x, y, width, height: h }) => (
                      <g>
                        <rect x={x} y={y + 4} width={width} height={h - 8}
                          rx={6} fill="#3b82f6" stroke="#fff" strokeWidth={2} />
                        <line x1={x + width/2} y1={y + h/2 - 5} x2={x + width/2} y2={y + h/2 + 5}
                          stroke="#fff" strokeWidth={1.5} strokeLinecap="round" />
                      </g>
                    )}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* ── Метрики 2×2 ── */}
            <div className={`grid grid-cols-2 gap-4 transition-all duration-500 ${statsLoading ? 'opacity-40' : 'opacity-100'}`}>
              {[
                { label: 'Сообщений',      val: (liveStats?.messages    ?? 0).toLocaleString(), color: 'text-blue-500',   bg: 'bg-blue-50',   icon: MessageSquareX },
                { label: 'Активных',       val: (liveStats?.activeUsers ?? 0).toString(),        color: 'text-indigo-500', bg: 'bg-indigo-50', icon: Users          },
                { label: 'Вступили',       val: `+${liveStats?.joined   ?? 0}`,                  color: 'text-green-500',  bg: 'bg-green-50',  icon: TrendingUp     },
                { label: 'Вышли',          val: `-${liveStats?.left     ?? 0}`,                  color: 'text-red-500',    bg: 'bg-red-50',    icon: TrendingDown   },
              ].map((m, i) => (
                <div key={i} className="bg-white p-6 rounded-[2rem] border border-gray-100 shadow-sm active:scale-95 transition-all duration-200"
                  style={{ animationDelay: `${i * 60}ms` }}>
                  <div className={`w-9 h-9 ${m.bg} rounded-2xl flex items-center justify-center mb-3`}>
                    <m.icon size={18} className={m.color} />
                  </div>
                  <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest block mb-1">{m.label}</span>
                  <span className="text-3xl font-black text-gray-900 leading-none">{m.val}</span>
                </div>
              ))}
            </div>

            {/* ── Банк ── */}
            <div className={`bg-gradient-to-r from-indigo-600 to-blue-600 p-6 rounded-[2rem] text-white shadow-xl transition-all duration-500 ${statsLoading ? 'opacity-40' : 'opacity-100'}`}>
              <span className="text-[10px] font-black opacity-60 uppercase tracking-widest block mb-1 flex items-center gap-1">
                <Wallet size={10} /> Баланс банка
              </span>
              <span className="text-3xl font-black tracking-tight">
                {(liveStats?.bankBalance ?? 0).toLocaleString()} 💳
              </span>
            </div>

            {/* ── Кнопка Excel ── */}
            <button onClick={exportExcel}
              className="w-full flex items-center justify-center space-x-3 bg-white border-2 border-gray-100 text-gray-700 p-5 rounded-[2rem] font-black active:scale-95 transition-all duration-200 hover:border-green-200 hover:text-green-700 hover:bg-green-50">
              <FileSpreadsheet size={22} className="text-green-600" />
              <span>Экспорт в Excel — {PERIODS.find(p=>p.id===statsPeriod)?.label}</span>
              <Download size={18} className="text-gray-400" />
            </button>
          </div>
        );

      case 'journal':
        return (
          <div className="space-y-4 pb-24">
            <div className="flex space-x-2 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4">
              {logTags.map(tag => (
                <button key={tag.id} onClick={() => setLogFilter(tag.id)} className={`flex-shrink-0 px-6 py-3 rounded-2xl font-black text-[10px] uppercase border transition-all ${logFilter === tag.id ? 'bg-gray-900 text-white border-gray-900 scale-105 shadow-md' : 'bg-white text-gray-400 border-gray-100'}`}>{tag.label}</button>
              ))}
            </div>
            {logsLoading && (
              <div className="text-center py-8 text-gray-400 font-black text-sm">
                <Loader2 size={24} className="animate-spin mx-auto mb-2" /> Загрузка журнала...
              </div>
            )}
            {!logsLoading && logs.length === 0 && (
              <div className="text-center py-12 text-gray-300 font-black text-sm uppercase tracking-widest">
                Событий пока нет
              </div>
            )}
            {logs.filter(l => logFilter === 'all' || l.type === logFilter).map(log => {
              const TAG_STYLE = {
                trigger:      'bg-orange-50 text-orange-600 border border-orange-200',
                mute:         'bg-yellow-50 text-yellow-700 border border-yellow-200',
                unmute:       'bg-lime-50 text-lime-700 border border-lime-200',
                ban:          'bg-red-50 text-red-600 border border-red-200',
                unban:        'bg-blue-50 text-blue-600 border border-blue-200',
                kick:         'bg-rose-50 text-rose-600 border border-rose-200',
                warn:         'bg-amber-50 text-amber-600 border border-amber-200',
                join:         'bg-green-50 text-green-600 border border-green-200',
                leave:        'bg-gray-100 text-gray-500 border border-gray-200',
                blacklist:    'bg-slate-100 text-slate-600 border border-slate-300',
                admin:        'bg-indigo-50 text-indigo-600 border border-indigo-200',
                survey:       'bg-purple-50 text-purple-600 border border-purple-200',
                profile:      'bg-teal-50 text-teal-600 border border-teal-200',
                activity:     'bg-cyan-50 text-cyan-600 border border-cyan-200',
                photo:        'bg-pink-50 text-pink-600 border border-pink-200',
              };
              const tagStyle = TAG_STYLE[log.type] || 'bg-blue-50 text-blue-600 border border-blue-200';
              return (
                <div key={log.id} className="bg-white p-5 rounded-[2rem] border border-gray-100 shadow-sm space-y-3 animate-in slide-in-from-bottom-2">
                  <div className="flex justify-between items-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${tagStyle}`}>{log.tag}</span>
                    <span className="text-[11px] text-gray-300 font-mono">{log.time?.replace('T',' ')}</span>
                  </div>
                  <div
                    className="text-xs text-gray-700 leading-relaxed break-words [&_a]:text-blue-500 [&_a]:underline [&_a]:font-semibold [&_b]:font-black [&_b]:text-gray-900 [&_blockquote]:border-l-4 [&_blockquote]:border-orange-300 [&_blockquote]:bg-orange-50 [&_blockquote]:px-3 [&_blockquote]:py-2 [&_blockquote]:my-2 [&_blockquote]:rounded-r-xl [&_blockquote]:text-gray-800 [&_blockquote]:font-medium [&_blockquote]:italic"
                    dangerouslySetInnerHTML={{ __html: log.text }}
                  />
                  <div className="pt-1 space-y-2">
                    <a href={`tg://user?id=${log.user_id}`} className="flex items-center justify-center space-x-2 bg-blue-600 text-white py-3 rounded-2xl font-black text-[10px] uppercase shadow-md shadow-blue-100 active:scale-[0.98] transition-all">
                      <MessageCircle size={14}/><span>Написать в ЛС</span>
                    </a>
                    <div className="grid grid-cols-2 gap-2">
                      {log.type === 'mute'    && <button className="flex items-center justify-center space-x-1 bg-green-50 text-green-700 py-2.5 rounded-xl font-black text-[9px] uppercase border border-green-200"><UserCheck size={13}/><span>Размутить</span></button>}
                      {log.type === 'ban'     && <button className="flex items-center justify-center space-x-1 bg-blue-50 text-blue-700 py-2.5 rounded-xl font-black text-[9px] uppercase border border-blue-200"><UserCheck size={13}/><span>Разбанить</span></button>}
                      {log.type === 'trigger' && <button className="flex items-center justify-center space-x-1 bg-orange-50 text-orange-700 py-2.5 rounded-xl font-black text-[9px] uppercase border border-orange-200"><Zap size={13}/><span>Амнистия</span></button>}
                      {log.type === 'join'    && <button className="flex items-center justify-center space-x-1 bg-indigo-50 text-indigo-700 py-2.5 rounded-xl font-black text-[9px] uppercase border border-indigo-200"><UserSearch size={13}/><span>Досье</span></button>}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        );

      case 'shipper':
        return (
          <div className="space-y-6 pb-24 animate-in fade-in duration-500">
            <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm flex items-center justify-between">
              <div>
                <h3 className="font-black text-xl text-gray-900 mb-1">Модуль Шиппер</h3>
                <span className={`text-[10px] font-black uppercase tracking-widest ${shipperSettings.enabled ? 'text-green-500' : 'text-red-500'}`}>
                   {shipperSettings.enabled ? '● Активен' : '○ Отключен'}
                </span>
              </div>
              <button onClick={() => setShipperSettings({...shipperSettings, enabled: !shipperSettings.enabled})} className={`w-14 h-8 rounded-full transition-colors relative ${shipperSettings.enabled ? 'bg-green-500' : 'bg-gray-200'}`}>
                <div className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-all ${shipperSettings.enabled ? 'left-7' : 'left-1'}`} />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-3">
              <h3 className="px-4 text-[10px] font-black text-gray-400 uppercase tracking-widest">Категории</h3>
              {shipperSettings.categories.map(cat => (
                <div key={cat.id} className="bg-white p-5 rounded-3xl border border-gray-100 shadow-sm flex items-center justify-between active:scale-[0.98] transition-all">
                  <div className="flex items-center space-x-4">
                    <div className="w-12 h-12 bg-gray-50 rounded-2xl flex items-center justify-center text-xl">{cat.id === 'hot18' ? '🔥' : cat.id === 'funny' ? '😂' : '💘'}</div>
                    <span className="font-black text-gray-900">{cat.name}</span>
                  </div>
                  <ChevronRight size={20} className="text-gray-300" />
                </div>
              ))}
            </div>

            <div className="bg-gray-900 text-white rounded-[2.5rem] p-8 space-y-6">
               <div className="space-y-4">
                  <h4 className="text-[10px] font-black text-blue-400 uppercase tracking-widest flex items-center"><Dices size={14} className="mr-2"/> Режим отбора</h4>
                  <div className="grid grid-cols-2 gap-2">
                    {['active_48', 'active_72', 'inactive', 'random'].map(m => (
                      <button key={m} onClick={() => setShipperSettings({...shipperSettings, mode: m})} className={`p-4 rounded-2xl font-black text-[9px] uppercase border transition-all ${shipperSettings.mode === m ? 'bg-blue-600 border-blue-600 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}>
                        {m === 'active_48' ? '48ч' : m === 'active_72' ? '72ч' : m === 'inactive' ? 'Спящие' : 'Рандом'}
                      </button>
                    ))}
                  </div>
               </div>
            </div>
          </div>
        );

      case 'system':
        return (
          <div className="space-y-6 pb-24 animate-in fade-in duration-500">
             <div className="grid grid-cols-1 gap-4">
                <div className="bg-white p-8 rounded-[2.5rem] border border-gray-100 shadow-sm flex items-center justify-between">
                   <div>
                      <span className="text-[10px] font-black text-blue-500 uppercase block mb-2">Курс Пульса</span>
                      <div className="flex items-baseline space-x-2">
                         <span className="text-5xl font-black text-gray-900">{liveStats?.pulseRate ?? systemStats.pulseRate}</span>
                         <span className="text-gray-400 font-bold uppercase text-xs"> manual</span>
                      </div>
                   </div>
                   <button className="p-5 bg-blue-50 text-blue-600 rounded-3xl"><Edit size={24}/></button>
                </div>

             </div>

             {/* ─── АДМИНИСТРАТОРЫ ─── */}
             <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100 space-y-4">
               <div className="flex items-center justify-between">
                 <h3 className="font-black text-gray-900 text-sm uppercase flex items-center">
                   <ShieldCheck className="mr-3 text-green-500" size={16}/> Администраторы
                 </h3>
                 <button onClick={fetchStaff} className="text-xs text-gray-400 font-bold px-3 py-1.5 bg-gray-50 rounded-xl active:scale-95 transition-all">
                   Обновить
                 </button>
               </div>

               {/* Добавить */}
               <div className="flex space-x-2">
                 <input
                   value={newAdminId}
                   onChange={e => { setNewAdminId(e.target.value); setStaffError(''); }}
                   onKeyDown={e => e.key === 'Enter' && addAdmin()}
                   placeholder="ID или @username"
                   className="flex-1 bg-gray-50 border border-gray-100 rounded-2xl px-4 py-3 text-sm font-bold focus:outline-none focus:border-blue-300"
                 />
                 <button
                   onClick={addAdmin}
                   disabled={staffAdding || !newAdminId.trim()}
                   className="px-5 py-3 bg-gray-900 text-white rounded-2xl font-black text-xs disabled:opacity-40 active:scale-95 transition-all flex items-center space-x-1"
                 >
                   {staffAdding ? <Loader2 size={14} className="animate-spin"/> : <PlusCircle size={14}/>}
                   <span>Добавить</span>
                 </button>
               </div>
               {staffError && <p className="text-xs text-red-500 font-bold px-1">{staffError}</p>}

               {/* Список */}
               {staffLoading ? (
                 <div className="flex items-center justify-center py-6 text-gray-400">
                   <Loader2 size={18} className="animate-spin mr-2"/> Загрузка...
                 </div>
               ) : (
                 <div className="space-y-2">
                   {staffList.length === 0 && (
                     <p className="text-center text-gray-300 font-black text-xs uppercase tracking-widest py-4">
                       Нет данных
                     </p>
                   )}
                   {staffList.map(m => (
                     <div key={m.user_id} className="flex items-center justify-between p-4 bg-gray-50 rounded-2xl">
                       <div>
                         <div className="font-black text-sm text-gray-900">
                           {m.username ? `@${m.username}` : `ID ${m.user_id}`}
                           {m.first_name ? ` · ${m.first_name}` : ''}
                         </div>
                         <div className="flex items-center gap-2 mt-1">
                           <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full ${m.is_owner ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'}`}>
                             {m.is_owner ? '👑 Владелец' : '🛡 Админ'}
                           </span>
                           <span className="text-[9px] text-gray-400 font-mono">{m.user_id}</span>
                         </div>
                       </div>
                       {!m.is_owner && (
                         <button
                           onClick={() => removeAdmin(m.user_id)}
                           disabled={staffRemoving === m.user_id}
                           className="p-2.5 bg-red-50 text-red-500 rounded-xl active:scale-95 transition-all disabled:opacity-40"
                         >
                           {staffRemoving === m.user_id
                             ? <Loader2 size={15} className="animate-spin"/>
                             : <UserMinus size={15}/>}
                         </button>
                       )}
                     </div>
                   ))}
                 </div>
               )}
             </div>

             {/* ─── УПРАВЛЕНИЕ ФУНКЦИЯМИ ─── */}
             <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100">
               <div className="flex items-center justify-between mb-5">
                 <h3 className="font-black text-gray-900 text-sm uppercase flex items-center">
                   <Wrench className="mr-3 text-purple-500" size={16}/> Функции бота
                 </h3>
                 <button
                   onClick={fetchFeatures}
                   className="text-xs text-gray-400 font-bold px-3 py-1.5 bg-gray-50 rounded-xl active:scale-95 transition-all"
                 >
                   Обновить
                 </button>
               </div>

               {featuresLoading && (
                 <div className="flex items-center justify-center py-8 text-gray-400">
                   <Loader2 size={20} className="animate-spin mr-2"/> Загрузка...
                 </div>
               )}

               {!featuresLoading && (
                 <div className="space-y-2">
                   {botFeatures.map(f => (
                     <div key={f.id} className="flex items-center justify-between p-3.5 bg-gray-50 rounded-2xl">
                       <span className="font-bold text-sm text-gray-800">{f.name}</span>
                       <button
                         onClick={() => toggleFeature(f.id)}
                         disabled={togglingFeature === f.id}
                         className={`relative w-12 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${
                           f.enabled ? 'bg-green-500' : 'bg-gray-300'
                         } ${togglingFeature === f.id ? 'opacity-50' : 'active:scale-95'}`}
                       >
                         <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all duration-200 ${
                           f.enabled ? 'left-[calc(100%-1.375rem)]' : 'left-0.5'
                         }`}/>
                       </button>
                     </div>
                   ))}
                 </div>
               )}
             </div>
          </div>
        );

      case 'triggers': {
        // ── Страница редактора триггера (полный экран) ──
        if (editingTrigger) {
          const upd = (field, val) => setEditingTrigger(prev => ({...prev, [field]: val}));
          const updCond = (idx, field, val) => setEditingTrigger(prev => {
            const arr = [...(prev.conditions||[])]; arr[idx] = {...arr[idx], [field]: val}; return {...prev, conditions: arr};
          });
          const updAction = (idx, field, val) => setEditingTrigger(prev => {
            const arr = [...(prev.actions||[])]; arr[idx] = {...arr[idx], [field]: val}; return {...prev, actions: arr};
          });
          const removeCond   = (idx) => setEditingTrigger(prev => ({...prev, conditions: (prev.conditions||[]).filter((_,i)=>i!==idx)}));
          const removeAction = (idx) => setEditingTrigger(prev => ({...prev, actions: (prev.actions||[]).filter((_,i)=>i!==idx)}));
          const addCondition = (signal) => {
            setEditingTrigger(prev => ({...prev, conditions: [...(prev.conditions||[]), {id: Date.now(), signal, type:'keyword', condition:'contains', keyword:''}]}));
            setShowConditionPicker(false);
          };
          const addAction = (type) => {
            setEditingTrigger(prev => ({...prev, actions: [...(prev.actions||[]), {id: Date.now(), type, reply_text:'', media_type:'none', reply_target:'none', bot_msg_delete:'no', bot_msg_delete_after:60, duration:'', emoji:''}]}));
            setShowActionPicker(false);
          };

          const conditions = editingTrigger.conditions || [];
          const actions    = editingTrigger.actions    || [];

          const COND_LABELS = { contains:'Содержит', exact:'Точное', starts_with:'Начало', ends_with:'Конец', whole_word:'Целое слово' };
          const ACTION_TYPES = [
            { type:'send_text', label:'Ответить в чат',    Icon: MessageCircle },
            { type:'dm',        label:'Ответить в ЛС',     Icon: Send          },
            { type:'mute',      label:'Мут',               Icon: Clock         },
            { type:'ban',       label:'Бан',               Icon: ShieldBan     },
            { type:'warn',      label:'Предупреждение',    Icon: AlertOctagon  },
            { type:'delete',    label:'Удалить сообщение', Icon: Trash2        },
            { type:'emoji',     label:'Реакция',           Icon: Smile         },
          ];

          return (
            <div className="pb-24 animate-in fade-in duration-300">

              {/* ── Шапка редактора ── */}
              <div className="bg-white rounded-[2rem] border border-gray-100 shadow-sm p-5 mb-5 space-y-4">

                {/* Кнопки действий */}
                <div className="flex items-center gap-2">
                  <button onClick={() => setEditingTrigger(null)}
                    className="p-2 text-gray-400 hover:text-gray-600 active:scale-90 transition-all mr-auto">
                    <X size={20}/>
                  </button>
                  <button onClick={saveTrigger}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-green-500 text-white rounded-xl font-black text-sm shadow-md shadow-green-100 active:scale-95 transition-all">
                    <CheckCircle2 size={15}/> Сохранить
                  </button>
                  <div className="relative">
                    <button onClick={() => setShowTriggerEditMenu(v=>!v)}
                      className="px-3 py-2.5 bg-gray-100 text-gray-500 rounded-xl font-black text-sm active:scale-95 transition-all hover:bg-gray-200">
                      ···
                    </button>
                    {showTriggerEditMenu && (
                      <div className="absolute right-0 top-full mt-1.5 w-56 bg-white border border-gray-100 rounded-2xl shadow-xl z-10 overflow-hidden"
                        onClick={() => setShowTriggerEditMenu(false)}>
                        <button className="w-full flex items-center gap-3 px-4 py-3.5 text-sm font-bold text-gray-300 cursor-not-allowed border-b border-gray-50">
                          <FileText size={14} className="text-gray-200"/>
                          <span>Сохранить и продолжить</span>
                          <span className="ml-auto text-[9px] bg-gray-100 text-gray-300 px-1.5 py-0.5 rounded font-black">***</span>
                        </button>
                        <button className="w-full flex items-center gap-3 px-4 py-3.5 text-sm font-bold text-gray-300 cursor-not-allowed">
                          <Download size={14} className="text-gray-200"/>
                          <span>Экспортировать триггер</span>
                          <span className="ml-auto text-[9px] bg-gray-100 text-gray-300 px-1.5 py-0.5 rounded font-black">***</span>
                        </button>
                      </div>
                    )}
                  </div>
                  {editingTrigger.id && (
                    <button onClick={() => { deleteTrigger(editingTrigger.id); setEditingTrigger(null); }}
                      className="flex items-center gap-1.5 px-4 py-2.5 bg-red-500 text-white rounded-xl font-black text-sm shadow-md shadow-red-100 active:scale-95 transition-all">
                      <Trash2 size={15}/> Удалить
                    </button>
                  )}
                </div>

                {/* Имя триггера */}
                <div>
                  <p className="text-xs font-black text-gray-800 mb-0.5">
                    Имя триггера <span className="text-red-500">*</span>
                  </p>
                  <p className="text-[10px] text-gray-400 font-medium mb-2">
                    Позволяет быстро найти нужный триггер и включить его
                  </p>
                  <input type="text" placeholder="Например: Мут за спам"
                    value={editingTrigger.name} onChange={e => upd('name', e.target.value)}
                    className="w-full px-4 py-3.5 bg-gray-50 border-2 border-gray-100 rounded-2xl font-black text-base outline-none focus:border-blue-200 transition-all"/>
                </div>
              </div>

              {/* ── Вероятность ── */}
              <div className="bg-amber-50 p-4 rounded-2xl border border-amber-100 mb-5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-black text-amber-700 uppercase tracking-widest flex items-center gap-1">
                    <Percent size={11}/> Шанс срабатывания
                  </span>
                  <span className="text-xl font-black text-amber-800">{editingTrigger.probability}%</span>
                </div>
                <input type="range" min="1" max="100" value={editingTrigger.probability}
                  onChange={e => upd('probability', parseInt(e.target.value))}
                  className="w-full h-2 bg-amber-200 rounded-full appearance-none cursor-pointer accent-amber-600"/>
              </div>

              {/* ── УСЛОВИЯ ── */}
              <div className="mb-5 space-y-2">
                <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block px-1">Условия</span>
                {conditions.map((cond, idx) => (
                  <div key={cond.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
                      <span className={`text-[10px] font-black px-2.5 py-1 rounded-full uppercase ${cond.signal==='message' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                        {cond.signal==='message' ? '📨 Сообщение' : '↩️ Цитируемое'}
                      </span>
                      <button onClick={() => removeCond(idx)} className="p-1.5 text-red-400 hover:text-red-600 active:scale-90 transition-all"><X size={13}/></button>
                    </div>
                    <div className="px-4 py-3 space-y-3">
                      <div className="flex gap-1.5 flex-wrap">
                        {Object.entries(COND_LABELS).map(([key, lbl]) => (
                          <button key={key} onClick={() => updCond(idx,'condition',key)}
                            className={`px-3 py-1 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${
                              cond.condition===key ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'
                            }`}>{lbl}
                          </button>
                        ))}
                      </div>
                      <textarea placeholder="Ключевые слова через запятую..."
                        value={cond.keyword} onChange={e => updCond(idx,'keyword',e.target.value)} rows={2}
                        className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl font-mono text-sm font-bold outline-none focus:border-blue-300 resize-none transition-all"/>
                    </div>
                  </div>
                ))}
                <button onClick={() => { setShowConditionPicker(v=>!v); setShowActionPicker(false); }}
                  className="w-full py-3.5 border-2 border-dashed border-gray-200 rounded-2xl text-gray-400 font-black text-[11px] uppercase flex items-center justify-center gap-2 hover:border-blue-300 hover:text-blue-400 transition-all bg-white">
                  <PlusCircle size={14}/> Добавить условие
                </button>
                {showConditionPicker && (
                  <div className="bg-white border-2 border-gray-100 rounded-2xl overflow-hidden shadow-lg">
                    <div className="flex">
                      {[{v:'message',l:'📨 Сообщение'},{v:'quoted',l:'↩️ Цитируемое'}].map(t => (
                        <button key={t.v} onClick={() => setCondSignalTab(t.v)}
                          className={`flex-1 py-3 text-[11px] font-black uppercase transition-all border-b-2 ${condSignalTab===t.v ? 'text-blue-600 border-blue-500' : 'text-gray-400 border-gray-100'}`}>
                          {t.l}
                        </button>
                      ))}
                    </div>
                    <div className="px-4 py-2 bg-blue-50 text-[10px] text-blue-700 font-medium">
                      {condSignalTab==='message' ? 'Триггер сработает на сообщение участника.' : 'Триггер сработает на сообщение, на которое ответили.'}
                    </div>
                    <button onClick={() => addCondition(condSignalTab)}
                      className="w-full flex items-center gap-3 px-4 py-4 hover:bg-gray-50 active:bg-gray-100 transition-all text-left border-t border-gray-50">
                      <span className="w-9 h-9 bg-blue-50 rounded-xl flex items-center justify-center text-base flex-shrink-0">🔤</span>
                      <div>
                        <p className="font-black text-sm text-gray-900">Слово в сообщении</p>
                        <p className="text-[10px] text-gray-400 font-medium">Реагирует на ключевые слова</p>
                      </div>
                    </button>
                  </div>
                )}
              </div>

              {/* ── ДЕЙСТВИЯ ── */}
              <div className="mb-5 space-y-2">
                <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block px-1">Действия</span>
                {actions.map((action, idx) => {
                  const actCfg = ACTION_TYPES.find(a=>a.type===action.type)||ACTION_TYPES[0];
                  const ActIcon = actCfg.Icon;
                  return (
                    <div key={action.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
                        <div className="flex items-center gap-2"><ActIcon size={14} className="text-gray-600"/><span className="text-sm font-black text-gray-800">{actCfg.label}</span></div>
                        <button onClick={() => removeAction(idx)} className="p-1.5 text-red-400 hover:text-red-600 active:scale-90 transition-all"><X size={13}/></button>
                      </div>
                      <div className="px-4 py-3 space-y-3">
                        {(action.type==='send_text'||action.type==='dm') && (<>
                          {action.type==='send_text' && (
                            <div className="flex gap-1.5 flex-wrap">
                              {[{v:'none',l:'Обычный'},{v:'initiator',l:'→ Автор'},{v:'quoted',l:'→ Цитата'}].map(o => (
                                <button key={o.v} onClick={() => updAction(idx,'reply_target',o.v)}
                                  className={`px-3 py-1 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${action.reply_target===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                                </button>
                              ))}
                            </div>
                          )}
                          <textarea placeholder="Текст сообщения..."
                            value={action.reply_text} onChange={e => updAction(idx,'reply_text',e.target.value)} rows={3}
                            className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 resize-none transition-all"/>
                          {action.type==='send_text' && (<>
                            <div>
                              <div className="flex items-center justify-between mb-1.5">
                                <span className="text-[10px] font-black text-gray-400 uppercase">Медиафайл</span>
                                <button onClick={() => { if (showMediaPicker) updAction(idx,'media_type','none'); setShowMediaPicker(v=>!v); }}
                                  className={`flex items-center gap-1 px-3 py-1 rounded-xl text-[10px] font-black uppercase transition-all ${action.media_type!=='none' ? 'bg-blue-600 text-white' : showMediaPicker ? 'bg-gray-200 text-gray-600' : 'bg-gray-100 text-gray-500'}`}>
                                  {action.media_type==='none' ? <><ImageIcon size={11}/><span>{showMediaPicker?'Убрать':'+ Добавить'}</span></> :
                                   action.media_type==='photo' ? <><ImageIcon size={11}/><span>Фото</span><X size={9} className="ml-1 opacity-60"/></> :
                                   action.media_type==='video' ? <><Video size={11}/><span>Видео</span><X size={9} className="ml-1 opacity-60"/></> :
                                   <><Smile size={11}/><span>GIF</span><X size={9} className="ml-1 opacity-60"/></>}
                                </button>
                              </div>
                              <div className={`overflow-hidden transition-all duration-300 ${showMediaPicker ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0'}`}>
                                <div className="grid grid-cols-3 gap-2 pb-1">
                                  {[{v:'photo',l:'Фото',I:ImageIcon},{v:'video',l:'Видео',I:Video},{v:'animation',l:'GIF',I:Smile}].map(m => (
                                    <button key={m.v} onClick={() => { updAction(idx,'media_type',m.v); setShowMediaPicker(false); }}
                                      className={`flex flex-col items-center gap-1 py-2.5 rounded-xl border-2 text-[10px] font-black uppercase transition-all ${action.media_type===m.v ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-gray-200 text-gray-500'}`}>
                                      <m.I size={16}/>{m.l}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                            <div>
                              <span className="text-[10px] font-black text-gray-400 uppercase block mb-1.5">Удаление ответа бота</span>
                              <div className="flex gap-2">
                                {[{v:'no',l:'Нет'},{v:'previous',l:'Пред.'},{v:'period',l:'Таймер'}].map(o => (
                                  <button key={o.v} onClick={() => updAction(idx,'bot_msg_delete',o.v)}
                                    className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${action.bot_msg_delete===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                                  </button>
                                ))}
                              </div>
                              {action.bot_msg_delete==='period' && (
                                <input type="number" placeholder="Секунд" value={action.bot_msg_delete_after}
                                  onChange={e => updAction(idx,'bot_msg_delete_after',parseInt(e.target.value))}
                                  className="w-full mt-2 p-3 bg-white border border-gray-200 rounded-xl font-black text-center outline-none focus:border-blue-300"/>
                              )}
                            </div>
                          </>)}
                        </>)}
                        {(action.type==='mute'||action.type==='ban') && (
                          <input type="text" placeholder="Длительность: 30m / 2h / forever"
                            value={action.duration} onChange={e => updAction(idx,'duration',e.target.value)}
                            className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl font-black text-sm outline-none focus:border-blue-300"/>
                        )}
                        {action.type==='emoji' && (
                          <input type="text" placeholder="👀 🔥 ❤️"
                            value={action.emoji} onChange={e => updAction(idx,'emoji',e.target.value)}
                            className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl font-black text-2xl text-center outline-none focus:border-blue-300"/>
                        )}
                      </div>
                    </div>
                  );
                })}
                <button onClick={() => { setShowActionPicker(v=>!v); setShowConditionPicker(false); }}
                  className="w-full py-3.5 border-2 border-dashed border-gray-200 rounded-2xl text-gray-400 font-black text-[11px] uppercase flex items-center justify-center gap-2 hover:border-blue-300 hover:text-blue-400 transition-all bg-white">
                  <PlusCircle size={14}/> Добавить действие
                </button>
                {showActionPicker && (
                  <div className="bg-white border-2 border-gray-100 rounded-2xl overflow-hidden shadow-lg">
                    {ACTION_TYPES.map(at => {
                      const AtIcon = at.Icon;
                      return (
                        <button key={at.type} onClick={() => addAction(at.type)}
                          className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-gray-50 active:bg-gray-100 border-b border-gray-50 last:border-0 transition-all text-left">
                          <AtIcon size={16} className="text-gray-500 flex-shrink-0"/>
                          <span className="font-black text-sm text-gray-800">{at.label}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* ── Дополнительно ── */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 space-y-4">
                <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Дополнительно</span>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">Где срабатывает</p>
                  <div className="flex gap-2">
                    {[{v:'chat',l:'Чат'},{v:'pv',l:'Личка'},{v:'global',l:'Везде'}].map(o => (
                      <button key={o.v} onClick={() => upd('where',o.v)}
                        className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${editingTrigger.where===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">На кого реагирует</p>
                  <div className="flex gap-2">
                    {[{v:'all',l:'Все'},{v:'users',l:'Юзеры'},{v:'admins',l:'Админы'}].map(o => (
                      <button key={o.v} onClick={() => upd('from',o.v)}
                        className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${editingTrigger.from===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

            </div>
          );
        }

        // ── Список триггеров ──
        const tSearch = triggerSearch.toLowerCase();
        const activeTriggers   = triggers.filter(t =>  t.is_enabled && (!tSearch || t.name.toLowerCase().includes(tSearch) || (t.keyword||'').toLowerCase().includes(tSearch)));
        const inactiveTriggers = triggers.filter(t => !t.is_enabled && (!tSearch || t.name.toLowerCase().includes(tSearch) || (t.keyword||'').toLowerCase().includes(tSearch)));

        const TriggerRow = ({ t, index, active }) => (
          <div
            key={t.id}
            draggable={active}
            onDragStart={() => active && handleDragStart(t.id)}
            onDragOver={e => { e.preventDefault(); }}
            onDrop={() => active && handleDrop(t.id)}
            className={`flex items-center py-3 px-4 border-b border-gray-50 last:border-b-0 transition-opacity ${dragId === t.id ? 'opacity-40' : 'opacity-100'}`}
          >
            {/* drag handle (только активные) */}
            {active ? (
              <GripVertical size={16} className="text-gray-300 mr-2 flex-shrink-0 cursor-grab active:cursor-grabbing"/>
            ) : (
              <div className="w-[20px] mr-2 flex-shrink-0"/>
            )}

            {/* номер (только активные) */}
            {active && (
              <span className="w-7 h-7 rounded-full bg-blue-500 text-white text-[10px] font-black flex items-center justify-center mr-3 flex-shrink-0">
                {index + 1}
              </span>
            )}

            {/* название */}
            <button
              onClick={() => openTriggerModal(t)}
              className="flex-1 text-left text-sm font-bold text-blue-600 hover:text-blue-800 truncate"
            >
              {t.name}
            </button>

            {/* кнопки */}
            <div className="flex items-center gap-1 ml-2 flex-shrink-0">
              {/* удалить — только неактивные */}
              {!active && (
                <button
                  onClick={() => deleteTrigger(t.id)}
                  className="p-2 text-red-400 hover:text-red-600 active:scale-90 transition-all"
                >
                  <Trash2 size={16}/>
                </button>
              )}
              {/* копировать */}
              <button
                onClick={() => copyTrigger(t.id)}
                disabled={copyingTrigger === t.id}
                className="p-2 text-blue-400 hover:text-blue-600 active:scale-90 transition-all disabled:opacity-40"
              >
                {copyingTrigger === t.id ? <Loader2 size={16} className="animate-spin"/> : <Copy size={16}/>}
              </button>
              {/* пауза (активные) / старт (неактивные) */}
              <button
                onClick={() => toggleTrigger(t.id)}
                disabled={togglingTrigger === t.id}
                className={`p-0.5 rounded-full active:scale-90 transition-all disabled:opacity-40 ${
                  active ? 'text-red-500 hover:text-red-700' : 'text-green-500 hover:text-green-700'
                }`}
              >
                {togglingTrigger === t.id
                  ? <Loader2 size={22} className="animate-spin"/>
                  : active
                    ? <span className="w-6 h-6 rounded-full border-2 border-red-500 flex items-center justify-center"><Square size={8} fill="currentColor"/></span>
                    : <span className="w-6 h-6 rounded-full border-2 border-green-500 flex items-center justify-center"><Play size={9} fill="currentColor"/></span>
                }
              </button>
            </div>
          </div>
        );

        return (
          <div className="space-y-4 pb-24">
            {/* ── Поиск ── */}
            <div className="relative">
              <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-300"/>
              <input
                value={triggerSearch}
                onChange={e => setTriggerSearch(e.target.value)}
                placeholder="Поиск по названию или ключевым словам..."
                className="w-full bg-white border border-gray-100 rounded-2xl pl-10 pr-4 py-3.5 text-sm font-bold focus:outline-none focus:border-blue-300 shadow-sm"
              />
            </div>

            {/* ── Панель действий ── */}
            <div className="flex items-center space-x-2">
              <button className="flex items-center space-x-2 px-5 py-3 bg-white border border-gray-100 rounded-2xl font-black text-xs text-gray-500 shadow-sm active:scale-95 transition-all">
                <Activity size={14}/><span>Статистика</span>
              </button>
              <button
                onClick={() => openTriggerModal()}
                className="flex-1 flex items-center justify-center space-x-2 py-3 bg-blue-600 text-white rounded-2xl font-black text-xs shadow-md shadow-blue-100 active:scale-95 transition-all"
              >
                <PlusCircle size={14}/><span>Создать триггер</span>
              </button>
              {/* меню ··· */}
              <div className="relative">
                <button
                  onClick={() => setShowTriggerMenu(v => !v)}
                  className="p-3 bg-white border border-gray-100 rounded-2xl text-gray-400 shadow-sm active:scale-95 transition-all font-black text-lg leading-none"
                >···</button>
                {showTriggerMenu && (
                  <div className="absolute right-0 top-full mt-2 w-56 bg-white border border-gray-100 rounded-2xl shadow-xl z-50 overflow-hidden" onClick={() => setShowTriggerMenu(false)}>
                    <button className="w-full text-left px-5 py-3.5 text-sm font-bold text-gray-700 hover:bg-gray-50 flex items-center gap-3">
                      <Download size={14} className="text-gray-400"/> Импортировать триггеры
                    </button>
                    <button className="w-full text-left px-5 py-3.5 text-sm font-bold text-gray-700 hover:bg-gray-50 flex items-center gap-3">
                      <Clock size={14} className="text-gray-400"/> Восстановить удалённый
                    </button>
                    <button
                      onClick={() => { triggers.forEach(t => t.is_enabled && toggleTrigger(t.id)); }}
                      className="w-full text-left px-5 py-3.5 text-sm font-bold text-gray-700 hover:bg-gray-50 flex items-center gap-3"
                    >
                      <Power size={14} className="text-gray-400"/> Отключить все триггеры
                    </button>
                  </div>
                )}
              </div>
            </div>

            {triggersLoading && (
              <div className="text-center py-8 text-gray-400 font-black text-sm">
                <Loader2 size={24} className="animate-spin mx-auto mb-2"/> Загрузка...
              </div>
            )}

            {/* ── Активные ── */}
            {!triggersLoading && activeTriggers.length > 0 && (
              <div>
                <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Активные триггеры</p>
                <div className="bg-white rounded-[2rem] border-l-4 border-l-green-500 border border-gray-100 shadow-sm overflow-hidden">
                  {activeTriggers.map((t, i) => <TriggerRow key={t.id} t={t} index={i} active={true}/>)}
                </div>
              </div>
            )}

            {/* ── Неактивные ── */}
            {!triggersLoading && inactiveTriggers.length > 0 && (
              <div>
                <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Не активные триггеры</p>
                <div className="bg-white rounded-[2rem] border-l-4 border-l-red-400 border border-gray-100 shadow-sm overflow-hidden">
                  {inactiveTriggers.map((t, i) => <TriggerRow key={t.id} t={t} index={i} active={false}/>)}
                </div>
              </div>
            )}

            {!triggersLoading && triggers.length === 0 && (
              <div className="text-center py-12 text-gray-300 font-black text-sm uppercase tracking-widest">
                Триггеров пока нет
              </div>
            )}
          </div>
        );
      }

      case 'updates':
        return (
          <div className="space-y-4 pb-24 animate-in fade-in duration-300">
            <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm flex items-center space-x-4">
              <div className="w-14 h-14 bg-blue-600 rounded-[1.5rem] flex items-center justify-center shadow-lg">
                <Megaphone size={26} className="text-white" />
              </div>
              <div>
                <h2 className="font-black text-2xl text-gray-900 leading-none">Обновления</h2>
                <p className="text-xs text-gray-400 font-bold mt-1">История улучшений панели и бота</p>
              </div>
            </div>

            {UPDATES.map((upd) => (
              <div key={upd.version} className="bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <span className="bg-blue-600 text-white text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full">{upd.version}</span>
                  <span className="text-xs text-gray-300 font-mono">{upd.date}</span>
                </div>
                <h3 className="font-black text-lg text-gray-900">{upd.title}</h3>
                <div className="space-y-2">
                  {upd.items.map((item, i) => {
                    const typeCfg = {
                      new:     { icon: PartyPopper, bg: 'bg-green-50',  text: 'text-green-600',  border: 'border-green-100',  label: 'НОВОЕ'      },
                      improve: { icon: Sparkles,    bg: 'bg-blue-50',   text: 'text-blue-600',   border: 'border-blue-100',   label: 'УЛУЧШЕНО'   },
                      fix:     { icon: Wrench,      bg: 'bg-orange-50', text: 'text-orange-600', border: 'border-orange-100', label: 'ИСПРАВЛЕНО' },
                    }[item.type] || { icon: Info, bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-100', label: '' };
                    const tagCfg = {
                      site:       { emoji: '🌐', label: 'Сайт',       color: 'bg-indigo-50 text-indigo-500' },
                      statistics: { emoji: '📊', label: 'Статистика', color: 'bg-violet-50 text-violet-500' },
                      journal:    { emoji: '📋', label: 'Журнал',     color: 'bg-sky-50 text-sky-500'       },
                      triggers:   { emoji: '⚡', label: 'Триггеры',   color: 'bg-yellow-50 text-yellow-600' },
                      bot:        { emoji: '🤖', label: 'Бот',        color: 'bg-gray-100 text-gray-500'    },
                    }[item.tag] || null;
                    const Icon = typeCfg.icon;
                    return (
                      <div key={i} className={`flex items-start space-x-3 p-3 rounded-2xl border ${typeCfg.bg} ${typeCfg.border}`}>
                        <div className={`flex-shrink-0 flex items-center space-x-1 ${typeCfg.text}`}>
                          <Icon size={14} />
                          <span className="text-[9px] font-black uppercase tracking-widest">{typeCfg.label}</span>
                        </div>
                        <p className="text-xs text-gray-700 font-medium leading-relaxed flex-1">{item.text}</p>
                        {tagCfg && (() => {
                          const key = `${upd.version}-${i}`;
                          return (
                            <span
                              onClick={() => triggerJiggle(key)}
                              onAnimationEnd={() => setJigglingTag(null)}
                              className={`flex-shrink-0 text-[9px] font-black px-2 py-1 rounded-full cursor-pointer select-none hover:scale-110 transition-transform ${tagCfg.color} ${jigglingTag === key ? 'tag-jiggle' : ''}`}
                            >
                              {tagCfg.emoji} {tagCfg.label}
                            </span>
                          );
                        })()}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        );

      default: return null;
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex font-sans text-gray-900 selection:bg-blue-100 overflow-hidden">
      <aside className={`fixed inset-y-0 left-0 z-50 w-[260px] bg-white border-r border-gray-100 flex flex-col transform transition-transform duration-500 lg:translate-x-0 lg:static ${isSidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'}`}>
        <div className="h-16 flex items-center justify-between px-5 border-b border-gray-100">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg">
              <Bot size={18} className="text-white" />
            </div>
            <div>
              <span className="block font-black text-base text-gray-900 leading-none">Pulse Admin</span>
              <span className="text-[9px] font-bold text-blue-500 uppercase tracking-wider mt-0.5 block">Owner Console</span>
            </div>
          </div>
          <button onClick={() => setIsSidebarOpen(false)} className="lg:hidden p-3 bg-white rounded-2xl text-gray-400 border border-gray-50 active:scale-90 transition-all"><X size={24} /></button>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-4 space-y-6">
          {['top', 'main', 'modules', 'features'].map(group => (
            <div key={group} className="space-y-2">
              {group !== 'top' && (
                <p className="px-5 text-[11px] font-black text-gray-300 uppercase tracking-[0.3em] mb-6">
                  {group === 'main' ? 'Мониторинг' : group === 'modules' ? 'Модули' : 'Сервис'}
                </p>
              )}
              {navigation.filter(n => n.group === group).map((item) => (
                <button
                  key={item.id}
                  onClick={() => { navigateTo(item.id); setIsSidebarOpen(false); setJigglingNav(item.id); }}
                  className={`w-full flex items-center px-4 py-2.5 rounded-xl transition-all duration-200 ${
                    activeTab === item.id
                    ? 'bg-gray-900 text-white shadow-md font-black'
                    : 'text-gray-500 hover:bg-gray-50 active:bg-gray-100'
                  }`}
                >
                  <item.icon
                    size={18}
                    onAnimationEnd={() => setJigglingNav(null)}
                    className={`mr-3 ${activeTab === item.id ? 'text-blue-400' : 'text-gray-400'} ${jigglingNav === item.id ? 'tag-jiggle' : ''}`}
                  />
                  <span className="text-sm flex-1">{item.name}</span>
                  {item.id === 'updates' && hasNewUpdate && (
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse shadow-md shadow-red-300" />
                  )}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <main className="flex-1 flex flex-col h-screen overflow-hidden bg-[#F8FAFC]">
        <header className="h-16 lg:h-16 bg-white border-b border-gray-100 flex items-center justify-between px-4 sm:px-6 z-10 shrink-0">
          <div className="flex items-center">
            <button className="lg:hidden p-4 bg-gray-50 rounded-[1.5rem] mr-5 border border-gray-100 shadow-sm" onClick={() => setIsSidebarOpen(true)}>
              <Menu size={26} />
            </button>
            <h1 className="text-2xl sm:text-3xl font-black text-gray-900 tracking-tighter">
              {navigation.find(n => n.id === activeTab)?.name}
            </h1>
          </div>
          <div className="flex items-center space-x-3">
            <div className="w-14 h-14 rounded-[1.5rem] bg-gradient-to-tr from-blue-600 to-indigo-700 flex items-center justify-center text-white font-black text-2xl border-4 border-white shadow-xl">В</div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-gray-50/10 custom-scrollbar">
          <div className="max-w-3xl mx-auto">{renderContent()}</div>
        </div>
      </main>

      {/* старый modal удалён — редактор теперь внутри case 'triggers' */}
      {false && (() => {
        const upd = (field, val) => setEditingTrigger(prev => ({...prev, [field]: val}));
        const updCond = (idx, field, val) => setEditingTrigger(prev => {
          const arr = [...(prev.conditions||[])]; arr[idx] = {...arr[idx], [field]: val}; return {...prev, conditions: arr};
        });
        const updAction = (idx, field, val) => setEditingTrigger(prev => {
          const arr = [...(prev.actions||[])]; arr[idx] = {...arr[idx], [field]: val}; return {...prev, actions: arr};
        });
        const removeCond   = (idx) => setEditingTrigger(prev => ({...prev, conditions: (prev.conditions||[]).filter((_,i)=>i!==idx)}));
        const removeAction = (idx) => setEditingTrigger(prev => ({...prev, actions:    (prev.actions||[]).filter((_,i)=>i!==idx)}));
        const addCondition = (signal) => {
          setEditingTrigger(prev => ({...prev, conditions: [...(prev.conditions||[]), {id: Date.now(), signal, type:'keyword', condition:'contains', keyword:''}]}));
          setShowConditionPicker(false);
        };
        const addAction = (type) => {
          setEditingTrigger(prev => ({...prev, actions: [...(prev.actions||[]), {id: Date.now(), type, reply_text:'', media_type:'none', reply_target:'none', bot_msg_delete:'no', bot_msg_delete_after:60, duration:'', emoji:''}]}));
          setShowActionPicker(false);
        };

        const conditions = editingTrigger.conditions || [];
        const actions    = editingTrigger.actions    || [];

        const COND_LABELS = { contains:'Содержит', exact:'Точное', starts_with:'Начало', ends_with:'Конец', whole_word:'Целое слово' };
        const ACTION_TYPES = [
          { type:'send_text', label:'Ответить в чат',   Icon: MessageCircle },
          { type:'dm',        label:'Ответить в ЛС',    Icon: Send          },
          { type:'mute',      label:'Мут',              Icon: Clock         },
          { type:'ban',       label:'Бан',              Icon: ShieldBan     },
          { type:'warn',      label:'Предупреждение',   Icon: AlertOctagon  },
          { type:'delete',    label:'Удалить сообщение',Icon: Trash2        },
          { type:'emoji',     label:'Реакция',          Icon: Smile         },
        ];

        return (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-[100] flex items-end sm:items-center justify-center"
            onClick={e => e.target === e.currentTarget && setIsTriggerModalOpen(false)}>
            <div className="bg-white w-full sm:max-w-lg rounded-t-[3.5rem] sm:rounded-[3rem] flex flex-col max-h-[92vh] shadow-2xl animate-in slide-in-from-bottom-full duration-500">

              {/* drag handle */}
              <div className="w-16 h-1.5 bg-gray-200 rounded-full mx-auto mt-4 mb-3 shrink-0"/>

              {/* Шапка: имя + кнопки */}
              <div className="px-6 pb-4 shrink-0 border-b border-gray-50 space-y-3">

                {/* Строка кнопок */}
                <div className="flex items-center justify-between gap-2">
                  <button onClick={() => setIsTriggerModalOpen(false)}
                    className="p-2 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                    <X size={20}/>
                  </button>
                  <div className="flex items-center gap-2 ml-auto">
                    {/* Сохранить */}
                    <button onClick={saveTrigger}
                      className="flex items-center gap-1.5 px-4 py-2.5 bg-green-500 text-white rounded-xl font-black text-sm shadow-md shadow-green-100 active:scale-95 transition-all">
                      <CheckCircle2 size={15}/>
                      <span>Сохранить</span>
                    </button>
                    {/* ··· */}
                    <div className="relative">
                      <button
                        onClick={() => setShowTriggerEditMenu(v => !v)}
                        className="px-3 py-2.5 bg-gray-100 text-gray-500 rounded-xl font-black text-sm active:scale-95 transition-all hover:bg-gray-200">
                        ···
                      </button>
                      {showTriggerEditMenu && (
                        <div className="absolute right-0 top-full mt-1.5 w-56 bg-white border border-gray-100 rounded-2xl shadow-xl z-10 overflow-hidden"
                          onClick={() => setShowTriggerEditMenu(false)}>
                          <button className="w-full flex items-center gap-3 px-4 py-3.5 text-sm font-bold text-gray-300 cursor-not-allowed select-none border-b border-gray-50">
                            <FileText size={14} className="text-gray-200"/>
                            <span>Сохранить и продолжить</span>
                            <span className="ml-auto text-[9px] bg-gray-100 text-gray-300 px-1.5 py-0.5 rounded font-black">***</span>
                          </button>
                          <button className="w-full flex items-center gap-3 px-4 py-3.5 text-sm font-bold text-gray-300 cursor-not-allowed select-none">
                            <Download size={14} className="text-gray-200"/>
                            <span>Экспортировать триггер</span>
                            <span className="ml-auto text-[9px] bg-gray-100 text-gray-300 px-1.5 py-0.5 rounded font-black">***</span>
                          </button>
                        </div>
                      )}
                    </div>
                    {/* Удалить (только для существующего) */}
                    {editingTrigger.id && (
                      <button onClick={() => { deleteTrigger(editingTrigger.id); setIsTriggerModalOpen(false); }}
                        className="flex items-center gap-1.5 px-4 py-2.5 bg-red-500 text-white rounded-xl font-black text-sm shadow-md shadow-red-100 active:scale-95 transition-all">
                        <Trash2 size={15}/>
                        <span>Удалить</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Имя триггера */}
                <div>
                  <p className="text-xs font-black text-gray-800 mb-0.5">
                    Имя триггера <span className="text-red-500">*</span>
                  </p>
                  <p className="text-[10px] text-gray-400 font-medium mb-2">
                    Позволяет быстро найти нужный триггер и включить его
                  </p>
                  <input type="text" placeholder="Например: Мут за спам"
                    value={editingTrigger.name} onChange={e => upd('name', e.target.value)}
                    className="w-full px-4 py-3.5 bg-gray-50 border-2 border-gray-100 rounded-2xl font-black text-base outline-none focus:border-blue-200 transition-all"/>
                </div>
              </div>

              {/* Body */}
              <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">

                {/* Вероятность */}
                <div className="bg-amber-50 p-4 rounded-2xl border border-amber-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-black text-amber-700 uppercase tracking-widest flex items-center gap-1">
                      <Percent size={11}/> Шанс срабатывания
                    </span>
                    <span className="text-xl font-black text-amber-800">{editingTrigger.probability}%</span>
                  </div>
                  <input type="range" min="1" max="100" value={editingTrigger.probability}
                    onChange={e => upd('probability', parseInt(e.target.value))}
                    className="w-full h-2 bg-amber-200 rounded-full appearance-none cursor-pointer accent-amber-600"/>
                </div>

                {/* ── УСЛОВИЯ ── */}
                <div className="space-y-2">
                  <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block">Условия</span>

                  {conditions.map((cond, idx) => (
                    <div key={cond.id} className="bg-gray-50 rounded-2xl border border-gray-100 overflow-hidden">
                      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
                        <span className={`text-[10px] font-black px-2.5 py-1 rounded-full uppercase ${cond.signal === 'message' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                          {cond.signal === 'message' ? '📨 Сообщение' : '↩️ Цитируемое'}
                        </span>
                        <button onClick={() => removeCond(idx)} className="p-1.5 text-red-400 hover:text-red-600 active:scale-90 transition-all"><X size={13}/></button>
                      </div>
                      <div className="px-4 py-3 space-y-3">
                        <div className="flex gap-1.5 flex-wrap">
                          {Object.entries(COND_LABELS).map(([key, lbl]) => (
                            <button key={key} onClick={() => updCond(idx, 'condition', key)}
                              className={`px-3 py-1 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${
                                cond.condition === key ? 'bg-gray-900 text-white' : 'bg-white border border-gray-200 text-gray-500 hover:border-gray-300'
                              }`}>{lbl}
                            </button>
                          ))}
                        </div>
                        <textarea placeholder="Ключевые слова через запятую..."
                          value={cond.keyword} onChange={e => updCond(idx, 'keyword', e.target.value)} rows={2}
                          className="w-full p-3 bg-white border border-gray-200 rounded-xl font-mono text-sm font-bold outline-none focus:border-blue-300 resize-none transition-all"/>
                      </div>
                    </div>
                  ))}

                  <button
                    onClick={() => { setShowConditionPicker(v=>!v); setShowActionPicker(false); }}
                    className="w-full py-3 border-2 border-dashed border-gray-200 rounded-2xl text-gray-400 font-black text-[11px] uppercase flex items-center justify-center gap-2 hover:border-blue-300 hover:text-blue-400 transition-all active:scale-[.98]">
                    <PlusCircle size={14}/> Добавить условие
                  </button>

                  {showConditionPicker && (
                    <div className="bg-white border-2 border-gray-100 rounded-2xl overflow-hidden shadow-lg animate-in slide-in-from-top-2 duration-200">
                      <div className="flex">
                        {[{v:'message',l:'📨 Сообщение'},{v:'quoted',l:'↩️ Цитируемое'}].map(t => (
                          <button key={t.v} onClick={() => setCondSignalTab(t.v)}
                            className={`flex-1 py-3 text-[11px] font-black uppercase transition-all border-b-2 ${condSignalTab===t.v ? 'text-blue-600 border-blue-500' : 'text-gray-400 border-gray-100'}`}>
                            {t.l}
                          </button>
                        ))}
                      </div>
                      <div className="px-4 py-2 bg-blue-50 text-[10px] text-blue-700 font-medium leading-relaxed">
                        {condSignalTab === 'message'
                          ? 'Триггер сработает на сообщение, которое отправил участник.'
                          : 'Триггер сработает на сообщение, на которое ответили.'}
                      </div>
                      <button onClick={() => addCondition(condSignalTab)}
                        className="w-full flex items-center gap-3 px-4 py-4 hover:bg-gray-50 active:bg-gray-100 transition-all text-left border-t border-gray-50">
                        <span className="w-9 h-9 bg-blue-50 rounded-xl flex items-center justify-center text-base flex-shrink-0">🔤</span>
                        <div>
                          <p className="font-black text-sm text-gray-900">Слово в сообщении</p>
                          <p className="text-[10px] text-gray-400 font-medium">Реагирует на ключевые слова</p>
                        </div>
                      </button>
                    </div>
                  )}
                </div>

                {/* ── ДЕЙСТВИЯ ── */}
                <div className="space-y-2">
                  <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block">Действия</span>

                  {actions.map((action, idx) => {
                    const actCfg = ACTION_TYPES.find(a=>a.type===action.type) || ACTION_TYPES[0];
                    const ActIcon = actCfg.Icon;
                    return (
                      <div key={action.id} className="bg-gray-50 rounded-2xl border border-gray-100 overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
                          <div className="flex items-center gap-2">
                            <ActIcon size={14} className="text-gray-600"/>
                            <span className="text-sm font-black text-gray-800">{actCfg.label}</span>
                          </div>
                          <button onClick={() => removeAction(idx)} className="p-1.5 text-red-400 hover:text-red-600 active:scale-90 transition-all"><X size={13}/></button>
                        </div>
                        <div className="px-4 py-3 space-y-3">
                          {(action.type === 'send_text' || action.type === 'dm') && (
                            <>
                              {action.type === 'send_text' && (
                                <div className="flex gap-1.5 flex-wrap">
                                  {[{v:'none',l:'Обычный'},{v:'initiator',l:'→ Автор'},{v:'quoted',l:'→ Цитата'}].map(o => (
                                    <button key={o.v} onClick={() => updAction(idx,'reply_target',o.v)}
                                      className={`px-3 py-1 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${
                                        action.reply_target===o.v ? 'bg-gray-900 text-white' : 'bg-white border border-gray-200 text-gray-500'
                                      }`}>{o.l}
                                    </button>
                                  ))}
                                </div>
                              )}
                              <textarea placeholder="Текст сообщения..."
                                value={action.reply_text} onChange={e => updAction(idx,'reply_text',e.target.value)} rows={3}
                                className="w-full p-3 bg-white border border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 resize-none transition-all"/>
                              {action.type === 'send_text' && (<>
                                <div>
                                  <div className="flex items-center justify-between mb-1.5">
                                    <span className="text-[10px] font-black text-gray-400 uppercase">Медиафайл</span>
                                    <button
                                      onClick={() => { if (showMediaPicker) updAction(idx,'media_type','none'); setShowMediaPicker(v=>!v); }}
                                      className={`flex items-center gap-1 px-3 py-1 rounded-xl text-[10px] font-black uppercase transition-all ${
                                        action.media_type!=='none' ? 'bg-blue-600 text-white' : showMediaPicker ? 'bg-gray-200 text-gray-600' : 'bg-gray-100 text-gray-500'
                                      }`}>
                                      {action.media_type==='none' ? <><ImageIcon size={11}/><span>{showMediaPicker?'Убрать':'+ Добавить'}</span></> :
                                       action.media_type==='photo' ? <><ImageIcon size={11}/><span>Фото</span><X size={9} className="ml-1 opacity-60"/></> :
                                       action.media_type==='video' ? <><Video size={11}/><span>Видео</span><X size={9} className="ml-1 opacity-60"/></> :
                                       <><Smile size={11}/><span>GIF</span><X size={9} className="ml-1 opacity-60"/></>}
                                    </button>
                                  </div>
                                  <div className={`overflow-hidden transition-all duration-300 ${showMediaPicker ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0'}`}>
                                    <div className="grid grid-cols-3 gap-2 pb-1">
                                      {[{v:'photo',l:'Фото',I:ImageIcon},{v:'video',l:'Видео',I:Video},{v:'animation',l:'GIF',I:Smile}].map(m => (
                                        <button key={m.v} onClick={() => { updAction(idx,'media_type',m.v); setShowMediaPicker(false); }}
                                          className={`flex flex-col items-center gap-1 py-2.5 rounded-xl border-2 text-[10px] font-black uppercase transition-all ${
                                            action.media_type===m.v ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-gray-200 text-gray-500'
                                          }`}><m.I size={16}/>{m.l}
                                        </button>
                                      ))}
                                    </div>
                                  </div>
                                </div>
                                <div>
                                  <span className="text-[10px] font-black text-gray-400 uppercase block mb-1.5">Удаление ответа бота</span>
                                  <div className="flex gap-2">
                                    {[{v:'no',l:'Нет'},{v:'previous',l:'Пред.'},{v:'period',l:'Таймер'}].map(o => (
                                      <button key={o.v} onClick={() => updAction(idx,'bot_msg_delete',o.v)}
                                        className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${
                                          action.bot_msg_delete===o.v ? 'bg-gray-900 text-white' : 'bg-white border border-gray-200 text-gray-500'
                                        }`}>{o.l}
                                      </button>
                                    ))}
                                  </div>
                                  {action.bot_msg_delete==='period' && (
                                    <input type="number" placeholder="Секунд" value={action.bot_msg_delete_after}
                                      onChange={e => updAction(idx,'bot_msg_delete_after',parseInt(e.target.value))}
                                      className="w-full mt-2 p-3 bg-white border border-gray-200 rounded-xl font-black text-center outline-none focus:border-blue-300"/>
                                  )}
                                </div>
                              </>)}
                            </>
                          )}
                          {(action.type==='mute'||action.type==='ban') && (
                            <input type="text" placeholder="Длительность: 30m / 2h / forever"
                              value={action.duration} onChange={e => updAction(idx,'duration',e.target.value)}
                              className="w-full p-3 bg-white border border-gray-200 rounded-xl font-black text-sm outline-none focus:border-blue-300"/>
                          )}
                          {action.type==='emoji' && (
                            <input type="text" placeholder="👀 🔥 ❤️"
                              value={action.emoji} onChange={e => updAction(idx,'emoji',e.target.value)}
                              className="w-full p-3 bg-white border border-gray-200 rounded-xl font-black text-2xl text-center outline-none focus:border-blue-300"/>
                          )}
                        </div>
                      </div>
                    );
                  })}

                  <button
                    onClick={() => { setShowActionPicker(v=>!v); setShowConditionPicker(false); }}
                    className="w-full py-3 border-2 border-dashed border-gray-200 rounded-2xl text-gray-400 font-black text-[11px] uppercase flex items-center justify-center gap-2 hover:border-blue-300 hover:text-blue-400 transition-all active:scale-[.98]">
                    <PlusCircle size={14}/> Добавить действие
                  </button>

                  {showActionPicker && (
                    <div className="bg-white border-2 border-gray-100 rounded-2xl overflow-hidden shadow-lg animate-in slide-in-from-top-2 duration-200">
                      {ACTION_TYPES.map(at => {
                        const AtIcon = at.Icon;
                        return (
                          <button key={at.type} onClick={() => addAction(at.type)}
                            className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-gray-50 active:bg-gray-100 border-b border-gray-50 last:border-0 transition-all text-left">
                            <AtIcon size={16} className="text-gray-500 flex-shrink-0"/>
                            <span className="font-black text-sm text-gray-800">{at.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* ── Дополнительно ── */}
                <div className="bg-gray-50 rounded-2xl border border-gray-100 p-4 space-y-4">
                  <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Дополнительно</span>
                  <div>
                    <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">Где срабатывает</p>
                    <div className="flex gap-2">
                      {[{v:'chat',l:'Чат'},{v:'pv',l:'Личка'},{v:'global',l:'Везде'}].map(o => (
                        <button key={o.v} onClick={() => upd('where',o.v)}
                          className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${
                            editingTrigger.where===o.v ? 'bg-gray-900 text-white' : 'bg-white border border-gray-200 text-gray-500'
                          }`}>{o.l}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">На кого реагирует</p>
                    <div className="flex gap-2">
                      {[{v:'all',l:'Все'},{v:'users',l:'Юзеры'},{v:'admins',l:'Админы'}].map(o => (
                        <button key={o.v} onClick={() => upd('from',o.v)}
                          className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${
                            editingTrigger.from===o.v ? 'bg-gray-900 text-white' : 'bg-white border border-gray-200 text-gray-500'
                          }`}>{o.l}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

              </div>

              {/* Нижний отступ для скролла */}
              <div className="h-6 shrink-0"/>

            </div>
          </div>
        );
      })()}

    </div>
  );
}