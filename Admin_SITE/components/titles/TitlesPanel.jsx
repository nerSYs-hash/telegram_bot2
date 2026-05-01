import { useState, useEffect } from 'react';
import { Plus, Trash2, Pencil, Check, X, ChevronDown } from 'lucide-react';

const API = (path, token, opts = {}) =>
  fetch(path, { ...opts, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(opts.headers || {}) } });

function Toggle({ value, onChange, disabled }) {
  return (
    <button
      onClick={() => !disabled && onChange(!value)}
      disabled={disabled}
      className={`relative inline-flex items-center w-10 h-5 rounded-full transition-colors shrink-0 ${value ? 'bg-green-500' : 'bg-gray-200'}`}>
      <span className={`inline-block w-3.5 h-3.5 bg-white rounded-full shadow transform transition-transform duration-200 ${value ? 'translate-x-5' : 'translate-x-1'}`} />
    </button>
  );
}

function PackageRow({ pkg, canEdit, onToggle, onDelete, onEdit }) {
  const dur = pkg.duration_days ? `${pkg.duration_days} дн.` : '∞';
  return (
    <div className={`flex items-center gap-2 px-4 py-2.5 border-b border-gray-50 last:border-0 ${!pkg.is_enabled ? 'opacity-50' : ''}`}>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-black text-gray-900 truncate">{pkg.label}</div>
        <div className="text-[10px] text-gray-400 mt-0.5 flex gap-2">
          <span>💎 {pkg.price_pulses.toLocaleString()}</span>
          {pkg.price_rub && <span>· 💳 {pkg.price_rub} ₽</span>}
          <span>· {dur}</span>
        </div>
      </div>
      {canEdit && (
        <div className="flex items-center gap-2 shrink-0">
          <Toggle value={!!pkg.is_enabled} onChange={() => onToggle(pkg.id)} />
          <button onClick={() => onEdit(pkg)}
            className="p-1 text-gray-400 hover:text-blue-500 transition"><Pencil size={13} /></button>
          <button onClick={() => onDelete(pkg.id)}
            className="p-1 text-gray-400 hover:text-red-500 transition"><Trash2 size={13} /></button>
        </div>
      )}
    </div>
  );
}

function PackageForm({ initial, onSave, onCancel }) {
  const [label, setLabel] = useState(initial?.label || '');
  const [days, setDays] = useState(initial?.duration_days ?? '');
  const [pulses, setPulses] = useState(initial?.price_pulses ?? '');
  const [rub, setRub] = useState(initial?.price_rub ?? '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!label.trim() || !pulses) return;
    setSaving(true);
    await onSave({
      label: label.trim(),
      duration_days: days === '' ? null : parseInt(days),
      price_pulses: parseInt(pulses),
      price_rub: rub === '' ? null : parseInt(rub),
    });
    setSaving(false);
  };

  return (
    <div className="bg-gray-50 rounded-2xl p-3 m-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <input value={label} onChange={e => setLabel(e.target.value)}
          placeholder="Название пакета"
          className="col-span-2 border border-gray-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
        <input value={pulses} onChange={e => setPulses(e.target.value)}
          type="number" min="1" placeholder="💎 Пульсы"
          className="border border-gray-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
        <input value={rub} onChange={e => setRub(e.target.value)}
          type="number" min="0" placeholder="💳 Рублей (необяз.)"
          className="border border-gray-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
        <input value={days} onChange={e => setDays(e.target.value)}
          type="number" min="1" placeholder="Дней (пусто = бесконечно)"
          className="col-span-2 border border-gray-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel}
          className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 transition">Отмена</button>
        <button onClick={handleSave} disabled={saving || !label.trim() || !pulses}
          className="px-3 py-1.5 bg-blue-500 text-white text-xs font-black rounded-xl disabled:opacity-50 hover:bg-blue-600 active:scale-95 transition">
          {saving ? '...' : 'Сохранить'}
        </button>
      </div>
    </div>
  );
}

