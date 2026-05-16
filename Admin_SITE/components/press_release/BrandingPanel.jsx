import { useState, useEffect } from 'react';
import { Palette, Save, CheckCircle2, Plus, Trash2, Edit3, Star, X } from 'lucide-react';
import { makeApi } from './useApi';
import Button from '../shared/Button';

/**
 * Менеджер шаблонов подписей.
 * Хранит JSON-массив в branding_settings.signatures = [{id, name, html, is_default}].
 * Один из них можно отметить как default — он подставляется при создании пресс-релиза.
 *
 * props:
 *   token             — JWT
 *   onChange()        — колбэк при изменении (чтобы родитель refetch'ил branding)
 *   compact           — компактный режим (без своего контейнера, для встраивания)
 */

function newId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }

function parseList(raw) {
  if (!raw) return [];
  try {
    const v = JSON.parse(raw);
    return Array.isArray(v) ? v : [];
  } catch { return []; }
}

export default function BrandingPanel({ token, onChange, compact = false }) {
  const api = makeApi(token);
  const [list, setList] = useState([]);
  const [editing, setEditing] = useState(null);  // {id?, name, html, is_default}
  const [savedAt, setSavedAt] = useState(0);
  const [busy, setBusy] = useState(false);

  const refresh = () => api.getBranding().then(d => {
    setList(parseList(d?.signatures));
  }).catch(() => {});

  useEffect(() => { refresh(); }, []);

  const saveAll = async (next) => {
    setBusy(true);
    try {
      // Сохраняем массив в JSON
      await api.setBranding('signatures', JSON.stringify(next));
      // Обновляем legacy ключ "signature" — это default-подпись для обратной совместимости
      const def = next.find(s => s.is_default);
      await api.setBranding('signature', def?.html || '');
      setList(next);
      setSavedAt(Date.now());
      setTimeout(() => setSavedAt(0), 1500);
      onChange?.();
    } catch (e) {
      alert('Ошибка: ' + (e?.detail || e?.message || e));
    } finally { setBusy(false); }
  };

  const startNew = () => setEditing({ id: null, name: '', html: '', is_default: list.length === 0 });
  const startEdit = (s) => setEditing({ ...s });
  const cancelEdit = () => setEditing(null);

  const saveDraft = async () => {
    if (!editing) return;
    if (!editing.name.trim()) { alert('Введите название шаблона'); return; }
    let next;
    if (editing.id) {
      next = list.map(s => s.id === editing.id ? { ...editing } : s);
    } else {
      next = [...list, { ...editing, id: newId() }];
    }
    // Только один может быть default
    if (editing.is_default) {
      next = next.map(s => ({ ...s, is_default: s.id === (editing.id || next[next.length - 1].id) }));
    }
    await saveAll(next);
    setEditing(null);
  };

  const deleteOne = async (id) => {
    if (!confirm('Удалить шаблон подписи?')) return;
    await saveAll(list.filter(s => s.id !== id));
  };

  const setDefault = async (id) => {
    await saveAll(list.map(s => ({ ...s, is_default: s.id === id })));
  };

  // ВАЖНО: НЕ объявлять Wrapper-компонент внутри функции — каждый ререндер
  // создаёт новую ссылку на тип, React размонтирует поддерево и теряет фокус
  // input/textarea (баг V1.16.14n: «курсор не встаёт в карточку подписи»).
  const wrapperCls = compact
    ? 'space-y-3'
    : 'bg-white rounded-3xl border border-gray-100 shadow-sm p-5 space-y-3';

  return (
    <div className={wrapperCls}>
      {/* В compact-режиме (внутри редактора пресс-релиза) свой заголовок не
          рисуем — он дублирует обёртку Section «Подпись и брендинг». */}
      {!compact && (
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-xl bg-pink-100 flex items-center justify-center">
            <Palette size={14} className="text-pink-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-xs font-black uppercase tracking-widest text-gray-900">Шаблоны подписей</h2>
            <p className="text-[10px] text-gray-400 mt-0.5">
              Можно создать несколько вариантов брендинга и переключаться при создании пресс-релиза
            </p>
          </div>
          {savedAt > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-black text-emerald-500">
              <CheckCircle2 size={12}/> сохранено
            </span>
          )}
        </div>
      )}
      {compact && savedAt > 0 && (
        <div className="flex justify-end">
          <span className="flex items-center gap-1 text-[10px] font-black text-emerald-500">
            <CheckCircle2 size={12}/> сохранено
          </span>
        </div>
      )}

      {/* List */}
      {list.length > 0 && (
        <div className="space-y-1.5">
          {list.map(s => (
            <div key={s.id} className={`bg-gray-50 border rounded-xl p-2.5 ${s.is_default ? 'border-amber-300 bg-amber-50' : 'border-gray-100'}`}>
              <div className="flex items-center gap-2 mb-1">
                {s.is_default && <Star size={12} className="text-amber-500 fill-amber-400" />}
                <div className="text-xs font-black text-gray-800 truncate flex-1">{s.name}</div>
                {!s.is_default && (
                  <button onClick={() => setDefault(s.id)} title="Сделать дефолтом"
                    className="p-1 text-gray-400 hover:text-amber-500 hover:bg-amber-50 rounded">
                    <Star size={11} />
                  </button>
                )}
                <button onClick={() => startEdit(s)} title="Редактировать"
                  className="p-1 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded">
                  <Edit3 size={11} />
                </button>
                <button onClick={() => deleteOne(s.id)} title="Удалить"
                  className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded">
                  <Trash2 size={11} />
                </button>
              </div>
              <div className="text-xs text-gray-600 leading-snug [&_b]:font-bold [&_strong]:font-bold [&_i]:italic"
                   dangerouslySetInnerHTML={{ __html: s.html || '<span class="text-gray-300 italic">(пусто)</span>' }} />
            </div>
          ))}
        </div>
      )}

      {/* Editor inline */}
      {editing && (
        <div className="bg-white border-2 border-pink-100 rounded-2xl p-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-black uppercase tracking-widest text-pink-600">
              {editing.id ? 'Редактирование' : 'Новый шаблон'}
            </span>
            <button onClick={cancelEdit} className="ml-auto text-gray-300 hover:text-gray-500">
              <X size={14}/>
            </button>
          </div>
          <input
            value={editing.name}
            onChange={(e) => setEditing(s => ({ ...s, name: e.target.value }))}
            placeholder="Название (например: Основная)"
            className="w-full px-3 py-2 bg-gray-50 border border-gray-100 rounded-lg text-xs font-bold focus:outline-none focus:border-pink-300"
          />
          <textarea
            value={editing.html}
            onChange={(e) => setEditing(s => ({ ...s, html: e.target.value }))}
            placeholder='— <b>Pulse Community</b> | @pulse_chat'
            rows={3}
            className="w-full px-3 py-2 bg-gray-50 border border-gray-100 rounded-lg text-xs font-mono focus:outline-none focus:border-pink-300 resize-y"
          />
          {editing.html.trim() && (
            <div className="bg-gray-50 border border-gray-100 rounded-lg px-3 py-2 [&_b]:font-bold [&_i]:italic">
              <div className="text-[9px] font-black uppercase tracking-widest text-gray-400 mb-1">Превью</div>
              <div className="text-xs text-gray-700" dangerouslySetInnerHTML={{ __html: editing.html }} />
            </div>
          )}
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={editing.is_default}
              onChange={(e) => setEditing(s => ({ ...s, is_default: e.target.checked }))}
              className="w-4 h-4 accent-amber-500" />
            <span className="text-[11px] font-bold text-gray-700">Сделать дефолтом</span>
          </label>
          <div className="flex gap-2">
            <Button variant="primary" size="sm" icon={Save} block disabled={busy} onClick={saveDraft}>
              Сохранить
            </Button>
            <Button variant="secondary" size="sm" onClick={cancelEdit}>
              Отмена
            </Button>
          </div>
        </div>
      )}

      {!editing && (
        <button onClick={startNew}
          className="w-full py-2.5 bg-gray-50 border-2 border-dashed border-gray-200 rounded-xl text-xs font-black text-gray-600 hover:bg-pink-50 hover:border-pink-200 hover:text-pink-600 flex items-center justify-center gap-1.5">
          <Plus size={12}/> Добавить шаблон подписи
        </button>
      )}
    </div>
  );
}

export { parseList as parseSignatures };
