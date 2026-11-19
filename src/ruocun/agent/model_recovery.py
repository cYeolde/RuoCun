"""管理单个回合的模型限流和服务不可用恢复。"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Literal, cast

from ..config.compat import resolve_env
from ..tools.types import ChoicePrompt

_WAIT_ON_RATE_LIMIT = "等待后用当前模型重试"
_STOP_ON_RATE_LIMIT = "中止本轮(稍后可用 /account 切换账号)"
_RATE_LIMIT_STOPPED = "已中止:当前账号触发限流(请求频率/配额超限)。可运行 /account 切换账号后重新发送消息。"

_Stop = tuple[Literal["cancelled", "failed", "model_unavailable"], str]


def _retry_setting(name: str, default: float, env: Mapping[str, str]) -> float:
    try:
        value = float(resolve_env(name, env) or 0)
    except ValueError:
        return default
    return value if value and math.isfinite(value) else default


class ModelRecovery:
    """处理已判定可以尝试恢复的请求失败，返回终止原因或继续请求。"""

    def __init__(
        self,
        env: Mapping[str, str],
        *,
        cancelled: Callable[[], bool],
        ask_choice: Callable[[], ChoicePrompt | None],
        save: Callable[[], Awaitable[None]],
        save_assistant_notice: Callable[[str], Awaitable[None]],
        notice: Callable[[str], None] | None,
        list_other_accounts: Callable[[], Sequence[str]] | None,
        switch_account_and_wait: Callable[[str], Awaitable[bool]] | None,
        on_model_unavailable: Callable[[], Awaitable[None]] | None,
    ) -> None:
        self._env = env
        self._cancelled = cancelled
        self._ask_choice = ask_choice
        self._save = save
        self._save_assistant_notice = save_assistant_notice
        self._notice = notice
        self._list_other_accounts = list_other_accounts
        self._switch_account_and_wait = switch_account_and_wait
        self._on_model_unavailable = on_model_unavailable
        self.reset()

    def reset(self) -> None:
        self._generic_retried = False
        self._rate_retries = 0

    async def _retry_delay(self, ms: float) -> _Stop | None:
        event_loop = asyncio.get_running_loop()
        deadline = event_loop.time() + max(0, ms) / 1000
        while not self._cancelled():
            remaining = deadline - event_loop.time()
            if remaining <= 0:
                return None
            await asyncio.sleep(min(remaining, .05))
        return "cancelled", "本轮已取消。"

    async def recover_rate_limit(self) -> _Stop | None:
        await self._save()
        if self._cancelled():
            return "cancelled", "本轮已取消。"
        if self._ask_choice() is not None:
            switch_account = self._switch_account_and_wait
            accounts = ({f"切到账号「{name}」重试": name for name in self._list_other_accounts()}
                        if self._list_other_accounts is not None and switch_account is not None else {})
            ask_choice = cast(ChoicePrompt, self._ask_choice())
            choice = await ask_choice("当前账号触发限流(请求频率/配额超限)。接下来怎么办?",
                                      [_WAIT_ON_RATE_LIMIT, *accounts, _STOP_ON_RATE_LIMIT])
            if self._cancelled():
                return "cancelled", "本轮已取消。"
            if switch_account is not None and choice in accounts:
                target = accounts[choice]
                try:
                    switched = await switch_account(target)
                except Exception:
                    # 配置可能已经确认写入，回执异常后直接保留现场。
                    return "failed", "限流时切换账号的结果未确认，原现场已保留；本轮已停止。"
                if self._cancelled():
                    return "cancelled", "本轮已取消。"
                if switched:
                    if self._notice is not None:
                        self._notice(f"[已切换到账号「{target}」,继续重试…]")
                    return None
                if self._notice is not None:
                    self._notice(f"[切换到账号「{target}」失败,仍在原账号]")
                return "failed", _RATE_LIMIT_STOPPED
            if choice != _WAIT_ON_RATE_LIMIT:
                return "failed", _RATE_LIMIT_STOPPED
        elif self._rate_retries >= _retry_setting("RATE_LIMIT_MAX_RETRIES", 5, self._env):
            return "failed", _RATE_LIMIT_STOPPED
        self._rate_retries += 1
        ms = min(_retry_setting("RATE_LIMIT_WAIT_MS", 5000, self._env) * self._rate_retries, 30000)
        if self._notice is not None:
            self._notice(f"[限流,等待 {max(0, ms) / 1000:g}s 后用当前模型重试…]")
        return await self._retry_delay(ms)

    async def recover_unavailable(self) -> _Stop | None:
        if not self._generic_retried:
            self._generic_retried = True
            await self._save()
            if self._notice is not None:
                self._notice("[请求失败(疑似过载/超时/网络问题),用当前模型重试一次…]")
            return await self._retry_delay(_retry_setting("HARD_RETRY_DELAY_MS", 1000, self._env))
        end = ("已停止本轮，已有进展、对话上下文和任务清单均已保留；可稍后重新发送消息继续，或用 /account 切换账号。"
               if self._ask_choice() is not None else "本次运行到此结束，已保留的上下文和任务清单不受影响。")
        note = "模型请求持续失败(疑似过载/超时/网络问题),重试一次仍未恢复。" + end
        await self._save_assistant_notice(note)
        if self._on_model_unavailable is not None and not self._cancelled():
            try:
                await self._on_model_unavailable()
            except Exception:
                return "model_unavailable", note + "后台停止结果未确认，请查看任务状态。"
        return "model_unavailable", note
