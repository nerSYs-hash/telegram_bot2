import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function EconomyMiniChart({ data }) {
  if (!data || data.length < 2) return null;

  return (
    <div className="bg-gray-50 rounded-2xl p-4">
      <div className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">
        График изменений
      </div>
      <ResponsiveContainer width="100%" height={80}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="econ-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#3B82F6" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="date" hide />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{ background: '#111827', border: 'none', borderRadius: 12, color: '#fff', fontSize: 11 }}
            labelStyle={{ color: '#9CA3AF', fontSize: 10 }}
            formatter={(v) => [v, 'значение']}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#3B82F6"
            strokeWidth={2}
            fill="url(#econ-grad)"
            dot={false}
            activeDot={{ r: 4, fill: '#3B82F6' }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
