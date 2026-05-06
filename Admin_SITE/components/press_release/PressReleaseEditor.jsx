import { useState, useEffect, useMemo, useRef } from 'react';
import {
  Save, X, Send, Trash2, Copy, RotateCcw, FileText,
  Image as ImageIcon, Calendar, Settings as SettingsIcon, ChevronDown, ChevronUp,
  Bold, Plus, GripVertical, Link as LinkIcon, MousePointerClick, AlertTriangle,
  CheckCircle2, Pin, EyeOff, BellOff, Lock, Megaphone,
} from 'lucide-react';
import DateTimePicker from '../shared/DateTimePicker';

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
function Section({ icon: Icon, title, children, right }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-3">
      <div className="flex items-center gap-2">
        {Icon && <Icon size={16} className="text-blue-500" />}
        <h3 className="text-xs font-black uppercase tracking-widest text-gray-700">{title}</h3>
        {right && <div className="ml-auto">{right}</div>}
      </div>
      {children}
    </div>
  );
}

// ── Toggle ───────────────────────────────────────────────────────
function Toggle({ checked, onChange, label, hint, icon: Icon }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer py-1">
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange?.(e.target.checked)} className="hidden" />
      <div className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 mt-0.5 ${checked ? 'bg-blue-500' : 'bg-gray-200'}`}>
        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-[18px]' : 'translate-x-0.5'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
          {Icon && <Icon size={13} className="text-gray-500" />}
          {label}
        </div>
        {hint && <div className="text-[10px] text-gray-400 mt-0.5">{hint}</div>}
      </div>
    </label>
  );
}

// ── Targets (multi-select) ───────────────────────────────────────
function TargetsPicker({ chats, value, onChange }) {
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
      <div className="text-sm text-gray-400 italic py-3">
        Список чатов пуст. Бот должен быть добавлен хотя бы в один чат/канал.
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-72 overflow-y-auto">
      {chats.map(chat => {
        const chatIcon = chat.type === 'channel' ? '📢' : (chat.is_forum ? '🏛' : '👥');
        return (
          <div key={chat.chat_id} className="border border-gray-100 rounded-xl overflow-hidden">
            <label className="flex items-center gap-2 p-3 hover:bg-gray-50 cursor-pointer">
              <input
                type="checkbox"
                checked={isSelected(chat.chat_id)}
                onChange={() => toggleTarget(chat.chat_id, null)}
                className="w-4 h-4 accent-blue-500"
              />
              <span className="text-base">{chatIcon}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-gray-800 truncate">{chat.title || `chat ${chat.chat_id}`}</div>
                {chat.username && <div className="text-[10px] text-gray-400">@{chat.username}</div>}
              </div>
            </label>
            {chat.is_forum && chat.topics?.length > 0 && (
              <div className="border-t border-gray-100 bg-gray-50 px-3 py-2 space-y-1">
                <div className="text-[9px] font-black uppercase tracking-widest text-gray-400">Топики</div>
                {chat.topics.map(t => (
                  <label key={t.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isSelected(chat.chat_id, t.thread_id)}
                      onChange={() => toggleTarget(chat.chat_id, t.thread_id)}
                      className="w-3.5 h-3.5 accent-blue-500"
                    />
                    <span className="text-xs text-gray-600">🧵 {t.name || `Топик #${t.thread_id}`}</span>
                    {t.source === 'manual' && (
                      <span className="text-[8px] font-black uppercase text-purple-500">manual</span>
                    )}
                  </label>
                ))}
              </div>
            )}
            {chat.is_forum && (!chat.topics || chat.topics.length === 0) && (
              <div className="border-t border-gray-100 bg-amber-50 px-3 py-2">
                <div className="text-[10px] text-amber-700 leading-relaxed">
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
        className="w-full py-3 bg-gray-50 border-2 border-dashed border-gray-200 rounded-xl text-sm font-bold text-gray-400 hover:bg-gray-100 transition-all">
        <Plus size={14} className="inline mr-1" /> Добавить кнопку
      </button>
    );
  }

  return (
    <div className="space-y-2">
      {keyboard.map((row, ri) => (
        <div key={ri} className="flex flex-wrap gap-2 items-center">
          {row.map((btn, bi) => (
            <div key={bi} className="flex-1 min-w-[200px] bg-gray-50 rounded-xl p-2 border border-gray-100 space-y-1.5">
              <div className="flex items-center gap-1.5">
                <select value={btn.type} onChange={(e) => updBtn(ri, bi, { type: e.target.value })}
                  className="text-[10px] font-black uppercase px-1.5 py-1 bg-white rounded border border-gray-100 focus:outline-none focus:border-blue-200">
                  <option value="url">URL</option>
                  <option value="callback">Callback (бета)</option>
                </select>
                <button onClick={() => remove(ri, bi)} className="ml-auto text-gray-300 hover:text-red-400">
                  <X size={12} />
                </button>
              </div>
              <input value={btn.text} onChange={(e) => updBtn(ri, bi, { text: e.target.value })}
                placeholder="📢 Текст кнопки"
                className="w-full px-2 py-1.5 text-xs font-bold bg-white border border-gray-100 rounded-lg focus:outline-none focus:border-blue-200" />
              <input value={btn.value} onChange={(e) => updBtn(ri, bi, { value: e.target.value })}
                placeholder={btn.type === 'url' ? 'https://...' : 'pulses_get'}
                className="w-full px-2 py-1.5 text-xs bg-white border border-gray-100 rounded-lg focus:outline-none focus:border-blue-200" />
            </div>
          ))}
        </div>
      ))}
      <div className="flex gap-2">
        <button onClick={addBtn} className="flex-1 py-2 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold hover:bg-blue-100">
          <Plus size={12} className="inline mr-1" /> Кнопка в этот ряд
        </button>
        <button onClick={newRow} className="flex-1 py-2 bg-gray-100 text-gray-600 rounded-xl text-xs font-bold hover:bg-gray-200">
          + Новый ряд
        </button>
      </div>
    </div>
  );
}

