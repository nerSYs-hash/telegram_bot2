// WorkspaceList (V1.17.0b13) — карточка списка сообществ на дашборде
// V1.17.0i (P4 C6+C8): ярлык «⭐ Главное / №N доп.» + красный бейдж
// «🔴 Бот не в чате», когда активных чатов 0 (но раньше был хотя бы один —
// бот удалён, не пустое сообщество без подключений).
import React from 'react';
import { Users, MessageCircle, ChevronRight, Plus, Plug } from 'lucide-react';
import { useWorkspaces } from './useWorkspaces';

export default function WorkspaceList({ token, onSelectWorkspace, onConnectClick }) {
  const { workspaces, loading, error } = useWorkspaces(token);

  // Состояние "Без чата" — никаких workspace
  if (!loading && workspaces.length === 0) {
    return (
      <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-[2rem] p-5
                      border border-blue-700 shadow-md text-white flex flex-col justify-between">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-white/15 backdrop-blur
                          flex items-center justify-center border border-white/30 flex-shrink-0">
            <Plug size={18} className="text-white"/>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-black uppercase tracking-wide">Без чата</h3>
            <p className="text-xs font-medium text-blue-100 mt-1 leading-snug">
              Pulse Bot ещё не работает в вашем чате
            </p>
          </div>
        </div>
        <button
          onClick={onConnectClick}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                     bg-sff text-cta font-black text-xs uppercase tracking-wide
                     hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] active:scale-[0.98] transition-all shadow">
          <Plug size={14}/> Подключить чат
        </button>
      </div>
    );
  }

  return (
    <div className="bg-sff rounded-[2rem] p-5 border border-bd space-y-2">
      <h3 className="font-black text-tx text-xs uppercase flex items-center mb-3">
        <Users className="mr-2 text-cta" size={14}/> Мои сообщества
      </h3>
      {error && <div className="text-xs text-danger font-medium">{error}</div>}
      {loading && <div className="text-xs text-lbl font-medium">Загрузка…</div>}
      <div className="space-y-2">
        {(() => {
          let extraIdx = 1; // первый ++ даст №2 (главное вне нумерации)
          return workspaces.map(ws => {
            // C6: active_chats_count — новое поле; на старом API → fallback на chats_count
            const total = ws.chats_count ?? 0;
            const active = ws.active_chats_count ?? total;
            const allRemoved = total > 0 && active === 0;
            const chatsLabel = active === total
              ? `${total} чат.`
              : `${active}/${total} чат.`;
            // C8: ярлык primary/доп. — primary вне нумерации
            const isPrimary = !!ws.is_primary;
            const tagIdx = isPrimary ? null : ++extraIdx;
            return (
              <button
                key={ws.id}
                onClick={() => onSelectWorkspace?.(ws.id)}
                className="w-full flex items-center justify-between p-3 bg-sf2 rounded-2xl
                           hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] hover:border-[color-mix(in_oklab,var(--cta)_40%,transparent)] border border-transparent
                           transition-all">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-9 h-9 rounded-xl bg-[color-mix(in_oklab,var(--cta)_16%,transparent)] flex items-center justify-center flex-shrink-0">
                    <MessageCircle size={16} className="text-cta"/>
                  </div>
                  <div className="text-left min-w-0 flex-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-black text-sm text-tx truncate">{ws.name}</span>
                      {isPrimary ? (
                        <span className="px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-wide
                                         bg-[color-mix(in_oklab,var(--warn)_16%,transparent)] text-warn
                                         border border-[color-mix(in_oklab,var(--warn)_36%,transparent)] flex-shrink-0">
                          ⭐ Главное
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-wide
                                         bg-sff text-txd border border-bd2 flex-shrink-0">
                          №{tagIdx} доп.
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] uppercase tracking-widest font-bold text-lbl mt-0.5">
                      {ws.role} · {ws.members_count} участн. · {chatsLabel}
                    </div>
                    {allRemoved && (
                      <div
                        title="Pulse Bot был удалён из подключённого чата. Добавьте его обратно — роль и настройки сохранены."
                        className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-md
                                   text-[10px] font-black uppercase tracking-wide
                                   bg-[color-mix(in_oklab,var(--danger)_14%,transparent)] text-danger
                                   border border-[color-mix(in_oklab,var(--danger)_36%,transparent)]">
                        🔴 Бот не в чате
                      </div>
                    )}
                  </div>
                </div>
                <ChevronRight size={16} className="text-lbl flex-shrink-0"/>
              </button>
            );
          });
        })()}
      </div>
      <button
        onClick={onConnectClick}
        className="mt-3 w-full flex items-center justify-center gap-2 py-2.5
                   border-2 border-dashed border-[color-mix(in_oklab,var(--cta)_40%,transparent)] rounded-2xl
                   text-cta font-black text-xs uppercase tracking-wide
                   hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] transition-all">
        <Plus size={14}/> Подключить ещё чат
      </button>
    </div>
  );
}
