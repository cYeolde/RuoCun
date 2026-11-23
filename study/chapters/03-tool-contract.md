# 第 3 章复习卡：模型请求工具后，谁真正执行

原文：[模型开口要读文件，谁真正去读？](../../docs/learning/revised/tool-contract.html)。本卡只把 CoreCoder 当设计对照；若存的实际行为以本仓库源码为准。

## 先回答 register 的疑问

`Tool` 对象包含 `name`、`description`、本地参数 `schema`、权限能力标签、真正执行的 `handler` 等字段。`registry.register(tool)` 以名字为键把**完整对象存在本地**。模型并不会读取 Python 注册表；程序还要调用 `toApiTools()`，把名称、描述和对外参数定义放进本次模型请求的 `tools`。模型提出调用后，程序再按名称找回本地对象，校验参数与权限，最后调用 `handler`。如果单独设置了 `apiParameters`，对外说明和本地 `schema` 可能不一致，应一起维护。

```text
本地登记 Tool → 本轮公布工具说明 → 模型提出工具名与 JSON 参数
→ 本地按名称查找 → 校验最终参数 → 权限/模式检查 → handler 执行
→ 真实结果按 tool_call_id 送回模型
```

源码：[`tools/types.py`](../../src/ruocun/tools/types.py)、[`tools/registry.py`](../../src/ruocun/tools/registry.py)、[`agent/runtime.py`](../../src/ruocun/agent/runtime.py)、[`tools/tool_batch.py`](../../src/ruocun/tools/tool_batch.py)。

## 同样没读到文件，分清失败发生在哪步

- `Read({"file":"version.txt"})`：工具名正确，但缺必填 `path`。JSON 能解析，**schema 校验失败**；处理器还没有打开文件。模型应改字段名。
- `Read({"path":"version.txt"})` 返回 `FileNotFoundError`：字段与类型已经过关，**在实际路径查找时失败**。核对当前 `ctx.cwd`、相对路径和真实文件位置。
- 路径在工作区外又未授权：**访问许可失败**。换成可访问路径，或由用户批准；不能把字段错误与权限拒绝混为一谈。
- 读取成功但读到 `examples/version.txt`：**工具操作成功不代表材料正确**。还需沿应用调用链找真正生效的文件。

若有前置 Hook 改写参数，批次会检查**改写后的最终参数**。参数错误会连同原调用 ID 返回模型，使模型知道该修哪里。源码：[`tools/tool_batch.py`](../../src/ruocun/tools/tool_batch.py)、[`tools/registry.py`](../../src/ruocun/tools/registry.py)。

## `Read` 的参数与多模态边界

`path` 必填；文本 `offset` 从 1 开始，默认 1；`limit` 是最多读取的**行数**，默认最多 2000 行。读第 8–10 行是 `{"offset":8,"limit":3}`；读第 20–24 行是 `{"offset":20,"limit":5}`。`offset`、`limit` 必须是符合 schema 的整数。

`Read` 支持文本，以及 PNG/JPG/GIF/WebP 图片（单张上限 5 MB，所选模型须支持视觉）。文本成功读取会记路径、修改时间、大小，供后续编辑检查基线。图片可用于观察界面，却不会建立源码文件的**文本编辑基线**；要改源码仍需读取目标文本。每次并行的图片 `Read` 有独立图片槽，避免一张图覆盖另一张；图片最终作为图像内容送入模型请求。用户输入也可附工作区内的 `@图片路径`，Windows 终端可用 `Alt+V` 附剪贴板图片。当前实现应表述为“支持图文”，不要泛称支持音视频。源码：[`tools/read_file.py`](../../src/ruocun/tools/read_file.py)、[`session/messages.py`](../../src/ruocun/session/messages.py)、[`tui/image_paste.py`](../../src/ruocun/tui/image_paste.py)。

## `ToolSearch`：先发现，再调用

`RepoMap` 已在本地注册，但标有 `shouldDefer=True`。普通请求的工具清单先不发它的完整说明，以节省重复输入。模型调用 `ToolSearch({"query":"RepoMap"})` 后，程序搜索并激活它，**这一步只返回用途和参数，还没有生成代码库摘要**。下一次请求才公布完整定义，模型再调用 `RepoMap` 才真正运行。首次使用多一步，平时节省工具说明长度。

