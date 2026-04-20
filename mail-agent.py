#!/usr/bin/env python3
"""
QQ邮箱 AI 自动回复机器人
功能：Brave实时搜索、MiniMax图片理解、PDF/语音附件处理、语言自适应回复
"""

import imaplib, email, smtplib, os, json, re, requests, signal, resource, io, tempfile, base64, subprocess, threading, fcntl
from email.header import decode_header

# ========== 文件锁防止并发执行 ==========
LOCK_FILE = "/tmp/mail-agent.lock"
lock_fp = open(LOCK_FILE, 'w')
try:
    fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("[警告] 邮件代理已在运行中，退出")
    exit(0)
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# ========== 资源限制 ==========
try:
    resource.setrlimit(resource.RLIMIT_AS, (1024*1024*512, resource.RLIMIT_INFINITY))
    resource.setrlimit(resource.RLIMIT_CPU, (60, resource.RLIMIT_INFINITY))
except:
    pass

# ========== 配置 ==========
def load_local_env(env_path=None):
    env_path = env_path or os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except Exception:
        pass


load_local_env()

IMAP_SERVER     = os.getenv("MAIL_AGENT_IMAP_SERVER", "imap.qq.com")
IMAP_PORT       = int(os.getenv("MAIL_AGENT_IMAP_PORT", "993"))
SMTP_SERVER     = os.getenv("MAIL_AGENT_SMTP_SERVER", "smtp.qq.com")
SMTP_PORT       = int(os.getenv("MAIL_AGENT_SMTP_PORT", "587"))
EMAIL_ACCOUNT   = os.getenv("MAIL_AGENT_EMAIL_ACCOUNT", "")
EMAIL_AUTH_CODE = os.getenv("MAIL_AGENT_EMAIL_PASSWORD", "")

MINIMAX_API_KEY = os.getenv("MAIL_AGENT_MINIMAX_API_KEY") or os.getenv("MINIMAX_API_KEY", "")
MINIMAX_URL     = os.getenv("MAIL_AGENT_MINIMAX_URL") or os.getenv("MINIMAX_URL", "https://api.minimaxi.com/anthropic/v1/messages")
MODEL           = os.getenv("MAIL_AGENT_MODEL") or os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
MINIMAX_HOST    = os.getenv("MAIL_AGENT_MINIMAX_HOST") or os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.com")

STATE_FILE      = os.getenv("MAIL_AGENT_STATE_FILE", "/root/.openclaw/workspace/mail-state.json")
TOKEN           = os.getenv("MAIL_AGENT_TOKEN", "")
BRAVE_KEY       = os.getenv("MAIL_AGENT_BRAVE_KEY") or os.getenv("BRAVE_API_KEY", "")
NOTIFY_TARGETS  = os.getenv("MAIL_AGENT_NOTIFY_TARGETS", "")

