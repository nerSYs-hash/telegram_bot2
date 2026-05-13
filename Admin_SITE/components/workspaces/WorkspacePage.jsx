// WorkspacePage (V1.17.0c, F) — детали сообщества + роли чатов + deep-link подключения
import React, { useEffect, useState } from 'react';
import {
  ArrowLeft, Edit2, Save, X, MessageCircle, Users, UserPlus, Trash2,
  Plus, Copy, Check, Crown, Shield, BookOpen,
} from 'lucide-react';
import {
  fetchWorkspaceDetails, renameWorkspace, removeMember, updateChatRole,
} from '../shared/api';

const ROLE_LABEL = { owner: '👑 Владелец', admin: '🛡 Админ', moderator: '🔧 Модератор' };
const ROLE_COLOR = {
  owner:     'bg-amber-100 text-amber-700',
  admin:     'bg-blue-100 text-blue-700',
  moderator: 'bg-gray-100 text-gray-700',
};

const CHAT_ROLES = [
  { value: 'main',    label: 'Главный', icon: Crown,    color: 'bg-amber-100 text-amber-700 border-amber-200' },
  { value: 'admin',   label: 'Админ',   icon: Shield,   color: 'bg-blue-100 text-blue-700 border-blue-200' },
  { value: 'journal', label: 'Журнал',  icon: BookOpen, color: 'bg-purple-100 text-purple-700 border-purple-200' },
];
const CHAT_ROLE_META = Object.fromEntries(CHAT_ROLES.map(r => [r.value, r]));

