import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, ShieldAlert, HeartHandshake, Coins, Trash2, ShieldCheck, Dices, Terminal } from 'lucide-react';
import { getActiveWs } from '../shared/api';

const CATEGORIES = [
  { id: 'system', name: 'Системные', desc: 'Команды бота (/start, /help, /rules) и сервисные сообщения', icon: Terminal },
  { id: 'moderation', name: 'Модерация', desc: 'Предупреждения, муты, баны и приветствия новых участников', icon: ShieldCheck },
  { id: 'triggers', name: 'Ответы Триггеров', desc: 'Автоматические реакции на ключевые слова (модуль Триггеры)', icon: ShieldAlert },
  { id: 'bbs', name: 'Знакомства (BBS)', desc: 'Публикация анкет из доски знакомств', icon: HeartHandshake },
  { id: 'shipper', name: 'Шиппер', desc: 'Результаты создания случайных пар', icon: HeartHandshake },
  { id: 'economy', name: 'Экономика', desc: 'Начисление пульсов, переводы и топы', icon: Coins },
  { id: 'games', name: 'Игровые', desc: 'Результаты Бинго, Лотереи, Спринтов', icon: Dices }
];

export default function GarbageCollectorPanel({ token }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [toast, setToast] = useState(null);

  // Default state matches "disabled by default"
  const [settings, setSettings] = useState({
    enabled: false,
    categories: CATEGORIES.reduce((acc, cat) => {
      acc[cat.id] = { enabled: false, delay_seconds: 60 };
      return acc;
    }, {})
  });

  const wsId = getActiveWs();

  useEffect(() => {
    if (!wsId || !token) return;
    setLoading(true);
    fetch(`/api/workspaces/${wsId}/garbage_collector`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        if (data && data.settings) {
          // Merge with defaults to ensure all categories exist
          const merged = { ...settings };
          merged.enabled = data.settings.enabled || false;
          Object.keys(data.settings.categories || {}).forEach(k => {
            if (merged.categories[k]) {
              merged.categories[k] = data.settings.categories[k];
            }
          });
          setSettings(merged);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [wsId, token]);

  const saveSettings = () => {
    setSaving(true);
    fetch(`/api/workspaces/${wsId}/garbage_collector`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ settings })
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(() => {
        setDirty(false);
        setToast('Настройки сохранены');
        setTimeout(() => setToast(null), 2500);
      })
      .catch(() => {
        setToast('Ошибка сохранения');
        setTimeout(() => setToast(null), 3000);
      })
      .finally(() => setSaving(false));
  };

  const updateCategory = (id, key, value) => {
    setSettings(prev => ({
      ...prev,
      categories: {
        ...prev.categories,
        [id]: {
          ...prev.categories[id],
          [key]: value
        }
      }
    }));
    setDirty(true);
  };

  const toggleModule = () => {
    setSettings(p => ({ ...p, enabled: !p.enabled }));
    setDirty(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-24 animate-in fade-in duration-500">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-20 right-4 z-50 px-5 py-3 rounded-2xl shadow-2xl font-black text-sm text-white transition-all duration-300 ${toast.startsWith('Ошибка') ? 'bg-red-500' : 'bg-green-500'}`}>
          {toast}
        </div>
      )}

      {/* Шапка модуля */}
      <div className="bg-sff rounded-[2.5rem] p-6 border border-bd shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h3 className="font-black text-xl text-tx mb-1 flex items-center">
            <Trash2 size={22} className="mr-3 text-cta" />
            Очистка чата от бота (GC)
          </h3>
          <p className="text-xs text-lbl font-medium">Централизованная настройка удаления системных сообщений бота.</p>
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="flex-1 sm:flex-none text-right">
            <span className={`text-[10px] font-black uppercase tracking-widest ${settings.enabled ? 'text-ok' : 'text-danger'}`}>
              {settings.enabled ? '● Активен' : '○ Отключен'}
            </span>
          </div>
          <button onClick={toggleModule} className={`w-14 h-8 rounded-full transition-colors relative flex-shrink-0 ${settings.enabled ? 'bg-green-500' : 'bg-bd2'}`}>
            <div className={`absolute top-1 w-6 h-6 bg-sff rounded-full transition-all ${settings.enabled ? 'left-7' : 'left-1'}`} />
          </button>
        </div>
      </div>

      <div className="bg-sff rounded-[2.5rem] p-6 border border-bd shadow-sm">
        <div className="flex items-center justify-between mb-6">
           <h4 className="font-black text-lg text-tx">Группы сообщений</h4>
           <button
             onClick={saveSettings}
             disabled={!dirty || saving}
             className={`flex items-center gap-1.5 px-5 py-2.5 rounded-xl font-black text-sm transition-all active:scale-95 ${
               dirty && !saving
                 ? 'bg-blue-600 text-white shadow-md shadow-blue-100 hover:bg-blue-700'
                 : 'bg-sf2 text-lbl cursor-not-allowed'
             }`}
           >
             {saving ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
             Сохранить
           </button>
        </div>

        <div className="space-y-3">
          {CATEGORIES.map(cat => {
            const Icon = cat.icon;
            const state = settings.categories[cat.id];
            
            return (
              <div key={cat.id} className={`p-5 rounded-2xl border transition-all ${state.enabled ? 'bg-[color-mix(in_oklab,var(--cta)_5%,transparent)] border-[color-mix(in_oklab,var(--cta)_20%,transparent)]' : 'bg-sf2 border-bd'}`}>
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                  {/* Иконка и Текст */}
                  <div className="flex-1 flex items-center gap-4 min-w-0">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${state.enabled ? 'bg-blue-500 text-white shadow-md shadow-blue-200' : 'bg-white border border-bd2 text-txd'}`}>
                      <Icon size={20} />
                    </div>
                    <div className="min-w-0">
                      <h5 className="font-black text-sm text-tx">{cat.name}</h5>
                      <p className="text-[11px] text-lbl font-medium mt-0.5 leading-snug">{cat.desc}</p>
                    </div>
                  </div>

                  {/* Настройки (Тумблер + Таймер) */}
                  <div className="flex items-center gap-4 w-full sm:w-auto mt-2 sm:mt-0 justify-end">
                     {state.enabled && (
                        <div className="flex items-center gap-2">
                           <span className="text-[11px] font-bold text-txd">Через:</span>
                           <div className="flex items-center bg-white border border-bd2 rounded-lg px-2 py-1.5 focus-within:border-blue-400">
                              <input 
                                 type="number" 
                                 min="5" 
                                 max="86400"
                                 value={state.delay_seconds}
                                 onChange={e => updateCategory(cat.id, 'delay_seconds', parseInt(e.target.value) || 60)}
                                 className="w-14 text-center font-black text-sm outline-none bg-transparent"
                              />
                              <span className="text-xs font-bold text-lbl ml-1">сек</span>
                           </div>
                        </div>
                     )}
                     
                     <button onClick={() => updateCategory(cat.id, 'enabled', !state.enabled)} className={`w-12 h-7 rounded-full transition-colors relative flex-shrink-0 ${state.enabled ? 'bg-blue-500' : 'bg-bd2'}`}>
                        <div className={`absolute top-1 w-5 h-5 bg-sff rounded-full transition-all ${state.enabled ? 'left-6' : 'left-1'}`} />
                     </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        
        <div className="mt-6 px-4 py-4 bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] border border-[color-mix(in_oklab,var(--warn)_30%,transparent)] rounded-2xl">
           <p className="text-xs font-medium text-warn leading-relaxed flex items-start">
             <ShieldAlert size={16} className="mr-2 flex-shrink-0 mt-0.5"/>
             <span>
               <strong>Примечание:</strong> Пресс-релизы исключены из системы автоматического удаления, так как они управляются собственным планировщиком. Убедитесь, что у бота есть права администратора на удаление сообщений.
             </span>
           </p>
        </div>
      </div>
    </div>
  );
}
