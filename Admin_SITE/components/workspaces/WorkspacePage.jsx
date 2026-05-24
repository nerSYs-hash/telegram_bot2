// WorkspacePage (V1.17.0c, F) — детали сообщества + роли чатов + deep-link подключения
// V1.17.0i (P4 C6): отключённые чаты (removed_at не пуст) показываются приглушённо,
// с плашкой «🔴 Бот не в чате — добавьте обратно, роль восстановится»; кнопка
// «Отключить» (LogOut) для уже soft-removed не отображается.
// V1.17.0j: аватар workspace в шапке «Общее» (auto из main-чата TG); при
// 404 / load fail — fallback на иконку Hash (тематически нейтральная).
import React, { useEffect, useState } from 'react';
import {
  ArrowLeft, Edit2, Save, X, MessageCircle, Users, UserPlus, Trash2,
  Plus, Copy, Check, Crown, Shield, BookOpen, LogOut, AlertTriangle, Hash,
} from 'lucide-react';
import {
  fetchWorkspaceDetails, renameWorkspace, removeMember, updateChatRole,
  disconnectChat, deleteWorkspace,
} from '../shared/api';
import { useAuthImage } from '../shared/useAuthImage';

const ROLE_LABEL = { owner: '👑 Владелец', admin: '🛡 Админ', moderator: '🔧 Модератор' };
const ROLE_COLOR = {
  owner:     'bg-[color-mix(in_oklab,var(--warn)_16%,transparent)] text-warn',
  admin:     'bg-[color-mix(in_oklab,var(--cta)_16%,transparent)] text-cta',
  moderator: 'bg-sf2 text-tx',
};

