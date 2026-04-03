content = open('handlers/owner_handlers.py', encoding='utf-8').read()
lines = content.split('\n')

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Conflict 8 (0-indexed: 793-843) -- keep HEAD (compensate) + dev (journal_connect)
    if i == 793:
        head_content = lines[794:839]
        dev_content = lines[841:843]
        new_lines.extend(head_content)
        new_lines.extend(dev_content)
        i = 844
        continue
    
    # Conflict 9 (0-indexed: 955-1029)
    elif i == 955:
        head_content = lines[956:1010]
        # Build merged show_recovery_menu (all buttons)
        merged = [
            '# ═══════════════════════════════════════════════════════════════',
            '#  🆘 ВОССТАНОВЛЕНИЕ ВЕТОК',
            '# ═══════════════════════════════════════════════════════════════',
            '',
            '# Константы форума',
            '_RECOVERY_CHAT_ID = -1003153855971',
            '_BBS_THREAD_ID = 8',
            '_NEWS_THREAD_ID = 26',
            '',
            '',
            'async def show_recovery_menu(query, db, admin_id: int) -> None:',
            '    """Меню восстановления веток."""',
            '    if not _is_owner(db, query.from_user.id, admin_id):',
            '        await query.answer("⛔", show_alert=True)',
            '        return',
            '    try:',
            '        db.cursor.execute("SELECT COUNT(*) FROM bbs_other_posts")',
            '        other_count = db.cursor.fetchone()[0]',
            '    except Exception:',
            '        other_count = 0',
            '    text = (',
            '        "🆘 <b>ВОССТАНОВЛЕНИЕ ВЕТОК</b>\\n\\n"',
            '        "Выберите ветку для восстановления из базы данных:"',
            '    )',
            '    keyboard = [',
            '        [InlineKeyboardButton("♻️ Восстановить BBS", callback_data="owner_restore_bbs")],',
            '        [InlineKeyboardButton("📰 Восстановить НьюзON", callback_data="owner_restore_news")],',
            '        [InlineKeyboardButton("🎁 Компенсация BBS", callback_data="owner_compensate_bbs")],',
            '        [InlineKeyboardButton(f"📦 Восстановить «Другое» ({other_count} шт.)", callback_data="owner_recovery_other_confirm")],',
            '        [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")],',
            '    ]',
            '    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))',
            '',
            '',
        ]
        new_lines.extend(merged)
        # Add restore_bbs_confirm from HEAD
        for j, hl in enumerate(head_content):
            if 'async def restore_bbs_confirm' in hl:
                new_lines.extend(head_content[j:])
                break
        i = 1030
        continue
    
    # Conflict 10 (0-indexed: 1034-1294) -- keep both HEAD and dev
    elif i == 1034:
        head_content = lines[1035:1265]
        dev_content = lines[1267:1295]
        new_lines.extend(head_content)
        new_lines.append('')
        new_lines.extend(dev_content)
        i = 1295
        continue
    
    else:
        new_lines.append(line)
        i += 1

print(f'Lines: {len(new_lines)}')
conflicts = [(i+1, l) for i, l in enumerate(new_lines) if '<<<<<<<' in l or '>>>>>>>' in l]
if conflicts:
    for ln, l in conflicts:
        print(f'CONFLICT REMAINS at line {ln}: {l}')
else:
    print('No conflicts remain')

open('handlers/owner_handlers.py', 'w', encoding='utf-8').write('\n'.join(new_lines))
print('Done - file written')
