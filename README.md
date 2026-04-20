# 📖 novel-tts — 网页小说听书工具

> 输入一个章节 URL 或本地 txt，自动抓取正文并转为语音，随时随地"听"小说。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🌐 URL 抓取 | 输入章节 URL，自动提取正文，过滤导航/页脚噪声 |
| 📂 本地 txt | 读取本地 txt 文件，自动识别 UTF-8 / GBK 编码 |
| 🔊 TTS 合成 | 两种引擎可选（见下方对比） |
| ✂️ 长文分段 | 按句子边界自动分段合成再拼接，不截断句子 |
| 🎙️ 声音克隆 | VoxCPM2 引擎支持提供参考音频克隆声音 |

### TTS 引擎对比

|  | edge-tts（默认） | VoxCPM2 |
|---|---|---|
| 运行方式 | 在线（微软服务） | 本地推理 |
| 是否需要 GPU | ❌ 不需要 | ✅ 推荐（8GB+ 显存） |
| 中文质量 | ★★★★ 很好 | ★★★★★ 极佳 |
| 速度 | 极快（秒级） | 中等（GPU 下实时） |
| 声音克隆 | ❌ | ✅ 支持参考音频 |
| 输出格式 | mp3 | wav |

---

## 🚀 安装

### 环境要求

- Python 3.10+
- （可选）NVIDIA GPU，8GB+ 显存（仅 VoxCPM2 引擎需要）

### 步骤一：克隆项目

```bash
git clone https://github.com/zwy/novel-tts.git
cd novel-tts
```

### 步骤二：创建虚拟环境（推荐）

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 步骤三：安装依赖

```bash
pip install -r requirements.txt
```

### 步骤四：初始化 crawl4ai 浏览器驱动

```bash
crawl4ai-setup
```

> 这一步会下载 Playwright 的 Chromium 浏览器，用于渲染 JS 网页，约 200MB。

### （可选）安装 VoxCPM2 本地引擎

```bash
pip install voxcpm
```

首次运行会自动从 HuggingFace 下载模型（约 4–8 GB）。国内用户建议设置镜像加速：

```bash
# Windows
set HF_ENDPOINT=https://hf-mirror.com

# macOS / Linux
export HF_ENDPOINT=https://hf-mirror.com
```

---

## 📖 使用方法

### 基础用法

```bash
# 从网页 URL 抓取并转语音（默认 edge-tts，小晓女声）
python main.py --url "https://example.com/book/1/chapter/1/"

# 从本地 txt 文件转语音
python main.py --file ./my_chapter.txt
```

### 先预览文本，确认抓取内容

```bash
python main.py --url "https://example.com/..." --preview
```

### 切换声音 / 调整语速

```bash
# 换男声
python main.py --url "https://..." --voice zh-CN-YunxiNeural

# 加快语速 20%
python main.py --url "https://..." --rate +20%

# 减慢语速 10%
python main.py --url "https://..." --rate -10%
```

### 指定输出文件路径

```bash
python main.py --url "https://..." --output ./output/chapter_01.mp3
```

### 使用 VoxCPM2 本地高质量引擎

```bash
# 使用默认声音
python main.py --url "https://..." --engine voxcpm2

# 声音克隆（提供参考音频 .wav）
python main.py --url "https://..." --engine voxcpm2 --reference-wav ./my_voice.wav

# 离线使用（提前下载好模型）
python main.py --url "https://..." --engine voxcpm2 --model-path /path/to/VoxCPM2
```

---

## ⚙️ 完整参数说明

```
usage: main.py [-h] (--url URL | --file PATH)
               [--engine {edge,voxcpm2}]
               [--voice VOICE] [--rate RATE]
               [--model-path PATH] [--reference-wav PATH]
               [--output PATH] [--preview]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--url URL` | — | 小说章节网页 URL（与 `--file` 二选一） |
| `--file PATH` | — | 本地 txt 文件路径（与 `--url` 二选一） |
| `--engine` | `edge` | TTS 引擎：`edge` / `voxcpm2` |
| `--voice` | `zh-CN-XiaoxiaoNeural` | edge-tts 声音名称 |
| `--rate` | `+0%` | edge-tts 语速，如 `+20%` / `-10%` |
| `--model-path` | 自动下载 | VoxCPM2 本地模型目录 |
| `--reference-wav` | 无 | VoxCPM2 声音克隆参考音频（.wav） |
| `--output PATH` | 自动生成 | 输出音频文件路径 |
| `--preview` | — | 仅打印提取的文本，不合成音频（调试用） |

---

## 🎙️ edge-tts 常用中文声音

```
zh-CN-XiaoxiaoNeural   # 小晓，女声（默认，自然流畅）
zh-CN-YunxiNeural      # 云希，男声
zh-CN-XiaoyiNeural     # 晓伊，女声
zh-CN-YunyangNeural    # 云扬，男声（新闻播报风）
zh-TW-HsiaoChenNeural  # 繁体中文，女声
zh-HK-HiuGaaiNeural    # 粤语，女声
```

查看全部声音列表：

```bash
edge-tts --list-voices | grep zh
```

---

## 🗂️ 项目结构

```
novel-tts/
├── main.py              # CLI 主入口
├── requirements.txt     # 依赖列表
├── README.md
├── novel_tts/
│   ├── __init__.py
│   ├── fetcher.py       # 网页抓取 + 本地 txt 读取
│   └── tts.py           # TTS 引擎（VoxCPM2 / edge-tts）
└── output/              # 生成的音频文件（自动创建）
```

---

## ❓ 常见问题

**Q: 抓取失败，提示"内容太短"？**  
A: 部分网站有反爬机制。可先用 `--preview` 查看内容，或直接复制正文到 txt 文件，用 `--file` 模式。

**Q: VoxCPM2 模型下载太慢？**  
A: 设置国内镜像：`export HF_ENDPOINT=https://hf-mirror.com`，然后重新运行。

**Q: edge-tts 没有输出声音？**  
A: 检查网络连接，edge-tts 需要访问微软服务器（`speech.platform.bing.com`）。

**Q: 想把 VoxCPM2 输出的 wav 转成 mp3？**  
A: 安装 [ffmpeg](https://ffmpeg.org/) 后执行：`ffmpeg -i output.wav output.mp3`

---

## 📦 依赖说明

| 包 | 用途 |
|---|---|
| [crawl4ai](https://github.com/unclecode/crawl4ai) | 网页正文抓取，支持 JS 渲染 |
| [edge-tts](https://github.com/rany2/edge-tts) | 微软在线 TTS |
| [voxcpm](https://github.com/OpenBMB/VoxCPM)（可选） | OpenBMB VoxCPM2 本地 TTS |
| soundfile | WAV 音频读写 |
| numpy | 音频数组拼接 |

---

## 📄 License

MIT
