# Windows 可选 MXC 沙箱

设置 `RUOCUN_SANDBOX=1` 可以为内置文件操作和命令启用额外写入边界。若存使用固定版本 Codex CLI 的本地沙箱子命令，模型与账户由若存自身管理。

## 启用

解包 [Codex CLI 0.169.0 Windows x64](https://github.com/openai/codex/releases/tag/rust-v0.169.0)，保留发行包目录结构。若存校验 `codex.exe` 的 SHA256：`ce1945eb440b5481ed1233ebaf32b7056ee7e4e452fa62ffe1cbfb26103cdee0`。

```powershell
$env:RUOCUN_SANDBOX = '1'
$env:RUOCUN_SANDBOX_CLI = 'C:\path\to\codex-0.169.0\bin\codex.exe'
python -m ruocun --cwd 'C:\path\to\project'
```

也可以将 CLI 放到用户目录的 `.ruocun/dependencies/codex/0.169.0/bin/codex.exe`。当依赖缺失、摘要不匹配或宿主 MXC 不可用时，启用沙箱的命令会失败并报告原因。

## 写入与扩展

内置 Bash、Monitor、Write 和 Edit 以启动项目为写入范围。命令需要额外目录时，交互审批会显示目录和本次命令。审批绑定到单次执行计划，后台恢复沿用原计划。命令的临时文件和常见工具缓存放在专用目录中，启用后首次运行可能需要重新下载依赖。

Hook、MCP 和 LSP 按各自的可信扩展配置执行。沙箱的运行边界对应内置文件和命令入口。网络默认可用，`RUOCUN_SANDBOX_NO_NET=1` 用于限制受管命令的网络。更多细节见 [MXC 上游文档](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/mxc-sandbox/README.md)。
