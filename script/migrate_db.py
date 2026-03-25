"""Миграция данных из registration_system/pulse_bot.db в pulse_bot.db"""
import sqlite3
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(BASE, 'registration_system', 'pulse_bot.db')
DST_PATH = os.path.join(BASE, 'pulse_bot.db')

src = sqlite3.connect(SRC_PATH)
src.row_factory = sqlite3.Row
dst = sqlite3.connect(DST_PATH)

sc = src.cursor()
dc = dst.cursor()

# --- USERS ---
common_cols = [
    'tg_id', 'username', 'first_name', 'last_name', 'role', 'status',
    'is_banned', 'ban_reason', 'q_name', 'q_age', 'q_city', 'q_therapy',
    'created_at', 'last_seen', 'last_exit_at', 'survey_sent_at',
    'last_rejection_reason', 'invite_link', 'previous_username',
    'previous_first_name', 'previous_last_name', 'birth_date',
    'blocked_until', 'invite_message_id', 'last_activity',
    'questionnaire_state', 'referral_code', 'referred_by',
    'referral_count', 'referral_earnings',
]
sc.execute('SELECT * FROM users')
users = sc.fetchall()
inserted_u = 0
for u in users:
    vals = [u[c] for c in common_cols]
    ph = ','.join(['?' for _ in common_cols])
    cs = ','.join(common_cols)
    dc.execute(f'INSERT OR IGNORE INTO users ({cs}) VALUES ({ph})', vals)
    if dc.rowcount > 0:
        inserted_u += 1
print(f'users: {inserted_u} inserted, {len(users) - inserted_u} skipped')

# --- APPLICATIONS ---
sc.execute('PRAGMA table_info(applications)')
src_app_cols = [r[1] for r in sc.fetchall()]
dc.execute('PRAGMA table_info(applications)')
dst_app_cols = {r[1] for r in dc.fetchall()}
app_cols = [c for c in src_app_cols if c in dst_app_cols]

sc.execute('SELECT * FROM applications')
apps = sc.fetchall()
inserted_a = 0
for a in apps:
    vals = [a[c] for c in app_cols]
    ph = ','.join(['?' for _ in app_cols])
    cs = ','.join(app_cols)
    dc.execute(f'INSERT OR IGNORE INTO applications ({cs}) VALUES ({ph})', vals)
    if dc.rowcount > 0:
        inserted_a += 1
print(f'applications: {inserted_a} inserted, {len(apps) - inserted_a} skipped')

# --- INVITE_LINKS ---
sc.execute('PRAGMA table_info(invite_links)')
src_il_cols = [r[1] for r in sc.fetchall()]
dc.execute('PRAGMA table_info(invite_links)')
dst_il_cols = {r[1] for r in dc.fetchall()}
il_cols = [c for c in src_il_cols if c in dst_il_cols]

sc.execute('SELECT * FROM invite_links')
links = sc.fetchall()
inserted_l = 0
for lnk in links:
    vals = [lnk[c] for c in il_cols]
    ph = ','.join(['?' for _ in il_cols])
    cs = ','.join(il_cols)
    dc.execute(f'INSERT OR IGNORE INTO invite_links ({cs}) VALUES ({ph})', vals)
    if dc.rowcount > 0:
        inserted_l += 1
print(f'invite_links: {inserted_l} inserted, {len(links) - inserted_l} skipped')

dst.commit()
src.close()
dst.close()
print('Migration complete.')
