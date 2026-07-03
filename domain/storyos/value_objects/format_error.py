"""FormatError — SF_LOG 解析错误的轻量数据类。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatError:
    """SF_LOG 格式错误的不可变记录。"""

    code: str
    message: str
    raw_text: str
    char_position: int