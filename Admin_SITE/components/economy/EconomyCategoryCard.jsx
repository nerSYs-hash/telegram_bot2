import { useEffect, useMemo, useState } from 'react';
import {
  X, Pickaxe, Gem, Ticket, Grid2x2, Gift, UsersRound, Heart, Settings,
  Edit, BarChart3, Coins, Crown, Ban, HelpCircle, AlertTriangle,
} from 'lucide-react';
import Toggle from '../shared/Toggle';
import Tooltip from '../shared/Tooltip';
import TitlesPanel from '../titles/TitlesPanel';
import EconomyCancellationsPanel from './EconomyCancellationsPanel';
import ModuleStatusBanner from '../modules/ModuleStatusBanner';

// V1.17.0h2b (21.05): вертикальная карточка с inline-expand.
// Collapsed = 130px, Expanded = 450px (карусель скроллится через EconomyPage).
// Единый стиль с Модулями: синяя плашка-иконка по умолчанию + lucide-иконки
// + paid-лента для донатных + hover-уголок цветом категории.

const CATEGORY_META = {
  // Системная карточка: всегда есть, мастер-свич скрыт (нельзя отключить)
  cancellations:{ Icon: Ban,        accent: 'var(--danger)', rgb: '255,69,58',   paid: false, system: true },
  mining:       { Icon: Pickaxe,    accent: 'var(--warn)',   rgb: '255,159,10',  paid: false },
  vip_bbs:      { Icon: Gem,        accent: 'var(--cta)',    rgb: '0,102,204',   paid: true  },
  titles:       { Icon: Crown,      accent: '#FFD60A',       rgb: '255,214,10',  paid: true  },
  lottery:      { Icon: Ticket,     accent: 'var(--purple)', rgb: '191,90,242',  paid: false },
  bingo:        { Icon: Grid2x2,    accent: 'var(--mint)',   rgb: '102,212,207', paid: false },
  monthly_gift: { Icon: Gift,       accent: 'var(--pink)',   rgb: '255,55,95',   paid: false },
  referral:     { Icon: UsersRound, accent: 'var(--ok)',     rgb: '50,215,75',   paid: false },
  bbs_bonus:    { Icon: Heart,      accent: 'var(--danger)', rgb: '255,69,58',   paid: false },
};
const DEFAULT_META = { Icon: Settings, accent: 'var(--lbl)', rgb: '156,163,175', paid: false };

// Категория Экономики → id модуля в каталоге (module_toggles). Для большинства
// совпадает с category.key; явное отображение только для расхождений.
const CATEGORY_TO_MODULE = { vip_bbs: 'bbs_vip' };

const SUBCAT_LABELS = {
  base:       '📑 Базовые ставки',
  base_coeff: '📑 Базовые коэффициенты',
  combo:      '📑 Комбо-квесты',
  sprint:     '📑 Спринты',
  penalty:    '📑 Штрафы',
  shipper:    '⚡ Буст · Шиппер-резонанс',
  defib:      '⚡ Буст · Дефибриллятор',
};

// Подсказка к единице значения (tooltip) — чтобы было понятно, что за число.
const UNIT_HINT = {
  'x':   'коэффициент / множитель',
  '×':   'коэффициент / множитель',
  '💎':  'Пульсы',
  'ч':   'часы',
  'мин': 'минуты',
};

// DEV-fallback: тестовые параметры для каждой категории, видны в expanded
// когда бэкенд не отвечает (для дизайн-QA на localhost).
const _DEV_PREVIEW = typeof window !== 'undefined'
  && import.meta.env.DEV
  && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

