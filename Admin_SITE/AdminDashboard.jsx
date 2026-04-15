import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts';
import { 
  Home, Users, Settings, Send, Power, Menu, X, Calendar, Heart, 
  ShieldAlert, ScrollText, PieChart, Trash2, PlusCircle, AlertOctagon, 
  CheckCircle2, Info, Edit, ShieldBan, Clock, MessageSquareX, 
  Zap, Bot, Sparkles, Wand2, Loader2, Download, FileSpreadsheet, 
  FileText, TrendingUp, TrendingDown, Activity, ChevronRight,
  Wallet, Ghost, MessageCircle, UserSearch, UserCheck,
  ChevronDown, ChevronUp, Globe, User, Image as ImageIcon, Video, Smile, Link2,
  Flame, HeartHandshake, Dices, Coins, ShieldCheck, UserMinus, Percent
} from 'lucide-react';

// === НАСТРОЙКИ GEMINI API ===
const apiKey = ""; 

export default function App() {
  const [activeTab, setActiveTab] = useState('statistics'); 
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [showDetailedIndices, setShowDetailedIndices] = useState(false);

  // ================= СОСТОЯНИЯ: ИИ =================
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [isAiLoading, setIsAiLoading] = useState(false);
  
  // ================= СОСТОЯНИЯ: ТРИГГЕРЫ =================
  const [isTriggerModalOpen, setIsTriggerModalOpen] = useState(false);
  const [editingTrigger, setEditingTrigger] = useState(null);
  const [triggerStep, setTriggerStep] = useState(1);
  const [triggers, setTriggers] = useState([]);
  const [triggersLoading, setTriggersLoading] = useState(false);

  const fetchTriggers = () => {
    setTriggersLoading(true);
    fetch('/api/triggers')
      .then(r => r.json())
      .then(data => { setTriggers(Array.isArray(data) ? data : []); setTriggersLoading(false); })
      .catch(() => setTriggersLoading(false));
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
    admins: ['@vitya_owner', '@alex_admin', '@pulse_mod'],
    blacklist: ['@spammer_1', '@bot_attacker']
  });

  // ================= СОСТОЯНИЯ: ЖУРНАЛ =================
  const logTags = [
    { id: 'all',     label: 'Все' },
    { id: 'trigger', label: 'Триггеры' },
    { id: 'mute',    label: 'Муты' },
    { id: 'ban',     label: 'Баны' },
    { id: 'warn',    label: 'Варны' },
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
  };

  const exportExcel = () => {
    window.open(`/api/stats/export?period=${statsPeriod}`, '_blank');
  };

  // ================= ФУНКЦИИ =================
  const openTriggerModal = (t = null) => {
    setEditingTrigger(t || {
      id: null, name: '', condition: 'any_word', keyword: '', probability: 100,
      action: 'send_text', duration: '0', from: 'all', where: 'chat', target: 'author',
      bot_msg_delete: 'no', bot_msg_delete_after: 60, reply_text: '', media_type: 'none', emoji: ''
    });
    setTriggerStep(1);
    setIsTriggerModalOpen(true);
  };

  const saveTrigger = () => {
    const body = {
      name:                 editingTrigger.name,
      condition:            editingTrigger.condition,
      keyword:              editingTrigger.keyword,
      probability:          editingTrigger.probability,
      where:                editingTrigger.where,
      from_who:             editingTrigger.from,
      action:               editingTrigger.action,
      duration:             editingTrigger.duration,
      reply_text:           editingTrigger.reply_text,
      media_type:           editingTrigger.media_type,
      bot_msg_delete:       editingTrigger.bot_msg_delete,
      bot_msg_delete_after: editingTrigger.bot_msg_delete_after,
    };
    const isEdit = !!editingTrigger.id;
    const url    = isEdit ? `/api/triggers/${editingTrigger.id}` : '/api/triggers';
    const method = isEdit ? 'PUT' : 'POST';
    fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(r => r.json())
      .then(() => { fetchTriggers(); setIsTriggerModalOpen(false); })
      .catch(() => setIsTriggerModalOpen(false));
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
            <div className={`bg-gradient-to-br from-indigo-700 via-blue-700 to-blue-500 rounded-[3rem] p-8 text-white shadow-xl relative overflow-hidden border border-white/10 transition-all duration-500 ${statsLoading ? 'opacity-60' : 'opacity-100'}`}>
              <div className="absolute -top-10 -right-10 opacity-10 scale-150 rotate-12"><Activity size={200} /></div>
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center space-x-2 bg-white/20 px-4 py-1.5 rounded-full backdrop-blur-md">
                    <Zap size={14} className="text-yellow-300 fill-yellow-300" />
                    <span className="text-[10px] font-black uppercase tracking-widest">Статус здоровья</span>
                  </div>
                  <span className="text-[10px] font-black bg-white/10 px-3 py-1 rounded-full uppercase">
                    {liveStats?.periodLabel || 'Сегодня'}
                  </span>
                </div>
                <div className="text-8xl font-black tracking-tighter leading-none">
                  {statsLoading ? <Loader2 size={48} className="animate-spin opacity-50" /> : (liveStats?.healthIndex ?? 84.5)}
                  {!statsLoading && <span className="text-2xl ml-1 opacity-50">%</span>}
                </div>
                <button onClick={() => setShowDetailedIndices(!showDetailedIndices)}
                  className="mt-8 w-full flex justify-between items-center text-[10px] font-black uppercase tracking-widest border-t border-white/10 pt-4">
                  <span>Детальные индексы</span>
                  {showDetailedIndices ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
                {showDetailedIndices && (
                  <div className="grid grid-cols-2 gap-x-8 gap-y-3 pt-4 animate-in slide-in-from-top-2 duration-300">
                    {['oksp','sdsp','cho','media','korp','kopyup'].map(k => (
                      <div key={k} className="flex justify-between border-b border-white/5 pb-1">
                        <span className="text-[9px] font-bold opacity-60 uppercase">{k}</span>
                        <span className="text-sm font-black">12.4</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

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
              <ResponsiveContainer width="100%" height={160}>
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

            {/* ── Банк + Курс ── */}
            <div className={`bg-gradient-to-r from-indigo-600 to-blue-600 p-6 rounded-[2rem] text-white shadow-xl transition-all duration-500 ${statsLoading ? 'opacity-40' : 'opacity-100'}`}>
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-[10px] font-black opacity-60 uppercase tracking-widest block mb-1 flex items-center gap-1">
                    <Wallet size={10} /> Баланс банка
                  </span>
                  <span className="text-3xl font-black tracking-tight">
                    {(liveStats?.bankBalance ?? 0).toLocaleString()} 💳
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-black opacity-60 uppercase tracking-widest block mb-1">Курс пульса</span>
                  <span className="text-3xl font-black">{liveStats?.pulseRate ?? '—'}</span>
                </div>
              </div>
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
                trigger: 'bg-orange-50 text-orange-600 border border-orange-200',
                mute:    'bg-yellow-50 text-yellow-700 border border-yellow-200',
                ban:     'bg-red-50 text-red-600 border border-red-200',
                warn:    'bg-amber-50 text-amber-600 border border-amber-200',
                join:    'bg-green-50 text-green-600 border border-green-200',
                leave:   'bg-gray-100 text-gray-500 border border-gray-200',
                unban:   'bg-blue-50 text-blue-600 border border-blue-200',
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
                         <span className="text-5xl font-black text-gray-900">{systemStats.pulseRate}</span>
                         <span className="text-gray-400 font-bold uppercase text-xs"> manual</span>
                      </div>
                   </div>
                   <button className="p-5 bg-blue-50 text-blue-600 rounded-3xl"><Edit size={24}/></button>
                </div>

                <div className="bg-indigo-600 p-8 rounded-[2.5rem] text-white shadow-xl">
                   <div className="flex justify-between items-start mb-6">
                      <div className="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center"><Coins size={24}/></div>
                      <span className="text-[10px] font-black uppercase opacity-60">Банк</span>
                   </div>
                   <div className="text-3xl font-black tracking-tight">{systemStats.bankBalance.toLocaleString()} 💳</div>
                </div>
             </div>

             <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100">
                <h3 className="font-black text-gray-900 text-sm uppercase flex items-center mb-6"><ShieldCheck className="mr-3 text-green-500"/> Админы</h3>
                <div className="space-y-2">
                   {systemStats.admins.map(adm => (
                     <div key={adm} className="flex justify-between items-center p-4 bg-gray-50 rounded-2xl font-bold text-sm">
                        <span>{adm}</span>
                        <button className="text-red-400 p-2"><UserMinus size={16}/></button>
                     </div>
                   ))}
                </div>
             </div>
          </div>
        );

      case 'triggers':
        return (
          <div className="space-y-4 pb-24">
            <button onClick={() => openTriggerModal()} className="w-full bg-gray-900 text-white p-6 rounded-[2rem] font-black flex items-center justify-center space-x-2">
              <PlusCircle size={20} /> <span>СОЗДАТЬ ТРИГГЕР</span>
            </button>
            {triggersLoading && (
              <div className="text-center py-8 text-gray-400 font-black text-sm">
                <Loader2 size={24} className="animate-spin mx-auto mb-2" /> Загрузка...
              </div>
            )}
            {!triggersLoading && triggers.length === 0 && (
              <div className="text-center py-12 text-gray-300 font-black text-sm uppercase tracking-widest">
                Триггеров пока нет
              </div>
            )}
            {triggers.map(t => (
              <div key={t.id} className="bg-white p-6 rounded-[2.5rem] border border-gray-100 shadow-sm space-y-4">
                <div className="flex justify-between items-start">
                  <h4 className="font-black text-2xl tracking-tighter text-gray-900">{t.name}</h4>
                  <div className="flex space-x-2">
                     <button onClick={() => openTriggerModal(t)} className="p-3 bg-blue-50 text-blue-600 rounded-2xl"><Edit size={20} /></button>
                     <button onClick={() => deleteTrigger(t.id)} className="p-3 bg-red-50 text-red-600 rounded-2xl"><Trash2 size={20} /></button>
                  </div>
                </div>
                <div className="bg-gray-50 p-4 rounded-3xl border border-gray-100 font-mono text-xs font-bold text-pink-600">
                  {t.keyword}
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
      <aside className={`fixed inset-y-0 left-0 z-50 w-[300px] bg-white border-r border-gray-100 flex flex-col transform transition-transform duration-500 lg:translate-x-0 lg:static ${isSidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'}`}>
        <div className="h-28 flex items-center justify-between px-8 border-b border-gray-50 bg-gray-50/20">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 bg-blue-600 rounded-[1.5rem] flex items-center justify-center shadow-2xl border-2 border-white">
              <Bot size={28} className="text-white" />
            </div>
            <div>
              <span className="block font-black text-2xl text-gray-900 leading-none tracking-tighter">Pulse Admin</span>
              <span className="text-[10px] font-bold text-blue-500 uppercase tracking-[0.3em] mt-1 block">Owner Console</span>
            </div>
          </div>
          <button onClick={() => setIsSidebarOpen(false)} className="lg:hidden p-3 bg-white rounded-2xl text-gray-400 border border-gray-50 active:scale-90 transition-all"><X size={24} /></button>
        </div>

        <nav className="flex-1 overflow-y-auto py-10 px-6 space-y-10">
          {['main', 'modules', 'features'].map(group => (
            <div key={group} className="space-y-2">
              <p className="px-5 text-[11px] font-black text-gray-300 uppercase tracking-[0.3em] mb-6">
                {group === 'main' ? 'Мониторинг' : group === 'modules' ? 'Модули' : 'Сервис'}
              </p>
              {navigation.filter(n => n.group === group).map((item) => (
                <button
                  key={item.id}
                  onClick={() => { setActiveTab(item.id); setIsSidebarOpen(false); }}
                  className={`w-full flex items-center px-6 py-5 rounded-[2.2rem] transition-all duration-300 ${
                    activeTab === item.id 
                    ? 'bg-gray-900 text-white shadow-2xl font-black scale-[1.03]' 
                    : 'text-gray-500 hover:bg-gray-50 active:bg-gray-100'
                  }`}
                >
                  <item.icon size={24} className={`mr-5 ${activeTab === item.id ? 'text-blue-400' : 'text-gray-400'}`} />
                  <span className="text-lg">{item.name}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <main className="flex-1 flex flex-col h-screen overflow-hidden bg-[#F8FAFC]">
        <header className="h-24 bg-white border-b border-gray-100 flex items-center justify-between px-6 sm:px-10 z-10 shrink-0">
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

        <div className="flex-1 overflow-y-auto p-4 sm:p-10 bg-gray-50/10 custom-scrollbar">
          <div className="max-w-xl mx-auto">{renderContent()}</div>
        </div>
      </main>

      {/* WIZARD ТРИГГЕРА — 4 ШАГА */}
      {isTriggerModalOpen && editingTrigger && (() => {
        const upd = (field, val) => setEditingTrigger(prev => ({...prev, [field]: val}));

        const STEPS = [
          { num: 1, title: 'Что ловим?',  sub: 'Условие срабатывания' },
          { num: 2, title: 'Кто и где?',  sub: 'Фильтр аудитории'     },
          { num: 3, title: 'Что делать?', sub: 'Действие бота'         },
          { num: 4, title: 'Итог',        sub: 'Проверь и сохрани'     },
        ];

        const TileBtn = ({ active, onClick, icon: Icon, label, color = 'gray' }) => {
          const colors = {
            gray:   active ? 'bg-gray-900 border-gray-900 text-white' : 'bg-white border-gray-100 text-gray-500',
            blue:   active ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-gray-100 text-gray-500',
            red:    active ? 'bg-red-500 border-red-500 text-white'   : 'bg-white border-gray-100 text-gray-500',
            amber:  active ? 'bg-amber-500 border-amber-500 text-white' : 'bg-white border-gray-100 text-gray-500',
            orange: active ? 'bg-orange-500 border-orange-500 text-white' : 'bg-white border-gray-100 text-gray-500',
            green:  active ? 'bg-green-500 border-green-500 text-white' : 'bg-white border-gray-100 text-gray-500',
          };
          return (
            <button onClick={onClick} className={`flex flex-col items-center justify-center gap-2 p-4 rounded-[1.8rem] border-2 transition-all active:scale-95 ${colors[color]}`}>
              <Icon size={22} />
              <span className="text-[10px] font-black uppercase tracking-wide leading-none">{label}</span>
            </button>
          );
        };

        const PreviewRow = ({ label, value }) => (
          <div className="flex justify-between items-center py-3 border-b border-gray-50 last:border-0">
            <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">{label}</span>
            <span className="text-sm font-black text-gray-900 max-w-[55%] text-right">{value || '—'}</span>
          </div>
        );

        const actionMap = { send_text: '💬 Текст', delete: '🗑 Удалить', mute: '🔇 Мут', ban: '🚫 Бан', warn: '⚠️ Варн' };
        const condMap   = { any_word: 'Слова', exact_match: 'Точно', regex: 'RegEx' };
        const whereMap  = { chat: 'Чат', pv: 'Личка', global: 'Везде' };
        const fromMap   = { all: 'Все', users: 'Юзеры', admins: 'Админы' };
        const delMap    = { no: 'Нет', previous: 'Предыдущее', period: `Таймер ${editingTrigger.bot_msg_delete_after}с` };

        return (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-[100] flex items-end sm:items-center justify-center">
            <div className="bg-white w-full sm:max-w-lg rounded-t-[3.5rem] sm:rounded-[3rem] flex flex-col max-h-[92vh] shadow-2xl animate-in slide-in-from-bottom-full duration-500">

              {/* Drag handle */}
              <div className="w-16 h-1.5 bg-gray-200 rounded-full mx-auto mt-4 mb-2 shrink-0" />

              {/* Header: progress + title */}
              <div className="px-8 pt-2 pb-5 shrink-0 border-b border-gray-50">
                {/* Progress */}
                <div className="flex items-center mb-5">
                  {STEPS.map((s, i) => (
                    <React.Fragment key={s.num}>
                      <button onClick={() => s.num < triggerStep && setTriggerStep(s.num)}
                        className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-black shrink-0 transition-all ${
                          s.num < triggerStep  ? 'bg-green-500 text-white cursor-pointer' :
                          s.num === triggerStep ? 'bg-gray-900 text-white scale-110 shadow-lg' :
                                                  'bg-gray-100 text-gray-400'
                        }`}>
                        {s.num < triggerStep ? '✓' : s.num}
                      </button>
                      {i < STEPS.length - 1 && (
                        <div className={`flex-1 h-0.5 mx-1.5 rounded-full transition-all ${s.num < triggerStep ? 'bg-green-400' : 'bg-gray-100'}`} />
                      )}
                    </React.Fragment>
                  ))}
                </div>
                {/* Title */}
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-black text-2xl tracking-tighter leading-none">{STEPS[triggerStep-1].title}</h3>
                    <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mt-1">{STEPS[triggerStep-1].sub}</p>
                  </div>
                  <button onClick={() => setIsTriggerModalOpen(false)} className="p-2.5 bg-gray-100 rounded-2xl text-gray-400 active:scale-90 transition-all"><X size={20} /></button>
                </div>
              </div>

              {/* Step content */}
              <div className="flex-1 overflow-y-auto px-8 py-6 space-y-5">

                {/* ── ШАГ 1: УСЛОВИЕ ── */}
                {triggerStep === 1 && (
                  <>
                    <input type="text" placeholder="Название триггера..." value={editingTrigger.name}
                      onChange={e => upd('name', e.target.value)}
                      className="w-full p-5 bg-gray-50 border-2 border-gray-100 rounded-[2rem] font-black text-lg outline-none focus:border-gray-300 transition-all" />

                    <div>
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Тип поиска</p>
                      <div className="grid grid-cols-3 gap-2">
                        <TileBtn active={editingTrigger.condition==='any_word'}   onClick={()=>upd('condition','any_word')}   icon={MessageCircle} label="Слова"  color="gray"/>
                        <TileBtn active={editingTrigger.condition==='exact_match'} onClick={()=>upd('condition','exact_match')} icon={CheckCircle2}   label="Точно"  color="gray"/>
                        <TileBtn active={editingTrigger.condition==='regex'}       onClick={()=>upd('condition','regex')}       icon={Globe}          label="RegEx"  color="gray"/>
                      </div>
                    </div>

                    <div>
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Ключевые слова / паттерн</p>
                      <textarea placeholder={editingTrigger.condition === 'regex' ? 'Например: t\\.me\\/|http' : 'Через пробел или запятую...'}
                        value={editingTrigger.keyword} onChange={e => upd('keyword', e.target.value)}
                        className="w-full p-5 bg-gray-50 border-2 border-gray-100 rounded-[2rem] font-mono text-sm font-bold outline-none focus:border-gray-300 resize-none transition-all" rows="2" />
                    </div>

                    <div className="bg-amber-50 p-5 rounded-[2rem] border-2 border-amber-100">
                      <div className="flex items-center justify-between mb-3">
                        <p className="text-[10px] font-black text-amber-700 uppercase tracking-widest flex items-center gap-1"><Percent size={12}/> Вероятность срабатывания</p>
                        <span className="text-xl font-black text-amber-800">{editingTrigger.probability}%</span>
                      </div>
                      <input type="range" min="1" max="100" value={editingTrigger.probability}
                        onChange={e => upd('probability', parseInt(e.target.value))}
                        className="w-full h-2 bg-amber-200 rounded-full appearance-none cursor-pointer accent-amber-600" />
                      <div className="flex justify-between mt-1">
                        <span className="text-[9px] text-amber-400 font-black">1%</span>
                        <span className="text-[9px] text-amber-400 font-black">50%</span>
                        <span className="text-[9px] text-amber-400 font-black">100%</span>
                      </div>
                    </div>
                  </>
                )}

                {/* ── ШАГ 2: КТО И ГДЕ ── */}
                {triggerStep === 2 && (
                  <>
                    <div>
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Где срабатывает</p>
                      <div className="grid grid-cols-3 gap-2">
                        <TileBtn active={editingTrigger.where==='chat'}   onClick={()=>upd('where','chat')}   icon={MessageSquareX} label="Чат"   color="blue"/>
                        <TileBtn active={editingTrigger.where==='pv'}     onClick={()=>upd('where','pv')}     icon={User}           label="Личка" color="blue"/>
                        <TileBtn active={editingTrigger.where==='global'} onClick={()=>upd('where','global')} icon={Globe}          label="Везде" color="blue"/>
                      </div>
                    </div>

                    <div>
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">На кого реагирует</p>
                      <div className="grid grid-cols-3 gap-2">
                        <TileBtn active={editingTrigger.from==='all'}    onClick={()=>upd('from','all')}    icon={Users}      label="Все"    color="green"/>
                        <TileBtn active={editingTrigger.from==='users'}  onClick={()=>upd('from','users')}  icon={UserCheck}  label="Юзеры" color="green"/>
                        <TileBtn active={editingTrigger.from==='admins'} onClick={()=>upd('from','admins')} icon={ShieldCheck} label="Админы" color="green"/>
                      </div>
                    </div>
                  </>
                )}

                {/* ── ШАГ 3: ДЕЙСТВИЕ ── */}
                {triggerStep === 3 && (
                  <>
                    <div>
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Действие бота</p>
                      <div className="grid grid-cols-2 gap-2">
                        <TileBtn active={editingTrigger.action==='send_text'} onClick={()=>upd('action','send_text')} icon={MessageCircle} label="Текст"    color="blue"/>
                        <TileBtn active={editingTrigger.action==='delete'}    onClick={()=>upd('action','delete')}    icon={Trash2}        label="Удалить"  color="gray"/>
                        <TileBtn active={editingTrigger.action==='mute'}      onClick={()=>upd('action','mute')}      icon={Clock}         label="Мут"      color="amber"/>
                        <TileBtn active={editingTrigger.action==='ban'}       onClick={()=>upd('action','ban')}       icon={ShieldBan}     label="Бан"      color="red"/>
                      </div>
                      <div className="mt-2">
                        <TileBtn active={editingTrigger.action==='warn'} onClick={()=>upd('action','warn')} icon={AlertOctagon} label="Предупреждение (Варн)" color="orange"/>
                      </div>
                    </div>

                    {['mute','ban'].includes(editingTrigger.action) && (
                      <div>
                        <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-2">Длительность</p>
                        <input type="text" placeholder="Напр: 2h / 30m / forever"
                          value={editingTrigger.duration} onChange={e => upd('duration', e.target.value)}
                          className="w-full p-5 bg-gray-50 border-2 border-gray-100 rounded-[2rem] font-black text-center outline-none focus:border-gray-300 transition-all" />
                      </div>
                    )}

                    {editingTrigger.action === 'send_text' && (
                      <div>
                        <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-2">Тип медиа</p>
                        <div className="grid grid-cols-4 gap-2">
                          <TileBtn active={editingTrigger.media_type==='none'}      onClick={()=>upd('media_type','none')}      icon={MessageCircle} label="Нет"  color="gray"/>
                          <TileBtn active={editingTrigger.media_type==='photo'}     onClick={()=>upd('media_type','photo')}     icon={ImageIcon}     label="Фото" color="gray"/>
                          <TileBtn active={editingTrigger.media_type==='video'}     onClick={()=>upd('media_type','video')}     icon={Video}         label="Видео" color="gray"/>
                          <TileBtn active={editingTrigger.media_type==='animation'} onClick={()=>upd('media_type','animation')} icon={Smile}         label="GIF"  color="gray"/>
                        </div>
                      </div>
                    )}

                    <div>
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-2">Текст ответа бота</p>
                      <textarea placeholder="Что напишет бот в ответ..." value={editingTrigger.reply_text}
                        onChange={e => upd('reply_text', e.target.value)}
                        className="w-full p-5 bg-gray-50 border-2 border-gray-100 rounded-[2rem] font-bold text-sm outline-none focus:border-gray-300 resize-none transition-all" rows="3" />
                    </div>

                    <div className="bg-gray-50 p-5 rounded-[2rem] border-2 border-gray-100">
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Удаление ответа бота</p>
                      <div className="grid grid-cols-3 gap-2">
                        <TileBtn active={editingTrigger.bot_msg_delete==='no'}       onClick={()=>upd('bot_msg_delete','no')}       icon={X}     label="Нет"    color="gray"/>
                        <TileBtn active={editingTrigger.bot_msg_delete==='previous'} onClick={()=>upd('bot_msg_delete','previous')} icon={Trash2} label="Пред."  color="gray"/>
                        <TileBtn active={editingTrigger.bot_msg_delete==='period'}   onClick={()=>upd('bot_msg_delete','period')}   icon={Clock}  label="Таймер" color="gray"/>
                      </div>
                      {editingTrigger.bot_msg_delete === 'period' && (
                        <input type="number" placeholder="Секунд до удаления" value={editingTrigger.bot_msg_delete_after}
                          onChange={e => upd('bot_msg_delete_after', parseInt(e.target.value))}
                          className="w-full mt-3 p-4 bg-white border-2 border-gray-200 rounded-2xl font-black text-center outline-none" />
                      )}
                    </div>
                  </>
                )}

                {/* ── ШАГ 4: ИТОГ ── */}
                {triggerStep === 4 && (
                  <>
                    <div className="bg-gradient-to-br from-gray-900 to-gray-800 p-6 rounded-[2.5rem] text-white">
                      <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 bg-blue-500 rounded-2xl flex items-center justify-center"><ShieldAlert size={20}/></div>
                        <div>
                          <p className="font-black text-xl leading-none">{editingTrigger.name || 'Без названия'}</p>
                          <p className="text-[10px] text-gray-400 uppercase font-black mt-0.5">{condMap[editingTrigger.condition]}</p>
                        </div>
                      </div>
                      {editingTrigger.keyword && (
                        <div className="mt-3 bg-white/10 rounded-2xl px-4 py-2 font-mono text-xs text-blue-300 font-bold">{editingTrigger.keyword}</div>
                      )}
                    </div>

                    <div className="bg-white rounded-[2.5rem] border-2 border-gray-100 px-6 py-2 divide-y divide-gray-50">
                      <PreviewRow label="Вероятность"  value={`${editingTrigger.probability}%`} />
                      <PreviewRow label="Где"          value={whereMap[editingTrigger.where]} />
                      <PreviewRow label="Кто"          value={fromMap[editingTrigger.from]} />
                      <PreviewRow label="Действие"     value={actionMap[editingTrigger.action]} />
                      {['mute','ban'].includes(editingTrigger.action) && (
                        <PreviewRow label="Длительность" value={editingTrigger.duration} />
                      )}
                      <PreviewRow label="Ответ бота"   value={editingTrigger.reply_text} />
                      <PreviewRow label="Удал. ответа" value={delMap[editingTrigger.bot_msg_delete]} />
                    </div>

                    <button onClick={() => { setTriggerStep(1); }} className="w-full py-4 bg-gray-50 border-2 border-gray-100 text-gray-500 rounded-[2rem] font-black text-sm active:scale-95 transition-all">
                      ✏️ Редактировать с шага 1
                    </button>
                  </>
                )}
              </div>

              {/* Footer navigation */}
              <div className="px-8 py-6 border-t border-gray-50 bg-white shrink-0 rounded-t-[2.5rem] shadow-xl">
                <div className="flex gap-3">
                  {triggerStep > 1 ? (
                    <button onClick={() => setTriggerStep(s => s - 1)}
                      className="flex-1 py-5 bg-gray-100 text-gray-700 rounded-[2rem] font-black active:scale-95 transition-all">
                      ← Назад
                    </button>
                  ) : (
                    <button onClick={() => setIsTriggerModalOpen(false)}
                      className="flex-1 py-5 bg-gray-100 text-gray-500 rounded-[2rem] font-black active:scale-95 transition-all">
                      Отмена
                    </button>
                  )}
                  {triggerStep < 4 ? (
                    <button onClick={() => setTriggerStep(s => s + 1)}
                      className="flex-2 flex-grow-[2] py-5 bg-gray-900 text-white rounded-[2rem] font-black active:scale-95 transition-all">
                      Далее →
                    </button>
                  ) : (
                    <button onClick={saveTrigger}
                      className="flex-2 flex-grow-[2] py-5 bg-blue-600 text-white rounded-[2rem] font-black text-lg shadow-xl shadow-blue-200 active:scale-95 transition-all">
                      СОХРАНИТЬ
                    </button>
                  )}
                </div>
              </div>

            </div>
          </div>
        );
      })()}

      {/* ИИ МОДАЛКА */}
      {isAiModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-[110] flex items-end justify-center">
           <div className="bg-white w-full rounded-t-[4rem] shadow-2xl flex flex-col animate-in slide-in-from-bottom-full duration-500 max-h-[85vh]">
              <div className="w-12 h-1.5 bg-gray-200 rounded-full mx-auto my-6 shrink-0 shadow-inner"></div>
              <div className="px-10 py-6 border-b border-gray-50 flex justify-between items-center bg-purple-50/50">
                 <h3 className="font-black text-3xl text-purple-950 flex items-center leading-none tracking-tighter">
                   <Sparkles className="mr-4 text-purple-600" size={36} /> ИИ-Мастер
                 </h3>
                 <button onClick={() => setIsAiModalOpen(false)} className="p-4 bg-white rounded-full text-gray-400 border border-gray-50 active:scale-90 transition-all"><X size={28} /></button>
              </div>
              <div className="p-10 space-y-8 overflow-y-auto pb-20">
                 <textarea rows="5" value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)} placeholder="Опиши задачу..." className="w-full bg-gray-50 border-4 border-purple-50 rounded-[3rem] p-8 text-xl font-bold focus:ring-8 focus:ring-purple-500/5 outline-none transition-all resize-none shadow-inner" />
                 <button onClick={handleAiTrigger} disabled={isAiLoading || !aiPrompt.trim()} className="w-full py-8 bg-gray-950 text-white font-black rounded-[3rem] text-2xl shadow-2xl active:scale-[0.97] transition-all flex items-center justify-center space-x-4 disabled:bg-gray-400">
                    {isAiLoading ? <Loader2 size={28} className="animate-spin" /> : <><Zap size={28} className="text-yellow-400 fill-yellow-400" /><span>СОЗДАТЬ</span></>}
                 </button>
              </div>
           </div>
        </div>
      )}
    </div>
  );
}