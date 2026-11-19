"""写入技能调用的 JSONL 记录，并按技能汇总调用情况。"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal, Protocol, TypedDict

from ..config.compat import resolve_env


class SkillTraceEvent(TypedDict):
    kind: Literal["loaded"]
    inputId: str
    ts: int
    name: str


class SkillStat(TypedDict):
    name: str
    loaded: int
    total: int


class SkillAuditSink(Protocol):
    def loaded(self, input_id: str, name: str) -> None: ...


class _Noop:
    def loaded(self, input_id: str, name: str) -> None:
        pass


class _Sink:
    def __init__(self, directory: Path) -> None:
        self.file = directory / "skill-trace.jsonl"
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def loaded(self, input_id: str, name: str) -> None:
        event: SkillTraceEvent = {
            "kind": "loaded", "inputId": input_id, "ts": time.time_ns() // 1_000_000, "name": name,
        }
        try:
            with self.file.open("a", encoding="utf-8", errors="backslashreplace", newline="\n") as trace:
                trace.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            pass


def createSkillAuditSink(sessionDir: str | Path, env: Mapping[str, str] | None = None) -> SkillAuditSink:
    values = os.environ if env is None else env
    specific = resolve_env("SKILL_AUDIT", values)
    if specific == "0" or (specific != "1" and resolve_env("AUDIT", values) == "0"):
        return _Noop()
    return _Sink(Path(sessionDir))


def summarizeSkillTrace(events: Iterable[Mapping[str, object]]) -> list[SkillStat]:
    groups: dict[str, tuple[set[str], int]] = {}
    for event in events:
        if event.get("kind") != "loaded" or type(event.get("ts")) is not int:
            continue
        name, input_id = event.get("name"), event.get("inputId")
        if not isinstance(name, str) or not (isinstance(input_id, str) or type(event.get("round")) is int):
            continue
        rounds, total = groups.setdefault(name, (set(), 0))
        if isinstance(input_id, str) and input_id:
            rounds.add(input_id)
        groups[name] = (rounds, total + 1)
    stats: list[SkillStat] = [{"name": name, "loaded": len(rounds), "total": total}
                             for name, (rounds, total) in groups.items()]
    return sorted(stats, key=lambda stat: (-stat["loaded"], -stat["total"]))


def formatSkillReport(stats: Iterable[SkillStat]) -> str:
    rows = []
    for stat in stats:
        name = stat["name"]
        padding = " " * max(0, 20 - len(name.encode("utf-16-le", errors="surrogatepass")) // 2)
        rows.append(f"  {name}{padding} 加载轮数 {stat['loaded']} · 总次数 {stat['total']}")
    if not rows:
        return "暂无技能加载记录(跑几轮带技能的任务后再看;RUOCUN_SKILL_AUDIT=0 会关闭记录)。"
    return "\n".join([
        "技能加载审计（本会话）",
        "  加载轮数按已确认输入 ID 去重；缺少输入 ID 的记录只计入总次数。",
        "  记的是模型实际加载了哪些 skill;'该加载却没加载'需 LLM 裁判判断(本表不含)。",
        *rows,
    ])
