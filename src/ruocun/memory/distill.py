"""为现行反思与受控学习共享模型调用类型和技能目录噪声过滤。"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from ..client.types import StreamChatOptions

ModelCall = Callable[[StreamChatOptions], Awaitable[str | None]]

_CATALOG_PATTERNS = (
    re.compile(r"使用\s*[A-Za-z0-9_./-]+\s*(技能|工具)"),
    re.compile(r"[0-9]+\s*个技能"),
    re.compile(r"工具名.*改为"),
)


def isCatalogNoise(text: str) -> bool:
    return any(pattern.search(text) for pattern in _CATALOG_PATTERNS)
