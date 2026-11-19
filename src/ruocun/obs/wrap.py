"""为模型请求和工具执行附加观测，沿用同步 Python 请求的结果接口。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from functools import wraps
from typing import Any, TypeVar

from ..client.types import StreamChatOptions, Usage
from ..tools.execute import looksFailed
from .attrs import TAGS_KEY, cacheLow, cacheTag, llmAttributes
from .backend import getBackend, obsEvent, safeValue, spanScope

R = TypeVar("R")
SPAN_OUTPUT = "lmnr.span.output"


def truncate(text: str, n: int = 2000) -> str:
    try:
        text = safeValue(text)
        raw = text.encode("utf-16-le", "surrogatepass")
        return raw[:n * 2].decode("utf-16-le", "surrogatepass") + "…" if len(raw) > n * 2 else text
    except Exception:
        return "[observation unavailable]"


def wrapRequest(inner: Callable[..., R]) -> Callable[..., R]:
    if getBackend() is None:
        return inner

    @wraps(inner)
    def wrapped(opts: StreamChatOptions, *args: Any, **kwargs: Any) -> R:
        if getBackend() is None:
            return inner(opts, *args, **kwargs)
        usage: Usage | None = None
        original = opts.get("onUsage")

        def on_usage(value: Usage) -> None:
            nonlocal usage
            usage = value
            if original:
                original(value)

        patched: StreamChatOptions = {**opts, "onUsage": on_usage}
        with spanScope("llm.call", spanType="LLM", input=opts.get("messages")) as span:
            result = inner(patched, *args, **kwargs)
            try:
                actual_usage = usage or getattr(result, "usage", None)
                span.setAttributes(llmAttributes(opts.get("model", ""), actual_usage))
                tag = cacheTag(actual_usage)
                if tag:
                    span.setAttributes({TAGS_KEY: [tag]})
                low = cacheLow(actual_usage)
                if low:
                    obsEvent("cache_low", {**low, "model": opts.get("model", "")})
                message = getattr(result, "message", {})
                content = message.get("content", "") if isinstance(message, Mapping) else ""
                span.setAttributes({SPAN_OUTPUT: truncate(content if isinstance(content, str) else "")})
            except Exception:
                pass
            return result
    return wrapped


def wrapToolHandler(inner: Callable[..., Awaitable[R]], name: str,
                    raw_args: str = "") -> Callable[..., Awaitable[R]]:
    if getBackend() is None:
        return inner

    @wraps(inner)
    async def wrapped(*args: Any, **kwargs: Any) -> R:
        with spanScope("tool." + name, spanType="TOOL", input=truncate(raw_args)) as span:
            result = await inner(*args, **kwargs)
            content = result if isinstance(result, str) else getattr(result, "content", "")
            if isinstance(content, str):
                span.setAttributes({SPAN_OUTPUT: truncate(content)})
                if looksFailed(content):
                    obsEvent("tool_error", {"tool": name})
            return result
    return wrapped
