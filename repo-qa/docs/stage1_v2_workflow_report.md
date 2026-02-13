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


## 8. 在线可视化与轨迹可读性改进（本次）

- 终端日志从“长块输出”改为“按 step 的紧凑摘要”，优先显示 action、输出前缀、returncode，降低阅读疲劳。
- 执行结束摘要额外输出 sub-question 满足率（`x/y satisfied`），减少在大段 history 中手工统计。
- final answer 在缺失显式 `## FINAL ANSWER` 时自动从历史对话回填结构化总结，避免空答案轨迹。

## 9. 动态工具调用策略（本次）

- `DECOMPOSE_WITH_GRAPH` 从“仅初始化调用”升级为“可二次调用”：当出现质量下降/高优先级停滞/持续低证据时触发重分解（带频率限制）。
- 图工具调用由“每步调用”改为“策略调用”：仅在检索型 action（`rg/grep/cat/nl/sed`）或证据连续停滞场景触发。
- 新增统计：`decompose_tool_calls`，用于评估动态分解带来的额外成本与收益。

## 10. 长期设计方向（年后重点）

- 分解与图的联合目标函数：不仅看 grounding coverage，还要看“每次图调用对 evidence 增量的贡献”。
- 将 `sub_question` 升级为“可执行查询计划单元”（含预期图路径、可验证断言、失败回退策略）。
- 形成 failure taxonomy：分解失败（plan 错）、检索失败（tool 用法错）、综合失败（答案覆盖不全），为后续 RL reward shaping 准备标签。


## 11. P0/P1 本轮落地（工具注册 + 轨迹 schema v2）

- 新增 `ToolRegistry`（`src/tool_registry.py`）：
  - 统一记录工具调用（tool_name / reason / success / latency / input_summary / output_summary）。
  - 当前接入工具：`DECOMPOSE_WITH_GRAPH`、`GRAPH_RETRIEVE`、`GRAPH_VALIDATE`。
- `StrategicRepoQAAgent` 接入 registry：
  - 分解与图工具调用通过 registry 封装后执行；
  - `statistics.tool_call_counters` 输出按工具聚合计数。
- trajectory 升级到 schema v2 最小版：
  - 新增 `trajectory_schema_version=stage1_v2.3`；
  - 新增 `tool_calls` 列表（完整工具调用轨迹）。
- 分析器升级：
  - `scripts/analyze_trajectory.py` 新增 `tool_call_count` 与 `tool_call_counter`。


## 12. 本轮修复（答案格式 + 终端可视化 + 子问题信号）

- 最终答案格式标准化：
  - 从“仅详细条目”改为 `Answer:` + `Detailed analysis:` 双段结构；
  - 自动去除尾部提交口令描述（如 `I will now submit ...`），避免污染最终答案。
- 终端可视化密度优化：
  - 每步输出改为紧凑两行（`Sxx | rc | action` + `output preview`）；
  - 在执行摘要中保留子问题中间状态统计（satisfied / blocked）。
- 子问题状态信号增强：
  - transition.signal 从“统一 action 字符串”升级为“每个 subq 的命中明细”；
  - 包含 `symbol_hits` / `required_hits` / `entry_hits` / `hit_score`，便于解释为何同一步中各子问题进度不同。

## 13. 稳定性回归结果（重构前锁稳）

- 针对 q1 离线流程复测：
  - 命令：`python scripts/run_single.py --offline --question-file q1_timeout_exception.txt`
  - 结果：流程完成，最终答案保持 `Answer + Detailed analysis` 双段；终端步骤输出保持紧凑；轨迹保存成功。
- 针对单元测试全量复测：
  - 命令：`pytest -q`
  - 结果：`34 passed, 3 skipped`。
- 结论：
  - 当前版本已具备“可继续迭代但先不做大改”的稳定基线；后续重构可在该基线上分阶段推进。


## 14. 稳定性补丁（提交门控与防漂移）

- 提交门控增强：
  - `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` 必须独立执行；
  - 若与读取/管道命令串联，直接拒绝并返回明确提示。
- 懒分解触发防漂移：
  - 对 `while/for/xargs/pipe/find` 等“全库脚本扫描”动作不触发懒分解，降低上下文语义污染风险。
- 重规划死循环抑制：
  - 提交动作（包括被拒绝提交）不再参与子问题进度更新与重规划计数，避免“提交失败 -> 无进展 -> 重分解”回路。


## 15. 补偿方案落地（A/B/C）与分解质量指标升级

- A（受控探索预算）：
  - 新增配置 `enable_scan_compensation / early_exploration_budget_steps / allow_broad_scan_after_stagnation`；
  - 在早期预算内默认阻断“全库脚本扫描”，仅在证据连续停滞后允许升级探索。
- B（软拦截+改写引导）：
  - 对宽扫描命令返回可执行的改写建议（先 `rg` 定位，再 `nl/sed` 取证），避免直接失败导致策略崩坏。
- C（图工具补偿）：
  - 当 sub-question 尚未初始化时，允许从任务文本抽取候选 symbols 触发 `GRAPH_RETRIEVE`，降低禁用宽扫描后的信息损失。

- 分解质量评估升级（relation-aware）：
  - 新增 `relation` 维度：
    - `symbol_overlap`：子问题间符号交叉强度；
    - `overlap_balance`：鼓励“有交叉但不过高”；
    - `dependency_signal`：priority 分层 + entry 跨模块分布；
    - `completeness_proxy`：required_evidence 覆盖与 unresolved_symbols 约束。
  - 说明：当前仍是“可解释代理指标”，尚不能严格等价于“语义完备性真值”；后续需结合人工标注或任务级回报做校准。


## 16. 主动图调度四点落地（本轮）

- ① 图调用前置（准前置）：
  - 在每步 observation 后立即执行图检索/校验，并向下一步决策注入 `GRAPH NEXT ACTIONS` 模板；
  - 实际效果是“在下一步动作生成前”给出图引导候选动作。
- ② 图结果结构化为动作模板：
  - 将 `GRAPH_RETRIEVE` 返回的 `file/line/symbol` 直接编译成 `rg` / `nl+sed` 命令建议，减少 LLM 自由度带来的偏航。
- ③ 图作为宽扫描守门器：
  - 当宽扫描被软拦截时，返回图引导改写建议（优先给出候选文件+行号附近读取模板），替代“直接拒绝不指导”。
- ④ relation 指标接入重规划：
  - 当 `overlap_balance/completeness_proxy` 明显失衡且证据停滞时，触发 relation 维度重分解信号（`relation_metric_imbalance`）。