# ========== MiniMax MCP 客户端 ==========
class MiniMaxMCP:
    """通过 stdio 调用 minimax-coding-plan-mcp"""
    def __init__(self):
        self.proc = None
        self._id = 0
        self._lock = threading.Lock()
        self._init_done = False

    def _start(self):
        if self.proc and self.proc.poll() is None:
            return
        if not MINIMAX_API_KEY:
            raise RuntimeError("MAIL_AGENT_MINIMAX_API_KEY 未配置")
        env = os.environ.copy()
        env["MINIMAX_API_KEY"] = MINIMAX_API_KEY
        env["MINIMAX_API_HOST"] = MINIMAX_HOST
        self.proc = subprocess.Popen(
            ["/root/.local/bin/uvx", "minimax-coding-plan-mcp", "-y"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
        # 初始化协议
        init_req = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "mail-agent", "version": "1.0"}}
        }) + "\n"
        self.proc.stdin.write(init_req.encode())
        self.proc.stdin.flush()
        self.proc.stdout.readline()  # consume init response
        self._init_done = True

    def _send_recv(self, req):
        with self._lock:
            self._start()
            self._id += 1
            req["id"] = self._id
            line = json.dumps(req) + "\n"
            self.proc.stdin.write(line.encode())
            self.proc.stdin.flush()
            while True:
                resp_line = self.proc.stdout.readline()
                if not resp_line:
                    return None
                resp = json.loads(resp_line.decode())
                if resp.get("id") == req["id"] or "result" in resp or "error" in resp:
                    return resp
            return None

    def call(self, tool, arguments):
        resp = self._send_recv({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": tool, "arguments": arguments}
        })
        if resp and "result" in resp:
            return resp["result"]
        return resp

    def web_search(self, query):
        """MiniMax MCP 联网搜索"""
        try:
            result = self.call("web_search", {"query": query})
            if result and "content" in result:
                for block in result["content"]:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block["text"]
                        try:
                            data = json.loads(text)
                            items = []
                            for item in data.get("organic", [])[:5]:
                                items.append(f"◆ {item.get('title','')[:80]}\n  {item.get('snippet','')[:150]}\n  {item.get('link','')}")
                            return "\n".join(items) if items else None
                        except (json.JSONDecodeError, TypeError):
                            return text[:500]
            return None
        except Exception as e:
            return None

    def understand_image(self, prompt, image_data, mime_type="image/jpeg"):
        """MiniMax MCP 图片理解"""
        try:
            b64 = base64.b64encode(image_data).decode()
            image_uri = f"data:{mime_type};base64,{b64}"
            for key in ("image_source", "image"):
                result = self.call("understand_image", {
                    "prompt": prompt,
                    key: image_uri
                })
                if result and "content" in result:
                    for block in result["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            return block["text"].strip()
            return None
        except Exception as e:
            return None

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
            except:
                pass
            self.proc = None
            self._init_done = False

# 全局 MCP 实例
_mcp_instance = None
def get_mcp():
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = MiniMaxMCP()
    return _mcp_instance

# ========== 状态 ==========
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"seen_ids": [], "last_reply": {}}

def save_state(state):
    # 原子写入：先写临时文件再 rename，避免并发写入损坏
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)

# ========== 工具 ==========
def decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            if enc and enc.lower() not in ("unknown-8bit", "x-user-defined"):
                try:
                    result.append(part.decode(enc, errors="replace"))
                except Exception:
                    result.append(part.decode("utf-8", errors="replace"))
            else:
                # Try common Chinese encodings for unknown-8bit
                for codec in ("gbk", "gb2312", "utf-8", "big5", "latin1", "cp936"):
                    try:
                        decoded = part.decode(codec, errors="strict")
                        # Verify it looks valid (has Chinese or reasonable chars)
                        if any('一' <= c <= '鿿' for c in decoded) or len(decoded) > 5:
                            result.append(decoded)
                            break
                    except Exception:
                        continue
                else:
                    # Last resort: try with replacement
                    try:
                        result.append(part.decode("utf-8", errors="replace"))
                    except Exception:
                        result.append(part.decode("latin1", errors="replace"))
        else:
            result.append(part)
    return "".join(result)

def extract_sender(msg):
    from_ = decode_str(msg.get("From", ""))
    match = re.search(r"<(.+?)>|([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", from_)
    return match.group(1) or match.group(2) or from_

def get_body(msg):
    body, attachments = "", []
    html_body = ""  # 暂存 HTML 正文，text/plain 为空时备用
    for part in msg.walk():
        ct, cd = part.get_content_type(), str(part.get("Content-Disposition", ""))
        fn = part.get_filename()
        if fn:
            attachments.append({"name": decode_str(fn), "type": ct, "part": part})
        if ct == "text/plain" and "attachment" not in cd:
            try:
                cs = part.get_content_charset() or "utf-8"
                body += part.get_payload(decode=True).decode(cs, errors="replace")
            except Exception:
                pass
        elif ct == "text/html" and "attachment" not in cd and not body:
            # text/plain 为空时，尝试从 HTML 提取纯文本
            try:
                cs = part.get_content_charset() or "utf-8"
                html_body += part.get_payload(decode=True).decode(cs, errors="replace")
            except Exception:
                pass
    # 如果没有 text/plain，用 HTML 解析提取纯文本
    if not body.strip() and html_body:
        try:
            from html.parser import HTMLParser
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text, self.skip = [], False
                def handle_starttag(self, tag, attrs):
                    if tag in ('script', 'style', 'head'): self.skip = True
                def handle_endtag(self, tag):
                    if tag in ('script', 'style', 'head'): self.skip = False
                def handle_data(self, d):
                    if not self.skip: self.text.append(d)
                def get_text(self):
                    return ' '.join(''.join(self.text).split())
            p = TextExtractor()
            p.feed(html_body)
            body = p.get_text()
        except Exception:
            body = html_body  # 解析失败则用原始 HTML
    return body.strip(), attachments

