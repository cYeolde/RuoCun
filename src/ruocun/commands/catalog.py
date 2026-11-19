"""按原样切分斜杠命令名和参数，交给运行入口分派。"""

from __future__ import annotations

import re

# 按 ECMAScript 的空白字符切分，避免 Python 将额外控制字符当成分隔符。
_JS_WHITESPACE = "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_SPACE = re.compile("[" + _JS_WHITESPACE + "]+")
_NAME = re.compile(r"[a-zA-Z0-9:_-]+")


def parseSlashCommand(text: str) -> tuple[str, str] | None:
    trimmed = text.strip(_JS_WHITESPACE)
    if not trimmed.startswith("/"):
        return None
    parts = _SPACE.split(trimmed[1:])
    name = parts[0]
    if _NAME.fullmatch(name) is None:
        return None
    return name, " ".join(parts[1:])
