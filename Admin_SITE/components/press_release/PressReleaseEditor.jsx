import { useState, useEffect, useMemo, useRef, forwardRef, useImperativeHandle } from 'react';
import {
  Save, X, Send, Trash2, Copy, RotateCcw, FileText, Palette,
  Image as ImageIcon, Calendar, Settings as SettingsIcon, ChevronDown, ChevronUp,
  Bold, Plus, GripVertical, Link as LinkIcon, MousePointerClick, AlertTriangle,
  CheckCircle2, Pin, EyeOff, BellOff, Lock, Megaphone, Eye, RefreshCw, ArrowUp
} from 'lucide-react';
import DateTimePicker from '../shared/DateTimePicker';
import RichTextEditor from '../shared/RichTextEditor';
import MediaBlock from '../shared/MediaBlock';
import StyledSelect from '../shared/StyledSelect';
import Button from '../shared/Button';
import ButtonGroup from '../shared/ButtonGroup';
import Toggle from '../shared/Toggle';
import Stepper from '../shared/Stepper';
import Card from '../shared/Card';
import BrandingPanel from './BrandingPanel';

// Этапы пресс-релиза для Stepper. Edge-кейсы (failed/cancelled) показываем
// отдельным баннером, в потоке степпера их нет.
const STATUS_STEPS = [
  { id: 'draft',     label: 'Черновик',     icon: FileText, color: 'blue'    },
  { id: 'scheduled', label: 'Запланирован', icon: Calendar, color: 'violet'  },
  { id: 'published', label: 'Опубликован',  icon: Send,     color: 'emerald' },
];

const TEXT_LIMIT      = 4096;
const CAPTION_LIMIT   = 1024;
const MAX_MEDIA       = 5;

const HEADER_OPEN  = '<!--HEADER-->';
const HEADER_CLOSE = '<!--/HEADER-->';
const SETTINGS_DEFAULTS = {
  pin: false,
  disable_preview: false,
  disable_notify: false,
  content_protection: false,
  media_position: 'above',                // above / below / reply
  delete_after_publish: { enabled: false, value: 1, unit: 'days' },
  throttle: { enabled: false, limit_per_hour: 5 },
};

function makeBlankPost() {
  return {
    id: null,
    title: '',
    text: '',
    photo_file_id: '',
    publish_at: null,
    status: 'draft',
    signature: '',
    bold_header: 1,
    add_signature: 1,
    inline_keyboard: [],
    settings_json: SETTINGS_DEFAULTS,
    pre_publish_reminder: 0,
    template_id: null,
    targets: [],
  };
}

// ── Section wrapper ──────────────────────────────────────────────
// Использует общий Card как обёртку — единый радиус/тень/бордер всей DS.
function Section({ icon: Icon, title, children, right, dragHandle }) {
  return (
    <Card padding="md" className="space-y-3">
      <div className="flex items-center gap-2">
        {dragHandle}
        {Icon && <Icon size={16} className="text-cta" />}
        <h3 className="text-xs font-black uppercase tracking-widest text-tx">{title}</h3>
        {right && <div className="ml-auto">{right}</div>}
      </div>
      {children}
    </Card>
  );
}

// ── Draggable wrapper ────────────────────────────────────────────
// Делаем draggable ТОЛЬКО саму иконку-ручку (GripVertical), а не
// родительский div. Это предотвращает любые проблемы с фокусом и
// текстовым вводом в input/textarea/contentEditable внутри секции.
function DraggableSection({ id, onDragStart, onDragOver, onDrop, isDraggingOver, children }) {
  const handle = (
    <span
      draggable
      onDragStart={(e) => {
        try {
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', id);
        } catch {}
        onDragStart(e, id);
      }}
      onDragEnd={(e) => { e.preventDefault(); }}
      className="cursor-grab active:cursor-grabbing text-lbl hover:text-txd select-none"
      title="Перетащить за иконку"
    >
      <GripVertical size={14}/>
    </span>
  );

  return (
    <div
      onDragOver={(e) => {
        // Принимаем drop только если идёт перетаскивание секции
        e.preventDefault();
        onDragOver(e, id);
      }}
      onDrop={(e) => {
        e.preventDefault();
        onDrop(e, id);
      }}
      className={`transition-all ${isDraggingOver ? 'ring-2 ring-blue-300 rounded-2xl' : ''}`}
    >
      {typeof children === 'function' ? children(handle) : children}
    </div>
  );
}

const DEFAULT_SECTION_ORDER = ['name', 'media', 'content', 'branding', 'publish', 'keyboard', 'settings'];

function getStoredOrder(userId) {
  try {
    const raw = localStorage.getItem(`pr_section_order_${userId || 'guest'}`);
    if (!raw) return DEFAULT_SECTION_ORDER;
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return DEFAULT_SECTION_ORDER;
    // Сливаем с дефолтом — добавляем недостающие в конец, отбрасываем неизвестные
    const known = arr.filter(id => DEFAULT_SECTION_ORDER.includes(id));
    const missing = DEFAULT_SECTION_ORDER.filter(id => !known.includes(id));
    return [...known, ...missing];
  } catch { return DEFAULT_SECTION_ORDER; }
}

