import { useState, useEffect } from 'react';
import { Palette, Save, CheckCircle2 } from 'lucide-react';
import { makeApi } from './useApi';

/**
 * Маленькая панель «Подпись и брендинг» — встраивается на страницу пресс-релизов
 * либо в Систему. Сохраняет ключи в branding_settings (signature и т.п.).
 */
export default function BrandingPanel({ token }) {
  const api = makeApi(token);
  const [signature, setSignature] = useState('');
  const [savedAt,   setSavedAt]   = useState(null);
  const [busy,      setBusy]      = useState(false);

  useEffect(() => {
    api.getBranding().then(d => setSignature(d?.signature || '')).catch(() => {});
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      await api.setBranding('signature', signature);
      setSavedAt(Date.now());
      setTimeout(() => setSavedAt(null), 2000);
    } catch (e) {
      alert('Ошибка: ' + (e?.detail || e?.message || e));
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-5 space-y-3">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-pink-100 flex items-center justify-center">
          <Palette size={16} className="text-pink-600" />
        </div>
        <div className="flex-1">
          <h2 className="text-xs font-black uppercase tracking-widest text-gray-900">Подпись и брендинг</h2>
          <p className="text-[10px] text-gray-400 mt-0.5">
            Кастомная подпись добавляется в конец пресс-релиза, если включён тумблер «Добавить подпись»
          </p>
        </div>
        {savedAt && (
          <span className="flex items-center gap-1 text-[10px] font-black text-emerald-500">
            <CheckCircle2 size={12}/> сохранено
          </span>
        )}
      </div>

      <textarea
        value={signature}
        onChange={(e) => setSignature(e.target.value)}
        placeholder='— <b>Pulse Community</b> | @pulse_chat'
        rows={3}
        className="w-full px-4 py-3 bg-gray-50 border-2 border-gray-100 rounded-xl text-sm font-mono focus:outline-none focus:border-blue-200 resize-y"
      />
      <p className="text-[10px] text-gray-400">
        Поддерживается HTML: <code className="bg-gray-100 px-1 rounded">&lt;b&gt;</code>{' '}
        <code className="bg-gray-100 px-1 rounded">&lt;i&gt;</code>{' '}
        <code className="bg-gray-100 px-1 rounded">&lt;a href&gt;</code>
      </p>

      {/* Превью */}
      {signature.trim() && (
        <div className="bg-gray-50 border border-gray-100 rounded-xl p-3">
          <div className="text-[9px] font-black uppercase tracking-widest text-gray-400 mb-1">Превью</div>
          <div className="text-sm text-gray-700" dangerouslySetInnerHTML={{ __html: signature }} />
        </div>
      )}

      <div className="flex justify-end">
        <button onClick={save} disabled={busy}
          className="px-4 py-2.5 bg-blue-500 text-white rounded-2xl font-black text-sm shadow-md shadow-blue-100 hover:bg-blue-600 disabled:opacity-50 flex items-center gap-1.5">
          <Save size={13}/> Сохранить подпись
        </button>
      </div>
    </div>
  );
}
