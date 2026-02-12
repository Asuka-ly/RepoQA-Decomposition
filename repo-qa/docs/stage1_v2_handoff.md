# Stage1 v2.0 交接文档（面向协作开发与实验复现）

## 0. 环境与测试（补全）

> 你提到的缺口（依赖下载/API 配置/测试命令）已补齐到独立操作手册：`docs/stage1_online_test_playbook.md`。

快速入口：

```bash
cd repo-qa
bash setup.sh --yes
pip install -r requirements.txt
# 配置 .env: OPENAI_API_KEY / OPENAI_API_BASE
python scripts/run_batch.py --mode ablation --all-questions
```


## 1. 给协作者（如 pwh）的快速入口

### 代码入口
- Agent 主流程：`src/agents/strategic_agent.py`
- 分解 Action：`src/decomposition_action.py`
- 分解器：`src/decomposer.py`
- 子问题状态：`src/subquestion_manager.py`
- 提交门槛：`src/agents/base.py`
- 轨迹分析：`scripts/analyze_trajectory.py`

### 核心新增（v2.x）
- 独立分解 Action `DECOMPOSE_WITH_GRAPH`。
- 分解质量分 `decomposition_quality`。
- 轨迹新增 `decomposition_action` 字段。
- P0/P1：新增 `ToolRegistry` 与 `tool_calls`（trajectory schema v2 最小版）。

## 2. 如何跑实验（最小命令）

```bash
# 单题（baseline）
python scripts/run_single.py --question-file q2_config_loading.txt

# 消融（baseline vs vanilla）
python scripts/run_ablation.py --question-file q4_message_history_flow.txt

# 轨迹分析
python scripts/analyze_trajectory.py --config baseline
python scripts/analyze_trajectory.py --config vanilla
```

## 3. 关键输出解释

- `statistics.decomposition_quality`：分解先验质量（0~1）。
- `decomposition_action.decomposition.action_metadata.contract_version`：分解契约版本（当前 stage1_v2.2）。
- `decomposition_action.quality`：质量明细（prior + posterior 占位）。
- `decomposition_action.decomposition.plan_order`：子问题执行顺序。
- `decomposition_action.decomposition.evidence_requirements`：每个子问题证据要求。
- `decomposition_action.decomposition.replan_triggers`：建议重规划触发器。
- `subquestion_trace`：在线状态更新和重规划事件。
- `tool_calls`：统一工具调用明细（name/reason/success/latency）。
- `statistics.graph_tool_calls`：图工具调用次数（用于评估图融合深度）。
- `quality_flags.missing_evidence_refs`：答案与轨迹证据都不足时为 true。

## 4. 协作分工建议

- A（算法/规划）：优化 decomposition quality 与 replan 策略。
- B（系统/工具）：图工具化（检索/验证接口）与 runner 稳定性。
- C（评测/数据）：构造问题集，维护 ablation 报告模板与轨迹对齐检查。

## 5. 当前风险与排查

1. 分解质量高但执行差：检查 entry_candidates 是否过泛。
2. 长答案无证据：检查 submit gate 是否命中 evidence 检查。
3. subq 满足率虚高：检查 evidence 是否被错误共享（targeted 逻辑）。

## 6. 建议的交接检查清单

- [ ] baseline/vanilla 各跑 1 次并保存轨迹
- [ ] analyzer 能正确输出 evidence_ref_count
- [ ] trajectory 中存在 decomposition_action 字段
- [ ] 至少一个问题触发有效 sub-question 更新
