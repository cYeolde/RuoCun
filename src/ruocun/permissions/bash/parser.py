"""限制 Bash 解析入口的输入长度，并把解析失败表示为调用方可判断的结果。

用 PARSE_ABORTED 表示解析中止，用 None 表示输入为空或超过长度限制。
"""
from __future__ import annotations

from .types import Node


class _ParseAborted:
    pass


PARSE_ABORTED = _ParseAborted()
_JS_WHITESPACE = "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"


def jsTrim(value: str) -> str:
    return value.strip(_JS_WHITESPACE)


def _tooLong(command: str) -> bool:
    return len(command.encode("utf-16-le", errors="surrogatepass")) // 2 > 10000


async def parseCommandRaw(command: str) -> Node | None | _ParseAborted:
    if not command or _tooLong(command):
        return None
    from .bash_parser import parseSource
    try:
        result = parseSource(command)
        return PARSE_ABORTED if result is None else result
    except Exception:
        return PARSE_ABORTED
