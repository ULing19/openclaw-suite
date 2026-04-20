#!/usr/bin/env python3
"""
跨平台多媒体 AI 处理中心
功能：图片理解 · 文件识别(OCR/PDF/Office) · 语音转写 · 自然语言文件修改
支持：QQ · 微信 · Telegram · 飞书 所有传入的多媒体消息处理
"""

import imaplib, email, smtplib, os, json, re, requests, signal, resource, io, tempfile, base64, subprocess, threading, sys, glob, shutil
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

# ========== 资源限制 ==========
try:
    resource.setrlimit(resource.RLIMIT_AS, (1024*1024*512, resource.RLIMIT_INFINITY))
    resource.setrlimit(resource.RLIMIT_CPU, (120, resource.RLIMIT_INFINITY))
except:
    pass

# ========== 本地环境变量 ==========
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

# ========== MiniMax API ==========
MINIMAX_API_KEY = os.getenv("MULTIMODAL_MINIMAX_API_KEY") or os.getenv("MAIL_AGENT_MINIMAX_API_KEY") or os.getenv("MINIMAX_API_KEY", "")
MINIMAX_URL     = os.getenv("MULTIMODAL_MINIMAX_URL") or os.getenv("MAIL_AGENT_MINIMAX_URL") or os.getenv("MINIMAX_URL", "https://api.minimaxi.com/anthropic/v1/messages")
MODEL           = os.getenv("MULTIMODAL_MODEL") or os.getenv("MAIL_AGENT_MODEL") or os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
MINIMAX_HOST    = os.getenv("MULTIMODAL_MINIMAX_HOST") or os.getenv("MAIL_AGENT_MINIMAX_HOST") or os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.com")

# ========== MiniMax MCP ==========
class MiniMaxMCP:
    def __init__(self):
        self.proc = None
        self._id = 0
        self._lock = threading.Lock()
        self._init_done = False

    def _start(self):
        if self.proc and self.proc.poll() is None:
            return
        if not MINIMAX_API_KEY:
            raise RuntimeError("MINIMAX_API_KEY 未配置")
        env = os.environ.copy()
        env["MINIMAX_API_KEY"] = MINIMAX_API_KEY
        env["MINIMAX_API_HOST"] = MINIMAX_HOST
        self.proc = subprocess.Popen(
            ["/root/.local/bin/uvx", "minimax-coding-plan-mcp", "-y"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
        init_req = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "multimodal-agent", "version": "1.0"}}
        }) + "\n"
        self.proc.stdin.write(init_req.encode())
        self.proc.stdin.flush()
        self.proc.stdout.readline()
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

    def understand_image(self, prompt, image_data, mime_type="image/jpeg"):
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

_mcp = None
def get_mcp():
    global _mcp
    if _mcp is None:
        _mcp = MiniMaxMCP()
    return _mcp

# ========== 工具函数 ==========
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
                for codec in ("gbk", "gb2312", "utf-8", "big5", "latin1", "cp936"):
                    try:
                        decoded = part.decode(codec, errors="strict")
                        if any('\u4e00' <= c <= '\u9fff' for c in decoded) or len(decoded) > 5:
                            result.append(decoded)
                            break
                    except Exception:
                        continue
                else:
                    try:
                        result.append(part.decode("utf-8", errors="replace"))
                    except Exception:
                        result.append(part.decode("latin1", errors="replace"))
        else:
            result.append(part)
    return "".join(result)

# ========== 图片理解 ==========
def process_image(file_path, prompt=None):
    """理解图片内容，支持中文描述"""
    mcp = get_mcp()
    prompt = prompt or "详细描述这张图片的完整内容，包括所有文字、人物、物体、场景、数据图表等细节。"
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        # 限制8MB
        data = data[:8*1024*1024]
        mime = "image/jpeg"
        if file_path.lower().endswith(".png"):
            mime = "image/png"
        elif file_path.lower().endswith(".gif"):
            mime = "image/gif"
        elif file_path.lower().endswith(".webp"):
            mime = "image/webp"

        desc = mcp.understand_image(prompt, data, mime)
        return desc if desc else "[图片理解失败]"
    except Exception as e:
        return f"[图片理解错误: {e}]"

