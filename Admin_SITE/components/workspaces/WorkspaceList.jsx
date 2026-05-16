// WorkspaceList (V1.17.0b13) — карточка списка сообществ на дашборде
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
                     bg-white text-blue-700 font-black text-xs uppercase tracking-wide
                     hover:bg-blue-50 active:scale-[0.98] transition-all shadow">
          <Plug size={14}/> Подключить чат
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-[2rem] p-5 border border-gray-100 space-y-2">
      <h3 className="font-black text-gray-900 text-xs uppercase flex items-center mb-3">
        <Users className="mr-2 text-blue-500" size={14}/> Мои сообщества
      </h3>
      {error && <div className="text-xs text-red-600 font-medium">{error}</div>}
      {loading && <div className="text-xs text-gray-400 font-medium">Загрузка…</div>}
      <div className="space-y-2">
        {workspaces.map(ws => (
          <button
            key={ws.id}
            onClick={() => onSelectWorkspace?.(ws.id)}
            className="w-full flex items-center justify-between p-3 bg-gray-50 rounded-2xl
                       hover:bg-blue-50 hover:border-blue-200 border border-transparent
                       transition-all">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center flex-shrink-0">
                <MessageCircle size={16} className="text-blue-600"/>
              </div>
              <div className="text-left min-w-0">
                <div className="font-black text-sm text-gray-900 truncate">{ws.name}</div>
                <div className="text-[10px] uppercase tracking-widest font-bold text-gray-400 mt-0.5">
                  {ws.role} · {ws.members_count} участн. · {ws.chats_count} чат.
                </div>
              </div>
            </div>
            <ChevronRight size={16} className="text-gray-400 flex-shrink-0"/>
          </button>
        ))}
      </div>
      <button
        onClick={onConnectClick}
        className="mt-3 w-full flex items-center justify-center gap-2 py-2.5
                   border-2 border-dashed border-blue-200 rounded-2xl
                   text-blue-600 font-black text-xs uppercase tracking-wide
                   hover:bg-blue-50 transition-all">
        <Plus size={14}/> Подключить ещё чат
      </button>
    </div>
  );
}
