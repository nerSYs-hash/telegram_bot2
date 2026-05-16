import sqlite3
import pytest
from database.migrations.ws_runtime_seed import up_add_kind_column, seed_pulse_ws1


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE bot_chats (
            chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, role TEXT
        );
        CREATE TABLE bot_chat_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            thread_id INTEGER NOT NULL, name TEXT, source TEXT,
            UNIQUE(chat_id, thread_id)
        );
    ''')
    c.execute("INSERT INTO bot_chats VALUES (-100, 1, NULL)")
    c.commit()
    yield c
    c.close()


def test_add_kind_column_idempotent(conn):
    up_add_kind_column(conn)
    up_add_kind_column(conn)  # второй раз не падает
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chat_topics)")]
    assert 'kind' in cols


def test_seed_pulse_sets_main_role(conn):
    up_add_kind_column(conn)
    seed_pulse_ws1(conn, main_chat_id=-100, admin_chat_id=-100,
                   threads={'applications': 241, 'dossier': 176})
    role = conn.execute("SELECT role FROM bot_chats WHERE chat_id=-100").fetchone()[0]
    assert role == 'main'


def test_seed_pulse_inserts_threads(conn):
    up_add_kind_column(conn)
    seed_pulse_ws1(conn, main_chat_id=-100, admin_chat_id=-100,
                   threads={'applications': 241, 'dossier': 176})
    rows = dict(conn.execute(
        "SELECT kind, thread_id FROM bot_chat_topics WHERE workspace_id=1"
    ).fetchall())
    assert rows == {'applications': 241, 'dossier': 176}


def test_seed_idempotent(conn):
    up_add_kind_column(conn)
    seed_pulse_ws1(conn, main_chat_id=-100, admin_chat_id=-100,
                   threads={'applications': 241})
    seed_pulse_ws1(conn, main_chat_id=-100, admin_chat_id=-100,
                   threads={'applications': 241})
    n = conn.execute(
        "SELECT COUNT(*) FROM bot_chat_topics WHERE workspace_id=1 AND kind='applications'"
    ).fetchone()[0]
    assert n == 1
