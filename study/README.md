# 若存源码与文档学习入口

本目录是面试学习补充材料。核对基线：`main` 提交 `5f588f5`（2026-11-21），发布版本 `v2.0.0`。课程正文以 [`docs/learning/课程学习地图.html`](../docs/learning/课程学习地图.html) 指向的 21 篇 `docs/learning/revised/` 为准；`docs/learning/` 根目录里另有早期页面和预览，编号与新版课程不同，不宜混读。

## 原仓库文档盘点

- [`README.md`](../README.md)：项目定位、功能展示、基准数字与快速安装。
- [`docs/install-and-recovery.md`](../docs/install-and-recovery.md)：Windows 安装、会话恢复、更新回退。
- [`docs/development.md`](../docs/development.md)：锁定依赖、构建 wheel、公开测试。
- [`docs/context-management.md`](../docs/context-management.md)：压缩、归档和回查。
- [`docs/memory-design.md`](../docs/memory-design.md)：长期记忆召回与经验生成。
- [`docs/windows-sandbox.md`](../docs/windows-sandbox.md)：可选 MXC 沙箱及边界。
- [`docs/benchmark/README.md`](../docs/benchmark/README.md)：Terminal-Bench 2.1 的记录和对照口径；逐题原始表见同目录 CSV/JSON/XLSX。
- [`CHANGELOG.md`](../CHANGELOG.md)、[`NOTICE.md`](../NOTICE.md)、[`LICENSE`](../LICENSE)、[`THIRD-PARTY-LICENSES.txt`](../THIRD-PARTY-LICENSES.txt)：版本与许可来源。

新版 21 篇均有“这一章带走什么”和“面经自测”，且都链接到仓库源码或测试。对仓库内 45 个 HTML 页面扫描了 2023 个本地引用，未发现缺失文件或锚点。这里的“覆盖完整”指**现有课程章节和站内导航齐备**，不等于所有工程主题都讲透，更不等于已完成跨平台运行验证。

本补充材料填四处学习空白：跨章节调用链、章节到源码的入口、可执行的复述/实验验收、当前机器与发布平台的差异。另把课程没有单列成章的 TUI、配置、观测、RepoMap/LSP 和平台能力汇在 [工程补遗](ENGINEERING-EXTRAS.md)。详见 [部署与验证](DEPLOYMENT.md)、[3 天计划](3-DAY-PLAN.md)、[面试演练](INTERVIEW.md)。

工具名称、用途和执行链另见 [Agent 工具速查](TOOL-GUIDE.md)。

逐章学习时的复习卡放在 `chapters/`：[第 1 章 · Agent Loop](chapters/01-agent-loop.md)、[第 2 章 · 模型输入](chapters/02-model-input.md)、[第 3 章 · 工具契约](chapters/03-tool-contract.md)、[第 4 章 · 文件编辑](chapters/04-file-editing.md)、[第 5 章 · 权限门](chapters/05-permission-gates.md)。后续每学完一章再补对应一篇。

## 一条请求如何穿过系统

```text
用户输入 / 恢复会话
  → cli.main → agent.runtime._run_session
  → 构造 prompt、账户、权限、工具注册表、会话
  → agent.loop.run_turn
  → context_runtime 预算检查 → client.resilient → client.client/SSE
  → 收齐模型 tool_calls → tools.tool_batch.executeToolBatch
  → hooks / 权限 / 执行器 / 持久化意图与结果
  → 把 tool_call_id 对应结果写回 session.messages → 再次请求模型
  → 完整回复且无工具调用时结束本轮
```

读源码时先从 [`src/ruocun/cli.py`](../src/ruocun/cli.py) 的 `main`、[`agent/runtime.py`](../src/ruocun/agent/runtime.py) 的 `_registry`/`_run_session`、[`agent/loop.py`](../src/ruocun/agent/loop.py) 的 `run_turn` 入手。工具派发在 [`tools/tool_batch.py`](../src/ruocun/tools/tool_batch.py)，模型协议在 [`client/client.py`](../src/ruocun/client/client.py) 与 [`client/sse.py`](../src/ruocun/client/sse.py)，持久会话在 [`session/conversation.py`](../src/ruocun/session/conversation.py) 与 [`session/durable_store.py`](../src/ruocun/session/durable_store.py)。

## 21 章速查：读什么、追哪里、讲什么

以下顺序采用新版学习地图。每章先读网页，再打开所列入口，最后不看材料口述该章问题。源码链接均指当前 checkout；课程中部分行号指 `v2.0.0` 标签，若之后同步上游，应以标签版本核对。

