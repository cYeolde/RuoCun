"""冻结width/theme/markdown/render/i18n等公开seam的来源断言，按模块逐步迁移。"""

import re

import pytest


def test_width_source() -> None:
    from ruocun.tui.width import displayWidth, padEnd
    assert [displayWidth(s) for s in ("ab", "张三", "a张", "")] == [2, 4, 3, 0]
    assert [padEnd(s, n) for s, n in (("张三", 6), ("ab", 5), ("张三", 4), ("abcd", 2))] == ["张三  ", "ab   ", "张三", "abcd"]


@pytest.mark.parametrize("tier", ["none", "truecolor", "ansi256", "ansi16"])
def test_notice_render_respects_terminal_color_capabilities(tier: str) -> None:
    from ruocun.tui.app.app import App
    from ruocun.tui.capabilities import Capabilities

    writes = []
    app = App(writes.append, caps=Capabilities(tier, True, 80))
    app.notice("渲染")
    out = "".join(writes)
    if tier == "none":
        assert out == "渲染\n"
    elif tier == "truecolor":
        assert "\x1b[38;2;" in out and out.endswith("渲染\x1b[39m\n")
    elif tier == "ansi256":
        assert "\x1b[38;5;" in out and out.endswith("渲染\x1b[39m\n")
    else:
        assert re.search(r"\x1b\[(3[0-7]|9[0-7])m", out)


def test_markdown_source_blocks_and_inline() -> None:
    from ruocun.tui.markdown import renderMarkdown
    assert "\x1b[1m" in renderMarkdown("# 标题")
    assert "标题" in renderMarkdown("# 标题")
    out = renderMarkdown("这是 **粗** 和 `码`")
    assert "\x1b[1m粗" in out and "\x1b[36m码" in out
    out = renderMarkdown("```\nconst a = 1; // **不加粗**\n```")
    assert "const a = 1; // **不加粗**" in re.sub(r"\x1b\[[0-9;]*m", "", out)
    assert "\x1b[1m" not in out
    assert "• 一\n• 二" in renderMarkdown("- 一\n- 二")
    highlighted = renderMarkdown("```python\nreturn 1\n```")
    assert "return 1" in re.sub(r"\x1b\[[0-9;]*m", "", highlighted)
    assert re.search(r"\x1b\[(?:3[0-7]|9[0-7]|38;)[0-9;]*m", highlighted)


def test_markdown_source_cjk_and_wrapped_table() -> None:
    from ruocun.tui.markdown import renderMarkdown
    from ruocun.tui.width import displayWidth
    out = re.sub(r"\x1b\[[0-9;]*m", "", renderMarkdown("| 名字 | 城市 |\n|---|---|\n| 张三 | 北京 |\n| 李 | 上海市 |"))
    body = [line for line in out.splitlines() if line.startswith("│") and ("张三" in line or "李" in line)]
    assert "┌" in out and len(body) == 2 and displayWidth(body[0]) == displayWidth(body[1])
    long = "很长的中文内容需要折行" * 6
    out = re.sub(r"\x1b\[[0-9;]*m", "", renderMarkdown(f"| 问题 | 为什么 |\n|---|---|\n| 短 | {long} |", 40))
    lines = [line for line in out.splitlines() if line.strip()]
    assert all(displayWidth(line) <= 40 and displayWidth(line) == displayWidth(lines[0]) for line in lines)
    assert "很长的中文内容需要折行很长的中文内容需要折行" in re.sub(r"[│┌┐└┘├┤┬┴─\s]", "", "".join(lines))


def test_i18n_source_resolution_and_dictionary() -> None:
    from ruocun.i18n.i18n import getLang, resolveLang, setLang, t
    from ruocun.i18n.messages.en import en
    from ruocun.i18n.messages.zh import zh
    assert set(zh) == set(en)
    assert resolveLang({"RUOCUN_LANG": "zh", "LANG": "en_US"}, "en") == "zh"
    assert resolveLang({"LANG": "en_US.UTF-8"}, "zh") == "zh"
    assert resolveLang({"LANG": "zh_CN.UTF-8"}) == "zh"
    assert resolveLang({"LANG": "fr_FR.UTF-8"}) == "en"
    assert resolveLang({"LC_ALL": "zh_CN.UTF-8", "LANG": "en_US"}) == "zh"
    assert resolveLang({}) == "en"
    assert resolveLang({"RUOCUN_LANG": "xx", "LANG": "zh_CN"}) == "zh"
    assert resolveLang({"RUOCUN_LANG": "zh-CN"}) == "zh"
    assert resolveLang({"DAO_LANG": "zh-CN"}) == "en"
    assert all("dao" not in value.casefold() for value in (*zh.values(), *en.values()))
    setLang("zh")
    assert getLang() == "zh" and t("onboard.done") == "✓ 设置完成,开始吧。"
    assert t("ui.notice.error", "boom") == "出错:boom"
    assert t("ui.detail.lines", 3) == "3 行"
    setLang("en")
    assert t("onboard.done") == "✓ Setup complete. Let's go."
    assert "SYNTHETIC_ENV" in t("key.envSource", "SYNTHETIC_ENV")
    assert t("no.such.key") == "no.such.key"
    assert t("ui.notice.error", "boom") == "Error: boom"
    assert t("onboard.progress", 2, 4) == "Step 2 / 4"


def test_i18n_source_settings_roundtrip(tmp_path) -> None:
    import json

    from ruocun.config.settings_store import setUserSetting
    from ruocun.i18n.i18n import readUserLang, writeUserLang
    from ruocun.platform.windows.durable_file import ensure_private_dir

    root = tmp_path / ".ruocun"
    ensure_private_dir(root)
    setUserSetting(root, "lang", "en")
    file = root / "settings.json"
    file.write_text(json.dumps({"permissions": {"allow": ["x"]}}), encoding="utf-8")
    writeUserLang("zh", userRoot=root)
    assert readUserLang(userRoot=root) == "zh"
    assert json.loads(file.read_text("utf-8"))["permissions"] == {"allow": ["x"]}
