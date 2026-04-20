"""
Task Mode — 检测消息是否需要后台任务模式
resolve_task_mode(message, explicit_flag)
"""


TASK_KEYWORDS = [
    "/task", "/background", "/async",
    "后台运行", "异步执行", "后台执行",
    "帮我完成", "帮我做", "帮我处理",
]


def resolve_task_mode(message: str = "", explicit_flag: bool = False) -> tuple[bool, str]:
    """
    返回 (should_use_task_mode, cleaned_message)
    explicit_flag=True 时强制任务模式
    """
    text = (message or "").strip()

    # 强制任务模式
    if explicit_flag:
        cleaned = _strip_prefix(text)
        return True, cleaned

    # 前缀触发
    for kw in TASK_KEYWORDS:
        if text.startswith(kw):
            cleaned = text[len(kw):].strip()
            # 去掉开头的空格或换行
            cleaned = cleaned.lstrip(" \n\t")
            return True, cleaned

    return False, text


def _strip_prefix(text: str) -> str:
    for kw in TASK_KEYWORDS:
        if text.startswith(kw):
            rest = text[len(kw):].strip()
            return rest.lstrip(" \n\t")
    return text
