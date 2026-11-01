import { useState, useEffect } from 'react';
import { Plus, Trash2, Pencil, Check, X, ChevronDown } from 'lucide-react';

const API = (path, token, opts = {}) =>
  fetch(path, { ...opts, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(opts.headers || {}) } });

function Toggle({ value, onChange, disabled }) {
  return (
    <button
      onClick={() => !disabled && onChange(!value)}
      disabled={disabled}
      className={`relative inline-flex items-center w-10 h-5 rounded-full transition-colors shrink-0 ${value ? 'bg-ok' : 'bg-bd2'}`}>
      <span className={`inline-block w-3.5 h-3.5 bg-sff rounded-full shadow transform transition-transform duration-200 ${value ? 'translate-x-5' : 'translate-x-1'}`} />
    </button>
  );
}

// Заголовок секции в стиле строк-параметров EconomyCategoryCard:
// мелкая капс-метка слева + слот действия справа.
function Section({ title, action, children }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1 min-h-[20px]">
        <div className="text-[10px] font-black text-lbl uppercase tracking-widest">{title}</div>
        {action}
      </div>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function PackageRow({ pkg, canEdit, onToggle, onDelete, onEdit }) {
  const dur = pkg.duration_days ? `${pkg.duration_days} дн.` : '∞';
  return (
    <div className={`rounded-xl border border-bd hover:border-bd2 bg-sff px-2.5 py-2 transition ${!pkg.is_enabled ? 'opacity-50' : ''}`}>
      <div className="flex items-center gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-[12px] font-bold text-tx leading-tight truncate">{pkg.label}</div>
          <div className="text-[10px] text-lbl mt-0.5 flex gap-2 flex-wrap">
            <span>💎 {pkg.price_pulses.toLocaleString()}</span>
            {pkg.price_rub && <span>· 💳 {pkg.price_rub} ₽</span>}
            <span>· {dur}</span>
          </div>
        </div>
        {canEdit && (
          <div className="flex items-center gap-1.5 shrink-0">
            <Toggle value={!!pkg.is_enabled} onChange={() => onToggle(pkg.id)} />
            <button onClick={() => onEdit(pkg)} title="Изменить"
              className="w-7 h-7 flex items-center justify-center rounded-lg text-lbl hover:bg-sf2 hover:text-cta transition">
              <Pencil size={12} />
            </button>
            <button onClick={() => onDelete(pkg.id)} title="Удалить"
              className="w-7 h-7 flex items-center justify-center rounded-lg text-lbl hover:bg-sf2 hover:text-danger transition">
              <Trash2 size={12} />
            </button>
          </div>
        )}
      </div>
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

  const inputCls = 'px-2 py-1.5 rounded-lg text-[12px] bg-sff border border-bd2 focus:border-cta outline-none';

  return (
    <div className="rounded-xl border border-cta bg-sff px-2.5 py-2 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <input value={label} onChange={e => setLabel(e.target.value)}
          placeholder="Название пакета" autoFocus
          className={`col-span-2 ${inputCls}`} />
        <input value={pulses} onChange={e => setPulses(e.target.value)}
          type="number" min="1" placeholder="💎 Пульсы"
          className={`font-mono ${inputCls}`} />
        <input value={rub} onChange={e => setRub(e.target.value)}
          type="number" min="0" placeholder="💳 Рублей (необяз.)"
          className={`font-mono ${inputCls}`} />
        <input value={days} onChange={e => setDays(e.target.value)}
          type="number" min="1" placeholder="Дней (пусто = бесконечно)"
          className={`col-span-2 font-mono ${inputCls}`} />
      </div>
      <div className="flex gap-1.5">
        <button onClick={onCancel}
          className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-sf2 border border-bd2 text-txd hover:bg-bd transition">
          Отмена
        </button>
        <button onClick={handleSave} disabled={saving || !label.trim() || !pulses}
          className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-cta text-white hover:brightness-110 transition disabled:opacity-40 disabled:cursor-not-allowed">
          {saving ? '…' : 'Сохранить'}
        </button>
      </div>
    </div>
  );
}

function RequestRow({ req, canEdit, onApprove, onReject }) {
  const statusColor = { pending: 'text-warn bg-[color-mix(in_oklab,var(--warn)_10%,transparent)]', approved: 'text-ok bg-[color-mix(in_oklab,var(--ok)_10%,transparent)]', rejected: 'text-danger bg-[color-mix(in_oklab,var(--danger)_10%,transparent)]', expired: 'text-lbl bg-sf2' };
  const statusLabel = { pending: 'Ожидает', approved: 'Одобрена', rejected: 'Отклонена', expired: 'Истекла' };
  return (
    <div className="rounded-xl border border-bd bg-sff px-2.5 py-2">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-[12px] font-bold text-tx leading-tight truncate">«{req.title_text}»</div>
          <div className="text-[10px] text-lbl mt-0.5 flex gap-2 flex-wrap">
            <span>user #{req.user_id}</span>
            <span>· 💳 {req.price_rub} ₽</span>
            {req.duration_days && <span>· {req.duration_days} дн.</span>}
            <span>· {req.created_at?.slice(0, 10)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`text-[9px] font-black px-2 py-0.5 rounded-full uppercase ${statusColor[req.status] || 'text-txd bg-sf2'}`}>
            {statusLabel[req.status] || req.status}
          </span>
          {canEdit && req.status === 'pending' && (
            <>
              <button onClick={() => onApprove(req.id)} title="Одобрить"
                className="w-7 h-7 flex items-center justify-center rounded-lg text-lbl hover:bg-sf2 hover:text-ok transition">
                <Check size={13} />
              </button>
              <button onClick={() => onReject(req.id)} title="Отклонить"
                className="w-7 h-7 flex items-center justify-center rounded-lg text-lbl hover:bg-sf2 hover:text-danger transition">
                <X size={13} />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TitlesPanel({ token, canEdit, embedded = false }) {
  const [packages, setPackages]     = useState([]);
  const [requests, setRequests]     = useState([]);
  const [stats, setStats]           = useState(null);
  const [settings, setSettings]     = useState(null);
  // embedded=true → сразу раскрыто (используется внутри карточки
  // Экономики, где обёртка-аккордеон не нужна).
  const [expanded, setExpanded]     = useState(embedded);
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

  // Общее тело — пакеты, настройки, заявки. Все блоки в едином стиле
  // строк-параметров: секция = капс-заголовок + карточки-строки.
  const body = (
    <div className="space-y-4">
      {/* ── Пакеты подписки ── */}
      <Section
        title="📦 Пакеты подписки"
        action={canEdit && !addMode && !editPkg && (
          <button onClick={() => setAddMode(true)}
            className="flex items-center gap-1 text-[10px] font-black text-cta hover:brightness-110 transition">
            <Plus size={11} /> Добавить
          </button>
        )}
      >
        {addMode && (
          <PackageForm onSave={handleSave} onCancel={() => setAddMode(false)} />
        )}
        {packages.length === 0 && !addMode && (
          <div className="text-center py-3 text-[11px] text-lbl">Нет пакетов</div>
        )}
        {packages.map(pkg =>
          editPkg?.id === pkg.id ? (
            <PackageForm key={pkg.id} initial={editPkg} onSave={handleSave} onCancel={() => setEditPkg(null)} />
          ) : (
            <PackageRow key={pkg.id} pkg={pkg} canEdit={canEdit}
              onToggle={handleToggle} onDelete={handleDelete} onEdit={setEditPkg} />
          )
        )}
      </Section>

      {/* ── Настройки ── */}
      <Section
        title="⚙️ Настройки"
        action={canEdit && !editSettings && settings && (
          <button onClick={() => { setSettingsDraft({ ...settings }); setEditSettings(true); }}
            className="flex items-center gap-1 text-[10px] font-black text-cta hover:brightness-110 transition">
            <Pencil size={11} /> Изменить
          </button>
        )}
      >
        {!editSettings && !settings && (
          <div className="text-center py-3 text-[11px] text-lbl">Загрузка…</div>
        )}
        {!editSettings && settings && (
          <>
            <div className="rounded-xl border border-bd bg-sff px-2.5 py-2 flex items-center gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-[12px] font-bold text-tx leading-tight">Смена имени титула</div>
                <div className="text-[10px] text-lbl mt-0.5 truncate">Сколько пульсов стоит переименовать купленный титул</div>
              </div>
              <div className="text-[13px] font-black text-tx font-mono shrink-0 whitespace-nowrap">
                {settings.rename_price_pulses}
                <span className="text-[10px] text-lbl font-normal ml-1">💎</span>
              </div>
            </div>
            <div className="rounded-xl border border-bd bg-sff px-2.5 py-2 flex items-center gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-[12px] font-bold text-tx leading-tight">Срок жизни заявки</div>
                <div className="text-[10px] text-lbl mt-0.5 truncate">Через сколько часов неоплаченная заявка истекает</div>
              </div>
              <div className="text-[13px] font-black text-tx font-mono shrink-0 whitespace-nowrap">
                {settings.request_ttl_hours}
                <span className="text-[10px] text-lbl font-normal ml-1">ч</span>
              </div>
            </div>
          </>
        )}
        {editSettings && (
          <div className="rounded-xl border border-cta bg-sff px-2.5 py-2 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <div className="text-[9px] text-lbl mb-0.5">Смена имени (💎)</div>
                <input type="number" value={settingsDraft.rename_price_pulses ?? ''}
                  onChange={e => setSettingsDraft(d => ({ ...d, rename_price_pulses: parseInt(e.target.value) || 0 }))}
                  className="w-full px-2 py-1.5 rounded-lg text-[12px] font-mono bg-sff border border-bd2 focus:border-cta outline-none" />
              </div>
              <div>
                <div className="text-[9px] text-lbl mb-0.5">Срок заявки (часы)</div>
                <input type="number" value={settingsDraft.request_ttl_hours ?? ''}
                  onChange={e => setSettingsDraft(d => ({ ...d, request_ttl_hours: parseInt(e.target.value) || 0 }))}
                  className="w-full px-2 py-1.5 rounded-lg text-[12px] font-mono bg-sff border border-bd2 focus:border-cta outline-none" />
              </div>
            </div>
            <div className="flex gap-1.5">
              <button onClick={() => setEditSettings(false)}
                className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-sf2 border border-bd2 text-txd hover:bg-bd transition">
                Отмена
              </button>
              <button onClick={handleSaveSettings}
                className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-cta text-white hover:brightness-110 transition">
                Сохранить
              </button>
            </div>
          </div>
        )}
      </Section>

      {/* ── Заявки на рублёвую оплату ── */}
      <Section
        title="📨 Заявки на оплату"
        action={
          <div className="flex gap-1">
            {['pending', 'approved', 'rejected', 'all'].map(tab => (
              <button key={tab} onClick={() => setReqTab(tab)}
                className={`text-[9px] font-black px-2 py-0.5 rounded-full transition ${reqTab === tab ? 'bg-cta text-white' : 'bg-sf2 text-txd hover:bg-bd2'}`}>
                {tab === 'pending' ? 'Ожидают' : tab === 'approved' ? 'Одобрены' : tab === 'rejected' ? 'Отклонены' : 'Все'}
              </button>
            ))}
          </div>
        }
      >
        {requests.length === 0 ? (
          <div className="text-center py-3 text-[11px] text-lbl">Нет заявок</div>
        ) : (
          requests.map(req => (
            <RequestRow key={req.id} req={req} canEdit={canEdit}
              onApprove={handleApprove} onReject={handleReject} />
          ))
        )}
      </Section>
    </div>
  );

  // embedded: только тело, без обёртки и accordion (заголовок уже даёт
  // EconomyCategoryCard — там «КАТЕГОРИЯ / Кастомные Титулы»).
  if (embedded) return body;

  // Старый режим (если кто-то импортирует TitlesPanel напрямую):
  // отдельная карточка с accordion-шапкой и красной рамкой.
  return (
    <div className="bg-sff rounded-3xl border-2 border-red-400 shadow-sm overflow-hidden">
      <div className="flex items-center">
        <button onClick={() => setExpanded(v => !v)}
          className="flex-1 flex items-center gap-3 px-5 py-3.5 hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] transition text-left">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-black text-tx">👑 Кастомные Титулы</span>
              <span className="text-[9px] font-black px-2 py-0.5 bg-[color-mix(in_oklab,var(--danger)_16%,transparent)] text-danger rounded-full uppercase tracking-widest">Платно</span>
            </div>
            <div className="text-[10px] text-lbl mt-0.5">
              {stats ? `${stats.packages_enabled}/${stats.packages_total} пакетов активно` : 'Управление пакетами и заявками'}
              {pendingCount > 0 && <span className="ml-2 text-warn font-black">• {pendingCount} ожидают</span>}
            </div>
          </div>
          <ChevronDown size={20} className={`text-lbl transition-transform duration-300 mr-4 ${expanded ? 'rotate-180' : ''}`} />
        </button>
      </div>
      {expanded && (
        <div className="border-t border-[color-mix(in_oklab,var(--danger)_30%,transparent)] p-3">
          {body}
        </div>
      )}
    </div>
  );
}
