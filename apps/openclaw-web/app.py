from __future__ import annotations

# 移除 dist-packages 中的 weasyprint（版本冲突）
import sys as _wys_sys
_wys_sys.path = [p for p in _wys_sys.path if not (p.startswith('/usr/lib/python3/dist-packages'))]
import hashlib, hmac, json, logging, os, re, secrets, sqlite3, sys, uuid, threading, subprocess, time, tempfile, shutil
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request, Response, status, Header, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile as StarletteUploadFile

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from task_store import create_task, get_task, list_task_events, bind_task_message, get_task_message_link
from task_mode import resolve_task_mode
from asr_service import transcribe_audio

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
if MINIMAX_API_KEY:
    os.environ["MINIMAX_API_KEY"] = MINIMAX_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("OPENCLAW_WEB_DATA_DIR", str(BASE_DIR / "data")))
DB_PATH = DATA_DIR / "app.db"
TASKS_DB = DATA_DIR / "tasks.db"
ARTIFACTS_ROOT = Path(os.getenv("OPENCLAW_WEB_ARTIFACTS_DIR", str(BASE_DIR / "artifacts" / "tasks")))
STATIC_DIR = Path(os.getenv("OPENCLAW_WEB_STATIC_DIR", str(BASE_DIR / "static")))
IMAGES_DIR = STATIC_DIR / "images"
FILES_DIR = STATIC_DIR / "files"
TOKEN_SECRET = os.getenv("OPENCLAW_WEB_TOKEN_SECRET", "change-me-in-production")

# ─── Database ───────────────────────────────────────────────────────────────
def get_db(path=DB_PATH):
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row  # 始终使用 dict-style 访问
    return conn