# ========== 附件处理 ==========
def extract_attachment_content(atts):
    """提取附件内容：图片用MiniMax MCP理解，其余文本/PDF/语音"""
    texts = []
    mcp = get_mcp()
    for att in atts:
        name, part, ct = att["name"], att["part"], att["type"]
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            ext = name.lower()

            # 图片 - 用 MiniMax MCP 图片理解
            if ct.startswith("image/") or ext.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic")):
                mime = ct if ct.startswith("image/") else "image/jpeg"
                # 取前3MB避免太大
                data = payload[:3*1024*1024]
                print(f"    [图片理解] {name} ({len(data)//1024}KB)")
                desc = mcp.understand_image(
                    f"详细描述这张图片的内容，包括文字、人物、物体、场景等所有细节。",
                    data, mime
                )
                if desc:
                    texts.append(f"【图片附件: {name}】\n{desc[:1000]}")
                else:
                    try:
                        from PIL import Image
                        img = Image.open(io.BytesIO(data))
                        texts.append(f"【图片附件: {name}】尺寸{img.size}，无法提取内容")
                    except:
                        texts.append(f"【图片附件: {name}】（无法分析）")

            # 文本类
            elif ct.startswith("text/") or ext.endswith((".txt", ".csv", ".md", ".json", ".xml", ".html", ".log", ".yaml", ".yml")):
                for enc in ("utf-8", "gbk", "gb2312", "big5", "latin1"):
                    try:
                        texts.append(f"【附件: {name}】\n{payload.decode(enc, errors='replace')[:3000]}")
                        break
                    except Exception:
                        continue

            # PDF - 增强：PyPDF2文字 + OCR备用 + 内嵌图片理解
            elif ext.endswith(".pdf") or ct == "application/pdf":
                pdf_file = io.BytesIO(payload)
                pdf_parts = []

                # 方法1: PyPDF2 提取文字层
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(pdf_file)
                    total_pages = len(reader.pages)
                    raw_pages = []
                    for i, page in enumerate(reader.pages[:10]):
                        t = page.extract_text()
                        if t:
                            raw_pages.append(t[:1500])
                    total_chars = sum(len(p) for p in raw_pages)
                    if raw_pages and total_chars > 80:
                        pdf_parts.append(f"（共{total_pages}页，文字层）\n" + "\n\n".join(raw_pages[:8]))
                    elif raw_pages:
                        pdf_parts.append(f"（共{total_pages}页，文字层内容较少，将进行OCR识别）\n" + "\n\n".join(raw_pages[:3]))
                    else:
                        pdf_parts.append(f"（共{total_pages}页，无可提取文字，进行OCR识别）")
                except Exception as e:
                    pdf_parts.append(f"（PDF读取异常，将尝试OCR: {e}）")

                # 方法2: pdf2image + tesseract OCR（扫描/图片型PDF）
                try:
                    from pdf2image import convert_from_bytes
                    import pytesseract
                    pdf_file.seek(0)
                    pages_img = convert_from_bytes(payload, dpi=150, first_page=1, last_page=5, fmt="png", thread_count=1)
                    ocr_lang = "chi_sim+eng"
                    ocr_pages = []
                    for img in pages_img:
                        txt = pytesseract.image_to_string(img, lang=ocr_lang, config="--psm 4")
                        if txt and txt.strip():
                            ocr_pages.append(txt.strip()[:2000])
                    if ocr_pages:
                        pdf_parts.append("[OCR识别结果]\n" + "\n\n".join(ocr_pages))
                except Exception as e:
                    if not pdf_parts:
                        pdf_parts.append(f"（OCR失败: {e}）")

                # 方法3: 提取PDF内嵌图片，用MiniMax理解
                try:
                    tmp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                    tmp_pdf.write(payload); tmp_pdf.flush(); tmp_pdf.close()
                    img_dir = tempfile.mkdtemp()
                    subprocess.run(["/usr/bin/pdfimages", "-png", "-f", "1", "-l", "3", tmp_pdf.name, img_dir + "/img"],
                                   capture_output=True, timeout=30)
                    import glob as _glob
                    for img_path in sorted(_glob.glob(img_dir + "/img-*.png"))[:3]:
                        try:
                            with open(img_path, "rb") as _f:
                                _d = _f.read()
                            if len(_d) < 5 * 1024 * 1024:
                                desc = mcp.understand_image(
                                    "详细描述这张图片的完整内容，包括所有文字、图表、数据、场景等细节。",
                                    _d, "image/png")
                                if desc:
                                    pdf_parts.append(f"[PDF内嵌图片理解]\n{desc[:800]}")
                        except:
                            pass
                        finally:
                            try: os.unlink(img_path)
                            except: pass
                    try: os.rmdir(img_dir)
                    except: pass
                    os.unlink(tmp_pdf.name)
                except Exception:
                    pass

                final = "\n".join(pdf_parts) if pdf_parts else ""
                texts.append(f"【PDF附件: {name}】\n{final[:5000]}" if final.strip() else f"【PDF附件: {name}】（无法提取内容）")

            # 语音
            elif ext.endswith((".mp3", ".wav", ".m4a", ".ogg", ".opus", ".amr", ".silk", ".aac", ".flac", ".wma")):
                try:
                    import faster_whisper
                    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                    tmp.write(payload)
                    tmp.flush()
                    tmp.close()
                    try:
                        model = faster_whisper.FasterWhisper(model_size_or_path="base", device="cpu", local_files_only=False)
                        segments, info = model.transcribe(tmp.name, beam_size=3)
                        transcript = "".join(seg.text for seg in segments if seg.text.strip())
                        if transcript.strip():
                            texts.append(f"【语音附件: {name}】（语言:{info.language if hasattr(info,'language') else 'zh'}）\n{transcript[:3000]}")
                        else:
                            texts.append(f"【语音附件: {name}】（未能识别文字）")
                    finally:
                        os.unlink(tmp.name)
                except Exception as e:
                    texts.append(f"【语音附件: {name}】（转写失败: {e}）")

            else:
                texts.append(f"【附件: {name}】（{ct}，需下载查看）")
        except Exception as e:
            texts.append(f"【附件: {name}】（处理失败: {e}）")
    return texts