// ── Главный компонент ───────────────────────────────────────────
export default function PressReleaseEditor({
  api, chats, branding, post, onSaved, onClose, userCan,
}) {
  const [draft, setDraft] = useState(() => post || makeBlankPost());
  const [saving, setSaving] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [autosaveStatus, setAutosaveStatus] = useState('idle'); // idle/saving/saved
  const lastSavedRef = useRef(null);

  // Подгружаем post если выбран существующий
  useEffect(() => { setDraft(post || makeBlankPost()); }, [post?.id]);

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
    setSaving(true);
    try {
      const body = { ...draftToBody(draft), status: newStatus || draft.status };
      let saved;
      if (draft.id) {
        saved = await api.update(draft.id, body);
      } else {
        saved = await api.create(body);
      }
      onSaved?.(saved);
      setDraft(saved);
    } catch (e) {
      alert('Ошибка сохранения: ' + (e?.detail || e?.message || e));
    } finally {
      setSaving(false);
    }
  };

  const handlePublishNow = async () => {
    if (!draft.id) {
      const saved = await handleSave('draft');
      if (!saved) return;
    }
    if (!confirm('Опубликовать сейчас?')) return;
    try {
      await api.publishNow(draft.id);
      onSaved?.({ ...draft, status: 'published' });
    } catch (e) { alert('Ошибка: ' + (e?.detail || e)); }
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

  return (
    <div className="space-y-3 pb-24">
      {/* ── Шапка действий ── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex items-center gap-2 sticky top-0 z-10">
        <button onClick={onClose} className="p-2 text-gray-400 hover:text-gray-600">
          <X size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-black text-gray-800 truncate">
            {draft.title || 'Новый пресс-релиз'}
          </div>
          <div className="flex items-center gap-2 text-[10px]">
            <StatusBadge status={draft.status} />
            {autosaveStatus === 'saving' && <span className="text-gray-400">сохранение…</span>}
            {autosaveStatus === 'saved'   && <span className="text-emerald-500 flex items-center gap-1"><CheckCircle2 size={10}/> сохранено</span>}
          </div>
        </div>
        <button onClick={() => handleSave('draft')} disabled={saving}
          className="px-3 py-2 bg-gray-100 text-gray-700 rounded-xl text-xs font-black hover:bg-gray-200 flex items-center gap-1">
          <Save size={12}/> Черновик
        </button>
        <button onClick={() => handleSave('scheduled')} disabled={saving || !draft.publish_at || draft.targets?.length === 0}
          className="px-3 py-2 bg-blue-500 text-white rounded-xl text-xs font-black hover:bg-blue-600 disabled:opacity-40 flex items-center gap-1">
          <Calendar size={12}/> Запланировать
        </button>
        {userCan('press_release.publish_now') && (
          <button onClick={handlePublishNow} disabled={saving || draft.targets?.length === 0}
            className="px-3 py-2 bg-emerald-500 text-white rounded-xl text-xs font-black hover:bg-emerald-600 disabled:opacity-40 flex items-center gap-1">
            <Send size={12}/> Сейчас
          </button>
        )}
        {draft.id && userCan('press_release.delete') && (
          <button onClick={handleDelete}
            className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-xl">
            <Trash2 size={14}/>
          </button>
        )}
      </div>

      {/* Имя */}
      <Section icon={FileText} title="Внутреннее имя">
        <input
          value={draft.title || ''}
          onChange={(e) => upd({ title: e.target.value })}
          placeholder="Например: Анонс эфира 7 мая"
          className="w-full px-4 py-3 bg-gray-50 border-2 border-gray-100 rounded-xl text-sm font-bold focus:outline-none focus:border-blue-200"
        />
        <p className="text-[10px] text-gray-400">Только для админки. В чате не отображается.</p>
      </Section>

      {/* Targets */}
      <Section
        icon={Megaphone}
        title="Куда публикуем"
        right={<span className="text-[10px] font-black text-gray-400">{draft.targets?.length || 0} выбрано</span>}
      >
        <TargetsPicker
          chats={chats}
          value={draft.targets || []}
          onChange={(targets) => upd({ targets })}
        />
      </Section>

      {/* Дата */}
      <Section icon={Calendar} title="Когда публикуем">
        <DateTimePicker
          value={draft.publish_at}
          onChange={(iso) => upd({ publish_at: iso })}
        />
        <div className="pt-2 flex items-center gap-3">
          <label className="text-xs font-bold text-gray-700">Напомнить за:</label>
          <select
            value={draft.pre_publish_reminder || 0}
            onChange={(e) => upd({ pre_publish_reminder: parseInt(e.target.value, 10) })}
            className="px-2 py-1.5 bg-gray-50 border border-gray-100 rounded-lg text-xs font-bold focus:outline-none focus:border-blue-200"
          >
            <option value={0}>Не напоминать</option>
            <option value={5}>5 минут</option>
            <option value={15}>15 минут</option>
            <option value={60}>1 час</option>
          </select>
        </div>
      </Section>

      {/* Текст */}
      <Section
        icon={FileText}
        title="Содержимое"
        right={
          <span className={`text-[10px] font-black ${isOverLimit ? 'text-red-500' : isOverCaption ? 'text-amber-500' : 'text-gray-400'}`}>
            {textLen}/{mediaList.length > 0 ? CAPTION_LIMIT : TEXT_LIMIT}
            {isOverCaption && !isOverLimit && ' · текст пойдёт отдельным сообщением'}
            {isOverLimit && ' · разделится на несколько сообщений'}
          </span>
        }
      >
        <div className="flex items-center gap-1.5 mb-2">
          <button onClick={insertHeader}
            className="px-2.5 py-1.5 bg-amber-50 text-amber-700 rounded-lg text-[10px] font-black uppercase hover:bg-amber-100 flex items-center gap-1">
            <Bold size={11}/> Шапка
          </button>
          <span className="text-[10px] text-gray-400 ml-1">— блок шапки выделится пунктиром</span>
        </div>
        <textarea
          value={draft.text || ''}
          onChange={(e) => upd({ text: e.target.value })}
          placeholder="Текст пресс-релиза. HTML поддерживается: <b>, <i>, <u>, <s>, <code>, <a href>"
          rows={10}
          className="w-full px-4 py-3 bg-gray-50 border-2 border-gray-100 rounded-xl text-sm font-mono focus:outline-none focus:border-blue-200 resize-y"
        />
        {(isOverLimit || isOverCaption) && (
          <div className="flex items-start gap-2 px-3 py-2 bg-amber-50 rounded-xl text-[11px] text-amber-700">
            <AlertTriangle size={12} className="flex-shrink-0 mt-0.5"/>
            <div>
              {isOverLimit
                ? `Текст ${textLen} симв. > ${TEXT_LIMIT} — Telegram разделит на части по абзацам.`
                : `Текст ${textLen} симв. > ${CAPTION_LIMIT} (caption под медиа) — пойдёт отдельным сообщением после медиа.`}
            </div>
          </div>
        )}
      </Section>

      {/* Медиа (file_id, до 5) */}
      <Section
        icon={ImageIcon}
        title="Медиа"
        right={<span className="text-[10px] font-black text-gray-400">{mediaList.length}/{MAX_MEDIA}</span>}
      >
        <textarea
          value={draft.photo_file_id || ''}
          onChange={(e) => upd({ photo_file_id: e.target.value })}
          placeholder='Формат: photo:AgACAg...|video:BAACAg... (можно оставить пустым)'
          rows={2}
          className="w-full px-4 py-2 bg-gray-50 border-2 border-gray-100 rounded-xl text-xs font-mono focus:outline-none focus:border-blue-200"
        />
        <p className="text-[10px] text-gray-400">
          file_id из Telegram. До {MAX_MEDIA} файлов через «|». Загрузка медиа с сайта — V2.
        </p>
      </Section>

      {/* Inline keyboard */}
      <Section icon={MousePointerClick} title="Inline-клавиатура">
        <KeyboardEditor
          keyboard={draft.inline_keyboard || []}
          onChange={(kb) => upd({ inline_keyboard: kb })}
        />
      </Section>

      {/* Settings */}
      <Section
        icon={SettingsIcon}
        title="Настройки публикации"
        right={
          <button onClick={() => setShowSettings(s => !s)} className="text-gray-400 hover:text-gray-600">
            {showSettings ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
          </button>
        }
      >
        {showSettings && (
          <div className="space-y-1">
            <Toggle icon={Pin}     label="Закрепить после публикации"  checked={settings.pin}                 onChange={(v) => updSettings({ pin: v })} />
            <Toggle icon={EyeOff}  label="Без превью ссылок"            checked={settings.disable_preview}     onChange={(v) => updSettings({ disable_preview: v })} />
            <Toggle icon={BellOff} label="Тихая отправка (без звука)"   checked={settings.disable_notify}      onChange={(v) => updSettings({ disable_notify: v })} />
            <Toggle icon={Lock}    label="Защита контента (запрет копирования)" checked={settings.content_protection}  onChange={(v) => updSettings({ content_protection: v })} />
            <div className="border-t border-gray-100 my-2" />
            <Toggle label="Жирная шапка"
              hint="Первая строка текста выделяется жирным"
              checked={!!draft.bold_header} onChange={(v) => upd({ bold_header: v ? 1 : 0 })} />
            <Toggle label="Добавить подпись"
              hint={branding?.signature ? `Текущая: ${branding.signature.slice(0,40)}…` : 'Подпись не задана в брендинге'}
              checked={!!draft.add_signature} onChange={(v) => upd({ add_signature: v ? 1 : 0 })} />
            <div className="border-t border-gray-100 my-2" />
            <Toggle label="Авто-удаление из Telegram"
              checked={settings.delete_after_publish?.enabled}
              onChange={(v) => updSettings({ delete_after_publish: { ...settings.delete_after_publish, enabled: v }})} />
            {settings.delete_after_publish?.enabled && (
              <div className="ml-12 flex items-center gap-2">
                <input type="number" min="1" value={settings.delete_after_publish?.value || 1}
                  onChange={(e) => updSettings({ delete_after_publish: { ...settings.delete_after_publish, value: parseInt(e.target.value, 10) || 1 }})}
                  className="w-16 px-2 py-1 bg-gray-50 border border-gray-100 rounded-lg text-xs font-bold focus:outline-none focus:border-blue-200" />
                <select value={settings.delete_after_publish?.unit || 'days'}
                  onChange={(e) => updSettings({ delete_after_publish: { ...settings.delete_after_publish, unit: e.target.value }})}
                  className="px-2 py-1 bg-gray-50 border border-gray-100 rounded-lg text-xs font-bold focus:outline-none focus:border-blue-200">
                  <option value="minutes">минут</option>
                  <option value="hours">часов</option>
                  <option value="days">дней</option>
                </select>
              </div>
            )}
            <div className="border-t border-gray-100 my-2" />
            <Toggle label="Throttling (не спамить)"
              hint="Лимит N релизов в час от одного автора"
              checked={settings.throttle?.enabled}
              onChange={(v) => updSettings({ throttle: { ...settings.throttle, enabled: v }})} />
            {settings.throttle?.enabled && (
              <div className="ml-12 flex items-center gap-2">
                <span className="text-xs font-bold text-gray-700">Не более</span>
                <input type="number" min="1" value={settings.throttle?.limit_per_hour || 5}
                  onChange={(e) => updSettings({ throttle: { ...settings.throttle, limit_per_hour: parseInt(e.target.value, 10) || 5 }})}
                  className="w-16 px-2 py-1 bg-gray-50 border border-gray-100 rounded-lg text-xs font-bold focus:outline-none focus:border-blue-200" />
                <span className="text-xs font-bold text-gray-700">в час</span>
              </div>
            )}
          </div>
        )}
      </Section>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    draft:     ['bg-gray-100 text-gray-600',     'Черновик'],
    scheduled: ['bg-blue-100 text-blue-700',     'Запланирован'],
    published: ['bg-emerald-100 text-emerald-700','Опубликован'],
    failed:    ['bg-red-100 text-red-700',       'Ошибка'],
    cancelled: ['bg-amber-100 text-amber-700',   'Отменён'],
  };
  const [cls, label] = map[status] || ['bg-gray-100 text-gray-600', status];
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
