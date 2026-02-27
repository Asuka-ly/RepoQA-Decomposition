# Stage1 重大重构方案（Decomposition Tool 化 + RL-Ready）

## 1) 重构后目录结构图（tree + 分层职责）

```text
repo-qa/
├── src/
│   ├── contracts/                # Data Contract 层：SWE-QA schema/adapter/validator
│   │   └── swe_qa.py
│   ├── planning/                 # Planning Tool 层：独立分解工具与重分解触发
│   │   ├── schema.py
│   │   ├── tool.py
│   │   └── replanner.py
│   ├── orchestrator/             # Agent Orchestrator 层：瘦状态机（可替换）
│   │   └── state_machine.py
│   ├── runtime/                  # Runtime 层：telemetry/report/runner 编排
│   │   └── reporting.py
│   └── agents/
│       └── strategic_agent.py    # 调用 planning tool，不再内嵌分解细节
├── scripts/
│   ├── run_single.py             # 支持统一 JSON report 导出
│   ├── run_batch.py
│   ├── demo_stage1_single.py     # 最小 single demo
│   └── demo_stage1_batch.py      # 最小 batch demo
└── docs/stage1_major_refactor_plan.md
```

## 2) 关键接口定义（dataclass schema）

- `SWEQARecord(question, repo, commit, instance_id, schema_version)`：严格样本契约。
- `InvalidSWEQARecord(reason_code, raw_preview)`：无效样本 reason code。
- `PlanSubQuestion` / `Plan(schema_version=decomposition_plan.v1)`：分解工具输出契约。
- `ReplanDecision(should_replan, reasons, trigger_source)`：重分解决策契约。
- `UnifiedTelemetry(tool_calls, decompose_calls, replan_events, evidence_coverage, completion_rate)`。
- `DecisionTraceExporter(schema_version=decision_trace.v1)`：导出 state/action/reward_proxy。

## 3) 迁移计划（Phase 拆分 + 风险回滚）

### Phase 1：Data Contract 落地
- 目标：SWE-QA adapter 只产出合法 record。
- 改动文件：`src/contracts/swe_qa.py`, `scripts/fetch_swe_qa_bench.py`。
- 风险：历史数据字段不全导致样本减少。
- 回滚：保留旧提取逻辑（`git revert` 单独回退 fetch PR）。
- 测试命令：`pytest tests/test_swe_qa_contract.py`。

### Phase 2：Decomposition Tool 独立包
- 目标：分解从 agent 内部抽离；输出带 version schema。
- 改动文件：`src/planning/*`, `src/agents/strategic_agent.py`。
- 风险：tool 接口切换影响原有策略。
- 回滚：恢复 `_run_decompose_tool` 使用旧 `DecompositionAction`。
- 测试命令：`pytest tests/test_planning_tool.py tests/test_strategic_tool_switches.py`。

### Phase 3：Orchestrator + Runtime 可观测
- 目标：增加瘦状态机与统一 telemetry / decision trace。
- 改动文件：`src/orchestrator/*`, `src/runtime/reporting.py`, `scripts/run_single.py`, `src/agents/base.py`。
- 风险：report schema 变更影响离线分析脚本。
- 回滚：run_single 退回旧输出，保留 trajectory。
- 测试命令：`pytest tests/test_run_single_report.py tests/test_run_batch.py`。

### Phase 4：Demo + 实验协议
- 目标：提供可直接执行的 single/batch demo 与论文实验计划。
- 改动文件：`scripts/demo_stage1_single.py`, `scripts/demo_stage1_batch.py`, 本文档。
- 风险：离线 demo 依赖 deterministic model 输出格式。
- 回滚：demo 仅删除新增脚本，不影响主运行链路。
- 测试命令：
  - `python scripts/demo_stage1_single.py`
  - `python scripts/demo_stage1_batch.py`

## 4) 最小可运行 Demo

- Single：`python scripts/demo_stage1_single.py`
- Batch：`python scripts/demo_stage1_batch.py`

## 5) 测试清单

- 单测：
  - 合约校验：`test_swe_qa_contract.py`
  - planning tool：`test_planning_tool.py`
  - 报告导出：`test_run_single_report.py`
- 集成：
  - `test_run_batch.py`
  - `test_strategic_tool_switches.py`
- 离线 smoke：
  - `python scripts/run_single.py --offline ... --report-file ...`

## 6) COLM/NeurIPS 实验计划（RL-ready）

- 对比实验：
  - Baseline agent（无工具化分解）
  - Toolized decomposition（固定分解）
  - Toolized + Dynamic Replan（stagnation/coverage/evidence）
- 分层统计：
  - 按 repo 规模、问题 hop 数、symbol grounding 覆盖率分桶。
- 关键指标：
  - completion rate, evidence coverage, replan frequency, tool call efficiency。
- 失败分析：
  - 无效样本过滤损失
  - 重分解过拟合（频繁 replan）
  - 低质量证据导致奖励代理偏置

## 7) 第一批可提交 PR 列表（标题 + 内容 + 验收）

1. **PR#1: 引入 SWE-QA 严格数据契约与 reason code 过滤**
   - 内容：新增 adapter/validator；fetch 脚本只写入合法样本。
   - 验收：输出样本均含 repo+commit；invalid reason code 可统计。
2. **PR#2: 分解能力独立为 Planning Tool 包**
   - 内容：新增 plan schema/tool/replanner；strategic agent 改为调用 tool。
   - 验收：分解工具可脱离 agent 单测；replan trigger 可配置。
3. **PR#3: 统一 telemetry 与 decision trace 导出**
   - 内容：新增 runtime reporting；run_single 输出标准 JSON report。
   - 验收：报告含 tool_calls/decompose_calls/replan_events/evidence_coverage/completion_rate/state-action-reward_proxy。
4. **PR#4: Single/Batch Demo 与迁移文档**
   - 内容：新增 demo 脚本与重构迁移文档。
   - 验收：离线模式可跑通，run_single/run_batch 无行为回退。
