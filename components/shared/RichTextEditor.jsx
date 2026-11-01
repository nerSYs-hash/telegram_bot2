import { useState, useEffect, useRef, useId } from 'react';

/**
 * Универсальный rich-text редактор в стиле триггеров.
 * Используется в Триггерах (send_text) и в Пресс-релизах.
 *
 * props:
 *   value          — HTML-строка
 *   onChange(html) — колбэк
 *   placeholder    — текст-плейсхолдер
 *   maxLength      — лимит символов (по умолчанию 4096)
 *   onPreview()    — колбэк для предпросмотра (опц.)
 *   onInsertHeader() — колбэк кнопки «📌 Шапка» (опц.)
 *   showHeaderButton — показывать кнопку шапки (по умолчанию false)
 *   minHeight      — мин. высота редактора в px (по умолчанию 160)
 */

const PH_GROUPS = [
  { label: 'Инициатор', color: 'blue', items: [
    { key: 'user_name',     label: 'Имя' },
    { key: 'user_username', label: '@username' },
    { key: 'user_id',       label: 'ID' },
  ]},
  { label: 'Чат', color: 'green', items: [
    { key: 'chat_name', label: 'Название чата' },
    { key: 'date',      label: 'Дата' },
    { key: 'time',      label: 'Время' },
  ]},
  { label: 'Аудитория', color: 'purple', items: [
    { key: 'members_count', label: 'Кол-во участников' },
    { key: 'admins_count',  label: 'Кол-во админов' },
  ]},
];

const COLOR_MAP = {
  blue:   'bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] text-cta hover:bg-[color-mix(in_oklab,var(--cta)_16%,transparent)] border-[color-mix(in_oklab,var(--cta)_30%,transparent)]',
  purple: 'bg-[color-mix(in_oklab,var(--purple)_10%,transparent)] text-purple hover:bg-[color-mix(in_oklab,var(--purple)_16%,transparent)] border-[color-mix(in_oklab,var(--purple)_30%,transparent)]',
  green:  'bg-[color-mix(in_oklab,var(--ok)_10%,transparent)] text-ok hover:bg-[color-mix(in_oklab,var(--ok)_16%,transparent)] border-[color-mix(in_oklab,var(--ok)_30%,transparent)]',
  amber:  'bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] text-warn hover:bg-[color-mix(in_oklab,var(--warn)_16%,transparent)] border-[color-mix(in_oklab,var(--warn)_30%,transparent)]',
};

const EMOJIS = ['😀','😂','😍','🥰','😎','🤔','👍','👎','🙏','🔥','❤️','💯','🎉','😊','😭','🤣','😱','💪','✅','❌','⚠️','💡','📌','🚀','👋','🌟','💬','🎯','⭐','🏆','🔑','💎','🍀','🎵'];

