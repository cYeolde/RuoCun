"""WIRE-01/PROMPT: 冻结提示词组装及品牌/环境差异白名单。

预期独立来源：
- 冻结 src/prompt/system_prompt.ts:687-877 及 .test.ts:4-318
- R-05（提示词保真、品牌身份与真实 Python/Windows 环境替换形成差异白名单）
- ADR-0001 / ADR-0005 / D09:101（RUOCUN.md / .ruocun 原生根）
"""

from __future__ import annotations

import re
from importlib.resources import files

import pytest

from ruocun.prompt import system_prompt


def _prompt(**kw):
    base = {"modelId": "deepseek-v4-pro", "toolSummaries": "- Read:读文件\n- Write:写文件",
            "projectInstructions": "### RUOCUN.md @ .\n这是项目指令内容"}
    return system_prompt.buildSystemPrompt({**base, **kw})


# ---------------------------------------------------------------------------
# buildSystemPrompt (system_prompt.test.ts)
# ---------------------------------------------------------------------------


def test_zh_identity_line_and_tool_summaries():
    p = _prompt()
    assert "交互式智能助手" in p
    assert "- Read:读文件" in p
    assert "- Write:写文件" in p


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_fixed_system_is_identical_across_working_directories(lang):
    first = _prompt(lang=lang, cwd=r"D:\synthetic\first")
    second = _prompt(lang=lang, cwd=r"D:\synthetic\second")
    assert first == second
    assert r"D:\synthetic" not in first and "<ruocun-runtime-context>" in first


def test_zh_model_self_identification_and_vision():
    p = _prompt()
    assert "你当前运行的模型是 deepseek-v4-pro" in p
    assert "不支持图片输入" in p
    v = _prompt(modelId="kimi-k3")
    assert "你当前运行的模型是 kimi-k3" in v
    assert "这个模型支持图片输入" in v


def test_zh_reflect_switches_default_off():
    p = _prompt()
    assert "[审视者]" not in p
    assert "[纠偏者]" not in p
    assert "[反思]" not in p
    assert "审视与反思提醒" not in p


def test_zh_reflect_memory_only():
    p = _prompt(reflectMemoryEnabled=True)
    assert "[反思]" in p
    assert "[审视者]" not in p
    assert "[纠偏者]" not in p


def test_zh_reflect_challenger_only():
    p = _prompt(reflectChallengerEnabled=True)
    assert "[审视者]" in p
    assert "[纠偏者]" in p
    assert "[反思]" not in p


def test_zh_reflect_both():
    p = _prompt(reflectMemoryEnabled=True, reflectChallengerEnabled=True)
    assert "[审视者]" in p and "[反思]" in p and "[纠偏者]" in p


def test_project_instructions_section_and_default_none():
    assert "# 项目指令" in _prompt()
    assert "这是项目指令内容" in _prompt()
    assert "(无)" in _prompt(projectInstructions="")
    assert "见下方" not in _prompt()
    assert "{project_instruction_files}" not in _prompt()


def test_no_unfilled_placeholders():
    assert not re.search(r"\{[a-z_]+\}", _prompt())
    assert not re.search(r"\{[a-z_]+\}", _prompt(lang="en"))


def test_memories_injection_and_default():
    p = _prompt(memories="- 用户偏好 TypeScript\n- 本项目用 pytest")
    assert "用户偏好 TypeScript" in p
    assert "本项目用 pytest" in p
    assert "(暂无)" in _prompt()


def test_interactive_default_has_no_unattended_guidance():
    assert "AskUserQuestion 不会有人来回答" not in _prompt()
    assert "AskUserQuestion 不会有人来回答" not in _prompt(interactive=True)


def test_interactive_false_injects_session_guidance_and_todowrite():
    p = _prompt(interactive=False)
    assert "会话特定指引" in p
    assert "AskUserQuestion 不会有人来回答" in p
    assert "合理默认" in p
    assert "第一步必须先调用 TodoWrite 把任务拆成具体子步骤" in p


def test_interactive_true_has_no_headless_todowrite_requirement():
    assert "第一步必须先调用 TodoWrite 把任务拆成具体子步骤" not in _prompt()
    assert "第一步必须先调用 TodoWrite 把任务拆成具体子步骤" not in _prompt(interactive=True)


def test_en_identity_headers_and_model_note():
    p = _prompt(lang="en", toolSummaries="- Read:Reads a text file")
    assert "interactive intelligent assistant" in p
    for header in ["# Who You Are", "# Authority Hierarchy", "# Honesty",
                   "# Project Instructions", "# Tools", "# Memory"]:
        assert header in p
    assert "- Read:Reads a text file" in p
    assert "You are currently running as deepseek-v4-pro" in p
    assert "does not support image input" in p


def test_default_lang_is_zh():
    p = system_prompt.buildSystemPrompt({"modelId": "x", "toolSummaries": "- a:b"})
    assert "# 你是谁" in p
    assert "# Who You Are" not in p


def test_long_task_directives():
    assert "长任务自主模式" in system_prompt.LONG_TASK_DIRECTIVE
    assert "Long-task autonomous mode" in system_prompt.LONG_TASK_DIRECTIVE_EN


# ---------------------------------------------------------------------------
# WIRE-01 品牌/环境差异白名单（R-05 / ADR-0005 / D09:101）
# ---------------------------------------------------------------------------


def test_brand_deltas_replace_dao_identity_strings():
    p = _prompt()
    assert "DAO.md" not in p
    assert ".dao/settings.json" not in p
    assert "python/node" not in p
    assert "RUOCUN.md" in p
    assert ".ruocun/settings.json" in p


def test_packaged_system_prompt_templates_use_current_product_paths():
    templates = files("ruocun.prompt").joinpath("resources")
    for language in ("zh", "en"):
        text = templates.joinpath(f"system_prompt.{language}.txt").read_text(encoding="utf-8")
        assert ".ruocun/settings.json" in text and "RUOCUN.md" in text
        assert "dao" not in text.casefold() and "python/node" not in text
