// PressReleaseList — список пресс-релизов с фильтрами по статусу
// (черновик/запланирован/опубликован) и кнопкой создания нового.

import { useState, useMemo } from 'react';
import {
  FileText, Calendar, CheckCircle2, XCircle, AlertTriangle, Trash2,
  Send, Copy, RotateCcw, Edit3, Eye, Plus, Search, X,
} from 'lucide-react';
import StyledSelect from '../shared/StyledSelect';
import Card from '../shared/Card';

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

// Безопасный HTML-превью: обрезаем по тексту, оставляем только разрешённые теги
const ALLOWED_TAGS = /<\/?(?:b|strong|i|em|u|s|del|code|a|tg-spoiler|blockquote)(?:\s[^>]*)?>/gi;

function richPreview(html, maxChars = 100) {
  if (!html) return '';
  // Считаем длину текста без тегов и обрезаем
  const plain = html.replace(/<[^>]+>/g, '');
  const truncate = plain.length > maxChars;
  if (!truncate) return html;
  // Обрезаем сам HTML на N видимых символов
  let visibleLen = 0, out = '';
  for (let i = 0; i < html.length; i++) {
    if (html[i] === '<') {
      const close = html.indexOf('>', i);
      if (close === -1) break;
      out += html.slice(i, close + 1);
      i = close;
      continue;
    }
    if (visibleLen >= maxChars) break;
    out += html[i];
    visibleLen++;
  }
  return out + '…';
}

function PostCard({ post, onSelect, onAction, isSelected, userCan }) {
  const targets = post.targets || [];
  const targetSummary = targets.length === 0 ? '—' :
    targets.length === 1 ? `1 чат` : `${targets.length} чатов`;

  return (
    <Card
      padding="sm"
      onClick={() => onSelect(post)}
      active={isSelected}
      hoverable={!isSelected}
      glow={isSelected}
      accent="blue"
      className="cursor-pointer"
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-black text-tx truncate">
            {post.title || <span className="text-lbl italic">(без имени)</span>}
          </div>
          <div
            className="text-[11px] text-txd truncate mt-0.5 [&_b]:font-bold [&_strong]:font-bold [&_i]:italic [&_em]:italic [&_u]:underline [&_s]:line-through"
            dangerouslySetInnerHTML={{ __html: richPreview(post.text || '', 100) }}
          />
          <div className="flex items-center gap-2 mt-1.5 text-[10px] text-lbl">
            <Calendar size={10} />
            <span>{fmtDate(post.publish_at)}</span>
            <span>·</span>
            <span>{targetSummary}</span>
          </div>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onAction('delete', post); }}
          title="Удалить"
          className="p-1 text-lbl hover:text-danger hover:bg-red-50 rounded-lg flex-shrink-0"
        >
          <X size={16} />
        </button>
      </div>

      {/* Actions row */}
      <div className="flex items-center gap-1 mt-2 pt-2 border-t border-bd">
        <button
          onClick={(e) => { e.stopPropagation(); onAction('edit', post); }}
          title="Редактировать"
          className="p-1.5 text-lbl hover:text-cta hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] rounded-lg">
          <Edit3 size={12} />
        </button>
        {userCan('press_release.create') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('clone', post); }}
            title="Дублировать"
            className="p-1.5 text-lbl hover:text-purple hover:bg-[color-mix(in_oklab,var(--purple)_10%,transparent)] rounded-lg">
            <Copy size={12} />
          </button>
        )}
        {post.status === 'scheduled' && userCan('press_release.publish_now') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('publish_now', post); }}
            title="Опубликовать сейчас"
            className="p-1.5 text-lbl hover:text-ok hover:bg-[color-mix(in_oklab,var(--ok)_10%,transparent)] rounded-lg">
            <Send size={12} />
          </button>
        )}
        {post.status === 'scheduled' && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('cancel', post); }}
            title="Отменить"
            className="p-1.5 text-lbl hover:text-warn hover:bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] rounded-lg">
            <XCircle size={12} />
          </button>
        )}
        {(post.status === 'cancelled' || post.status === 'failed') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('restore', post); }}
            title="Восстановить (вернуть в черновик)"
            className="p-1.5 text-lbl hover:text-cta hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] rounded-lg">
            <RotateCcw size={12} />
          </button>
        )}
        {post.status === 'published' && userCan('press_release.delete') && (
          <button
            onClick={(e) => { e.stopPropagation(); onAction('delete_from_tg', post); }}
            title="Удалить из Telegram (на сайте останется)"
            className="p-1.5 text-lbl hover:text-danger hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] rounded-lg ml-auto">
            <span className="text-[10px] font-black">TG</span>
          </button>
        )}
      </div>
    </Card>
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

  const currentTab = TABS.find(t => t.id === tab) || TABS[0];

  return (
    <div className="space-y-3">
      {/* Dropdown tabs */}
      <div className="relative">
        <StyledSelect
          value={tab}
          onChange={(v) => setTab(v)}
          options={TABS.map(t => ({
            value: t.id,
            label: `${t.label}${(counts[t.id] || 0) > 0 ? ` (${counts[t.id]})` : ''}`,
          }))}
          className="w-full uppercase tracking-wide"
        />
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-lbl" />
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по имени/тексту"
          className="w-full pl-8 pr-3 py-2 bg-sff border border-bd rounded-xl text-xs font-bold focus:outline-none focus:border-[color-mix(in_oklab,var(--cta)_40%,transparent)]" />
      </div>

      {/* List */}
      <div className="space-y-2 max-h-[60vh] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-lbl text-sm">
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
