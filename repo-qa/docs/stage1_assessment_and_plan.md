# Stage1 评审与计划（精简）

## 1) 评审结论

### 已达成
- 工具化分解与图检索已落地，轨迹可审计。
- submit gate 可抑制过早提交。
- SWE-QA question->repo->commit 绑定链路打通。

### 主要收益
- 运行流程从“固定仓库猜答案”升级为“按题绑定仓库取证”。
- 交付形态从“单脚本实验”升级为“单题/批量/离线统一流程”。

## 2) 当前风险
- repo cache 在大批次下可能持续增长。
- clone/fetch 异常处理偏直接失败，重试策略不足。
- 文档历史包袱仍可能回流（新增多、删减少）。

## 3) 下一阶段计划（P0/P1/P2）

### P0（必须）
- clone/fetch 增加重试与错误分级。
- 增加 repo cache 清理命令与阈值策略。

### P1（建议）
- batch 报告增加“绑定覆盖率”和“失败原因分桶”。
- 补一条端到端 smoke（fetch -> single -> batch）CI 任务。

### P2（优化）
- 进一步压缩 prompt 与日志冗余，降低 token 消耗。
- 为后续 RL 数据整理统一 trajectory schema 文档。

## 4) 验收标准
- 关键测试通过（run_single_binding / run_batch / offline_smoke）。
- 至少一次 swe_qa 批跑成功，并能确认 target repo 与题目绑定一致。
- 交接文档可独立指导新同学跑通流程。
