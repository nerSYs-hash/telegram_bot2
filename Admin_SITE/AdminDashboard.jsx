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
  GripVertical, Play, Square, Copy, Search, Check, RotateCcw, Ban
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
  const [showCondPickerModal, setShowCondPickerModal] = useState(false);
  const [condPickerGroupIdx, setCondPickerGroupIdx] = useState(0);
  const [condPickerSearch, setCondPickerSearch] = useState('');
  const [condPickerTab, setCondPickerTab] = useState('message');
  const [condTooltip, setCondTooltip] = useState(null);
  const [showActPickerModal, setShowActPickerModal] = useState(false);
  const [actPickerGroupIdx, setActPickerGroupIdx] = useState(0);
  const [actPickerSearch, setActPickerSearch] = useState('');
  const [actGroupSettingsIdx, setActGroupSettingsIdx] = useState(null);
  const [condChipInput, setCondChipInput] = useState('');
  const [condSettingsModal, setCondSettingsModal] = useState(null); // {gIdx, cIdx}
  const [condOpenDropdown, setCondOpenDropdown] = useState(null);   // 'type_g_c' | 'mod_g_c'
  const [actOpenDropdown, setActOpenDropdown] = useState(null);     // 'reply_g_a'
  const [showKeyboardModal, setShowKeyboardModal] = useState(false);
  const [kbModalTarget, setKbModalTarget] = useState(null);         // {gIdx, aIdx}
  const [kbButtonType, setKbButtonType] = useState(null);           // null|'link'|'trigger'|'share'|'reaction'
  const [kbNewButton, setKbNewButton] = useState({});
  const [kbReactionEmoji, setKbReactionEmoji] = useState('🌐');
  const [showTriggerEditMenu, setShowTriggerEditMenu] = useState(false);
  const [triggerSearch, setTriggerSearch] = useState('');
  const [showTriggerMenu, setShowTriggerMenu] = useState(false);
  const [togglingTrigger, setTogglingTrigger] = useState(null);
  const [copyingTrigger, setCopyingTrigger] = useState(null);
  const [dragId, setDragId] = useState(null);
  const [actionSettingsModal, setActionSettingsModal] = useState(null); // {gIdx, aIdx}
  const [actionSettingsPct, setActionSettingsPct] = useState(100);      // temp % в модале

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
      // ── Условия: восстанавливаем из keywords строки ──
      const chips = t.keywords ? t.keywords.split(',').map(s => s.trim()).filter(Boolean) : [];
      const conditions = chips.length > 0
        ? [{ id: 1, signal: 'message', type: 'keyword', condition: t.condition || 'contains', chips, keyword: chips[0] || '' }]
        : [];

      // ── Действия: восстанавливаем из actions[] + action_configs{} ──
      const actionList = (t.actions || []).map((type, i) => ({
        id: i + 1,
        type,
        ...(t.action_configs || {})[type] || {},
      }));

      setEditingTrigger({
        ...t,
        conditionGroups: [{ id: 1, conditions }],
        actionGroups: [{ id: 1, probability: t.probability ?? 100, actions: actionList }],
      });
    } else {
      setEditingTrigger({
        id: null, name: '', probability: 100,
        where_fires: 'all', initiator: 'all',
        conditionGroups: [{ id: 1, conditions: [] }],
        actionGroups: [{ id: 1, probability: 100, actions: [] }]
      });
    }
    setShowCondPickerModal(false);
    setShowActPickerModal(false);
    setShowTriggerEditMenu(false);
    setCondTooltip(null);
    setActGroupSettingsIdx(null);
    setCondSettingsModal(null);
    setCondOpenDropdown(null);
    setCondChipInput('');
    setShowMediaPicker(false);
    navigateTo('triggers');
  };

  const saveTrigger = () => {
    // ── Условия: берём из первой группы ──
    const firstGroup = (editingTrigger.conditionGroups || [])[0] || {};
    const conditions = firstGroup.conditions || [];
    const firstCond  = conditions[0] || {};
    // keywords: объединяем chips всех keyword-условий через запятую
    const keywords = conditions
      .filter(c => c.type === 'keyword')
      .flatMap(c => c.chips && c.chips.length ? c.chips : (c.keyword ? [c.keyword] : []))
      .join(',');
    const condition = firstCond.condition || 'contains';

    // ── Действия: собираем из всех групп ──
    const allActions = (editingTrigger.actionGroups || []).flatMap(g => g.actions || []);
    const actionTypes = allActions.map(a => a.type);
    const actionConfigs = {};
    allActions.forEach(a => {
      if (!a.type) return;
      const {id, type, ...cfg} = a;
      actionConfigs[a.type] = cfg;
    });

    const body = {
      name:                 editingTrigger.name,
      condition,
      keywords,
      probability:          editingTrigger.probability ?? 100,
      where_fires:          editingTrigger.where_fires  || 'all',
      initiator:            editingTrigger.initiator    || 'all',
      target:               editingTrigger.target       || 'nobody',
      target_user:          editingTrigger.target_user  || '',
      actions:              actionTypes,
      action_configs:       actionConfigs,
      bot_msg_delete:       editingTrigger.bot_msg_delete       || 'no',
      bot_msg_delete_after: editingTrigger.bot_msg_delete_after || 60,
      fire_limit:           editingTrigger.fire_limit   || 0,
      auto_pin:             editingTrigger.auto_pin     || 0,
      is_enabled:           editingTrigger.is_enabled   ?? true,
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
          const conditionGroups = editingTrigger.conditionGroups || [{ id: 1, conditions: [] }];
          const updCond = (gIdx, cIdx, field, val) => setEditingTrigger(prev => ({
            ...prev,
            conditionGroups: (prev.conditionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
              ...g, conditions: g.conditions.map((c, ci) => ci !== cIdx ? c : {...c, [field]: val})
            })
          }));
          const removeCond = (gIdx, cIdx) => setEditingTrigger(prev => ({
            ...prev,
            conditionGroups: (prev.conditionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
              ...g, conditions: g.conditions.filter((_, ci) => ci !== cIdx)
            })
          }));
          const addConditionToGroup = (gIdx, signal) => {
            setEditingTrigger(prev => ({
              ...prev,
              conditionGroups: (prev.conditionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
                ...g, conditions: [...g.conditions, { id: Date.now(), signal, type: 'keyword', condition: 'contains', keyword: '', chips: [], keywordMode: 'chips', inverted: false, modifier: 'nocase', placeholder_key: '' }]
              })
            }));
            setShowCondPickerModal(false);
          };
          const addChip = (gIdx, cIdx, text) => {
            const trimmed = text.trim();
            if (!trimmed) return;
            const chips = [...(conditionGroups[gIdx]?.conditions[cIdx]?.chips || []), trimmed];
            updCond(gIdx, cIdx, 'chips', chips);
            updCond(gIdx, cIdx, 'keyword', chips.join(', '));
            setCondChipInput('');
          };
          const removeChip = (gIdx, cIdx, chipIdx) => {
            const chips = (conditionGroups[gIdx]?.conditions[cIdx]?.chips || []).filter((_, i) => i !== chipIdx);
            updCond(gIdx, cIdx, 'chips', chips);
            updCond(gIdx, cIdx, 'keyword', chips.join(', '));
          };
          const moveCondInGroup = (gIdx, cIdx, dir) => setEditingTrigger(prev => {
            const groups = (prev.conditionGroups||[]).map((g, gi) => {
              if (gi !== gIdx) return g;
              const conds = [...g.conditions];
              const newIdx = cIdx + dir;
              if (newIdx < 0 || newIdx >= conds.length) return g;
              [conds[cIdx], conds[newIdx]] = [conds[newIdx], conds[cIdx]];
              return {...g, conditions: conds};
            });
            return {...prev, conditionGroups: groups};
          });
          const addCondGroup = () => setEditingTrigger(prev => ({
            ...prev, conditionGroups: [...(prev.conditionGroups||[]), { id: Date.now(), conditions: [] }]
          }));
          const removeCondGroup = (gIdx) => setEditingTrigger(prev => ({
            ...prev, conditionGroups: (prev.conditionGroups||[]).filter((_, i) => i !== gIdx)
          }));
          const moveCondGroup = (gIdx, dir) => setEditingTrigger(prev => {
            const groups = [...(prev.conditionGroups||[])];
            const newIdx = gIdx + dir;
            if (newIdx < 0 || newIdx >= groups.length) return prev;
            [groups[gIdx], groups[newIdx]] = [groups[newIdx], groups[gIdx]];
            return {...prev, conditionGroups: groups};
          });
          const actionGroups = editingTrigger.actionGroups || [{ id: 1, probability: 100, actions: [] }];
          const updActionGroup = (gIdx, field, val) => setEditingTrigger(prev => ({
            ...prev,
            actionGroups: (prev.actionGroups||[]).map((g, gi) => gi !== gIdx ? g : {...g, [field]: val})
          }));
          const updAction = (gIdx, aIdx, field, val) => setEditingTrigger(prev => ({
            ...prev,
            actionGroups: (prev.actionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
              ...g, actions: g.actions.map((a, ai) => ai !== aIdx ? a : {...a, [field]: val})
            })
          }));
          const removeAction = (gIdx, aIdx) => setEditingTrigger(prev => ({
            ...prev,
            actionGroups: (prev.actionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
              ...g, actions: g.actions.filter((_, ai) => ai !== aIdx)
            })
          }));
          const addActionToGroup = (gIdx, type) => {
            const base = { id: Date.now(), type, duration: '', emoji_reaction: '' };
            const sendTextExtra = type === 'send_text' || type === 'dm' ? {
              variants: [{ id: Date.now(), text: '', media_type: 'none' }],
              currentVariant: 0, msgTab: 'editor', reply_target: 'none',
              settings: { delete_after: false, delete_after_sec: 60, send_delayed: false, pin: false, disable_preview: false, disable_notify: false, delete_previous: false, content_protection: false },
              keyboard: [],
              reply_text: '', media_type: 'none', bot_msg_delete: 'no', bot_msg_delete_after: 60,
            } : { reply_text: '', media_type: 'none', reply_target: 'none', bot_msg_delete: 'no', bot_msg_delete_after: 60 };
            setEditingTrigger(prev => ({
              ...prev,
              actionGroups: (prev.actionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
                ...g, actions: [...g.actions, { ...base, ...sendTextExtra }]
              })
            }));
            setShowActPickerModal(false);
          };
          const addActionGroup = () => setEditingTrigger(prev => ({
            ...prev, actionGroups: [...(prev.actionGroups||[]), { id: Date.now(), probability: 100, actions: [] }]
          }));
          const removeActionGroup = (gIdx) => setEditingTrigger(prev => ({
            ...prev, actionGroups: (prev.actionGroups||[]).filter((_, i) => i !== gIdx)
          }));
          const moveActionGroup = (gIdx, dir) => setEditingTrigger(prev => {
            const groups = [...(prev.actionGroups||[])];
            const newIdx = gIdx + dir;
            if (newIdx < 0 || newIdx >= groups.length) return prev;
            [groups[gIdx], groups[newIdx]] = [groups[newIdx], groups[gIdx]];
            return {...prev, actionGroups: groups};
          });
          const COND_TOOLTIP_TEXT = {
            'msg_keyword': 'Проверяет текст входящего сообщения — содержит ли оно указанное слово или фразу.',
            'msg_any':     'Срабатывает на любое текстовое сообщение, без проверки содержимого.',
            'qmsg_keyword': 'Проверяет текст сообщения, на которое ответили (цитируемое).',
            'qmsg_any':    'Срабатывает, когда пользователь отвечает на любое сообщение цитированием.',
          };

          const COND_LABELS = { contains:'Содержит', exact:'Точное', starts_with:'Начало', ends_with:'Конец', whole_word:'Целое слово' };
          const ACTION_TYPES = [
            { type:'send_text', label:'Отправить сообщение в чат', Icon: MessageCircle },
            { type:'dm',        label:'Личное сообщение',   Icon: Send          },
            { type:'mute',      label:'Мут',               Icon: Clock         },
            { type:'ban',       label:'Бан',               Icon: ShieldBan     },
            { type:'warn',      label:'Предупреждение',    Icon: AlertOctagon  },
            { type:'delete',    label:'Удалить сообщение', Icon: Trash2        },
            { type:'emoji',     label:'Реакция',           Icon: Smile         },
            { type:'pin',       label:'Закрепить сообщение',Icon: CheckCircle2   },
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

              {/* ── УСЛОВИЯ + ДЕЙСТВИЯ (2 колонки) ── */}
              <div className="grid grid-cols-2 gap-3 mb-5">

              {/* ─── Левая колонка: УСЛОВИЯ ─── */}
              <div className="space-y-3">
                {/* Заголовок блока */}
                <div className="flex items-center gap-2 px-1">
                  <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Условия</span>
                  <div className="relative">
                    <button
                      onClick={() => setCondTooltip(condTooltip === 'block' ? null : 'block')}
                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 active:scale-90 transition-all flex-shrink-0">
                      ?
                    </button>
                    {condTooltip === 'block' && (
                      <div className="absolute left-0 top-6 w-64 bg-gray-900 text-white text-[11px] font-medium p-3 rounded-2xl shadow-xl z-50 leading-relaxed">
                        Условия определяют, на что реагирует триггер. Несколько условий в одной группе работают как «И» (все должны совпасть). Несколько групп работают как «ИЛИ» (достаточно одной).
                        <div className="absolute -top-1.5 left-2 w-3 h-3 bg-gray-900 rotate-45"/>
                      </div>
                    )}
                  </div>
                  {conditionGroups.length > 1 && (
                    <span className="ml-auto text-[9px] font-black text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full uppercase">
                      {conditionGroups.length} группы
                    </span>
                  )}
                </div>

                {/* Группы условий */}
                {conditionGroups.map((group, gIdx) => {
                  return (
                    <div key={group.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm">
                      {/* Шапка группы */}
                      <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 border-b border-gray-100 rounded-t-2xl overflow-hidden">
                        <span className="text-[10px] font-black text-gray-600 uppercase tracking-widest flex-1">
                          {conditionGroups.length > 1 ? `Группа ${gIdx + 1}` : 'Условия'}
                          {conditionGroups.length > 1 && gIdx < conditionGroups.length - 1 && (
                            <span className="ml-2 text-[9px] font-black text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full">ИЛИ ↓</span>
                          )}
                        </span>
                        <div className="flex items-center gap-0.5">
                          <button onClick={() => moveCondGroup(gIdx, -1)} disabled={gIdx === 0}
                            className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↑</button>
                          <button onClick={() => moveCondGroup(gIdx, 1)} disabled={gIdx === conditionGroups.length - 1}
                            className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↓</button>
                          {conditionGroups.length > 1 && (
                            <button onClick={() => removeCondGroup(gIdx)}
                              className="p-1 text-red-300 hover:text-red-500 active:scale-90 transition-all ml-0.5">
                              <Trash2 size={12}/>
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Условия внутри группы */}
                      <div className="p-3 space-y-2">
                        {group.conditions.length === 0 && (
                          <div className="text-center py-4 text-gray-300 text-[11px] font-black uppercase tracking-widest">
                            Список пуст
                          </div>
                        )}
                        {group.conditions.map((cond, cIdx) => {
                          const COND_TYPE_LABELS = { exact:'Полное совпадение', ends_with:'Сообщение заканчивается на', starts_with:'Сообщение начинается с', contains:'Сообщение содержит', whole_word:'Целое слово' };
                          const typeKey = `type_${gIdx}_${cIdx}`;
                          const modKey  = `mod_${gIdx}_${cIdx}`;
                          return (
                          <div key={cond.id} className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
                            {/* Шапка: ⚙️ + Условие N + ↑↓🗑 */}
                            <div className="flex items-center gap-1.5 px-3 py-2 bg-gray-50 border-b border-gray-100">
                              <button onClick={() => setCondSettingsModal({gIdx, cIdx})}
                                className="p-1 text-gray-400 hover:text-gray-600 active:scale-90 transition-all flex-shrink-0">
                                <Settings size={12}/>
                              </button>
                              <span className="text-[11px] font-black text-gray-700 flex-1">Условие {cIdx + 1}</span>
                              {cond.placeholder_key && (
                                <span className="text-[9px] font-bold text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded-full">%{cond.placeholder_key}%</span>
                              )}
                              <div className="flex items-center gap-0">
                                <button onClick={() => moveCondInGroup(gIdx, cIdx, -1)} disabled={cIdx === 0}
                                  className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↑</button>
                                <button onClick={() => moveCondInGroup(gIdx, cIdx, 1)} disabled={cIdx === group.conditions.length - 1}
                                  className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↓</button>
                                <button onClick={() => removeCond(gIdx, cIdx)}
                                  className="p-1 text-red-300 hover:text-red-500 active:scale-90 transition-all">
                                  <Trash2 size={11}/>
                                </button>
                              </div>
                            </div>

                            {/* Тело карточки */}
                            <div className="px-3 py-3 space-y-3" onClick={() => setCondOpenDropdown(null)}>

                              {/* Сигнал */}
                              <div className="flex items-center gap-1.5">
                                <span className="text-[12px] font-black text-gray-800">
                                  {cond.signal === 'message' ? 'Сообщение' : 'Цитируемое'}
                                </span>
                                <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `sig_${gIdx}_${cIdx}` ? null : `sig_${gIdx}_${cIdx}`); }}
                                  className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600 flex-shrink-0">?</button>
                                {condTooltip === `sig_${gIdx}_${cIdx}` && (
                                  <div className="absolute z-50 mt-1 w-52 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl leading-relaxed">
                                    {cond.signal === 'message' ? 'Условие проверяет текст входящего сообщения.' : 'Условие проверяет текст цитируемого (reply) сообщения.'}
                                  </div>
                                )}
                              </div>

                              {/* Тип условия */}
                              <div onClick={e => e.stopPropagation()}>
                                <p className="text-[9px] font-black text-gray-500 uppercase mb-1.5">
                                  Выберите тип условия <span className="text-red-400">*</span>
                                </p>
                                <div className="relative">
                                  <button
                                    onClick={() => setCondOpenDropdown(condOpenDropdown === typeKey ? null : typeKey)}
                                    className="w-full flex items-center justify-between px-3 py-2.5 bg-white border-2 border-gray-200 rounded-xl text-sm font-bold text-gray-700 hover:border-gray-300 transition-all">
                                    <span>{COND_TYPE_LABELS[cond.condition] || cond.condition}</span>
                                    <ChevronDown size={14} className={`text-gray-400 transition-transform duration-200 ${condOpenDropdown === typeKey ? 'rotate-180' : ''}`}/>
                                  </button>
                                  {condOpenDropdown === typeKey && (
                                    <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                      {Object.entries(COND_TYPE_LABELS).map(([key, lbl]) => (
                                        <button key={key}
                                          onClick={() => { updCond(gIdx, cIdx, 'condition', key); setCondOpenDropdown(null); }}
                                          className={`w-full px-4 py-2.5 text-sm font-bold text-left transition-all ${cond.condition === key ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                          {lbl}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* Сигнал для вызова */}
                              <p className="text-[10px] text-orange-500 font-semibold -mt-1">
                                Сигнал для вызова триггера: {cond.signal === 'message' ? '📋 Сообщение' : '↩️ Цитируемое'}
                              </p>

                              {/* Значения условия (Chips / Text) */}
                              <div onClick={e => e.stopPropagation()}>
                                <div className="flex items-center gap-1.5 mb-2">
                                  <p className="text-[9px] font-black text-gray-500 uppercase">
                                    Значения условия <span className="text-red-400">*</span>
                                  </p>
                                  <div className="relative">
                                    <button
                                      onClick={() => setCondOpenDropdown(condOpenDropdown === `kw_${gIdx}_${cIdx}` ? null : `kw_${gIdx}_${cIdx}`)}
                                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600 flex-shrink-0">
                                      ⚙
                                    </button>
                                    {condOpenDropdown === `kw_${gIdx}_${cIdx}` && (
                                      <div className="absolute left-0 top-6 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl overflow-hidden min-w-[160px]">
                                        <button onClick={() => { updCond(gIdx, cIdx, 'chips', []); updCond(gIdx, cIdx, 'keyword', ''); setCondOpenDropdown(null); setCondChipInput(''); }}
                                          className="w-full flex items-center gap-2 px-3 py-2.5 text-[11px] font-bold text-red-500 hover:bg-red-50 transition-all text-left">
                                          <RotateCcw size={11}/> Отменить изменения
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                </div>
                                {/* Табы */}
                                <div className="flex border-b border-gray-200 mb-2">
                                  <button onClick={() => updCond(gIdx, cIdx, 'keywordMode', 'chips')}
                                    className={`flex items-center gap-1 px-3 py-1.5 text-[10px] font-black border-b-2 -mb-px transition-all ${(cond.keywordMode||'chips') === 'chips' ? 'text-blue-600 border-blue-500' : 'text-gray-400 border-transparent'}`}>
                                    🏷 Chips ({(cond.chips||[]).length})
                                  </button>
                                  <button onClick={() => updCond(gIdx, cIdx, 'keywordMode', 'text')}
                                    className={`flex items-center gap-1 px-3 py-1.5 text-[10px] font-black border-b-2 -mb-px transition-all ${(cond.keywordMode||'chips') === 'text' ? 'text-blue-600 border-blue-500' : 'text-gray-400 border-transparent'}`}>
                                    📄 Text
                                  </button>
                                </div>
                                {(cond.keywordMode||'chips') === 'chips' ? (
                                  <div>
                                    {(cond.chips||[]).length > 0 && (
                                      <div className="flex flex-wrap gap-1 mb-2">
                                        {(cond.chips||[]).map((chip, ci) => (
                                          <span key={ci} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-lg text-[10px] font-bold">
                                            {chip}
                                            <button onClick={() => removeChip(gIdx, cIdx, ci)} className="text-blue-400 hover:text-blue-700 leading-none ml-0.5">×</button>
                                          </span>
                                        ))}
                                      </div>
                                    )}
                                    <div className="flex gap-1">
                                      <input type="text"
                                        value={condChipInput}
                                        onChange={e => setCondChipInput(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addChip(gIdx, cIdx, condChipInput); }}}
                                        placeholder=""
                                        className="flex-1 px-3 py-2 bg-white border-2 border-gray-200 rounded-xl text-sm font-bold outline-none focus:border-blue-300 transition-all"/>
                                      <button onClick={() => addChip(gIdx, cIdx, condChipInput)}
                                        className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-xl text-gray-500 active:scale-95 transition-all">
                                        <Check size={13}/>
                                      </button>
                                    </div>
                                    <p className="text-[9px] text-gray-400 mt-1">* Введите значения по одному с помощью «Enter»</p>
                                    {(cond.chips||[]).length === 0 && <p className="text-[9px] text-red-400 mt-0.5">Обязательное поле</p>}
                                  </div>
                                ) : (
                                  <div>
                                    <textarea
                                      value={(cond.chips||[]).join(', ')}
                                      onChange={e => { const chips = e.target.value.split(',').map(s=>s.trim()).filter(Boolean); updCond(gIdx, cIdx, 'chips', chips); updCond(gIdx, cIdx, 'keyword', e.target.value); }}
                                      rows={2}
                                      className="w-full p-2.5 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 resize-none transition-all"/>
                                    <p className="text-[9px] text-gray-400 mt-1">* Перечислите значения через запятую</p>
                                  </div>
                                )}
                              </div>

                              {/* Модификаторы */}
                              <div onClick={e => e.stopPropagation()}>
                                <div className="flex items-center gap-1 mb-1.5">
                                  <p className="text-[9px] font-black text-gray-500 uppercase">Модификаторы</p>
                                  <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `modtip_${gIdx}_${cIdx}` ? null : `modtip_${gIdx}_${cIdx}`); }}
                                    className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600">?</button>
                                  {condTooltip === `modtip_${gIdx}_${cIdx}` && (
                                    <div className="absolute z-50 mt-1 w-52 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl leading-relaxed">
                                      Модификаторы изменяют поведение проверки. «Не учитывать регистр» позволяет реагировать на «Привет» и «привет» одинаково.
                                    </div>
                                  )}
                                </div>
                                <div className="relative">
                                  <button onClick={() => setCondOpenDropdown(condOpenDropdown === modKey ? null : modKey)}
                                    className="w-full flex items-center justify-between px-3 py-2 bg-white border-2 border-gray-200 rounded-xl text-sm hover:border-gray-300 transition-all">
                                    <div className="flex items-center gap-1.5 flex-1 flex-wrap">
                                      {cond.modifier === 'nocase' ? (
                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded-lg text-[10px] font-bold text-gray-600">
                                          Не учитывать регистр
                                          <button onClick={e => { e.stopPropagation(); updCond(gIdx, cIdx, 'modifier', ''); }} className="ml-0.5 text-gray-400 hover:text-gray-700 leading-none">×</button>
                                        </span>
                                      ) : <span className="text-gray-400 text-sm font-medium">—</span>}
                                    </div>
                                    <ChevronDown size={13} className={`text-gray-400 flex-shrink-0 transition-transform ${condOpenDropdown === modKey ? 'rotate-180' : ''}`}/>
                                  </button>
                                  {condOpenDropdown === modKey && (
                                    <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                      <button onClick={() => { updCond(gIdx, cIdx, 'modifier', 'nocase'); setCondOpenDropdown(null); }}
                                        className={`w-full px-4 py-2.5 text-sm font-bold text-left transition-all ${cond.modifier === 'nocase' ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                        Не учитывать регистр
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* Инвертировать */}
                              <div className="space-y-1">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[11px] font-black text-gray-700">Инвертировать условие</span>
                                    <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `inv_${gIdx}_${cIdx}` ? null : `inv_${gIdx}_${cIdx}`); }}
                                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600">?</button>
                                  </div>
                                  <button onClick={() => updCond(gIdx, cIdx, 'inverted', !(cond.inverted||false))}
                                    className={`relative w-10 h-5 rounded-full transition-all duration-200 flex-shrink-0 ${cond.inverted ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                    <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${cond.inverted ? 'left-[calc(100%-1.125rem)]' : 'left-0.5'}`}/>
                                  </button>
                                </div>
                                <p className="text-[9px] text-gray-400 leading-relaxed">* Триггер будет работать наоборот. Бот будет реагировать, если условие не выполнено.</p>
                              </div>

                            </div>
                          </div>
                          );
                        })}

                        {/* Добавить условие в эту группу */}
                        <button
                          onClick={() => { setCondPickerGroupIdx(gIdx); setCondPickerTab('message'); setCondPickerSearch(''); setShowCondPickerModal(true); }}
                          className="w-full py-2.5 border-2 border-dashed border-blue-200 rounded-xl text-blue-400 font-black text-[10px] uppercase flex items-center justify-center gap-1.5 hover:border-blue-400 hover:text-blue-500 transition-all bg-blue-50/30 active:scale-[0.98]">
                          <PlusCircle size={12}/> Добавить условие
                        </button>
                      </div>
                    </div>
                  );
                })}

                {/* Добавить группу условий */}
                <button
                  onClick={addCondGroup}
                  className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-2xl text-gray-400 font-black text-[10px] uppercase flex items-center justify-center gap-1.5 hover:border-blue-200 hover:text-blue-400 transition-all bg-white active:scale-[0.98]">
                  <PlusCircle size={11}/> Добавить группу условий
                </button>
              </div>{/* конец левой колонки */}

              {/* ─── Правая колонка: ДЕЙСТВИЯ ─── */}
              <div className="space-y-3">
                {/* Заголовок */}
                <div className="flex items-center gap-2 px-1">
                  <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Действия</span>
                  <div className="relative">
                    <button
                      onClick={() => setCondTooltip(condTooltip === 'actions_block' ? null : 'actions_block')}
                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 active:scale-90 transition-all flex-shrink-0">
                      ?
                    </button>
                    {condTooltip === 'actions_block' && (
                      <div className="absolute left-0 top-6 w-64 bg-gray-900 text-white text-[11px] font-medium p-3 rounded-2xl shadow-xl z-50 leading-relaxed">
                        Действия — это что бот делает при срабатывании триггера. Можно добавить несколько групп: каждая группа имеет свой шанс выполнения.
                        <div className="absolute -top-1.5 left-2 w-3 h-3 bg-gray-900 rotate-45"/>
                      </div>
                    )}
                  </div>
                </div>

                {/* Группы действий */}
                {actionGroups.map((group, gIdx) => (
                  <div key={group.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                    {/* Шапка группы */}
                    <div className="flex items-center gap-1.5 px-3 py-2 bg-gray-50 border-b border-gray-100">
                      {/* Шестерёнка */}
                      <div className="relative">
                        <button
                          onClick={() => setActGroupSettingsIdx(actGroupSettingsIdx === gIdx ? null : gIdx)}
                          className="p-1 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                          <Settings size={12}/>
                        </button>
                        {actGroupSettingsIdx === gIdx && (
                          <div className="absolute left-0 top-7 w-56 bg-white border border-gray-100 rounded-2xl shadow-xl z-50 p-3 space-y-2"
                            onClick={e => e.stopPropagation()}>
                            <p className="text-[10px] font-black text-gray-600 uppercase tracking-wide">Настройки группы</p>
                            <div className="flex items-center gap-2">
                              <label className="text-[10px] font-bold text-gray-500 flex-1">Шанс выполнения</label>
                              <div className="flex items-center gap-1 bg-gray-50 border border-gray-200 rounded-lg px-2 py-1">
                                <input
                                  type="number" min="1" max="100"
                                  value={group.probability}
                                  onChange={e => updActionGroup(gIdx, 'probability', Math.min(100, Math.max(1, parseInt(e.target.value)||1)))}
                                  className="w-10 text-center font-black text-sm bg-transparent outline-none"/>
                                <span className="text-[10px] font-black text-gray-400">%</span>
                              </div>
                            </div>
                            <button onClick={() => setActGroupSettingsIdx(null)}
                              className="w-full py-1.5 bg-blue-500 text-white rounded-xl text-[10px] font-black uppercase active:scale-95 transition-all">
                              Готово
                            </button>
                          </div>
                        )}
                      </div>
                      <span className="text-[10px] font-black text-gray-600 uppercase tracking-widest flex-1">
                        {actionGroups.length > 1 ? `Группа ${gIdx + 1}` : 'Действия'}
                        {group.probability < 100 && (
                          <span className="ml-1.5 text-[9px] font-black text-orange-500 bg-orange-50 px-1.5 py-0.5 rounded-full">{group.probability}%</span>
                        )}
                      </span>
                      <div className="flex items-center gap-0.5">
                        <button onClick={() => moveActionGroup(gIdx, -1)} disabled={gIdx === 0}
                          className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↑</button>
                        <button onClick={() => moveActionGroup(gIdx, 1)} disabled={gIdx === actionGroups.length - 1}
                          className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↓</button>
                        {actionGroups.length > 1 && (
                          <button onClick={() => removeActionGroup(gIdx)}
                            className="p-1 text-red-300 hover:text-red-500 active:scale-90 transition-all ml-0.5">
                            <Trash2 size={12}/>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Действия внутри группы */}
                    <div className="p-2.5 space-y-2">
                      {group.actions.length === 0 && (
                        <div className="text-center py-4 text-gray-300 text-[11px] font-black uppercase tracking-widest">
                          Список пуст
                        </div>
                      )}
                      {group.actions.map((action, aIdx) => {
                        const actCfg = ACTION_TYPES.find(a => a.type === action.type) || ACTION_TYPES[0];
                        const variants = action.variants || [{ id: 1, text: '', media_type: 'none' }];
                        const curVarIdx = action.currentVariant || 0;
                        const curVar = variants[curVarIdx] || variants[0] || { text: '', media_type: 'none' };
                        const msgTab = action.msgTab || 'editor';
                        const settings = action.settings || {};
                        const keyboard = action.keyboard || [];
                        const replyDropKey = `reply_${gIdx}_${aIdx}`;

                        const updVar = (field, val) => updAction(gIdx, aIdx, 'variants',
                          variants.map((v, vi) => vi === curVarIdx ? {...v, [field]: val} : v));
                        const addVariant = () => {
                          updAction(gIdx, aIdx, 'variants', [...variants, { id: Date.now(), text: '', media_type: 'none' }]);
                          updAction(gIdx, aIdx, 'currentVariant', variants.length);
                        };
                        const deleteVariant = () => {
                          if (variants.length <= 1) return;
                          const newVars = variants.filter((_, vi) => vi !== curVarIdx);
                          updAction(gIdx, aIdx, 'variants', newVars);
                          updAction(gIdx, aIdx, 'currentVariant', Math.max(0, curVarIdx - 1));
                        };
                        const updSetting = (key, val) => updAction(gIdx, aIdx, 'settings', {...settings, [key]: val});

                        return (
                          <div key={action.id} className="bg-white rounded-2xl border border-gray-200">
                            {/* Шапка: ⚙️ + "Действие N" + ↑↓🗑 */}
                            <div className="flex items-center gap-1.5 px-3 py-2 bg-gray-50 border-b border-gray-100 rounded-t-2xl overflow-hidden">
                              <button
                                onClick={() => { setActionSettingsPct(action.action_probability ?? 100); setActionSettingsModal({gIdx, aIdx}); }}
                                className="p-1 text-gray-400 hover:text-blue-500 active:scale-90 transition-all flex-shrink-0">
                                <Settings size={12}/>
                              </button>
                              <span className="text-[11px] font-black text-gray-700 flex-1">Действие {aIdx + 1}</span>
                              <div className="flex items-center gap-0">
                                <button onClick={() => { /* moveActionInGroup */ }} disabled={aIdx === 0}
                                  className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↑</button>
                                <button onClick={() => { /* moveActionInGroup */ }} disabled={aIdx === group.actions.length - 1}
                                  className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↓</button>
                                <button onClick={() => removeAction(gIdx, aIdx)}
                                  className="p-1 text-red-300 hover:text-red-500 active:scale-90 transition-all">
                                  <Trash2 size={11}/>
                                </button>
                              </div>
                            </div>

                            {/* Тело карточки */}
                            <div className="px-3 py-3 space-y-3">

                              {/* Тип действия — заголовок */}
                              <div className="flex items-center gap-1.5">
                                <span className="text-[12px] font-black text-gray-800">{actCfg.label}</span>
                                <div className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center">?</div>
                              </div>

                              {/* ── send_text / dm ── */}
                              {(action.type === 'send_text' || action.type === 'dm') && (
                                <div className="space-y-3">

                                  {/* ── Сообщение * ── */}
                                  <div>
                                    <p className="text-sm font-black text-gray-800 mb-2">
                                      {action.type === 'dm' ? 'Текст сообщения' : 'Сообщение'} <span className="text-red-400">*</span>
                                    </p>

                                    {/* Навигация вариантов */}
                                    <div className="flex items-center gap-2 mb-2">
                                      <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
                                        <button onClick={() => updAction(gIdx, aIdx, 'currentVariant', Math.max(0, curVarIdx - 1))}
                                          disabled={curVarIdx === 0}
                                          className="px-2.5 py-1.5 text-gray-500 hover:text-gray-700 disabled:opacity-30 text-sm font-bold transition-colors">‹</button>
                                        <span className="text-xs font-black text-gray-700 px-2 border-x border-gray-200">{curVarIdx + 1} из {variants.length}</span>
                                        <button onClick={() => updAction(gIdx, aIdx, 'currentVariant', Math.min(variants.length - 1, curVarIdx + 1))}
                                          disabled={curVarIdx === variants.length - 1}
                                          className="px-2.5 py-1.5 text-gray-500 hover:text-gray-700 disabled:opacity-30 text-sm font-bold transition-colors">›</button>
                                      </div>
                                      <button onClick={addVariant}
                                        className="flex items-center gap-1.5 px-3 py-1.5 border border-blue-200 text-blue-600 rounded-lg text-xs font-black hover:bg-blue-50 transition-all active:scale-95 ml-auto">
                                        <PlusCircle size={11}/> Добавить вариант сообщения
                                      </button>
                                      {variants.length > 1 && (
                                        <button onClick={deleteVariant}
                                          className="p-1.5 text-red-300 hover:text-red-500 active:scale-90 transition-all">
                                          <Trash2 size={14}/>
                                        </button>
                                      )}
                                    </div>

                                    {/* Медиа область */}
                                    <div
                                      onClick={() => { const inp = document.createElement('input'); inp.type='file'; inp.accept='image/*,video/*,image/gif'; inp.onchange=e=>{ if(e.target.files[0]) { const f=e.target.files[0]; updVar('media_type', f.type.startsWith('video') ? 'video' : f.type==='image/gif' ? 'animation' : 'photo'); }}; inp.click(); }}
                                      className="w-full h-28 border-2 border-dashed border-blue-200 rounded-xl flex flex-col items-center justify-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/30 transition-all mb-2 select-none">
                                      {curVar.media_type === 'none' || !curVar.media_type ? (
                                        <>
                                          <span className="text-2xl mb-1">👆</span>
                                          <span className="text-xs text-blue-500 font-semibold">Нажмите, чтобы загрузить медиа</span>
                                        </>
                                      ) : (
                                        <div className="flex items-center gap-2">
                                          <span className="text-xl">{curVar.media_type==='photo'?'🖼':curVar.media_type==='video'?'🎬':'🎞'}</span>
                                          <span className="text-sm font-black text-gray-700 capitalize">{curVar.media_type}</span>
                                          <button onClick={e=>{e.stopPropagation();updVar('media_type','none');}}
                                            className="text-red-400 hover:text-red-600 text-lg ml-1">×</button>
                                        </div>
                                      )}
                                    </div>

                                    {/* Топики + вкладки + редактор */}
                                    <div className="border border-gray-200 rounded-xl overflow-hidden">
                                      {/* Строка вкладок */}
                                      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200">
                                        <div className="flex items-center gap-1.5">
                                          <span className="text-xs font-black text-gray-600 flex items-center gap-1">
                                            <span>📋</span> Топики
                                          </span>
                                          <span className="text-[10px] font-black text-white bg-orange-400 px-1.5 py-0.5 rounded-md">Starter</span>
                                        </div>
                                        <div className="flex gap-0.5">
                                          {[
                                            { v:'editor',   l:'✏ Редактор' },
                                            { v:'code',     l:'<> Код'     },
                                            { v:'settings', l:'⚙ Настройки'},
                                          ].map(t => (
                                            <button key={t.v} onClick={() => updAction(gIdx, aIdx, 'msgTab', t.v)}
                                              className={`px-2.5 py-1 text-[11px] font-black rounded transition-all ${msgTab===t.v ? 'bg-blue-500 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
                                              {t.l}
                                            </button>
                                          ))}
                                        </div>
                                      </div>

                                      {/* Редактор */}
                                      {msgTab === 'editor' && (
                                        <div>
                                          <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-gray-100 flex-wrap">
                                            {[
                                              {l:'B',  cls:'font-black'},
                                              {l:'I',  cls:'italic'},
                                              {l:'S',  cls:'line-through'},
                                              {l:'U',  cls:'underline'},
                                              {l:'<>', cls:'font-mono text-[9px]'},
                                              {l:'»',  cls:''},
                                              {l:'🔗', cls:''},
                                              {l:'✒',  cls:''},
                                              {l:'🖼',  cls:''},
                                              {l:'Tx', cls:'text-[9px]'},
                                              {l:'😊', cls:''},
                                            ].map(f => (
                                              <button key={f.l} className={`w-7 h-7 text-[11px] text-gray-600 hover:bg-gray-100 rounded flex items-center justify-center transition-all active:scale-90 ${f.cls}`}>{f.l}</button>
                                            ))}
                                            <button className="ml-auto px-2 py-1 text-[10px] font-bold text-blue-500 border border-blue-200 rounded-lg hover:bg-blue-50 transition-all whitespace-nowrap">
                                              %плейсхолдеры%
                                            </button>
                                            <div className="flex items-center gap-0.5 ml-1">
                                              <button className="w-6 h-6 text-[10px] text-gray-400 hover:text-gray-600 font-black rounded hover:bg-gray-100 flex items-center justify-center">?</button>
                                              <button className="w-6 h-6 text-[10px] text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100 flex items-center justify-center">↗</button>
                                            </div>
                                          </div>
                                          <div className="relative">
                                            <textarea
                                              value={curVar.text || ''}
                                              onChange={e => updVar('text', e.target.value)}
                                              placeholder="Insert text here ..."
                                              rows={6}
                                              className="w-full px-4 py-3 text-sm font-medium text-gray-700 italic outline-none resize-none bg-white placeholder:text-gray-300 placeholder:not-italic"/>
                                            <span className="absolute bottom-2 right-3 text-[10px] text-blue-500 font-black bg-white px-1">{(curVar.text||'').length}/4096</span>
                                          </div>
                                        </div>
                                      )}

                                      {/* Код */}
                                      {msgTab === 'code' && (
                                        <textarea
                                          value={curVar.text || ''}
                                          onChange={e => updVar('text', e.target.value)}
                                          placeholder="HTML код сообщения..."
                                          rows={6}
                                          className="w-full px-4 py-3 font-mono text-sm text-gray-700 outline-none resize-none bg-white"/>
                                      )}

                                      {/* Настройки */}
                                      {msgTab === 'settings' && (
                                        <div className="p-4 grid grid-cols-2 gap-x-6 gap-y-4">
                                          {[
                                            { key:'delete_after',      label:'Удалить сообщение через'       },
                                            { key:'send_delayed',      label:'Отправить сообщение с задержкой'},
                                            { key:'pin',               label:'Закрепить сообщение'           },
                                            { key:'disable_preview',   label:'Отключить предпросмотр ссылок' },
                                            { key:'disable_notify',    label:'Отключить уведомления'         },
                                            { key:'delete_previous',   label:'Удалять предыдущее сообщение'  },
                                            { key:'content_protection',label:'Защита контента'               },
                                          ].map(s => (
                                            <div key={s.key} className="flex items-center justify-between gap-2">
                                              <div className="flex items-center gap-1 min-w-0">
                                                <span className="text-xs font-medium text-gray-700 leading-tight">{s.label}</span>
                                                <div className="w-4 h-4 rounded-full bg-blue-100 text-blue-500 text-[9px] font-black flex items-center justify-center flex-shrink-0 cursor-pointer">?</div>
                                              </div>
                                              <button onClick={() => updSetting(s.key, !settings[s.key])}
                                                className={`relative w-10 h-5 rounded-full transition-all duration-200 flex-shrink-0 ${settings[s.key] ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                                <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${settings[s.key] ? 'left-[calc(100%-1.125rem)]' : 'left-0.5'}`}/>
                                              </button>
                                            </div>
                                          ))}
                                        </div>
                                      )}

                                      {/* Создать / Редактировать клавиатуру */}
                                      <div className="border-t border-gray-100">
                                        {keyboard.length === 0 ? (
                                          <button
                                            onClick={() => { setKbModalTarget({gIdx, aIdx}); setKbButtonType(null); setKbNewButton({}); setShowKeyboardModal(true); }}
                                            className="w-full py-3 text-sm font-bold text-gray-500 hover:bg-gray-50 flex items-center justify-center gap-2 transition-all active:scale-[0.99]">
                                            ✏️ Создать клавиатуру
                                          </button>
                                        ) : (
                                          <div>
                                            <div className="p-2 space-y-1.5">
                                              {keyboard.map((btn, bi) => (
                                                <div key={btn.id} className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg border border-gray-100">
                                                  <GripVertical size={13} className="text-gray-300 cursor-grab flex-shrink-0"/>
                                                  <span className="text-base w-5 text-center">{btn.emoji || '○'}</span>
                                                  <span className="text-xs font-bold text-gray-700 flex-1 truncate">{btn.text || 'Текст кнопки'}</span>
                                                  <button onClick={() => updAction(gIdx, aIdx, 'keyboard', keyboard.filter((_,i)=>i!==bi))}
                                                    className="text-red-300 hover:text-red-500 text-lg leading-none">×</button>
                                                </div>
                                              ))}
                                            </div>
                                            <button
                                              onClick={() => { setKbModalTarget({gIdx, aIdx}); setKbButtonType(null); setKbNewButton({}); setShowKeyboardModal(true); }}
                                              className="w-full py-2.5 text-xs font-bold text-blue-500 hover:bg-blue-50 flex items-center justify-center gap-1.5 transition-all border-t border-gray-100">
                                              ✏️ Редактировать клавиатуру
                                            </button>
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Отправить ответом — только для send_text */}
                                    {action.type === 'send_text' && (
                                      <div className="mt-3">
                                        <p className="text-sm font-black text-gray-800 mb-1.5">
                                          Отправить ответом <span className="text-red-400">*</span>
                                        </p>
                                        <div className="relative">
                                          <button onClick={() => setActOpenDropdown(actOpenDropdown === replyDropKey ? null : replyDropKey)}
                                            className="w-full flex items-center justify-between px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm font-bold text-gray-700 hover:border-gray-300 transition-all">
                                            <span>{action.reply_target === 'initiator' ? 'Ответить реплаем автору' : action.reply_target === 'quoted' ? 'Ответить на цитируемое' : 'Отправить сообщение реплаем'}</span>
                                            <ChevronDown size={14} className={`text-gray-400 transition-transform ${actOpenDropdown === replyDropKey ? 'rotate-180' : ''}`}/>
                                          </button>
                                          {actOpenDropdown === replyDropKey && (
                                            <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                              {[{v:'none',l:'Отправить сообщение реплаем'},{v:'initiator',l:'Ответить реплаем автору'},{v:'quoted',l:'Ответить на цитируемое'}].map(o => (
                                                <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'reply_target', o.v); setActOpenDropdown(null); }}
                                                  className={`w-full px-4 py-3 text-sm font-bold text-left transition-all border-b border-gray-50 last:border-0 ${action.reply_target === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                  {o.l}
                                                </button>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* ── mute ── */}
                              {action.type === 'mute' && (() => {
                                const MUTE_TARGETS = [
                                  { v:'initiator', l:'Инициатор триггера' },
                                  { v:'both',      l:'Кому ответили и инициатор триггера' },
                                  { v:'replied',   l:'Кому ответили' },
                                  { v:'command',   l:'Режим команды' },
                                ];
                                const MUTE_UNITS = [
                                  { v:'seconds', l:'секунда' },
                                  { v:'minutes', l:'минута'  },
                                  { v:'hours',   l:'час'     },
                                  { v:'days',    l:'день'    },
                                  { v:'weeks',   l:'неделя'  },
                                  { v:'months',  l:'месяц'   },
                                ];
                                const MUTE_TYPES = [
                                  { v:'all',     l:'Все сообщения'          },
                                  { v:'media',   l:'Медиа файлы'            },
                                  { v:'inline',  l:'Inline сообщения'       },
                                  { v:'invite',  l:'Возможность приглашать' },
                                  { v:'polls',   l:'Опросы'                 },
                                ];
                                const muteTarget    = action.mute_target     || 'initiator';
                                const muteTimeOn    = action.mute_time_enabled || false;
                                const muteTimeVal   = action.mute_time_value  ?? 1;
                                const muteTimeUnit  = action.mute_time_unit   || 'days';
                                const muteType      = action.mute_type        || 'all';

                                const muteTgtKey    = `muteTgt_${gIdx}_${aIdx}`;
                                const muteUnitKey   = `muteUnit_${gIdx}_${aIdx}`;
                                const muteTypeKey   = `muteType_${gIdx}_${aIdx}`;
                                const muteTgtGear   = `muteTgtGear_${gIdx}_${aIdx}`;
                                const muteTimeGear  = `muteTimeGear_${gIdx}_${aIdx}`;

                                const curTgt  = MUTE_TARGETS.find(o => o.v === muteTarget) || MUTE_TARGETS[0];
                                const curUnit = MUTE_UNITS.find(o => o.v === muteTimeUnit) || MUTE_UNITS[3];
                                const curType = MUTE_TYPES.find(o => o.v === muteType)     || MUTE_TYPES[0];

                                return (
                                  <div className="space-y-4">

                                    {/* На кого распространяется */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-black text-gray-800">
                                          На кого распространяется действие <span className="text-red-400">*</span>
                                        </p>
                                        {muteTarget !== 'initiator' && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === muteTgtGear ? null : muteTgtGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === muteTgtGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'mute_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                                <button onClick={() => { updAction(gIdx, aIdx, 'mute_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <Ban size={11} className="text-gray-400"/> Отключить настройку
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === muteTgtKey ? null : muteTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === muteTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curTgt.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === muteTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === muteTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {MUTE_TARGETS.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'mute_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${muteTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Кол-во времени */}
                                    <div>
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-1.5">
                                          <p className="text-sm font-black text-gray-800">
                                            Кол-во времени <span className="text-red-400">*</span>
                                          </p>
                                          {muteTimeOn && (
                                            <div className="relative">
                                              <button onClick={() => setActOpenDropdown(actOpenDropdown === muteTimeGear ? null : muteTimeGear)}
                                                className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                                <Settings size={14}/>
                                              </button>
                                              {actOpenDropdown === muteTimeGear && (
                                                <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                  <button onClick={() => { updAction(gIdx, aIdx, 'mute_time_value', 1); updAction(gIdx, aIdx, 'mute_time_unit', 'days'); setActOpenDropdown(null); }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                    <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                  </button>
                                                  <button onClick={() => { updAction(gIdx, aIdx, 'mute_time_enabled', false); setActOpenDropdown(null); }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                    <Ban size={11} className="text-gray-400"/> Отключить настройку
                                                  </button>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                        {muteTimeOn ? (
                                          <button onClick={() => updAction(gIdx, aIdx, 'mute_time_enabled', false)}
                                            className="p-1.5 border border-gray-200 rounded-lg text-gray-400 hover:text-red-500 hover:border-red-200 active:scale-90 transition-all">
                                            <Ban size={14}/>
                                          </button>
                                        ) : (
                                          <button onClick={() => updAction(gIdx, aIdx, 'mute_time_enabled', true)}
                                            className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-black text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-all active:scale-95">
                                            Включить
                                          </button>
                                        )}
                                      </div>
                                      {muteTimeOn && (
                                        <div className="flex gap-2 mt-2">
                                          <input type="number" min="1"
                                            value={muteTimeVal}
                                            onChange={e => updAction(gIdx, aIdx, 'mute_time_value', Math.max(1, parseInt(e.target.value)||1))}
                                            className="flex-1 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === muteUnitKey ? null : muteUnitKey)}
                                              className={`flex items-center gap-2 px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 min-w-[110px] hover:border-blue-300 transition-all ${actOpenDropdown === muteUnitKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                              <span className="flex-1">{curUnit.l}</span>
                                              <ChevronDown size={13} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === muteUnitKey ? 'rotate-180' : ''}`}/>
                                            </button>
                                            {actOpenDropdown === muteUnitKey && (
                                              <div className="absolute top-full right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden min-w-[110px]">
                                                {MUTE_UNITS.map(o => (
                                                  <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'mute_time_unit', o.v); setActOpenDropdown(null); }}
                                                    className={`w-full px-3 py-1.5 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${muteTimeUnit === o.v ? 'text-blue-600 bg-blue-50 font-black' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                    {o.l}
                                                  </button>
                                                ))}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      )}
                                    </div>

                                    {/* Тип ограничения */}
                                    <div>
                                      <p className="text-sm font-black text-gray-800 mb-1.5">Тип ограничения</p>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === muteTypeKey ? null : muteTypeKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === muteTypeKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curType.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === muteTypeKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === muteTypeKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {MUTE_TYPES.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'mute_type', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${muteType === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                  </div>
                                );
                              })()}

                              {/* ── ban ── */}
                              {action.type === 'ban' && (
                                <p className="text-xs text-gray-400 font-medium italic">Карточка бана — в разработке.</p>
                              )}

                              {/* ── emoji ── */}
                              {action.type === 'emoji' && (
                                <input type="text" placeholder="👀 🔥 ❤️"
                                  value={action.emoji_reaction || ''} onChange={e => updAction(gIdx, aIdx, 'emoji_reaction', e.target.value)}
                                  className="w-full p-2.5 bg-white border border-gray-200 rounded-xl font-black text-2xl text-center outline-none focus:border-blue-300"/>
                              )}

                              {/* ── warn ── */}
                              {action.type === 'warn' && (() => {
                                const WARN_TARGETS = [
                                  { v:'both',      l:'Кому ответили и инициатор триггера' },
                                  { v:'initiator', l:'Инициатор триггера'                 },
                                  { v:'replied',   l:'Кому ответили'                      },
                                  { v:'command',   l:'Режим команды'                      },
                                ];
                                const warnNotify  = action.warn_notify  ?? true;
                                const warnTarget  = action.warn_target  || 'initiator';
                                const warnCount   = action.warn_count   ?? 1;

                                const warnTgtKey    = `warnTgt_${gIdx}_${aIdx}`;
                                const warnNotifyGear = `warnNotifyGear_${gIdx}_${aIdx}`;
                                const warnTgtGear    = `warnTgtGear_${gIdx}_${aIdx}`;

                                const curTgt = WARN_TARGETS.find(o => o.v === warnTarget) || WARN_TARGETS[1];

                                return (
                                  <div className="space-y-4">

                                    {/* Отправлять уведомление */}
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-1.5">
                                        <p className="text-sm font-medium text-gray-700">Отправлять уведомление о предупреждении</p>
                                        {!warnNotify && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === warnNotifyGear ? null : warnNotifyGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === warnNotifyGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'warn_notify', true); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <button onClick={() => updAction(gIdx, aIdx, 'warn_notify', !warnNotify)}
                                        className={`relative w-11 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${warnNotify ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                        <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${warnNotify ? 'left-[calc(100%-1.25rem)]' : 'left-1'}`}/>
                                      </button>
                                    </div>

                                    {/* На кого */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-black text-gray-800">
                                          На кого распространяется действие <span className="text-red-400">*</span>
                                        </p>
                                        {warnTarget !== 'initiator' && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === warnTgtGear ? null : warnTgtGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === warnTgtGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'warn_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                                <button onClick={() => { updAction(gIdx, aIdx, 'warn_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <Ban size={11} className="text-gray-400"/> Отключить настройку
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === warnTgtKey ? null : warnTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === warnTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curTgt.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === warnTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === warnTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {WARN_TARGETS.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'warn_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${warnTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Кол-во */}
                                    <div className="flex items-center justify-between gap-3">
                                      <p className="text-sm font-black text-gray-800">
                                        Кол-во <span className="text-red-400">*</span>
                                      </p>
                                      <input type="number" min="1" max="999"
                                        value={warnCount}
                                        onChange={e => updAction(gIdx, aIdx, 'warn_count', Math.max(1, parseInt(e.target.value)||1))}
                                        className="w-20 px-3 py-2 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm text-center outline-none focus:border-blue-300 transition-all"/>
                                    </div>

                                  </div>
                                );
                              })()}

                              {/* ── delete ── */}
                              {action.type === 'delete' && (() => {
                                const delTarget    = action.delete_target    || 'initiator';
                                const delDelay     = action.delete_delay     ?? 0;
                                const delDelayUnit = action.delete_delay_unit|| 'seconds';
                                const delTgtKey    = `delTgt_${gIdx}_${aIdx}`;
                                const delUnitKey   = `delUnit_${gIdx}_${aIdx}`;
                                const delGearKey   = `delGear_${gIdx}_${aIdx}`;
                                const isModified   = delTarget !== 'initiator';

                                const TARGET_OPTIONS = [
                                  { v:'both',      l:'Кому ответили и инициатор триггера' },
                                  { v:'initiator', l:'Инициатор триггера'                 },
                                  { v:'replied',   l:'Кому ответили'                      },
                                ];
                                const UNIT_OPTIONS = [
                                  { v:'seconds', l:'секунд' },
                                  { v:'minutes', l:'минут'  },
                                  { v:'hours',   l:'часов'  },
                                  { v:'days',    l:'дней'   },
                                ];
                                const curTarget = TARGET_OPTIONS.find(o => o.v === delTarget) || TARGET_OPTIONS[1];
                                const curUnit   = UNIT_OPTIONS.find(o => o.v === delDelayUnit) || UNIT_OPTIONS[0];

                                return (
                                  <div className="space-y-4">

                                    {/* На кого распространяется */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-black text-gray-800">
                                          На кого распространяется действие <span className="text-red-400">*</span>
                                        </p>
                                        {isModified && (
                                          <div className="relative">
                                            <button
                                              onClick={() => setActOpenDropdown(actOpenDropdown === delGearKey ? null : delGearKey)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === delGearKey && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-lg shadow-xl z-[500] overflow-hidden whitespace-nowrap">
                                                <button
                                                  onClick={() => { updAction(gIdx, aIdx, 'delete_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button
                                          onClick={() => setActOpenDropdown(actOpenDropdown === delTgtKey ? null : delTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === delTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curTarget.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === delTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === delTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {TARGET_OPTIONS.map(o => (
                                              <button key={o.v}
                                                onClick={() => { updAction(gIdx, aIdx, 'delete_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-3 py-2 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${delTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Задержка */}
                                    <div>
                                      <p className="text-sm font-black text-gray-800 mb-1.5">
                                        Задержка <span className="text-red-400">*</span>
                                      </p>
                                      <div className="flex gap-2">
                                        <input
                                          type="number" min="0"
                                          value={delDelay}
                                          onChange={e => updAction(gIdx, aIdx, 'delete_delay', Math.max(0, parseInt(e.target.value)||0))}
                                          className="flex-1 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                                        <div className="relative">
                                          <button
                                            onClick={() => setActOpenDropdown(actOpenDropdown === delUnitKey ? null : delUnitKey)}
                                            className={`flex items-center gap-2 px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all min-w-[110px] ${actOpenDropdown === delUnitKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                            <span className="flex-1">{curUnit.l}</span>
                                            <ChevronDown size={13} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === delUnitKey ? 'rotate-180' : ''}`}/>
                                          </button>
                                          {actOpenDropdown === delUnitKey && (
                                            <div className="absolute top-full right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden min-w-[100px]">
                                              {UNIT_OPTIONS.map(o => (
                                                <button key={o.v}
                                                  onClick={() => { updAction(gIdx, aIdx, 'delete_delay_unit', o.v); setActOpenDropdown(null); }}
                                                  className={`w-full px-3 py-1.5 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${delDelayUnit === o.v ? 'text-blue-600 bg-blue-50 font-black' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                  {o.l}
                                                </button>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    </div>

                                  </div>
                                );
                              })()}

                              {/* ── pin ── */}
                              {action.type === 'pin' && (() => {
                                const pinTimeEnabled = action.pin_time_enabled || false;
                                const pinTimeValue   = action.pin_time_value   ?? 10;
                                const pinTimeUnit    = action.pin_time_unit    || 'seconds';
                                const pinNotify      = action.pin_notify       || false;
                                const pinTarget      = action.pin_target       || '';
                                const pinUnitKey     = `pinUnit_${gIdx}_${aIdx}`;
                                const pinTgtKey      = `pinTgt_${gIdx}_${aIdx}`;
                                const pinNotifyGear  = `pinNotifyGear_${gIdx}_${aIdx}`;
                                const pinTgtGear     = `pinTgtGear_${gIdx}_${aIdx}`;
                                const pinTimeGear    = `pinTimeGear_${gIdx}_${aIdx}`;

                                const PIN_UNITS = [
                                  { v:'seconds', l:'секунд'  },
                                  { v:'minutes', l:'минут'   },
                                  { v:'hours',   l:'часов'   },
                                  { v:'days',    l:'дней'    },
                                  { v:'weeks',   l:'недель'  },
                                  { v:'months',  l:'месяцев' },
                                ];
                                const PIN_TARGETS = [
                                  { v:'initiator', l:'инициатора триггера' },
                                  { v:'replied',   l:'на которое ответили' },
                                ];
                                const curUnit   = PIN_UNITS.find(o => o.v === pinTimeUnit)   || PIN_UNITS[0];
                                const curTarget = PIN_TARGETS.find(o => o.v === pinTarget);

                                return (
                                  <div className="space-y-4">

                                    {/* Через какое время открепить */}
                                    <div>
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-1.5">
                                          <p className="text-sm font-medium text-gray-700">Через какое время открепить</p>
                                          {pinTimeEnabled && (
                                            <div className="relative">
                                              <button onClick={() => setActOpenDropdown(actOpenDropdown === pinTimeGear ? null : pinTimeGear)}
                                                className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                                <Settings size={14}/>
                                              </button>
                                              {actOpenDropdown === pinTimeGear && (
                                                <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                  <button onClick={() => { updAction(gIdx, aIdx, 'pin_time_enabled', false); updAction(gIdx, aIdx, 'pin_time_value', 10); updAction(gIdx, aIdx, 'pin_time_unit', 'seconds'); setActOpenDropdown(null); }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                    <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                  </button>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                        {pinTimeEnabled ? (
                                          <button onClick={() => updAction(gIdx, aIdx, 'pin_time_enabled', false)}
                                            className="p-1.5 border border-gray-200 rounded-lg text-gray-400 hover:text-red-500 hover:border-red-200 active:scale-90 transition-all">
                                            <Ban size={14}/>
                                          </button>
                                        ) : (
                                          <button onClick={() => updAction(gIdx, aIdx, 'pin_time_enabled', true)}
                                            className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-black text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-all active:scale-95">
                                            Включить
                                          </button>
                                        )}
                                      </div>
                                      {pinTimeEnabled && (
                                        <div className="flex gap-2 mt-2">
                                          <input type="number" min="1"
                                            value={pinTimeValue}
                                            onChange={e => updAction(gIdx, aIdx, 'pin_time_value', Math.max(1, parseInt(e.target.value)||1))}
                                            className="flex-1 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === pinUnitKey ? null : pinUnitKey)}
                                              className={`flex items-center gap-2 px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 min-w-[110px] hover:border-blue-300 transition-all ${actOpenDropdown === pinUnitKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                              <span className="flex-1">{curUnit.l}</span>
                                              <ChevronDown size={13} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === pinUnitKey ? 'rotate-180' : ''}`}/>
                                            </button>
                                            {actOpenDropdown === pinUnitKey && (
                                              <div className="absolute top-full right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden min-w-[100px]">
                                                {PIN_UNITS.map(o => (
                                                  <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'pin_time_unit', o.v); setActOpenDropdown(null); }}
                                                    className={`w-full px-3 py-1.5 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${pinTimeUnit === o.v ? 'text-blue-600 bg-blue-50 font-black' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                    {o.l}
                                                  </button>
                                                ))}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      )}
                                    </div>

                                    {/* Уведомить участников чата */}
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-1.5">
                                        <p className="text-sm font-medium text-gray-700">Уведомить участников чата</p>
                                        {pinNotify && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === pinNotifyGear ? null : pinNotifyGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === pinNotifyGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'pin_notify', false); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <button onClick={() => updAction(gIdx, aIdx, 'pin_notify', !pinNotify)}
                                        className={`relative w-11 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${pinNotify ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                        <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${pinNotify ? 'left-[calc(100%-1.25rem)]' : 'left-1'}`}/>
                                      </button>
                                    </div>

                                    {/* Закрепить сообщение */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-medium text-gray-700">Закрепить сообщение</p>
                                        {pinTarget && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === pinTgtGear ? null : pinTgtGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === pinTgtGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'pin_target', ''); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === pinTgtKey ? null : pinTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-600 hover:border-blue-300 transition-all ${actOpenDropdown === pinTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span className={curTarget ? 'text-gray-800' : 'text-gray-400'}>
                                            {curTarget ? curTarget.l : '-'}
                                          </span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === pinTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === pinTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {PIN_TARGETS.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'pin_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-3 py-2 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${pinTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                  </div>
                                );
                              })()}

                            </div>

                          </div>
                        );
                      })}

                      {/* Добавить действие в группу — всегда видна (в т.ч. когда список пуст) */}
                      <button
                        onClick={() => { setActPickerGroupIdx(gIdx); setActPickerSearch(''); setShowActPickerModal(true); }}
                        className="w-full py-2.5 border-2 border-dashed border-blue-200 rounded-xl text-blue-400 font-black text-[10px] uppercase flex items-center justify-center gap-1.5 hover:border-blue-400 hover:text-blue-500 transition-all bg-blue-50/30 active:scale-[0.98]">
                        <PlusCircle size={12}/> Добавить действие
                      </button>
                    </div>
                  </div>
                ))}

                {/* Добавить группу действий */}
                <button
                  onClick={addActionGroup}
                  className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-2xl text-gray-400 font-black text-[10px] uppercase flex items-center justify-center gap-1.5 hover:border-blue-200 hover:text-blue-400 transition-all bg-white active:scale-[0.98]">
                  <PlusCircle size={11}/> Добавить группу действий
                </button>
              </div>{/* конец правой колонки */}

              </div>{/* конец grid */}

              {/* ── МОДАЛ ВЫБОРА УСЛОВИЯ (full-screen overlay) ── */}
              {showCondPickerModal && (
                <div className="fixed inset-0 z-[200] flex flex-col" onClick={e => { if (e.target === e.currentTarget) setShowCondPickerModal(false); }}>
                  {/* Backdrop */}
                  <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowCondPickerModal(false)}/>
                  {/* Panel */}
                  <div className="relative mt-auto bg-white rounded-t-[2rem] max-h-[85vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">
                    {/* Drag handle */}
                    <div className="flex justify-center pt-3 pb-1">
                      <div className="w-10 h-1 bg-gray-200 rounded-full"/>
                    </div>
                    {/* Header */}
                    <div className="flex items-center justify-between px-6 py-3 border-b border-gray-100">
                      <h3 className="font-black text-base text-gray-900">Выберите условие</h3>
                      <button onClick={() => setShowCondPickerModal(false)} className="p-2 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                        <X size={18}/>
                      </button>
                    </div>
                    {/* Signal tabs */}
                    <div className="flex border-b border-gray-100">
                      {[{v:'message',l:'Сообщение'},{v:'quoted',l:'Цитируемое'}].map(tab => (
                        <button key={tab.v} onClick={() => setCondPickerTab(tab.v)}
                          className={`flex-1 py-3 text-[11px] font-black uppercase tracking-wide transition-all border-b-2 ${condPickerTab===tab.v ? 'text-blue-600 border-blue-500' : 'text-gray-400 border-transparent'}`}>
                          {tab.l}
                        </button>
                      ))}
                    </div>
                    {/* Info box */}
                    <div className="mx-4 mt-3 px-4 py-3 bg-blue-50 border border-blue-100 rounded-2xl text-[11px] text-blue-700 font-medium leading-relaxed">
                      {condPickerTab === 'message'
                        ? '📨 Триггер проверит входящее сообщение участника чата по выбранному условию.'
                        : '↩️ Триггер проверит сообщение, на которое ответил пользователь (цитируемое).'}
                    </div>
                    {/* Search */}
                    <div className="px-4 mt-3">
                      <div className="relative">
                        <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"/>
                        <input
                          type="text"
                          placeholder="Поиск условий..."
                          value={condPickerSearch}
                          onChange={e => setCondPickerSearch(e.target.value)}
                          className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-bold outline-none focus:border-blue-300 transition-all"/>
                      </div>
                    </div>
                    {/* Conditions list */}
                    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
                      {/* Секция: Условия по тексту */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">
                          Условия по {condPickerTab === 'message' ? 'сообщению' : 'цитируемому сообщению'}
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                          {/* Сообщение (any) */}
                          {(condPickerSearch === '' || 'сообщение любое'.includes(condPickerSearch.toLowerCase())) && (
                            <button
                              onClick={() => addConditionToGroup(condPickerGroupIdx, condPickerTab === 'message' ? 'message' : 'quoted')}
                              className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                              <span className="text-xl">📩</span>
                              <span className="text-[11px] font-black text-gray-800 leading-tight">
                                {condPickerTab === 'message' ? 'Сообщение' : 'Цитируемое'}
                              </span>
                              <span className="text-[9px] text-gray-400 font-medium leading-tight">Любое входящее сообщение</span>
                              {/* ⓘ tooltip */}
                              <button
                                onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `picker_any_${condPickerTab}` ? null : `picker_any_${condPickerTab}`); }}
                                className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 z-10">
                                ?
                              </button>
                              {condTooltip === `picker_any_${condPickerTab}` && (
                                <div className="absolute top-8 right-2 w-48 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl z-20 leading-relaxed">
                                  {condPickerTab === 'message' ? COND_TOOLTIP_TEXT['msg_any'] : COND_TOOLTIP_TEXT['qmsg_any']}
                                </div>
                              )}
                            </button>
                          )}
                          {/* Слово в сообщении */}
                          {(condPickerSearch === '' || 'слово ключевое keyword'.includes(condPickerSearch.toLowerCase())) && (
                            <button
                              onClick={() => addConditionToGroup(condPickerGroupIdx, condPickerTab === 'message' ? 'message' : 'quoted')}
                              className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                              <span className="text-xl">🔤</span>
                              <span className="text-[11px] font-black text-gray-800 leading-tight">Слово в сообщении</span>
                              <span className="text-[9px] text-gray-400 font-medium leading-tight">Реагирует на ключевые слова</span>
                              <button
                                onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `picker_kw_${condPickerTab}` ? null : `picker_kw_${condPickerTab}`); }}
                                className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 z-10">
                                ?
                              </button>
                              {condTooltip === `picker_kw_${condPickerTab}` && (
                                <div className="absolute top-8 right-2 w-48 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl z-20 leading-relaxed">
                                  {condPickerTab === 'message' ? COND_TOOLTIP_TEXT['msg_keyword'] : COND_TOOLTIP_TEXT['qmsg_keyword']}
                                </div>
                              )}
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Секция: Условия по параметрам */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">
                          Условия по параметрам сообщения
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { icon: '📎', label: 'Тип медиа', sub: 'Фото, видео, файл...' },
                            { icon: '👤', label: 'Автор', sub: 'ID или username' },
                            { icon: '💬', label: 'Длина текста', sub: 'Больше/меньше N символов' },
                            { icon: '🕐', label: 'Время отправки', sub: 'В заданный промежуток' },
                          ].map(item => (
                            <div key={item.label}
                              className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-dashed border-gray-200 rounded-2xl opacity-50 cursor-not-allowed">
                              <span className="text-xl">{item.icon}</span>
                              <span className="text-[11px] font-black text-gray-500 leading-tight">{item.label}</span>
                              <span className="text-[9px] text-gray-400 font-medium leading-tight">{item.sub}</span>
                              <span className="absolute top-2 right-2 text-[8px] font-black bg-gray-200 text-gray-400 px-1.5 py-0.5 rounded-full uppercase">***</span>
                              <div className="absolute top-2 right-8 w-4 h-4 rounded-full bg-gray-300 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── МОДАЛ НАСТРОЕК УСЛОВИЯ (ключ плейсхолдера) ── */}
              {condSettingsModal && (() => {
                const { gIdx, cIdx } = condSettingsModal;
                const cond = conditionGroups[gIdx]?.conditions[cIdx];
                if (!cond) return null;
                return (
                  <div className="fixed inset-0 z-[300] flex items-center justify-center px-4">
                    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setCondSettingsModal(null)}/>
                    <div className="relative bg-white rounded-3xl shadow-2xl w-full max-w-sm p-6 space-y-4 animate-in fade-in zoom-in-95 duration-200">
                      <div className="flex items-center justify-between">
                        <h3 className="font-black text-base text-gray-900">Дополнительные настройки условия</h3>
                        <button onClick={() => setCondSettingsModal(null)} className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                          <X size={16}/>
                        </button>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center gap-1.5">
                          <p className="text-sm font-black text-gray-700">Ключ плейсхолдера</p>
                          <div className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center">?</div>
                        </div>
                        <p className="text-red-400 text-[10px] font-bold">*</p>
                        <p className="text-[11px] text-gray-500 font-medium leading-relaxed">
                          Укажите ключ, который станет плейсхолдером и будет выводить в тексте условие сработки триггера.<br/>
                          <span className="text-gray-400">Пример: <span className="font-mono font-bold">words_list</span></span>
                        </p>
                        <p className="text-[11px] text-gray-500 font-medium leading-relaxed">
                          Поместите этот ключ между <span className="font-mono font-bold text-purple-600">%%</span> и добавьте его в текст действия «Отправить сообщение в чат».<br/>
                          <span className="text-gray-400">Пример: <span className="font-mono text-purple-600">%words_list%</span></span>
                        </p>
                        <input type="text"
                          value={cond.placeholder_key || ''}
                          onChange={e => updCond(gIdx, cIdx, 'placeholder_key', e.target.value)}
                          placeholder="words_list"
                          className="w-full px-4 py-3 bg-gray-50 border-2 border-gray-200 rounded-2xl font-mono font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                      </div>
                      <div className="flex gap-2 justify-end pt-1">
                        <button onClick={() => setCondSettingsModal(null)}
                          className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-xl font-black text-sm hover:bg-gray-200 active:scale-95 transition-all">
                          Отмена
                        </button>
                        <button onClick={() => setCondSettingsModal(null)}
                          className="px-5 py-2.5 bg-blue-500 text-white rounded-xl font-black text-sm shadow-md shadow-blue-100 hover:bg-blue-600 active:scale-95 transition-all">
                          Сохранить
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* ── МОДАЛ ВЫБОРА ДЕЙСТВИЯ (full-screen overlay) ── */}
              {showActPickerModal && (
                <div className="fixed inset-0 z-[200] flex flex-col">
                  <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowActPickerModal(false)}/>
                  <div className="relative mt-auto bg-white rounded-t-[2rem] max-h-[85vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">
                    <div className="flex justify-center pt-3 pb-1">
                      <div className="w-10 h-1 bg-gray-200 rounded-full"/>
                    </div>
                    <div className="flex items-start justify-between px-6 py-3 border-b border-gray-100">
                      <div>
                        <h3 className="font-black text-base text-gray-900">Выберите действия</h3>
                        <p className="text-[10px] text-gray-400 font-medium mt-0.5">Укажите реакцию бота на выполненное условие</p>
                      </div>
                      <button onClick={() => setShowActPickerModal(false)} className="p-2 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                        <X size={18}/>
                      </button>
                    </div>
                    <div className="px-4 mt-3">
                      <div className="relative">
                        <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"/>
                        <input type="text" placeholder="Поиск действий..." value={actPickerSearch}
                          onChange={e => setActPickerSearch(e.target.value)}
                          className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-bold outline-none focus:border-blue-300 transition-all"/>
                      </div>
                    </div>
                    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5">
                      {/* Секция 1: Действия с сообщениями */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Действия с сообщениями</p>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { type:'send_text', icon:'📤', label:'Отправить сообщение в чат', sub:'Ответить сообщением', active:true  },
                            { type:'delete',    icon:'🗑',  label:'Удалить сообщение', sub:'Удалить триггер-сообщение', active:true  },
                            { type:'dm',        icon:'✉️',  label:'Личное сообщение',  sub:'Написать пользователю в ЛС',active:true  },
                            { type:'pin',       icon:'📌',  label:'Закрепить',          sub:'Закрепить сообщение',      active:true  },
                            { type:'unpin',     icon:'📍',  label:'Открепить',          sub:'Открепить сообщение',      active:false },
                          ].filter(a => actPickerSearch === '' || a.label.toLowerCase().includes(actPickerSearch.toLowerCase())).map(a => (
                            a.active ? (
                              <button key={a.type} onClick={() => addActionToGroup(actPickerGroupIdx, a.type)}
                                className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-800 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </button>
                            ) : (
                              <div key={a.type} className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-dashed border-gray-200 rounded-2xl opacity-50 cursor-not-allowed">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-500 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <span className="absolute top-2 right-2 text-[8px] font-black bg-gray-200 text-gray-400 px-1.5 py-0.5 rounded-full uppercase">***</span>
                                <div className="absolute top-2 right-8 w-4 h-4 rounded-full bg-gray-300 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </div>
                            )
                          ))}
                        </div>
                      </div>
                      {/* Секция 2: Действия по пользователям */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Действия по пользователям</p>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { type:'mute',   icon:'🔇', label:'Запретить писать', sub:'Мут на время',        active:true  },
                            { type:'ban',    icon:'🚫', label:'Заблокировать',     sub:'Бан из чата',         active:true  },
                            { type:'kick',   icon:'👢', label:'Удалить из чата',   sub:'Кик с возможностью вернуться', active:false },
                            { type:'unmute', icon:'🔊', label:'Разрешить писать',  sub:'Снять мут',           active:false },
                            { type:'unban',  icon:'✅', label:'Разблокировать',    sub:'Снять бан',           active:false },
                          ].filter(a => actPickerSearch === '' || a.label.toLowerCase().includes(actPickerSearch.toLowerCase())).map(a => (
                            a.active ? (
                              <button key={a.type} onClick={() => addActionToGroup(actPickerGroupIdx, a.type)}
                                className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-800 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </button>
                            ) : (
                              <div key={a.type} className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-dashed border-gray-200 rounded-2xl opacity-50 cursor-not-allowed">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-500 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <span className="absolute top-2 right-2 text-[8px] font-black bg-gray-200 text-gray-400 px-1.5 py-0.5 rounded-full uppercase">***</span>
                                <div className="absolute top-2 right-8 w-4 h-4 rounded-full bg-gray-300 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </div>
                            )
                          ))}
                        </div>
                      </div>
                      {/* Секция 3: Прочее */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Прочее</p>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { type:'warn',  icon:'⚠️', label:'Предупреждение',   sub:'Варн с эскалацией',    active:true  },
                            { type:'emoji', icon:'😀', label:'Реакция эмодзи',    sub:'Поставить реакцию',    active:true  },
                            { type:'warn_add', icon:'✋', label:'Уровень наказания', sub:'Добавить варн',     active:false },
                            { type:'trigger_toggle', icon:'🔄', label:'Изменить триггер', sub:'Вкл/выкл другой', active:false },
                          ].filter(a => actPickerSearch === '' || a.label.toLowerCase().includes(actPickerSearch.toLowerCase())).map(a => (
                            a.active ? (
                              <button key={a.type} onClick={() => addActionToGroup(actPickerGroupIdx, a.type)}
                                className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-800 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </button>
                            ) : (
                              <div key={a.type} className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-dashed border-gray-200 rounded-2xl opacity-50 cursor-not-allowed">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-500 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <span className="absolute top-2 right-2 text-[8px] font-black bg-gray-200 text-gray-400 px-1.5 py-0.5 rounded-full uppercase">***</span>
                                <div className="absolute top-2 right-8 w-4 h-4 rounded-full bg-gray-300 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </div>
                            )
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── МОДАЛ КЛАВИАТУРЫ ── */}
              {showKeyboardModal && kbModalTarget && (() => {
                const { gIdx, aIdx } = kbModalTarget;
                const tgt = (editingTrigger.actionGroups||[])[gIdx]?.actions[aIdx];
                if (!tgt) return null;
                const keyboard = tgt.keyboard || [];
                const addKbButton = (btn) => {
                  updAction(gIdx, aIdx, 'keyboard', [...keyboard, { id: Date.now(), ...btn }]);
                  setKbButtonType(null);
                  setKbNewButton({});
                };
                const REACTION_PRESETS = [
                  { emoji: '🌍' }, { emoji: '👋' }, { emoji: '🔥' }, { emoji: '💡' },
                ];
                return (
                  <div className="fixed inset-0 z-[300] flex flex-col bg-white">

                    {/* ── Шапка ── */}
                    <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 flex-shrink-0">
                      <span className="text-[10px] font-black bg-blue-100 text-blue-600 px-2 py-0.5 rounded uppercase tracking-wide">Beta</span>
                      <button onClick={() => { setShowKeyboardModal(false); setKbButtonType(null); setKbNewButton({}); }}
                        className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                        <X size={20}/>
                      </button>
                    </div>

                    {/* ── Список добавленных кнопок ── */}
                    <div className="px-5 py-3 border-b border-gray-100 flex-shrink-0">
                      {keyboard.length === 0 ? (
                        <p className="text-sm font-bold text-gray-400 text-center py-1">Кнопки не выбраны</p>
                      ) : (
                        <div className="space-y-1.5">
                          {keyboard.map((btn, bi) => (
                            <div key={btn.id} className="flex items-center gap-2.5 px-3 py-2 bg-gray-50 rounded-xl border border-gray-100">
                              <span className="text-gray-300 font-black text-lg select-none leading-none">+</span>
                              <span className="text-base w-5 text-center leading-none">{btn.emoji || '○'}</span>
                              <span className="text-sm font-bold text-gray-500 flex-1 truncate">{btn.text || 'Текст кнопки'}</span>
                              <button onClick={() => updAction(gIdx, aIdx, 'keyboard', keyboard.filter((_,i)=>i!==bi))}
                                className="text-red-300 hover:text-red-500 text-xl leading-none flex-shrink-0">×</button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* ── Контент ── */}
                    <div className="flex-1 overflow-y-auto">
                      {kbButtonType === null ? (

                        /* Выбор типа кнопки */
                        <div className="px-5 py-5">
                          <p className="text-sm font-black text-gray-800 mb-4">Выберите тип кнопки</p>
                          <div className="grid grid-cols-3 gap-2">
                            <button
                              onClick={() => { setKbButtonType('trigger'); setKbNewButton({}); }}
                              className="px-4 py-4 border border-gray-200 rounded-xl text-sm font-bold text-gray-700 text-left hover:border-blue-300 hover:bg-blue-50 transition-all active:scale-[0.97]">
                              Вызов триггера
                            </button>
                            <button
                              onClick={() => { setKbButtonType('share'); setKbNewButton({}); }}
                              className="px-4 py-4 border border-gray-200 rounded-xl text-sm font-bold text-gray-700 text-left hover:border-blue-300 hover:bg-blue-50 transition-all active:scale-[0.97]">
                              Поделиться
                            </button>
                            {REACTION_PRESETS.map((r, ri) => (
                              <button key={ri}
                                onClick={() => {
                                  setKbButtonType('reaction');
                                  setKbReactionEmoji(r.emoji);
                                  setKbNewButton({ text: r.emoji, noMultiple: true, uniqueOnly: true });
                                }}
                                className="flex items-center gap-2 px-4 py-4 border border-gray-200 rounded-xl text-sm font-bold text-gray-700 text-left hover:border-blue-300 hover:bg-blue-50 transition-all active:scale-[0.97]">
                                <span className="text-lg">{r.emoji}</span>
                                <span>Реакция</span>
                              </button>
                            ))}
                            <button
                              onClick={() => { setKbButtonType('link'); setKbNewButton({}); }}
                              className="px-4 py-4 border border-gray-200 rounded-xl text-sm font-bold text-gray-700 text-left hover:border-blue-300 hover:bg-blue-50 transition-all active:scale-[0.97]">
                              Ссылка
                            </button>
                          </div>
                        </div>

                      ) : (

                        /* Подформа */
                        <div className="px-5 py-5 space-y-4">
                          {/* Назад + заголовок */}
                          <div className="flex items-center gap-2">
                            <button onClick={() => { setKbButtonType(null); setKbNewButton({}); }}
                              className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all text-lg font-bold leading-none">←</button>
                            {kbButtonType === 'reaction' && <span className="text-xl">{kbReactionEmoji}</span>}
                            <h3 className="text-base font-black text-gray-900">
                              {kbButtonType === 'trigger' ? 'Вызов триггера' :
                               kbButtonType === 'share'   ? 'Поделиться'    :
                               kbButtonType === 'reaction'? 'Реакция'       : 'Ссылка'}
                            </h3>
                          </div>

                          {/* Info box */}
                          <div className="px-4 py-3 bg-blue-50 border border-blue-100 rounded-2xl text-[12px] text-blue-700 font-medium leading-relaxed">
                            {kbButtonType === 'trigger' && <>
                              Кнопка при нажатии на которую запустится выбранный триггер.<br/><br/>
                              <span className="underline cursor-pointer">Пример</span>: сделайте триггер без условий с развёрнутыми правилами чата и поместите его в кнопку "Вызов триггера".
                            </>}
                            {kbButtonType === 'share' && <>
                              Здесь можно создать кнопку, при нажатии на которую у пользователя сразу откроется список его контактов и чатов для пересылки этого сообщения (поста).
                            </>}
                            {kbButtonType === 'reaction' && <>
                              Если вы отключили реакции на посты в канале, но мнение пользователей об определённой публикации или теме важно — помогут кнопки с реакциями. Можно вставить любые эмодзи вместо предложенных в поле "Текст кнопки".<br/><br/>
                              Задать уведомление, которое увидит пользователь после нажатия на кнопку, можно в поле "Сообщение пользователю".<br/><br/>
                              После того, как читатели нажмут на кнопку, рядом с эмодзи появится количество нажатий. Вот как это будет выглядеть с использованием текущего эмодзи: {kbReactionEmoji} - 3.
                            </>}
                            {kbButtonType === 'link' && <>
                              Кнопка-ссылка — при нажатии открывает указанный URL в браузере пользователя.
                            </>}
                          </div>

                          {/* Текст кнопки */}
                          <div>
                            <p className="text-sm font-black text-gray-700 mb-1.5">Текст кнопки <span className="text-red-400">*</span></p>
                            <input type="text" placeholder="Текст кнопки"
                              value={kbNewButton.text || ''}
                              onChange={e => setKbNewButton(p => ({...p, text: e.target.value}))}
                              className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                          </div>

                          {/* Триггер dropdown */}
                          {kbButtonType === 'trigger' && (
                            <div>
                              <p className="text-sm font-black text-gray-700 mb-0.5">Триггер <span className="text-red-400">*</span></p>
                              <p className="text-[11px] text-gray-400 font-medium mb-2">* Выбранный триггер будет вызван после нажатия на кнопку</p>
                              <div className="relative">
                                <button
                                  onClick={() => setKbNewButton(p => ({...p, _open: !p._open}))}
                                  className="w-full flex items-center justify-between px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm text-gray-700 hover:border-blue-300 transition-all">
                                  <span className={kbNewButton.trigger_id ? 'text-gray-800' : 'text-gray-400'}>
                                    {triggers.find(t => t.id === kbNewButton.trigger_id)?.name || ''}
                                  </span>
                                  <ChevronDown size={14} className={`text-gray-400 transition-transform ${kbNewButton._open ? 'rotate-180' : ''}`}/>
                                </button>
                                {kbNewButton._open && (
                                  <div className="absolute top-full left-0 right-0 z-10 bg-white border border-gray-200 rounded-xl shadow-xl mt-1 max-h-52 overflow-y-auto">
                                    {triggers.map(t => (
                                      <button key={t.id}
                                        onClick={() => setKbNewButton(p => ({...p, trigger_id: t.id, _open: false}))}
                                        className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${kbNewButton.trigger_id === t.id ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}>
                                        {t.name}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {/* URL */}
                          {kbButtonType === 'link' && (
                            <div>
                              <p className="text-sm font-black text-gray-700 mb-1.5">URL <span className="text-red-400">*</span></p>
                              <input type="url" placeholder="https://..."
                                value={kbNewButton.url || ''}
                                onChange={e => setKbNewButton(p => ({...p, url: e.target.value}))}
                                className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                            </div>
                          )}

                          {/* Реакция: сообщение + чекбоксы */}
                          {kbButtonType === 'reaction' && (<>
                            <div>
                              <p className="text-sm font-black text-gray-700 mb-1.5">Сообщение пользователю</p>
                              <div className="relative">
                                <textarea
                                  value={kbNewButton.user_msg || ''}
                                  onChange={e => setKbNewButton(p => ({...p, user_msg: e.target.value.slice(0,200)}))}
                                  rows={4}
                                  className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all resize-none"/>
                                <span className="absolute bottom-2 right-3 text-[10px] text-gray-400 font-bold">
                                  {(kbNewButton.user_msg||'').length} / 200
                                </span>
                              </div>
                            </div>
                            <div className="space-y-4">
                              <div className="flex items-start gap-3 cursor-pointer" onClick={() => setKbNewButton(p => ({...p, noMultiple: !p.noMultiple}))}>
                                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-all ${kbNewButton.noMultiple ? 'bg-blue-500 border-blue-500' : 'border-gray-300'}`}>
                                  {kbNewButton.noMultiple && <Check size={12} className="text-white"/>}
                                </div>
                                <div>
                                  <p className="text-sm font-bold text-gray-700">Запрет на выбор нескольких вариантов</p>
                                  <p className="text-[11px] text-gray-400 font-medium mt-0.5">* Активируйте данный параметр, чтобы запретить пользователю выбирать несколько вариантов реакции</p>
                                </div>
                              </div>
                              <div className="flex items-start gap-3 cursor-pointer" onClick={() => setKbNewButton(p => ({...p, uniqueOnly: !p.uniqueOnly}))}>
                                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-all ${kbNewButton.uniqueOnly ? 'bg-blue-500 border-blue-500' : 'border-gray-300'}`}>
                                  {kbNewButton.uniqueOnly && <Check size={12} className="text-white"/>}
                                </div>
                                <div>
                                  <p className="text-sm font-bold text-gray-700">Учитывать только уникальные нажатия</p>
                                  <p className="text-[11px] text-gray-400 font-medium mt-0.5">* При активации данного параметра будет зачтено только первое нажатие на кнопку от уникального пользователя. Если параметр выключен, то учитываться в счётчике будут все нажатия от одного и того же человека</p>
                                </div>
                              </div>
                            </div>
                          </>)}
                        </div>
                      )}
                    </div>

                    {/* ── Добавить кнопку ── */}
                    {kbButtonType !== null && (
                      <div className="px-5 py-4 border-t border-gray-100 flex-shrink-0">
                        <button
                          onClick={() => {
                            if (!kbNewButton.text) return;
                            addKbButton({
                              type: kbButtonType,
                              text: kbNewButton.text,
                              emoji: kbButtonType === 'reaction' ? kbReactionEmoji : undefined,
                              trigger_id: kbNewButton.trigger_id,
                              url: kbNewButton.url,
                              user_msg: kbNewButton.user_msg,
                              noMultiple: kbNewButton.noMultiple,
                              uniqueOnly: kbNewButton.uniqueOnly,
                            });
                          }}
                          className="w-full py-4 bg-blue-500 text-white font-black text-sm rounded-2xl shadow-md shadow-blue-100 hover:bg-blue-600 active:scale-[0.98] transition-all">
                          Добавить кнопку
                        </button>
                      </div>
                    )}

                  </div>
                );
              })()}

              {/* ── МОДАЛ ДОПОЛНИТЕЛЬНЫХ НАСТРОЕК ДЕЙСТВИЯ ── */}
              {actionSettingsModal && (() => {
                const { gIdx, aIdx } = actionSettingsModal;
                return (
                  <div className="fixed inset-0 z-[400] flex items-center justify-center px-4">
                    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setActionSettingsModal(null)}/>
                    <div className="relative bg-white rounded-3xl shadow-2xl w-full max-w-sm p-6 space-y-5 animate-in fade-in zoom-in-95 duration-200">
                      <div className="flex items-center justify-between">
                        <h3 className="font-black text-base text-gray-900">Дополнительные настройки действия</h3>
                        <button onClick={() => setActionSettingsModal(null)} className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                          <X size={16}/>
                        </button>
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5 mb-2">
                          <p className="text-sm font-black text-gray-800">Шанс выполнения действия <span className="text-red-400">*</span></p>
                        </div>
                        <input
                          type="number" min="1" max="100"
                          value={actionSettingsPct}
                          onChange={e => setActionSettingsPct(Math.min(100, Math.max(1, parseInt(e.target.value)||1)))}
                          className="w-full px-4 py-3 bg-gray-50 border-2 border-gray-200 rounded-2xl font-black text-sm text-right outline-none focus:border-blue-300 transition-all"
                          style={{appearance:'textfield'}}/>
                      </div>
                      <div className="flex gap-2 justify-end pt-1">
                        <button onClick={() => setActionSettingsModal(null)}
                          className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-xl font-black text-sm hover:bg-gray-200 active:scale-95 transition-all">
                          Отмена
                        </button>
                        <button onClick={() => { updAction(gIdx, aIdx, 'action_probability', actionSettingsPct); setActionSettingsModal(null); }}
                          className="px-5 py-2.5 bg-blue-500 text-white rounded-xl font-black text-sm shadow-md shadow-blue-100 hover:bg-blue-600 active:scale-95 transition-all">
                          Сохранить
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* ── ДЕЙСТВИЯ (старый блок — удалён, теперь в правой колонке) ── */}
              {false && <div className="mb-5 space-y-2">
                <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block px-1">Действия</span>
                {[].map((action, idx) => {
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
              </div>}

              {/* ── Дополнительно ── */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 space-y-4">
                <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Дополнительно</span>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">Где срабатывает</p>
                  <div className="flex gap-2">
                    {[{v:'all',l:'Везде'},{v:'chat',l:'Чат'},{v:'pv',l:'Личка'}].map(o => (
                      <button key={o.v} onClick={() => upd('where_fires',o.v)}
                        className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${editingTrigger.where_fires===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">На кого реагирует</p>
                  <div className="flex gap-2">
                    {[{v:'all',l:'Все'},{v:'users',l:'Юзеры'},{v:'admins',l:'Админы'}].map(o => (
                      <button key={o.v} onClick={() => upd('initiator',o.v)}
                        className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${editingTrigger.initiator===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
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


    </div>
  );
}
