# novel-tts

Async chapter-level Text-to-Speech (TTS) service for novels, backed by **Qwen3-TTS 0.6B / 1.7B** (CustomVoice variants). Clients submit a chapter's text, receive a `job_id`, poll for progress, and download the finished WAV file when the job reaches `succeeded`.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Environment Requirements](#2-environment-requirements)
3. [Quick Start](#3-quick-start)
4. [Windows 一键启动器](#4-windows-一键启动器)
5. [Configuration via Environment Variables](#5-configuration-via-environment-variables)
6. [API Usage](#6-api-usage)
7. [Job Lifecycle](#7-job-lifecycle)
8. [Model Switch: 0.6B → 1.7B](#8-model-switch-06b--17b)
9. [Running Tests](#9-running-tests)
10. [Troubleshooting](#10-troubleshooting)
11. [Windows Deployment (NSSM / Task Scheduler)](#11-windows-deployment-nssm--task-scheduler)

---

## 1. Project Overview

**novel-tts** is a FastAPI microservice that:

- Accepts a chapter's full text (up to 10 000 chars by default) via a REST `POST` request.
- Splits the text into natural segments (sentences / clauses) using `novel_tts/segmentation.py`.
- Synthesises each segment with a Qwen3-TTS model running locally on GPU.
- Concatenates all segment WAV arrays and writes the final file to `NOVEL_TTS_OUTPUT_DIR`.
- Exposes job status and audio download endpoints so callers can poll asynchronously.

The primary target environment is a **Windows workstation with an NVIDIA RTX 4090** running the service 24/7 alongside other creative tools (ComfyUI, Ollama, etc.).

---

## 2. Environment Requirements

| Requirement | Notes |
|---|---|
| Python | 3.11 or later (3.12 tested) |
| GPU | NVIDIA GPU with CUDA; RTX 4090 recommended |
| CUDA | Compatible with the installed PyTorch wheel |
| OS | Linux or Windows 10/11 (macOS CPU-only for development) |
| RAM | ≥ 16 GB system RAM; ≥ 8 GB VRAM for 0.6B model |
| Disk | ≥ 5 GB for model weights; output audio grows with usage |

Python dependencies are listed in `requirements.txt`. Key packages:

```
fastapi
uvicorn[standard]
sqlalchemy
pydantic-settings
soundfile
numpy
torch          # GPU build from pytorch.org for CUDA support
qwen-tts       # Official Qwen3-TTS inference API
```

---

## 3. Quick Start

```bash
# 1. Clone
git clone https://github.com/your-org/novel-tts.git
cd novel-tts

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) set your API key
export NOVEL_TTS_API_KEY=my-secret-key

# 4. Start the service
python main.py
# — or —
uvicorn main:app --host 0.0.0.0 --port 8008
```

The service starts on `http://0.0.0.0:8008` by default. SQLite database and audio output directories are created automatically on first run.

---

## 4. Windows 一键启动器

项目根目录提供了 **开箱即用的 Windows 批处理脚本**，无需手动输入命令即可启动/停止服务。

### 4.1 文件清单

| 文件 | 用途 |
|---|---|
| `start.bat` | 控制台启动脚本，带环境检测、依赖检查和自动目录创建 |
| `stop.bat` | 停止脚本，自动查找并终止服务进程 |
| `start_hidden.vbs` | 隐藏窗口启动器，后台静默运行，日志写入 `novel-tts.log` |
| `config.bat.template` | 配置模板，复制为 `config.bat` 后可自定义所有环境变量 |

### 4.2 快速使用

**首次使用（推荐）：**

1. 复制配置模板：
   ```batch
   copy config.bat.template config.bat
   ```
2. 按需编辑 `config.bat`，取消注释需要修改的行：
   ```batch
   set NOVEL_TTS_PORT=8008
   set NOVEL_TTS_API_KEY=my-secret-key
   set NOVEL_TTS_OUTPUT_DIR=D:\novel-tts\audio
   ```
3. 双击 `start.bat` 启动服务。

**日常启动：**

- **开发调试** → 双击 `start.bat`（保留控制台窗口，实时查看日志）
- **后台挂机** → 双击 `start_hidden.vbs`（无窗口，日志写入 `novel-tts.log`）
- **停止服务** → 双击 `stop.bat`，或在 `start.bat` 窗口按 `Ctrl+C`

### 4.3 功能说明

**`start.bat` 启动流程**

```
[1/5] 检测 Python 环境（3.11+）
[2/5] 检测 uvicorn，缺失则自动 pip install -r requirements.txt
[3/5] 自动创建 data/audio 和 data/temp 目录
[4/5] 加载 config.bat（如果存在）
[5/5] 启动 uvicorn 服务
```

**`stop.bat` 停止逻辑**

- 优先查找监听 `:8008` 端口的进程
- 其次按窗口标题匹配 `novel-tts 一键启动器`
- 自动执行 `taskkill /F /PID <pid>`

**`start_hidden.vbs` 隐藏模式**

- 通过 VBScript 的 `WshShell.Run` 以隐藏窗口（参数 `0`）启动
- 启动后等待 2 秒，自动探测端口是否监听
- 弹出对话框提示启动成功/失败
- 所有 stdout/stderr 重定向到 `novel-tts.log`

---

## 5. Configuration via Environment Variables

All settings are read from environment variables with the prefix `NOVEL_TTS_`. No config file is required.

| Variable | Default | Description |
|---|---|---|
| `NOVEL_TTS_API_KEY` | `dev-local-key` | Bearer / header key required on every request (`X-Api-Key`). **Change in production.** |
| `NOVEL_TTS_HOST` | `0.0.0.0` | Bind address passed to uvicorn. |
| `NOVEL_TTS_PORT` | `8008` | Listen port. |
| `NOVEL_TTS_DB_URL` | `sqlite:///./novel_tts.db` | SQLAlchemy database URL. Use a full path for Windows, e.g. `sqlite:///C:/data/novel_tts.db`. |
| `NOVEL_TTS_OUTPUT_DIR` | `./data/audio` | Directory where final WAV files are written. |
| `NOVEL_TTS_TEMP_DIR` | `./data/temp` | Scratch directory for per-segment temporary audio files. |
| `NOVEL_TTS_DEFAULT_MODEL_ID` | `qwen3_tts_0_6b_customvoice` | Model used when a request omits `model_id`. |
| `NOVEL_TTS_MAX_CONCURRENT_JOBS` | `1` | Maximum jobs processed simultaneously. Keep at 1 to avoid VRAM contention. |

Example `.env` file (loaded automatically by `pydantic-settings` if present):

```env
NOVEL_TTS_API_KEY=my-secret-key
NOVEL_TTS_OUTPUT_DIR=D:/novel-tts/audio
NOVEL_TTS_TEMP_DIR=D:/novel-tts/temp
NOVEL_TTS_DB_URL=sqlite:///D:/novel-tts/novel_tts.db
```

---

## 6. API Usage

All endpoints except `/healthz` require the header `X-Api-Key: <your key>`.

### 5.1 Create a TTS job

```bash
curl -s -X POST http://localhost:8008/v1/tts/jobs \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: dev-local-key" \
  -d '{
    "request_id": "req-001",
    "book_id": "book-42",
    "chapter_id": "chapter-03",
    "text": "第三章\n\n林默站在山巅，望着远处连绵的群山，心中涌起一股难以言说的感慨。",
    "voice_profile": "female_calm",
    "model_id": "qwen3_tts_0_6b_customvoice"
  }'
```

Response:

```json
{"job_id": "a1b2c3d4-...", "status": "queued"}
```

**Idempotency:** Submitting the same `(text, voice_profile, model_id)` combination returns the existing job rather than creating a duplicate.

---

### 5.2 Poll job status

```bash
curl -s http://localhost:8008/v1/tts/jobs/a1b2c3d4-... \
  -H "X-Api-Key: dev-local-key"
```

Response (in-progress):

```json
{
  "job_id": "a1b2c3d4-...",
  "status": "processing",
  "progress": 45,
  "segments_total": 11,
  "segments_done": 5,
  "audio_url": null,
  "error_code": null,
  "error_message": null
}
```

Response (completed):

```json
{
  "job_id": "a1b2c3d4-...",
  "status": "succeeded",
  "progress": 100,
  "segments_total": 11,
  "segments_done": 11,
  "audio_url": "/v1/tts/jobs/a1b2c3d4-.../audio",
  "error_code": null,
  "error_message": null
}
```

---

### 5.3 Download audio

```bash
curl -s -o chapter-03.wav \
  http://localhost:8008/v1/tts/jobs/a1b2c3d4-.../audio \
  -H "X-Api-Key: dev-local-key"
```

Returns a `WAV` file (`audio/wav`). Returns `409 Conflict` if the job has not yet reached `succeeded`.

---

### 5.4 List available models

```bash
curl -s http://localhost:8008/v1/models \
  -H "X-Api-Key: dev-local-key"
```

Response:

```json
{
  "models": [
    {"id": "qwen3_tts_0_6b_customvoice", "hf_repo": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"}
  ]
}
```

Only models listed in `NOVEL_TTS_AVAILABLE_MODELS` *and* having `enabled: true` in the registry are returned.

---

### 5.5 Health check

```bash
curl -s http://localhost:8008/healthz
```

Response:

```json
{"status": "ok", "model_loaded": true}
```

No authentication required. Use this endpoint for load-balancer or NSSM health probes.

---

## 7. Job Lifecycle

```
         POST /v1/tts/jobs
                │
                ▼
           ┌─────────┐
           │  queued  │  ← created in DB; added to in-memory asyncio queue
           └────┬─────┘
                │  worker picks up job
                ▼
         ┌────────────┐
         │ processing │  ← segments synthesised one-by-one; progress updated
         └──────┬─────┘
          ┌─────┴──────┐
          ▼            ▼
     ┌──────────┐  ┌────────┐
     │ succeeded │  │ failed │
     └──────────┘  └────────┘
```

| State | Description |
|---|---|
| `queued` | Job accepted; waiting for a worker slot. |
| `processing` | Worker is actively synthesising segments. `segments_done` increments as each segment finishes. |
| `succeeded` | All segments merged; WAV file written; `audio_url` is populated. |
| `failed` | An unrecoverable error occurred. `error_code` and `error_message` are set. |

Jobs remain in the database indefinitely. Re-submitting an identical request returns the original job (idempotent).

---

## 8. Model Switch: 0.6B → 1.7B

The 1.7B model produces higher-quality audio but requires more VRAM (~14 GB vs ~6 GB).

**Step 1** — Enable the 1.7B model in environment:

```env
NOVEL_TTS_DEFAULT_MODEL_ID=qwen3_tts_1_7b_customvoice
NOVEL_TTS_AVAILABLE_MODELS=["qwen3_tts_1_7b_customvoice"]
```

Or keep both available and let callers choose per request:

```env
NOVEL_TTS_DEFAULT_MODEL_ID=qwen3_tts_0_6b_customvoice
NOVEL_TTS_AVAILABLE_MODELS=["qwen3_tts_0_6b_customvoice","qwen3_tts_1_7b_customvoice"]
```

**Step 2** — Update `model_registry` in `novel_tts/config.py` to set `enabled: true` for `qwen3_tts_1_7b_customvoice` (or override via env).

**Step 3** — Restart the service. The model is loaded at startup from Hugging Face (`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`).

**Note:** Both models cannot be loaded simultaneously. The service loads one model at startup based on `default_model_id`.

---

## 9. Running Tests

```bash
# All tests (unit + integration with fake engine)
pytest -v

# Single module
pytest tests/test_jobs_api.py -v

# With coverage
pytest --cov=novel_tts --cov-report=term-missing
```

The test suite uses a `FakeTTSEngine` (returns synthetic numpy arrays) so **no GPU is required to run tests**.

Expected output: **12 passed**.

---

## 10. Troubleshooting

### Queue backlog — jobs stuck in `queued`

`NOVEL_TTS_MAX_CONCURRENT_JOBS=1` means only one job runs at a time. Long chapters (100+ sentences) can take several minutes. Increase the value only if VRAM allows running multiple model inferences in parallel — on a single GPU this is rarely beneficial.

Check the queue depth by polling `/v1/tts/jobs/<id>` for recently submitted jobs; if `status` stays `queued` for more than a minute, the worker may have crashed. Restart the service.

### GPU contention with other processes (Ollama, ComfyUI)

If Ollama or ComfyUI holds the GPU while novel-tts tries to synthesise, synthesis will be slow or fail with CUDA out-of-memory errors. Mitigation options:

- Schedule TTS jobs at off-peak hours.
- Set `CUDA_VISIBLE_DEVICES` to a dedicated GPU index if the machine has multiple GPUs.
- Reduce `NOVEL_TTS_MAX_CONCURRENT_JOBS` to 1 (the default) to avoid stacking CUDA allocations.

### Auth failures (401)

```json
{"detail": "unauthorized"}
```

The `X-Api-Key` header is missing or does not match `NOVEL_TTS_API_KEY`. Verify the key:

```bash
curl -s http://localhost:8008/healthz          # no key required
curl -s http://localhost:8008/v1/models \
  -H "X-Api-Key: dev-local-key"               # should return 200
```

### Audio file not found after `succeeded` (503 / 404)

The job reached `succeeded` but the WAV file was removed from disk (e.g., manual cleanup, temp-drive full). The audio path is stored in the database; the file itself must exist at `NOVEL_TTS_OUTPUT_DIR/<job_id>.wav`. Re-running the job (new `request_id` with same text) will regenerate it.

If the service returns `503 Service Unavailable` on `/v1/tts/jobs/{id}/audio`, the file exists in the DB but is missing on disk. Check disk space and the value of `NOVEL_TTS_OUTPUT_DIR`.

### Windows error: `SoX could not be found`

If logs include:

```text
'sox' 不是内部或外部命令
SoX could not be found!
```

Install SoX and restart the terminal/service:

```powershell
choco install sox.portable -y
```

Then verify:

```powershell
sox --version
```

If `sox` still cannot be found, reopen PowerShell (or reboot) so updated `PATH` takes effect.

### Startup warning: `flash-attn is not installed`

This is a performance warning, not a functional error. Synthesis still works with the PyTorch fallback.

### Startup log: `oneDNN custom operations are on`

This TensorFlow info log is harmless for this service and can be ignored.

---

## 11. Windows Deployment (NSSM / Task Scheduler)

### Option A — NSSM (recommended for always-on service)

[NSSM](https://nssm.cc/) wraps any executable as a Windows service with automatic restart on failure.

```powershell
# Install NSSM, then from an elevated prompt:
nssm install novel-tts "C:\Python311\python.exe"
nssm set novel-tts AppParameters "-m uvicorn main:app --host 0.0.0.0 --port 8008"
nssm set novel-tts AppDirectory "C:\Services\novel-tts"
nssm set novel-tts AppEnvironmentExtra `
    "NOVEL_TTS_API_KEY=my-secret-key" `
    "NOVEL_TTS_OUTPUT_DIR=D:\novel-tts\audio" `
    "NOVEL_TTS_DB_URL=sqlite:///D:\novel-tts\novel_tts.db"
nssm set novel-tts Start SERVICE_AUTO_START
nssm start novel-tts
```

Logs are written to `AppStdout` / `AppStderr` paths you configure in NSSM.

### Option B — Task Scheduler (simpler, no third-party tool)

1. Open **Task Scheduler → Create Basic Task**.
2. Trigger: **At system startup** (or **At log on**).
3. Action: **Start a program**
   - Program: `C:\Python311\python.exe`
   - Arguments: `-m uvicorn main:app --host 0.0.0.0 --port 8008`
   - Start in: `C:\Services\novel-tts`
4. Check **Run whether user is logged on or not** and **Run with highest privileges**.
5. Set environment variables in the task's **Properties → Environment** tab or via a wrapper `.bat` file.

### Health probe

Use the `/healthz` endpoint as a health check in either setup:

```
http://localhost:8008/healthz  →  {"status":"ok","model_loaded":true}
```

NSSM can be configured to restart the service if this probe fails (use a scheduled task or a custom monitor script).