def init_db():
    db = get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS conversations(
        id TEXT PRIMARY KEY, user_id INTEGER, title TEXT, status TEXT DEFAULT 'active',
        created_at TEXT, updated_at TEXT, last_message_at TEXT,
        owner_type TEXT DEFAULT 'user', owner_guest_cookie TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS messages(
        id TEXT PRIMARY KEY, conversation_id TEXT, role TEXT,
        content TEXT, content_type TEXT DEFAULT 'text', created_at TEXT,
        status TEXT DEFAULT 'done', error_text TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS attachments(
        id TEXT PRIMARY KEY, message_id TEXT, file_name TEXT,
        kind TEXT, url TEXT, created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT,
        is_active INTEGER DEFAULT 1, created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS guest_sessions(
        id TEXT PRIMARY KEY, guest_cookie TEXT, ip_hash TEXT,
        created_at TEXT, updated_at TEXT, expires_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS guest_rate_limits(
        ip_hash TEXT, action TEXT,
        request_count INTEGER DEFAULT 0, window_start TEXT,
        PRIMARY KEY (ip_hash, action))""")
    db.commit()
    db.close()

# ─── Auth ────────────────────────────────────────────────────────────────────
def make_token(user_id: int) -> str:
    return hmac.new(TOKEN_SECRET.encode(), str(user_id).encode(), "sha256").hexdigest()[:32]

def make_salt() -> str:
    return secrets.token_hex(16)

def verify_token(token: str) -> Optional[int]:
    if not token:
        return None
    db = get_db()
    row = db.execute(
        "SELECT user_id FROM web_sessions WHERE id=? AND expires_at>?",
        (token, datetime.now(timezone.utc).isoformat())
    ).fetchone()
    db.close()
    return row["user_id"] if row else None

def get_user(user_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    db.close()
    return dict(row) if row else None

# ─── Task Worker ─────────────────────────────────────────────────────────────
def _filter_dist_packages():
    import sys
    sys.path = [p for p in sys.path if 'dist-packages' not in p]

def markdown_to_pdf(md_path, task_id):
    """用 markdown + weasyprint 生成中文 PDF"""
    import markdown as md_lib
    try:
        import weasyprint as _wp
        weasyprint = _wp
    except Exception:
        weasyprint = None
    
    if weasyprint:
        pdf_path = str(ARTIFACTS_ROOT / task_id / "report.pdf")
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        try:
            with open(md_path, encoding="utf-8") as f:
                md_content = f.read()
            html_body = md_lib.markdown(md_content, extensions=['tables','fenced_code'])
            html_full = (
                '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
                '<style>body{font-family:"Noto Serif CJK SC","AR PL UMing CN",serif;'
                'font-size:12pt;line-height:1.8;max-width:800px;margin:2cm auto;padding:0 1cm;color:#333;}'
                'h1{color:#1a1a2e;border-bottom:2px solid #5465ff;padding-bottom:8px;}'
                'h2{color:#16213e;margin-top:24px;border-left:4px solid #5465ff;padding-left:12px;}'
                'table{border-collapse:collapse;width:100%;margin:16px 0;}'
                'th,td{border:1px solid #ddd;padding:8px;text-align:center;}'
                'th{background:#f0f2ff;}code{background:#f5f5f5;padding:2px 6px;border-radius:4px;}'
                'blockquote{border-left:4px solid #5465ff;margin:16px 0;padding:8px 16px;color:#555;}</style>'
                '</head><body>' + html_body + '</body></html>'
            )
            weasyprint.HTML(string=html_full).write_pdf(pdf_path)
            if os.path.exists(pdf_path):
                logger.info(f"[worker] PDF生成: {os.path.getsize(pdf_path)} bytes")
                return f"/api/tasks/{task_id}/download/report.pdf"
        except Exception as e:
            logger.error(f"[worker] PDF失败: {e}")
    return None

def find_artifact_links(task_id):
    adir = ARTIFACTS_ROOT / task_id
    if not adir.is_dir():
        return []
    return [f"/api/tasks/{task_id}/download/{f.name}" for f in adir.iterdir() if f.is_file()]

def normalize_media_paths_for_web(reply_text: str) -> str:
    raw = str(reply_text or "")
    if not raw:
        return raw

    static_dir = IMAGES_DIR
    static_dir.mkdir(exist_ok=True)

    def _replace(match):
        src = Path(match.group(1).strip())
        if not src.is_file():
            return match.group(0)
        ext = src.suffix.lower() or ".png"
        image_id = uuid.uuid4().hex[:16]
        dest = static_dir / f"{image_id}{ext}"
        shutil.copy2(src, dest)
        return f"[图片已生成](/images/{image_id}{ext})"

    return re.sub(r"MEDIA:([^\s]+)", _replace, raw)

def process_single_task(task: dict):
    tid = task["id"]
    prompt = task.get("prompt_text") or ""
    delivery = json.loads(task.get("delivery_target") or "{}")
    conv_id = delivery.get("conversation_id")
    logger.info(f"[worker] 处理任务 {tid}")

    REPORT_PREFIX = (
        "你是一位专业的行业研究报告撰写专家。请撰写一篇3000字以上、内容详尽的专业报告，"
        "必须包含以下全部章节：\n"
        "1. 摘要（Executive Summary）\n"
        "2. 行业背景与现状\n"
        "3. 市场规模与增长趋势（含数据）\n"
        "4. 核心技术与驱动因素\n"
        "5. 竞争格局与主要玩家\n"
        "6. 政策环境分析\n"
        "7. 发展趋势与预测（2026-2030）\n"
        "8. 投资机会与风险\n"
        "9. 结论与建议\n"
        "10. 参考来源与数据出处\n\n"
        "使用Markdown格式，章节标题用##，每个章节必须有至少300字以上的详细分析内容。\n\n"
        "【重要】必须将完整报告（3000字以上）保存为Markdown文件："
        + str(ARTIFACTS_ROOT / tid / "report.md") + "\n\n"
        "只需撰写报告内容，不要包含LaTeX代码，不要输出其他格式。\n\n"
    )

    try:
        env = os.environ.copy()
        if os.environ.get("AIPAIBOX_API_KEY"):
            env["AIPAIBOX_API_KEY"] = os.environ["AIPAIBOX_API_KEY"]
        result = subprocess.run(
            ["openclaw", "agent", "--session-id", "task-"+tid, "--message", REPORT_PREFIX + prompt],
            capture_output=True, text=True, timeout=300, env=env
        )
        answer = result.stdout if result.returncode == 0 else f"[错误] {result.stderr[:200]}"
    except Exception as e:
        answer = f"[错误] {e}"

    # 字数不足则补充
    if len(answer) < 3000:
        logger.info(f"[worker] 字数{len(answer)}不足3000，补充中...")
        supp = (
            "上述报告字数不足3000字，请继续补充，在每章节增加更详细的数据分析、案例和预测，"
            "使总字数达到3000字以上。然后将补充后的完整报告（包含所有章节）重新保存到"
            + str(ARTIFACTS_ROOT / tid / "report.md") + "，覆盖原有文件。"
        )
        try:
            env = os.environ.copy()
            if os.environ.get("AIPAIBOX_API_KEY"):
                env["AIPAIBOX_API_KEY"] = os.environ["AIPAIBOX_API_KEY"]
            r2 = subprocess.run(
                ["openclaw", "agent", "--session-id", "task-"+tid+"-sup", "--message", supp],
                capture_output=True, text=True, timeout=180, env=env
            )
            if r2.returncode == 0 and len(r2.stdout) > len(answer):
                answer = r2.stdout
        except Exception as e:
            logger.error(f"[worker] 补充失败: {e}")

    logger.info(f"[worker] 最终字数: {len(answer)}")

    # 去掉 LaTeX 源码，并把本地 MEDIA 路径转成 Web 可访问链接
    answer_clean = re.sub(r"附：LaTeX 源码.*", "", answer, flags=re.DOTALL).rstrip()
    answer_clean = normalize_media_paths_for_web(answer_clean)

    # 生成 PDF
    md_path = ARTIFACTS_ROOT / tid / "report.md"
    if md_path.exists():
        pdf_url = markdown_to_pdf(str(md_path), tid)
        if pdf_url:
            answer_clean += f"\n\n📕 [下载 PDF 版报告]({pdf_url})"

    # 追加 artifact 链接
    for link in find_artifact_links(tid):
        fname = os.path.basename(link)
        if fname not in answer_clean and link not in answer_clean:
            answer_clean += f"\n\n📄 [下载 {fname}]({link})"

    now = datetime.now(timezone.utc).isoformat()
    db = get_db(TASKS_DB)
    db.execute("UPDATE tasks SET status='done',result_text=?,finished_at=? WHERE id=?", (answer_clean, now, tid))
    db.commit()
    db.close()

    # 更新关联的助手消息
    if conv_id:
        adb = get_db()
        link = get_task_message_link(tid)
        if link:
            assistant_msg_id = link.get("assistant_message_id")
            adb.execute("UPDATE messages SET content=?,status='done' WHERE id=?", (answer_clean, assistant_msg_id))
        adb.execute("UPDATE conversations SET status='active',updated_at=? WHERE id=?", (now, conv_id))
        adb.commit()
        adb.close()

    logger.info(f"[worker] 任务 {tid} 完成")

def cleanup_expired_guest_sessions():
    """清理超过3小时的过期游客会话及其关联的对话、消息、附件"""
    try:
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        # 找出已过期的游客 token
        guest_user_id = db.execute("SELECT id FROM users WHERE username='__guest__'").fetchone()
        if not guest_user_id:
            db.close()
            return
        guest_user_id = guest_user_id[0]
        expired_tokens = db.execute(
            "SELECT id FROM web_sessions WHERE expires_at < ? AND user_id = ?",
            (now, guest_user_id)
        ).fetchall()
        
        expired_count = 0
        for (token,) in expired_tokens:
            # 找出该游客 token 关联的对话
            convs = db.execute(
                "SELECT id FROM conversations WHERE owner_type='guest' AND owner_guest_cookie=?",
                (token,)
            ).fetchall()
            
            for (conv_id,) in convs:
                # 删除附件
                db.execute("DELETE FROM attachments WHERE message_id IN (SELECT id FROM messages WHERE conversation_id=?)", (conv_id,))
                # 删除消息
                db.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
                # 删除对话
                db.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
                expired_count += 1
            
            # 删除过期的 web_session
            db.execute("DELETE FROM web_sessions WHERE id=?", (token,))
        
        db.commit()
        db.close()
        
        if expired_count > 0:
            logger.info(f"[cleanup] 清理了 {expired_count} 条过期游客对话")
    except Exception as e:
        logger.error(f"[cleanup] 清理失败: {e}")


def background_worker():
    logger.info("[worker] 后台线程启动")
    cleanup_interval = 60  # 每60秒检查一次
    last_cleanup = time.time()
    
    while True:
        try:
            db = get_db(TASKS_DB)
            row = db.execute("SELECT * FROM tasks WHERE status='pending' ORDER BY created_at ASC LIMIT 1").fetchone()
            db.close()
            if row:
                process_single_task(dict(row))
            else:
                time.sleep(2)
            
            # 每60秒清理一次过期游客会话
            if time.time() - last_cleanup >= cleanup_interval:
                cleanup_expired_guest_sessions()
                last_cleanup = time.time()
                
        except Exception as e:
            logger.error(f"[worker] 异常: {e}")
            time.sleep(5)

# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(title="OpenClaw Web Chat")

@app.on_event("startup")
def startup():
    init_db()
    threading.Thread(target=background_worker, daemon=True).start()
    logger.info("启动完成")

# ─── Rate limiting helpers ─────────────────────────────────────────────────
def get_client_ip(request: Request) -> str:
    """获取客户端 IP，优先从 X-Forwarded-For 取真实 IP"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

def check_guest_rate_limit(db, ip_hash: str, action: str, max_count: int, window_hours: float) -> tuple[bool, int, int]:
    """
    检查游客频率限制
    action: 'message' 或 'image'
    window_hours: 时间窗口（小时）
    返回: (allowed, current_count, remaining)
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)
    
    row = db.execute(
        "SELECT request_count, window_start FROM guest_rate_limits WHERE ip_hash=? AND action=?",
        (ip_hash, action)
    ).fetchone()
    
    if not row:
        return True, 0, max_count
    
    stored_start = datetime.fromisoformat(row["window_start"])
    if stored_start < window_start:
        # 窗口过期，重置
        return True, 0, max_count
    
    current = row["request_count"]
    if current >= max_count:
        return False, current, 0
    return True, current, max_count - current

def record_guest_action(db, ip_hash: str, action: str, max_count: int, window_hours: float):
    """记录一次游客操作，更新计数"""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)
    
    row = db.execute(
        "SELECT request_count, window_start FROM guest_rate_limits WHERE ip_hash=? AND action=?",
        (ip_hash, action)
    ).fetchone()
    
    if not row:
        db.execute(
            "INSERT INTO guest_rate_limits(ip_hash, action, request_count, window_start) VALUES(?,?,1,?)",
            (ip_hash, action, now.isoformat())
        )
    else:
        stored_start = datetime.fromisoformat(row["window_start"])
        if stored_start < now - timedelta(hours=window_hours):
            # 新窗口
            db.execute(
                "UPDATE guest_rate_limits SET request_count=1, window_start=? WHERE ip_hash=? AND action=?",
                (now.isoformat(), ip_hash, action)
            )
        else:
            db.execute(
                "UPDATE guest_rate_limits SET request_count=request_count+1 WHERE ip_hash=? AND action=?",
                (ip_hash, action)
            )


# ─── Auth helpers ────────────────────────────────────────────────────────────
def get_user_from_header(authorization: str = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        user_id = verify_token(token)
        return get_user(user_id) if user_id else None
    except:
        return None

# ─── API Routes ───────────────────────────────────────────────────────────────
@app.get("/ok")
async def root():
    return {"ok": True}

@app.get("/api/me")
async def me(user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    # 返回 username 或 name
    name = u.get("name") or u.get("username") or "-"
    role = u.get("role", "user")
    is_guest = u.get("username") == "__guest__"
    # 游客用户特殊处理
    if is_guest:
        name = "游客"
        role = "guest"
    # 是否可发邮件（仅 Akihiro 用户可发邮件）
    can_send_mail = not is_guest and name == "Akihiro"
    return {
        "id": u["id"],
        "name": name,
        "role": role,
        "auth": {
            "mode": role,
            "can_send_mail": can_send_mail
        }
    }

@app.post("/api/login")
async def login(req: Request):
    body = await req.json()
    db = get_db()
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM users WHERE username=? AND is_active=1", (body.get("username",""),)).fetchone()
    if not row:
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)
    import hashlib
    pwd_hash = hashlib.sha256((body.get("password","") or "").encode()).hexdigest()
    if dict(row)["password_hash"] != pwd_hash:
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)
    user_id = dict(row)["id"]
    token = make_token(user_id)
    exp = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    db.execute("INSERT OR REPLACE INTO web_sessions(id,user_id,created_at,expires_at) VALUES(?,?,?,?)",
               (token, user_id, datetime.now(timezone.utc).isoformat(), exp))
    db.commit()
    db.close()
    return {"token": token, "user": {"id": user_id, "name": dict(row).get("username")}}

@app.get("/api/conversations")
async def list_conversations(user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    db = get_db()
    # 游客只能看到自己的对话（按 token 隔离）
    if u.get("username") == "__guest__":
        rows = db.execute(
            "SELECT * FROM conversations WHERE user_id=? AND owner_type='guest' AND owner_guest_cookie=? ORDER BY updated_at DESC",
            (u["id"], user)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC", (u["id"],)).fetchall()
    db.close()
    return {"conversations": [dict(r) for r in rows]}

@app.post("/api/conversations")
async def create_conversation(req: Request, user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    body = await req.json()
    cid = "conv_" + uuid.uuid4().hex[:24]
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    
    # 区分游客和正式用户
    owner_type = "user"
    owner_guest_cookie = None
    if u.get("username") == "__guest__":
        owner_type = "guest"
        # 游客：使用 token 作为会话标识，用于3小时后自动清理
        owner_guest_cookie = user
    
    db.execute("INSERT INTO conversations(id,title,user_id,status,created_at,updated_at,owner_type,owner_guest_cookie) VALUES(?,?,?,?,?,?,?,?)",
               (cid, body.get("title","新对话"), u["id"], "active", now, now, owner_type, owner_guest_cookie))
    db.commit()
    row = db.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    db.close()
    return {"conversation": dict(row)} if row else {"id": cid}

@app.patch("/api/conversations/{cid}")
async def rename_conversation(cid: str, req: Request, user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    body = await req.json()
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    # 游客只能操作自己的对话
    owner_cond = ""
    if u.get("username") == "__guest__":
        owner_cond = " AND owner_guest_cookie='" + user + "'"
    db.execute("UPDATE conversations SET title=?, updated_at=? WHERE id=? AND user_id=?" + owner_cond,
               (body.get("title", "新对话"), now, cid, u["id"]))
    db.commit()
    row = db.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    db.close()
    if not row:
        return JSONResponse({"error": "对话不存在或无权操作"}, status_code=404)
    return {"conversation": dict(row)}

@app.delete("/api/conversations/{cid}")
async def delete_conversation(cid: str, user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    db = get_db()
    # 游客只能删除自己的对话
    owner_cond = ""
    if u.get("username") == "__guest__":
        owner_cond = " AND owner_guest_cookie='" + user + "'"
    db.execute("UPDATE conversations SET status='deleted' WHERE id=? AND user_id=?" + owner_cond, (cid, u["id"]))
    db.commit()
    db.close()
    return {"ok": True}

@app.post("/api/conversations/{cid}/archive")
async def archive_conversation(cid: str, user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    db = get_db()
    # 游客只能操作自己的对话
    owner_cond = ""
    if u.get("username") == "__guest__":
        owner_cond = " AND owner_guest_cookie='" + user + "'"
    db.execute("UPDATE conversations SET status='archived' WHERE id=? AND user_id=?" + owner_cond, (cid, u["id"]))
    db.commit()
    row = db.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    db.close()
    if not row:
        return JSONResponse({"error": "对话不存在"}, status_code=404)
    return {"conversation": dict(row)}

@app.post("/api/conversations/{cid}/restore")
async def restore_conversation(cid: str, user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    db = get_db()
    # 游客只能操作自己的对话
    owner_cond = ""
    if u.get("username") == "__guest__":
        owner_cond = " AND owner_guest_cookie='" + user + "'"
    db.execute("UPDATE conversations SET status='active' WHERE id=? AND user_id=?" + owner_cond, (cid, u["id"]))
    db.commit()
    row = db.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    db.close()
    if not row:
        return JSONResponse({"error": "对话不存在或无权操作"}, status_code=404)
    return {"conversation": dict(row)}

@app.get("/api/conversations/{cid}/messages")
async def get_messages(cid: str, user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    db = get_db()
    # 验证对话所有权（游客只能访问自己的对话）
    conv_row = db.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    if not conv_row:
        db.close()
        return JSONResponse({"error": "对话不存在"}, status_code=404)
    conv = dict(conv_row)
    if u.get("username") == "__guest__" and conv.get("owner_guest_cookie") != user:
        db.close()
        return JSONResponse({"error": "无权访问此对话"}, status_code=403)
    rows = db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (cid,)).fetchall()
    messages = []
    for r in rows:
        msg = dict(r)
        att_rows = db.execute("SELECT * FROM attachments WHERE message_id=?", (msg["id"],)).fetchall()
        msg["attachments"] = [dict(a) for a in att_rows]
        messages.append(msg)
    db.close()
    return {"messages": messages}

@app.post("/api/conversations/{cid}/send")
async def send_message(cid: str, req: Request, user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)

    # 游客频率限制检查（20条/小时）和记录
    if u.get("username") == "__guest__":
        ip = get_client_ip(req)
        import hashlib
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()
        db_rate = get_db()
        allowed, current, remaining = check_guest_rate_limit(db_rate, ip_hash, "message", max_count=20, window_hours=1)
        if not allowed:
            db_rate.close()
            return JSONResponse({
                "error": "消息发送受限",
                "detail": "游客模式每小时最多发送 20 条消息，请稍后再试",
                "limit": 20,
                "window_hours": 1
            }, status_code=429)
        # 消息发送后记录一次
        record_guest_action(db_rate, ip_hash, "message", max_count=20, window_hours=1)
        db_rate.close()

    form = await req.form()
    text = form.get("message", "")
    
    # 游客禁止发送邮件（后端强制检查）
    if u.get("username") == "__guest__":
        text_lower = text.lower()
        email_keywords = ["发邮件", "发送邮件", "send mail", "send email", "寄邮件", "发一封邮件"]
        for kw in email_keywords:
            if kw in text_lower:
                return JSONResponse({
                    "error": "邮件发送受限",
                    "detail": "游客模式禁止使用发邮件功能，请登录后再试"
                }, status_code=403)

    task_mode = form.get("task_mode") == "1"
    file = form.get("file")
    reply_to = form.get("reply_to")

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    
    # 游客：验证对话所有权
    if u.get("username") == "__guest__":
        conv_row = db.execute("SELECT * FROM conversations WHERE id=? AND owner_guest_cookie=?", (cid, user)).fetchone()
        if not conv_row:
            db.close()
            return JSONResponse({"error": "无权访问此对话"}, status_code=403)
    
    # 处理文件（图片/音频/其他）
    multimodal_text = ""
    pending_attachment = None
    image_url = None
    task_attachment_path = None
    task_attachment_name = None
    task_attachment_kind = None
    if file:
        suffix = Path(file.filename).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        image_url = None
        if suffix in [".jpg",".jpeg",".png",".gif",".webp"]:
            # 保存图片到永久存储
            img_id = uuid.uuid4().hex[:16]
            static_dir = IMAGES_DIR
            static_dir.mkdir(exist_ok=True)
            dest_path = static_dir / f"{img_id}{suffix}"
            shutil.copy2(tmp_path, dest_path)
            image_url = f"/images/{img_id}{suffix}"
            task_attachment_path = str(dest_path)
            task_attachment_name = Path(file.filename).name
            task_attachment_kind = "image"
            # 多模态图片理解
            try:
                from multimodal_img import understand_image
                multimodal_text = understand_image(tmp_path, text or "请描述这张图片")
            except Exception as e:
                multimodal_text = f"[图片理解失败: {e}]"
            if multimodal_text and text:
                text = f"{text}\n\n[图片分析]: {multimodal_text}"
            elif multimodal_text:
                text = multimodal_text
        elif suffix in [".mp3",".wav",".m4a",".ogg",".aac"]:
            multimodal_text = transcribe_audio(tmp_path)
            if multimodal_text and text:
                text = f"{text}\n\n[语音转写]: {multimodal_text}"
            elif multimodal_text:
                text = multimodal_text
            os.unlink(tmp_path)
        else:
            # PDF/DOCX/TXT 等文件：保存到永久存储并创建附件
            file_id = uuid.uuid4().hex[:16]
            files_dir = FILES_DIR
            files_dir.mkdir(exist_ok=True)
            dest_path = files_dir / f"{file_id}{suffix}"
            shutil.copy2(tmp_path, dest_path)
            file_url = f"/files/{file_id}{suffix}"
            task_attachment_path = str(dest_path)
            task_attachment_name = Path(file.filename).name
            task_attachment_kind = "file"
            import mimetypes
            mime_type = mimetypes.guess_type(tmp_path)[0] or "application/octet-stream"
            size_bytes = Path(tmp_path).stat().st_size
            # 提取 PDF 文本内容
            pdf_text = ""
            if suffix == ".pdf":
                try:
                    import PyPDF2
                    with open(tmp_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        text_parts = []
                        for page in reader.pages[:5]:  # 只取前5页避免太长
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(page_text)
                        pdf_text = "\n".join(text_parts)
                        if pdf_text and len(pdf_text) > 50:
                            text = f"{text}\n\n[PDF 内容]:\n{pdf_text[:3000]}"
                except Exception as e:
                    logger.error(f"PDF 提取失败: {e}")
            # 创建附件记录（先不提交，等消息一起）
            att_id = "att_" + uuid.uuid4().hex[:16]
            att_record = (att_id, cid, None, Path(file.filename).name, file_url, mime_type, size_bytes, "file", now, "saved")
            # 放到消息后再插入，但这里先记录以便后面使用
            pending_attachment = att_record
            os.unlink(tmp_path)

    # 存储用户消息
    msg_id = "msg_" + uuid.uuid4().hex[:24]
    content_type = 'image' if image_url else ('mixed' if multimodal_text else 'text')
    db.execute("INSERT INTO messages(id,conversation_id,role,content,content_type,status,created_at) VALUES(?,?,?,?,?,?,?)",
               (msg_id, cid, "user", text, content_type, "done", now))
    
    # 游客频率限制记录
    if u.get("username") == "__guest__":
        ip = get_client_ip(req)
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()
        record_guest_action(db, ip_hash, "message", max_count=20, window_hours=1)
    # 存储附件（图片或其他文件）
    if image_url:
        att_id = "att_" + uuid.uuid4().hex[:16]
        db.execute("INSERT INTO attachments(id,conversation_id,message_id,file_name,stored_path,mime_type,size_bytes,kind,created_at,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (att_id, cid, msg_id, Path(file.filename).name, image_url, None, None, "image", now, "saved"))
    elif pending_attachment:
        att_id, _, _, fname, fpath, fmime, fsize, fkind, _, _ = pending_attachment
        db.execute("INSERT INTO attachments(id,conversation_id,message_id,file_name,stored_path,mime_type,size_bytes,kind,created_at,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (att_id, cid, msg_id, fname, fpath, fmime, fsize, fkind, now, "saved"))

    # 对话状态设为 processing
    db.execute("UPDATE conversations SET status='processing',updated_at=? WHERE id=?", (now, cid))

    # 处理回复
    if task_mode:
        # 创建空的助手消息占位符
        assistant_msg_id = "msg_" + uuid.uuid4().hex[:24]
        db.execute(
            "INSERT INTO messages(id,conversation_id,role,content,status,created_at) VALUES(?,?,?,?,?,?)",
            (assistant_msg_id, cid, "assistant", "任务执行中...", "done", now)
        )
        task_type = "image" if task_attachment_kind == "image" else ("file" if task_attachment_kind == "file" else "text")
        task_id = create_task(
            prompt_text=text,
            task_type=task_type,
            attachment_path=task_attachment_path,
            attachment_name=task_attachment_name,
            attachment_kind=task_attachment_kind,
            delivery_target={"conversation_id": cid},
        )
        bind_task_message(task_id, cid, assistant_msg_id)
        conv_row = db.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
        db.commit(); db.close()
        resp = {"task_id": task_id, "task_mode": True}
        if conv_row:
            resp["conversation"] = dict(conv_row)
        return resp

    # 检测图片生成指令
    img_keywords = ["生成图片", "生成图", "生成一幅", "画一幅", "画一张", "生成一张", "生成画", "给我画", "画一个", "生成一个", "画个", "画个图", "生成个图", "给我画一个", "给我生成一个", "帮我画", "帮我生成"]
    is_image_request = any(text.startswith(kw) or text.startswith("给我"+kw) for kw in img_keywords)
    image_generated_this_turn = False  # 标记本轮是否生成了图片
    if is_image_request:
        # 提取描述
        prompt_img = re.sub(r"^(生成图片|生成图|生成一幅|画一幅|画一张|生成一张|生成画|给我画|给我生成|给我)", "", text).strip()
        img_path = None
        last_error = ""
        for attempt in range(2):  # 重试一次
            try:
                img_env = os.environ.copy()
                if os.environ.get("VIVIAI_API_KEY"):
                    img_env["VIVIAI_API_KEY"] = os.environ["VIVIAI_API_KEY"]
                logger.info(f"[img] Guest generating image, attempt {attempt+1}, prompt: {prompt_img[:50]}")
                result = subprocess.run(
                    ["/root/bin/nanobanana_generate.py", prompt_img, "2K", "16:9"],
                    capture_output=True, text=True, timeout=300, env=img_env
                )
                logger.info(f"[img] Result: rc={result.returncode}, stdout_len={len(result.stdout)}, stderr={result.stderr[:100] if result.stderr else 'none'}")
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        img_data = json.loads(result.stdout.strip())
                        if img_data.get("ok") and img_data.get("output_path"):
                            img_path = img_data["output_path"]
                            break  # 成功，跳出重试循环
                    except:
                        pass
                # 详细错误信息
                err_detail = result.stderr.strip() if result.stderr else ""
                if not err_detail and result.stdout:
                    try:
                        resp_data = json.loads(result.stdout.strip())
                        if "error" in resp_data:
                            err_detail = resp_data["error"][:200]
                    except:
                        pass
                last_error = err_detail if err_detail else (result.stdout.strip()[:200] if result.stdout else "unknown error")
            except Exception as e:
                logger.error(f"[img] Exception: {e}")
                last_error = str(e)
        
        if img_path and os.path.exists(img_path):
            img_id = uuid.uuid4().hex[:16]
            static_dir = IMAGES_DIR
            static_dir.mkdir(exist_ok=True)
            ext = Path(img_path).suffix or ".png"
            dest = static_dir / f"{img_id}{ext}"
            shutil.copy2(img_path, dest)
            # 记录游客图片额度消耗
            if u.get("username") == "__guest__":
                ip = get_client_ip(req)
                ip_hash = hashlib.sha256(ip.encode()).hexdigest()
                record_guest_action(db, ip_hash, "image", max_count=3, window_hours=24)
            reply = f"[图片已生成](/images/{img_id}{ext})"
            image_generated_this_turn = True  # 标记本轮生成了图片，用于返回额度
        else:
            reply = f"[图片生成失败: {last_error[:200]}]（可能是内容被安全过滤或API临时故障，请尝试更换描述词）"
    else:
        # 普通对话：调用 Agent
        try:
            env = os.environ.copy()
            if os.environ.get("AIPAIBOX_API_KEY"):
                env["AIPAIBOX_API_KEY"] = os.environ["AIPAIBOX_API_KEY"]
            result = subprocess.run(
                ["openclaw", "agent", "--session-id", "web-"+cid, "--message", text],
                capture_output=True, text=True, timeout=120, env=env
            )
            reply = result.stdout if result.returncode == 0 else f"[错误] {result.stderr[:100]}"
        except Exception as e:
            reply = f"[错误] {e}"

    # 去掉 LaTeX 源码，并把本地 MEDIA 路径转成 Web 可访问链接
    reply = re.sub(r"附：LaTeX 源码.*", "", reply, flags=re.DOTALL).rstrip()
    reply = normalize_media_paths_for_web(reply)

    # 如果生成了图片，返回额度信息
    img_quota = None
    if u.get("username") == "__guest__" and image_generated_this_turn:
        ip = get_client_ip(req)
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()
        _, _, remaining = check_guest_rate_limit(db, ip_hash, "image", max_count=3, window_hours=24)
        img_quota = {"action": "image", "limit": 3, "remaining": max(0, remaining), "used": 3 - max(0, remaining)}

    reply_id = "msg_" + uuid.uuid4().hex[:24]
    db.execute("INSERT INTO messages(id,conversation_id,role,content,status,created_at) VALUES(?,?,?,?,?,?)",
               (reply_id, cid, "assistant", reply, "done", now))
    db.execute("UPDATE conversations SET status='active',updated_at=? WHERE id=?", (now, cid))
    db.commit()
    
    # 返回游客额度信息
    resp = {"reply_id": reply_id}
    if u.get("username") == "__guest__":
        ip = get_client_ip(req)
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()
        # 消息额度
        _, _, msg_remaining = check_guest_rate_limit(db, ip_hash, "message", max_count=20, window_hours=1)
        msg_quota = {"action": "message", "limit": 20, "remaining": max(0, msg_remaining), "used": 20 - max(0, msg_remaining)}
        # 图片额度（如果有生成）
        quotas = [msg_quota]
        if img_quota:
            quotas.append(img_quota)
        resp["quotas"] = quotas
    
    db.close()
    return resp
# ─── Tasks API ───────────────────────────────────────────────────────────────
@app.get("/api/tasks/{tid}")
async def get_task_api(tid: str, user=Header(None, alias='Authorization')):
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    db = get_db(TASKS_DB)
    row = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    db.close()
    if not row:
        return JSONResponse({"error": "Not Found"}, status_code=404)
    return {"task": dict(row), "events": []}

@app.get("/api/tasks/{tid}/artifacts")
async def task_artifacts(tid: str):
    links = find_artifact_links(tid)
    return {"ok": True, "task_id": tid, "artifacts": [{"name": os.path.basename(l), "download_url": l} for l in links]}

@app.get("/api/tasks/{tid}/download/{path:path}")
async def download_artifact(tid: str, path: str):
    file_path = ARTIFACTS_ROOT / tid / path
    if not file_path.is_file():
        return JSONResponse({"error": "Not Found"}, status_code=404)
    return FileResponse(file_path, filename=path)

# ─── ASR ─────────────────────────────────────────────────────────────────────
@app.post("/api/asr/transcribe")
async def asr_transcribe(file: UploadFile, language: str = Form("zh")):
    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    text = transcribe_audio(tmp_path, language)
    os.unlink(tmp_path)
    return {"text": text}

# ─── Guest ───────────────────────────────────────────────────────────────────
@app.post("/api/guest/start")
async def guest_start(req: Request):
    """创建游客会话，返回 token（复用同一游客的未过期会话，返回真实配额）"""
    db = get_db()
    now = datetime.now(timezone.utc)
    
    # 获取客户端 IP（用于会话复用和配额追踪）
    client_ip = get_client_ip(req)
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()
    
    # 创建游客用户（如果不存在）
    guest_row = db.execute("SELECT id FROM users WHERE username='__guest__'").fetchone()
    if not guest_row:
        guest_hash = hashlib.sha256("guest".encode()).hexdigest()
        db.execute("INSERT OR IGNORE INTO users(id, username, password_hash, is_active, created_at) VALUES(NULL,?,?,1,?)",
                   ("__guest__", guest_hash, now.isoformat()))
        db.commit()
        guest_id = db.execute("SELECT id FROM users WHERE username='__guest__'").fetchone()[0]
    else:
        guest_id = guest_row[0]
    
    # 查找该用户的未过期会话
    existing = db.execute(
        "SELECT id, expires_at FROM web_sessions WHERE user_id=? AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
        (guest_id, now.isoformat())
    ).fetchone()
    
    if existing:
        token = existing["id"]
        exp = (now + timedelta(hours=3)).isoformat()
        db.execute("UPDATE web_sessions SET expires_at=? WHERE id=?", (exp, token))
    else:
        token = secrets.token_hex(24)
        exp = (now + timedelta(hours=3)).isoformat()
        db.execute("INSERT INTO web_sessions(id, user_id, created_at, expires_at) VALUES(?,?,?,?)",
                   (token, guest_id, now.isoformat(), exp))
    
    db.commit()
    
    # 查询真实剩余配额
    _, _, msg_remaining = check_guest_rate_limit(db, ip_hash, "message", max_count=20, window_hours=1)
    _, _, img_remaining = check_guest_rate_limit(db, ip_hash, "image", max_count=3, window_hours=24)
    
    quotas = [
        {"action": "message", "limit": 20, "remaining": max(0, msg_remaining), "used": 20 - max(0, msg_remaining)},
        {"action": "image",  "limit": 3,  "remaining": max(0, img_remaining), "used": 3  - max(0, img_remaining)}
    ]
    
    db.close()
    
    return {
        "token": token,
        "user": {"id": guest_id, "name": "游客"},
        "role": "guest",
        "quotas": quotas,
        "expires_at": exp
    }

# ─── Static files ─────────────────────────────────────────────────────────────
@app.post("/api/image/generate")
async def generate_image(req: Request, user=Header(None, alias='Authorization')):
    """图像生成 API
    POST body: {"prompt": "描述", "resolution": "2K", "aspect": "16:9"}
    返回: {"image_url": "/api/image/{image_id}"}
    """
    u = get_user_from_header(user)
    if not u:
        return JSONResponse({"error": "未登录"}, status_code=401)
    
    # 游客图片限制检查（3张/天）
    if u.get("username") == "__guest__":
        ip = get_client_ip(req)
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()
        db_rate = get_db()
        allowed, current, remaining = check_guest_rate_limit(db_rate, ip_hash, "image", max_count=3, window_hours=24)
        db_rate.close()
        if not allowed:
            return JSONResponse({
                "error": "图片生成受限",
                "detail": "游客模式每天最多生成 3 张图片，请明天再试",
                "limit": 3,
                "window_hours": 24
            }, status_code=429)
    
    body = await req.json()
    prompt = body.get("prompt", "")
    resolution = body.get("resolution", "2K")
    aspect = body.get("aspect", "16:9")
    if not prompt:
        return JSONResponse({"error": "prompt 不能为空"}, status_code=400)
    
    # 调用 nanobanana 生成图片
    try:
        env = os.environ.copy()
        api_key = env.get("VIVIAI_API_KEY") or os.environ.get("VIVIAI_API_KEY")
        if api_key:
            env["VIVIAI_API_KEY"] = api_key
        if os.environ.get("AIPAIBOX_API_KEY"):
            env["AIPAIBOX_API_KEY"] = os.environ["AIPAIBOX_API_KEY"]
        result = subprocess.run(
            ["/root/bin/nanobanana_generate.py", prompt, resolution, aspect],
            capture_output=True, text=True, timeout=300, env=env
        )
        if result.returncode != 0:
            return JSONResponse({"error": f"生成失败: {result.stderr[:200]}"}, status_code=500)
        
        output = result.stdout.strip()
        # 解析输出（通常是图片路径或 base64）
        image_path = None
        if os.path.exists(output):
            image_path = output
        else:
            # 尝试解析 JSON 输出
            try:
                data = json.loads(output)
                image_path = data.get("image_path") or data.get("path") or data.get("url") or data.get("output_path")
            except:
                pass
        
        if not image_path or not os.path.exists(image_path):
            return JSONResponse({"error": f"图片生成后未找到: {output[:100]}"}, status_code=500)
        
        # 保存到 static/images 目录供下载
        img_id = uuid.uuid4().hex[:16]
        static_dir = IMAGES_DIR
        static_dir.mkdir(exist_ok=True)
        ext = Path(image_path).suffix or ".png"
        dest_path = static_dir / f"{img_id}{ext}"
        shutil.copy2(image_path, dest_path)
        
        # 游客图片限制记录
        if u.get("username") == "__guest__":
            ip = get_client_ip(req)
            ip_hash = hashlib.sha256(ip.encode()).hexdigest()
            db_rate = get_db()
            record_guest_action(db_rate, ip_hash, "image", max_count=3, window_hours=24)
            db_rate.close()
        
        return {"ok": True, "image_id": img_id, "image_url": f"/images/{img_id}{ext}"}
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "生成超时（超过5分钟）"}, status_code=504)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/image/{image_id}")
async def get_image(image_id: str):
    static_dir = IMAGES_DIR
    for f in static_dir.glob(f"{image_id}.*"):
        return FileResponse(f, filename=f.name)
    return JSONResponse({"error": "Not Found"}, status_code=404)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
