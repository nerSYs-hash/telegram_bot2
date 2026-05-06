import { useState, useEffect, useCallback } from 'react';
import { Megaphone, Loader2 } from 'lucide-react';
import { makeApi } from './useApi';
import PressReleaseEditor from './PressReleaseEditor';
import PressReleaseList from './PressReleaseList';
import BrandingPanel from './BrandingPanel';

export default function PressReleasePage({ token, userPermissions }) {
  const api = makeApi(token);

  const [chats, setChats]     = useState([]);
  const [posts, setPosts]     = useState([]);
  const [branding, setBrand]  = useState({});
  const [selected, setSelected] = useState(null);  // post или 'new'
  const [loading, setLoading] = useState(true);
  const [showBranding, setShowBranding] = useState(false);

  const userCan = useCallback((perm) =>
    Array.isArray(userPermissions) ? userPermissions.includes(perm) || userPermissions.includes('*') : false,
  [userPermissions]);

  const refresh = useCallback(async () => {
    try {
      const [c, p, b] = await Promise.all([
        api.listChats().catch(() => []),
        api.list().catch(() => []),
        api.getBranding().catch(() => ({})),
      ]);
      setChats(c);
      setPosts(p);
      setBrand(b);
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleSelect = (post) => {
    if (!post) { setSelected(null); return; }
    setSelected(post);
  };

  const handleCreate = () => {
    setSelected({ id: null, status: 'draft', targets: [] });
  };

  const handleAction = async (action, post) => {
    try {
      if (action === 'edit') {
        const full = await api.get(post.id);
        setSelected(full);
      } else if (action === 'clone') {
        const cloned = await api.clone(post.id);
        await refresh();
        setSelected(cloned);
      } else if (action === 'publish_now') {
        if (!confirm('Опубликовать сейчас?')) return;
        await api.publishNow(post.id);
        await refresh();
      } else if (action === 'cancel') {
        if (!confirm('Отменить запланированный пресс-релиз?')) return;
        await api.cancel(post.id);
        await refresh();
      } else if (action === 'restore') {
        await api.restore(post.id);
        await refresh();
      } else if (action === 'delete') {
        if (!confirm('Удалить пресс-релиз с сайта?\n\n⚠️ Сообщение в Telegram (если опубликовано) останется. Чтобы удалить и из Telegram — используйте кнопку «TG».')) return;
        await api.remove(post.id);
        if (selected?.id === post.id) setSelected(null);
        await refresh();
      } else if (action === 'delete_from_tg') {
        if (!confirm('Удалить сообщения из Telegram?\n\n⚠️ Это удалит опубликованные сообщения из чатов навсегда. Запись на сайте останется.')) return;
        const r = await api.deleteFromTg(post.id);
        alert(`Удалено: ${r.deleted}${r.errors?.length ? `\nОшибки: ${r.errors.join('\\n')}` : ''}`);
      }
    } catch (e) {
      alert('Ошибка: ' + (e?.detail || e?.message || JSON.stringify(e)));
    }
  };

  const handleSaved = async (saved) => {
    await refresh();
    if (saved) setSelected(saved);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={28} className="animate-spin text-blue-400" />
      </div>
    );
  }

  return (
    <div className="space-y-3 pb-24">
      {/* Заголовок */}
      <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-4 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-violet-100 flex items-center justify-center">
          <Megaphone size={16} className="text-violet-600" />
        </div>
        <div className="flex-1">
          <h1 className="text-sm font-black uppercase tracking-widest text-gray-900">Пресс-Релизы</h1>
          <p className="text-[10px] text-gray-400 mt-0.5">
            Создание, планирование и история публикаций в чаты/каналы
          </p>
        </div>
        <button onClick={() => setShowBranding(s => !s)}
          className="px-3 py-2 bg-pink-50 text-pink-700 rounded-xl text-xs font-black hover:bg-pink-100">
          🎨 Брендинг
        </button>
      </div>

      {/* Брендинг (раскрывающийся) */}
      {showBranding && <BrandingPanel token={token} />}

      {/* Split layout: editor (left) + list (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3">
        {/* Левая колонка: редактор */}
        <div className="min-w-0">
          {selected ? (
            <PressReleaseEditor
              api={api}
              chats={chats}
              branding={branding}
              post={selected.id ? selected : null}
              onSaved={handleSaved}
              onClose={() => setSelected(null)}
              userCan={userCan}
            />
          ) : (
            <EmptyEditor onCreate={handleCreate} />
          )}
        </div>

        {/* Правая колонка: список */}
        <div className="min-w-0">
          <PressReleaseList
            api={api}
            posts={posts}
            selectedId={selected?.id || null}
            onSelect={handleSelect}
            onAction={handleAction}
            onCreate={handleCreate}
            userCan={userCan}
          />
        </div>
      </div>
    </div>
  );
}

function EmptyEditor({ onCreate }) {
  return (
    <div className="bg-white rounded-3xl border-2 border-dashed border-gray-200 p-12 flex flex-col items-center justify-center text-center min-h-[400px]">
      <Megaphone size={40} className="text-gray-300 mb-3" />
      <h3 className="text-sm font-black text-gray-700 mb-1">Выберите пресс-релиз справа</h3>
      <p className="text-xs text-gray-400 mb-4">или создайте новый</p>
      <button onClick={onCreate}
        className="px-5 py-2.5 bg-blue-500 text-white rounded-2xl font-black text-sm shadow-md shadow-blue-100 hover:bg-blue-600 transition-all">
        + Новый пресс-релиз
      </button>
    </div>
  );
}
