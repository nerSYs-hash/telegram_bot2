import { useState, useMemo } from 'react';
import {
  FileText, Calendar, CheckCircle2, XCircle, AlertTriangle, Trash2,
  Send, Copy, RotateCcw, Edit3, Eye, Plus, Search,
} from 'lucide-react';

const TABS = [
  { id: 'scheduled', label: 'Запланированные', icon: Calendar,      color: 'blue'    },
  { id: 'draft',     label: 'Черновики',       icon: FileText,      color: 'gray'    },
  { id: 'published', label: 'История',         icon: CheckCircle2,  color: 'emerald' },
  { id: 'cancelled', label: 'Отменённые',      icon: XCircle,       color: 'amber'   },
  { id: 'failed',    label: 'Ошибки',          icon: AlertTriangle, color: 'red'     },
];

function fmtDate(iso) {
  if (!iso || iso.startsWith('1970')) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function PostCard({ post, onSelect, onAction, isSelected, userCan }) {
  const targets = post.targets || [];
  const targetSummary = targets.length === 0 ? '—' :
    targets.length === 1 ? `1 чат` : `${targets.length} чатов`;

  return (
    <div
      onClick={() => onSelect(post)}
      className={`rounded-2xl border p-3 cursor-pointer transition-all ${
        isSelected ? 'bg-blue-50 border-blue-200 shadow-sm' : 'bg-white border-gray-100 hover:border-gray-200'
      }`}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-black text-gray-800 truncate">
            {post.title || <span className="text-gray-400 italic">(без имени)</span>}
          </div>
          <div className="text-[11px] text-gray-500 truncate mt-0.5">
            {(post.text || '').slice(0, 80)}{(post.text || '').length > 80 ? '…' : ''}
          </div>
          <div className="flex items-center gap-2 mt-1.5 text-[10px] text-gray-400">
            <Calendar size={10} />
            <span>{fmtDate(post.publish_at)}</span>
            <span>·</span>
            <span>{targetSummary}</span>
          </div>
        </div>
      </div>

      {/* Actions row */}
      <div className="flex items-center gap-1 mt-2 pt-2 border-t border-gray-100">
        <button
          onClick={(e) => { e.stopPropagation(); onAction('edit', post); }}
          title="Редактировать"
          className="p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg">
          <Edit3 size={12} />
        </button>
        {userCan('press_release.create') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('clone', post); }}
            title="Дублировать"
            className="p-1.5 text-gray-400 hover:text-violet-500 hover:bg-violet-50 rounded-lg">
            <Copy size={12} />
          </button>
        )}
        {post.status === 'scheduled' && userCan('press_release.publish_now') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('publish_now', post); }}
            title="Опубликовать сейчас"
            className="p-1.5 text-gray-400 hover:text-emerald-500 hover:bg-emerald-50 rounded-lg">
            <Send size={12} />
          </button>
        )}
        {post.status === 'scheduled' && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('cancel', post); }}
            title="Отменить"
            className="p-1.5 text-gray-400 hover:text-amber-500 hover:bg-amber-50 rounded-lg">
            <XCircle size={12} />
          </button>
        )}
        {(post.status === 'cancelled' || post.status === 'failed') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('restore', post); }}
            title="Восстановить (вернуть в черновик)"
            className="p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg">
            <RotateCcw size={12} />
          </button>
        )}
        {post.status === 'published' && userCan('press_release.delete') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('delete_from_tg', post); }}
            title="Удалить из Telegram (на сайте останется)"
            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg ml-auto">
            <span className="text-[10px] font-black">TG</span>
          </button>
        )}
        {userCan('press_release.delete') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('delete', post); }}
            title="Удалить с сайта (сообщение в Telegram останется)"
            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg ml-auto">
            <Trash2 size={12} />
          </button>
        )}
      </div>
    </div>
  );
}

export default function PressReleaseList({
  api, posts, selectedId, onSelect, onAction, onCreate, userCan,
}) {
  const [tab, setTab] = useState('scheduled');
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const list = (posts || []).filter(p => p.status === tab);
    if (!search) return list;
    const q = search.toLowerCase();
    return list.filter(p =>
      (p.title || '').toLowerCase().includes(q) ||
      (p.text || '').toLowerCase().includes(q)
    );
  }, [posts, tab, search]);

  const counts = useMemo(() => {
    const c = {};
    (posts || []).forEach(p => { c[p.status] = (c[p.status] || 0) + 1; });
    return c;
  }, [posts]);

  return (
    <div className="space-y-3">
      {/* Кнопка нового */}
      <button onClick={onCreate}
        className="w-full py-3 bg-blue-500 text-white rounded-2xl font-black text-sm shadow-md shadow-blue-100 hover:bg-blue-600 active:scale-95 transition-all flex items-center justify-center gap-2">
        <Plus size={14}/> Новый пресс-релиз
      </button>

      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto scrollbar-hide -mx-1 px-1">
        {TABS.map(t => {
          const active = t.id === tab;
          const cnt = counts[t.id] || 0;
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex-shrink-0 px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wide flex items-center gap-1.5 transition-all ${
                active ? 'bg-gray-900 text-white' : 'bg-white text-gray-500 border border-gray-100'
              }`}>
              <t.icon size={11} />
              {t.label}
              {cnt > 0 && (
                <span className={`px-1.5 py-0.5 rounded-full text-[9px] ${active ? 'bg-white/20' : `bg-${t.color}-100 text-${t.color}-700`}`}>
                  {cnt}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" />
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по имени/тексту"
          className="w-full pl-8 pr-3 py-2 bg-white border border-gray-100 rounded-xl text-xs font-bold focus:outline-none focus:border-blue-200" />
      </div>

      {/* List */}
      <div className="space-y-2 max-h-[60vh] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-sm">
            {search ? 'Ничего не найдено' : 'Пусто'}
          </div>
        ) : filtered.map(p => (
          <PostCard
            key={p.id}
            post={p}
            isSelected={selectedId === p.id}
            onSelect={onSelect}
            onAction={onAction}
            userCan={userCan}
          />
        ))}
      </div>
    </div>
  );
}
