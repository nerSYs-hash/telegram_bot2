import { Coins, TrendingUp, TrendingDown, Gem, Repeat2, Landmark, Users } from 'lucide-react';

function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return Number(n).toLocaleString('ru-RU');
}

// ── Компактная метрика ────────────────────────────────────────────
function Metric({ icon: Icon, label, value, valueClass = 'text-tx' }) {
  return (
    <div className="rounded-2xl bg-sff border border-bd shadow-sm p-3 flex flex-col gap-1 min-w-0">
      <div className="flex items-center gap-1.5">
        {Icon && <Icon size={13} className="text-warn shrink-0" />}
        <span className="text-[9px] font-black uppercase tracking-widest text-lbl truncate">{label}</span>
      </div>
      <div className={`text-lg md:text-xl font-black leading-tight truncate ${valueClass}`}>
        {value}
      </div>
    </div>
  );
}

// ── Главный компонент ─────────────────────────────────────────────
export default function EconomyHeader({ metrics }) {
  if (!metrics) {
    return (
      <div className="bg-sff rounded-3xl border border-bd shadow-sm p-4 space-y-3">
        <div className="h-5 w-32 bg-sf2 rounded-full animate-pulse" />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 bg-sf2 rounded-2xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const { pulse_rate, bank_balance, users_balance, total_supply, emission_24h, emission_7d } = metrics;
  const emPos = (emission_24h ?? 0) >= 0;
  const EmIcon = emPos ? TrendingUp : TrendingDown;

  return (
    <div className="bg-sff rounded-3xl border border-bd shadow-sm p-4
                    sticky -top-4 sm:-top-6 lg:-top-8 z-30 space-y-3">

      {/* Заголовок */}
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-xl bg-[color-mix(in_oklab,var(--warn)_16%,transparent)] flex items-center justify-center">
          <Coins size={14} className="text-warn" />
        </div>
        <h1 className="text-sm font-black uppercase tracking-widest text-tx">Экономика</h1>
        <div className="ml-auto flex items-center gap-1.5">
          <span className="text-[9px] font-black uppercase tracking-widest text-lbl">live</span>
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
        </div>
      </div>

      {/* Все метрики — компактная сетка */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        <Metric icon={Gem}      label="В обороте"   value={`${fmt(total_supply)}`} valueClass="text-cta" />
        <Metric icon={Repeat2}  label="Курс пульса" value={`${Number(pulse_rate).toFixed(2)} ₽`} valueClass="text-purple" />
        <Metric icon={Landmark} label="В банке"     value={`${fmt(bank_balance)}`} />
        <Metric icon={Users}    label="У юзеров"    value={`${fmt(users_balance)}`} />
        <div className="rounded-2xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-[color-mix(in_oklab,var(--ok)_30%,transparent)] p-3 flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <EmIcon size={12} className="text-ok" />
            <span className="text-[9px] font-black uppercase tracking-widest text-ok truncate">
              Эмиссия 24ч
            </span>
          </div>
          <div className="flex items-baseline gap-2 min-w-0">
            <span className="text-lg md:text-xl font-black leading-tight text-ok truncate">
              {emPos ? '+' : ''}{fmt(emission_24h ?? 0)}
            </span>
            <span className="text-[10px] font-black text-ok shrink-0">
              7д: +{fmt(emission_7d ?? 0)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
