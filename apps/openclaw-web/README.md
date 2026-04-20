# OpenClaw Web Reference App

[中文说明](#中文) | [English](#english)

---

## 中文

这是从 `openclaw-web` 仓库中清洗并并入的一个参考 Web 应用子目录。

它的定位不是当前主仓库的“核心库”，而是：

- 一个可运行的 OpenClaw Web UI 参考实现
- 展示任务模式、多媒体处理、游客会话和文件下载链路
- 方便把多模态工具与 Web 界面整合在一起

### 当前做过的公开化处理

- 移除了硬编码 API key
- 把绝对路径改成环境变量或相对路径
- 去掉数据库、日志、缓存、备份页面等运行时垃圾
- 把页面标题中的个人标识改成通用名称

### 关键环境变量

- `MINIMAX_API_KEY`
- `VIVIAI_API_KEY`
- `AIPAIBOX_API_KEY`
- `OPENCLAW_WEB_TOKEN_SECRET`
- `OPENCLAW_WEB_DATA_DIR`
- `OPENCLAW_WEB_ARTIFACTS_DIR`
- `OPENCLAW_WEB_STATIC_DIR`

### 说明

这部分代码仍然更像“参考应用”而不是成熟框架，适合：

- 继续单独部署
- 当作子应用进行二次开发
- 拆分其中的任务模式 / Web UI / bridge 逻辑

---

## English

This directory is a sanitized reference web app merged from the `openclaw-web` repository.

It is not positioned as the core library of this repository. Instead, it serves as:

- a runnable OpenClaw Web UI reference
- an example of task mode, multimodal handling, guest sessions, and artifact downloads
- a practical bridge between the toolkit and a browser-based interface

### Public-safety cleanup already applied

- removed hardcoded API keys
- replaced absolute server paths with environment-driven or relative paths
- excluded databases, logs, caches, and backup HTML files
- replaced personal branding with a generic app title

### Key environment variables

- `MINIMAX_API_KEY`
- `VIVIAI_API_KEY`
- `AIPAIBOX_API_KEY`
- `OPENCLAW_WEB_TOKEN_SECRET`
- `OPENCLAW_WEB_DATA_DIR`
- `OPENCLAW_WEB_ARTIFACTS_DIR`
- `OPENCLAW_WEB_STATIC_DIR`
