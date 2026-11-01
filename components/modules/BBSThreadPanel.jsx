// V1.17.0Q4: панель настройки тредов BBS-семейства (per-ws).
//
// Илья 29.05: «в семействе ББС куча детей и нужно центральный модуль на него
// навесить привязку к ветке и все. Единственный вопрос по ББС Другое (это
// объявления продаж/аренды) — для него тоже предусмотреть свой топик. Но
// если не выбирает — публикуется в общий ББС-тред (как у Вити)».
//
// Модель cascade:
//   bbs_pulse (главный) → kind='bbs' thread_id
//     ├── bbs_edit / vip_bbs / bbs_bonus — наследуют
//     └── bbs_other — опциональный kind='bbs_other' (fallback на 'bbs')
import { useState, useEffect } from 'react';
import { X, Save, Info, Trash2 } from 'lucide-react';
import { getActiveWs } from '../shared/api';

const API = (path, token, opts = {}) =>
  fetch(path, {
    ...opts,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });

export default function BBSThreadPanel({ open, onClose }) {
  const [bbsThread, setBbsThread] = useState('');
  const [otherThread, setOtherThread] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(null);

  const wsId = getActiveWs();
  const token = localStorage.getItem('auth_token');

  // Загрузка текущих настроек
  useEffect(() => {
    if (!open || !wsId || !token) return;
    setLoading(true);
    setError(null);
    API(`/api/workspaces/${wsId}/topics`, token)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d && d.topics) {
          const bbs = d.topics.find(t => t.kind === 'bbs');
          const other = d.topics.find(t => t.kind === 'bbs_other');
          setBbsThread(bbs ? String(bbs.thread_id) : '');
          setOtherThread(other ? String(other.thread_id) : '');
        }
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [open, wsId, token]);

  const saveTopic = async (kind, value) => {
    if (!wsId || !token) return;
    const tid = parseInt(value, 10);
    if (!tid || isNaN(tid)) {
      setError(`${kind}: введи числовой thread_id`);
      return;
    }
    setError(null);
    try {
      const r = await API(`/api/workspaces/${wsId}/topics/${kind}`, token, {
        method: 'PUT',
        body: JSON.stringify({ thread_id: tid }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        setError(err.detail || `Ошибка сохранения ${kind}: ${r.status}`);
        return;
      }
      setSaved(kind);
      setTimeout(() => setSaved(null), 2000);
    } catch (e) {
      setError(String(e));
    }
  };

  const clearTopic = async (kind) => {
    if (!wsId || !token) return;
    try {
      const r = await API(`/api/workspaces/${wsId}/topics/${kind}`, token, {
        method: 'DELETE',
      });
      if (!r.ok) {
        setError(`Ошибка сброса ${kind}`);
        return;
      }
      if (kind === 'bbs_other') setOtherThread('');
      if (kind === 'bbs') setBbsThread('');
      setSaved(`${kind}_cleared`);
      setTimeout(() => setSaved(null), 2000);
    } catch (e) {
      setError(String(e));
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
         onClick={onClose}>
      <div className="bg-sff rounded-3xl border border-bd w-full max-w-lg shadow-2xl"
           onClick={e => e.stopPropagation()}>
        {/* Заголовок */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-bd">
          <h2 className="text-lg font-black text-tx">Ветки публикаций ББС</h2>
          <button onClick={onClose}
                  className="p-2 hover:bg-sf2 rounded-lg transition">
            <X size={20} className="text-txd" />
          </button>
        </div>

        {/* Тело */}
        <div className="p-6 space-y-5">
          {/* Главная ветка ББС */}
          <div>
            <label className="block text-sm font-bold text-tx mb-2">
              Главная ветка для анкет
            </label>
            <div className="text-[12px] text-txd mb-2">
              Куда бот будет публиковать анкеты участников.
              Остальные модули ББС (Редактор анкет, VIP BBS, BBS-бонусы)
              автоматически работают в этой же ветке.
            </div>
            <div className="flex gap-2">
              <input type="number" value={bbsThread}
                     onChange={e => setBbsThread(e.target.value)}
                     placeholder="ID ветки"
                     className="flex-1 px-3 py-2 rounded-xl border border-bd bg-sff text-tx text-sm focus:outline-none focus:border-cta" />
              <button onClick={() => saveTopic('bbs', bbsThread)}
                      className="px-4 py-2 rounded-xl bg-cta text-white font-bold text-sm hover:opacity-90 transition flex items-center gap-1.5">
                <Save size={14} />Сохранить
              </button>
              {bbsThread && (
                <button onClick={() => clearTopic('bbs')}
                        className="px-3 py-2 rounded-xl border border-bd hover:bg-sf2 transition"
                        title="Очистить настройку">
                  <Trash2 size={14} className="text-danger" />
                </button>
              )}
            </div>
          </div>

          {/* ББС Другое override */}
          <div className="pt-4 border-t border-bd">
            <label className="block text-sm font-bold text-tx mb-2">
              Отдельная ветка для объявлений — по желанию
            </label>
            <div className="text-[12px] text-txd mb-2">
              Касается раздела «ББС Другое» — продажи, аренда, услуги.
              <br />
              Можно выделить этим объявлениям свою ветку — заполни поле ниже.
              <br />
              Можно оставить <b>пустым</b> — тогда объявления пойдут в ту же ветку что и анкеты.
            </div>
            <div className="flex gap-2">
              <input type="number" value={otherThread}
                     onChange={e => setOtherThread(e.target.value)}
                     placeholder="ID ветки (или оставь пустым)"
                     className="flex-1 px-3 py-2 rounded-xl border border-bd bg-sff text-tx text-sm focus:outline-none focus:border-cta" />
              <button onClick={() => saveTopic('bbs_other', otherThread)}
                      className="px-4 py-2 rounded-xl bg-cta text-white font-bold text-sm hover:opacity-90 transition flex items-center gap-1.5">
                <Save size={14} />Сохранить
              </button>
              {otherThread && (
                <button onClick={() => clearTopic('bbs_other')}
                        className="px-3 py-2 rounded-xl border border-bd hover:bg-sf2 transition"
                        title="Очистить — объявления пойдут вместе с анкетами">
                  <Trash2 size={14} className="text-danger" />
                </button>
              )}
            </div>
          </div>

          {/* Помощь */}
          <div className="bg-sf2 rounded-2xl p-4 text-[12px] text-txd flex gap-2">
            <Info size={16} className="text-cta shrink-0 mt-0.5" />
            <div>
              <b>Где взять ID ветки:</b> зайди в нужную ветку чата в Telegram,
              отправь команду <code className="font-mono">/get_thread_id</code> —
              бот ответит числом. Скопируй и вставь сюда.
            </div>
          </div>

          {/* Статусы */}
          {loading && <div className="text-sm text-txd">Загрузка…</div>}
          {error && <div className="text-sm text-danger">{error}</div>}
          {saved && (
            <div className="text-sm text-ok">
              ✓ Сохранено{saved.includes('_cleared') ? ' (сброшено)' : ''}.
              Изменения применятся к следующей публикации.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