export default function RichTextEditor({
  value, onChange, placeholder = 'Введите текст…',
  maxLength = 4096, onPreview, onInsertHeader, showHeaderButton = false,
  minHeight = 160,
}) {
  const ceId = useId();
  const editorRef = useRef(null);
  const savedRangeRef = useRef(null);

  const [tab, setTab]               = useState('editor');   // editor / code
  const [phOpen, setPhOpen]         = useState(false);
  const [emojiOpen, setEmojiOpen]   = useState(false);
  const [helpOpen, setHelpOpen]     = useState(false);
  const [fmtState, setFmtState]     = useState({ bold: false, italic: false, underline: false, strikeThrough: false });

  // Sync value → contentEditable
  useEffect(() => {
    if (tab !== 'editor') return;
    const el = editorRef.current;
    if (el && (value || '') !== el.innerHTML) el.innerHTML = value || '';
  }, [value, tab]);

  const focusEditor = () => {
    const el = editorRef.current;
    if (el) el.focus();
  };

  const updateFromEditor = () => {
    const el = editorRef.current;
    if (el) onChange?.(el.innerHTML);
  };

  // execCommand bold/italic/etc
  const execFmt = (cmd) => {
    focusEditor();
    document.execCommand(cmd, false, null);
    updateFromEditor();
    setTimeout(() => {
      try {
        setFmtState({
          bold:           document.queryCommandState('bold'),
          italic:         document.queryCommandState('italic'),
          underline:      document.queryCommandState('underline'),
          strikeThrough:  document.queryCommandState('strikeThrough'),
        });
      } catch {}
    }, 0);
  };

  const insertCustomTag = (open, close) => {
    const el = editorRef.current;
    if (!el) return;
    el.focus();
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    const range = sel.getRangeAt(0);
    const text = range.toString() || '​';
    const tmp = document.createElement('div');
    tmp.innerHTML = open + text + close;
    const frag = document.createDocumentFragment();
    let last;
    while (tmp.firstChild) last = frag.appendChild(tmp.firstChild);
    range.deleteContents();
    range.insertNode(frag);
    if (last) {
      const r2 = document.createRange();
      r2.setStartAfter(last);
      r2.collapse(true);
      sel.removeAllRanges();
      sel.addRange(r2);
    }
    setTimeout(updateFromEditor, 0);
  };

  const insertLink = () => {
    const url = window.prompt('Введите URL:');
    if (!url) return;
    focusEditor();
    document.execCommand('createLink', false, url);
    editorRef.current?.querySelectorAll('a').forEach(a => a.removeAttribute('target'));
    updateFromEditor();
  };

  const clearFmt = () => {
    const el = editorRef.current;
    if (!el) return;
    focusEditor();
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    const range = sel.getRangeAt(0);
    const text = range.toString();
    range.deleteContents();
    range.insertNode(document.createTextNode(text));
    setTimeout(updateFromEditor, 0);
  };

  const saveRange = () => {
    const sel = window.getSelection();
    savedRangeRef.current = (sel && sel.rangeCount) ? sel.getRangeAt(0).cloneRange() : null;
  };
  const restoreRange = () => {
    if (savedRangeRef.current) {
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(savedRangeRef.current);
    }
  };

  const insertText = (text) => {
    focusEditor();
    restoreRange();
    document.execCommand('insertText', false, text);
    updateFromEditor();
  };

  const insertEmoji = (em) => { insertText(em); setEmojiOpen(false); };
  const insertPh    = (key) => { insertText(`%${key}%`); setPhOpen(false); };

  const TOOLBAR = [
    { l: 'B',  cmd: 'bold',          cls: 'font-black',     tip: 'Жирный' },
    { l: 'I',  cmd: 'italic',        cls: 'italic',         tip: 'Курсив' },
    { l: 'S',  cmd: 'strikeThrough', cls: 'line-through',   tip: 'Зачёркнутый' },
    { l: 'U',  cmd: 'underline',     cls: 'underline',      tip: 'Подчёркнутый' },
    { l: '<>', custom: () => insertCustomTag('<code>','</code>'),             cls: 'font-mono text-[9px]', tip: 'Моноширинный код' },
    { l: '»',  custom: () => insertCustomTag('<blockquote>','</blockquote>'), cls: '',                      tip: 'Цитата' },
    { l: '🔗', custom: insertLink,                                            cls: '',                      tip: 'Ссылка' },
    { l: '✒',  custom: () => insertCustomTag('<tg-spoiler>','</tg-spoiler>'),  cls: '',                      tip: 'Спойлер' },
    { l: 'Tx', custom: clearFmt,                                              cls: 'text-[9px]',            tip: 'Очистить форматирование' },
  ];

  const textLen = (value || '').replace(/<[^>]+>/g, '').length;
  const isOver  = textLen > maxLength;

  return (
    <div className="bg-sff rounded-xl border-2 border-bd overflow-hidden">
      {/* Tabs */}
      <div className="flex items-center gap-0.5 px-2 pt-2 pb-1 border-b border-bd">
        <button onClick={() => setTab('editor')}
          className={`px-2.5 py-1 text-[11px] font-black rounded transition-all ${tab === 'editor' ? 'bg-blue-500 text-white' : 'text-txd hover:bg-sf2'}`}>
          ✏ Редактор
        </button>
        <button onClick={() => setTab('code')}
          className={`px-2.5 py-1 text-[11px] font-black rounded transition-all ${tab === 'code' ? 'bg-blue-500 text-white' : 'text-txd hover:bg-sf2'}`}>
          {'<>'} Код
        </button>
      </div>

      {tab === 'editor' && (
        <>
          {/* Toolbar */}
          <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-bd flex-wrap">
            {TOOLBAR.map((f) => {
              const isActive = f.cmd ? fmtState[f.cmd] : false;
              return (
                <button key={f.l}
                  title={f.tip}
                  onMouseDown={(e) => { e.preventDefault(); f.cmd ? execFmt(f.cmd) : f.custom(); }}
                  className={`w-7 h-7 text-[11px] rounded flex items-center justify-center transition-all active:scale-90 ${f.cls} ${isActive ? 'bg-[color-mix(in_oklab,var(--cta)_16%,transparent)] text-cta' : 'text-txd hover:bg-sf2'}`}>
                  {f.l}
                </button>
              );
            })}

            {/* Emoji */}
            <div className="relative">
              <button title="Эмодзи"
                onMouseDown={(e) => { e.preventDefault(); saveRange(); setEmojiOpen(o => !o); }}
                className={`w-7 h-7 text-[13px] rounded flex items-center justify-center transition-all active:scale-90 ${emojiOpen ? 'bg-[color-mix(in_oklab,var(--cta)_16%,transparent)] text-cta' : 'text-txd hover:bg-sf2'}`}>
                😊
              </button>
              {emojiOpen && (
                <div className="absolute left-0 top-9 z-50 bg-sff border border-bd2 rounded-xl shadow-xl p-1.5"
                     style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', width: 220 }}>
                  {EMOJIS.map(em => (
                    <button key={em}
                      onMouseDown={(ev) => { ev.preventDefault(); insertEmoji(em); }}
                      className="w-7 h-7 text-base flex items-center justify-center rounded hover:bg-sf2">
                      {em}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Header button */}
            {showHeaderButton && (
              <button title="Вставить блок-шапку"
                onMouseDown={(e) => { e.preventDefault(); onInsertHeader?.(); }}
                className="px-2 py-1 ml-1 text-[10px] font-black uppercase rounded-lg bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] text-warn border border-[color-mix(in_oklab,var(--warn)_30%,transparent)] hover:bg-[color-mix(in_oklab,var(--warn)_16%,transparent)]">
                📌 Шапка
              </button>
            )}

            {/* %плейсхолдеры% */}
            <div className="ml-auto relative">
              <button
                onMouseDown={(e) => { e.preventDefault(); saveRange(); setPhOpen(o => !o); }}
                className={`px-2 py-1 text-[10px] font-bold border rounded-lg whitespace-nowrap transition-all ${phOpen ? 'bg-blue-500 text-white border-blue-500' : 'text-cta border-[color-mix(in_oklab,var(--cta)_40%,transparent)] hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)]'}`}>
                %плейсхолдеры%
              </button>
              {phOpen && (
                <div className="absolute right-0 top-9 z-50 w-[280px] bg-sff border border-bd2 rounded-xl shadow-xl p-2 max-h-[280px] overflow-y-auto">
                  {PH_GROUPS.map(grp => (
                    <div key={grp.label} className="mb-2 last:mb-0">
                      <div className="text-[9px] font-black uppercase tracking-widest text-lbl mb-1">{grp.label}</div>
                      <div className="flex flex-wrap gap-1">
                        {grp.items.map(it => (
                          <button key={it.key}
                            onMouseDown={(ev) => { ev.preventDefault(); insertPh(it.key); }}
                            className={`px-1.5 py-0.5 text-[10px] font-bold border rounded ${COLOR_MAP[grp.color]}`}
                            title={`%${it.key}%`}>
                            {it.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ? Help */}
            <button onMouseDown={(e) => { e.preventDefault(); setHelpOpen(o => !o); }}
              className="w-6 h-6 text-[10px] text-lbl hover:text-cta font-black rounded hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] flex items-center justify-center"
              title="Справка по тегам">?</button>

            {/* ↗ Preview */}
            {onPreview && (
              <button onMouseDown={(e) => { e.preventDefault(); onPreview(); }}
                className="w-6 h-6 text-[10px] text-lbl hover:text-cta rounded hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] flex items-center justify-center"
                title="Предпросмотр">↗</button>
            )}
          </div>

          {/* Help */}
          {helpOpen && (
            <div className="px-3 py-2 bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] text-[11px] text-cta border-b border-[color-mix(in_oklab,var(--cta)_30%,transparent)] leading-relaxed">
              Поддерживаются HTML-теги Telegram: <code className="bg-sff px-1 rounded">&lt;b&gt;</code>{' '}
              <code className="bg-sff px-1 rounded">&lt;i&gt;</code>{' '}
              <code className="bg-sff px-1 rounded">&lt;u&gt;</code>{' '}
              <code className="bg-sff px-1 rounded">&lt;s&gt;</code>{' '}
              <code className="bg-sff px-1 rounded">&lt;code&gt;</code>{' '}
              <code className="bg-sff px-1 rounded">&lt;a href&gt;</code>{' '}
              <code className="bg-sff px-1 rounded">&lt;blockquote&gt;</code>{' '}
              <code className="bg-sff px-1 rounded">&lt;tg-spoiler&gt;</code>.
              %плейсхолдеры% подставятся при отправке.
            </div>
          )}

          {/* Editor */}
          <div className="relative">
            {!value && (
              <span className="absolute top-3 left-4 text-sm text-lbl italic pointer-events-none select-none">
                {placeholder}
              </span>
            )}
            <div
              ref={editorRef}
              id={ceId}
              contentEditable
              suppressContentEditableWarning
              onKeyDown={(e) => {
                // Enter без Shift → вставляем перенос строки текстом, не <br>/<div>
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  document.execCommand('insertText', false, '\n');
                }
              }}
              onInput={(e) => onChange?.(e.currentTarget.innerHTML)}
              onKeyUp={() => {
                try {
                  setFmtState({
                    bold:           document.queryCommandState('bold'),
                    italic:         document.queryCommandState('italic'),
                    underline:      document.queryCommandState('underline'),
                    strikeThrough:  document.queryCommandState('strikeThrough'),
                  });
                } catch {}
              }}
              className="w-full px-4 py-3 text-sm font-medium text-tx outline-none bg-sff"
              style={{ minHeight, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}
            />
            <span className={`absolute bottom-2 right-3 text-[10px] font-black bg-sff px-1 ${isOver ? 'text-danger' : 'text-cta'}`}>
              {textLen}/{maxLength}
            </span>
          </div>
        </>
      )}

      {tab === 'code' && (
        <textarea
          value={value || ''}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder="HTML-код сообщения…"
          rows={8}
          className="w-full px-4 py-3 font-mono text-sm text-tx outline-none resize-y bg-sff"
          style={{ minHeight }}
        />
      )}
    </div>
  );
}