const _MOCK_SETTINGS = {
  mining: [
    { key: 'm1', label: 'Базовая ставка', description: 'Начисление за сообщение', value: 10, unit: '💎', is_enabled: true,  history_count: 7, subcategory: 'base',    min_value: 1,   max_value: 100 },
    { key: 'm2', label: 'Дневной лимит',  description: 'Макс. начислений в день', value: 500, unit: '💎', is_enabled: true,  history_count: 3, subcategory: 'base',    min_value: 100, max_value: 5000 },
    { key: 'm3', label: 'Кулдаун',        description: 'Интервал между начислениями', value: 30, unit: 'сек', is_enabled: true, history_count: 2, subcategory: 'base', min_value: 0, max_value: 3600 },
    { key: 'm4', label: 'Комбо-бонус',    description: 'Множитель за серию',      value: 1.5, unit: '×',   is_enabled: false, history_count: 0, subcategory: 'combo',  min_value: 1, max_value: 10 },
    { key: 'm5', label: 'Спринт-бонус',   description: 'Бонус за активность в спринте', value: 50, unit: '💎', is_enabled: true, history_count: 5, subcategory: 'sprint', min_value: 10, max_value: 500 },
    { key: 'm6', label: 'Шиппер-резонанс',description: 'Бонус при активном шиппере', value: 2.0, unit: '×',  is_enabled: true, history_count: 1, subcategory: 'shipper', min_value: 1, max_value: 5 },
  ],
  vip_bbs: [
    { key: 'v1', label: 'VIP-множитель',     description: 'Множитель для VIP',         value: 2.5,  unit: '×',  is_enabled: true, history_count: 12, subcategory: 'base', min_value: 1,   max_value: 10 },
    { key: 'v2', label: 'Цена VIP-статуса',  description: 'Стоимость VIP на 30 дней',  value: 1000, unit: '💎', is_enabled: true, history_count: 4,  subcategory: 'base', min_value: 100, max_value: 50000 },
    { key: 'v3', label: 'BBS базовая ставка',description: 'Начисление за активность',  value: 25,   unit: '💎', is_enabled: true, history_count: 8,  subcategory: 'base', min_value: 5,   max_value: 200 },
    { key: 'v4', label: 'Дефибриллятор',     description: 'Оживление неактивных',      value: 100,  unit: '💎', is_enabled: false, history_count: 2, subcategory: 'defib', min_value: 10, max_value: 1000 },
  ],
  lottery: [
    { key: 'l1', label: 'Цена билета', description: 'Стоимость лотерейного билета', value: 50,   unit: '💎', is_enabled: false, history_count: 3, subcategory: 'base', min_value: 10,  max_value: 500 },
    { key: 'l2', label: 'Джекпот',     description: 'Максимальный выигрыш',         value: 5000, unit: '💎', is_enabled: false, history_count: 1, subcategory: 'base', min_value: 100, max_value: 100000 },
  ],
  bingo: [
    { key: 'b1', label: 'Приз победителя', description: 'Начисление за победу', value: 200, unit: '💎', is_enabled: true, history_count: 5, subcategory: 'base', min_value: 50, max_value: 2000 },
    { key: 'b2', label: 'Взнос участника', description: 'Стоимость участия',    value: 20,  unit: '💎', is_enabled: true, history_count: 2, subcategory: 'base', min_value: 5,  max_value: 500 },
  ],
  monthly_gift: [
    { key: 'g1', label: 'Топ-1 приз', description: 'Приз за 1-е место', value: 10000, unit: '💎', is_enabled: true, history_count: 2, subcategory: 'base', min_value: 1000, max_value: 100000 },
    { key: 'g2', label: 'Топ-3 приз', description: 'Приз за 3-е место', value: 3000,  unit: '💎', is_enabled: true, history_count: 2, subcategory: 'base', min_value: 100,  max_value: 50000 },
  ],
  referral: [
    { key: 'r1', label: 'Реферальный бонус', description: 'Начисление за приведённого', value: 150, unit: '💎', is_enabled: true, history_count: 6, subcategory: 'base', min_value: 10, max_value: 5000 },
  ],
  bbs_bonus: [
    { key: 'bb1', label: 'Бонус за ❤️', description: 'За реакцию ❤️ в чате', value: 5, unit: '💎', is_enabled: true, history_count: 4, subcategory: 'base', min_value: 1, max_value: 50 },
  ],
};

function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return Number(n).toLocaleString('ru-RU');
}

