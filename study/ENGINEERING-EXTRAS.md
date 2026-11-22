# 21 章之外的工程模块

21 章覆盖了 Agent harness 的核心机制，但并非逐目录介绍整个仓库。面试官如果顺着“你熟悉整个项目吗”追问，以下模块也要能定位。它们是**补充阅读**，不另算原课程章节。

## 启动、配置与终端界面

- 入口：[`cli.py`](../src/ruocun/cli.py) 区分 `--version`、`--help`、演示/内部子进程和普通对话；普通对话进 [`agent/runtime.py`](../src/ruocun/agent/runtime.py)。
- 账户配置：[`config/profiles_store.py`](../src/ruocun/config/profiles_store.py) 负责读取、保存、切换配置；[`config/credential.py`](../src/ruocun/config/credential.py) 处理凭据；[`config/trust.py`](../src/ruocun/config/trust.py) 处理目录信任。向导在 [`tui/onboarding/onboarding.py`](../src/ruocun/tui/onboarding/onboarding.py)。
- TUI：[`tui/app/app.py`](../src/ruocun/tui/app/app.py) 显示活动与结果，输入和等待由 [`agent/input_broker.py`](../src/ruocun/agent/input_broker.py) 与调度器衔接。中文/英文在 [`i18n/i18n.py`](../src/ruocun/i18n/i18n.py)。

**自测：** 说出首次启动无账户、已有账户、`--continue` 三种路径从 CLI 到会话分别要装配什么；解释 UI 显示“收到工具输出”为什么不能代替会话持久保存。

## 代码库定位：RepoMap 与 LSP

第 4 章把它们作为代码定位工具介绍；深入时读 [`repomap/index.py`](../src/ruocun/repomap/index.py)、[`repomap/graph.py`](../src/ruocun/repomap/graph.py)、[`lsp/manager.py`](../src/ruocun/lsp/manager.py)、[`tools/lsp.py`](../src/ruocun/tools/lsp.py)。RepoMap 从仓库结构给出有限 token 的导航线索，LSP 需要对应语言服务；都不能替代对目标文件的实际读取与验证。

**自测：** 仓库中有两份同名 `prices.mjs` 时，RepoMap 或 LSP 给出候选后，你怎样确认页面真正调用哪一份？

## 观测与测试边界

[`obs/init.py`](../src/ruocun/obs/init.py) 实现可选 OpenTelemetry 初始化，入口需显式 `--obs`；其结果帮助定位调用耗时与错误，不是任务通过的判分器。公开测试在 [`tests/`](../tests/)；`pyproject.toml` 默认排除 `oracle`、`live`、`terminal`、`install` 标记测试。因此“默认 pytest 通过”只说明默认集合通过。发布说明的 1,983 个离线验证，以及真实模型/终端/安装验收，要分别陈述。

**自测：** 设计一个故障报告，分别列出模型请求日志、工具结果、持久会话记录、用户可见行为和测试断言；指出哪一项能证明任务完成，哪一项只能辅助诊断。

## 平台与功能取舍

当前发布 wheel 固定 Windows x64/CPython 3.11，持久会话还受受控 SQLite 运行库门控。可选 MXC 沙箱见 [`docs/windows-sandbox.md`](../docs/windows-sandbox.md)，默认不启用；不要把“有权限规则”讲成“所有扩展都在 OS 沙箱内”。[`schedule.py`](../src/ruocun/schedule.py) 的系统级定时在 Windows 本轮明确不支持；会话内 `/loop` 是另一功能。

**自测：** 面试官问“这个 Agent 是否跨平台、是否默认安全沙箱、是否支持系统级定时？”时，分别按代码和文档说清已验证范围与配置条件。
