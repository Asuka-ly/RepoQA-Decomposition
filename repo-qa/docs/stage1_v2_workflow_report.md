# Stage1 v2.0 工作流与数据流报告（问题分解 Action/Tool）

## 1. 背景与目标

本阶段不进入 RL（Stage2），聚焦把“问题分解”从提示增强步骤升级为**独立 action/tool**，并形成可观测、可评估、可交接的工程形态。

目标：
- 把分解输出变成可执行 contract（sub-question + evidence + exit criterion）。
- 建立分解质量估计（先验）。
- 打通轨迹侧保存（decomposition + quality + workflow trace）。

## 2. 新工作流（Workflow）

1. Build graph（可选）
2. `DECOMPOSE_WITH_GRAPH`（新 Action）
3. 初始化 sub-question state
4. 执行 agent loop（action/observation）
5. 在线更新 sub-question + replan signal
6. submit gate（证据+进度约束）
7. 保存完整 trajectory（含 decomposition action 结果）

## 3. 新数据流（Dataflow）

### 3.1 输入
- 原始问题 question
- 图上下文（symbol search + neighbors）

### 3.2 中间结构（Action 输出）
- `decomposition.sub_questions`
- `decomposition.action_metadata`
  - `action_name=DECOMPOSE_WITH_GRAPH`
  - `quality`
  - `contract_version=stage1_v2.2`
  - `required_subq_fields`
- `plan_order`
- `evidence_requirements`
- `replan_triggers`
- `quality_estimate`
- `workflow_trace`

### 3.3 运行时状态
- `SubQuestionManager.sub_questions`
- `SubQuestionManager.transitions`
- `SubQuestionManager.replan_events`

### 3.4 轨迹输出
- `decomposition_action`
  - decomposition
  - quality
  - workflow_trace
- `subquestion_trace`
- history/final_answer/stats

## 3.5 Action Contract（冻结）

`DECOMPOSE_WITH_GRAPH` 输出中每个 `sub_question` 必须包含：
- id
- sub_question
- hypothesis
- entry_candidates
- symbols
- required_evidence
- exit_criterion
- status
- priority
- evidence_found
- progress
- attempts

并在 `action_metadata` 中写入：
- action_name
- quality
- contract_version
- required_subq_fields
- plan_order
- evidence_requirements
- replan_triggers
- quality_estimate

## 4. 质量指标（当前实现）

`DecompositionAction._estimate_quality()`：
- prior: graph_grounding_coverage / entry_executability / subq_uniqueness
- penalties: duplicate_subq_penalty / generic_entry_penalty
- posterior: evidence_yield / completion_rate / answer_alignment（运行后更新）
- overall（先验-惩罚聚合）

## 5. 已知限制
- 质量评估目前是启发式分数，不是学习得到。
- replan 仍主要依赖 blocked 子问题事件。
- graph 仍以注入/检索辅助为主，尚未完全工具化（下一步）。

## 6. 图工具层（mock-first）

- `GRAPH_RETRIEVE(symbols)`：返回候选节点与 grounded 数。
- `GRAPH_VALIDATE(sub_questions)`：返回 grounding coverage 与 entry executability。

## 7. 下一步（Stage1 继续）

- 将 graph 能力扩展为显式工具调用（检索/验证）。
- 把 replan 触发从 blocked 扩展到“低证据增量”场景。
- 增加 decomposition quality 与执行效果（evidence yield）的关联分析报表。