# ========== 过滤器 ==========
def is_bounce(msg):
    s = decode_str(msg.get("Subject", "")).lower()
    sender = extract_sender(msg).lower()
    if any(k in s for k in ["退信","undelivered","bounce","failure","未送达","投递失败","mail delivery"]):
        return True
    if "postmaster" in sender or "mailer-daemon" in sender:
        return True
    if any(k in s for k in ["自动回复","auto-reply","out of office","已外出"]):
        return True
    return False

def is_marketing(msg):
    s = decode_str(msg.get("Subject", "")).lower()
    f = decode_str(msg.get("From", "")).lower()
    for k in ["广告","推广","促销","优惠","打折","秒杀","限时","营销","群发","newsletter","promotion","advertisement","满减","领券","优惠券","抽奖","积分","免费领取","恭喜","获奖","中奖"]:
        if k.lower() in s or k.lower() in f:
            return True
    if ("noreply" in f or "no-reply" in f) and not any(k in s for k in ["账单","订单","快递","支付","安全","验证码","登录","通知","注册","确认"]):
        return True
    return False

# ========== Brave 搜索 ==========
def brave_search(query):
    """用 Brave Search API 实时搜索，返回格式化文本"""
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 5},
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_KEY},
            timeout=15
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("web", {}).get("results", [])
        if not results:
            return None
        lines = []
        for r in results[:5]:
            title = r.get("title", "")[:80]
            snippet = r.get("description", "")[:200]
            url = r.get("url", "")[:120]
            lines.append(f"◆ {title}\n  {snippet}\n  {url}")
        return "".join(lines) if lines else None
    except Exception as e:
        print(f"    [Brave搜索失败] {e}")
        return None

# ========== 语言检测 ==========
def detect_lang(text):
    c = len(re.findall(r'[\u4e00-\u9fff]', text))
    e = len(re.findall(r'[a-zA-Z]', text))
    total = c + e
    return "zh" if total > 0 and c / total > 0.12 else "en"

