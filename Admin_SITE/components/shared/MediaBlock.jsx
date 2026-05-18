import { useState, useRef } from 'react';
import {
  Image as ImageIcon, Video, FileImage, Trash2,
  Plus, ArrowUp, ArrowDown, Reply, Loader2, Upload,
} from 'lucide-react';
import ButtonGroup from './ButtonGroup';

/**
 * Универсальный блок управления медиа.
 *
 * Хранение в БД (поле photo_file_id):
 *   - "photo:URL_OR_FID|video:URL_OR_FID|animation:URL_OR_FID"
 *   - URL_OR_FID — либо file_id (старая схема, начинается с букв),
 *                   либо локальный путь с /media/ или server_path после загрузки.
 *
 * При публикации publisher.py:
 *   - Если значение начинается с '/' или 'http' → открыть файл/скачать и отправить.
 *   - Иначе → отправить как file_id.
 *
 * props:
 *   value          — строка
 *   onChange(str)  — колбэк
 *   maxItems       — макс. число медиа (по умолчанию 5)
 *   position       — 'above' | 'below' | 'reply'
 *   onPositionChange(pos)
 *   showPosition   — показывать ли селектор позиции
 */

const KIND_META = {
  photo:     { Icon: ImageIcon,  label: 'Фото',  color: 'blue',   accept: 'image/jpeg,image/png,image/webp' },
  video:     { Icon: Video,      label: 'Видео', color: 'purple', accept: 'video/mp4,video/quicktime'        },
  animation: { Icon: FileImage,  label: 'GIF',   color: 'pink',   accept: 'image/gif'                        },
};

function parseMedia(value) {
  if (!value) return [];
  return value.split('|').map(p => p.trim()).filter(Boolean).map(p => {
    if (p.startsWith('video:'))     return { kind: 'video',     fid: p.slice(6) };
    if (p.startsWith('animation:')) return { kind: 'animation', fid: p.slice(10) };
    if (p.startsWith('photo:'))     return { kind: 'photo',     fid: p.slice(6) };
    return { kind: 'photo', fid: p };
  });
}

function packMedia(items) {
  return items.map(i => `${i.kind}:${i.fid}`).join('|');
}

function isUrl(fid) {
  return fid?.startsWith('/') || fid?.startsWith('http');
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
  const [uploading, setUploading] = useState(false);
  const [error, setError]         = useState(null);
  const fileInputRef = useRef(null);
  const pendingKindRef = useRef(null);

  const startUpload = async (file, kind) => {
    setError(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('/api/media/upload', { method: 'POST', body: fd });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(err || 'Ошибка загрузки');
      }
      const data = await res.json();
      // Сервер сам определит media_type — но мы доверяем выбору пользователя
      const finalKind = kind || data.media_type || 'photo';
      const newItems = [...items, { kind: finalKind, fid: data.url }];
      onChange(packMedia(newItems));
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setUploading(false);
    }
  };

  const pickFile = (kind) => {
    pendingKindRef.current = kind;
    if (fileInputRef.current) {
      fileInputRef.current.accept = KIND_META[kind]?.accept || '*/*';
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

  const onFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await startUpload(file, pendingKindRef.current);
    pendingKindRef.current = null;
  };

  const removeItem = (idx) => onChange(packMedia(items.filter((_, i) => i !== idx)));
  const moveItem = (idx, dir) => {
    const next = [...items];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    onChange(packMedia(next));
  };

  return (
    <div className="space-y-3">
      <input ref={fileInputRef} type="file" className="hidden" onChange={onFileChange} />

      {/* Position selector */}
      {showPosition && items.length > 0 && (
        <ButtonGroup
          value={position}
          onChange={(v) => onPositionChange?.(v)}
          options={POSITIONS.map(p => ({ value: p.v, label: p.label, icon: p.Icon }))}
          block
        />
      )}

      {/* List with previews */}
      {items.length > 0 && (
        <div className="space-y-1.5">
          {items.map((it, i) => {
            const meta = KIND_META[it.kind] || KIND_META.photo;
            const url = isUrl(it.fid) ? it.fid : null;
            return (
              <div key={i} className="flex items-center gap-2 bg-sf2 border border-bd rounded-xl p-2">
                {/* Preview */}
                <div className={`w-12 h-12 rounded-lg overflow-hidden flex items-center justify-center bg-${meta.color}-100 flex-shrink-0`}>
                  {url ? (
                    it.kind === 'video' ? (
                      <video src={url} className="w-full h-full object-cover" muted />
                    ) : (
                      <img src={url} alt="" className="w-full h-full object-cover" />
                    )
                  ) : (
                    <meta.Icon size={16} className={`text-${meta.color}-600`} />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] font-black text-tx">{meta.label}</div>
                  <div className="text-[10px] text-lbl font-mono truncate">
                    {url ? url.split('/').pop() : it.fid}
                  </div>
                </div>
                <div className="flex items-center gap-0.5">
                  <button onClick={() => moveItem(i, -1)} disabled={i === 0}
                    className="p-1 text-lbl hover:text-cta disabled:opacity-30">
                    <ArrowUp size={11} />
                  </button>
                  <button onClick={() => moveItem(i, 1)} disabled={i === items.length - 1}
                    className="p-1 text-lbl hover:text-cta disabled:opacity-30">
                    <ArrowDown size={11} />
                  </button>
                  <button onClick={() => removeItem(i)}
                    className="p-1 text-lbl hover:text-danger hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] rounded">
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {error && (
        <div className="text-xs text-danger bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] border border-[color-mix(in_oklab,var(--danger)_30%,transparent)] rounded-xl px-3 py-2">
          {error}
        </div>
      )}

      {/* Upload buttons */}
      {items.length < maxItems && (
        uploading ? (
          <div className="flex items-center justify-center gap-2 py-3 border-2 border-dashed border-[color-mix(in_oklab,var(--cta)_40%,transparent)] rounded-xl">
            <Loader2 size={14} className="animate-spin text-cta"/>
            <span className="text-sm text-cta font-bold">Загрузка…</span>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(KIND_META).map(([k, m]) => (
              <button key={k} onClick={() => pickFile(k)}
                className={`flex flex-col items-center justify-center gap-1 py-3 border-2 border-bd2 rounded-xl text-xs font-bold text-txd hover:border-${m.color}-300 hover:bg-${m.color}-50 transition-all active:scale-95`}>
                <m.Icon size={18} className={`text-${m.color}-500`} />
                <span>{m.label}</span>
              </button>
            ))}
          </div>
        )
      )}

      {items.length < maxItems && !uploading && (
        <p className="text-[10px] text-lbl text-center">
          Загружено: {items.length}/{maxItems}. Поддерживается: JPG, PNG, WEBP, MP4, GIF.
        </p>
      )}
    </div>
  );
}