# ========== 语音转写 ==========
def process_voice(file_path):
    """用 faster-whisper 转写语音"""
    import faster_whisper
    ext = os.path.splitext(file_path)[1].lower()
    supported = (".mp3", ".wav", ".m4a", ".ogg", ".opus", ".amr", ".silk", ".aac", ".flac", ".wma")
    if ext not in supported:
        return f"[不支持的音频格式: {ext}]"

    # 模型本地路径（跳过 huggingface 缓存验证）
    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    snapshot_dir = os.path.join(cache_dir, "hub", "models--Systran--faster-whisper-base", "snapshots")
    cached_model_path = None
    if os.path.isdir(snapshot_dir):
        snapshots = os.listdir(snapshot_dir)
        if snapshots:
            cached_model_path = os.path.join(snapshot_dir, snapshots[0])

    try:
        # 复制到临时文件避免权限问题
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        shutil.copy(file_path, tmp.name)
        tmp.close()

        if cached_model_path:
            # 已缓存，直接用本地路径加载
            model = faster_whisper.WhisperModel(
                model_size_or_path=cached_model_path,
                device="cpu",
                local_files_only=True
            )
        else:
            # 未缓存，尝试联网下载
            model = faster_whisper.WhisperModel(
                model_size_or_path="base",
                device="cpu",
                local_files_only=False
            )

        segments, info = model.transcribe(tmp.name, beam_size=3)
        transcript = "".join(seg.text for seg in segments if seg.text.strip())
        os.unlink(tmp.name)

        if transcript.strip():
            lang = info.language if hasattr(info, "language") else "未知"
            return f"【语音转写】语言: {lang}\n{transcript[:3000]}"
        else:
            return "【语音转写】未能识别出文字"
    except Exception as e:
        return f"【语音转写失败: {e}]"

# ========== PDF 处理（增强OCR） ==========
def process_pdf(file_path):
    """处理 PDF：文字层 + OCR + 内嵌图片"""
    mcp = get_mcp()
    parts = []

    with open(file_path, "rb") as f:
        payload = f.read()

    pdf_file = io.BytesIO(payload)

    # 方法1: PyPDF2 提取文字
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_file)
        total = len(reader.pages)
        raw_pages = []
        for page in reader.pages[:10]:
            t = page.extract_text()
            if t:
                raw_pages.append(t[:1500])
        total_chars = sum(len(p) for p in raw_pages)
        if raw_pages and total_chars > 80:
            parts.append(f"【PDF文字层】（共{total}页）\n" + "\n\n".join(raw_pages[:8]))
        elif raw_pages:
            parts.append(f"【PDF文字层较少】（共{total}页，将OCR）\n" + "\n\n".join(raw_pages[:3]))
        else:
            parts.append(f"【PDF无文字层】（共{total}页，进行OCR）")
    except Exception as e:
        parts.append(f"【PDF读取异常: {e}】，将尝试OCR")

    # 方法2: OCR
    try:
        pdf_file.seek(0)
        pages_img = convert_from_bytes(payload, dpi=150, first_page=1, last_page=5, fmt="png", thread_count=1)
        ocr_pages = []
        for img in pages_img:
            txt = pytesseract.image_to_string(img, lang="chi_sim+eng", config="--psm 4")
            if txt and txt.strip():
                ocr_pages.append(txt.strip()[:2000])
        if ocr_pages:
            parts.append("[OCR识别结果]\n" + "\n\n".join(ocr_pages))
    except Exception as e:
        if not parts:
            parts.append(f"[OCR失败: {e}]")

    # 方法3: 提取内嵌图片理解
    try:
        img_dir = tempfile.mkdtemp()
        res = subprocess.run(
            ["/usr/bin/pdfimages", "-png", "-f", "1", "-l", "3", file_path, img_dir + "/img"],
            capture_output=True, timeout=30
        )
        for img_path in sorted(glob.glob(img_dir + "/img-*.png"))[:3]:
            try:
                with open(img_path, "rb") as f:
                    d = f.read()
                if len(d) < 5*1024*1024:
                    desc = mcp.understand_image(
                        "详细描述这张图片的完整内容，包括所有文字、图表、数据、场景等细节。",
                        d, "image/png"
                    )
                    if desc:
                        parts.append(f"[PDF内嵌图片理解]\n{desc[:800]}")
            except:
                pass
            finally:
                try: os.unlink(img_path)
                except: pass
        try: os.rmdir(img_dir)
        except: pass
    except:
        pass

    return "\n".join(parts) if parts else "[PDF处理失败]"

