# OpenClaw Web Deployment Guide

[中文说明](#中文) | [English](#english)

---

## 中文

### 推荐目录

```text
/opt/openclaw-suite/apps/openclaw-web
```

### 1. 安装依赖

```bash
cd /opt/openclaw-suite
pip install -r apps/openclaw-web/requirements.txt
```

### 2. 配置环境

```bash
cd apps/openclaw-web
cp config_example.env .env
```

至少配置：

- `MINIMAX_API_KEY`
- `OPENCLAW_WEB_TOKEN_SECRET`

如果要启用额外图生或桥接：

- `VIVIAI_API_KEY`
- `AIPAIBOX_API_KEY`

### 3. 运行方式

开发模式：

```bash
python app.py
```

Gunicorn：

```bash
gunicorn -c gunicorn_config.py app:app
```

### 4. 目录建议

- `OPENCLAW_WEB_DATA_DIR=./data`
- `OPENCLAW_WEB_ARTIFACTS_DIR=./artifacts/tasks`
- `OPENCLAW_WEB_STATIC_DIR=./static`

如果跑生产环境，建议把 `data/` 和 `artifacts/` 放到持久卷。

---

## English

### Suggested path

```text
/opt/openclaw-suite/apps/openclaw-web
```

### 1. Install dependencies

```bash
cd /opt/openclaw-suite
pip install -r apps/openclaw-web/requirements.txt
```

### 2. Configure environment

```bash
cd apps/openclaw-web
cp config_example.env .env
```

At minimum configure:

- `MINIMAX_API_KEY`
- `OPENCLAW_WEB_TOKEN_SECRET`

Optional:

- `VIVIAI_API_KEY`
- `AIPAIBOX_API_KEY`

### 3. Run

Development:

```bash
python app.py
```

Gunicorn:

```bash
gunicorn -c gunicorn_config.py app:app
```