function saveOrder(userId, order) {
  try { localStorage.setItem(`pr_section_order_${userId || 'guest'}`, JSON.stringify(order)); } catch {}
}

// ── Targets (multi-select) ───────────────────────────────────────
function TargetsPicker({ chats, value, onChange }) {
  const [collapsed, setCollapsed] = useState(() => {
    const st = {};
    if (chats?.length > 1) {
      chats.forEach(c => { st[c.chat_id] = true; });
    }
    return st;
  });

  const toggleCollapse = (e, chat_id) => {
    e.preventDefault();
    e.stopPropagation();
    setCollapsed(prev => ({ ...prev, [chat_id]: !prev[chat_id] }));
  };

  const toggleTarget = (chat_id, thread_id = null) => {
    const exists = value.some(t => t.chat_id === chat_id && (t.thread_id || null) === (thread_id || null));
    if (exists) {
      onChange(value.filter(t => !(t.chat_id === chat_id && (t.thread_id || null) === (thread_id || null))));
    } else {
      onChange([...value, { chat_id, thread_id }]);
    }
  };

  const isSelected = (chat_id, thread_id = null) =>
    value.some(t => t.chat_id === chat_id && (t.thread_id || null) === (thread_id || null));

  if (!chats?.length) {
    return (
      <div className="text-sm text-lbl italic py-3">
        Список чатов пуст. Бот должен быть добавлен хотя бы в один чат/канал.
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
      {chats.map(chat => {
        const chatIcon = chat.type === 'channel' ? '📢' : (chat.is_forum ? '🏛' : '👥');
        const isCollapsed = collapsed[chat.chat_id];
        return (
          <div key={chat.chat_id} className="border border-bd rounded-xl overflow-hidden">
            <div className="flex items-center hover:bg-sf2 pr-3">
              <label className="flex items-center gap-2 p-3 cursor-pointer flex-1 min-w-0">
                <input
                  type="checkbox"
                  checked={isSelected(chat.chat_id)}
                  onChange={() => toggleTarget(chat.chat_id, null)}
                  className="w-4 h-4 accent-blue-500 flex-shrink-0"
                />
                <span className="text-base flex-shrink-0">{chatIcon}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-tx truncate">{chat.title || `chat ${chat.chat_id}`}</div>
                  {chat.username && <div className="text-[10px] text-lbl truncate">@{chat.username}</div>}
                </div>
              </label>
              {chat.is_forum && chat.topics?.length > 0 && (
                <button 
                  type="button"
                  onClick={(e) => toggleCollapse(e, chat.chat_id)}
                  className="p-1.5 hover:bg-sf3 rounded-lg text-lbl transition-colors ml-2 flex-shrink-0"
                  title={isCollapsed ? "Развернуть ветки" : "Свернуть ветки"}
                >
                  {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                </button>
              )}
            </div>
            {chat.is_forum && chat.topics?.length > 0 && !isCollapsed && (
              <div className="border-t border-bd bg-sf2 px-3 py-2 space-y-1">
                <div className="text-[9px] font-black uppercase tracking-widest text-lbl">Топики</div>
                {chat.topics.map(t => (
                  <label key={t.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isSelected(chat.chat_id, t.thread_id)}
                      onChange={() => toggleTarget(chat.chat_id, t.thread_id)}
                      className="w-3.5 h-3.5 accent-blue-500 flex-shrink-0"
                    />
                    <span className="text-xs text-txd truncate">🧵 {t.name || `Топик #${t.thread_id}`}</span>
                    {t.source === 'manual' && (
                      <span className="text-[8px] font-black uppercase text-purple flex-shrink-0">manual</span>
                    )}
                  </label>
                ))}
              </div>
            )}
            {chat.is_forum && (!chat.topics || chat.topics.length === 0) && (
              <div className="border-t border-bd bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] px-3 py-2">
                <div className="text-[10px] text-warn leading-relaxed">
                  📋 Топики собираются автоматически при сообщениях. Можно добавить вручную.
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Inline keyboard editor (basic) ───────────────────────────────
function KeyboardEditor({ keyboard, onChange }) {
  const addBtn = () => {
    const next = keyboard.length === 0
      ? [[{ text: '', type: 'url', value: '' }]]
      : [...keyboard.slice(0, -1), [...keyboard[keyboard.length - 1], { text: '', type: 'url', value: '' }]];
    onChange(next);
  };
  const newRow = () => onChange([...keyboard, []]);
  const updBtn = (ri, bi, patch) => onChange(keyboard.map((row, i) => i !== ri ? row :
    row.map((b, j) => j !== bi ? b : { ...b, ...patch })));
  const remove = (ri, bi) => {
    const next = keyboard.map((row, i) => i !== ri ? row : row.filter((_, j) => j !== bi));
    onChange(next.filter(r => r.length));
  };

  if (keyboard.length === 0) {
    return (
      <button onClick={addBtn}
        className="w-full py-3 bg-sf2 border-2 border-dashed border-bd2 rounded-xl text-sm font-bold text-lbl hover:bg-sf2 transition-all">
        <Plus size={14} className="inline mr-1" /> Добавить кнопку
      </button>
    );
  }

  return (
    <div className="space-y-2">
      {keyboard.map((row, ri) => (
        <div key={ri} className="flex flex-wrap gap-2 items-center">
          {row.map((btn, bi) => (
            <div key={bi} className="flex-1 min-w-[200px] bg-sf2 rounded-xl p-2 border border-bd space-y-1.5">
              <div className="flex items-center gap-1.5">
                <StyledSelect
                  value={btn.type}
                  onChange={(v) => updBtn(ri, bi, { type: v })}
                  options={[
                    { value: 'url',      label: 'URL' },
                    { value: 'callback', label: 'Callback (в разработке)' },
                  ]}
                  size="sm"
                />
                <button onClick={() => remove(ri, bi)} className="ml-auto text-lbl hover:text-red-400">
                  <X size={12} />
                </button>
              </div>
              <input value={btn.text} onChange={(e) => updBtn(ri, bi, { text: e.target.value })}
                placeholder="📢 Текст кнопки"
                className="w-full px-2 py-1.5 text-xs font-bold bg-sff border border-bd rounded-lg focus:outline-none focus:border-[color-mix(in_oklab,var(--cta)_40%,transparent)]" />
              <input value={btn.value} onChange={(e) => updBtn(ri, bi, { value: e.target.value })}
                placeholder={btn.type === 'url' ? 'https://...' : 'pulses_get'}
                className="w-full px-2 py-1.5 text-xs bg-sff border border-bd rounded-lg focus:outline-none focus:border-[color-mix(in_oklab,var(--cta)_40%,transparent)]" />
              {btn.type === 'callback' && (
                <div className="text-[10px] text-amber-500 font-bold px-1 bg-amber-500/10 rounded">
                  ⚠️ В разработке: обработка кликов пока недоступна
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
      <div className="flex gap-2">
        <button onClick={addBtn} className="flex-1 py-2 bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] text-cta rounded-xl text-xs font-bold hover:bg-[color-mix(in_oklab,var(--cta)_16%,transparent)]">
          <Plus size={12} className="inline mr-1" /> Кнопка в этот ряд
        </button>
        <button onClick={newRow} className="flex-1 py-2 bg-sf2 text-txd rounded-xl text-xs font-bold hover:bg-bd2">
          + Новый ряд
        </button>
      </div>
    </div>
  );
}

// ── Главный компонент ───────────────────────────────────────────
const PressReleaseEditor = forwardRef(function PressReleaseEditor({
  api, chats, branding, post, onSaved, onClose, userCan, token, onBrandingChange, userId,
}, ref) {
  const [sectionOrder, setSectionOrder] = useState(() => getStoredOrder(userId));
  const [dragOverId, setDragOverId]     = useState(null);
  const draggedIdRef = useRef(null);

  const handleDragStart = (e, id) => {
    draggedIdRef.current = id;
    try { e.dataTransfer.effectAllowed = 'move'; } catch {}
  };
  const handleDragOver = (e, id) => {
    e.preventDefault();
    if (dragOverId !== id) setDragOverId(id);
  };
  const handleDrop = (e, id) => {
    e.preventDefault();
    const from = draggedIdRef.current;
    setDragOverId(null);
    draggedIdRef.current = null;
    if (!from || from === id) return;
    setSectionOrder(prev => {
      const next = [...prev];
      const fromIdx = next.indexOf(from);
      const toIdx   = next.indexOf(id);
      if (fromIdx < 0 || toIdx < 0) return prev;
      next.splice(fromIdx, 1);
      next.splice(toIdx, 0, from);
      saveOrder(userId, next);
      return next;
    });
  };
  const resetOrder = () => {
    setSectionOrder(DEFAULT_SECTION_ORDER);
    saveOrder(userId, DEFAULT_SECTION_ORDER);
  };
  const [draft, setDraft] = useState(() => post || makeBlankPost());
  // savingAction/doneAction — для stateful-кнопок (loading/done на конкретной кнопке)
  const [savingAction, setSavingAction] = useState(null);   // 'draft' | 'scheduled' | 'published' | null
  const [doneAction, setDoneAction]     = useState(null);
  const [publishMenuOpen, setPublishMenuOpen] = useState(false);
  const publishMenuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (publishMenuRef.current && !publishMenuRef.current.contains(e.target)) {
        setPublishMenuOpen(false);
      }
    }
    if (publishMenuOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [publishMenuOpen]);   // то же
  const saving = savingAction !== null;
  const [showSettings, setShowSettings] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [autosaveStatus, setAutosaveStatus] = useState('idle'); // idle/saving/saved
  const lastSavedRef = useRef(null);
  const initialRef   = useRef(JSON.stringify(post || makeBlankPost()));

  const isDirty = JSON.stringify(draft) !== initialRef.current;

  // Прокидываем наверх возможность спросить «сохранить?»
  useImperativeHandle(ref, () => ({
    isDirty: () => isDirty,
    saveCurrent: async () => {
      if (!isDirty) return true;
      try {
        await handleSave(draft.status || 'draft');
        return true;
      } catch { return false; }
    },
    discardChanges: () => {
      initialRef.current = JSON.stringify(draft);
    },
  }), [isDirty, draft]);

  // Подгружаем post если выбран существующий
  useEffect(() => {
    const next = post || makeBlankPost();
    setDraft(next);
    initialRef.current = JSON.stringify(next);
  }, [post?.id]);

  // Защита от закрытия вкладки браузера
  useEffect(() => {
    const handler = (e) => {
      if (isDirty) { e.preventDefault(); e.returnValue = ''; }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const settings = { ...SETTINGS_DEFAULTS, ...(draft.settings_json || {}) };
  const upd = (patch) => setDraft(prev => ({ ...prev, ...patch }));
  const updSettings = (patch) => setDraft(prev => ({
    ...prev, settings_json: { ...settings, ...patch }
  }));

  // Счётчики
  const textLen = (draft.text || '').length;
  const mediaList = (draft.photo_file_id || '').split('|').filter(Boolean);
  const isOverLimit = textLen > TEXT_LIMIT;
  const isOverCaption = textLen > CAPTION_LIMIT && mediaList.length > 0;

  // Авто-сохранение каждые 30 секунд (только для существующих)
  useEffect(() => {
    if (!draft.id) return;
    const t = setInterval(async () => {
      const snap = JSON.stringify(draft);
      if (lastSavedRef.current === snap) return;
      try {
        setAutosaveStatus('saving');
        await api.update(draft.id, draftToBody(draft));
        lastSavedRef.current = snap;
        setAutosaveStatus('saved');
        setTimeout(() => setAutosaveStatus('idle'), 1500);
      } catch (e) {
        setAutosaveStatus('idle');
      }
    }, 30000);
    return () => clearInterval(t);
  }, [draft]);

  // Ручное сохранение
  const handleSave = async (newStatus) => {
    const action = newStatus || draft.status || 'draft';
    setSavingAction(action);
    try {
      const body = { ...draftToBody(draft), status: action };
      let saved;
      if (draft.id) {
        saved = await api.update(draft.id, body);
      } else {
        saved = await api.create(body);
      }
      if (saved._flood_warning) {
        alert(saved._flood_warning);
      }
      onSaved?.(saved);
      setDraft(saved);
      // Pop-галочка на 1.5с
      setDoneAction(action);
      setTimeout(() => setDoneAction(null), 1500);
      return saved; // Возвращаем для handlePublishNow
    } catch (e) {
      alert('Ошибка сохранения: ' + (e?.detail || e?.message || e));
    } finally {
      setSavingAction(null);
    }
  };

  const handlePublishNow = async () => {
    if (!draft.id) {
      const saved = await handleSave('draft');
      if (!saved) return;
    }
    if (!confirm('Опубликовать сейчас?')) return;
    setSavingAction('published');
    try {
      const publishedPost = await api.publishNow(draft.id);
      if (publishedPost && publishedPost._flood_warning) {
        alert(publishedPost._flood_warning);
      }
      onSaved?.({ ...draft, status: 'published' });
      setDoneAction('published');
      setTimeout(() => setDoneAction(null), 1500);
    } catch (e) { alert('Ошибка: ' + (e?.detail || e)); }
    finally { setSavingAction(null); }
  };

  const handleDelete = async () => {
    if (!draft.id || !confirm('Удалить пресс-релиз?')) return;
    await api.remove(draft.id);
    onSaved?.(null);
    onClose?.();
  };

  // Вставить шапку (контент в пунктирной рамке)
  const insertHeader = () => {
    const cur = draft.text || '';
    if (cur.includes(HEADER_OPEN)) return;
    const placeholder = `${HEADER_OPEN}ЗАГОЛОВОК${HEADER_CLOSE}\n\n`;
    upd({ text: placeholder + cur });
  };

  // ── Рендер секции по id ──
  const renderSection = (sid, handle = null) => {
    switch (sid) {
      case 'name':
        return (
          <Section icon={FileText} title="Внутреннее имя" dragHandle={handle}>
            <input
              value={draft.title || ''}
              onChange={(e) => upd({ title: e.target.value })}
              placeholder="Например: Анонс эфира 7 мая"
              className="w-full px-4 py-3 bg-sf2 border-2 border-bd rounded-xl text-sm font-bold focus:outline-none focus:border-[color-mix(in_oklab,var(--cta)_40%,transparent)]"
            />
            <p className="text-[10px] text-lbl">Только для админки. В чате не отображается.</p>
          </Section>
        );

      case 'media':
        return (
          <Section
            icon={ImageIcon} title="Медиа" dragHandle={handle}
            right={<span className="text-[10px] font-black text-lbl">{mediaList.length}/{MAX_MEDIA}</span>}
          >
            <MediaBlock
              value={draft.photo_file_id || ''}
              onChange={(s) => upd({ photo_file_id: s })}
              maxItems={MAX_MEDIA}
              position={settings.media_position || 'above'}
              onPositionChange={(p) => updSettings({ media_position: p })}
              showPosition={mediaList.length > 0}
            />
          </Section>
        );

      case 'content':
        return (
          <Section
            icon={FileText} title="Содержимое" dragHandle={handle}
            right={
              <Button variant="outlined" size="sm" icon={Eye} onClick={() => setShowPreview(true)}>
                Превью
              </Button>
            }
          >
            <RichTextEditor
              value={draft.text || ''}
              onChange={(html) => upd({ text: html })}
              placeholder="Введите текст пресс-релиза…"
              maxLength={mediaList.length > 0 ? CAPTION_LIMIT : TEXT_LIMIT}
              showHeaderButton
              onInsertHeader={insertHeader}
              onPreview={() => setShowPreview(true)}
              minHeight={200}
            />
            {(isOverLimit || isOverCaption) && (
              <div className="flex items-start gap-2 px-3 py-2 bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] rounded-xl text-[11px] text-warn mt-2">
                <AlertTriangle size={12} className="flex-shrink-0 mt-0.5"/>
                <div>
                  {isOverLimit
                    ? `Текст ${textLen} симв. > ${TEXT_LIMIT} — Telegram разделит на части по абзацам.`
                    : `Текст ${textLen} симв. > ${CAPTION_LIMIT} (caption под медиа) — пойдёт отдельным сообщением после медиа.`}
                </div>
              </div>
            )}
          </Section>
        );

      case 'branding':
        return (
          <Section icon={Palette} title="Подпись и брендинг" dragHandle={handle}>
            <BrandingPanel token={token} onChange={onBrandingChange} compact />
          </Section>
        );

      case 'publish':
        return (
          <Section icon={Calendar} title="Куда + Когда" dragHandle={handle}>
            <PublishBlock
              chats={chats}
              targets={draft.targets || []}
              onTargetsChange={(t) => upd({ targets: t })}
              publishAt={draft.publish_at}
              onPublishAtChange={(iso) => upd({ publish_at: iso })}
              reminder={draft.pre_publish_reminder || 0}
              onReminderChange={(v) => upd({ pre_publish_reminder: v })}
            />
          </Section>
        );

      case 'keyboard':
        return (
          <Section icon={MousePointerClick} title="Inline-клавиатура" dragHandle={handle}>
            <KeyboardEditor
              keyboard={draft.inline_keyboard || []}
              onChange={(kb) => upd({ inline_keyboard: kb })}
            />
          </Section>
        );

      case 'settings':
        return (
          <Section
            icon={SettingsIcon} title="Настройки публикации" dragHandle={handle}
            right={
              <Button variant="ghost" size="sm" icon={showSettings ? ChevronUp : ChevronDown}
                onClick={() => setShowSettings(s => !s)}
                aria-label={showSettings ? 'Свернуть настройки' : 'Развернуть настройки'} />
            }
          >
            {showSettings && (
              <div className="space-y-1">
                <Toggle icon={Pin}     label="Закрепить после публикации"  checked={settings.pin}                 onChange={(v) => updSettings({ pin: v })} />
                <Toggle icon={EyeOff}  label="Без превью ссылок"            checked={settings.disable_preview}     onChange={(v) => updSettings({ disable_preview: v })} />
                <Toggle icon={BellOff} label="Тихая отправка (без звука)"   checked={settings.disable_notify}      onChange={(v) => updSettings({ disable_notify: v })} />
                <Toggle icon={Lock}    label="Защита контента (запрет копирования)" checked={settings.content_protection}  onChange={(v) => updSettings({ content_protection: v })} />
                <div className="border-t border-bd my-2" />
                <Toggle label="Жирная шапка"
                  hint="Первая строка текста выделяется жирным"
                  checked={!!draft.bold_header} onChange={(v) => upd({ bold_header: v ? 1 : 0 })} />
                <Toggle label="Добавить подпись"
                  hint="Подпись будет добавлена в конец сообщения согласно глобальным настройкам"
                  checked={!!draft.add_signature} onChange={(v) => upd({ add_signature: v ? 1 : 0 })} />
                <div className="border-t border-bd my-2" />
                <Toggle label="Авто-удаление из Telegram"
                  checked={settings.delete_after_publish?.enabled}
                  onChange={(v) => updSettings({ delete_after_publish: { ...settings.delete_after_publish, enabled: v }})} />
                {settings.delete_after_publish?.enabled && (
                  <div className="ml-12 flex items-center gap-2">
                    <input type="number" min="1" value={settings.delete_after_publish?.value || 1}
                      onChange={(e) => updSettings({ delete_after_publish: { ...settings.delete_after_publish, value: parseInt(e.target.value, 10) || 1 }})}
                      className="w-16 px-2 py-1 bg-sf2 border border-bd rounded-lg text-xs font-bold focus:outline-none focus:border-[color-mix(in_oklab,var(--cta)_40%,transparent)]" />
                    <StyledSelect
                      value={settings.delete_after_publish?.unit || 'days'}
                      onChange={(v) => updSettings({ delete_after_publish: { ...settings.delete_after_publish, unit: v }})}
                      options={[
                        { value: 'minutes', label: 'минут' },
                        { value: 'hours',   label: 'часов' },
                        { value: 'days',    label: 'дней'  },
                      ]}
                      size="sm"
                    />
                  </div>
                )}
                <div className="border-t border-bd my-2" />
                <Toggle label="Throttling (не спамить)"
                  hint="Лимит N релизов в час от одного автора"
                  checked={settings.throttle?.enabled}
                  onChange={(v) => updSettings({ throttle: { ...settings.throttle, enabled: v }})} />
                {settings.throttle?.enabled && (
                  <div className="ml-12 flex items-center gap-2">
                    <span className="text-xs font-bold text-tx">Не более</span>
                    <input type="number" min="1" value={settings.throttle?.limit_per_hour || 5}
                      onChange={(e) => updSettings({ throttle: { ...settings.throttle, limit_per_hour: parseInt(e.target.value, 10) || 5 }})}
                      className="w-16 px-2 py-1 bg-sf2 border border-bd rounded-lg text-xs font-bold focus:outline-none focus:border-[color-mix(in_oklab,var(--cta)_40%,transparent)]" />
                    <span className="text-xs font-bold text-tx">в час</span>
                  </div>
                )}
              </div>
            )}
          </Section>
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-3 pb-24">
      {/* ── Шапка действий ── */}
      <div className="bg-sff rounded-2xl border border-bd shadow-sm p-3 flex items-center gap-2 relative z-20 mb-4">
        <Button variant="ghost" size="sm" icon={X} onClick={onClose} aria-label="Закрыть" />
        <div className="flex-1 min-w-0 flex items-center gap-2">
          <div className="text-sm font-black text-tx truncate">
            {draft.title || 'Новый пресс-релиз'}
          </div>
          {autosaveStatus === 'saving' && <span className="text-[10px] text-lbl">сохранение…</span>}
          {autosaveStatus === 'saved'   && <span className="text-[10px] text-ok flex items-center gap-1"><CheckCircle2 size={10}/> сохранено</span>}
        </div>
        <Button
          variant="secondary" size="sm" icon={Save}
          state={savingAction === 'draft' ? 'loading' : doneAction === 'draft' ? 'done' : 'idle'}
          loadingLabel="Сохраняю…"
          onClick={() => handleSave('draft')}
          disabled={saving}
        >
          Черновик
        </Button>
        
        {/* Сплит-кнопка Запланировать / Опубликовать сейчас */}
        <div className="relative flex" ref={publishMenuRef}>
          <Button
            variant="primary" size="sm" icon={Calendar}
            state={savingAction === 'scheduled' ? 'loading' : doneAction === 'scheduled' ? 'done' : 'idle'}
            loadingLabel="Сохраняю…"
            onClick={() => handleSave('scheduled')}
            disabled={saving || !draft.publish_at || draft.targets?.length === 0}
            className={userCan('press_release.publish_now') ? '!rounded-r-none' : ''}
          >
            {draft.status === 'scheduled' ? 'Перепланировать' : 'Запланировать'}
          </Button>
          {userCan('press_release.publish_now') && (
            <button
              onClick={() => setPublishMenuOpen(!publishMenuOpen)}
              className="px-2.5 bg-cta text-white hover:brightness-110 border-l border-white/20 !rounded-l-none rounded-r-2xl transition-all disabled:opacity-50 flex items-center justify-center pulse-btn-glow"
              style={{ '--glow-from': '#3b82f6', '--glow-via': '#a855f7', '--glow-to': '#3b82f6' }}
              disabled={saving}
              title="Дополнительные действия"
            >
              <ChevronDown size={16} />
            </button>
          )}

          {publishMenuOpen && userCan('press_release.publish_now') && (
            <div className="absolute top-full right-0 mt-2 w-56 bg-sff border border-bd shadow-xl rounded-xl overflow-hidden z-30 animate-in fade-in slide-in-from-top-2 duration-200">
              <button
                onClick={() => { setPublishMenuOpen(false); handlePublishNow(); }}
                disabled={saving || draft.targets?.length === 0 || draft.status === 'published'}
                className="w-full text-left px-4 py-3 hover:bg-ih text-sm font-bold flex items-center gap-2 disabled:opacity-50 text-tx transition-colors"
              >
                <Send size={16} className="text-cta" />
                {draft.status === 'published' ? 'Опубликован' : 'Опубликовать сейчас'}
              </button>
            </div>
          )}
        </div>
        {draft.id && (
          <Button variant="ghost" size="sm" icon={Trash2} onClick={handleDelete}
            aria-label="Удалить" className="text-red-400 hover:text-danger hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)]" />
        )}
        {!draft.id && (
          <Button variant="ghost" size="sm" icon={Trash2} onClick={() => {
            if (confirm('Очистить форму?')) {
              setDraft(makeBlankPost());
              initialRef.current = JSON.stringify(makeBlankPost());
            }
          }} aria-label="Очистить форму" className="text-red-400 hover:text-danger hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)]" />
        )}
      </div>

      {/* ── Stepper статуса публикации ── */}
      {(draft.status === 'failed' || draft.status === 'cancelled') ? (
        <div className={`rounded-2xl border px-4 py-3 flex items-center gap-3 ${
          draft.status === 'failed'
            ? 'bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] border-[color-mix(in_oklab,var(--danger)_40%,transparent)] text-danger'
            : 'bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] border-[color-mix(in_oklab,var(--warn)_40%,transparent)] text-warn'
        }`}>
          <AlertTriangle size={18} className="flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-black">
              {draft.status === 'failed' ? 'Публикация упала с ошибкой' : 'Публикация отменена'}
            </div>
            <div className="text-[11px] opacity-80 mt-0.5">
              {draft.status === 'failed'
                ? 'Проверьте таргеты и попробуйте опубликовать заново.'
                : 'Запланированная отправка была отменена. Можно перепланировать или удалить.'}
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-sff rounded-2xl border border-bd shadow-sm px-6 py-3">
          <Stepper
            steps={STATUS_STEPS}
            current={draft.status || 'draft'}
          />
        </div>
      )}

      {/* Подсказка о drag&drop + сброс */}
      <div className="flex items-center justify-between bg-blue-50/60 border border-[color-mix(in_oklab,var(--cta)_30%,transparent)] rounded-xl px-3 py-2">
        <span className="text-[10px] text-cta font-bold">
          🎯 Перетащите секции за иконку <GripVertical size={10} className="inline"/> чтобы расположить как удобно
        </span>
        <Button variant="link" size="sm" icon={RefreshCw} onClick={resetOrder}>
          сброс
        </Button>
      </div>

      {sectionOrder.map((sid) => (
        <DraggableSection
          key={sid}
          id={sid}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          isDraggingOver={dragOverId === sid}
        >
          {(handle) => renderSection(sid, handle)}
        </DraggableSection>
      ))}

      {/* Preview modal */}
      {showPreview && (
        <PreviewModal
          draft={draft}
          settings={settings}
          mediaList={mediaList}
          branding={branding}
          onClose={() => setShowPreview(false)}
        />
      )}

      {/* Scroll to Top FAB */}
      <button
        onClick={() => {
          const editorContainer = document.querySelector('.custom-scrollbar');
          if (editorContainer) editorContainer.scrollTo({ top: 0, behavior: 'smooth' });
          else window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        className="fixed bottom-8 right-8 w-12 h-12 bg-cta text-white rounded-[1.2rem] shadow-xl flex items-center justify-center hover:scale-105 transition-all z-50 active:scale-95"
        title="Наверх"
      >
        <ArrowUp size={24} />
      </button>
    </div>
  );
});

export default PressReleaseEditor;

function PreviewModal({ draft, settings, mediaList, branding, onClose }) {
  const sig = draft.add_signature ? (draft.signature || branding?.signature || '') : '';
  let textHtml = draft.text || '';
  if (draft.bold_header && textHtml) {
    // Первый разрыв строки может быть \n, <br>, </div>, </p> — в зависимости
    // от того, что вставил contentEditable. Берём всё до первого такого разрыва.
    const m = textHtml.match(/\n|<br\s*\/?>|<\/div>|<\/p>/i);
    const cut   = m ? m.index : textHtml.length;
    const first = textHtml.slice(0, cut);
    const rest  = textHtml.slice(cut);
    if (first.replace(/<[^>]+>/g, '').trim() && !/<(b|strong)\b/i.test(first)) {
      textHtml = `<b>${first}</b>${rest}`;
    }
  }
  const fullHtml = sig ? `${textHtml}\n\n${sig}` : textHtml;
  const pos = settings.media_position || 'above';

  return (
    <div className="fixed inset-0 z-[200] bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-sff rounded-3xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-bd">
          <div className="flex items-center gap-2">
            <Eye size={14} className="text-cta" />
            <span className="text-xs font-black uppercase tracking-widest text-tx">Превью</span>
          </div>
          <button onClick={onClose} className="p-1 text-lbl hover:text-txd">
            <X size={16}/>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 bg-sf2">
          <div className="bg-sff rounded-2xl shadow-md p-3 space-y-2">
            {pos === 'above' && mediaList.length > 0 && (
              <div className="flex items-center justify-center bg-sf2 rounded-xl py-6 text-xs text-lbl font-bold">
                🖼 {mediaList.length} медиа · выше текста
              </div>
            )}
            <div className="text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: fullHtml || '<i class="text-lbl">Пусто…</i>' }} />
            {pos === 'below' && mediaList.length > 0 && (
              <div className="flex items-center justify-center bg-sf2 rounded-xl py-6 text-xs text-lbl font-bold">
                🖼 {mediaList.length} медиа · ниже текста
              </div>
            )}
            {(draft.inline_keyboard || []).length > 0 && (
              <div className="space-y-1 pt-2">
                {(draft.inline_keyboard || []).map((row, ri) => (
                  <div key={ri} className="flex gap-1">
                    {row.map((b, bi) => (
                      <button key={bi} className="flex-1 py-2 px-2 bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] text-cta rounded-lg text-xs font-bold border border-[color-mix(in_oklab,var(--cta)_30%,transparent)]">
                        {b.text || '(без текста)'}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="mt-3 text-[10px] text-lbl leading-relaxed space-y-1">
            <div>📍 {(draft.targets || []).length} получателей</div>
            <div>📏 {(draft.text || '').replace(/<[^>]+>/g, '').length} симв.</div>
            {pos === 'reply' && <div>💬 Медиа отправится отдельным реплаем</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Блок «Куда + Когда» (две вкладки) ──────────────
// Внешняя обёртка-карточка приходит от Section — здесь только содержимое.
function PublishBlock({ chats, targets, onTargetsChange, publishAt, onPublishAtChange, reminder, onReminderChange }) {
  const [tab, setTab] = useState(null);  // null / 'where' / 'when'
  const targetsCnt = targets?.length || 0;
  const dateLabel = publishAt
    ? new Date(publishAt).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
    : 'не задано';

  return (
    <div className="rounded-xl border border-bd">
      <div className="grid grid-cols-2">
        <button
          onClick={() => setTab(tab === 'where' ? null : 'where')}
          className={`flex items-center gap-2 p-3 transition-all ${tab === 'where' ? 'bg-[color-mix(in_oklab,var(--cta)_10%,transparent)]' : 'hover:bg-sf2'} rounded-tl-xl ${!tab ? 'rounded-bl-xl' : ''}`}>
          <Megaphone size={14} className={tab === 'where' ? 'text-cta' : 'text-lbl'} />
          <div className="flex-1 text-left min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-wider text-txd">Куда</div>
            <div className="text-sm font-black text-tx truncate">
              {targetsCnt === 0 ? <span className="text-red-400">не выбрано</span> : `${targetsCnt} получателей`}
            </div>
          </div>
        </button>
        <button
          onClick={() => setTab(tab === 'when' ? null : 'when')}
          className={`flex items-center gap-2 p-3 border-l border-bd transition-all ${tab === 'when' ? 'bg-[color-mix(in_oklab,var(--cta)_10%,transparent)]' : 'hover:bg-sf2'} rounded-tr-xl ${!tab ? 'rounded-br-xl' : ''}`}>
          <Calendar size={14} className={tab === 'when' ? 'text-cta' : 'text-lbl'} />
          <div className="flex-1 text-left min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-wider text-txd">Когда</div>
            <div className="text-sm font-black text-tx truncate">{dateLabel}</div>
          </div>
        </button>
      </div>
      {tab === 'where' && (
        <div className="border-t border-bd p-3 rounded-b-xl">
          <TargetsPicker chats={chats} value={targets} onChange={onTargetsChange} />
        </div>
      )}
      {tab === 'when' && (
        <div className="border-t border-bd p-3 space-y-2 rounded-b-xl">
          <DateTimePicker value={publishAt} onChange={onPublishAtChange} />
          <div className="flex items-center gap-2 pt-1">
            <label className="text-xs font-bold text-tx">Напомнить за:</label>
            <StyledSelect
              value={reminder}
              onChange={(v) => onReminderChange(parseInt(v, 10))}
              align="top"
              options={[
                { value: 0,  label: 'Не напоминать' },
                { value: 5,  label: '5 минут'       },
                { value: 15, label: '15 минут'      },
                { value: 60, label: '1 час'         },
              ]}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    draft:     ['bg-sf2 text-txd',     'Черновик'],
    scheduled: ['bg-[color-mix(in_oklab,var(--cta)_16%,transparent)] text-cta',     'Запланирован'],
    published: ['bg-[color-mix(in_oklab,var(--ok)_16%,transparent)] text-ok','Опубликован'],
    failed:    ['bg-[color-mix(in_oklab,var(--danger)_16%,transparent)] text-danger',       'Ошибка'],
    cancelled: ['bg-[color-mix(in_oklab,var(--warn)_16%,transparent)] text-warn',   'Отменён'],
  };
  const [cls, label] = map[status] || ['bg-sf2 text-txd', status];
  return <span className={`px-1.5 py-0.5 rounded ${cls} font-black uppercase`}>{label}</span>;
}

// ── helpers ─────────────────────────────────────────────────
function draftToBody(d) {
  return {
    title:                d.title,
    text:                 d.text,
    photo_file_id:        d.photo_file_id,
    publish_at:           d.publish_at,
    status:               d.status,
    signature:            d.signature,
    bold_header:          d.bold_header,
    add_signature:        d.add_signature,
    inline_keyboard:      d.inline_keyboard || [],
    settings_json:        d.settings_json || {},
    pre_publish_reminder: d.pre_publish_reminder || 0,
    template_id:          d.template_id,
    targets:              d.targets || [],
  };
}
