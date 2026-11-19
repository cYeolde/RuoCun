"""定义批执行器所需的注册表接口，并集中处理写入、命令执行的审批判断，以及命令失败识别。"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from .types import Tool, ToolContext

Approval = Callable[[str, dict[str, Any]], Awaitable[bool]]


class ShellToolOutput(str):
    """保留工具文字接口，并携带由 Shell 后端确认的失败状态。"""

    failed: bool

    def __new__(cls, content: str, *, failed: bool) -> ShellToolOutput:
        output = super().__new__(cls, content)
        output.failed = failed
        return output


def looksFailed(content: str) -> bool:
    """优先读取命令执行状态，纯文字结果沿用原有分类规则。"""
    if isinstance(content, ShellToolOutput):
        return content.failed
    return content.startswith("Error") or bool(re.search(
        r"\[exit -?[1-9]\d*(?:\]|,)|\[超时|\[已中断(?:\]|,)", content,
    ))


class Registry(Protocol):
    def get(self, name: str) -> Tool | None: ...
    def validate(self, name: str, rawArgs: str) -> dict[str, Any]: ...
    def toApiTools(self) -> list[dict[str, Any]]: ...
    async def dispatch(self, name: str, rawArgs: str, ctx: ToolContext) -> str: ...


async def permitted(tool: Tool, args: dict[str, Any], approve: Approval) -> bool:
    # 写入和命令执行共用此审批入口，其他能力在此处直接放行。
    return tool.capability not in {"write", "exec"} or await approve(tool.name, args)