const CHAT_ROLES = [
  { value: 'main',    label: 'Главный', icon: Crown,    color: 'bg-[color-mix(in_oklab,var(--warn)_16%,transparent)] text-warn border-[color-mix(in_oklab,var(--warn)_40%,transparent)]' },
  { value: 'admin',   label: 'Админ',   icon: Shield,   color: 'bg-[color-mix(in_oklab,var(--cta)_16%,transparent)] text-cta border-[color-mix(in_oklab,var(--cta)_40%,transparent)]' },
  { value: 'journal', label: 'Журнал',  icon: BookOpen, color: 'bg-[color-mix(in_oklab,var(--purple)_16%,transparent)] text-purple border-[color-mix(in_oklab,var(--purple)_40%,transparent)]' },
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

  const handleDisconnectChat = async (chatId, title) => {
    if (!window.confirm(
      `Отключить чат «${title}» от сообщества?\n\nБот выйдет из чата, ` +
      `запись в БД удалится. Чат сам не исчезнет в Telegram.`
    )) return;
    setSavingRole(chatId);
    try {
      await disconnectChat(token, wsId, chatId);
      await reload();
    } catch (e) { setErr(e.message); }
    finally { setSavingRole(null); }
  };

  const handleDeleteWorkspace = async () => {
    const name = details?.workspace?.name || '';
    const c1 = window.confirm(
      `Удалить сообщество «${name}»?\n\n` +
      `• Бот покинет ВСЕ привязанные чаты\n` +
      `• Все помощники потеряют доступ\n` +
      `• Запись о сообществе будет полностью удалена\n\n` +
      `Это действие необратимо.`
    );
    if (!c1) return;
    const typed = window.prompt(`Для подтверждения введи название сообщества: «${name}»`);
    if (typed !== name) {
      setErr('Имя не совпало — удаление отменено.');
      return;
    }
    try {
      await deleteWorkspace(token, wsId);
      onBack();
    } catch (e) { setErr(e.message); }
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

  // V1.17.0j10 HOTFIX: хук useAuthImage ОБЯЗАН идти до раннего return
  // (`if (!details) return ...`). Иначе при первом рендере (details=null)
  // хук не вызывается, а после загрузки — вызывается → React падает с
  // «Rendered more hooks than during the previous render» → белый экран
  // страницы управления сообществом. Хук безопасно отрабатывает с
  // undefined url (guard внутри useAuthImage). Псевдо-комментарий
  // eslint-disable не работал — в проекте ESLint вообще не подключён.
  // V1.17.0j: аватар workspace (auto из TG); 404/fail → fallback Hash-icon
  const { src: avatarSrc, failed: avatarFailed } = useAuthImage(details?.workspace?.icon_url, token);

  if (!details) return <div className="p-5 text-lbl text-sm">Загрузка…</div>;

  const ws = details.workspace;
  const isOwner = details.members.find(m => m.user_id === currentUserId)?.role === 'owner';
  // V1.17.0i (C6): шапка показывает «N активных · M всего» если есть отключённые
  const totalChats = details.chats.length;
  const activeChats = details.chats.filter(c => !c.removed_at).length;
  const chatsTitle = activeChats === totalChats
    ? `Чаты (${totalChats})`
    : `Чаты (${activeChats} активных · ${totalChats})`;

  return (
    <div className="space-y-4">
      <button onClick={onBack}
              className="flex items-center gap-2 text-cta font-black text-xs uppercase tracking-wide hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] rounded-xl px-3 py-2">
        <ArrowLeft size={14}/> Назад
      </button>

      {err && <div className="bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] text-danger rounded-2xl p-3 text-xs font-medium">{err}</div>}

      {/* General */}
      <div className="bg-sff rounded-[2rem] p-5 border border-bd">
        <h3 className="font-black text-tx text-xs uppercase mb-3">Общее</h3>
        {editing ? (
          <div className="flex items-center gap-2">
            <input value={newName} onChange={e => setNewName(e.target.value)}
                   className="flex-1 px-3 py-2 border border-bd2 rounded-xl text-sm font-medium"/>
            <button onClick={handleSave} disabled={saving}
                    className="p-2 rounded-xl bg-blue-600 text-white disabled:opacity-50">
              <Save size={14}/>
            </button>
            <button onClick={() => { setEditing(false); setNewName(ws.name); }}
                    className="p-2 rounded-xl bg-sf2 text-tx"><X size={14}/></button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              {/* V1.17.0j: аватар workspace */}
              <div className="w-12 h-12 rounded-2xl bg-[color-mix(in_oklab,var(--cta)_16%,transparent)]
                              flex items-center justify-center flex-shrink-0 relative overflow-hidden">
                {avatarSrc && !avatarFailed ? (
                  <img src={avatarSrc} alt=""
                       className="absolute inset-0 w-full h-full object-cover" draggable={false}/>
                ) : (
                  <Hash size={20} className="text-cta"/>
                )}
              </div>
              <h2 className="text-xl font-black text-tx truncate">{ws.name}</h2>
            </div>
            {isOwner && (
              <button onClick={() => setEditing(true)} className="p-2 rounded-xl hover:bg-sf2 flex-shrink-0">
                <Edit2 size={14} className="text-lbl"/>
              </button>
            )}
          </div>
        )}
        <div className="mt-2 text-[10px] uppercase tracking-widest font-bold text-lbl">
          Тариф: {ws.plan}{ws.is_pulse_themed ? ' · Pulse-themed' : ''}
        </div>
      </div>

      {/* Chats */}
      <div className="bg-sff rounded-[2rem] p-5 border border-bd">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-black text-tx text-xs uppercase flex items-center">
            <MessageCircle className="mr-2 text-ok" size={14}/> {chatsTitle}
          </h3>
          {isOwner && connectLink && (
            <div className="flex items-center gap-2">
              <a href={connectLink} target="_blank" rel="noopener noreferrer"
                 className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 text-white
                            text-xs font-black uppercase tracking-wide hover:bg-emerald-700">
                <Plus size={12}/> Подключить чат
              </a>
              <button onClick={handleCopyLink} title="Скопировать ссылку"
                      className="p-2 rounded-xl bg-sf2 hover:bg-bd2 text-tx">
                {linkCopied ? <Check size={14} className="text-ok"/> : <Copy size={14}/>}
              </button>
            </div>
          )}
        </div>

        {details.chats.length === 0 && (
          <div className="text-xs text-lbl font-medium">
            Нет подключённых чатов. Нажми «Подключить чат» и добавь бота в нужный чат.
          </div>
        )}

        <div className="space-y-2">
          {details.chats.map(c => {
            const meta = c.role ? CHAT_ROLE_META[c.role] : null;
            const isRemoved = !!c.removed_at;  // V1.17.0i (C6): soft-removed чат
            return (
              <div
                key={c.chat_id}
                className={`p-3 rounded-2xl transition-opacity ${
                  isRemoved
                    ? 'bg-sf2 opacity-70 border-l-4 border-[color-mix(in_oklab,var(--danger)_60%,transparent)]'
                    : 'bg-sf2'
                }`}>
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-black text-sm text-tx truncate">
                      {c.title || `Чат ${c.chat_id}`}
                    </div>
                    <div className="text-[10px] uppercase tracking-widest font-bold text-lbl mt-0.5">
                      {c.chat_type || '—'} · добавлен {c.added_at?.slice(0, 10) || '—'}
                    </div>
                    {isRemoved && (
                      <div className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-md
                                      text-[10px] font-black uppercase tracking-wide
                                      bg-[color-mix(in_oklab,var(--danger)_14%,transparent)] text-danger
                                      border border-[color-mix(in_oklab,var(--danger)_36%,transparent)]"
                           title="Pulse Bot был удалён из чата. Добавьте его обратно — роль и настройки восстановятся.">
                        🔴 Бот не в чате — добавьте обратно, роль восстановится
                      </div>
                    )}
                  </div>
                  {meta && (
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg
                                      text-[10px] font-black uppercase tracking-wide border ${meta.color}`}>
                      <meta.icon size={11}/> {meta.label}
                    </span>
                  )}
                  {isOwner && !isRemoved && (
                    <button
                      disabled={savingRole === c.chat_id}
                      onClick={() => handleDisconnectChat(c.chat_id, c.title || `Чат ${c.chat_id}`)}
                      title="Отключить чат — бот покинет его"
                      className="p-2 rounded-xl hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] text-danger disabled:opacity-50">
                      <LogOut size={14}/>
                    </button>
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
                                              : 'bg-sff text-txd border-bd2 hover:bg-sf2'}`}>
                          <r.icon size={11}/> {r.label}
                        </button>
                      );
                    })}
                    {c.role && (
                      <button disabled={savingRole === c.chat_id}
                              onClick={() => handleSetChatRole(c.chat_id, null)}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px]
                                         font-black uppercase tracking-wide border bg-sff text-lbl
                                         border-bd2 hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] hover:text-danger disabled:opacity-50">
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
      <div className="bg-sff rounded-[2rem] p-5 border border-bd">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-black text-tx text-xs uppercase flex items-center">
            <Users className="mr-2 text-purple" size={14}/> Помощники ({details.members.length})
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
            <div key={m.user_id} className="flex items-center justify-between p-3 bg-sf2 rounded-2xl">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-bd2 flex items-center justify-center text-xs font-black text-txd">
                  {String(m.user_id).slice(-2)}
                </div>
                <div>
                  <div className="font-black text-sm text-tx">ID {m.user_id}</div>
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wide ${ROLE_COLOR[m.role]}`}>
                    {ROLE_LABEL[m.role]}
                  </span>
                </div>
              </div>
              {isOwner && m.role !== 'owner' && (
                <button onClick={() => handleRemove(m.user_id)}
                        className="p-2 rounded-xl hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] text-danger">
                  <Trash2 size={14}/>
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Danger zone — удаление сообщества (только не-Pulse, только owner) */}
      {isOwner && !ws.is_pulse_themed && (
        <div className="bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] border-2 border-dashed border-[color-mix(in_oklab,var(--danger)_40%,transparent)] rounded-[2rem] p-5">
          <h3 className="font-black text-danger text-xs uppercase mb-2 flex items-center">
            <AlertTriangle className="mr-2 text-danger" size={14}/> Опасная зона
          </h3>
          <p className="text-xs text-danger font-medium mb-3">
            Удаление сообщества необратимо. Бот покинет все привязанные чаты, помощники потеряют доступ.
          </p>
          <button onClick={handleDeleteWorkspace}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-600 text-white
                             text-xs font-black uppercase tracking-wide hover:bg-red-700">
            <Trash2 size={14}/> Удалить сообщество
          </button>
        </div>
      )}
      {isOwner && ws.is_pulse_themed && (
        <div className="bg-sf2 border border-dashed border-bd2 rounded-2xl p-3 text-[11px] text-txd font-medium">
          Это Pulse-сообщество — удалить через сайт нельзя.
        </div>
      )}
    </div>
  );
}
