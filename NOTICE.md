# 若存 Code 发布须知

若存是面向 Windows Terminal 的 Python 编码助手，支持在终端中编辑代码、运行命令和恢复会话。

运行 `ruocun` 启动，进入后用 `/help` 查看命令，或用 `/doctor` 检查运行环境。

若存原创内容采用 [MIT 许可证](LICENSE)。随附组件的许可见 [第三方许可证](THIRD-PARTY-LICENSES.txt)。

上下文压缩参考 DeepSeek Harness 固定提交 `e8f7b93a344964de3dca1ace9e72b6e4d6de87cb`（MIT，Copyright 2026 DeepSeek）。参考内容包括 `compaction-basic` 的完整请求预算、近期原文保留、工具结果头尾裁剪、旧摘要重整，以及原文与模型投影的区分。[参考源码](https://github.com/deepseek-ai/deepseek-harness/tree/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb)

若存保留压缩失败时停止的策略，并使用现有 SQLite 事务、执行范围和权限体系保存原文归档。
