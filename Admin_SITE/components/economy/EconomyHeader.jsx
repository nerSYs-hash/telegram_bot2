import { Coins, TrendingUp, TrendingDown } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts';

function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return Number(n).toLocaleString('ru-RU');
}

// ── Маленькая карточка справа ──────────────────────────────────────
function SideCard({ icon, label, value, accent }) {
  return (
    <div className={`rounded-2xl p-4 border flex flex-col gap-1 ${
      accent
        ? 'bg-gradient-to-br from-violet-50 to-blue-50 border-violet-100'
        : 'bg-white border-gray-100 shadow-sm'
    }`}>
      <div className="flex items-center gap-1.5">
        <span className="text-base leading-none">{icon}</span>
        <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">{label}</span>
      </div>
      <div className={`text-2xl font-black leading-tight ${accent ? 'text-violet-700' : 'text-gray-900'}`}>
        {value}
      </div>
    </div>
  );
}

// ── Главный герой-блок ─────────────────────────────────────────────
function HeroCard({ value, chartData }) {
  return (
    <div className="rounded-2xl bg-gradient-to-br from-blue-600 via-blue-500 to-indigo-600
                    p-5 flex flex-col justify-between min-h-[160px] md:min-h-[180px]
                    shadow-lg shadow-blue-200 relative overflow-hidden">
      {/* Декоративный круг */}
      <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full bg-white/10 pointer-events-none" />
      <div className="absolute -right-4 -bottom-10 w-28 h-28 rounded-full bg-white/5 pointer-events-none" />

      <div>
        <div className="text-[10px] font-black uppercase tracking-widest text-blue-200 mb-1">
          В обороте
        </div>
        <div className="text-4xl md:text-5xl font-black text-white leading-none">
          {value}
        </div>
        <div className="text-sm text-blue-200 mt-1 font-semibold">💎 Пульсов</div>
      </div>

      {chartData?.length > 1 && (
        <div className="h-14 mt-3 -mx-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="hero-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#fff" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#fff" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <Tooltip
                contentStyle={{ background: '#1e40af', border: 'none', borderRadius: 8, color: '#fff', fontSize: 10 }}
                formatter={(v) => [fmt(v), '💎']}
              />
              <Area type="monotone" dataKey="value" stroke="rgba(255,255,255,0.7)"
                    strokeWidth={2} fill="url(#hero-grad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// ── Полоса эмиссии ────────────────────────────────────────────────
function EmissionBar({ emission24h, emission7d }) {
  const isPositive = emission24h >= 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  return (
    <div className="rounded-2xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-100
                    px-5 py-4 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
          <Icon size={18} className="text-emerald-600" />
        </div>
        <div>
          <div className="text-[10px] font-black uppercase tracking-widest text-emerald-600">Эмиссия 24ч</div>
          <div className="text-2xl font-black text-emerald-700 leading-tight">
            {isPositive ? '+' : ''}{fmt(emission24h)} 💎
          </div>
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-0.5">За 7 дней</div>
        <div className="text-sm font-black text-emerald-600">+{fmt(emission7d)} 💎</div>
      </div>
    </div>
  );
}

// ── Главный компонент ─────────────────────────────────────────────
export default function EconomyHeader({ metrics, chartData }) {
  if (!metrics) {
    return (
      <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 space-y-4">
        <div className="h-5 w-32 bg-gray-100 rounded-full animate-pulse" />
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2 h-44 bg-gray-100 rounded-2xl animate-pulse" />
          <div className="space-y-3">
            <div className="h-20 bg-gray-100 rounded-2xl animate-pulse" />
            <div className="h-20 bg-gray-100 rounded-2xl animate-pulse" />
          </div>
        </div>
        <div className="h-16 bg-gray-100 rounded-2xl animate-pulse" />
      </div>
    );
  }

  const { pulse_rate, bank_balance, users_balance, total_supply, emission_24h, emission_7d } = metrics;

  return (
    <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-5 md:p-6
                    sticky -top-4 sm:-top-6 lg:-top-8 z-30 space-y-3">

      {/* Заголовок */}
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-amber-100 flex items-center justify-center">
          <Coins size={16} className="text-amber-600" />
        </div>
        <h1 className="text-base font-black uppercase tracking-widest text-gray-900">Экономика</h1>
        <div className="ml-auto flex items-center gap-1.5">
          <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">live</span>
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
        </div>
      </div>

      {/* Bento сетка */}
      <div className="grid grid-cols-3 gap-3">
        {/* Герой — В обороте */}
        <div className="col-span-2">
          <HeroCard value={fmt(total_supply)} chartData={chartData} />
        </div>

        {/* Правая колонка */}
        <div className="col-span-1 flex flex-col gap-3">
          <SideCard icon="💱" label="Курс пульса"
                    value={`${Number(pulse_rate).toFixed(2)} ₽`}
                    accent />
          <SideCard icon="🏦" label="В банке"
                    value={`${fmt(bank_balance)} 💎`} />
        </div>
      </div>

      {/* Нижняя строка: У юзеров + Эмиссия */}
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-1">
          <SideCard icon="👥" label="У юзеров" value={`${fmt(users_balance)} 💎`} />
        </div>
        <div className="col-span-2">
          <EmissionBar emission24h={emission_24h ?? 0} emission7d={emission_7d ?? 0} />
        </div>
      </div>
    </div>
  );
}