1. [Agent Loop](../docs/learning/revised/task-loop.html)：一轮里多次模型请求、工具结果回流、停止条件。追 `agent/loop.py:run_turn` 与 `tests/test_mvp_loop.py`。能画出 user → assistant/tool call → tool result → assistant 的序列。
2. [模型输入](../docs/learning/revised/model-input.html)：system、历史、项目规则、工作目录快照各在何时更新。追 `agent/run_agent.py`、`agent/runtime_context.py`、`project_doc.py`。能解释改了 `AGENTS.md` 后何时生效。
3. [工具契约](../docs/learning/revised/tool-contract.html)：注册、JSON 参数校验、工具搜索、批量派发。追 `tools/registry.py`、`tools/execute.py`、`tools/tool_batch.py`。能说清模型请求不等于本地执行。
4. [文件编辑](../docs/learning/revised/file-editing.html)：定位真实入口、读取基线、并发写入、端到端验证。追 `tools/edit_file.py`、`tools/read_file.py`、`tools/paths.py`。能解释旧文唯一仍可能需要重读。
5. [权限门](../docs/learning/revised/permission-gates.html)：最终参数、实际路径、模式与批准绑定。追 `permissions/runtime.py`、`permissions/gate.py`、`tools/tool_batch.py`。能说清 Hook 改路径后为何重新判定。
6. [模型协议](../docs/learning/revised/model-protocol.html)：SSE 字节/事件、交错参数片段、call ID 配对。追 `client/sse.py`、`client/client.py:ChatAccumulator`。能解释为什么未收齐整批调用不能先执行。
7. [请求恢复](../docs/learning/revised/request-recovery.html)：限流、上下文过长、部分响应、迟到回调。追 `client/resilient.py`、`agent/model_recovery.py`。能按“是否已暴露输出”决定重试。
8. [耐久执行](../docs/learning/revised/durable-execution.html)：意图先落盘、执行结果不明、重启后的核实。追 `session/durable_store.py`、`session/recovery.py`、`tools/tool_batch.py`。能区分未执行、已执行、未知三种状态。
9. [任务规划](../docs/learning/revised/task-planning.html)：计划是可核对目标，不等于执行。追 `agent/progress_advice.py`、`agent/tasks.py`、`tools/todo_write.py`。能指出每项待办的证据。
10. [后台命令](../docs/learning/revised/shell-lifecycle.html)：同一运行的转后台、等待、取消、通知消费。追 `tools/managed_shell.py`、`agent/background_runtime.py`、`agent/background_delivery.py`。能区分 task ID 与 run ID。
11. [交互控制](../docs/learning/revised/interactive-control.html)：用户补充要求、等待审批、旧回调防串线。追 `agent/session_scheduler.py`、`agent/input_broker.py`、`tools/ask_user.py`。能解释“已收到”与“模型已看到”的区别。
12. [子代理](../docs/learning/revised/subagents.html)：任务边界、独立会话、工作树、结果汇总。追 `agent/fork_agent.py`、`agent/tasks.py`、`agent/worktree.py`。能说明父子共享什么以及不共享什么。
13. [上下文压缩](../docs/learning/revised/context-compaction.html)：预算、裁剪、成组切点、摘要失败。追 `agent/context_runtime.py`、`agent/compact.py`。能解释为什么工具调用与回包不能切开。
14. [归档回查](../docs/learning/revised/archive-retrieval.html)：摘要 lineage、归档 ID、分页读原文。追 `session/archive.py`、`tools/archive_read.py`、`session/durable_store.py`。能从一条摘要找到原始测试回执。
15. [前缀缓存](../docs/learning/revised/prefix-cache.html)：稳定前缀、动态尾部、服务端真实用量。追 `session/cache_audit.py`、`client/client.py:buildRequestBody`。能说明高命中率为何不保证更低总成本。
16. [记忆使用](../docs/learning/revised/memory-use.html)：启动注入、按任务召回、来源有效性。追 `memory/inject.py`、`memory/retrieval.py`、`memory/validate.py`。能说明旧经验不能代替当前验证。
17. [经验生成](../docs/learning/revised/experience-learning.html)：候选、证据绑定、并发更新。追 `agent/controlled_learning.py`、`memory/store.py`。能区分用户偏好与有证据的技术做法。
18. [Skills](../docs/learning/revised/skills.html)：发现、加载、同名优先级与实际工具执行。追 `skills/discover.py`、`skills/skills.py`、`tools/skill.py`。能说明 Skill 只是流程文本，执行仍走工具和权限。
19. [MCP](../docs/learning/revised/mcp.html)：连接、工具清单、按需发现、远端写入不明。追 `mcp/mcp.py`、`agent/agent_mcp.py`、`tools/tool_search.py`。能说明客户端校验与服务端校验分别负责什么。
20. [Hooks](../docs/learning/revised/hooks.html)：前后置时点、改参后的再授权、回执。追 `hooks/hooks.py`、`hooks/journal.py`、`agent/agent_hooks.py`。能解释前置 Hook 的 allow 不能覆盖最终权限拒绝。
21. [评测与验收](../docs/learning/revised/completion-evidence.html)：任务结果、过程、成本、停止原因、样本局限。追 `docs/benchmark/README.md` 与 `tests/`。能设计固定用例与新旧版本对照，并诚实描述结论范围。

## 读文档时不要误讲的三件事

- `71/89` 是项目记录的 Terminal-Bench 2.1 自测结果；不能当作同模型、同试次数的官方排行榜复现。对照方法和缺失用量见基准文档。
- `1,983` 是 v2.0.0 发布说明中的离线验证数量，使用合成回包与本地对照；不能当作真实模型生产可靠性证明。
- 对主循环而言“无工具调用”是正常结束条件；对用户任务而言“完成”还需要结果证据，尤其是文件修改后的实际入口验证。
