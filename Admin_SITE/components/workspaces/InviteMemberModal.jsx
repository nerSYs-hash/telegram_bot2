// InviteMemberModal (V1.17.0b15) — приглашение помощника owner-only
import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { X, UserPlus } from 'lucide-react';
import { inviteMember } from '../shared/api';

export default function InviteMemberModal({ token, wsId, onClose, onSuccess }) {
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState('admin');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const uid = parseInt(userId.replace('@', ''), 10);
      if (!uid || isNaN(uid)) throw new Error('Введи Telegram user_id (число)');
      await inviteMember(token, wsId, uid, role);
      onSuccess?.();
      onClose();
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-4
                    bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <form
        onSubmit={handleSubmit}
        onClick={e => e.stopPropagation()}
        className="bg-sff w-full max-w-md rounded-t-[2.5rem] sm:rounded-[2.5rem] p-6 shadow-2xl">
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-[color-mix(in_oklab,var(--purple)_16%,transparent)] flex items-center justify-center">
              <UserPlus size={22} className="text-purple"/>
            </div>
            <div>
              <h3 className="font-black text-tx text-base">Пригласить помощника</h3>
              <p className="text-xs text-txd font-medium">user_id из Telegram</p>
            </div>
          </div>
          <button type="button" onClick={onClose}
                  className="p-2 rounded-xl hover:bg-sf2">
            <X size={18} className="text-lbl"/>
          </button>
        </div>

        <label className="text-[10px] uppercase tracking-widest font-bold text-lbl mb-1.5 block">
          Telegram user_id
        </label>
        <input
          value={userId}
          onChange={e => setUserId(e.target.value)}
          placeholder="например 123456789"
          className="w-full px-3 py-3 border border-bd2 rounded-2xl text-sm font-medium mb-4
                     focus:border-blue-500 focus:outline-none"/>

        <label className="text-[10px] uppercase tracking-widest font-bold text-lbl mb-1.5 block">
          Роль
        </label>
        <div className="grid grid-cols-2 gap-2 mb-5">
          {['admin', 'moderator'].map(r => (
            <button key={r} type="button" onClick={() => setRole(r)}
                    className={`py-3 rounded-2xl font-black text-xs uppercase tracking-wide transition-all
                                ${role === r
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-sf2 text-txd hover:bg-bd2'}`}>
              {r === 'admin' ? '🛡 Админ' : '🔧 Модератор'}
            </button>
          ))}
        </div>

        {err && <div className="bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] text-danger rounded-2xl p-3 text-xs font-medium mb-4">{err}</div>}

        <button type="submit" disabled={loading || !userId}
                className="w-full py-4 rounded-2xl bg-blue-600 text-white font-black text-sm uppercase
                           tracking-wide hover:bg-blue-700 disabled:opacity-50">
          {loading ? 'Добавляю…' : 'Пригласить'}
        </button>
      </form>
    </div>,
    document.body
  );
}
