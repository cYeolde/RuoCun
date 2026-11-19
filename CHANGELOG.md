# 更新日志

## 2.0.0

- 将模型故障恢复和工具执行后的反馈从 Agent 主循环拆出，按职责分组回合参数。
- 清理只由旧测试调用的会话、MCP、记忆、权限、终端、配置与 Skills 包装。迁移后的测试从正式入口验证输入接纳、恢复、防重放和工具行为。
- 同步第 04、05、06、16、19、20、22 章的源码摘录、链接与相关说明。
- 发布 Windows x64、CPython 3.11 安装包和源码包。

## 1.0.0

- 发布 Windows x64、CPython 3.11 安装包和源码包。
- 提供 22 章中文源码课程、课程示例和完整课程地图。
- 公开 Terminal-Bench 2.1 的 89 题自测记录和五题输入缓存对照精简表。
- 清理源码中的旧项目名称，退役旧的 SessionStart 标记兼容处理。

[安装与恢复](docs/install-and-recovery.md) · [开发与构建](docs/development.md) · [测评记录](docs/benchmark/README.md)
