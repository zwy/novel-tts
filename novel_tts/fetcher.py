"""
fetcher.py — 从小说网页 URL 抓取正文内容
支持：crawl4ai（异步，带 JS 渲染）
"""

import asyncio
import re
from typing import Optional


async def fetch_from_url(url: str) -> str:
    """
    使用 crawl4ai 抓取指定 URL 的小说正文。
    返回纯文本正文内容。
    """
    try:
        from crawl4ai import AsyncWebCrawler, CacheMode
        from crawl4ai.extraction_strategy import NoExtractionStrategy
    except ImportError:
        raise ImportError("请先安装 crawl4ai：pip install crawl4ai && crawl4ai-setup")

    async with AsyncWebCrawler(headless=True) as crawler:
        result = await crawler.arun(
            url=url,
            cache_mode=CacheMode.BYPASS,          # 每次都重新抓，避免缓存旧内容
            word_count_threshold=50,               # 过滤掉字数太少的噪声块
            excluded_tags=["nav", "footer", "header", "script", "style"],
            remove_overlay_elements=True,          # 移除弹窗/遮罩
        )

    if not result.success:
        raise RuntimeError(f"抓取失败: {result.error_message}")

    # result.markdown 是清理后的 Markdown，通常已过滤导航、页脚等
    text = result.markdown or result.cleaned_html or ""
    text = _clean_text(text)

    if len(text) < 100:
        raise ValueError(f"抓取到的内容太短（{len(text)} 字），可能被反爬或结构不匹配。")

    return text


def _clean_text(raw: str) -> str:
    """
    清理 Markdown/HTML 转换后的文本：
    - 去除 Markdown 标记（#、*、[]()等）
    - 合并多余空行
    - 去除页眉页脚常见噪声短语
    """
    # 去除 Markdown 链接 [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', raw)
    # 去除图片 ![alt](url)
    text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)
    # 去除 Markdown 标题符号 # ## ###
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # 去除加粗/斜体
    text = re.sub(r'\*{1,3}([^\*]+)\*{1,3}', r'\1', text)
    # 去除水平线
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # 去除常见噪声短语（可按需扩充）
    noise_phrases = [
        r'點擊追書.*',
        r'追書',
        r'A[-+]',
        r'上一章',
        r'下一章',
        r'目[錄录]',
        r'首[頁页]',
        r'閱讀記錄',
        r'登[出入]',
        r'簽到',
        r'Copyright.*',
        r'未滿\s*\d+\s*歲.*',
        r'全站皆為限制級.*',
    ]
    for phrase in noise_phrases:
        text = re.sub(phrase, '', text, flags=re.MULTILINE)
    # 合并连续空行（超过2行空行压缩为1行）
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def read_from_file(path: str) -> str:
    """
    从本地 txt 文件读取小说内容。
    支持 UTF-8 和 GBK 编码自动检测。
    """
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                content = f.read()
            return _clean_text(content)
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    raise ValueError(f"无法读取文件 {path}，请检查文件编码（支持 UTF-8 / GBK）")
