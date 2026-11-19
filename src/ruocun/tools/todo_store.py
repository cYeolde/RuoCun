"""为工具和界面提供共用的任务清单文本格式。"""

from __future__ import annotations

ICON = {"pending": "☐", "in_progress": "▶", "completed": "☑"}


def formatTodos(todos: list[dict[str, str]]) -> str:
    return "\n".join(f"{ICON[todo['status']]} {todo.get('activeForm', todo['content'])}" for todo in todos)
