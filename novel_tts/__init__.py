# novel_tts 包入口
from .fetcher import fetch_from_url, read_from_file
from .tts import get_engine

__version__ = "0.1.0"
__all__ = ["fetch_from_url", "read_from_file", "get_engine"]
