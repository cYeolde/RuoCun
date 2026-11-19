"""从启动参数、环境与区域设置解析终端语言，按语言格式化消息，并持久化用户的语言选择。"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

from ..config.settings_store import setUserSetting
from ..platform.windows.durable_file import local_path
from .messages.en import en
from .messages.zh import zh

Lang = Literal["zh", "en"]
_current: Lang = "en"


def _explicit(value: str | None) -> Lang | None:
    text = (value or "").lower()
    return "zh" if text.startswith("zh") else "en" if text.startswith("en") else None


def resolveLang(env: Mapping[str, str], settingsLang: str | None = None) -> Lang:
    explicit = env.get("RUOCUN_LANG")
    locale = env.get("LC_ALL") or env.get("LC_MESSAGES") or env.get("LANG", "")
    return _explicit(explicit) or _explicit(settingsLang) or ("zh" if locale.lower().startswith("zh") else "en")


def setLang(lang: str) -> None:
    if lang not in ("zh", "en"):
        raise ValueError("lang must be zh or en")
    global _current
    _current = cast(Lang, lang)


def getLang() -> Lang:
    return _current


def t(key: str, *args: str | int | float) -> str:
    raw = (zh if _current == "zh" else en).get(key, key)
    return re.sub(r"\{(\d+)\}", lambda match: str(args[int(match[1])]) if int(match[1]) < len(args) else match[0], raw)


def _file(userRoot: Path | None) -> Path:
    path = (userRoot if userRoot is not None else Path.home() / ".ruocun") / "settings.json"
    return local_path(path) if sys.platform == "win32" else path.absolute()


def readUserLang(*, userRoot: Path | None = None) -> str | None:
    try:
        value = json.loads(_file(userRoot).read_text(encoding="utf-8"))
        lang = value.get("lang") if isinstance(value, dict) else None
        return lang if isinstance(lang, str) else None
    except (OSError, ValueError, UnicodeError):
        return None


def writeUserLang(lang: str, *, userRoot: Path | None = None) -> None:
    if lang not in ("zh", "en"):
        raise ValueError("lang must be zh or en")
    root = userRoot if userRoot is not None else Path.home() / ".ruocun"
    setUserSetting(root, "lang", lang)


def switchLang(lang: str, *, userRoot: Path | None = None) -> None:
    writeUserLang(lang, userRoot=userRoot)
    setLang(lang)
