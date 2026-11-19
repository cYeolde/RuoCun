"""维护当前进程内的模型上下文、对话配置和 token 用量。

运行时通过 Session 读取并更新对话，检查点由会话存储层提交。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Literal, TypedDict

from ..client.types import ChatMessage, Usage
from .cost import estimateCostByModel

Mode = Literal["normal", "plan"]


class UsageTotals(TypedDict):
    promptTokens: int
    completionTokens: int
    cacheHitTokens: int
    cacheMissTokens: int


CacheBustInfo = TypedDict("CacheBustInfo", {
    "from": float, "to": float, "promptTokens": int, "changed": list[str],
})


def _emptyUsage() -> UsageTotals:
    return {"promptTokens": 0, "completionTokens": 0, "cacheHitTokens": 0, "cacheMissTokens": 0}


class Session:
    def __init__(
        self, systemPrompt: str, model: str, *, env: Mapping[str, str] | None = None,
    ) -> None:
        self._env = env
        self.model = model
        self.mode: Mode = "normal"
        self.messages: list[ChatMessage] = [{"role": "system", "content": systemPrompt}]
        self.usage = _emptyUsage()
        self._modelUsage: dict[str, UsageTotals] = {}
        self.lastPromptTokens: int | None = None
        self.lastSentLength = 0
        self.budgetCNY: float | None = None
        self._lastCacheRatio: float | None = None
        self._cacheBustWarner: Callable[[CacheBustInfo], None] | None = None
        self._prevFp: dict[str, str] | None = None
        self._curFp: dict[str, str] | None = None

    def onCacheBust(self, fn: Callable[[CacheBustInfo], None]) -> None:
        self._cacheBustWarner = fn

    def notePrefix(self, fp: dict[str, str]) -> None:
        self._prevFp = self._curFp
        self._curFp = fp

    def addUsage(self, u: Usage, model: str | None = None) -> None:
        """累加本次模型调用的 token 和费用依据。"""
        selected = self.model if model is None else model
        prompt = u.get("prompt_tokens", 0) or 0
        completion = u.get("completion_tokens", 0) or 0
        hit = u.get("prompt_cache_hit_tokens", 0) or 0
        miss = u.get("prompt_cache_miss_tokens", 0) or 0
        bucket = self._modelUsage.setdefault(selected, _emptyUsage())
        for totals in (self.usage, bucket):
            totals["promptTokens"] += prompt
            totals["completionTokens"] += completion
            totals["cacheHitTokens"] += hit
            totals["cacheMissTokens"] += miss

    def addPrimaryUsage(self, u: Usage, model: str) -> None:
        """登记工具循环的模型调用，并更新该循环的上下文和缓存诊断。"""
        self.addUsage(u, model)
        prompt = u.get("prompt_tokens", 0) or 0
        hit = u.get("prompt_cache_hit_tokens", 0) or 0
        if model == self.model and prompt:
            self.lastPromptTokens = prompt
        if prompt >= 4000:
            ratio = hit / prompt
            if (self._lastCacheRatio is not None and self._lastCacheRatio >= .5
                    and self._lastCacheRatio - ratio >= .5 and self._cacheBustWarner is not None):
                self._cacheBustWarner({
                    "from": self._lastCacheRatio, "to": ratio, "promptTokens": prompt,
                    "changed": self._changedDims(),
                })
            self._lastCacheRatio = ratio

    def _changedDims(self) -> list[str]:
        if self._prevFp is None or self._curFp is None:
            return []
        keys = dict.fromkeys([*self._prevFp, *self._curFp])
        return [key for key in keys if self._prevFp.get(key) != self._curFp.get(key)]

    def cacheHitRatio(self) -> float:
        prompt = self.usage["promptTokens"]
        return self.usage["cacheHitTokens"] / prompt if prompt > 0 else 0

    def costCNY(self) -> float:
        return estimateCostByModel(self._modelUsage, self._env)

    def overBudget(self) -> bool:
        return self.budgetCNY is not None and self.costCNY() >= self.budgetCNY

    def setModel(self, model: str) -> None:
        self.model = model
