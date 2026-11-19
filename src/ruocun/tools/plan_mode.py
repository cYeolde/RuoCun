"""提供进入计划模式和请求批准计划的两个工具。实际模式由当前回合提供的入口切换。"""
from typing import Any

from .schema import objectSchema
from .types import Tool, ToolContext


async def _enter(_args: dict[str, Any], ctx: ToolContext) -> str:
    if ctx.setMode is None:
        return "当前环境不支持模式切换。"
    if ctx.headless:
        return "无人值守（headless）会话无法接收退出规划所需的用户确认。本次未切换模式，请在已有授权内推进并说明结果。"
    ctx.setMode("plan")
    return "已进入规划模式(只读)。探索代码库、设计方案,完成后用 ExitPlanMode 退出。"


async def _exit(_args: dict[str, Any], ctx: ToolContext) -> str:
    if ctx.setMode is None:
        return "当前环境不支持模式切换。"
    if ctx.askChoice is not None:
        answer = await ctx.askChoice("已设计好方案,是否批准并退出规划模式开始实现?", ["批准,开始实现", "不批准,继续讨论"])
        if not answer.startswith("批准"):
            return f"用户未批准方案(回应:{answer})。仍在规划模式,根据反馈调整方案后再试。"
    ctx.setMode("normal")
    return "已退出规划模式,切回 normal。可以开始实现方案。"


enterPlanModeTool = Tool(
    name="EnterPlanMode",
    description=(
        "进入只读规划模式，先了解项目、确定改动范围并写好可验收的方案。方案完成时用 ExitPlanMode 提交给用户，获准后开始实现。"
    ),
    descriptionEn=(
        "Start read-only planning. Inspect the project and prepare an actionable plan with "
        "verification steps. Submit it with ExitPlanMode and wait for approval before "
        "implementation."
    ),
    capability="plan", shouldDefer=True,
    schema=objectSchema({}, []), handler=_enter,
)

exitPlanModeTool = Tool(
    name="ExitPlanMode",
    description="在交互会话中提交当前规划，获准后退出规划模式。",
    descriptionEn="Submit the current plan for approval in an interactive session and leave planning mode when approved.",
    capability="plan", shouldDefer=True,
    schema=objectSchema({}, []), handler=_exit,
)