export default function EconomyCategoryCard({
  category, active, onActivate, onClose,
  onOpenHistory,
  modulesApi, canEdit, canCancel, token, recentlyChanged,
}) {
  const meta = CATEGORY_META[category.key] || DEFAULT_META;
  const Icon = meta.Icon;

  // Состояние модуля берём из каталога module_toggles (единая точка
  // управления). Системная карточка «Отмены выплат» — всегда активна.
  const moduleId   = CATEGORY_TO_MODULE[category.key] || category.key;
  const moduleRec  = modulesApi?.modules?.find(m => m.id === moduleId);
  const moduleOn   = meta.system ? true : !!moduleRec?.is_enabled;
  const showBanner = !meta.system && !!modulesApi && !!moduleRec;

  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [topRow, setTopRow] = useState(null);
  const [hover, setHover] = useState(false);

  // Главный параметр для collapsed-state (один fetch при монтировании)
  useEffect(() => {
    if (category.key === 'titles') return; // Титулы без topRow в collapsed
    const useDevMock = () => {
      if (!_DEV_PREVIEW) return;
      const arr = _MOCK_SETTINGS[category.key] || [];
      if (arr.length) setTopRow(arr[0]);
    };
    if (!token) { useDevMock(); return; }
    fetch(`/api/economy/settings?category=${category.key}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (Array.isArray(d) && d.length > 0) setTopRow(d[0]);
        else useDevMock();
      })
      .catch(() => useDevMock());
  }, [category.key, token]);

  // Полная подгрузка параметров при раскрытии (+dev-fallback на mock)
  useEffect(() => {
    if (!active || settings) return;
    if (category.key === 'titles') return; // Титулы рендерят свой TitlesPanel
    if (!token) {
      if (_DEV_PREVIEW) setSettings(_MOCK_SETTINGS[category.key] || []);
      return;
    }
    setLoading(true);
    fetch(`/api/economy/settings?category=${category.key}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (Array.isArray(d) && d.length) setSettings(d);
        else setSettings(_DEV_PREVIEW ? (_MOCK_SETTINGS[category.key] || []) : []);
      })
      .catch(() => {
        setSettings(_DEV_PREVIEW ? (_MOCK_SETTINGS[category.key] || []) : []);
      })
      .finally(() => setLoading(false));
  }, [active, category.key, token, settings]);

  const grouped = useMemo(() => {
    if (!settings) return {};
    return settings.reduce((acc, s) => {
      const k = s.subcategory || 'base';
      (acc[k] = acc[k] || []).push(s);
      return acc;
    }, {});
  }, [settings]);

  const isDisabled = !moduleOn;

  // Inline-редактирование параметра — НЕ через модалку (по решению 21.05).
  // API вызывается тут, settings обновляется локально.
  const handleRowEdit = async (row, value, comment) => {
    if (token) {
      const r = await fetch(`/api/economy/settings/${row.key}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ value, comment }),
      });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'Ошибка');
    }
    // Применяем локально
    setSettings(prev => prev?.map(s => s.key === row.key ? { ...s, value, history_count: (s.history_count || 0) + 1 } : s));
  };

  const handleRowToggle = async (row, comment) => {
    if (token) {
      const r = await fetch(`/api/economy/settings/${row.key}/toggle`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ comment }),
      });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'Ошибка');
    }
    setSettings(prev => prev?.map(s => s.key === row.key ? { ...s, is_enabled: !s.is_enabled, history_count: (s.history_count || 0) + 1 } : s));
  };

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={!active ? onActivate : undefined}
      className={`relative flex-shrink-0 rounded-2xl border bg-sff overflow-hidden
                  transition-[width,box-shadow,border-color] duration-500
                  ${active
                    ? `h-full shadow-xl border-[color-mix(in_oklab,${meta.accent}_60%,transparent)]`
                    : `h-full cursor-pointer shadow-sm ${isDisabled ? 'border-bd2 opacity-60' : 'border-bd hover:shadow-lg'}`
                  }`}
      style={{
        width: active ? 450 : 130,
        minWidth: active ? 450 : 130,
        transitionTimingFunction: 'cubic-bezier(.22,1,.36,1)',
      }}
    >
      {/* ── Hover-уголок (только в collapsed): маленький треугольник цветом категории ── */}
      {!active && (
        <div
          aria-hidden
          className="absolute top-0 left-0 w-6 h-6 pointer-events-none
                     transition-opacity duration-200 z-10"
          style={{
            background: meta.accent,
            clipPath: 'polygon(0 0, 100% 0, 0 100%)',
            opacity: hover && !isDisabled ? 1 : 0,
            borderTopLeftRadius: 16,
          }}
        />
      )}

      {/* ── Paid-лента: только в collapsed (по решению Ильи 21.05 —
              в expanded она мешает, обсудим место позже). ── */}
      {meta.paid && !active && (
        <div
          className="absolute -top-px right-5 w-7 pointer-events-none z-20"
          title="Донатная функция — реальные деньги"
        >
          <div
            className="bg-amber-500 text-white flex items-center justify-center pt-1.5 pb-3 shadow-md"
            style={{ clipPath: 'polygon(0 0,100% 0,100% 100%,50% 72%,0 100%)' }}
          >
            <Coins size={12} />
          </div>
        </div>
      )}

      {/* ══ COLLAPSED ══ (crossfade при переходе в expanded) ══ */}
      <div
        className={`absolute inset-0 h-full p-3 flex flex-col gap-2 select-none
                    transition-opacity duration-300
                    ${active ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
      >
        {/* Watermark: небольшая полупрозрачная иконка в нижнем-правом углу */}
        <div
          aria-hidden
          className="absolute -bottom-5 -right-5 pointer-events-none select-none
                     text-[color-mix(in_oklab,var(--tx)_5%,transparent)]"
        >
          <Icon size={80} strokeWidth={1.5} />
        </div>

        {/* Иконка-плашка как в Модулях */}
        <div
          className={`relative w-11 h-11 rounded-2xl flex items-center justify-center flex-shrink-0
                      ${moduleOn ? 'bg-cta text-white' : 'bg-sf2 text-txd'}`}
        >
          <Icon size={20} />
        </div>

        {/* Название */}
        <div className="relative text-[13px] font-black text-tx leading-tight line-clamp-2 mt-1">
          {category.label}
        </div>

        {/* Главный параметр (если подгружен) */}
        {topRow ? (
          <div className="relative mt-auto">
            <div className="text-[9px] font-bold text-lbl uppercase tracking-wider truncate">
              {topRow.label}
            </div>
            <div className="text-lg font-black text-tx leading-none font-mono">
              {fmt(topRow.value)}
            </div>
          </div>
        ) : (
          <div className="relative mt-auto text-[10px] text-lbl">
            {category.rows_count} парам.
          </div>
        )}

        {/* Статус-точка */}
        <div className="relative flex items-center gap-1.5">
          <div
            className={`w-1.5 h-1.5 rounded-full flex-shrink-0
                        ${moduleOn ? 'bg-ok' : 'bg-danger'}`}
          />
          <span className="text-[9px] font-bold text-lbl">
            {moduleOn ? 'Активно' : 'Выкл.'}
          </span>
        </div>
      </div>

      {/* ══ EXPANDED ══ (crossfade появление) ══ */}
      <div
        className={`h-full flex flex-col transition-opacity duration-300
                    ${active ? 'opacity-100 delay-200' : 'opacity-0 pointer-events-none'}`}
      >
          {/* Тонкая верхняя кромка цветом категории */}
          <div className="h-2 flex-shrink-0" style={{ background: meta.accent }} />

          {/* Белая шапка с тонкой линией снизу — цветом верхней кромки */}
          <div
            className="flex items-center gap-3 px-4 py-3 flex-shrink-0 bg-sff
                       border-b-2"
            style={{ borderBottomColor: meta.accent }}
          >
            {/* Иконка-плашка как в Модулях: синяя + белая иконка */}
            <div className="w-11 h-11 rounded-2xl bg-cta text-white flex items-center justify-center flex-shrink-0">
              <Icon size={20} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[9px] font-black uppercase tracking-widest text-lbl">
                Категория
              </div>
              <div className="text-base font-black text-tx truncate">
                {category.label}
              </div>
            </div>

            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onClose(); }}
              className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0
                         bg-sf2 text-txd hover:bg-bd hover:text-tx transition"
              title="Свернуть"
            >
              <X size={16} />
            </button>
          </div>

          {/* Контент карточки */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 min-h-0">
            {/* Статус модуля — единая точка управления в каталоге «Модули».
                Тумблер с карточки убран: вкл/выкл здесь только индикатор
                + быстрое включение, отключение — из каталога с причиной. */}
            {showBanner && (
              <ModuleStatusBanner
                moduleId={moduleId}
                moduleName={category.label}
                modulesApi={modulesApi}
              />
            )}
            {/* Дисклеймер донатных категорий — ответственность за платежи */}
            {meta.paid && (
              <div className="rounded-xl border px-3 py-2.5 flex items-start gap-2
                              border-[color-mix(in_oklab,var(--warn)_35%,transparent)]
                              bg-[color-mix(in_oklab,var(--warn)_8%,transparent)]">
                <span className="text-warn flex-shrink-0 mt-0.5"><AlertTriangle size={14} /></span>
                <p className="text-[10px] text-txd leading-relaxed">
                  <strong className="text-tx">Донатная система.</strong> Мы не несём
                  ответственности за приём и обработку платежей. Вы можете подключить
                  сторонние сервисы приёма оплаты или принимать оплату звёздами
                  Telegram внутри бота.
                </p>
              </div>
            )}
            {/* Спец-случай: «Отмены выплат» — системная карточка, всегда
                первая, относится ко всем модулям Экономики. В expanded:
                сводка + кнопка «Открыть полную панель» (drawer с журналом). */}
            {category.key === 'cancellations' ? (
              <div className="space-y-3">
                <div className="flex items-start gap-2">
                  <div className="text-[11px] text-txd leading-relaxed flex-1">
                    Системная функция: откат начисленных пульсов по конкретной
                    транзакции (точечно) или массово за период. Действует на
                    <strong> все подключённые модули</strong> Экономики.
                  </div>
                  <Tooltip content="Точечная — отмена по ID транзакции. Массовая — по периоду и категории. Любое действие необратимо и попадает в журнал отмен ниже.">
                    <span className="w-7 h-7 flex items-center justify-center rounded-full bg-sf2 text-lbl cursor-help hover:bg-bd hover:text-tx transition shrink-0">
                      <HelpCircle size={14} />
                    </span>
                  </Tooltip>
                </div>
                <EconomyCancellationsPanel
                  embedded
                  token={token}
                  canCancel={canCancel}
                />
              </div>
            ) : category.key === 'titles' ? (
              <TitlesPanel token={token} canEdit={canEdit} embedded={true} />
            ) : (
              <>
                {loading && (
                  <div className="text-center py-8 text-[12px] text-lbl font-bold">
                    Загрузка…
                  </div>
                )}
                {!loading && settings && settings.length === 0 && (
                  <div className="text-center py-8 text-[12px] text-lbl font-bold">
                    Параметров пока нет
                  </div>
                )}
                {!loading && settings && settings.length > 0 && (
                  <p className="text-[10px] text-lbl leading-relaxed px-1">
                    Нажми на значение, чтобы изменить его. Тумблер включает или выключает параметр.
                  </p>
                )}
                {!loading && settings && Object.entries(grouped).map(([subKey, rows]) => (
                  <div key={subKey}>
                    <div className="text-[10px] font-black text-lbl uppercase tracking-widest mb-2 px-1">
                      {SUBCAT_LABELS[subKey] || `📑 ${subKey}`}
                    </div>
                    <div className="space-y-1.5">
                      {rows.map(row => (
                        <DetailRow
                          key={row.key}
                          row={row}
                          onEdit={(value, comment) => handleRowEdit(row, value, comment)}
                          onToggle={(comment) => handleRowToggle(row, comment)}
                          onHistory={() => onOpenHistory?.(row.key, row.label)}
                          recentlyChanged={recentlyChanged}
                          canEdit={canEdit}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
    </div>
  );
}

function DetailRow({ row, onEdit, onToggle, onHistory, recentlyChanged, canEdit }) {
  const isRecent = recentlyChanged?.has(row.key);
  // defib-множитель: «(xN = +M%)» считаем динамически по текущему значению
  const descText = (row.key === 'defib.buff_multiplier' && row.description)
    ? `${row.description} (x${Number(row.value)} = +${Math.round((Number(row.value) - 1) * 100)}%)`
    : row.description;
  // mode: 'view' | 'edit' | 'toggle' — inline-формы прямо в карточке
  const [mode, setMode] = useState('view');
  const [value, setValue] = useState(String(row.value));
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const reset = () => {
    setMode('view'); setValue(String(row.value)); setComment(''); setError(null);
  };

  const validValue = () => {
    const v = parseFloat(String(value).replace(',', '.'));
    if (isNaN(v)) return false;
    if (row.min_value != null && v < row.min_value) return false;
    if (row.max_value != null && v > row.max_value) return false;
    return true;
  };
  const validComment = comment.trim().length >= 5;

  const submitEdit = async () => {
    if (!validValue() || !validComment || busy) return;
    setBusy(true); setError(null);
    try {
      const v = parseFloat(String(value).replace(',', '.'));
      await onEdit(v, comment.trim());
      reset();
    } catch (e) {
      setError(e.message || 'Ошибка'); setBusy(false);
    }
  };

  const submitToggle = async () => {
    if (!validComment || busy) return;
    setBusy(true); setError(null);
    try {
      await onToggle(comment.trim());
      reset();
    } catch (e) {
      setError(e.message || 'Ошибка'); setBusy(false);
    }
  };

  return (
    <div
      className={`rounded-xl border px-2.5 py-2 bg-sff
                  ${isRecent
                    ? 'border-[color-mix(in_oklab,var(--warn)_45%,transparent)] bg-[color-mix(in_oklab,var(--warn)_5%,transparent)]'
                    : mode !== 'view'
                      ? 'border-cta'
                      : 'border-bd hover:border-bd2'} transition`}
    >
      {/* ── VIEW: обычное состояние строки ── */}
      {mode === 'view' && (
        <div className="flex items-center gap-2.5">
          {/* что за параметр — название + полное пояснение (не обрезаем) */}
          <div className="flex-1 min-w-0">
            <div className="text-[12px] font-bold text-tx leading-snug">{row.label}</div>
            {descText && (
              <div className="text-[11px] text-lbl mt-0.5 leading-relaxed">{descText}</div>
            )}
          </div>
          {/* значение — кликабельное поле, открывает редактирование */}
          <button
            type="button"
            onClick={() => {
              if (!canEdit) return;
              setValue(String(row.value)); setComment(''); setError(null); setMode('edit');
            }}
            disabled={!canEdit}
            title={canEdit ? 'Нажми, чтобы изменить значение' : 'Нет прав на изменение'}
            className={`flex items-baseline gap-1 px-2.5 py-1.5 rounded-lg border flex-shrink-0 transition
                        ${canEdit
                          ? 'bg-sf2 border-bd2 hover:border-cta hover:bg-sff cursor-pointer'
                          : 'bg-sf2 border-bd cursor-not-allowed'}`}
          >
            <span className="text-[14px] font-black text-tx font-mono whitespace-nowrap">{row.value}</span>
            <span className="text-[10px] text-lbl font-bold" title={UNIT_HINT[row.unit] || ''}>
              {row.unit}
            </span>
          </button>
          {/* вкл/выкл этого начисления */}
          <Toggle
            checked={row.is_enabled}
            onChange={() => {
              if (!canEdit) return;
              setComment(''); setError(null); setMode('toggle');
            }}
            className={!canEdit ? 'opacity-50 pointer-events-none' : ''}
          />
          {/* история изменений параметра */}
          <button
            type="button"
            onClick={onHistory}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-lbl hover:bg-sf2 hover:text-cta transition shrink-0"
            title="История изменений"
          >
            <BarChart3 size={13} />
          </button>
        </div>
      )}

      {/* ── EDIT: inline-форма редактирования значения ── */}
      {mode === 'edit' && (
        <div className="space-y-2">
          <div className="flex items-start gap-2">
            <div className="flex-1 text-[11px] font-bold text-tx">{row.label}</div>
            <Tooltip content="Введите новое число в допустимом диапазоне и причину (≥5 симв.) — изменение попадает в журнал и его можно откатить.">
              <span className="text-lbl cursor-help">
                <HelpCircle size={12} />
              </span>
            </Tooltip>
            <button
              type="button"
              onClick={reset}
              className="w-5 h-5 flex items-center justify-center rounded-md text-lbl hover:bg-sf2 hover:text-tx transition shrink-0"
              title="Закрыть"
            >
              <X size={12} />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              autoFocus
              placeholder={`${row.min_value ?? 0} — ${row.max_value ?? '∞'}`}
              className={`flex-1 px-2 py-1.5 rounded-lg text-[13px] font-mono font-bold bg-sff border
                          ${!validValue() && value ? 'border-danger' : 'border-bd2 focus:border-cta'} outline-none`}
            />
            {row.unit && <span className="text-[11px] text-lbl">{row.unit}</span>}
          </div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            placeholder="Причина (мин. 5 символов)"
            className="w-full px-2 py-1.5 rounded-lg text-[11px] bg-sff border border-bd2 focus:border-cta outline-none resize-none"
          />
          {error && <div className="text-[10px] text-danger">{error}</div>}
          <div className="flex gap-1.5">
            <button type="button" onClick={reset} disabled={busy}
              className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-sf2 border border-bd2 text-txd hover:bg-bd transition">
              Отмена
            </button>
            <button type="button" onClick={submitEdit}
              disabled={!validValue() || !validComment || busy}
              className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-cta text-white hover:brightness-110 transition disabled:opacity-40 disabled:cursor-not-allowed">
              {busy ? '…' : 'Сохранить'}
            </button>
          </div>
        </div>
      )}

      {/* ── TOGGLE: inline-форма подтверждения вкл/выкл ── */}
      {mode === 'toggle' && (
        <div className="space-y-2">
          <div className="flex items-start gap-2">
            <div className="flex-1 text-[11px] font-bold text-tx">
              {row.is_enabled ? '🔴 Выключить' : '🟢 Включить'} «{row.label}»?
            </div>
            <Tooltip content="Параметр перестанет/начнёт начислять. Изменение фиксируется в журнале — можно откатить.">
              <span className="text-lbl cursor-help">
                <HelpCircle size={12} />
              </span>
            </Tooltip>
            <button
              type="button"
              onClick={reset}
              className="w-5 h-5 flex items-center justify-center rounded-md text-lbl hover:bg-sf2 hover:text-tx transition shrink-0"
              title="Закрыть"
            >
              <X size={12} />
            </button>
          </div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            autoFocus
            placeholder="Причина (мин. 5 символов)"
            className="w-full px-2 py-1.5 rounded-lg text-[11px] bg-sff border border-bd2 focus:border-cta outline-none resize-none"
          />
          {error && <div className="text-[10px] text-danger">{error}</div>}
          <div className="flex gap-1.5">
            <button type="button" onClick={reset} disabled={busy}
              className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-sf2 border border-bd2 text-txd hover:bg-bd transition">
              Отмена
            </button>
            <button type="button" onClick={submitToggle}
              disabled={!validComment || busy}
              className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-cta text-white hover:brightness-110 transition disabled:opacity-40 disabled:cursor-not-allowed">
              {busy ? '…' : 'Подтвердить'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