“本地注册”“对模型可见”“执行被允许”是三层不同状态。隐藏说明不是安全边界：若名称和有效参数已知，注册表仍可能派发；真正限制来自执行时的模式、参数及权限检查。源码：[`tools/tools_for_mode.py`](../../src/ruocun/tools/tools_for_mode.py)、[`tools/tool_search.py`](../../src/ruocun/tools/tool_search.py)、[`tools/registry.py`](../../src/ruocun/tools/registry.py)。

## 一批工具怎样安排并行

模型若一次提出 `r_before`（读价格）、`r_rules`（读规则）、`e_price`（改价格）、`r_after`（再读价格），只按回包顺序排列并不能保证最后一读看到新价。若存把无持久副作用的独立读取放进并行组；遇到 `Edit` 这类持久副作用，先等前组结束，再单独执行编辑；编辑完成后才开始后续读取。组内最多八路并发。带事后 Hook 的调用也单独处理。执行结果最终按原调用顺序配回各自 `tool_call_id`。

因此，**调用 ID 管结果归谁，执行屏障管读到哪一版。** 这种按工具类别分组偏保守，即使读写不同文件也可能牺牲并行度；收益是同一批里读、改、再读的先后更可靠。未经批准的编辑不会启动，后读可能仍看到旧值。源码：[`tools/tool_batch.py`](../../src/ruocun/tools/tool_batch.py)。

## 原文 7 道面经与设计题

1. **新工具怎样注册、被发现并执行？** 定义名称、描述、schema、能力和 handler；注册表保存；模型看到本轮公布的 API 工具说明后提出调用；程序按名称找到本地对象，校验最终参数和权限，再执行并回流结果。
2. **工具列表太长怎么办？** 常用工具直接公布，少用工具延迟显示；`ToolSearch` 先找并激活，下一轮带完整定义。权衡是首次使用多一步。
3. **模型一次提出几个调用，哪些可并行？** 看数据依赖和副作用。两次独立读可并行；改价要等之前的读；检查新价的读要等编辑完成。
4. **选错工具或执行失败，怎样发现并告诉模型？** 分清未注册、参数错误、权限拒绝、文件不存在、读到错误文件；把具体错误按调用 ID 回给模型。成功回包仍要核对是否是生效文件。
5. **模型给 Read 填错字段，为什么本地还要查？** 工具说明只是引导模型，输出不可信。`file` 不是 `path`，本地 schema 在执行前拒绝，避免处理器误读别的文件。
6. **读了图片，可以直接编辑源码吗？** 不行。图片给视觉信息；编辑源码需要读取目标文本，建立原文与文件状态基线。
7. **读第 8–10 行，offset/limit 填什么？** `offset=8`、`limit=3`。起始行也计入三行。

## 额外高频追问

- **ToolSearch 找到 RepoMap 后，摘要已经生成了吗？** 没有；还要再调用 `RepoMap`。
- **模型能看到注册表里的 Python handler 吗？** 不能；只收到程序投影出的工具说明，handler 留在本地。
- **隐藏工具定义就不能执行了吗？** 不是安全保证。执行时仍须按模式和权限作决定。
- **回包排在 Edit 后，能证明读到新文件吗？** 不能单看回包排序；要确认读取实际在编辑完成后才开始。
- **模型还不知道旧文字，却在同一批里请求 Read 和 Edit，能保证 Edit 参数正确吗？** 不能。模型生成这一批时尚未见到读取结果；应先读，下一次模型请求再形成编辑参数。
- **CoreCoder 和若存是否同步？** 不是。课程用 CoreCoder 作设计对照：例如 CoreCoder 工具对象的 `schema()/execute()` 与若存的注册表/handler，以及批次并行策略。面试叙述若存行为时以若存源码为准。

## 90 秒面试表述

“若存把工具定义注册在本地，给模型的是名称、描述和参数 schema，执行函数不会发给模型。模型提出调用后，程序按名称查注册表，对最终 JSON 参数做本地校验，再经模式与权限判断后调用 handler。比如 `Read` 把 `path` 写成 `file`，会在读文件前被拒绝；字段正确但路径不存在，则是执行阶段的文件定位问题。少用的 RepoMap 先经 ToolSearch 激活，降低每轮工具说明开销。批量工具里，独立读可并行，但 Edit 等持久副作用会形成执行屏障，让读、改、再读按依赖顺序发生；每条结果仍用调用 ID 配对。”
