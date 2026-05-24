import { useState, useEffect } from 'react';
import {
  Moon, Sun, Save, Eye, Trash2, Rocket, Plus, Check, Loader2,
  Search, AlertCircle, Users, Globe, Activity, ChevronDown, Coins, Zap,
  ChevronLeft, ChevronRight, MoreVertical, Home, FileText, Settings,
  LogOut, Bell, X, PanelLeftClose,
} from 'lucide-react';
/* БОЕВЫЕ shared-компоненты (cutover §2b) — рендерим живьём для приёмки */
import RealButton from '../shared/Button.jsx';
import RealToggle from '../shared/Toggle.jsx';
import RealCard from '../shared/Card.jsx';
import RealStyledSelect from '../shared/StyledSelect.jsx';
import RealStepper from '../shared/Stepper.jsx';

/* ════════════════════════════════════════════════════════════════════
   Puls Chat · Design System — LIVE PREVIEW (auth-free)
   Живой State Sheet на реальном React + токены index.css §2.5.
   Контракт: DESIGN_BRIEF_Puls_Chat (T1-тир). Обе темы из одного дерева.
   ════════════════════════════════════════════════════════════════════ */

/* ── Section scaffold ─────────────────────────────────────────────── */
function Sec({ n, name, desc, children }) {
  return (
    <section className="mt-10">
      <div className="mb-3.5 flex items-baseline gap-2.5 flex-wrap">
        <span className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[7px] bg-sf2 border border-bd text-[10px] font-black text-cta">{n}</span>
        <span className="text-[18px] font-black text-tx tracking-tight">{name}</span>
        <span className="w-full text-xs text-txd mt-0.5 leading-relaxed max-w-[700px]">{desc}</span>
      </div>
      <div className="bg-sff border border-bd rounded-token p-6" style={{ boxShadow: 'var(--shc)' }}>
        {children}
      </div>
    </section>
  );
}
function VB({ h, children }) {
  return (
    <div className="mt-5 first:mt-0">
      <div className="text-[10px] font-extrabold tracking-[.16em] uppercase text-lbl mb-3 flex items-center gap-2 after:content-[''] after:flex-1 after:h-px after:bg-bd">{h}</div>
      <div className="flex flex-wrap gap-3.5 items-start">{children}</div>
    </div>
  );
}
function DM({ label, children }) {
  return (
    <div className="flex flex-col items-start gap-1.5">
      {children}
      <span className="text-[10px] font-bold text-lbl tracking-[.08em] uppercase">{label}</span>
    </div>
  );
}
const Sep = () => <div className="h-px bg-bd my-5" />;

/* ── Button (API-эквивалент shared/Button.jsx, токен-скин) ────────── */
const BTN_GLOW = {
  primary: '--glow-from:#3b82f6;--glow-via:#a855f7;--glow-to:#3b82f6;',
  danger:  '--glow-from:#fb7185;--glow-via:#FF453A;--glow-to:#fb7185;',
  success: '--glow-from:#34d399;--glow-via:#32D74B;--glow-to:#34d399;',
};
function vars(s) {
  const o = {}; s.split(';').forEach(p => { const [k, v] = p.split(':').map(x => x?.trim()); if (k && v) o[k] = v; });
  return o;
}
function Btn({ variant = 'primary', size = 'md', state = 'idle', icon: Icon, force = '', children }) {
  const base = {
    primary:   'bg-cta text-white hover:brightness-110',
    secondary: 'bg-sf2 text-tx border border-bd hover:bg-ih hover:border-bd2',
    ghost:     'bg-transparent text-txd hover:bg-ih hover:text-tx',
    outlined:  'bg-transparent text-cta border-[1.5px] border-[color-mix(in_oklab,var(--cta)_40%,transparent)] hover:border-cta hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)]',
    danger:    'bg-danger text-white hover:brightness-110',
    success:   'bg-ok text-white hover:brightness-110',
    link:      'bg-transparent text-cta hover:underline px-0',
  }[variant];
  const sz = { sm: 'h-7 px-3 text-xs rounded-[14px]', md: 'h-9 px-4 text-sm rounded-token', lg: 'h-11 px-5 text-base rounded-token' }[size];
  const glow = BTN_GLOW[variant];
  const loading = state === 'loading', done = state === 'done';
  return (
    <button
      disabled={state === 'disabled' || loading}
      style={glow ? vars(glow) : undefined}
      className={[
        'relative inline-flex items-center justify-center gap-2 font-bold tracking-tight whitespace-nowrap',
        'transition-[background,color,transform,border-color] duration-150 ease-ds',
        'active:scale-[.97] focus:outline-none focus-visible:ring-2 focus-visible:ring-[color-mix(in_oklab,var(--cta)_60%,transparent)] focus-visible:ring-offset-2 focus-visible:ring-offset-sff',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100',
        glow ? 'pulse-btn-glow' : '', sz, base, force,
      ].filter(Boolean).join(' ')}
    >
      {loading && <Loader2 size={15} className="animate-spin" />}
      {done && <Check size={17} strokeWidth={3} className="pulse-btn-check" />}
      {!loading && !done && Icon && <Icon size={15} />}
      {!done && children && <span>{children}</span>}
    </button>
  );
}

/* ── Toggle — ФИКС брифа: on = --ok (зелёный), не blue ────────────── */
function Tog({ on: initial = false, disabled = false }) {
  const [on, setOn] = useState(initial);
  return (
    <button
      disabled={disabled}
      onClick={() => setOn(o => !o)}
      className={`relative inline-flex items-center w-11 h-[26px] rounded-pill p-[3px] transition-colors duration-[220ms] ease-ds disabled:opacity-50 ${on ? 'bg-ok' : 'bg-bd2'}`}
    >
      <span className={`w-5 h-5 rounded-pill bg-white shadow transition-transform duration-[220ms] ease-ds ${on ? 'translate-x-[18px]' : ''}`} />
    </button>
  );
}

