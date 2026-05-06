import { Coins } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts';

function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return Number(n).toLocaleString('ru-RU');
}

function Metric({ icon, label, value, sub, highlight }) {
  return (
    <div className={`p-4 rounded-2xl ${highlight ? 'bg-blue-600' : 'bg-gray-800'}`}>
      <div className="text-xl mb-1">{icon}</div>
      <div className="text-[9px] font-black text-gray-400 uppercase tracking-widest leading-tight">{label}</div>
      <div className="text-lg font-black mt-1 leading-tight">{value}</div>
      {sub && <div className="text-[8px] text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function EconomyHeader({ metrics, chartData }) {
  if (!metrics) {
    return <div className="bg-gray-100 rounded-[2.5rem] h-48 animate-pulse" />;
  }

  const { pulse_rate, bank_balance, users_balance, total_supply, emission_24h, emission_7d } = metrics;

  return (
    <div className="bg-gray-900 text-white rounded-[2.5rem] p-6 md:p-8 sticky -top-4 sm:-top-6 lg:-top-8 z-30 shadow-2xl">
      <div className="flex items-center gap-3 mb-5">
        <Coins size={22} className="text-amber-400" />
        <h1 className="text-xl font-black uppercase tracking-widest">Экономика</h1>
        <span className="ml-auto text-[9px] font-black text-gray-500 uppercase tracking-widest">live</span>
        <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric icon="💱" label="Курс пульса"  value={`${Number(pulse_rate).toFixed(2)} ₽`} sub="read-only" />
        <Metric icon="🏦" label="В банке"       value={`${fmt(bank_balance)} 💎`} />
        <Metric icon="👥" label="У юзеров"      value={`${fmt(users_balance)} 💎`} />
        <Metric icon="📊" label="В обороте"     value={`${fmt(total_supply)} 💎`} highlight />
      </div>

      <div className="mt-5 pt-5 border-t border-gray-800 grid grid-cols-2 gap-4">
        <div>
          <div className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">Эмиссия 24ч</div>
          <div className="text-2xl font-black text-emerald-300 mt-1">+{fmt(emission_24h)} 💎</div>
          <div className="text-[9px] text-gray-500 mt-0.5">за 7д: +{fmt(emission_7d)} 💎</div>
        </div>
        {chartData?.length > 1 && (
          <div className="h-14">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="hdr-grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#10B981" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <Tooltip
                  contentStyle={{ background: '#1F2937', border: 'none', borderRadius: 8, color: '#fff', fontSize: 10 }}
                  formatter={(v) => [fmt(v), '💎']}
                />
                <Area type="monotone" dataKey="value" stroke="#10B981" strokeWidth={2}
                  fill="url(#hdr-grad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