# ========== AI 回复 ==========
def get_ai_reply(body, sender, subject, att_info="", realtime_info=""):
    lang = detect_lang(body + " " + subject)
    # Always use Traditional Chinese (the email was detected as Chinese)
    #简繁检测：统计中文字符（简繁通用）
    zh_chars = len(re.findall(r'[\u4e00-\u9fff]', body + subject))
    en_chars = len(re.findall(r'[a-zA-Z]', body + subject))
    
    if zh_chars >= 3:  # 有中文就用简体中文回复
        system = "你是一个专业的AI邮件助理，用简体中文回复，350字以内，只写回复正文，不加标题问候语。禁止提及自己是AI或提到搜索过程。回复必须使用简体中文（使用「信息」「数据」「货币」「关于」等简体字形）。"
        user_prompt = f"""根据以下信息回复：
{att_info}
{realtime_info}
发件人: {sender}
主题: {subject}
邮件内容:
{body[:2000]}

请用简体中文回复。"""
    else:
        system = "You are a professional AI email assistant. Reply in English only, within 200 words. Write only the reply body, no subject line or greeting. Do not mention being an AI."
        user_prompt = f"""Reply based on:
{att_info}
{realtime_info}
Sender: {sender}
Subject: {subject}
Email:
{body[:2000]}"""

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.7,
        "thinking": {"type": "budget", "budget_tokens": 0}
    }

    try:
        resp = requests.post(MINIMAX_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            parts = [b["text"].strip() for b in data.get("content", []) if b.get("type") == "text" and b["text"].strip()]
            if not parts:
                return None
            return "\n".join(parts)
        elif resp.status_code == 429:
            return None
        return f"[AI錯誤 {resp.status_code}]"
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        return f"[AI錯誤: {e}]"

# ========== 发送邮件 ==========
def send_reply(to_addr, subject, body, in_reply_to=None):
    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = to_addr
    msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    msg.attach(MIMEText(f"您好，\n\n{body}\n\n---\n本邮件为 AI 助理自动回复", "plain", "utf-8"))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as s:
            s.ehlo("mailer")
            s.starttls()
            s.login(EMAIL_ACCOUNT, EMAIL_AUTH_CODE)
            s.sendmail(EMAIL_ACCOUNT, [to_addr], msg.as_string())
        return True
    except Exception as e:
        print(f"  [SMTP錯誤] {e}")
        return False

# ========== 通知 ==========
def notify(text):
    import subprocess
    env = {**os.environ, "OPENCLAW_GATEWAY_TOKEN": TOKEN}
    results = []
    try:
        targets = json.loads(NOTIFY_TARGETS) if NOTIFY_TARGETS else []
    except Exception:
        print("    [通知配置无效] MAIL_AGENT_NOTIFY_TARGETS 需为 JSON 数组")
        return
    if not targets:
        print("    [通知跳过] 未配置 MAIL_AGENT_NOTIFY_TARGETS")
        return
    for item in targets:
        ch = item.get("channel", "")
        tgt = item.get("target", "")
        if not ch or not tgt:
            continue
        try:
            r = subprocess.run(["/usr/bin/openclaw","message","send",
                          "--channel",ch,"--target",tgt,"--message",text],
                capture_output=True, text=True, timeout=15, env=env, check=False)
            ok = r.returncode == 0 and "NO_REPLY" not in r.stdout
            results.append(f"{ch}:{'✅' if ok else '❌'}")
            if not ok:
                print(f"    [通知失败] {ch}: {r.stderr[:100] if r.stderr else r.stdout[:100]}")
        except Exception as e:
            results.append(f"{ch}:❌({e})")
    print(f"    [通知] " + " ".join(results))

# ========== 主流程 ==========
REALTIME_KEYWORDS = [
    "黃金","金價","gold","goldprice","金","比特幣","比特币","BTC","ETH","以太坊","crypto",
    "天氣","天气","weather","溫度","价格","price","行情","報價","报价","市價","市值",
    "股價","股价","stock","股市","指數","指数","匯率","汇率","exchange","美元","歐元","英鎊",
    "新聞","新闻","news","即時","实时","今日","油價","油价","原油","大宗商品","commodity",
    "今天","明日","本周","本月","預測","预测","行情","走勢","走势","漲","跌","漲幅","跌幅"
]

def needs_realtime(subject, body):
    text = (subject + " " + body[:500]).lower()
    return any(kw.lower() in text for kw in REALTIME_KEYWORDS)

def process():
    state = load_state()
    seen_ids = set(state.get("seen_ids", []))
    last_reply = state.get("last_reply", {})
    processed = set()

    cutoff = datetime.now() - timedelta(days=7)
    last_reply = {k: v for k, v in last_reply.items()
                  if datetime.fromisoformat(v) > cutoff}

    mcp = get_mcp()
    new_count = 0

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ACCOUNT, EMAIL_AUTH_CODE)
        mail.select("INBOX")
        _, msgs = mail.search(None, "UNSEEN")
        ids = msgs[0].split()

        for mid in ids:
            mid_str = mid.decode()
            if mid_str in seen_ids or mid_str in processed:
                continue

            _, data = mail.fetch(mid, "(RFC822)")
            if not data or not data[0]:
                continue

            msg = email.message_from_bytes(data[0][1])
            subject = decode_str(msg.get("Subject", "(无主题)"))
            sender  = extract_sender(msg)
            body, atts = get_body(msg)
            msg_id = msg.get("Message-ID", "")
            processed.add(mid_str)

            if is_bounce(msg):
                print(f"  [退信] {subject[:40]} <- {sender}")
                try: mail.store(mid, "+FLAGS", "\\Seen")
                except: pass
                seen_ids.add(mid_str); continue

            if is_marketing(msg):
                print(f"  [过滤] {subject[:40]} (营销)")
                try: mail.store(mid, "+FLAGS", "\\Seen")
                except: pass
                seen_ids.add(mid_str); continue

            last = last_reply.get(sender)
            if last and (datetime.now() - datetime.fromisoformat(last)).seconds < 300:
                print(f"  [跳过] {sender} 5分钟内已回复")
                seen_ids.add(mid_str); continue

            print(f"  [处理] {subject[:40]} <- {sender}")

            # 提取附件内容（包括图片理解）
            att_texts = extract_attachment_content(atts)
            att_info = "\n".join(att_texts) if att_texts else "无附件"

            # 实时搜索 - 用 Brave（轻量快速）
            realtime_info = ""
            if needs_realtime(subject, body):
                kws = [kw for kw in REALTIME_KEYWORDS if kw.lower() in (subject+" "+body[:500]).lower()]
                if kws:
                    q = " ".join(kws[:4])
                    print(f"    [Brave搜索] {q}")
                    r = brave_search(q)
                    if r:
                        realtime_info = r
                        print(f"    [Brave搜索] 完成")

            # AI 回复（失败也加入seen_ids避免同一邮件被重复处理）
            ai_reply = get_ai_reply(body, sender, subject, att_info=att_info, realtime_info=realtime_info)
            if ai_reply is None:
                print(f"    [跳过] AI回复无效（速率限制或超时），已标记避免重复处理")
                seen_ids.add(mid_str); continue
            if ai_reply.startswith("[AI"):
                print(f"    [错误] {ai_reply}")
                seen_ids.add(mid_str); continue

            # 发送
            ok = send_reply(sender, subject, ai_reply, in_reply_to=msg_id)
            if ok:
                print(f"    [已回] {ai_reply[:60]}...")
                last_reply[sender] = datetime.now().isoformat()
                new_count += 1
                att_s = att_texts[0][:100] if att_texts else "无附件"
                notify(f"📧 AI 已自动回复\n发件人: {sender}\n主题: {subject}\n附件: {att_s}\n🤖 回复:\n{ai_reply[:200]}")
                # 回复成功后标记邮件为已读
                try:
                    mail.store(mid, "+FLAGS", "\\Seen")
                except Exception as e:
                    print(f"    [标已读失败] {e}")
            else:
                print(f"    [发送失败]")
                # 发送失败也标记，避免无限重试
                seen_ids.add(mid_str); continue

            seen_ids.add(mid_str)

        mail.logout()
    except Exception as e:
        print(f"[错误] {e}")
        import traceback; traceback.print_exc()

    state["seen_ids"] = list(seen_ids)[-200:]
    state["last_reply"] = last_reply
    save_state(state)

    # 主动关闭 MCP 子进程，避免累积泄漏
    try:
        get_mcp().close()
    except Exception as e:
        print(f"  [MCP清理] {e}")

    return new_count

def cleanup():
    try:
        get_mcp().close()
    except:
        pass

import atexit
atexit.register(cleanup)

if __name__ == "__main__":
    # 捕获 SIGTERM/SIGINT，确保退出时清理 MCP
    def sig_handler(sig, frame):
        cleanup()
        exit(0)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] === 邮件检查 ===")
    n = process()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 完成{f' ({n}封新回复)' if n else ''}")
    cleanup()
