"""FormatError — SF_LOG 解析错误的轻量数据类（可作为 Exception 抛出）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatError(Exception):
    """SF_LOG 格式错误的不可变记录。可作为 Exception 抛出，以便调用方
    通过 `pytest.raises(FormatError)` 捕获；同时保留 4 字段结构供数据流使用。
    """

    code: str
    message: str
    raw_text: str
    char_position: int