# ========== 通用文件处理 ==========
def process_file(file_path):
    """处理各类文件，返回内容描述"""
    ext = os.path.splitext(file_path)[1].lower()
    name = os.path.basename(file_path)
    size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    # 图片
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".tiff"):
        return process_image(file_path)

    # 音频/语音
    if ext in (".mp3", ".wav", ".m4a", ".ogg", ".opus", ".amr", ".silk", ".aac", ".flac", ".wma"):
        return process_voice(file_path)

    # PDF
    if ext == ".pdf" or ext == "":
        if ext == "" and "pdf" not in name.lower():
            return f"[不支持的文件类型: {name}]"
        return process_pdf(file_path)

    # 文本类
    if ext in (".txt", ".csv", ".md", ".json", ".xml", ".html", ".htm", ".log", ".yaml", ".yml", ".py", ".js", ".ts", ".c", ".cpp", ".h", ".sh", ".bat"):
        for enc in ("utf-8", "gbk", "gb2312", "big5", "latin1"):
            try:
                with open(file_path, "r", encoding=enc, errors="replace") as f:
                    content = f.read()[:5000]
                return f"【文件: {name}】（{size}字节）\n{content}"
            except:
                continue
        return f"[文件 {name} 无法读取（编码问题）]"

    # Word / Excel / PPT (docx/xlsx/pptx 用 unzip + xml 解析)
    if ext in (".docx", ".xlsx", ".pptx"):
        return process_office_xml(file_path, ext)

    # 压缩包
    if ext in (".zip", ".rar", ".7z", ".tar", ".gz"):
        return process_archive(file_path)

    return f"【文件: {name}】（{size}字节，{ext}格式暂不支持预览）"

def process_office_xml(file_path, ext):
    """处理 Office Open XML 格式（docx/xlsx/pptx）"""
    import zipfile
    parts = []
    name = os.path.basename(file_path)

    try:
        with zipfile.ZipFile(file_path, "r") as z:
            if ext == ".docx":
                # 提取 word/document.xml
                for fname in z.namelist():
                    if "word/document" in fname and fname.endswith(".xml"):
                        content = z.read(fname).decode("utf-8", errors="replace")
                        # 去除XML标签，保留文本
                        text = re.sub(r"<[^>]+>", " ", content)
                        text = re.sub(r"\s+", " ", text).strip()
                        parts.append(f"【Word文档: {name}】\n{text[:5000]}")
                        break
            elif ext == ".xlsx":
                # 提取 xl/sharedStrings.xml 和 sheet1.xml
                for fname in z.namelist():
                    if "xl/sharedStrings" in fname and fname.endswith(".xml"):
                        content = z.read(fname).decode("utf-8", errors="replace")
                        text = re.sub(r"<[^>]+>", " ", content)
                        text = re.sub(r"\s+", " ", text).strip()
                        parts.append(f"【Excel文件: {name}】\n{text[:3000]}")
                        break
            elif ext == ".pptx":
                for fname in z.namelist():
                    if "ppt/slides/slide" in fname and fname.endswith(".xml"):
                        content = z.read(fname).decode("utf-8", errors="replace")
                        text = re.sub(r"<[^>]+>", " ", content)
                        text = re.sub(r"\s+", " ", text).strip()
                        parts.append(f"【PPT文件: {name}】\n{text[:3000]}")
                        break
    except Exception as e:
        return f"[Office文件读取失败: {e}]"

    return "\n".join(parts) if parts else f"【{name}】（无内容可提取）"

def process_archive(file_path):
    """列出压缩包内容"""
    import zipfile
    name = os.path.basename(file_path)
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            items = [f"{i.filename} ({i.file_size}字节)" for i in z.infolist()[:20]]
        return f"【压缩包: {name}】（共{len(items)}项）\n" + "\n".join(items)
    except Exception as e:
        return f"[压缩包读取失败: {e}]"

