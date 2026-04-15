import React, { useState, useMemo } from 'react';
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
  const [triggers, setTriggers] = useState([
    { 
      id: 1, name: 'Анти-Реклама', condition: 'regex', keyword: 't.me/|http', 
      probability: 100, action: 'ban', duration: 'forever', 
      from: 'users', where: 'chat', target: 'author',
      bot_msg_delete: 'previous', reply_text: 'Реклама запрещена!' 
    }
  ]);

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
  const [logFilter, setLogFilter] = useState('all');
  const [logs] = useState([
    { id: 1, time: '19:45', tag: '#Триггер', user: '@vitya_owner', userId: 1, text: 'Сработал триггер "Анти-Реклама".', type: 'trigger' },
    { id: 2, time: '19:30', tag: '#Шиппер', user: 'Система', userId: 0, text: 'Запущена рулетка пар. Категория: 18+.', type: 'shipper' },
    { id: 3, time: '19:15', tag: '#Мут', user: '@spammer', userId: 12345, text: 'Выдан мут на 24ч: Оскорбления.', type: 'mute' },
  ]);
  
  // ================= СОСТОЯНИЯ: СТАТИСТИКА =================
  const historyData = [
    { day: 'Пн', val: 65 }, { day: 'Вт', val: 72 }, { day: 'Ср', val: 68 },
    { day: 'Чт', val: 85 }, { day: 'Пт', val: 78 }, { day: 'Сб', val: 92 }, { day: 'Вс', val: 84 },
  ];

  // ================= ФУНКЦИИ =================
  const openTriggerModal = (t = null) => {
    setEditingTrigger(t || { 
      id: null, name: '', condition: 'any_word', keyword: '', probability: 100, 
      action: 'send_text', duration: '0', from: 'all', where: 'chat', target: 'author',
      bot_msg_delete: 'no', bot_msg_delete_after: 60, reply_text: '', media_type: 'none', emoji: ''
    });
    setIsTriggerModalOpen(true);
  };

  const saveTrigger = () => {
    if (editingTrigger.id) {
      setTriggers(triggers.map(t => t.id === editingTrigger.id ? editingTrigger : t));
    } else {
      setTriggers([...triggers, { ...editingTrigger, id: Date.now() }]);
    }
    setIsTriggerModalOpen(false);
  };

  const TrendChart = () => {
    const points = historyData.map((d, i) => `${(i * 50) + 20},${150 - (d.val * 1.2)}`).join(' ');
    return (
      <div className="w-full bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm relative overflow-hidden">
        <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-6 flex items-center">
          <Activity size={14} className="mr-2 text-blue-500" /> Пульс активности чата
        </h3>
        <div className="relative h-32 w-full">
          <svg className="w-full h-full" viewBox="0 0 350 150" preserveAspectRatio="none">
            <path d={`M 20,150 L ${points} L 320,150 Z`} fill="url(#grad)" className="opacity-10" />
            <polyline fill="none" stroke="#3b82f6" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" points={points} className="drop-shadow-md" />
            <defs><linearGradient id="grad" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stopColor="#3b82f6" /><stop offset="100%" stopColor="#fff" /></linearGradient></defs>
          </svg>
        </div>
        <div className="flex justify-between px-2 mt-4">
          {historyData.map((d, i) => <span key={i} className="text-[10px] font-black text-gray-300 uppercase">{d.day}</span>)}
        </div>
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
          <div className="space-y-4 pb-24 animate-in fade-in duration-500">
            <div className="bg-gradient-to-br from-indigo-700 via-blue-700 to-blue-500 rounded-[3rem] p-8 text-white shadow-xl relative overflow-hidden border border-white/10 active:scale-[0.98] transition-all">
               <div className="absolute -top-10 -right-10 opacity-10 scale-150 rotate-12"><Activity size={200} /></div>
               <div className="relative z-10">
                 <div className="flex items-center space-x-2 mb-6 bg-white/20 w-fit px-4 py-1.5 rounded-full backdrop-blur-md">
                   <Zap size={14} className="text-yellow-300 fill-yellow-300" />
                   <span className="text-[10px] font-black uppercase tracking-widest text-white">Статус здоровья</span>
                 </div>
                 <div className="text-8xl font-black tracking-tighter leading-none">84.5<span className="text-2xl ml-1 opacity-50">%</span></div>
                 
                 <button onClick={() => setShowDetailedIndices(!showDetailedIndices)} className="mt-8 w-full flex justify-between items-center text-[10px] font-black uppercase tracking-widest border-t border-white/10 pt-4">
                   <span>Детальные индексы</span>
                   {showDetailedIndices ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                 </button>
                 {showDetailedIndices && (
                    <div className="grid grid-cols-2 gap-x-8 gap-y-3 pt-4 animate-in slide-in-from-top-2">
                       {['oksp', 'sdsp', 'cho', 'media', 'korp', 'kopyup'].map(k => (
                         <div key={k} className="flex justify-between border-b border-white/5 pb-1">
                           <span className="text-[9px] font-bold opacity-60 uppercase">{k}</span>
                           <span className="text-sm font-black">12.4</span>
                         </div>
                       ))}
                    </div>
                 )}
               </div>
            </div>
            
            <TrendChart />

            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'Сообщения', val: '3,120', color: 'text-blue-500', icon: MessageSquareX },
                { label: 'Юзеры', val: '485', color: 'text-indigo-500', icon: Users },
                { label: 'Входы', val: '+32', color: 'text-green-500', icon: TrendingUp },
                { label: 'Выходы', val: '-8', color: 'text-red-500', icon: TrendingDown },
              ].map((m, i) => (
                <div key={i} className="bg-white p-6 rounded-[2rem] border border-gray-100 shadow-sm active:scale-95 transition-all">
                  <div className="flex items-center space-x-2 mb-2">
                    <m.icon size={16} className={m.color} />
                    <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">{m.label}</span>
                  </div>
                  <span className="text-3xl font-black text-gray-900 leading-none">{m.val}</span>
                </div>
              ))}
            </div>
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
            {logs.filter(l => logFilter === 'all' || l.tag === logFilter).map(log => (
              <div key={log.id} className="bg-white p-6 rounded-[2.5rem] border border-gray-100 shadow-sm space-y-4 animate-in slide-in-from-bottom-2">
                <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest">
                  <span className="bg-blue-50 text-blue-600 px-3 py-1 rounded-full">{log.tag}</span>
                  <span className="text-gray-300 font-mono">{log.time}</span>
                </div>
                <div className="text-sm font-bold text-gray-700 leading-relaxed"><span className="text-blue-600 font-black">{log.user}:</span> {log.text}</div>
                <div className="grid grid-cols-1 gap-2 pt-2">
                  <a href={`tg://user?id=${log.userId}`} className="flex items-center justify-center space-x-2 bg-blue-600 text-white py-4 rounded-3xl font-black text-[10px] uppercase shadow-lg shadow-blue-200 active:scale-[0.98] transition-all"><MessageCircle size={16}/><span>ЛС</span></a>
                  <div className="grid grid-cols-2 gap-2">
                     {log.type === 'mute' && <button className="flex items-center justify-center space-x-2 bg-green-50 text-green-700 py-3 rounded-2xl font-black text-[9px] uppercase border border-green-200"><UserCheck size={14}/><span>Размутить</span></button>}
                     {log.type === 'trigger' && <button className="flex items-center justify-center space-x-2 bg-orange-50 text-orange-700 py-3 rounded-2xl font-black text-[9px] uppercase border border-orange-200"><Zap size={14}/><span>Амнистия</span></button>}
                     {log.type === 'join' && <button className="flex items-center justify-center space-x-2 bg-indigo-50 text-indigo-700 py-3 rounded-2xl font-black text-[9px] uppercase border border-indigo-200"><UserSearch size={14}/><span>Досье</span></button>}
                  </div>
                </div>
              </div>
            ))}
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
            {triggers.map(t => (
              <div key={t.id} className="bg-white p-6 rounded-[2.5rem] border border-gray-100 shadow-sm space-y-4">
                <div className="flex justify-between items-start">
                  <h4 className="font-black text-2xl tracking-tighter text-gray-900">{t.name}</h4>
                  <div className="flex space-x-2">
                     <button onClick={() => openTriggerModal(t)} className="p-3 bg-blue-50 text-blue-600 rounded-2xl"><Edit size={20} /></button>
                     <button className="p-3 bg-red-50 text-red-600 rounded-2xl"><Trash2 size={20} /></button>
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

      {/* МОДАЛКА ТРИГГЕРА */}
      {isTriggerModalOpen && editingTrigger && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-[100] flex items-end sm:items-center justify-center">
          <div className="bg-white w-full sm:max-w-lg rounded-t-[3.5rem] sm:rounded-[3rem] flex flex-col max-h-[92vh] shadow-2xl animate-in slide-in-from-bottom-full duration-500">
            <div className="w-16 h-1.5 bg-gray-200 rounded-full mx-auto my-4 shrink-0 shadow-inner"></div>
            
            <div className="px-10 py-4 border-b border-gray-50 flex justify-between items-center bg-gray-50/50">
              <h3 className="font-black text-2xl uppercase tracking-tighter">Параметры триггера</h3>
              <button onClick={() => setIsTriggerModalOpen(false)} className="p-3 bg-white rounded-full shadow-sm active:scale-90 transition-all"><X size={24} /></button>
            </div>
            
            <div className="p-8 overflow-y-auto space-y-8 custom-scrollbar pb-32">
              <div className="space-y-4">
                <input type="text" placeholder="Имя триггера" value={editingTrigger.name} onChange={(e) => setEditingTrigger({...editingTrigger, name: e.target.value})} className="w-full p-5 bg-gray-50 border border-gray-100 rounded-[2rem] font-black outline-none focus:ring-4 focus:ring-blue-500/5 transition-all" />
                <textarea placeholder="Ключевые слова или RegEx" value={editingTrigger.keyword} onChange={(e) => setEditingTrigger({...editingTrigger, keyword: e.target.value})} className="w-full p-5 bg-gray-50 border border-gray-100 rounded-[2rem] font-mono text-sm font-bold outline-none resize-none" rows="2" />
                
                <div className="flex items-center space-x-4 bg-yellow-50 p-5 rounded-[2rem] border border-yellow-100 shadow-inner">
                   <div className="flex-1">
                      <p className="text-[10px] font-black text-yellow-700 uppercase mb-2">Вероятность</p>
                      <input type="range" min="1" max="100" value={editingTrigger.probability} onChange={(e) => setEditingTrigger({...editingTrigger, probability: parseInt(e.target.value)})} className="w-full h-2 bg-yellow-200 rounded-lg appearance-none cursor-pointer accent-yellow-600" />
                   </div>
                   <span className="text-xl font-black text-yellow-800 w-12 text-right">{editingTrigger.probability}%</span>
                </div>
              </div>

              <div className="bg-blue-50/50 p-6 rounded-[2.5rem] border border-blue-100 space-y-5">
                <div className="grid grid-cols-1 gap-4">
                   <div className="flex items-center justify-between">
                      <span className="text-xs font-black text-gray-500 uppercase tracking-widest">Тип поиска:</span>
                      <select value={editingTrigger.condition} onChange={(e) => setEditingTrigger({...editingTrigger, condition: e.target.value})} className="bg-white border border-blue-200 rounded-xl px-4 py-2 text-xs font-black shadow-sm text-blue-900 uppercase">
                        <option value="any_word">Слова</option><option value="exact_match">Точно</option><option value="regex">RegEx</option>
                      </select>
                   </div>
                   <div className="flex items-center justify-between">
                      <span className="text-xs font-black text-gray-500 uppercase tracking-widest">Где ловим:</span>
                      <select value={editingTrigger.where} onChange={(e) => setEditingTrigger({...editingTrigger, where: e.target.value})} className="bg-white border border-blue-200 rounded-xl px-4 py-2 text-xs font-black shadow-sm text-blue-900 uppercase">
                        <option value="chat">В чате</option><option value="pv">В личке</option><option value="global">Везде</option>
                      </select>
                   </div>
                   <div className="flex items-center justify-between">
                      <span className="text-xs font-black text-gray-500 uppercase tracking-widest">Кто:</span>
                      <select value={editingTrigger.from} onChange={(e) => setEditingTrigger({...editingTrigger, from: e.target.value})} className="bg-white border border-blue-200 rounded-xl px-4 py-2 text-xs font-black shadow-sm text-blue-900 uppercase">
                        <option value="all">Все</option><option value="users">Юзеры</option><option value="admins">Админы</option>
                      </select>
                   </div>
                </div>
              </div>

              <div className="space-y-6">
                 <div className="grid grid-cols-2 gap-3">
                   <select value={editingTrigger.action} onChange={(e) => setEditingTrigger({...editingTrigger, action: e.target.value})} className="w-full p-5 bg-gray-900 text-white rounded-[2rem] font-black text-xs uppercase appearance-none text-center shadow-lg">
                      <option value="send_text">Текст</option><option value="delete">Удалить</option><option value="mute">Мут</option><option value="ban">Бан</option><option value="warn">Варн</option>
                   </select>
                   {['mute', 'ban'].includes(editingTrigger.action) ? (
                      <input type="text" placeholder="Напр: 2h" value={editingTrigger.duration} onChange={(e) => setEditingTrigger({...editingTrigger, duration: e.target.value})} className="w-full p-5 bg-white border border-gray-100 rounded-[2rem] font-black text-center text-sm shadow-inner" />
                   ) : (
                      <select value={editingTrigger.media_type} onChange={(e) => setEditingTrigger({...editingTrigger, media_type: e.target.value})} className="w-full p-5 bg-white border border-gray-100 rounded-[2rem] font-black text-xs uppercase appearance-none text-center shadow-inner">
                        <option value="none">Без медиа</option><option value="photo">Фото</option><option value="video">Видео</option><option value="animation">GIF</option>
                      </select>
                   )}
                 </div>
                 
                 <div className="relative">
                    <textarea placeholder="Текст ответа бота..." value={editingTrigger.reply_text} onChange={(e) => setEditingTrigger({...editingTrigger, reply_text: e.target.value})} className="w-full p-6 bg-gray-50 border border-gray-100 rounded-[2.5rem] font-bold text-sm outline-none shadow-inner" rows="3" />
                 </div>

                 <div className="bg-gray-100/50 p-6 rounded-[2.5rem] border border-gray-200">
                    <div className="flex items-center justify-between">
                       <span className="text-xs font-black text-gray-500 uppercase tracking-widest">Удаление ответа:</span>
                       <select value={editingTrigger.bot_msg_delete} onChange={(e) => setEditingTrigger({...editingTrigger, bot_msg_delete: e.target.value})} className="bg-white border border-gray-300 rounded-xl px-4 py-2 text-[10px] font-black uppercase shadow-sm">
                          <option value="no">Нет</option><option value="previous">Пред.</option><option value="period">Таймер</option>
                       </select>
                    </div>
                    {editingTrigger.bot_msg_delete === 'period' && (
                       <input type="number" placeholder="Секунд" value={editingTrigger.bot_msg_delete_after} onChange={(e) => setEditingTrigger({...editingTrigger, bot_msg_delete_after: parseInt(e.target.value)})} className="w-full mt-4 bg-white border border-gray-300 rounded-2xl px-4 py-2 font-black text-xs text-center outline-none" />
                    )}
                 </div>
              </div>
            </div>

            <div className="p-8 border-t border-gray-50 bg-white sticky bottom-0 rounded-t-[3rem] shadow-xl">
              <button onClick={saveTrigger} className="w-full py-6 bg-blue-600 text-white rounded-[2.2rem] font-black text-xl shadow-2xl active:scale-[0.97] transition-all">
                СОХРАНИТЬ ПРАВИЛО
              </button>
            </div>
          </div>
        </div>
      )}

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