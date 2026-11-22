# 部署与验证：当前机器和以后 Windows 环境

## 当前状态

源码已在本机 macOS checkout。该仓库的 `pyproject.toml` 固定 `Python ==3.11.*`，`hatch_build.py` 强制 wheel 标签 `py311-none-win_amd64`。普通会话启动时，`agent/runtime.py` 会调用 `session/runtime.py:verify_controlled_runtime`；其中明确拒绝非 `win32` 平台。因此本机适合阅读、搜索和编辑源码，不能将“终端程序可正常运行”写入验收记录。当前机器 `python3` 为 3.9.6，且未发现 `python3.11`、`uv`、Docker 或 Homebrew 命令。

不要为了在 macOS 上启动它而跳过 SQLite 运行库检查；那会改变项目的持久会话保证，使面试里的可靠性结论失去依据。

## 本地源码学习已可用

```bash
cd /Users/yeolde/Downloads/Projects/RuoCun
git remote -v
git tag --list
rg --files src/ruocun | wc -l
rg -n 'async def run_turn|executeToolBatch|verify_controlled_runtime' src/ruocun
```

按 [`README.md`](README.md) 的 21 章入口阅读。课程正文引用了 `v2.0.0` 标签的源码位置；若要逐行对照，可用 `git show v2.0.0:src/ruocun/agent/loop.py`，不必切走当前学习分支。

## 将来在 Windows x64 实际运行

使用原项目支持的 Windows x64 与 CPython 3.11；按 [上游安装文档](../docs/install-and-recovery.md) 从 v2.0.0 Release 下载发布 wheel，建立独立虚拟环境。先验证包和依赖，再运行交互入口：

```powershell
py -3.11 -m venv .venv
$py = (Resolve-Path .venv/Scripts/python.exe).Path
& $py -I -X utf8 -m pip install .\ruocun-2.0.0-py311-none-win_amd64.whl
& $py -I -X utf8 -m pip check
& $py -I -X utf8 -m ruocun --version
& $py -I -X utf8 -m ruocun --help
& $py -I -X utf8 -m ruocun --cwd 'C:\path\to\disposable-practice-repo'
```

首次启动向导配置服务商、密钥与工作目录信任。用 `/doctor` 检查环境，用 `/help` 查命令，用 `/exit` 正常退出。第二次用相同 `--cwd` 加 `--continue`，验证能找到原会话。模型密钥不要写进仓库或提交到 fork。

如需源码构建，按 [上游开发文档](../docs/development.md) 的 Windows 锁文件、wheelhouse、`tools/run.py` 流程执行。不要在 macOS 上把 Windows 锁文件硬装进本地 Python。

## 运行验收清单

1. `pip check`、`--version`、`--help` 均成功；记录 Python 版本、系统架构、wheel 文件名和当前提交。
2. `/doctor` 未报告影响当前练习的关键失败；确认模型服务与项目目录。
3. 在一次性练习仓库里运行只读任务：让 Agent 找到一个函数并解释调用路径，保存工具结果与最终回答。
4. 再做一次有明确测试的可回退编辑；核对目标文件、相关测试和 `git diff`，不要只凭最终回复判定成功。
5. 退出后用 `--continue` 恢复；用 `/recovery` 检查有无未决副作用。

验收记录应包含命令、退出状态、可见结果和失败原因。真实模型行为和费用只能在完成上述运行后填写。