export default function WorkspacePage({
  token, wsId, currentUserId, botUsername,
  onBack, onInviteClick, reloadTrigger,
}) {
  const [details, setDetails] = useState(null);
  const [editing, setEditing] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);
  const [savingRole, setSavingRole] = useState(null); // chat_id, идёт PATCH
  const [linkCopied, setLinkCopied] = useState(false);

  const reload = async () => {
    try {
      setErr(null);
      const d = await fetchWorkspaceDetails(token, wsId);
      setDetails(d);
      setNewName(d.workspace.name);
    } catch (e) { setErr(e.message); }
  };

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [wsId, reloadTrigger]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await renameWorkspace(token, wsId, newName);
      await reload();
      setEditing(false);
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  };

  const handleRemove = async (memberUserId) => {
    if (!window.confirm('Удалить помощника?')) return;
    try {
      await removeMember(token, wsId, memberUserId);
      await reload();
    } catch (e) { setErr(e.message); }
  };

  const handleSetChatRole = async (chatId, role) => {
    setSavingRole(chatId);
    try {
      await updateChatRole(token, wsId, chatId, role);
      await reload();
    } catch (e) { setErr(e.message); }
    finally { setSavingRole(null); }
  };

  const connectLink = botUsername
    ? `https://t.me/${botUsername}?startgroup=connect_ws_${wsId}`
    : null;

  const handleCopyLink = async () => {
    if (!connectLink) return;
    try {
      await navigator.clipboard.writeText(connectLink);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch (e) { setErr('Не удалось скопировать ссылку'); }
  };

  if (!details) return <div className="p-5 text-gray-400 text-sm">Загрузка…</div>;

  const ws = details.workspace;
  const isOwner = details.members.find(m => m.user_id === currentUserId)?.role === 'owner';

  return (
    <div className="space-y-4">
      <button onClick={onBack}
              className="flex items-center gap-2 text-blue-600 font-black text-xs uppercase tracking-wide hover:bg-blue-50 rounded-xl px-3 py-2">
        <ArrowLeft size={14}/> Назад
      </button>

      {err && <div className="bg-red-50 text-red-700 rounded-2xl p-3 text-xs font-medium">{err}</div>}

      {/* General */}
      <div className="bg-white rounded-[2rem] p-5 border border-gray-100">
        <h3 className="font-black text-gray-900 text-xs uppercase mb-3">Общее</h3>
        {editing ? (
          <div className="flex items-center gap-2">
            <input value={newName} onChange={e => setNewName(e.target.value)}
                   className="flex-1 px-3 py-2 border border-gray-200 rounded-xl text-sm font-medium"/>
            <button onClick={handleSave} disabled={saving}
                    className="p-2 rounded-xl bg-blue-600 text-white disabled:opacity-50">
              <Save size={14}/>
            </button>
            <button onClick={() => { setEditing(false); setNewName(ws.name); }}
                    className="p-2 rounded-xl bg-gray-100 text-gray-700"><X size={14}/></button>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-black text-gray-900">{ws.name}</h2>
            {isOwner && (
              <button onClick={() => setEditing(true)} className="p-2 rounded-xl hover:bg-gray-100">
                <Edit2 size={14} className="text-gray-400"/>
              </button>
            )}
          </div>
        )}
        <div className="mt-2 text-[10px] uppercase tracking-widest font-bold text-gray-400">
          Тариф: {ws.plan}{ws.is_pulse_themed ? ' · Pulse-themed' : ''}
        </div>
      </div>

      {/* Chats */}
      <div className="bg-white rounded-[2rem] p-5 border border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-black text-gray-900 text-xs uppercase flex items-center">
            <MessageCircle className="mr-2 text-emerald-500" size={14}/> Чаты ({details.chats.length})
          </h3>
          {isOwner && connectLink && (
            <div className="flex items-center gap-2">
              <a href={connectLink} target="_blank" rel="noopener noreferrer"
                 className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 text-white
                            text-xs font-black uppercase tracking-wide hover:bg-emerald-700">
                <Plus size={12}/> Подключить чат
              </a>
              <button onClick={handleCopyLink} title="Скопировать ссылку"
                      className="p-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700">
                {linkCopied ? <Check size={14} className="text-emerald-600"/> : <Copy size={14}/>}
              </button>
            </div>
          )}
        </div>

        {details.chats.length === 0 && (
          <div className="text-xs text-gray-400 font-medium">
            Нет подключённых чатов. Нажми «Подключить чат» и добавь бота в нужный чат.
          </div>
        )}

        <div className="space-y-2">
          {details.chats.map(c => {
            const meta = c.role ? CHAT_ROLE_META[c.role] : null;
            return (
              <div key={c.chat_id} className="p-3 bg-gray-50 rounded-2xl">
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-black text-sm text-gray-900 truncate">
                      {c.title || `Чат ${c.chat_id}`}
                    </div>
                    <div className="text-[10px] uppercase tracking-widest font-bold text-gray-400 mt-0.5">
                      {c.chat_type || '—'} · добавлен {c.added_at?.slice(0, 10) || '—'}
                    </div>
                  </div>
                  {meta && (
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg
                                      text-[10px] font-black uppercase tracking-wide border ${meta.color}`}>
                      <meta.icon size={11}/> {meta.label}
                    </span>
                  )}
                </div>

                {isOwner && (
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {CHAT_ROLES.map(r => {
                      const active = c.role === r.value;
                      return (
                        <button key={r.value}
                                disabled={savingRole === c.chat_id}
                                onClick={() => handleSetChatRole(c.chat_id, active ? null : r.value)}
                                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px]
                                            font-black uppercase tracking-wide border transition-colors
                                            disabled:opacity-50
                                            ${active
                                              ? r.color
                                              : 'bg-white text-gray-500 border-gray-200 hover:bg-gray-100'}`}>
                          <r.icon size={11}/> {r.label}
                        </button>
                      );
                    })}
                    {c.role && (
                      <button disabled={savingRole === c.chat_id}
                              onClick={() => handleSetChatRole(c.chat_id, null)}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px]
                                         font-black uppercase tracking-wide border bg-white text-gray-400
                                         border-gray-200 hover:bg-red-50 hover:text-red-600 disabled:opacity-50">
                        <X size={11}/> Снять
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Members */}
      <div className="bg-white rounded-[2rem] p-5 border border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-black text-gray-900 text-xs uppercase flex items-center">
            <Users className="mr-2 text-violet-500" size={14}/> Помощники ({details.members.length})
          </h3>
          {isOwner && (
            <button onClick={onInviteClick}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 text-white
                               text-xs font-black uppercase tracking-wide hover:bg-blue-700">
              <UserPlus size={12}/> Пригласить
            </button>
          )}
        </div>
        <div className="space-y-2">
          {details.members.map(m => (
            <div key={m.user_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-2xl">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-gray-200 flex items-center justify-center text-xs font-black text-gray-500">
                  {String(m.user_id).slice(-2)}
                </div>
                <div>
                  <div className="font-black text-sm text-gray-900">ID {m.user_id}</div>
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wide ${ROLE_COLOR[m.role]}`}>
                    {ROLE_LABEL[m.role]}
                  </span>
                </div>
              </div>
              {isOwner && m.role !== 'owner' && (
                <button onClick={() => handleRemove(m.user_id)}
                        className="p-2 rounded-xl hover:bg-red-50 text-red-500">
                  <Trash2 size={14}/>
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
