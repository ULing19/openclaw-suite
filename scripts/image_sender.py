#!/usr/bin/env python3
"""
多渠道图片发送工具 v2
用法: python3 image_sender.py <image_path> <channel> <target> [caption]

channel: telegram | feishu | qq | weixin | webchat | auto
target:  渠道对应的目标ID
  - telegram: 用户ID (数字字符串)
  - feishu: open_id (ou_xxx)
  - qq: 子频道ID 或 user_id
  - weixin: wxid
  - webchat/auto: 忽略此参数

示例:
  python3 image_sender.py /root/nanobanana_outputs/xxx.jpg telegram <telegram_user_id>
  python3 image_sender.py /root/nanobanana_outputs/xxx.jpg feishu <feishu_open_id>
  python3 image_sender.py /root/nanobanana_outputs/xxx.jpg qq <channel_or_user_id>
  python3 image_sender.py /root/nanobanana_outputs/xxx.jpg weixin wxid_xxxxx
  python3 image_sender.py /root/nanobanana_outputs/xxx.jpg auto          # 从当前会话推断

对于 webchat，image_generate 工具会自动交付图片，无需调用此脚本。
此脚本主要用于 telegram / feishu / qq / weixin 等外部渠道。
"""
import sys
import os
import json
import subprocess
import tempfile
import urllib.request
import urllib.error
import re

OPENCLAW_CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")

# ============================================================================
# 工具函数
# ============================================================================

def get_gateway_token():
    try:
        with open(OPENCLAW_CONFIG_PATH) as f:
            content = f.read()
        m = re.search(r'"token"\s*:\s*"([^"]+)"', content)
        if m:
            return m.group(1)
    except:
        pass
    return os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")


def get_feishu_token():
    """获取 Feishu tenant access token"""
    try:
        with open(OPENCLAW_CONFIG_PATH) as f:
            content = f.read()
        
        # 在整个配置文件中搜索 feishu credentials
        # 尝试 personal 和 enterprise 两个账号
        personal_m = re.search(
            r'"personal"\s*:\s*\{[^}]*?"appId"\s*:\s*"([^"]+)"[^}]*?"appSecret"\s*:\s*"([^"]+)"',
            content, re.DOTALL
        )
        enterprise_m = re.search(
            r'"enterprise"\s*:\s*\{[^}]*?"appId"\s*:\s*"([^"]+)"[^}]*?"appSecret"\s*:\s*"([^"]+)"',
            content, re.DOTALL
        )
        
        credentials_to_try = []
        # 优先 enterprise，然后 personal（发送失败时用于重试）
        if enterprise_m:
            credentials_to_try.append((enterprise_m.group(1), enterprise_m.group(2)))
        if personal_m:
            credentials_to_try.append((personal_m.group(1), personal_m.group(2)))
        
        for app_id, app_secret in credentials_to_try:
            resp = subprocess.run(
                ["curl", "-s", "-X", "POST",
                 "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps({"app_id": app_id, "app_secret": app_secret})],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(resp.stdout.strip())
            if data.get("code") == 0:
                return data.get("tenant_access_token")
    except Exception as e:
        print(f"获取Feishu token失败: {e}", file=sys.stderr)
    return None


def get_qqbot_token():
    """获取 QQBot API token (通过 openclaw channels resolve)"""
    try:
        result = subprocess.run(
            ["openclaw", "channels", "resolve", "--channel", "qqbot", "--help"],
            capture_output=True, text=True, timeout=10
        )
        # QQBot 的 token 由插件内部管理，我们通过 API 代理访问
        # 需要先获取 access_token
        return None  # 暂不支持，留空
    except:
        return None


# ============================================================================
# Telegram 发送 (使用 openclaw CLI)
# ============================================================================

MEDIA_OUTBOUND = os.path.expanduser("~/.openclaw/media/outbound")

def _copy_to_outbound(image_path):
    """复制图片到 outbound 目录（Telegram 必须从允许的目录读取本地图片）"""
    os.makedirs(MEDIA_OUTBOUND, exist_ok=True)
    filename = f"img_{os.path.basename(image_path)}"
    dest = os.path.join(MEDIA_OUTBOUND, filename)
    import shutil
    shutil.copy2(image_path, dest)
    return dest


def send_telegram(image_path, target, caption=""):
    """通过 openclaw message send --media 发送图片到 Telegram"""
    # Telegram 要求本地图片在允许的目录，先复制到 outbound
    local_path = _copy_to_outbound(image_path)
    
    cmd = [
        "openclaw", "message", "send",
        "--channel", "telegram",
        "--target", target,
        "--media", local_path,
        "--json"
    ]
    if caption:
        cmd += ["--message", caption]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "OPENCLAW_STATE_DIR": os.path.expanduser("~/.openclaw")}
        )
        combined = result.stdout + result.stderr
        try:
            return {"ok": True, "result": json.loads(combined), "raw": combined}
        except:
            return {"ok": result.returncode == 0, "output": combined, "returncode": result.returncode}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        # 清理临时文件
        try:
            if local_path != image_path:
                os.remove(local_path)
        except:
            pass