/* ── Card — акцент-палитры + Aceternity glow на hover ─────────────── */
const CARD_GLOW = {
  blue:    '--card-glow-from:#60a5fa;--card-glow-via:#a855f7;--card-glow-to:#60a5fa;',
  violet:  '--card-glow-from:#c084fc;--card-glow-via:#BF5AF2;--card-glow-to:#c084fc;',
  amber:   '--card-glow-from:#fbbf24;--card-glow-via:#FF9F0A;--card-glow-to:#fbbf24;',
  emerald: '--card-glow-from:#34d399;--card-glow-via:#32D74B;--card-glow-to:#34d399;',
  pink:    '--card-glow-from:#fb7185;--card-glow-via:#FF375F;--card-glow-to:#fb7185;',
};
function DSCard({ accent = 'blue', icon: Icon = Activity }) {
  return (
    <div
      style={vars(CARD_GLOW[accent])}
      className="pulse-card-glow relative w-[200px] bg-sf2 border border-bd rounded-token p-5 transition-transform duration-200 ease-ds hover:-translate-y-0.5"
    >
      <div className="w-9 h-9 rounded-token-sm bg-sff border border-bd flex items-center justify-center text-cta mb-3"><Icon size={18} /></div>
      <div className="text-[10px] font-extrabold tracking-[.16em] uppercase text-lbl">{accent}</div>
      <div className="text-sm font-black text-tx mt-0.5">Карточка-стекло</div>
      <div className="text-xs text-txd mt-1">Наведи — glow-кольцо 4s + lift</div>
    </div>
  );
}

/* ── Input ────────────────────────────────────────────────────────── */
function Inp({ state, value, placeholder = 'Введите…', hint, err, prefix: Prefix }) {
  const ring = {
    focus:   'border-cta ring-2 ring-[color-mix(in_oklab,var(--cta)_25%,transparent)]',
    error:   'border-danger ring-2 ring-[color-mix(in_oklab,var(--danger)_25%,transparent)]',
    disabled:'opacity-50 cursor-not-allowed',
  }[state] || 'border-bd';
  return (
    <div className="flex flex-col gap-1.5 w-[190px]">
      <span className="text-[10px] font-bold uppercase tracking-wide text-lbl">Имя чата</span>
      <div className={`flex items-center gap-2 h-10 px-3.5 rounded-token bg-sf border-[1.5px] transition-all duration-150 ease-ds ${ring}`}>
        {Prefix && <Prefix size={15} className="text-lbl shrink-0" />}
        <input
          disabled={state === 'disabled'}
          defaultValue={value}
          placeholder={placeholder}
          className="bg-transparent outline-none text-sm text-tx placeholder:text-lbl w-full"
        />
      </div>
      {err
        ? <span className="text-[11px] text-danger flex items-center gap-1"><AlertCircle size={11} />{err}</span>
        : hint && <span className="text-[11px] text-txd">{hint}</span>}
    </div>
  );
}

/* ── Badge ────────────────────────────────────────────────────────── */
function Badge({ tone = 'cta', children }) {
  const m = {
    cta:    'bg-[color-mix(in_oklab,var(--cta)_15%,transparent)] text-cta',
    ok:     'bg-[color-mix(in_oklab,var(--ok)_15%,transparent)] text-ok',
    danger: 'bg-[color-mix(in_oklab,var(--danger)_15%,transparent)] text-danger',
    warn:   'bg-[color-mix(in_oklab,var(--warn)_15%,transparent)] text-warn',
  }[tone];
  return <span className={`inline-flex items-center h-5 px-2 rounded-pill text-[10px] font-extrabold uppercase tracking-wide ${m}`}>{children}</span>;
}

/* ── StatusPill (под V1.17.0h) ────────────────────────────────────── */
function StatusPill({ kind }) {
  if (kind === 'ok') return (
    <span className="inline-flex items-center gap-2 h-7 px-3 rounded-pill bg-sf2 border border-bd text-[13px] font-bold text-tx">
      <span className="relative w-[7px] h-[7px] rounded-pill bg-ok before:content-[''] before:absolute before:-inset-1 before:rounded-pill before:border-[1.5px] before:border-ok before:animate-[dsPing_1.6s_ease-in-out_infinite]" />
      Подключён
    </span>
  );
  if (kind === 'err') return (
    <span className="inline-flex items-center gap-2 h-7 px-3 rounded-pill bg-sf2 border border-bd text-[13px] font-bold text-txd">
      <span className="w-[7px] h-[7px] rounded-pill bg-danger" />Отключён
    </span>
  );
  return (
    <span className="inline-flex items-center gap-2 h-7 px-3 rounded-pill bg-sf2 border border-bd text-[13px] font-bold text-ok">
      <Loader2 size={13} className="animate-spin" />Восстановлен
    </span>
  );
}

/* ── Textarea ─────────────────────────────────────────────────────── */
function Txa({ state, value = '', count }) {
  const ring = {
    focus:    'border-cta ring-2 ring-[color-mix(in_oklab,var(--cta)_25%,transparent)]',
    error:    'border-danger ring-2 ring-[color-mix(in_oklab,var(--danger)_25%,transparent)]',
    disabled: 'opacity-50 cursor-not-allowed',
  }[state] || 'border-bd';
  return (
    <div className="flex flex-col gap-1.5 w-[200px]">
      <div className={`rounded-token bg-sf border-[1.5px] transition-all duration-150 ease-ds ${ring}`}>
        <textarea
          disabled={state === 'disabled'} defaultValue={value} placeholder="Введите текст…"
          className="w-full h-16 bg-transparent outline-none resize-none p-3 text-sm text-tx placeholder:text-lbl"
        />
        <div className="px-3 pb-2 text-right">
          <span className={`text-[10px] font-bold ${state === 'error' ? 'text-danger' : 'text-lbl'}`}>{count ?? '0 / 500'}</span>
        </div>
      </div>
    </div>
  );
}

