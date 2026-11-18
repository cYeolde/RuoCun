# 长任务怎样继续，又能回查原文

调试跑了几十轮，聊天记录里堆满了构建日志。下一轮可能只需要最近改动和失败位置，但等到验收时，仍可能需要核对某条断言的完整输出。若存把这两项需求交给不同的机制。发给模型的是经过压缩的会话视图，SQLite 会话库保存可回查的原始消息。

## 先裁剪日志，再决定要不要摘要

1. **按实际请求估算窗口压力。** 若存用即将发出的请求估算占用，考虑消息、工具定义、图片及输出余量。可以用 `/context` 查看当前估算和压缩阈值。[请求预算与触发入口](../src/ruocun/agent/context_runtime.py#L150)
2. **先在候选视图里裁剪过长的工具正文。** 可裁剪文本超过 8192 字符时，留下前 4096 和后 1024 字符，在省略处标记并附归档 ID。这一步如果已腾出足够空间，就可以直接提交候选。[工具结果裁剪](../src/ruocun/agent/compact.py#L127)
3. **空间仍不足时，摘要较早的对话。** 若存按预算留下近期消息，切点避开尚未配对的工具调用和结果。摘要请求读取连续的旧前缀，让模型服务有机会复用缓存。生成的一份摘要取代旧段，必须缩小被替换区段及最终请求。[切点与摘要生成](../src/ruocun/agent/compact.py#L179)
4. **原文、来源引用和新视图一起提交。** SQLite 事务确认后才切换会话视图。摘要为空、截断、未缩小、取消或保存未确认时，本轮停止并保留原视图。[候选提交](../src/ruocun/agent/context_runtime.py#L366) · [会话事务接口](../src/ruocun/session/conversation.py#L339)

## 要看证据时，用归档 ID 回查

如果摘要只写了「会员价测试失败」，而当前任务要核对失败详情，模型可以用摘要里的 ID 调用 `ArchiveRead`。它是按当前授权执行范围分页查询的只读工具。同一条证据也可以用 `/archive list` 和 `/archive read <ID>` 在终端查看。[ArchiveRead 工具](../src/ruocun/tools/archive_read.py#L13) · [SQLite 原文查询](../src/ruocun/session/durable_store.py#L1243)

压缩策略参考 DeepSeek Harness 固定提交 `e8f7b93a344964de3dca1ace9e72b6e4d6de87cb`。若存从 `compaction-basic` 借鉴完整请求预算、完整工具组切点、近期原文保留和旧摘要重整，也参考了配套裁剪插件的工具输出头尾保留策略。原文查询与事务提交由若存自己的 SQLite 会话库负责。[上游请求预算](https://raw.githubusercontent.com/deepseek-ai/deepseek-harness/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/compaction/compaction-basic/src/config.ts) · [上游工具输出裁剪](https://raw.githubusercontent.com/deepseek-ai/deepseek-harness/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/compaction/compaction-tool-result-pruner/src/index.ts) · [项目来源说明](../NOTICE.md)

继续读 [第 14 章 · 上下文放不下怎么办](learning/14-上下文放不下怎么办.html) 和 [第 15 章 · 摘要丢了细节怎样回查](learning/15-摘要丢了细节怎样回查.html)。
