"""为权限检查识别隐藏控制字符和 Unicode 规范化差异。"""
from __future__ import annotations

import unicodedata


def hasSuspiciousUnicode(text: str) -> bool:
    return (any(unicodedata.category(char) in {"Cf", "Co", "Cn", "Cc"} for char in text if char not in "\t\n\r")
            or unicodedata.normalize("NFKC", text) != text)