# ============================================================================
# Feishu 发送 (直接调用 Feishu API)
# ============================================================================

def send_feishu(image_path, target_open_id, caption=""):
    """
    通过 Feishu API 上传图片并发送
    target_open_id: 用户的 open_id
    支持跨应用重试：如果企业版 token 发送失败（cross-app），自动尝试个人版 token
    """
    # 获取所有可用 credentials
    try:
        with open(OPENCLAW_CONFIG_PATH) as f:
            content = f.read()
        
        enterprise_m = re.search(
            r'"enterprise"\s*:\s*\{[^}]*?"appId"\s*:\s*"([^"]+)"[^}]*?"appSecret"\s*:\s*"([^"]+)"',
            content, re.DOTALL
        )
        personal_m = re.search(
            r'"personal"\s*:\s*\{[^}]*?"appId"\s*:\s*"([^"]+)"[^}]*?"appSecret"\s*:\s*"([^"]+)"',
            content, re.DOTALL
        )
        
        credentials = []
        if enterprise_m:
            credentials.append((enterprise_m.group(1), enterprise_m.group(2)))
        if personal_m:
            credentials.append((personal_m.group(1), personal_m.group(2)))
    except Exception as e:
        return {"ok": False, "error": f"读取配置失败: {e}"}
    
    if not credentials:
        return {"ok": False, "error": "无法获取 Feishu token"}

    # Step 2: 上传图片到 Feishu（使用第一个 token）
    filename = os.path.basename(image_path)
    with open(image_path, "rb") as f:
        image_data = f.read()

    import email.mime.multipart
    import email.mime.base
    
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body = f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="image_type"\r\n\r\n'
    body += "message\r\n"
    body += f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
    body += "Content-Type: application/octet-stream\r\n\r\n"
    encoded = body.encode() + image_data + f"\r\n--{boundary}--\r\n".encode()

    last_error = None
    
    for app_id, app_secret in credentials:
        # 获取 token
        resp = subprocess.run(
            ["curl", "-s", "-X", "POST",
             "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"app_id": app_id, "app_secret": app_secret})],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(resp.stdout.strip())
        if data.get("code") != 0:
            continue
        token = data.get("tenant_access_token")
        
        # 上传图片
        try:
            req = urllib.request.Request(
                "https://open.feishu.cn/open-apis/im/v1/images",
                data=encoded,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                upload_result = json.loads(resp.read())
        except Exception as e:
            last_error = f"图片上传失败: {e}"
            continue
        
        if upload_result.get("code") != 0:
            last_error = f"上传失败: {upload_result}"
            continue
        
        image_key = upload_result.get("data", {}).get("image_key")
        if not image_key:
            last_error = "无 image_key"
            continue
        
        # 发送图片消息
        msg_payload = {
            "receive_id": target_open_id,
            "msg_type": "image",
            "content": json.dumps({"image_key": image_key})
        }
        
        try:
            req2 = urllib.request.Request(
                f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
                data=json.dumps(msg_payload).encode(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with urllib.request.urlopen(req2, timeout=30) as resp:
                send_result = json.loads(resp.read())
            
            if send_result.get("code") == 0:
                return {"ok": True, "image_key": image_key, "message_id": send_result.get("data", {}).get("message_id")}
            
            # 检查是否是 cross-app 错误，决定是否重试
            err_code = send_result.get("code", 0)
            if err_code == 99992361:  # open_id cross app
                last_error = f"cross-app error with app {app_id}, retrying..."
                continue  # 尝试下一个 credential
            else:
                last_error = f"发送失败: {send_result}"
                break
        except urllib.error.HTTPError as e:
            body_str = e.read().decode()
            try:
                err_data = json.loads(body_str)
                if err_data.get("code") == 99992361:
                    last_error = f"cross-app error with app {app_id}, retrying..."
                    continue
            except:
                pass
            last_error = f"HTTP {e.code}: {body_str}"
            break
        except Exception as e:
            last_error = f"消息发送失败: {e}"
            break
    
    return {"ok": False, "error": last_error or "发送失败"}


# ============================================================================
# QQ 发送 (通过 qqbot_channel_api 代理)
# ============================================================================

def send_qq_image(image_path, target_id, caption=""):
    """
    QQ 频道发送图片
    由于 qqbot 使用 <qqimg> 标签发送图片，我们需要：
    1. 将图片复制到 /tmp/ 目录（qqbot 可以读取）
    2. 压缩图片（如果太大，qqbot 会栈溢出）
    3. 返回路径，让 agent 用 <qqimg> 标签发送
    """
    import shutil
    
    # 创建 qqbot 可访问的目录
    qq_tmp = "/tmp/qqbot_images"
    os.makedirs(qq_tmp, exist_ok=True)
    
    # 生成唯一文件名
    filename = f"qq_img_{os.path.basename(image_path)}"
    dest_path = os.path.join(qq_tmp, filename)
    
    # 复制图片
    shutil.copy2(image_path, dest_path)
    
    # 检查文件大小，如果超过 1MB 则压缩
    file_size = os.path.getsize(dest_path)
    max_size = 1 * 1024 * 1024  # 1MB
    
    if file_size > max_size:
        try:
            from PIL import Image
            img = Image.open(dest_path)
            # 缩放到最大 1920x1080
            img.thumbnail((1920, 1080), Image.LANCZOS)
            # 保存为压缩版本
            compressed_path = dest_path.replace('.jpg', '_compressed.jpg')
            img.save(compressed_path, 'JPEG', quality=85, optimize=True)
            dest_path = compressed_path
            print(f"[qqbot] Compressed image: {file_size/1024/1024:.2f}MB -> {os.path.getsize(dest_path)/1024/1024:.2f}MB", file=sys.stderr)
        except Exception as e:
            print(f"[qqbot] Compression failed: {e}", file=sys.stderr)
    
    # 确保可读
    os.chmod(dest_path, 0o644)
    
    return {
        "ok": True,
        "method": "tag",
        "path": dest_path,
        "message": f"请在 QQ 中发送: <qqimg>{dest_path}</qqimg>",
        "hint": f"图片已准备好，文件大小: {os.path.getsize(dest_path)/1024:.1f}KB"
    }


# ============================================================================
# WeChat 发送 (通过 openclaw-weixin 插件)
# ============================================================================

def send_weixin(image_path, target_wxid, caption=""):
    """
    微信发送图片 - 通过 OpenClaw 内部机制
    openclaw-weixin 插件处理 media，上层通过 message tool 发送
    由于我们无法直接调用 message tool，这里返回提示让 agent 处理
    """
    return {
        "ok": False,
        "error": "WeChat 图片发送需要通过 Agent 的 message 工具",
        "hint": "请在 WeChat 对话中由 Agent 调用 message(action=send, channel=openclaw-weixin, to=target, media=image_path)",
        "image_path": image_path,
        "target": target_wxid
    }


# ============================================================================
# Webchat (直接返回，image_generate 会自动处理)
# ============================================================================

def handle_webchat(image_path):
    return {
        "ok": True,
        "message": "Webchat 图片由 image_generate 工具自动交付，无需额外操作",
        "image_path": image_path
    }


# ============================================================================
# 主分发逻辑
# ============================================================================

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "参数不足", "usage": __doc__}, ensure_ascii=False))
        sys.exit(1)
    
    image_path = sys.argv[1].strip()
    channel = sys.argv[2].strip().lower()
    target = sys.argv[3].strip() if len(sys.argv) > 3 else ""
    caption = sys.argv[4].strip() if len(sys.argv) > 4 else ""
    
    if not os.path.exists(image_path):
        print(json.dumps({"error": f"图片不存在: {image_path}"}))
        sys.exit(1)
    
    print(f"[image_sender] channel={channel}, target={target}, image={image_path}", file=sys.stderr)
    
    if channel == "telegram":
        result = send_telegram(image_path, target, caption)
    elif channel == "feishu":
        result = send_feishu(image_path, target, caption)
    elif channel == "qq":
        result = send_qq_image(image_path, target, caption)
    elif channel == "weixin":
        result = send_weixin(image_path, target, caption)
    elif channel == "webchat" or channel == "auto":
        result = handle_webchat(image_path)
    else:
        print(json.dumps({"error": f"不支持的渠道: {channel}"}))
        sys.exit(1)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