# ========== 文件修改（自然语言） ==========
def modify_file(file_path, instruction, original_content):
    """
    用 AI 理解修改指令，对文件内容进行修改
    支持：文本文件、Word(docx)、Python代码 等
    返回修改后的内容（bytes）或原内容
    """
    lang = "zh" if any('\u4e00' <= c for c in instruction) else "en"

    if lang == "zh":
        system = f"""你是一个专业的文件编辑助手。用户要求修改一个文件，你的任务是：
1. 理解原文件内容和修改指令
2. 直接输出修改后的完整文件内容（不要解释，不要加标题，原文件是什么格式就输出什么格式）
3. 对于代码/文本文件：输出纯文本内容
4. 对于 Word(docx)：用相同格式输出修改后的文本（其他部分保持原样）
5. 严格遵循用户的修改要求，只输出文件内容本身，不要有额外说明"""

        user_prompt = f"""原始文件内容：
---
{original_content[:8000]}
---

修改指令：{instruction}

请直接输出修改后的文件内容："""
    else:
        system = "You are a file editing assistant. Output ONLY the modified file content, no explanations."

        user_prompt = f"""Original file content:
---
{original_content[:8000]}
---

Modification request: {instruction}

Output the modified file content only:"""

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
        "max_tokens": 2000,
        "temperature": 0.3
    }

    try:
        if not MINIMAX_API_KEY:
            return "[修改失败: MINIMAX_API_KEY 未配置]"
        resp = requests.post(MINIMAX_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            parts = [b["text"].strip() for b in data.get("content", []) if b.get("type") == "text" and b["text"].strip()]
            if parts:
                return "\n".join(parts)
    except Exception as e:
        return f"[修改失败: {e}]"

    return None

# ========== CLI 入口 ==========
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "image":
        # python3 multimodal-agent.py image <file_path> [prompt]
        result = process_image(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        print(result)

    elif cmd == "voice":
        # python3 multimodal-agent.py voice <file_path>
        result = process_voice(sys.argv[2])
        print(result)

    elif cmd == "file":
        # python3 multimodal-agent.py file <file_path>
        result = process_file(sys.argv[2])
        print(result)

    elif cmd == "modify":
        # python3 multimodal-agent.py modify <file_path> <instruction>
        # 先获取原文件内容
        file_path = sys.argv[2]
        instruction = sys.argv[3] if len(sys.argv) > 3 else ""
        ext = os.path.splitext(file_path)[1].lower()

        # 获取原始内容
        if ext in (".txt", ".md", ".py", ".js", ".csv", ".json", ".xml", ".html", ".yaml", ".yml", ".sh"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    original = f.read()
            except:
                with open(file_path, "r", encoding="gbk", errors="replace") as f:
                    original = f.read()
        elif ext == ".pdf":
            original = process_pdf(file_path)
        else:
            original = process_file(file_path)

        modified = modify_file(file_path, instruction, original)
        if modified:
            # 写回文件
            out_path = file_path + ".modified.txt"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(modified)
            print(f"[OK] 修改内容已保存到: {out_path}")
            print("---")
            print(modified[:500])
        else:
            print("[ERROR] 修改失败")

    elif cmd == "transcribe":
        # python3 multimodal-agent.py transcribe <file_path> [instruction]
        # 类似 voice，但支持额外说明
        result = process_voice(sys.argv[2])
        print(result)

    else:
        print("""multimodal-agent.py - 跨平台多媒体处理中心

用法:
  python3 multimodal-agent.py image <图片路径> [prompt]    # 图片理解
  python3 multimodal-agent.py voice <音频路径>            # 语音转写
  python3 multimodal-agent.py file  <文件路径>           # 文件内容提取
  python3 multimodal-agent.py modify <文件路径> <修改指令> # 自然语言修改文件

示例:
  python3 multimodal-agent.py image /tmp/photo.jpg
  python3 multimodal-agent.py voice /tmp/voice.mp3
  python3 multimodal-agent.py file /tmp/document.pdf
  python3 multimodal-agent.py modify /tmp/notes.txt "把标题改成每日报告"
""")
