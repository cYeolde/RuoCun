"""在已提交的工具批之后更新进度提醒和反思状态。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence

from .progress_advice import POLL_TOOLS, createProgressAdvice
from .reflect_prompts import SELF_CHALLENGE_NUDGE
from .turn_health import (
    TurnOutcome,
    assessTurn,
    defaultHealthConfig,
    errSignature,
    initHealth,
)


class ToolBatchFeedback:
    def __init__(
        self, env: Mapping[str, str], *,
        cancelled: Callable[[], bool],
        append_feedback: Callable[[str], Awaitable[None]],
        notice: Callable[[str], None] | None,
        reflect: Callable[[str], Awaitable[str | None]] | None,
        self_challenge: bool,
        long_task: bool,
        interactive: bool,
        progress_advice: bool,
        productive_tools: Collection[str],
    ) -> None:
        self._health = initHealth()
        self._health_cfg = defaultHealthConfig(env)
        self._progress = createProgressAdvice(env)
        self._cancelled = cancelled
        self._append_feedback = append_feedback
        self._notice = notice
        self._reflect = reflect
        self._self_challenge = self_challenge
        self._long_task = long_task
        self._interactive = interactive
        self._progress_advice = progress_advice
        self._productive_tools = productive_tools

    async def after_tool_batch(
        self, batch_names: Sequence[str], failures: Sequence[str], *,
        running_background: bool,
    ) -> None:
        advice = self._progress.step(
            batch_names, runningBackground=running_background,
            interactive=self._interactive, enabled=self._progress_advice,
        )
        if advice and not self._cancelled():
            # 反思会读取当前会话，先提交本批的进度提醒。
            await self._append_feedback(advice)
            if self._progress.notice and self._notice:
                self._notice(self._progress.notice)

        if (self._reflect is None and not self._self_challenge) or self._cancelled():
            return

        progressed = any(name in self._productive_tools for name in batch_names) or bool(
            batch_names and running_background and all(name in POLL_TOOLS for name in batch_names)
        )
        outcome: TurnOutcome = {"progressed": progressed, "toolFailures": len(failures)}
        if failures:
            outcome["errSig"] = errSignature(failures[-1])
        decision = assessTurn(self._health, outcome, self._health_cfg, {"longTask": self._long_task})
        self._health = decision["next"]

        reflection_note = ""
        if self._reflect is not None and (decision["challenger"] or decision["refocuser"]):
            label = "审视者" if decision["challenger"] else "纠偏者"
            if self._notice:
                self._notice(f"[反思：{label}…]")
            verdict = await self._reflect("challenger" if decision["challenger"] else "refocuser")
            if verdict and not self._cancelled():
                reflection_note = f"[{label}]\n{verdict}"
        elif self._self_challenge and decision["challenger"]:
            reflection_note = SELF_CHALLENGE_NUDGE
        if reflection_note:
            await self._append_feedback(reflection_note)
