# Stage1 v2 交接文档（主文档）

> 目标：给下一位协作者最短路径理解“架构、逻辑流、方法、任务状态与下一步”。

## A. 架构总览（Architecture）

### A1. 分层
- **执行层**：`src/agents/strategic_agent.py`、`src/agents/base.py`
- **工具层**：`src/decomposition_action.py`、`src/graph_tools.py`、`src/tool_registry.py`
- **状态层**：`src/subquestion_manager.py`
- **图分析层**：`src/graph.py`
- **运行层**：`scripts/run_single.py`、`scripts/run_batch.py`、`scripts/run_offline_smoke.py`

### A2. 核心机制
- `DECOMPOSE_WITH_GRAPH`：生成结构化 sub-questions。
- `GRAPH_RETRIEVE` / `GRAPH_VALIDATE`：候选路径收敛与证据覆盖校验。
- Submit gate：控制“何时允许提交”，避免空答/早答。

---

## B. 逻辑流（Logic Flow）
1. **题目输入**：从 `data/questions/...` 读取。
2. **题目绑定仓库解析**：若问题来自 SWE-QA 索引，则读取 `repo/commit`。
3. **仓库定位**：`run_single.py` 动态 clone+checkout 到绑定版本（可用 `--repo-path` 覆盖）。
4. **Agent 循环**：分解 -> 图检索/验证 -> 定向读取 -> 子问题更新。
5. **提交判定**：submit gate 通过才结束。
6. **轨迹输出**：保存统计、subq trace、tool calls。

---

## C. 使用方法（Methods）

### C1. 数据准备
```bash
python scripts/fetch_swe_qa_bench.py --max-questions 200
```

### C2. 单题
```bash
python scripts/run_single.py --config baseline --question-file swe_qa_bench/swe_qa_0001.txt
```

### C3. 批量
```bash
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions
python scripts/run_batch.py --mode both --question-source auto --all-questions
python scripts/run_batch.py --mode ablation --question-source stage1 --all-questions
```

### C4. 离线冒烟
```bash
python scripts/run_offline_smoke.py
```

---

## D. 任务书（Question / Target / To Do / Done）

### D1. Question（我们要解决什么）
- 如何在 Repo-QA 中稳定做到：
  1) 问题与目标仓库版本严格绑定；
  2) 分解与检索可观测、可复盘；
  3) 最终回答具备可追溯证据。

### D2. Target（本阶段目标）
- Stage1 交付“可运行、可批跑、可审计、可交接”的基线系统。

### D3. Done（已完成）
- 工具化分解/图检索/图验证接入。
- submit gate + 命令过滤 + 宽扫描补偿机制落地。
- SWE-QA 问题绑定仓库（repo/commit）链路贯通。
- 单题/批量/离线 runner 与核心测试覆盖。

### D4. To Do（下一步）
- 增强 clone/fetch 失败自动重试与错误聚合。
- 增加 repo cache 生命周期管理（清理策略、上限控制）。
- 补充线上批跑观测面板（失败类型分桶、仓库绑定覆盖率）。

---

## E. 最小验收清单
- [ ] `fetch_swe_qa_bench.py` 成功生成索引。
- [ ] `run_single.py` 在 SWE-QA 题目上使用绑定 repo/commit。
- [ ] `run_batch.py --question-source swe_qa` 可执行。
- [ ] `run_offline_smoke.py` strategic/vanilla 均完成提交。
- [ ] `pytest -q` 通过。
