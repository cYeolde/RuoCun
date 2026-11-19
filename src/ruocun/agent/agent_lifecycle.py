"""统一后台代理的已知终态，供等待、恢复和结果交付判断任务是否结束。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .background_types import ExecutionStatus

if TYPE_CHECKING:
    from ..client.types import ChatMessage
    from .loop import TurnResult


def settleAgentTurn(messages: Sequence[ChatMessage], outcome: TurnResult) -> tuple[ExecutionStatus, str]:
    last = next((message["content"] for message in reversed(messages)
                 if message.get("role") == "assistant" and isinstance(message.get("content"), str)
                 and message["content"]), "")
    if outcome.status == "complete":
        return "completed", last or "(子代理无最终输出)"
    if outcome.status == "cancelled":
        return "canceled", last or outcome.error or "子代理已停止。"
    if outcome.status == "outcome_unknown":
        return "unknown", outcome.error or "子代理工具结果未确认，保留现场。"
    return "failed", (outcome.error or "子代理未完成。") + ("\n\n(部分输出)\n" + last if last else "")
