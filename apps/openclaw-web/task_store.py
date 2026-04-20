"""
Task Store — 轻量任务队列（内存 + SQLite 持久化）
create_task / get_task / list_task_events / bind_task_message
"""
import sqlite3, json, uuid, threading, os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("OPENCLAW_WEB_DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "tasks.db"

_lock = threading.Lock()

def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.row_factory = sqlite3.Row
    return conn

def init():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                source_channel TEXT,
                source_account_id TEXT,
                source_chat_id TEXT,
                source_user_id TEXT,
                source_message_id TEXT,
                source_thread_id TEXT,
                reply_to_id TEXT,
                model_session_id TEXT,
                task_type TEXT,
                prompt_text TEXT,
                attachment_path TEXT,
                attachment_name TEXT,
                attachment_kind TEXT,
                delivery_target TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                result_text TEXT,
                error_text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                content TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS task_message_links (
                task_id TEXT PRIMARY KEY,
                conversation_id TEXT,
                assistant_message_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
        """)

@contextmanager
def get_db():
    conn = _conn()
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def _now():
    return datetime.now(timezone.utc).isoformat()

def create_task(
    conversation_id: Optional[str] = None,
    source_channel: str = "web",
    source_account_id: Optional[str] = None,
    source_chat_id: Optional[str] = None,
    source_user_id: Optional[str] = None,
    source_message_id: Optional[str] = None,
    source_thread_id: Optional[str] = None,
    reply_to_id: Optional[str] = None,
    model_session_id: Optional[str] = None,
    task_type: str = "text",
    prompt_text: str = "",
    attachment_path: Optional[str] = None,
    attachment_name: Optional[str] = None,
    attachment_kind: Optional[str] = None,
    delivery_target: Optional[dict] = None,
) -> str:
    task_id = f"task_{uuid.uuid4().hex}"
    now = _now()
    with get_db() as db:
        db.execute("""
            INSERT INTO tasks (id, conversation_id, source_channel, source_account_id,
                source_chat_id, source_user_id, source_message_id, source_thread_id,
                reply_to_id, model_session_id, task_type, prompt_text,
                attachment_path, attachment_name, attachment_kind, delivery_target,
                status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (
            task_id, conversation_id, source_channel, source_account_id,
            source_chat_id, source_user_id, source_message_id, source_thread_id,
            reply_to_id, model_session_id, task_type, prompt_text,
            attachment_path, attachment_name, attachment_kind,
            json.dumps(delivery_target) if delivery_target else None,
            now, now
        ))
        db.execute("""
            INSERT INTO task_events (task_id, event_type, content, created_at)
            VALUES (?, 'created', ?, ?)
        """, (task_id, prompt_text[:200], now))
    return task_id

def get_task(task_id: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        return dict(row)

def update_task(task_id: str, **kwargs):
    sets = []
    vals = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(_now())
    vals.append(task_id)
    with get_db() as db:
        db.execute(f"UPDATE tasks SET {','.join(sets)} WHERE id = ?", vals)

def add_task_event(task_id: str, event_type: str, content: str = ""):
    with get_db() as db:
        db.execute("""
            INSERT INTO task_events (task_id, event_type, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (task_id, event_type, content, _now()))

def list_task_events(task_id: str) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def bind_task_message(task_id: str, conversation_id: str, assistant_message_id: str):
    now = _now()
    with get_db() as db:
        db.execute("""
            INSERT OR REPLACE INTO task_message_links
            (task_id, conversation_id, assistant_message_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, conversation_id, assistant_message_id, now, now))

def get_task_message_link(task_id: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM task_message_links WHERE task_id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

# 初始化
try:
    init()
except Exception as e:
    print(f"[task_store] init error: {e}")
