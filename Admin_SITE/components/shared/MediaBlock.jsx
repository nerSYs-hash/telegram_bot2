import { useState } from 'react';
import { Image as ImageIcon, Video, FileImage, Trash2, Plus, ArrowUp, ArrowDown, Reply } from 'lucide-react';

/**
 * Универсальный блок управления медиа.
 *
 * props:
 *   value          — строка вида "photo:fid|video:fid|..."
 *   onChange(str)  — колбэк
 *   maxItems       — макс. число медиа (по умолчанию 5)
 *   position       — 'above' | 'below' | 'reply'
 *   onPositionChange(pos)
 *   showPosition   — показывать ли селектор позиции (по умолчанию true)
 */

const KIND_META = {
  photo:     { Icon: ImageIcon,  label: 'Фото',  color: 'blue'   },
  video:     { Icon: Video,      label: 'Видео', color: 'purple' },
  animation: { Icon: FileImage,  label: 'GIF',   color: 'pink'   },
};

function parseMedia(value) {
  if (!value) return [];
  return value.split('|').map(p => p.trim()).filter(Boolean).map(p => {
    if (p.startsWith('video:'))     return { kind: 'video',     fid: p.slice(6) };
    if (p.startsWith('animation:')) return { kind: 'animation', fid: p.slice(10) };
    if (p.startsWith('photo:'))     return { kind: 'photo',     fid: p.slice(6) };
    return { kind: 'photo', fid: p };  // legacy
  });
}

function packMedia(items) {
  return items.map(i => `${i.kind}:${i.fid}`).join('|');
}

const POSITIONS = [
  { v: 'above', label: 'Выше текста', Icon: ArrowUp   },
  { v: 'below', label: 'Ниже текста', Icon: ArrowDown },
  { v: 'reply', label: 'Реплаем',     Icon: Reply     },
];

export default function MediaBlock({
  value, onChange, maxItems = 5,
  position = 'above', onPositionChange, showPosition = true,
}) {
  const items = parseMedia(value);
  const [adding, setAdding] = useState(false);
  const [draftKind, setDraftKind] = useState('photo');
  const [draftFid,  setDraftFid]  = useState('');

  const addItem = () => {
    const fid = draftFid.trim();
    if (!fid) return;
    if (items.length >= maxItems) return;
    onChange(packMedia([...items, { kind: draftKind, fid }]));
    setDraftFid('');
    setAdding(false);
  };

  const removeItem = (idx) => {
    onChange(packMedia(items.filter((_, i) => i !== idx)));
  };

  const moveItem = (idx, dir) => {
    const next = [...items];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    onChange(packMedia(next));
  };

  return (
    <div className="space-y-3">
      {/* Position selector */}
      {showPosition && items.length > 0 && (
        <div className="flex items-center gap-1 p-1 bg-gray-50 rounded-xl">
          {POSITIONS.map(p => {
            const active = position === p.v;
            return (
              <button key={p.v}
                onClick={() => onPositionChange?.(p.v)}
                className={`flex-1 flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg text-[10px] font-black uppercase tracking-wide transition-all ${
                  active ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}>
                <p.Icon size={11} /> {p.label}
              </button>
            );
          })}
        </div>
      )}

      {/* List */}
      {items.length > 0 && (
        <div className="space-y-1.5">
          {items.map((it, i) => {
            const meta = KIND_META[it.kind] || KIND_META.photo;
            return (
              <div key={i} className="flex items-center gap-2 bg-gray-50 border border-gray-100 rounded-xl p-2">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center bg-${meta.color}-100`}>
                  <meta.Icon size={14} className={`text-${meta.color}-600`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] font-black text-gray-800">{meta.label}</div>
                  <div className="text-[10px] text-gray-400 font-mono truncate">{it.fid}</div>
                </div>
                <div className="flex items-center gap-0.5">
                  <button onClick={() => moveItem(i, -1)} disabled={i === 0}
                    className="p-1 text-gray-400 hover:text-blue-500 disabled:opacity-30">
                    <ArrowUp size={11} />
                  </button>
                  <button onClick={() => moveItem(i, 1)} disabled={i === items.length - 1}
                    className="p-1 text-gray-400 hover:text-blue-500 disabled:opacity-30">
                    <ArrowDown size={11} />
                  </button>
                  <button onClick={() => removeItem(i)}
                    className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded">
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add form */}
      {items.length < maxItems && (
        adding ? (
          <div className="bg-gray-50 border-2 border-dashed border-gray-200 rounded-xl p-3 space-y-2">
            <div className="flex gap-1">
              {Object.entries(KIND_META).map(([k, m]) => (
                <button key={k} onClick={() => setDraftKind(k)}
                  className={`flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-[10px] font-black uppercase ${
                    draftKind === k ? `bg-${m.color}-500 text-white` : 'bg-white text-gray-500 border border-gray-100'
                  }`}>
                  <m.Icon size={11} /> {m.label}
                </button>
              ))}
            </div>
            <input
              value={draftFid}
              onChange={(e) => setDraftFid(e.target.value)}
              placeholder="file_id из Telegram (например: AgACAgIA...)"
              className="w-full px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs font-mono focus:outline-none focus:border-blue-300"
              onKeyDown={(e) => { if (e.key === 'Enter') addItem(); }}
              autoFocus
            />
            <div className="flex gap-2">
              <button onClick={addItem} disabled={!draftFid.trim()}
                className="flex-1 py-2 bg-blue-500 text-white rounded-lg text-xs font-black hover:bg-blue-600 disabled:opacity-40">
                Добавить
              </button>
              <button onClick={() => { setAdding(false); setDraftFid(''); }}
                className="px-3 py-2 bg-gray-200 text-gray-700 rounded-lg text-xs font-black hover:bg-gray-300">
                Отмена
              </button>
            </div>
            <p className="text-[10px] text-gray-400">
              Загрузка файлов с компьютера будет в следующей версии. Пока — file_id из Telegram.
            </p>
          </div>
        ) : (
          <button onClick={() => setAdding(true)}
            className="w-full py-2.5 bg-gray-50 border-2 border-dashed border-gray-200 rounded-xl text-xs font-black text-gray-500 hover:bg-gray-100 hover:border-gray-300 flex items-center justify-center gap-1.5">
            <Plus size={12} /> Добавить медиа ({items.length}/{maxItems})
          </button>
        )
      )}
    </div>
  );
}
