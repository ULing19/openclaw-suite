"""gunicorn 配置文件 - 含任务 Worker post_fork 钩子"""
import os
import sys
import threading
import time
from pathlib import Path

# gunicorn 配置文件
bind = "127.0.0.1:8091"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
daemon = False  # 不要 daemon 模式，方便调试
BASE_DIR = Path(__file__).resolve().parent

def post_fork(server, worker):
    """每个 gunicorn worker 进程启动后执行"""
    server.log.info(f"[post_fork] Worker {worker.pid} 启动，开始延迟初始化")
    def delayed_start():
        time.sleep(2)  # 等待 uvicorn ASGI app 完全加载
        try:
            sys.path.insert(0, str(BASE_DIR))
            # 触发 app 模块加载
            import importlib
            if 'app' not in sys.modules:
                server.log.warning("[post_fork] app 模块未加载，跳过")
                return
            app_mod = sys.modules.get('app')
            poll_fn = getattr(app_mod, '_poll_and_process_tasks', None)
            if poll_fn:
                t = threading.Thread(target=poll_fn, daemon=True, name="task-worker")
                t.start()
                server.log.info(f"[post_fork] 任务 Worker 已启动 (worker PID={os.getpid()})")
            else:
                server.log.warning(f"[post_fork] _poll_and_process_tasks 未找到，app 属性: {dir(app_mod)[:10]}")
        except Exception as e:
            server.log.warning(f"[post_fork] 启动任务 Worker 失败: {e}")
    t = threading.Thread(target=delayed_start, daemon=True)
    t.start()

def when_ready(server):
    server.log.info("[gunicorn] 服务器已就绪")