/* ── Select (StyledSelect-скин) ───────────────────────────────────── */
function Sel({ state, value, open }) {
  const trig = {
    focus:   'border-cta',
    error:   'border-danger',
    disabled:'opacity-50 cursor-not-allowed',
  }[state] || (open ? 'border-cta bg-sff' : 'border-bd');
  return (
    <div className="flex flex-col gap-2">
      <div className={`flex items-center gap-1.5 h-9 px-3.5 min-w-[170px] rounded-token bg-sf2 border-[1.5px] text-sm font-bold transition-all duration-150 ease-ds ${trig} ${value ? 'text-tx' : 'text-lbl'}`}>
        <span className="flex-1 truncate">{value || 'Категория…'}</span>
        <ChevronDown size={15} className={`text-txd transition-transform ${open ? 'rotate-180' : ''}`} />
      </div>
      {open && (
        <div className="w-[180px] bg-sff border border-bd rounded-token-sm p-1" style={{ boxShadow: 'var(--shd)' }}>
          {[['Все категории', false, false], ['Майнинг', true, false], ['Триггеры', false, 'hover'], ['Лотерея', false, 'dis']].map(([l, on, st]) => (
            <div key={l} className={`flex items-center gap-2 px-2.5 h-8 rounded-[8px] text-sm ${
              on ? 'bg-[color-mix(in_oklab,var(--cta)_14%,transparent)] text-cta font-bold'
                 : st === 'hover' ? 'bg-ih text-tx' : st === 'dis' ? 'text-lbl opacity-50' : 'text-txd'}`}>
              <span className="flex-1">{l}</span>
              {on && <Check size={13} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Checkbox ─────────────────────────────────────────────────────── */
function Cbx({ kind = 'off', label }) {
  const box = {
    off:  'border-[1.5px] border-bd2 bg-transparent',
    on:   'bg-cta border-[1.5px] border-cta',
    ind:  'bg-cta border-[1.5px] border-cta',
    dis:  'border-[1.5px] border-bd2 bg-transparent opacity-50',
    dison:'bg-cta border-[1.5px] border-cta opacity-50',
    focus:'border-[1.5px] border-bd2 bg-transparent ring-2 ring-[color-mix(in_oklab,var(--cta)_45%,transparent)]',
  }[kind];
  return (
    <label className="inline-flex items-center gap-2 text-sm text-tx cursor-pointer select-none">
      <span className={`w-[18px] h-[18px] rounded-[6px] flex items-center justify-center transition-all ${box}`}>
        {(kind === 'on' || kind === 'dison') && <Check size={11} strokeWidth={3} className="text-white" />}
        {kind === 'ind' && <span className="w-[7px] h-[2px] bg-white rounded-sm" />}
      </span>
      {label}
    </label>
  );
}

/* ── Radio ────────────────────────────────────────────────────────── */
function Rb({ kind = 'off', label }) {
  const on = kind === 'on';
  return (
    <label className={`inline-flex items-center gap-2 text-sm text-tx cursor-pointer select-none ${kind === 'dis' ? 'opacity-50' : ''}`}>
      <span className={`w-[18px] h-[18px] rounded-full border-[1.5px] flex items-center justify-center transition-all ${on ? 'border-cta' : 'border-bd2'} ${kind === 'focus' ? 'ring-2 ring-[color-mix(in_oklab,var(--cta)_45%,transparent)]' : ''}`}>
        <span className={`w-2 h-2 rounded-full bg-cta transition-transform ${on ? 'scale-100' : 'scale-0'}`} />
      </span>
      {label}
    </label>
  );
}
function RbCard({ on, dis, icon: Icon, title, desc }) {
  return (
    <div className={`relative w-[220px] rounded-token border-[1.5px] p-4 transition-all duration-150 ease-ds ${
      dis ? 'border-bd opacity-50' : on ? 'border-cta bg-[color-mix(in_oklab,var(--cta)_8%,transparent)]' : 'border-bd hover:border-bd2'}`}>
      <div className="w-8 h-8 rounded-[10px] bg-sf2 border border-bd flex items-center justify-center text-txd mb-2"><Icon size={16} /></div>
      <div className="text-sm font-black text-tx">{title}</div>
      <div className="text-xs text-txd mt-0.5">{desc}</div>
      <div className={`absolute top-2.5 right-2.5 w-[18px] h-[18px] rounded-full border-[1.5px] flex items-center justify-center ${on ? 'bg-cta border-cta' : 'border-bd2'}`}>
        {on && <Check size={11} strokeWidth={3} className="text-white" />}
      </div>
    </div>
  );
}

/* ── Tabs (primary / subtle / underline) ──────────────────────────── */
function Tabs({ variant }) {
  const items = ['Запланированные', 'Черновики', 'История'];
  const [act, setAct] = useState(1);
  if (variant === 'underline') return (
    <div className="flex gap-1 border-b border-bd">
      {items.map((t, i) => (
        <button key={t} onClick={() => setAct(i)}
          className={`relative px-4 py-2 text-sm font-bold transition-colors ${i === act ? 'text-tx' : 'text-txd hover:text-tx'}`}>
          {t}
          {i === act && <span className="absolute left-0 right-0 -bottom-px h-0.5 rounded-t" style={{ background: 'linear-gradient(90deg,var(--g-from),var(--g-via))' }} />}
        </button>
      ))}
    </div>
  );
  const pill = variant === 'subtle'
    ? (a) => a ? 'bg-[color-mix(in_oklab,var(--cta)_15%,transparent)] text-cta' : 'text-txd hover:text-tx'
    : (a) => a ? 'bg-sf2 text-tx border border-bd' : 'text-txd hover:text-tx';
  return (
    <div className="inline-flex gap-1 p-1 rounded-token bg-sf2/40">
      {items.map((t, i) => (
        <button key={t} onClick={() => setAct(i)} className={`px-3.5 py-1.5 rounded-[12px] text-[13px] font-bold transition-colors ${pill(i === act)}`}>{t}</button>
      ))}
    </div>
  );
}

/* ── Tooltip (всегда тёмный, обе темы) ────────────────────────────── */
function Tip({ dir = 'top' }) {
  const pos = {
    top:    'bottom-full left-1/2 -translate-x-1/2 mb-2',
    right:  'left-full top-1/2 -translate-y-1/2 ml-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left:   'right-full top-1/2 -translate-y-1/2 mr-2',
  }[dir];
  return (
    <div className="relative group">
      <div className="w-9 h-9 rounded-token bg-sf2 border border-bd flex items-center justify-center text-txd cursor-pointer transition-colors hover:text-tx hover:border-bd2"><Activity size={15} /></div>
      <span className={`absolute ${pos} whitespace-nowrap px-2.5 py-1 rounded-[8px] text-[11px] font-bold bg-[#1B1B22] text-[#F4F4F6] shadow-lg z-20 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none`}>Подсказка · {dir}</span>
    </div>
  );
}

/* ── DashedAdd / EmptySlot (§11 — одна роль) ──────────────────────── */
function DashAdd({ force = '' }) {
  return (
    <button className={`inline-flex items-center gap-2 h-9 px-4 rounded-token border-[1.5px] border-dashed border-bd2 text-txd text-sm font-bold transition-all duration-150 ease-ds hover:border-cta hover:text-cta hover:bg-[color-mix(in_oklab,var(--cta)_8%,transparent)] ${force}`}>
      <Plus size={15} />Добавить параметр
    </button>
  );
}
function EmptySlot({ force = '' }) {
  return (
    <div className={`w-[220px] flex flex-col items-center gap-2 px-5 py-7 rounded-token border-[1.5px] border-dashed border-bd2 text-center transition-all duration-150 ease-ds hover:border-cta hover:bg-[color-mix(in_oklab,var(--cta)_6%,transparent)] ${force}`}>
      <div className="w-9 h-9 rounded-[11px] bg-sf2 border border-bd flex items-center justify-center text-txd"><Plus size={18} /></div>
      <div className="text-sm font-bold text-tx">Добавить медиаблок</div>
      <div className="text-xs text-txd">Перетащите файл или нажмите</div>
    </div>
  );
}

/* ── Table ────────────────────────────────────────────────────────── */
function DSTable() {
  const [sel, setSel] = useState([1]);
  const rows = [
    { id: 0, name: 'Puls Official', st: 'ok',   role: 'Главный' },
    { id: 1, name: 'Puls VIP',      st: 'ok',   role: 'Админ' },
    { id: 2, name: 'Puls Journal',  st: 'warn', role: 'Журнал' },
    { id: 3, name: 'Старый чат',    st: 'er',   role: '—' },
  ];
  const dot = { ok: 'bg-ok', warn: 'bg-warn', er: 'bg-danger' };
  const all = sel.length === rows.length;
  return (
    <div className="rounded-token border border-bd overflow-hidden">
      <table className="w-full text-[13px]" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr className="bg-sf2 border-b border-bd">
            <th className="w-10 p-2.5">
              <span onClick={() => setSel(all ? [] : rows.map(r => r.id))}
                className={`inline-flex w-[18px] h-[18px] rounded-[6px] items-center justify-center cursor-pointer ${sel.length ? 'bg-cta border-[1.5px] border-cta' : 'border-[1.5px] border-bd2'}`}>
                {all ? <Check size={11} strokeWidth={3} className="text-white" /> : sel.length ? <span className="w-[7px] h-[2px] bg-white rounded-sm" /> : null}
              </span>
            </th>
            {['Чат', 'Статус', 'Роль'].map(h => (
              <th key={h} className="px-3.5 py-2.5 text-left text-[10px] font-extrabold tracking-widest uppercase text-lbl cursor-pointer hover:text-txd">{h} ▾</th>
            ))}
            <th className="w-12" />
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const on = sel.includes(r.id);
            return (
              <tr key={r.id} className={`border-b border-bd last:border-0 transition-colors ${on ? 'bg-[color-mix(in_oklab,var(--cta)_8%,transparent)]' : 'hover:bg-ih'}`}>
                <td className="p-2.5">
                  <span onClick={() => setSel(s => on ? s.filter(x => x !== r.id) : [...s, r.id])}
                    className={`inline-flex w-[18px] h-[18px] rounded-[6px] items-center justify-center cursor-pointer ${on ? 'bg-cta border-[1.5px] border-cta' : 'border-[1.5px] border-bd2'}`}>
                    {on && <Check size={11} strokeWidth={3} className="text-white" />}
                  </span>
                </td>
                <td className="px-3.5 py-2.5 text-tx font-medium">{r.name}</td>
                <td className="px-3.5 py-2.5">
                  <span className="inline-flex items-center gap-1.5 font-bold"><span className={`w-[7px] h-[7px] rounded-full ${dot[r.st]}`} />{r.st === 'ok' ? 'Подключён' : r.st === 'warn' ? 'Реконнект' : 'Отключён'}</span>
                </td>
                <td className="px-3.5 py-2.5 text-txd">{r.role}</td>
                <td className="px-2"><button className="w-7 h-7 rounded-[8px] text-txd hover:bg-ih hover:text-tx inline-flex items-center justify-center"><MoreVertical size={15} /></button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
function TableEmpty() {
  return (
    <div className="rounded-token border border-bd flex flex-col items-center gap-2 py-10 text-center">
      <div className="w-10 h-10 rounded-token bg-sf2 border border-bd flex items-center justify-center text-lbl"><Search size={18} /></div>
      <div className="text-sm font-bold text-tx">Ничего не найдено</div>
      <div className="text-xs text-txd">Измени фильтр или поисковый запрос</div>
    </div>
  );
}

/* ── Modal (spec-view inline) ─────────────────────────────────────── */
function ModalCard({ danger }) {
  return (
    <div className="w-[340px] rounded-token bg-sff border border-bd p-5" style={{ boxShadow: 'var(--shd)' }}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-[10px] font-extrabold tracking-widest uppercase text-lbl mb-1">{danger ? 'Подтверждение' : 'Редактирование'}</div>
          <h3 className="text-base font-black text-tx">{danger ? 'Удалить чат?' : 'Причина изменения'}</h3>
        </div>
        <button className="w-7 h-7 rounded-[8px] text-txd hover:bg-ih inline-flex items-center justify-center"><X size={15} /></button>
      </div>
      {danger
        ? <p className="text-sm text-txd mb-4">Чат «Старый чат» и его данные будут удалены безвозвратно. Действие нельзя отменить.</p>
        : <div className="mb-4"><Inp value="Корр. майнинга" hint="Обязательно для аудита" /></div>}
      <div className="flex justify-end gap-2">
        <Btn variant="secondary" size="sm">Отмена</Btn>
        {danger ? <Btn variant="danger" size="sm" icon={Trash2}>Удалить</Btn> : <Btn variant="primary" size="sm" icon={Save}>Сохранить</Btn>}
      </div>
    </div>
  );
}

/* ── Stepper (re-skin, .pulse-step-current канон 1.8s) ────────────── */
function DSStepper({ compact }) {
  const steps = ['Бот', 'Чат', 'Роль', 'Готово'];
  const cur = 1;
  return (
    <div className="w-full flex items-center">
      {steps.map((s, i) => {
        const done = i < cur, active = i === cur;
        const isLast = i === steps.length - 1;
        return (
          <div key={s} className={`flex items-center ${isLast ? '' : 'flex-1'}`}>
            <div className="flex flex-col items-center gap-1.5">
              <div className={`w-9 h-9 rounded-full flex items-center justify-center border-2 transition-all ${
                done ? 'bg-ok border-ok text-white'
                : active ? 'pulse-step-current border-transparent text-white' : 'bg-transparent border-bd2 text-lbl'}`}
                style={active ? { background: 'linear-gradient(135deg,var(--cta),var(--purple))' } : undefined}>
                {done ? <Check size={16} strokeWidth={3} /> : <span className="text-xs font-black">{i + 1}</span>}
              </div>
              {!compact && <span className={`text-[10px] font-black uppercase tracking-wide ${active ? 'text-cta' : done ? 'text-ok' : 'text-lbl'}`}>{s}</span>}
            </div>
            {!isLast && <div className={`flex-1 h-0.5 mx-2 ${compact ? '' : 'mb-5'} rounded-full ${done ? 'bg-ok' : 'bg-bd2'}`} />}
          </div>
        );
      })}
    </div>
  );
}

/* ── StatRing (SVG, бренд-градиент stroke) ────────────────────────── */
function StatRing({ size = 90, pct = 68, label = 'Активность', val }) {
  const sw = size >= 110 ? 9 : size >= 84 ? 8 : 7;
  const r = (size - sw) / 2, c = 2 * Math.PI * r;
  const gid = `rg${size}`;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs><linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--g-from)" /><stop offset="100%" stopColor="var(--g-via)" />
        </linearGradient></defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bd2)" strokeWidth={sw} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`url(#${gid})`} strokeWidth={sw}
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-black text-tx tabular-nums" style={{ fontSize: size / 4 }}>{val ?? `${pct}%`}</span>
        <span className="text-[9px] font-bold uppercase tracking-wider text-lbl">{label}</span>
      </div>
    </div>
  );
}

/* ── Pagination ───────────────────────────────────────────────────── */
function Pagination({ page = 3 }) {
  const pages = [1, 2, 3, '…', 6];
  return (
    <div className="inline-flex items-center gap-1">
      <button disabled={page === 1} className="w-8 h-8 rounded-[10px] inline-flex items-center justify-center text-txd hover:bg-ih disabled:opacity-35"><ChevronLeft size={15} /></button>
      {pages.map((p, i) => (
        <button key={i} disabled={p === '…'}
          className={`min-w-8 h-8 px-2 rounded-[10px] text-[13px] font-bold inline-flex items-center justify-center ${
            p === page ? 'bg-cta text-white' : p === '…' ? 'text-lbl' : 'text-txd hover:bg-ih'}`}>{p}</button>
      ))}
      <button className="w-8 h-8 rounded-[10px] inline-flex items-center justify-center text-txd hover:bg-ih"><ChevronRight size={15} /></button>
    </div>
  );
}

/* ── TwoColLayout / Section shell ─────────────────────────────────── */
function TwoCol() {
  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 280px' }}>
      <div className="rounded-token border border-dashed border-bd2 p-5 text-xs text-lbl uppercase tracking-widest">main (1fr)</div>
      <div className="rounded-token border border-dashed border-bd2 p-5 text-xs text-lbl uppercase tracking-widest">aside (280px)</div>
    </div>
  );
}
function SectionShell() {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-token border border-bd bg-sf2/30 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 cursor-pointer" onClick={() => setOpen(o => !o)}>
        <div>
          <div className="text-[10px] font-extrabold tracking-widest uppercase text-lbl">Раздел</div>
          <div className="text-sm font-black text-tx">Экономика чата</div>
        </div>
        <div className="flex items-center gap-2">
          <Btn variant="ghost" size="sm" icon={Plus}>Добавить</Btn>
          <ChevronDown size={16} className={`text-txd transition-transform ${open ? '' : '-rotate-90'}`} />
        </div>
      </div>
      {open && <div className="px-4 py-4 border-t border-bd text-sm text-txd">Тело секции — единая оболочка миграции сложных экранов (§10/§11).</div>}
    </div>
  );
}

/* ── Sidebar §5a (expanded 248 / collapsed 80 + фикс #7 бейдж→точка) ─ */
function SbItem({ icon: Icon, label, active, badge, collapsed }) {
  return (
    <div className={`relative flex items-center h-10 rounded-token cursor-pointer transition-colors ${collapsed ? 'justify-center' : 'px-3 gap-3'} ${
      active ? 'bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] text-tx' : 'text-txd hover:bg-ih hover:text-tx'}`}>
      <Icon size={20} className={active ? 'text-cta' : ''} />
      {!collapsed && <span className="flex-1 text-sm font-bold">{label}</span>}
      {/* §5a: expanded → число-бейдж; collapsed → точка в углу (ФИКС #7) */}
      {badge != null && (collapsed
        ? <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-danger" />
        : <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-danger text-white text-xs font-bold inline-flex items-center justify-center">{badge}</span>)}
    </div>
  );
}
function Sidebar({ collapsed }) {
  const w = collapsed ? 80 : 248;
  return (
    <div className="rounded-token bg-sff border border-bd flex flex-col" style={{ width: w, paddingTop: 24, paddingBottom: 16, paddingLeft: 16, paddingRight: 16 }}>
      <div className={`flex items-center h-10 mb-4 ${collapsed ? 'justify-center' : 'gap-2'}`}>
        <div className="pulse-beat w-7 h-7 rounded-[9px] flex items-center justify-center text-white" style={{ background: 'linear-gradient(135deg,var(--g-from),var(--g-via))' }}><Activity size={16} /></div>
        {!collapsed && <span className="text-[20px] font-black text-tx tracking-tight">Puls</span>}
      </div>
      <div className={`flex items-center h-10 mb-6 rounded-token bg-sf2 border border-bd text-lbl ${collapsed ? 'justify-center' : 'px-3 gap-2'}`}>
        <Search size={collapsed ? 18 : 16} />{!collapsed && <span className="text-sm font-semibold">Поиск</span>}
      </div>
      {!collapsed && <div className="text-[11px] font-semibold uppercase tracking-widest text-lbl mb-2">Меню</div>}
      <div className="flex flex-col gap-1">
        <SbItem icon={Home} label="Дашборд" active collapsed={collapsed} />
        <SbItem icon={Users} label="Сообщества" collapsed={collapsed} />
        <SbItem icon={FileText} label="Журнал" badge={14} collapsed={collapsed} />
        <SbItem icon={Bell} label="Триггеры" badge={2} collapsed={collapsed} />
        <SbItem icon={Settings} label="Настройки" collapsed={collapsed} />
      </div>
      <div className="mt-6 pt-4 border-t border-bd flex flex-col gap-3">
        {!collapsed
          ? <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-full bg-sf2 border border-bd flex items-center justify-center text-txd font-black">И</div>
              <div className="flex-1 min-w-0"><div className="text-sm font-bold text-tx truncate">Илья</div><div className="text-[11px] text-lbl truncate">@Nersys</div></div>
              <LogOut size={18} className="text-txd" />
            </div>
          : <div className="w-10 h-10 mx-auto rounded-full bg-sf2 border border-bd flex items-center justify-center text-txd font-black">И</div>}
      </div>
    </div>
  );
}

/* ── БОЕВЫЕ shared-компоненты (cutover §2b, реальные импорты) ──────── */
function RealShowcase() {
  const [tg1, setTg1] = useState(true);
  const [tg2, setTg2] = useState(false);
  const [selV, setSelV] = useState('mining');
  const opts = [
    { value: 'all', label: 'Все категории' },
    { value: 'mining', label: 'Майнинг', hint: 'осн.' },
    { value: 'trig', label: 'Триггеры' },
    { value: 'lot', label: 'Лотерея' },
  ];
  const steps = [
    { id: 'a', label: 'Бот', icon: Activity },
    { id: 'b', label: 'Чат', icon: Users },
    { id: 'c', label: 'Роль', icon: Settings },
    { id: 'd', label: 'Готово', icon: Check },
  ];
  return (
    <>
      <VB h="Button (боевой) — варианты · состояния · размеры">
        <DM label="primary"><RealButton variant="primary" icon={Save}>Сохранить</RealButton></DM>
        <DM label="secondary"><RealButton variant="secondary">Отмена</RealButton></DM>
        <DM label="ghost"><RealButton variant="ghost" icon={Eye}>Превью</RealButton></DM>
        <DM label="outlined"><RealButton variant="outlined">Подробнее</RealButton></DM>
        <DM label="danger"><RealButton variant="danger" icon={Trash2}>Удалить</RealButton></DM>
        <DM label="success"><RealButton variant="success" icon={Rocket}>Опубликовать</RealButton></DM>
        <DM label="link"><RealButton variant="link">Журнал →</RealButton></DM>
        <DM label="loading"><RealButton variant="primary" state="loading">Сохраняю…</RealButton></DM>
        <DM label="done"><RealButton variant="success" state="done" /></DM>
        <DM label="disabled"><RealButton variant="primary" disabled>Сохранить</RealButton></DM>
        <DM label="sm/md/lg"><div className="flex items-center gap-2"><RealButton size="sm" icon={Plus}>sm</RealButton><RealButton size="md" icon={Plus}>md</RealButton><RealButton size="lg" icon={Plus}>lg</RealButton></div></DM>
      </VB>
      <Sep />
      <VB h="Toggle (боевой) — фикс брифа on=зелёный">
        <DM label="on (клик)"><RealToggle checked={tg1} onChange={setTg1} label="Уведомления" hint="Слать в чат при срабатывании" /></DM>
        <DM label="off (клик)"><RealToggle checked={tg2} onChange={setTg2} label="Тихий режим" hint="Без звука" /></DM>
      </VB>
      <Sep />
      <VB h="Card (боевой) — accent · hover-glow v2 · active">
        <DM label="blue hover-glow"><RealCard accent="blue" glow hoverable><div className="text-sm font-black text-tx">Glass-карточка</div><div className="text-xs text-txd mt-1">Наведи — glow v2</div></RealCard></DM>
        <DM label="violet active"><RealCard accent="violet" active><div className="text-sm font-black text-tx">Выбрана</div><div className="text-xs text-txd mt-1">accent tint</div></RealCard></DM>
        <DM label="amber hoverable"><RealCard accent="amber" hoverable><div className="text-sm font-black text-tx">Hoverable</div><div className="text-xs text-txd mt-1">lift на hover</div></RealCard></DM>
      </VB>
      <Sep />
      <VB h="StyledSelect (боевой) — API сохранён">
        <DM label="value-driven"><RealStyledSelect value={selV} options={opts} onChange={setSelV} /></DM>
      </VB>
      <Sep />
      <VB h="Stepper (боевой) — белый ободок убран, пульс cta">
        <DM label="current = Чат"><div className="w-[460px]"><RealStepper steps={steps} current="b" /></div></DM>
      </VB>
    </>
  );
}

/* ════════════════════════════════════════════════════════════════════ */
export default function DesignSystemPreview() {
  return (
    <div className="ds-canvas min-h-screen">
      <style>{`@keyframes dsPing{0%,100%{transform:scale(1);opacity:.6}50%{transform:scale(1.7);opacity:0}}
        @media(prefers-reduced-motion:reduce){.pulse-btn-glow,.pulse-card-glow,[class*=animate-]{animation:none!important}}`}</style>

      {/* Topbar */}
      <div className="sticky top-0 z-50 flex items-center justify-between gap-4 px-8 py-3.5 bg-bg border-b border-bd">
        <h1 className="text-base font-black text-tx tracking-tight">
          Puls Chat · Design System <span className="text-xs font-bold text-txd ml-2">Live Preview · T1 · без авторизации</span>
        </h1>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 h-6 px-2.5 rounded-pill bg-sff border border-bd text-[10px] font-extrabold tracking-widest uppercase text-txd">
            <span className="w-1.5 h-1.5 rounded-full bg-ok" />token-tree §2.5 · light
          </span>
        </div>
      </div>

      <div className="relative z-[1] max-w-[1360px] mx-auto px-8 pb-24">

        <Sec n="01" name="Button" desc="7 вариантов · 3 размера · состояния. Glow-кольцо (канон index.css 2.4s) на primary/danger/success — только hover/focus. Success-pop 350ms spring.">
          <VB h="Варианты · idle">
            <DM label="primary"><Btn variant="primary" icon={Save}>Сохранить</Btn></DM>
            <DM label="secondary"><Btn variant="secondary">Отмена</Btn></DM>
            <DM label="ghost"><Btn variant="ghost" icon={Eye}>Превью</Btn></DM>
            <DM label="outlined"><Btn variant="outlined">Подробнее</Btn></DM>
            <DM label="danger"><Btn variant="danger" icon={Trash2}>Удалить</Btn></DM>
            <DM label="success"><Btn variant="success" icon={Rocket}>Опубликовать</Btn></DM>
            <DM label="link"><Btn variant="link">Журнал →</Btn></DM>
          </VB>
          <Sep />
          <VB h="Primary · состояния">
            <DM label="idle"><Btn icon={Save}>Сохранить</Btn></DM>
            <DM label="loading"><Btn state="loading">Сохраняю…</Btn></DM>
            <DM label="done"><Btn variant="success" state="done" /></DM>
            <DM label="disabled"><Btn state="disabled">Сохранить</Btn></DM>
          </VB>
          <Sep />
          <VB h="Размеры">
            <DM label="sm · 28px"><Btn size="sm" icon={Plus}>sm</Btn></DM>
            <DM label="md · 36px"><Btn size="md" icon={Plus}>md</Btn></DM>
            <DM label="lg · 44px"><Btn size="lg" icon={Plus}>lg</Btn></DM>
          </VB>
        </Sec>

        <Sec n="02" name="Toggle" desc="ФИКС брифа: on = --ok зелёный (было blue). 44×26, thumb-spring 220ms. Кликабельно.">
          <VB h="Состояния (клик переключает)">
            <DM label="off → on"><Tog /></DM>
            <DM label="on (стартовый)"><Tog on /></DM>
            <DM label="disabled off"><Tog disabled /></DM>
            <DM label="disabled on"><Tog on disabled /></DM>
          </VB>
        </Sec>

        <Sec n="03" name="Input / TextField" desc="default · focus · filled · error · disabled + search prefix. Label + hint/error.">
          <VB h="Состояния">
            <DM label="default"><Inp hint="Видно модераторам" /></DM>
            <DM label="focus"><Inp state="focus" hint="Видно модераторам" /></DM>
            <DM label="filled"><Inp value="Puls Official" hint="Видно модераторам" /></DM>
            <DM label="error"><Inp state="error" value="@" err="Недопустимый символ" /></DM>
            <DM label="disabled"><Inp state="disabled" value="Puls Official" /></DM>
            <DM label="search"><Inp prefix={Search} placeholder="Поиск…" /></DM>
          </VB>
        </Sec>

        <Sec n="04" name="Card" desc="5 акцент-палитр. Hover: вращающийся glow-бордер (канон 4s) + lift translateY(-2px). Dark — стекло; Light — белый+тень.">
          <VB h="Idle · 5 палитр (наведи мышь)">
            <DSCard accent="blue" icon={Activity} />
            <DSCard accent="violet" icon={Rocket} />
            <DSCard accent="amber" icon={Save} />
            <DSCard accent="emerald" icon={Check} />
            <DSCard accent="pink" icon={Users} />
          </VB>
        </Sec>

        <Sec n="05" name="Badge / StatusPill" desc="Semantic pill (tinted) + StatusPill чата под V1.17.0h: подключён (ping-ring §6a-искл.2) / отключён / восстановлен.">
          <VB h="Semantic badge">
            <DM label="cta"><Badge tone="cta">12 новых</Badge></DM>
            <DM label="ok"><Badge tone="ok">активен</Badge></DM>
            <DM label="warn"><Badge tone="warn">внимание</Badge></DM>
            <DM label="danger"><Badge tone="danger">2 ошибки</Badge></DM>
          </VB>
          <Sep />
          <VB h="StatusPill · 3 состояния (V1.17.0h)">
            <DM label="ok · ping-ring 1.6s"><StatusPill kind="ok" /></DM>
            <DM label="danger · dim"><StatusPill kind="err" /></DM>
            <DM label="restored · ↻"><StatusPill kind="restored" /></DM>
          </VB>
        </Sec>

        <Sec n="06" name="Textarea" desc="Те же 5 состояний + char-counter внизу справа. Trust-паттерн: «причина» всегда с counter.">
          <VB h="Состояния">
            <DM label="default"><Txa /></DM>
            <DM label="focus"><Txa state="focus" /></DM>
            <DM label="filled"><Txa value="Обновление ставок майнинга на Q2." count="34 / 500" /></DM>
            <DM label="error"><Txa state="error" value="ok" count="2 / 500" /></DM>
            <DM label="disabled"><Txa state="disabled" value="Заблокировано" /></DM>
          </VB>
        </Sec>

        <Sec n="07" name="Select" desc="API сохранён (StyledSelect). Trigger-состояния + открытый дропдаун с состояниями опций. Скин — токены, механика не меняется.">
          <VB h="Trigger · состояния">
            <DM label="default"><Sel /></DM>
            <DM label="focus"><Sel state="focus" /></DM>
            <DM label="filled"><Sel value="Майнинг" /></DM>
            <DM label="error"><Sel state="error" value="–" /></DM>
            <DM label="disabled"><Sel state="disabled" value="Майнинг" /></DM>
          </VB>
          <Sep />
          <VB h="Открытый дропдаун · состояния опций">
            <DM label="on / hover / disabled"><Sel value="Майнинг" open /></DM>
          </VB>
        </Sec>

        <Sec n="08" name="Checkbox" desc="off · on · indeterminate (для «выбрать всё» в таблицах) · disabled ×2 · focus-visible.">
          <VB h="Состояния">
            <DM label="off"><Cbx kind="off" label="Не выбрано" /></DM>
            <DM label="on"><Cbx kind="on" label="Выбрано" /></DM>
            <DM label="indeterminate"><Cbx kind="ind" label="Частично" /></DM>
            <DM label="disabled off"><Cbx kind="dis" label="Disabled" /></DM>
            <DM label="disabled on"><Cbx kind="dison" label="Disabled on" /></DM>
            <DM label="focus-visible"><Cbx kind="focus" label="Focus" /></DM>
          </VB>
        </Sec>

        <Sec n="09" name="Radio" desc="Simple (circle+label) + card-variant (выбор-карточка). Card — бренд-бордер+tint при selected. Приоритет: онбординг подключения чата.">
          <VB h="Simple · состояния">
            <DM label="off"><Rb kind="off" label="Не выбрано" /></DM>
            <DM label="on"><Rb kind="on" label="Выбрано" /></DM>
            <DM label="disabled"><Rb kind="dis" label="Disabled" /></DM>
            <DM label="focus-visible"><Rb kind="focus" label="Focus" /></DM>
          </VB>
          <Sep />
          <VB h="Card-variant · онбординг подключения чата">
            <DM label="default"><RbCard icon={Users} title="В готовое сообщество" desc="Подключить бота к существующему чату" /></DM>
            <DM label="selected"><RbCard on icon={Globe} title="Новое отдельное" desc="Создать новый чат с нуля" /></DM>
            <DM label="disabled"><RbCard dis icon={Activity} title="Недоступно" desc="Опция временно заблокирована" /></DM>
          </VB>
        </Sec>

        <Sec n="10" name="Tabs" desc="primary (тёмная пилюля) · subtle (синяя пилюля) · underline (бренд-линия, 200ms). Клик переключает.">
          <VB h="primary — тёмная активная"><Tabs variant="primary" /></VB>
          <Sep />
          <VB h="subtle — синяя активная"><Tabs variant="subtle" /></VB>
          <Sep />
          <VB h="underline — бренд-линия под-навигации"><Tabs variant="underline" /></VB>
        </Sec>

        <Sec n="11" name="Tooltip" desc="4 направления. Всегда тёмный (#1B1B22 / светлый текст) в обеих темах. НАВЕДИ на иконку — подсказка появляется (в покое скрыта).">
          <VB h="top · right · bottom · left — наведи мышь на иконку">
            <div className="flex gap-16 py-10">
              <DM label="top"><Tip dir="top" /></DM>
              <DM label="right"><Tip dir="right" /></DM>
              <DM label="bottom"><Tip dir="bottom" /></DM>
              <DM label="left"><Tip dir="left" /></DM>
            </div>
          </VB>
        </Sec>

        <Sec n="12" name="DashedAdd / EmptySlot" desc="Одна семантика — два форм-фактора. Пунктир 1.5px dashed — ТОЛЬКО «добавить / пусто / drop-таргет» (§11). Hover: бренд-бордер + tint.">
          <VB h="Inline button-row · состояния">
            <DM label="default"><DashAdd /></DM>
            <DM label="hover (форс)"><DashAdd force="border-cta text-cta bg-[color-mix(in_oklab,var(--cta)_8%,transparent)]" /></DM>
          </VB>
          <Sep />
          <VB h="EmptySlot card · состояния">
            <DM label="default"><EmptySlot /></DM>
            <DM label="hover (форс)"><EmptySlot force="border-cta bg-[color-mix(in_oklab,var(--cta)_6%,transparent)]" /></DM>
          </VB>
        </Sec>

        <div className="mt-14 mb-2 text-[11px] font-extrabold tracking-[.2em] uppercase text-cta">— Tier T2 · составные —</div>

        <Sec n="13" name="Table" desc="Заголовок с сортировкой · строки default/hover/selected · status-dot · чекбокс с indeterminate · 3-dot меню · empty state. Кликабельно.">
          <VB h="Таблица · все состояния строк (кликай чекбоксы)"><div className="w-full"><DSTable /></div></VB>
          <Sep />
          <VB h="Empty state"><div className="w-full max-w-[460px]"><TableEmpty /></div></VB>
        </Sec>

        <Sec n="14" name="Modal" desc="Форм-модал + confirm-danger. Backdrop rgba .45 + blur 4. Радиус 16, max-w 440.">
          <VB h="Spec-view (форм + danger)">
            <DM label="форм-модал"><ModalCard /></DM>
            <DM label="danger confirm"><ModalCard danger /></DM>
          </VB>
        </Sec>

        <Sec n="15" name="Stepper" desc="Re-skin. done — --ok + чек. active — бренд-градиент + pulse-step 1.8s (канон index.css). future — рамка.">
          <VB h="Горизонтальный (current = шаг 2)"><div className="w-full max-w-[460px]"><DSStepper /></div></VB>
          <Sep />
          <VB h="Compact (без лейблов)"><div className="w-full max-w-[300px]"><DSStepper compact /></div></VB>
        </Sec>

        <Sec n="16" name="StatRing" desc="SVG-кольцо, stroke = бренд-градиент #3b82f6→#a855f7. Центр — tabular число + лейбл. 3 размера.">
          <VB h="lg 120 · md 90 · sm 72">
            <DM label="lg · 120"><StatRing size={120} pct={74} label="Активность" /></DM>
            <DM label="md · 90"><StatRing size={90} pct={68} label="Аптайм" /></DM>
            <DM label="sm · 72"><StatRing size={72} pct={42} label="Лимит" val="42%" /></DM>
          </VB>
        </Sec>

        <Sec n="17" name="Pagination" desc="Prev/next стрелки + номера + эллипсис. Текущая — --cta fill. Disabled — opacity .35.">
          <VB h="Страница 3 / 6"><Pagination page={3} /></VB>
        </Sec>

        <Sec n="18" name="TwoColLayout" desc="Grid 1fr + 280px, gap 16. Схлоп в 1 колонку ≤768px. Один компонент — не верстать по месту (§11).">
          <VB h="Desktop · main + aside"><div className="w-full"><TwoCol /></div></VB>
        </Sec>

        <Sec n="19" name="Section" desc="Единая оболочка секций: eyebrow + заголовок + правый слот + collapsible. Контейнер миграции сложных экранов (§10).">
          <VB h="Expanded / Collapsed (клик по шапке)"><div className="w-full max-w-[520px]"><SectionShell /></div></VB>
        </Sec>

        <Sec n="20" name="Sidebar §5a" desc="Expanded 248 / collapsed 80. Active-пилюля + иконка в --cta. ФИКС #7: collapsed → бейдж становится точкой в углу иконки, НЕ числом (число залезало).">
          <VB h="Expanded 248px  ·  Collapsed 80px (смотри бейджи Журнал/Триггеры)">
            <div className="flex gap-8 items-start">
              <DM label="expanded · число-бейдж"><Sidebar /></DM>
              <DM label="collapsed · бейдж→точка ✓"><Sidebar collapsed /></DM>
            </div>
          </VB>
        </Sec>

        <div className="mt-14 mb-2 text-[11px] font-extrabold tracking-[.2em] uppercase text-ok">— БОЕВЫЕ shared (cutover §2b · реальные импорты) —</div>
        <Sec n="✓" name="Боевые shared-компоненты" desc="Это РЕАЛЬНЫЕ Admin_SITE/components/shared/* (Button/Toggle/Card/StyledSelect/Stepper), переведённые на токены. API/логика не тронуты (§12.1), behavior-preserving (§10). Проверь обе темы — это то, что попадёт на прод.">
          <RealShowcase />
        </Sec>

        <div className="mt-12 text-center text-[11px] text-lbl">
          Puls Chat Design System · token-tree §2.5 · обе темы · glow CANON v2 · T1 (12/12) + T2 (8/8) + боевые shared · DESIGN_BRIEF
        </div>
      </div>
    </div>
  );
}
