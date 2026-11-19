"""轮末反思的实际模型请求和记忆筛选。"""

import asyncio
import json

import pytest

from ruocun.agent.unified_reflect import reflect
from ruocun.memory.distill import isCatalogNoise


@pytest.mark.parametrize(("texts", "expected"), [
    (["用户使用 test-driven-development 技能进行测试", "用户使用 Grep 工具(原 Grep)来搜索代码库",
      "用户维护了一个包含 31 个技能的本地技能库"], True),
    (["用户偏好将工具名从 Task/TodoWrite 改为 agent/TodoWrite"], True),
    (["用户在学 agent 原理,偏好讲机制", "示例项目面向个人开发者，强调低成本和本地运行",
      "验证必须基于实际证据,不能仅凭测试通过就声称完成"], False),
])
def test_catalog_noise(texts, expected):
    assert all(isCatalogNoise(text) is expected for text in texts)


def _call(text, requests):
    async def request(options):
        requests.append(options)
        return text
    return request


def _run(text, messages=(), options=None, **kwargs):
    requests = []
    result = asyncio.run(reflect(messages, options=options or {"model": "synthetic"},
                                 call=_call(text, requests), **kwargs))
    return result["memories"], requests[0]


def test_reflect_parses_fenced_json_and_checks_memory_content():
    body = {"memories": [
        {"title": "讲解偏好", "text": "用户在学 agent 原理,偏好讲机制", "type": "user", "importance": 7, "confidence": 0.6},
        {"title": "临时信息", "text": "随口一句", "type": "episodic", "importance": 2},
        {"title": "合成敏感记录", "text": "sk" + "-" + "A" * 24, "type": "semantic"},
    ]}
    selected, _ = _run("```json\n" + json.dumps(body, ensure_ascii=False) + "\n```", [{"role": "user", "content": "..."}])
    memory, = selected
    assert (memory["title"], memory["type"], memory["importance"], memory["confidence"]) == ("讲解偏好", "user", 7, 0.6)


def test_reflect_accepts_feedback_type():
    selected, _ = _run(json.dumps({"memories": [
        {"title": "讲解顺序", "text": "先答原理再动手。为什么:用户在学机制。怎么用:问题先给结论与原理。",
         "type": "feedback", "importance": 8},
    ]}, ensure_ascii=False))
    memory, = selected
    assert (memory["type"], memory["importance"]) == ("feedback", 8)


def test_reflect_fork_preserves_prefix_tools_and_reasoning():
    tools = [{"type": "function", "function": {"name": "Read"}}]
    messages = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "hi"}]
    _, request = _run('{"memories":[]}', messages, {"model": "synthetic", "tools": tools}, fork=True, reasoningEffort="max")
    assert request["tools"] == tools and request["parallelToolCalls"] is True
    assert request["extra"] == {"reasoning_effort": "max"}
    assert request["messages"][:-1] == messages and request["messages"][-1]["role"] == "user"


def test_reflect_nonfork_drops_tools_and_disables_thinking():
    _, request = _run('{"memories":[]}', [{"role": "user", "content": "hi"}],
                      {"model": "synthetic", "tools": [{"type": "function", "function": {"name": "Read"}}]})
    assert "tools" not in request and request["extra"]["thinking"] == {"type": "disabled"}


def test_reflect_non_json_returns_empty():
    assert _run("抱歉无法")[0] == []


def test_reflect_nonfork_excludes_original_system_messages():
    _, request = _run('{"memories":[]}', [
        {"role": "system", "content": "SYSTEM_PROMPT_SENTINEL_应被排除"},
        {"role": "user", "content": "我用 pnpm"}, {"role": "assistant", "content": "好的"},
    ])
    transcript = request["messages"][1]["content"]
    assert "SYSTEM_PROMPT_SENTINEL" not in transcript and "我用 pnpm" in transcript
