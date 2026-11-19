"""执行一轮会话的核心循环。先准备请求并读模型响应，再按权限派发工具，把助手调用和工具结果成对保存后进入下一次请求。

请求、权限和存储由各自接口提供。压缩失败则保留旧上下文并停止本轮，见 ADR-0012。
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, nullcontext
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any, Protocol, cast

from ..client.resilient import (
    ResilientContext,
    ResilientResult,
    isContextLengthError,
    isRateLimitError,
    isRetryable,
    streamChatResilient,
)
from ..client.types import StreamChatOptions, StreamDelta, Usage
from ..obs.backend import getObsMeta
from ..session.cache_audit import cachePrefixFingerprint
from ..session.messages import flushReadImages
from ..session.session import Session
from ..tools.execute import Registry
from ..tools.registry import ToolRegistry
from ..tools.tool_batch import (
    ToolJournal,
    UnknownToolOutcome,
    executeToolBatch,
)
from ..tools.types import ToolContext
from .background_runtime import WaitControl, currentWaitControl
from .background_types import WaitHandle
from .model_recovery import ModelRecovery
from .tool_batch_feedback import ToolBatchFeedback
from .turn_options import (
    ContextHooks,
    ModelRecoveryHooks,
    ToolAuthorization,
    ToolFeedbackOptions,
    TurnEvents,
    TurnPolicy,
)


class Journal(ToolJournal, Protocol):
    async def save(self, session: Session) -> None: ...
    async def replace_context(self, session: Session, messages: list[dict[str, Any]], *, reset_prompt: bool = True) -> None: ...


@dataclass(frozen=True)
class TurnResult:
    status: str
    error: str = ""
    wait: WaitHandle | None = None


@dataclass
class _RequestStream:
    text: list[str] = field(default_factory=list)
    exposed: bool = False
    empty_truncation: bool = False


Request = Callable[[StreamChatOptions, ResilientContext], ResilientResult]
EMPTY_TRUNCATION_NOTE = files("ruocun.agent").joinpath("resources/empty-truncation.zh.txt").read_text("utf-8")
_FORCED_TOOLS = {"Write", "Edit", "NotebookEdit", "Bash"}
_TRANSIENT_MODEL_FAILURE = re.compile(r"\b5[0-9]{2}\b|overload|timeout|timed out|超时|连接.*失败|网络|非流式", re.I)


def _request(opts: StreamChatOptions, context: ResilientContext) -> ResilientResult:
    return streamChatResilient(opts, context=context)


def _reject_json_constant(value: str) -> None:
    raise ValueError("JSON不允许NaN或Infinity常量")


def sanitizeHistoryForResume(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """为续写清理不可解析的 arguments，保留已有的推理和其余历史字段。"""
    cleaned = []
    for message in messages:
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            cleaned.append(message)
            continue
        updated = copy.deepcopy(message)
        for call in updated["tool_calls"]:
            function = call.get("function", {})
            try:
                json.loads(function.get("arguments") or "{}", parse_constant=_reject_json_constant)
            except (ValueError, TypeError):
                function["arguments"] = "{}"
        cleaned.append(updated)
    return cleaned


def _safe_calls(raw: Any) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
    """保存历史时把损坏的 JSON 参数归一为空对象，工具执行仍按原始参数校验。"""
    saved: list[dict[str, Any]] = []
    calls: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    if not isinstance(raw, list):
        raise ValueError("模型tool_calls必须为列表")
    for call in raw:
        if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
            raise ValueError("模型工具调用格式无效")
        fn = call["function"]
        call_id, name, args = call.get("id"), fn.get("name"), fn.get("arguments", "")
        if (not isinstance(call_id, str) or not call_id or not isinstance(name, str)
                or not name or not isinstance(args, str)):
            raise ValueError("模型工具调用缺少id、名称或JSON字符串参数")
        if call_id in seen:
            raise ValueError("同一模型回答出现重复工具调用id")
        seen.add(call_id)
        normalized = args
        try:
            json.loads(args, parse_constant=_reject_json_constant)
        except ValueError:
            normalized = "{}"
        saved.append({"id": call_id, "type": "function", "function": {
            "name": name, "arguments": normalized,
        }})
        calls.append((call_id, name, args))
    return saved, calls


async def run_turn(
    session: Session, options: StreamChatOptions, registry: Registry, ctx: ToolContext, *,
    authorization: ToolAuthorization,
    request: Request = _request,
    journal: Journal | None = None,
    wait_control: WaitControl | None = None,
    tool_batch_scope: AbstractAsyncContextManager[None] | None = None,
    api_tools: Callable[[], list[dict[str, Any]]] | None = None,
    on_boundary: Callable[[], Awaitable[None]] | None = None,
    on_tool_boundary: Callable[[], Awaitable[None]] | None = None,
    env: Mapping[str, str] | None = None,
    events: TurnEvents = TurnEvents(),
    context_hooks: ContextHooks = ContextHooks(),
    policy: TurnPolicy = TurnPolicy(),
    recovery: ModelRecoveryHooks = ModelRecoveryHooks(),
    feedback: ToolFeedbackOptions = ToolFeedbackOptions(),
) -> TurnResult:
    """执行一个已保存用户输入的回合。造成副作用前须先提交相应执行意图。"""
    wait_control = (wait_control or currentWaitControl()) if ctx.subagentDepth == 0 else None
    empty = 0
    turns = 0
    context_retries = 0
    boundary = True
    budget_warned = False
    retry_reasoning = False
    forcing_unsupported = False
    recovery_env = env if env is not None else {}
    notice = events.notice
    on_delta = events.on_delta
    compact = context_hooks.compact

    async def save() -> None:
        if journal is not None:
            try:
                await journal.save(session)
            except BaseException:
                if wait_control is not None and not wait_control.runtime.checkpointUnknown:
                    if wait_control.pending and session.messages and session.messages[-1].get("role") == "tool":
                        session.messages[-1]["content"] = "Error: 等待状态保存失败,未激活等待;后台结果仍待投递。"
                    wait_control.rollback()
                raise

    async def save_assistant_notice(text: str) -> None:
        assistant = {"role": "assistant", "content": text}
        session.messages.append(assistant)
        await save()
        if events.on_assistant_saved is not None:
            events.on_assistant_saved(assistant)

    model_recovery = ModelRecovery(
        recovery_env,
        cancelled=lambda: ctx.signal.is_set(),
        ask_choice=lambda: ctx.askChoice,
        save=save,
        save_assistant_notice=save_assistant_notice,
        notice=notice,
        list_other_accounts=recovery.list_other_accounts,
        switch_account_and_wait=recovery.switch_account_and_wait,
        on_model_unavailable=recovery.on_model_unavailable,
    )

    async def append_feedback(text: str) -> None:
        messages = [*session.messages, {"role": "system", "content": text}]
        if journal is None:
            session.messages = messages
        else:
            await journal.replace_context(session, messages, reset_prompt=False)

    tool_feedback = ToolBatchFeedback(
        recovery_env,
        cancelled=lambda: ctx.signal.is_set(),
        append_feedback=append_feedback,
        notice=notice,
        reflect=feedback.reflect,
        self_challenge=feedback.self_challenge,
        long_task=feedback.long_task,
        interactive=feedback.interactive,
        progress_advice=feedback.progress_advice,
        productive_tools=_FORCED_TOOLS,
    )
    foreground = ctx.subagentDepth == 0 and not options.get("background")
    ctx.sessionModel = session.model
    ctx.forkToolSnapshot = None
    event_loop = asyncio.get_running_loop()
    active_request: _RequestStream | None = None

    async def compress() -> TurnResult | None:
        assert compact is not None
        original = copy.deepcopy(session.messages)
        try:
            await compact()
        except InterruptedError:
            return TurnResult("cancelled", "压缩已取消，原上下文保留。")
        except Exception:
            # 压缩失败时保留原上下文，停止本轮的请求和工具派发。
            return TurnResult("compaction_failed", "摘要未确认，原上下文保留；本轮已停止，可修复后重试。")
        if ctx.signal.is_set():
            return TurnResult("cancelled", "本轮已取消。")
        if session.messages == original:
            return TurnResult("compaction_failed", "没有可安全缩小的历史，原文保留；本轮停止。")
        return None

    while not ctx.signal.is_set():
        if boundary:
            if turns >= policy.max_turns:
                await save()
                return TurnResult("turn_limit", "已达最大轮数，记录已保存。")
            if session.overBudget():
                if not budget_warned and notice:
                    notice(f"[成本提醒] 本次进程费用约 ¥{session.costCNY():.2f}，已达阈值 ¥{session.budgetCNY}。")
                budget_warned = True
                if policy.budget_hard:
                    await save()
                    return TurnResult("budget_limit", "已达显式硬预算上限，本轮停止。")
            if on_boundary is not None:
                await on_boundary()
                if ctx.signal.is_set():
                    break
            boundary = False
        opts = cast(StreamChatOptions, dict(options))
        opts["model"] = session.model
        opts["messages"] = copy.deepcopy(session.messages)
        opts["tools"] = api_tools() if api_tools is not None else registry.toApiTools()
        if opts["tools"]:
            opts["parallelToolCalls"] = True
        opts["extra"] = {**options.get("extra", {}), "reasoning_effort": policy.reasoning_effort}
        forced = retry_reasoning and not forcing_unsupported
        if retry_reasoning:
            opts["extra"]["reasoning_effort"] = "low"
            opts["maxTokens"] = cast(int, policy.empty_retry_max_tokens)
            if forced:
                productive = [tool for tool in opts["tools"] if tool["function"]["name"] in _FORCED_TOOLS]
                opts["tools"] = productive or opts["tools"]
                opts["extra"]["tool_choice"] = "required"
        if context_hooks.request_preflight is not None:
            try:
                opts = await context_hooks.request_preflight(opts)
            except InterruptedError:
                return TurnResult("cancelled", "上下文检查已取消，原文保留。")
            except Exception as preflight_error:
                return TurnResult("compaction_failed", f"上下文检查未完成，原文保留；本轮停止。{preflight_error}")
            if ctx.signal.is_set():
                return TurnResult("cancelled", "本轮已取消。")
        if (ctx.subagentDepth == 0 and isinstance(registry, ToolRegistry)
                and (ctx.runAgent is not None or ctx.launchAgent is not None)):
            ctx.forkToolSnapshot = registry.forkSnapshot(opts["tools"])
        stream = _RequestStream()

        def on_empty_truncation(current: _RequestStream = stream) -> None:
            if active_request is current:
                current.empty_truncation = True

        opts["onEmptyTruncation"] = on_empty_truncation
        session.lastSentLength = len(session.messages)
        system = opts["messages"][0].get("content") if opts["messages"] else ""
        tools_raw = json.dumps(opts["tools"], ensure_ascii=False, separators=(",", ":"))
        session.notePrefix(cachePrefixFingerprint(opts["model"], system if isinstance(system, str) else "", tools_raw))
        active_request = stream

        def receive_delta(value: StreamDelta, current: _RequestStream = stream) -> None:
            if active_request is not current:
                return
            if value.get("kind") in {"content", "reasoning", "tool_call"}:
                current.exposed = True
            if value.get("kind") == "content" and isinstance(value.get("text"), str):
                current.text.append(value["text"])
            if on_delta is None:
                return

            def deliver() -> None:
                if (active_request is current and not ctx.signal.is_set()
                        and (events.accepts_delta is None or events.accepts_delta())):
                    on_delta(value)
            try:
                event_loop.call_soon_threadsafe(deliver)
            except RuntimeError:
                # 业务循环关闭后丢弃迟到的展示事件，可信结果由完成路径接收。
                pass

        request_error: Exception | None = None
        try:
            if wait_control is not None:
                wait_control.runtime.modelRequested()
            response = await asyncio.to_thread(
                request, opts, ResilientContext(cancel=ctx.signal.is_set, on_delta=receive_delta),
            )
        except Exception as exc:
            request_error, response = exc, None
        finally:
            active_request = None
        if response is not None and response.usage:
            session.addPrimaryUsage(cast(Usage, response.usage), opts["model"])
            if ctx.cacheAudit is not None:
                redact = ctx.auditRedact or str
                identity = getObsMeta()
                record = {"agent": "sub" if ctx.subagentDepth else "main", "depth": ctx.subagentDepth,
                    "turn": turns, "model": opts["model"], "usage": cast(Usage, response.usage),
                    "sys": redact(system if isinstance(system, str) else ""), "tools": redact(tools_raw), "tail": ""}
                if ctx.subagentDepth:
                    record["subId"] = identity.get("runId", "")
                else:
                    record["msgs"] = redact(json.dumps(opts["messages"], ensure_ascii=False))
                try:
                    ctx.cacheAudit.record(cast(Any, record))
                except Exception:
                    pass  # 观测失败时，模型结果和工具派发照常完成。
        message = copy.deepcopy(response.message) if response is not None else {}
        content = message.get("content") or "".join(stream.text)
        if ctx.signal.is_set() or response is not None and response.cancelled:
            if content:
                # 取消时保留已展示的部分文字，收集到的工具调用不再派发。
                session.messages.append({"role": "assistant", "content": content})
            await save()
            return TurnResult("cancelled", "本轮已取消。")
        if response is None or response.status != "complete":
            failure = (response.error or "模型回答未完成，工具未执行。" if response is not None
                       else f"模型请求失败：{type(request_error).__name__}")
            if (stream.exposed or content or message.get("tool_calls") or
                    response is not None and (response.status == "partial" or response.deltas)):
                if content:
                    session.messages.append({"role": "assistant", "content": content})
                await save()
                return TurnResult("failed", failure)
            error = request_error or (response.error_exception if response is not None else None) or RuntimeError(failure)
            status = response.error_status if response is not None else getattr(error, "status", None)
            if isContextLengthError(error) or isContextLengthError(RuntimeError(failure)):
                await save()
                if compact and context_retries < 2:
                    context_retries += 1
                    stopped = await compress()
                    if stopped:
                        return stopped
                    continue
                return TurnResult("context_limit", "上下文仍达模型上限，记录已保留；请调整窗口或启动新会话。")
            if foreground and (status == 429 or isRateLimitError(error)):
                recovery_stopped = await model_recovery.recover_rate_limit()
                if recovery_stopped is not None:
                    return TurnResult(*recovery_stopped)
                continue
            if foreground and (isRetryable(error) or _TRANSIENT_MODEL_FAILURE.search(f"{type(error).__name__} {error}")
                               or isinstance(status, int) and 500 <= status <= 599):
                recovery_stopped = await model_recovery.recover_unavailable()
                if recovery_stopped is not None:
                    return TurnResult(*recovery_stopped)
                continue
            if forced:
                forcing_unsupported = True
                if notice:
                    notice("[服务端不接受强制工具调用，回退成普通重试…]")
                continue
            await save()
            return TurnResult("failed", failure)
        model_recovery.reset()
        try:
            saved_calls, calls = _safe_calls(message.get("tool_calls", []))
        except ValueError as exc:
            await save()
            return TurnResult("failed", str(exc))
        if not (isinstance(content, str) and content.strip()) and not calls:
            empty += 1
            if empty > policy.empty_max_retries:
                await save()
                return TurnResult("failed", "模型连续返回空回答，已停止本轮。")
            retry_reasoning = stream.empty_truncation
            forcing_unsupported = False
            if retry_reasoning:
                session.messages.append({"role": "system", "content": EMPTY_TRUNCATION_NOTE})
                await save()
                if notice:
                    notice("[思考耗尽输出预算，提示收敛后重试…]")
            continue
        empty = 0
        retry_reasoning = False
        forcing_unsupported = False
        context_retries = 0
        # 保留助手消息中的 Chat reasoningContent 与 Responses 加密推理项。
        # 后续请求需要这些历史，按角色和正文重建会丢失它们。
        assistant: dict[str, Any] = message
        assistant["role"] = "assistant"
        assistant["content"] = content
        if saved_calls:
            assistant["tool_calls"] = saved_calls
        session.messages.append(assistant)
        await save()
        if events.on_assistant_saved is not None:
            events.on_assistant_saved(assistant)
        if not calls:
            return TurnResult("complete")

        try:
            async with tool_batch_scope if tool_batch_scope is not None else nullcontext():
                batch = await executeToolBatch(
                    calls, registry, ctx, approve=authorization.approve, journal=journal,
                    authorize=authorization.authorize, authorize_batch=authorization.authorize_batch,
                    call_scope=authorization.call_scope, permission_mode=authorization.permission_mode,
                )
        except UnknownToolOutcome as exc:
            return TurnResult("outcome_unknown", str(exc))
        session.messages.extend(batch.messages)
        if wait_control is not None and wait_control.pending and journal is None:
            wait_control.rollback()
            return TurnResult("failed", "TaskWait 需要会话保存接口。")
        await save()
        if events.on_tool_message is not None:
            saved_by_id = {call["id"]: call for call in saved_calls}
            for tool_message in batch.messages:
                events.on_tool_message(saved_by_id[tool_message["tool_call_id"]], tool_message)
        if events.on_tool_result is not None:
            names = {call_id: name for call_id, name, raw in calls}
            for tool_message in batch.messages:
                events.on_tool_result(names[tool_message["tool_call_id"]], tool_message["content"])
        if batch.approval_incomplete:
            return TurnResult("failed", "权限确认未完成，现场已保存，本轮已停止。")
        if wait_control is not None and wait_control.pending:
            if ctx.signal.is_set():
                wait_control.rollback()
                return TurnResult("cancelled", "本轮已取消。")
            handle = wait_control.commit()
            if handle is not None:
                return TurnResult("waiting", wait=handle)
        projected = flushReadImages(session.messages)
        if projected is not session.messages:
            if journal is None:
                session.messages = projected
            else:
                await journal.replace_context(session, projected, reset_prompt=False)
        if on_tool_boundary is not None and not ctx.signal.is_set():
            # 助手和工具结果配对、图片投影也已提交后，才发布工具批产生的会话状态。
            await on_tool_boundary()
        batch_names = [name for _, name, _ in calls]
        running_background = (
            feedback.has_running_background() if feedback.has_running_background is not None else False
        )
        await tool_feedback.after_tool_batch(batch_names, batch.failure_messages(), running_background=running_background)
        if turns == policy.max_turns - 5 and notice:
            notice(f"[轮数提醒：接近最大轮数 {turns + 1}/{policy.max_turns:g}]")
        turns += 1
        boundary = True
    return TurnResult("cancelled", "本轮已取消。")
