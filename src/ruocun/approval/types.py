"""定义审批请求、审批结果和提供审批能力的接口。"""
from __future__ import annotations

from typing import Awaitable, Callable, Literal, NotRequired, TypedDict

ApprovalDecision = Literal["once", "session", "always", "deny"]
GateDecision = Literal["allow", "ask", "deny"]


class ApprovalRequest(TypedDict):
    id: str
    toolName: str
    capability: str
    summary: str
    argsJson: NotRequired[str]
    sensitive: NotRequired[bool]
    dangerous: NotRequired[bool]
    noPersist: NotRequired[bool]


class TripNotice(TypedDict):
    consecutiveDenials: int
    totalDenials: int


ApprovalPrompt = Callable[[list[ApprovalRequest]], Awaitable[dict[str, ApprovalDecision]]]
