// PressReleasePage — страница раздела «Пресс-релизы»:
// список (PressReleaseList) → редактор (PressReleaseEditor)
// → предпросмотр и планировщик публикаций.

import { useState, useEffect, useCallback, useRef } from 'react';
import { Megaphone, Loader2, Plus } from 'lucide-react';
import { makeApi } from './useApi';
import PressReleaseEditor from './PressReleaseEditor';
import PressReleaseList from './PressReleaseList';
import BrandingPanel from './BrandingPanel';
import ConfirmDialog from '../shared/ConfirmDialog';
import Button from '../shared/Button';

export default function PressReleasePage({ token, userPermissions, userId }) {
  const api = makeApi(token);

  const [chats, setChats]     = useState([]);
  const [posts, setPosts]     = useState([]);
  const [branding, setBrand]  = useState({});
  const [selected, setSelected] = useState(null);  // post или 'new'
  const [loading, setLoading] = useState(true);
  const editorRef             = useRef(null);
  const [leaveDialog, setLeaveDialog] = useState(null);  // { resolve }

  /** Спросить «сохранить?» если черновик грязный. Возвращает true если можно идти дальше. */
  const confirmDiscard = useCallback(() => new Promise((resolve) => {
    if (!editorRef.current?.isDirty?.()) { resolve(true); return; }
    setLeaveDialog({ resolve });
  }), []);

  const dialogConfirm = useCallback(async () => {
    // «Продолжить настройку» — остаться, не уходить
    leaveDialog?.resolve?.(false);
    setLeaveDialog(null);
  }, [leaveDialog]);

  const dialogCancel = useCallback(() => {
    // «Выйти» — отбросить изменения и уйти
    editorRef.current?.discardChanges?.();
    leaveDialog?.resolve?.(true);
    setLeaveDialog(null);
  }, [leaveDialog]);

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

  const handleSelect = async (post) => {
    if (!(await confirmDiscard())) return;
    if (!post) { setSelected(null); return; }
    setSelected(post);
  };

  const handleCreate = async () => {
    if (!(await confirmDiscard())) return;
    setSelected({ id: null, status: 'draft', targets: [] });
  };

  const handleClose = async () => {
    if (!(await confirmDiscard())) return;
    setSelected(null);
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
      <div className="bg-sff rounded-3xl border border-bd shadow-sm p-4 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-[color-mix(in_oklab,var(--purple)_16%,transparent)] flex items-center justify-center">
          <Megaphone size={16} className="text-purple" />
        </div>
        <div className="flex-1">
          <h1 className="text-sm font-black uppercase tracking-widest text-tx">Пресс-Релизы</h1>
          <p className="text-[10px] text-lbl mt-0.5">
            Создание, планирование и история публикаций в чаты/каналы
          </p>
        </div>
      </div>

      {/* Split layout: editor (left) + list (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3">
        {/* Левая колонка: редактор */}
        <div className="min-w-0">
          {selected ? (
            <PressReleaseEditor
              ref={editorRef}
              api={api}
              token={token}
              userId={userId}
              chats={chats}
              branding={branding}
              post={selected.id ? selected : null}
              onSaved={handleSaved}
              onClose={handleClose}
              userCan={userCan}
              onBrandingChange={refresh}
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

      {/* Модал подтверждения выхода с несохранёнными изменениями */}
      <ConfirmDialog
        open={!!leaveDialog}
        title="Внимание"
        message={<>Вы уверены, что хотите покинуть раздел?<br/>Несохранённые изменения пресс-релиза будут потеряны.</>}
        cancelLabel="Выйти"
        confirmLabel="Продолжить настройку"
        onCancel={dialogCancel}
        onConfirm={dialogConfirm}
      />
    </div>
  );
}

function EmptyEditor({ onCreate }) {
  return (
    <div className="bg-sff rounded-3xl border-2 border-dashed border-bd2 p-12 flex flex-col items-center justify-center text-center min-h-[400px]">
      <Megaphone size={40} className="text-lbl mb-3" />
      <h3 className="text-sm font-black text-tx mb-1">Выберите пресс-релиз справа</h3>
      <p className="text-xs text-lbl mb-4">или создайте новый</p>
      <Button variant="primary" size="md" icon={Plus} onClick={onCreate}>
        Новый пресс-релиз
      </Button>
    </div>
  );
}
