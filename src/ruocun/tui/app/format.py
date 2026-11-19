"""从工具结果中提取任务清单。"""

import re


def parseTodoResult(content: str) -> list[dict[str, str]]:
    statuses = {"☐": "pending", "▶": "in_progress", "☑": "completed"}
    result = []
    for line in content.split("\n"):
        match = re.match(r"^([☐▶☑])\s+(.*)$", line.strip())
        if match:
            result.append({"status": statuses[match[1]], "content": match[2]})
    return result