function RequestRow({ req, canEdit, onApprove, onReject }) {
  const statusColor = { pending: 'text-amber-600 bg-amber-50', approved: 'text-green-600 bg-green-50', rejected: 'text-red-600 bg-red-50', expired: 'text-gray-400 bg-gray-50' };
  const statusLabel = { pending: 'Ожидает', approved: 'Одобрена', rejected: 'Отклонена', expired: 'Истекла' };
  return (
    <div className="px-4 py-2.5 border-b border-gray-50 last:border-0">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-black text-gray-900 truncate">«{req.title_text}»</div>
          <div className="text-[10px] text-gray-400 mt-0.5 flex gap-2 flex-wrap">
            <span>user #{req.user_id}</span>
            <span>· 💳 {req.price_rub} ₽</span>
            {req.duration_days && <span>· {req.duration_days} дн.</span>}
            <span>· {req.created_at?.slice(0, 10)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`text-[9px] font-black px-2 py-0.5 rounded-full uppercase ${statusColor[req.status] || 'text-gray-500 bg-gray-50'}`}>
            {statusLabel[req.status] || req.status}
          </span>
          {canEdit && req.status === 'pending' && (
            <>
              <button onClick={() => onApprove(req.id)} title="Одобрить"
                className="p-1 text-gray-400 hover:text-green-500 transition"><Check size={13} /></button>
              <button onClick={() => onReject(req.id)} title="Отклонить"
                className="p-1 text-gray-400 hover:text-red-500 transition"><X size={13} /></button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TitlesPanel({ token, canEdit }) {
  const [packages, setPackages]     = useState([]);
  const [requests, setRequests]     = useState([]);
  const [stats, setStats]           = useState(null);
  const [settings, setSettings]     = useState(null);
  const [expanded, setExpanded]     = useState(false);
  const [addMode, setAddMode]       = useState(false);
  const [editPkg, setEditPkg]       = useState(null);
  const [reqTab, setReqTab]         = useState('pending');
  const [editSettings, setEditSettings] = useState(false);
  const [settingsDraft, setSettingsDraft] = useState({});

  const load = () => {
    API('/api/titles/packages', token)
      .then(r => r.json()).then(d => Array.isArray(d) && setPackages(d));
    API('/api/titles/stats', token)
      .then(r => r.json()).then(d => d?.packages_total != null && setStats(d));
    API('/api/titles/settings', token)
      .then(r => r.json()).then(d => d?.rename_price_pulses != null && setSettings(d));
  };

  const loadRequests = (status) => {
    const qs = status === 'all' ? '' : `?status=${status}`;
    API(`/api/titles/requests${qs}`, token)
      .then(r => r.json())
      .then(d => d?.items && setRequests(d.items));
  };

  useEffect(() => { if (expanded) { load(); loadRequests(reqTab); } }, [expanded, token]);
  useEffect(() => { if (expanded) loadRequests(reqTab); }, [reqTab]);

  const handleToggle = async (id) => {
    await API(`/api/titles/packages/${id}/toggle`, token, { method: 'PATCH' });
    load();
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Удалить пакет?')) return;
    await API(`/api/titles/packages/${id}`, token, { method: 'DELETE' });
    load();
  };

  const handleSave = async (data) => {
    if (editPkg) {
      await API(`/api/titles/packages/${editPkg.id}`, token, { method: 'PUT', body: JSON.stringify(data) });
      setEditPkg(null);
    } else {
      await API('/api/titles/packages', token, { method: 'POST', body: JSON.stringify(data) });
      setAddMode(false);
    }
    load();
  };

  const handleApprove = async (id) => {
    const res = await API(`/api/titles/requests/${id}/approve`, token, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert('Ошибка применения титула: ' + (err.detail || 'неизвестная ошибка'));
      return;
    }
    loadRequests(reqTab);
    load();
  };

  const handleReject = async (id) => {
    const reason = window.prompt('Причина отказа (необязательно):');
    if (reason === null) return;
    await API(`/api/titles/requests/${id}/reject?reason=${encodeURIComponent(reason)}`, token, { method: 'POST' });
    loadRequests(reqTab);
    load();
  };

  const handleSaveSettings = async () => {
    await API('/api/titles/settings', token, { method: 'PUT', body: JSON.stringify(settingsDraft) });
    setEditSettings(false);
    load();
  };

  const pendingCount = stats?.requests_pending ?? 0;

  return (
    <div className="bg-white rounded-3xl border-2 border-red-400 shadow-sm overflow-hidden">
      {/* Заголовок */}
      <div className="flex items-center">
        <button onClick={() => setExpanded(v => !v)}
          className="flex-1 flex items-center gap-3 px-5 py-3.5 hover:bg-red-50 transition text-left">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-black text-gray-900">👑 Кастомные Титулы</span>
              <span className="text-[9px] font-black px-2 py-0.5 bg-red-100 text-red-600 rounded-full uppercase tracking-widest">Платно</span>
            </div>
            <div className="text-[10px] text-gray-400 mt-0.5">
              {stats ? `${stats.packages_enabled}/${stats.packages_total} пакетов активно` : 'Управление пакетами и заявками'}
              {pendingCount > 0 && <span className="ml-2 text-amber-500 font-black">• {pendingCount} ожидают</span>}
            </div>
          </div>
          <ChevronDown size={20} className={`text-gray-400 transition-transform duration-300 mr-4 ${expanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Тело */}
      {expanded && (
        <div className="border-t border-red-100">
          {/* Пакеты */}
          <div className="px-4 pt-3 pb-1">
            <div className="flex items-center justify-between mb-1">
              <div className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Пакеты подписки</div>
              {canEdit && !addMode && !editPkg && (
                <button onClick={() => setAddMode(true)}
                  className="flex items-center gap-1 text-[10px] font-black text-blue-500 hover:text-blue-700 transition">
                  <Plus size={11} /> Добавить
                </button>
              )}
            </div>
          </div>

          {addMode && (
            <PackageForm onSave={handleSave} onCancel={() => setAddMode(false)} />
          )}

          {packages.length === 0 && !addMode && (
            <div className="px-4 py-4 text-center text-xs text-gray-400">Нет пакетов</div>
          )}

          {packages.map(pkg =>
            editPkg?.id === pkg.id ? (
              <PackageForm key={pkg.id} initial={editPkg} onSave={handleSave} onCancel={() => setEditPkg(null)} />
            ) : (
              <PackageRow key={pkg.id} pkg={pkg} canEdit={canEdit}
                onToggle={handleToggle} onDelete={handleDelete} onEdit={setEditPkg} />
            )
          )}

          {/* Настройки */}
          <div className="border-t border-gray-50 px-4 py-2.5">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Настройки</div>
              {canEdit && !editSettings && (
                <button onClick={() => { setSettingsDraft({ ...settings }); setEditSettings(true); }}
                  className="text-[10px] font-black text-blue-500 hover:text-blue-700 transition flex items-center gap-1">
                  <Pencil size={11} /> Изменить
                </button>
              )}
            </div>
            {!editSettings && settings && (
              <div className="flex gap-4 mt-1.5 text-xs text-gray-500">
                <span>💎 Смена имени: <b className="text-gray-700">{settings.rename_price_pulses}</b></span>
                <span>⏱ TTL заявки: <b className="text-gray-700">{settings.request_ttl_hours}ч</b></span>
              </div>
            )}
            {editSettings && (
              <div className="mt-2 space-y-2">
                <div className="flex gap-2">
                  <div className="flex-1">
                    <div className="text-[9px] text-gray-400 mb-0.5">Смена имени (💎)</div>
                    <input type="number" value={settingsDraft.rename_price_pulses ?? ''}
                      onChange={e => setSettingsDraft(d => ({ ...d, rename_price_pulses: parseInt(e.target.value) || 0 }))}
                      className="w-full border border-gray-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
                  </div>
                  <div className="flex-1">
                    <div className="text-[9px] text-gray-400 mb-0.5">TTL заявки (часы)</div>
                    <input type="number" value={settingsDraft.request_ttl_hours ?? ''}
                      onChange={e => setSettingsDraft(d => ({ ...d, request_ttl_hours: parseInt(e.target.value) || 0 }))}
                      className="w-full border border-gray-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setEditSettings(false)}
                    className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 transition">Отмена</button>
                  <button onClick={handleSaveSettings}
                    className="px-3 py-1.5 bg-blue-500 text-white text-xs font-black rounded-xl hover:bg-blue-600 active:scale-95 transition">
                    Сохранить
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Заявки на рублёвую оплату */}
          <div className="border-t border-gray-50">
            <div className="px-4 pt-2.5 pb-1 flex items-center justify-between">
              <div className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Заявки на оплату</div>
              <div className="flex gap-1">
                {['pending', 'approved', 'rejected', 'all'].map(tab => (
                  <button key={tab} onClick={() => setReqTab(tab)}
                    className={`text-[9px] font-black px-2 py-0.5 rounded-full transition ${reqTab === tab ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>
                    {tab === 'pending' ? 'Ожидают' : tab === 'approved' ? 'Одобрены' : tab === 'rejected' ? 'Отклонены' : 'Все'}
                  </button>
                ))}
              </div>
            </div>
            {requests.length === 0 ? (
              <div className="px-4 py-4 text-center text-xs text-gray-400">Нет заявок</div>
            ) : (
              requests.map(req => (
                <RequestRow key={req.id} req={req} canEdit={canEdit}
                  onApprove={handleApprove} onReject={handleReject} />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
