"""
main.py — 小说听书工具 CLI 入口

用法：
  # 从 URL 抓取并转语音（edge-tts，无需 GPU，推荐新手）
  python main.py --url https://hotupub.net/book/1060/0/

  # 从本地 txt 文件转语音
  python main.py --file ./my_novel.txt

  # 使用 VoxCPM2 本地模型（质量更高，需要 GPU + 8GB+ 显存）
  python main.py --url https://... --engine voxcpm2

  # 指定输出文件名
  python main.py --url https://... --output ./output/chapter1.mp3

  # edge-tts 换声音（男声）
  python main.py --url https://... --voice zh-CN-YunxiNeural

  # edge-tts 调速（加快20%）
  python main.py --url https://... --rate +20%
"""

import argparse
import asyncio
import sys
from pathlib import Path
from datetime import datetime

from novel_tts.fetcher import fetch_from_url, read_from_file
from novel_tts.tts import get_engine


def parse_args():
    parser = argparse.ArgumentParser(
        description="🎧 小说听书工具 — URL 或本地 txt 转语音",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # 输入源（二选一）
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", metavar="URL", help="小说章节网页 URL")
    src.add_argument("--file", metavar="PATH", help="本地 txt 文件路径")

    # TTS 引擎
    parser.add_argument(
        "--engine",
        choices=["edge", "voxcpm2"],
        default="edge",
        help="TTS 引擎：edge（默认，在线轻量）/ voxcpm2（本地高质量，需 GPU）",
    )

    # edge-tts 参数
    parser.add_argument(
        "--voice",
        default="zh-CN-XiaoxiaoNeural",
        help="edge-tts 声音名称（默认：zh-CN-XiaoxiaoNeural 小晓，女声）",
    )
    parser.add_argument(
        "--rate",
        default="+0%",
        help="edge-tts 语速调整，如 +20%% 加快 / -10%% 减慢（默认 +0%%）",
    )

    # VoxCPM2 参数
    parser.add_argument(
        "--model-path",
        default=None,
        help="VoxCPM2 本地模型路径（不填则从 HuggingFace 自动下载）",
    )
    parser.add_argument(
        "--reference-wav",
        default=None,
        help="VoxCPM2 声音克隆参考音频路径（不填则使用默认声音）",
    )

    # 输出
    parser.add_argument(
        "--output",
        default=None,
        help="输出音频文件路径（默认自动生成到 ./output/ 目录）",
    )

    # 调试
    parser.add_argument(
        "--preview",
        action="store_true",
        help="仅打印抓取到的文本，不合成语音（用于调试）",
    )

    return parser.parse_args()


def auto_output_path(engine: str) -> str:
    """自动生成输出文件名（带时间戳）"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "mp3" if engine == "edge" else "wav"
    path = Path("output") / f"novel_{ts}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def main():
    args = parse_args()

    # ── Step 1: 获取文本 ──────────────────────────
    print("=" * 50)
    if args.url:
        print(f"📡 正在抓取网页内容: {args.url}")
        try:
            text = asyncio.run(fetch_from_url(args.url))
        except Exception as e:
            print(f"❌ 抓取失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"📂 正在读取本地文件: {args.file}")
        try:
            text = read_from_file(args.file)
        except Exception as e:
            print(f"❌ 读取失败: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"✅ 获取到文本，共 {len(text)} 字")
    print("-" * 50)

    # ── 预览模式 ──────────────────────────────────
    if args.preview:
        print("【预览模式 — 仅显示文本，不合成语音】")
        print(text[:2000])
        if len(text) > 2000:
            print(f"\n... （共 {len(text)} 字，已截断显示前 2000 字）")
        return

    # ── Step 2: 初始化 TTS 引擎 ───────────────────
    print(f"🔊 使用引擎: {args.engine}")
    if args.engine == "edge":
        engine = get_engine("edge", voice=args.voice, rate=args.rate)
        print(f"   声音: {args.voice} | 语速: {args.rate}")
    else:
        engine = get_engine(
            "voxcpm2",
            model_path=args.model_path,
            reference_wav=args.reference_wav,
        )

    # ── Step 3: 合成语音 ──────────────────────────
    output_path = args.output or auto_output_path(args.engine)
    print(f"🎵 开始合成语音 → {output_path}")
    print("-" * 50)

    try:
        saved = engine.synthesize(text, output_path)
    except Exception as e:
        print(f"❌ 语音合成失败: {e}", file=sys.stderr)
        sys.exit(1)

    print("=" * 50)
    print(f"✅ 完成！音频文件: {saved}")
    print("   提示: 用任意音频播放器打开即可收听。")


if __name__ == "__main__":
    main()
