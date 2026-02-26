# Stage1 v2 Workflow Report（摘要版）

## 1. Workflow Snapshot
- Input: question file（支持 SWE-QA 索引绑定）
- Resolve target: repo/commit -> local checkout
- Agent loop: decomposition + graph retrieve/validate + focused reads
- Guardrails: command filter + submit gate
- Output: final answer + trajectory artifacts

## 2. Key Observability Fields
- `statistics.decomposition_quality`
- `tool_calls`
- `subquestion_trace`
- `quality_flags.missing_evidence_refs`

## 3. What worked well
- 工具调用轨迹可复盘。
- 提交门槛降低了“空结论”提交概率。
- swe_qa 绑定流程显著提升问题-仓库匹配正确率。

## 4. Gaps
- 仓库缓存生命周期管理不足。
- 网络抖动时 clone/fetch 稳定性仍可提升。
- 文档需要持续保持“主文档+操作手册”双层结构，避免再膨胀。

## 5. Recommended Next Actions
1. 做 repo cache 管理与重试机制。
2. 增加批跑失败报告维度（绑定缺失、网络失败、证据不足）。
3. 保持文档精简，任何新增内容优先替换旧内容而非叠加。
