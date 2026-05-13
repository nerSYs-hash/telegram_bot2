"""Production reset: перепривязать workspace=1 на нового владельца и новый чат.

Сценарий: предыдущий владелец ушёл из проекта, новый владелец сменил BOT_TOKEN
через BotFather, создал новые чаты в Telegram. Этот скрипт обновляет БД так,
чтобы бот стартовал в новых чатах с теми же settings/economy/BBS/титулами.

Идемпотентен — можно запускать несколько раз.

Usage:
    python scripts/reset_workspace_owner.py \\
        --new-owner-id 123456789 \\
        --new-chat-id -1001234567890 \\
        --new-chat-title "Новый Чат" \\
        --chat-type supergroup

Опционально:
    --db-path database/bot_database.db   # путь к БД (default из .env DATABASE_PATH)
    --dry-run                            # только показать, что будет сделано
    --keep-old-members                   # не удалять старых owner/admin/moderator
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--new-owner-id', type=int, required=True,
                        help='Telegram user_id нового владельца')
    parser.add_argument('--new-chat-id', type=int, required=True,
                        help='Telegram chat_id нового основного чата (TARGET_CHAT_ID)')
    parser.add_argument('--new-chat-title', type=str, default='Главный чат',
                        help='Название чата для bot_chats.title')
    parser.add_argument('--chat-type', type=str, default='supergroup',
                        choices=['group', 'supergroup', 'channel'],
                        help='Тип чата для bot_chats.chat_type (default supergroup)')
    parser.add_argument('--db-path', type=str,
                        default=os.path.join(os.path.dirname(__file__), '..',
                                             'database', 'bot_database.db'),
                        help='Путь к БД')
    parser.add_argument('--dry-run', action='store_true',
                        help='Показать что будет сделано, ничего не изменять')
    parser.add_argument('--keep-old-members', action='store_true',
                        help='Не удалять старых owner/admin/moderator из ws=1')
    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f'[FAIL] БД не найдена: {args.db_path}', file=sys.stderr)
        sys.exit(1)

    print(f'[info] DB: {args.db_path}')
    print(f'[info] New owner_user_id: {args.new_owner_id}')
    print(f'[info] New TARGET_CHAT_ID: {args.new_chat_id}')
    print(f'[info] New chat title: {args.new_chat_title!r}')
    print(f'[info] Chat type: {args.chat_type}')
    print(f'[info] Mode: {"DRY-RUN" if args.dry_run else "APPLY"}')
    print()

    # Бэкап перед изменением
    if not args.dry_run:
        backup_dir = os.path.join(os.path.dirname(args.db_path), '..', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'pre_reset_owner_{ts}.db')
        import shutil
        shutil.copy2(args.db_path, backup_path)
        print(f'[backup] {backup_path}')

    conn = sqlite3.connect(args.db_path)
    try:
        # 1. Проверка что ws=1 существует
        ws = conn.execute(
            'SELECT id, name, owner_user_id, is_pulse_themed, plan '
            'FROM workspaces WHERE id=1'
        ).fetchone()
        if not ws:
            print('[FAIL] workspace_id=1 не найден. Миграция multi_tenancy не применена?',
                  file=sys.stderr)
            sys.exit(1)
        old_owner = ws[2]
        print(f'[current] ws=1 name={ws[1]!r} owner={old_owner} '
              f'pulse_themed={bool(ws[3])} plan={ws[4]}')

        members = conn.execute(
            'SELECT user_id, role FROM workspace_members WHERE workspace_id=1 '
            'ORDER BY CASE role WHEN "owner" THEN 0 WHEN "admin" THEN 1 ELSE 2 END'
        ).fetchall()
        print(f'[current] members: {members}')

        chats = conn.execute(
            'SELECT chat_id, title FROM bot_chats WHERE workspace_id=1'
        ).fetchall()
        print(f'[current] bot_chats: {chats}')
        print()

        # 2. Обновить owner_user_id в workspaces
        print(f'[plan] UPDATE workspaces SET owner_user_id={args.new_owner_id} WHERE id=1')

        # 3. Members: удалить старого owner, удалить других admin/moderator (если не --keep)
        #    добавить нового owner
        if args.keep_old_members:
            print(f'[plan] DELETE FROM workspace_members WHERE workspace_id=1 '
                  f'AND user_id={old_owner}  -- старый owner')
        else:
            print(f'[plan] DELETE FROM workspace_members WHERE workspace_id=1  '
                  f'-- все старые члены')
        print(f'[plan] INSERT new owner (workspace_id=1, user_id={args.new_owner_id}, '
              f'role=owner)')

        # 4. bot_chats: удалить старые записи, добавить новую
        print(f'[plan] DELETE FROM bot_chats WHERE workspace_id=1  -- старые чаты')
        print(f'[plan] INSERT bot_chats (chat_id={args.new_chat_id}, workspace_id=1, '
              f'added_by_user_id={args.new_owner_id}, title={args.new_chat_title!r}, '
              f'chat_type={args.chat_type!r})')

        # 5. Убедиться что нового owner есть в `users` (иначе get_site_user вернёт None
        #    и invite через сайт не сработает для других)
        user_exists = conn.execute(
            'SELECT 1 FROM users WHERE user_id=?', (args.new_owner_id,)
        ).fetchone()
        if not user_exists:
            print(f'[plan] INSERT users (user_id={args.new_owner_id}, is_owner=1, '
                  f'is_admin=1)  -- юзера не было в users')
        else:
            print(f'[plan] UPDATE users SET is_owner=1, is_admin=1 '
                  f'WHERE user_id={args.new_owner_id}')

        if args.dry_run:
            print('\n[dry-run] изменения не применены. Уберите --dry-run для apply.')
            return

        # ── APPLY ──
        print('\n[apply] выполняю...')

        conn.execute('UPDATE workspaces SET owner_user_id=?, updated_at=CURRENT_TIMESTAMP '
                     'WHERE id=1', (args.new_owner_id,))

        if args.keep_old_members:
            conn.execute('DELETE FROM workspace_members WHERE workspace_id=1 AND user_id=?',
                         (old_owner,))
        else:
            conn.execute('DELETE FROM workspace_members WHERE workspace_id=1')

        conn.execute(
            'INSERT OR REPLACE INTO workspace_members (workspace_id, user_id, role) '
            'VALUES (1, ?, ?)',
            (args.new_owner_id, 'owner')
        )

        conn.execute('DELETE FROM bot_chats WHERE workspace_id=1')
        conn.execute('''
            INSERT INTO bot_chats (chat_id, workspace_id, added_by_user_id, title,
                                    chat_type, added_at)
            VALUES (?, 1, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (args.new_chat_id, args.new_owner_id, args.new_chat_title, args.chat_type))

        # users — гарантируем наличие
        if not user_exists:
            conn.execute(
                'INSERT INTO users (user_id, is_owner, is_admin) VALUES (?, 1, 1)',
                (args.new_owner_id,)
            )
        else:
            conn.execute(
                'UPDATE users SET is_owner=1, is_admin=1 WHERE user_id=?',
                (args.new_owner_id,)
            )

        conn.commit()
        print('[ok] изменения применены')

        # ── Recheck ──
        print('\n[recheck]')
        ws = conn.execute(
            'SELECT id, name, owner_user_id, is_pulse_themed, plan FROM workspaces WHERE id=1'
        ).fetchone()
        print(f'  ws=1: {ws}')
        members = conn.execute(
            'SELECT user_id, role FROM workspace_members WHERE workspace_id=1'
        ).fetchall()
        print(f'  members: {members}')
        chats = conn.execute(
            'SELECT chat_id, title, chat_type FROM bot_chats WHERE workspace_id=1'
        ).fetchall()
        print(f'  bot_chats: {chats}')

        print('\n✅ Done. Дальше:')
        print('  1. Обновить .env: BOT_TOKEN, MAIN_ADMIN_ID, TARGET_CHAT_ID, '
              'ADMIN_CHAT_ID и thread IDs.')
        print('  2. systemctl restart pulse_bot')
        print('  3. В новом чате: /start от тебя → должен ответить как владельцу.')

    finally:
        conn.close()


if __name__ == '__main__':
    main()
