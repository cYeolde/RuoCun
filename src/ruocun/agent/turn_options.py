"""按职责定义单个模型回合所需的配置与回调。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ..client.types import ChatMessage, StreamChatOptions, StreamDelta
from ..tools.execute import Approval
from ..tools.tool_batch import Authorize, BatchAuthorize, CallScope


@dataclass(frozen=True, kw_only=True)
class ToolAuthorization:
    """选择单次授权或整批授权，并提供工具派发所需的权限状态。"""

    approve: Approval | None = None
    authorize: Authorize | None = None
    authorize_batch: BatchAuthorize | None = None
    call_scope: CallScope | None = None
    permission_mode: Callable[[], str] | None = None

    def __post_init__(self) -> None:
        if self.authorize_batch is not None:
            if self.approve is not None or self.authorize is not None:
                raise ValueError("工具授权必须选择单次或整批模式。")
        elif self.approve is None:
            raise ValueError("单次授权必须提供确认回调。")


@dataclass(frozen=True, kw_only=True)
class TurnEvents:
    """流式输出、消息保存和工具结果对应的同步回调。"""

    on_delta: Callable[[StreamDelta], None] | None = None
    accepts_delta: Callable[[], bool] | None = None
    on_assistant_saved: Callable[[ChatMessage], None] | None = None
    on_tool_message: Callable[[ChatMessage, ChatMessage], None] | None = None
    on_tool_result: Callable[[str, str], None] | None = None
    notice: Callable[[str], None] | None = None


@dataclass(frozen=True, kw_only=True)
class ContextHooks:
    """发送请求前的上下文检查与上下文压缩。"""

    request_preflight: Callable[[StreamChatOptions], Awaitable[StreamChatOptions]] | None = None
    compact: Callable[[], Awaitable[Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class TurnPolicy:
    """本轮的运行限制与模型输出设置。"""

    max_turns: float = float("inf")
    budget_hard: bool = False
    reasoning_effort: str = "max"
    empty_max_retries: float = 2
    empty_retry_max_tokens: float = 256000


@dataclass(frozen=True, kw_only=True)
class ModelRecoveryHooks:
    """模型故障后运行时可以执行的动作。"""

    list_other_accounts: Callable[[], Sequence[str]] | None = None
    switch_account_and_wait: Callable[[str], Awaitable[bool]] | None = None
    on_model_unavailable: Callable[[], Awaitable[None]] | None = None


@dataclass(frozen=True, kw_only=True)
class ToolFeedbackOptions:
    """工具批提交后的进度提示和反思。"""

    reflect: Callable[[str], Awaitable[str | None]] | None = None
    self_challenge: bool = False
    long_task: bool = False
    progress_advice: bool = False
    interactive: bool = True
    has_running_background: Callable[[], bool] | None = None
