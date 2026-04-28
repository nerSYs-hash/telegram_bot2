import { PlusCircle } from 'lucide-react';
import EconomyRow from './EconomyRow';

const SUBCATEGORY_LABELS = {
  base:    '📑 Базовые ставки',
  combo:   '📑 Комбо-квесты',
  sprint:  '📑 Спринты',
  shipper: '📑 Шиппер-резонанс',
  defib:   '📑 Дефибриллятор',
};

export default function EconomySubTable({ subcategory, rows, onOpenHistory, recentlyChanged }) {
  const label = SUBCATEGORY_LABELS[subcategory] || `📑 ${subcategory}`;

  return (
    <div className="bg-gray-50/50 rounded-2xl p-4">
      <h3 className="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-3 px-1">
        {label}
      </h3>

      <div className="space-y-2">
        {rows.map(row => (
          <EconomyRow
            key={row.key}
            row={row}
            onOpenHistory={onOpenHistory}
            recentlyChanged={recentlyChanged}
          />
        ))}
      </div>

      <button
        disabled
        className="mt-3 w-full py-2.5 border-2 border-dashed border-gray-200 rounded-xl
                   text-gray-300 font-black text-[10px] uppercase
                   flex items-center justify-center gap-1.5 cursor-not-allowed">
        <PlusCircle size={12} /> Добавить параметр
      </button>
    </div>
  );
}
