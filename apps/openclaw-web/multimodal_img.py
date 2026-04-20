"""
多模态理解 — 直接调用 MiniMax VLM API
"""
import urllib.request
import json
import base64
import os

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_URL = os.getenv("MINIMAX_VLM_URL", "https://api.minimaxi.com/v1/coding_plan/vlm")

def understand_image(image_path: str, prompt: str = "请详细描述这张图片的完整内容，包括所有文字、人物、物体、场景、数据图表等细节。") -> str:
    """理解图片内容"""
    try:
        if not MINIMAX_API_KEY:
            return "[图片理解失败: MINIMAX_API_KEY 未配置]"
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        
        data = json.dumps({
            "prompt": prompt,
            "image_url": f"data:image/jpeg;base64,{img_b64}"
        }).encode()
        
        req = urllib.request.Request(
            MINIMAX_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            content = result.get("content", "")
            if content:
                return content
            return "[图片理解未返回内容]"
            
    except Exception as e:
        return f"[图片理解失败: {e}]"
