"""从当前工作目录构造仓库索引，并按令牌预算限制交给模型的内容。"""

from typing import Any

from ..repomap.index import buildRepoMap, repoMapTokenBudget, wrapRepoMapNotice
from .schema import objectSchema
from .types import Tool, ToolContext


async def _handler(args: dict[str, Any], ctx: ToolContext) -> str:
    root = ctx.cwd or ctx.workspaceRoot
    budget = args.get("max_tokens", repoMapTokenBudget(ctx.notificationEnv))
    result = await buildRepoMap(root, budget, signal=ctx.signal, refresh=args.get("refresh") is True)
    english = ctx.lang == "en"
    if not result.text:
        return (f"No supported-language source files found under {root} (supported: TS/JS/Python/Go/Rust/Java)."
                if english else f"在 {root} 下没找到支持语言的源文件(支持:TS/JS/Python/Go/Rust/Java)。")
    footer = ("\n(Scan limit reached. This map covers the files indexed so far.)" if english
              else "\n(注:仓库文件数超过扫描上限,地图只覆盖前一批)") if result.truncated else ""
    return wrapRepoMapNotice(result.text, english, result.fileCount) + footer


repoMapTool = Tool(
    name="RepoMap",
    description=((
        "生成代码库结构摘要。从支持的语言中提取定义签名，按依赖关系优先展示关键符号。用 refresh 强制重扫，max_tokens 限定输出预算。需要精确定位时结合 "
        "LSP 或 Grep。"
    )),
    descriptionEn=((
        "Build a compact map of definitions in supported languages. The map prioritizes "
        "symbols using repository dependencies. Set refresh to rescan or max_tokens to "
        "bound the output. Use LSP or Grep for precise locations."
    )),
    schema=objectSchema({
        "refresh": {"type": "boolean", "description": "本次跳过文件提取缓存并重新解析(默认 false)"},
        "max_tokens": {"type": "integer", "minimum": 256, "maximum": 16384,
                       "description": "token 预算覆盖(默认 RUOCUN_REPO_MAP_TOKENS 或 2048)"},
    }, []), capability="read", shouldDefer=True, handler=_handler,
)
