// EconomySubTable — под-таблица параметров одной подкатегории
// Экономики (legacy табличный вид).

import { PlusCircle } from 'lucide-react';
import EconomyRow from './EconomyRow';

const SUBCATEGORY_LABELS = {
  base:    '📑 Базовые ставки',
  combo:   '📑 Комбо-квесты',
  sprint:  '📑 Спринты',
  shipper: '📑 Шиппер-резонанс',
  defib:   '📑 Дефибриллятор',
};

export default function EconomySubTable({ subcategory, rows, onOpenHistory, onRowUpdated, recentlyChanged, token, canEdit }) {
  const label = SUBCATEGORY_LABELS[subcategory] || `📑 ${subcategory}`;

  return (
    <div className="bg-gray-50/50 rounded-2xl p-4">
      <h3 className="text-[10px] font-black text-txd uppercase tracking-widest mb-3 px-1">
        {label}
      </h3>

      <div className="space-y-2">
        {rows.map(row => (
          <EconomyRow
            key={row.key}
            row={row}
            onOpenHistory={onOpenHistory}
            onUpdated={onRowUpdated}
            recentlyChanged={recentlyChanged}
            token={token}
            canEdit={canEdit}
          />
        ))}
      </div>

      <button
        disabled
        className="mt-3 w-full py-2.5 border-2 border-dashed border-bd2 rounded-xl
                   text-lbl font-black text-[10px] uppercase
                   flex items-center justify-center gap-1.5 cursor-not-allowed">
        <PlusCircle size={12} /> Добавить параметр
      </button>
    </div>
  );
}
