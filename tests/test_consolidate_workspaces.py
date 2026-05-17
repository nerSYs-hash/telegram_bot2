import sqlite3, pytest
from scripts.consolidate_workspaces import consolidate, ConsolidateBlocked


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT, owner_user_id INTEGER, is_pulse_themed INTEGER, plan TEXT)")
    conn.execute("CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT)")
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER, role TEXT, removed_at TIMESTAMP)")
    conn.execute("CREATE TABLE economy_settings (workspace_id INTEGER, key TEXT)")
    for wid, themed in ((1, 1), (5, 0), (6, 0)):
        conn.execute("INSERT INTO workspaces VALUES (?,?,?,?,?)", (wid, f"W{wid}", 42, themed, 'free'))
        conn.execute("INSERT INTO workspace_members VALUES (?,?,?)", (wid, 42, 'owner'))
    conn.execute("INSERT INTO bot_chats VALUES (-1,1,'main',NULL)")
    conn.execute("INSERT INTO bot_chats VALUES (-5,5,'journal',NULL)")
    conn.execute("INSERT INTO bot_chats VALUES (-6,6,'admin',NULL)")
    conn.commit()
    return conn


def test_dry_run_changes_nothing():
    conn = _db()
    consolidate(conn, from_ids=[5, 6], into_id=1, apply=False)
    assert conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 3
    assert conn.execute("SELECT workspace_id FROM bot_chats WHERE chat_id=-5").fetchone()[0] == 5


def test_apply_repoints_and_deletes_empty():
    conn = _db()
    consolidate(conn, from_ids=[5, 6], into_id=1, apply=True)
    assert conn.execute("SELECT workspace_id FROM bot_chats WHERE chat_id=-5").fetchone()[0] == 1
    assert conn.execute("SELECT role FROM bot_chats WHERE chat_id=-5").fetchone()[0] == 'journal'
    assert conn.execute("SELECT COUNT(*) FROM workspaces WHERE id IN (5,6)").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM workspace_members WHERE workspace_id IN (5,6)").fetchone()[0] == 0


def test_apply_idempotent():
    conn = _db()
    consolidate(conn, from_ids=[5, 6], into_id=1, apply=True)
    consolidate(conn, from_ids=[5, 6], into_id=1, apply=True)  # no error, no-op
    assert conn.execute("SELECT workspace_id FROM bot_chats WHERE chat_id=-5").fetchone()[0] == 1


def test_blocks_if_source_has_tenant_data():
    conn = _db()
    conn.execute("INSERT INTO economy_settings VALUES (5,'k')")
    conn.commit()
    with pytest.raises(ConsolidateBlocked):
        consolidate(conn, from_ids=[5, 6], into_id=1, apply=True)
