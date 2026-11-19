"""从已确认的工具结果构造模型消息，并在批末投递 Read 图片。

已投递标记归属上下文检查点，工具账本中的可信结果仍按原样保留。
"""

from __future__ import annotations

import copy

from ..client.types import ChatMessage, ContentPart
from .contract import ToolResult


def isValidToolResult(result: object, call_id: str) -> bool:
    """检查旧文本结果或工具调用身份匹配的完整结果消息。"""
    if isinstance(result, str):
        return True
    if not isinstance(result, dict):
        return False
    if (result.get("role") != "tool" or result.get("tool_call_id") != call_id
            or not isinstance(result.get("content"), str) or "imageDelivered" in result):
        return False
    if "shellFailed" in result and type(result["shellFailed"]) is not bool:
        return False
    if "imageData" in result:
        image = result["imageData"]
        if (not isinstance(image, dict) or set(image) != {"base64", "mediaType"}
                or not isinstance(image["base64"], str) or not isinstance(image["mediaType"], str)):
            return False
    return True


def projectToolResult(result: ToolResult, call_id: str) -> ChatMessage:
    """还原结果文本及图片，留出仅供批次判断的状态。"""
    if isinstance(result, str):
        return {"role": "tool", "tool_call_id": call_id, "content": str(result)}
    message = copy.deepcopy(result)
    message.pop("shellFailed", None)
    return message


def flushReadImages(messages: list[ChatMessage]) -> list[ChatMessage]:
    """从当前上下文生成批末图片消息。已从上下文移除的工具结果不会从账本再次投递。"""
    pending = [index for index, message in enumerate(messages)
               if message.get("role") == "tool" and message.get("imageData")
               and not message.get("imageDelivered")]
    if not pending:
        return messages
    candidate = copy.deepcopy(messages)
    parts: list[ContentPart] = []
    for index in pending:
        image = candidate[index]["imageData"]
        parts.append({"type": "image_url", "image_url": {
            "url": f"data:{image['mediaType']};base64,{image['base64']}",
        }})
        candidate[index]["imageDelivered"] = True
    parts.append({"type": "text", "text": "[以上图片由 Read 工具读取,请基于图片内容回答用户的问题]"})
    candidate.append({"role": "user", "content": parts})
    return candidate
