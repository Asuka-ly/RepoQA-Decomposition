# RepoQA-Decomposition (Stage1)

面向仓库级问答（Repo-QA）的 Stage1 系统：
- 用分解 + 图工具指导检索路径；
- 用提交门槛确保最终答案有可追溯证据；
- 用统一 runner 支持在线/离线/批量实验。

## 1) 当前架构（最小视图）
- **Agent 层**：`StrategicRepoQAAgent` / `VanillaRepoQAAgent`。
- **策略工具层**：`DECOMPOSE_WITH_GRAPH`、`GRAPH_RETRIEVE`、`GRAPH_VALIDATE`。
- **状态层**：`SubQuestionManager`（子问题进度、证据、重规划信号）。
- **安全层**：`BaseRepoQAAgent`（命令过滤、submit gate、宽扫描补偿）。
- **数据与运行层**：`run_single.py`、`run_batch.py`、`run_offline_smoke.py`。

## 2) 关键逻辑流
1. 读取问题（优先 SWE-QA 问题索引）。
2. 若题目有 `repo/commit` 绑定，动态 clone + checkout 到对应版本。
3. Agent 执行：分解 -> 图检索/验证 -> 定向读代码 -> 聚合证据。
4. submit gate 校验（步骤、证据、答案引用）通过后提交。
5. 轨迹落盘，供 `analyze_trajectory.py` 分析。

## 3) 快速开始
```bash
bash setup.sh --yes
pip install -r requirements.txt
```

### 3.1 SWE-QA 数据准备
```bash
python scripts/fetch_swe_qa_bench.py --max-questions 200
```

### 3.2 单题运行（默认建议）
```bash
python scripts/run_single.py --config baseline --question-file swe_qa_bench/swe_qa_0001.txt
```

### 3.3 批量运行
```bash
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions
python scripts/run_batch.py --mode both --question-source auto --all-questions
python scripts/run_batch.py --mode ablation --question-source stage1 --all-questions
```

### 3.4 离线验证
```bash
python scripts/run_offline_smoke.py
```

## 4) 文档导航
- 交接文档（主）：`docs/stage1_v2_handoff.md`
- 在线测试手册（操作步骤）：`docs/stage1_online_test_playbook.md`
- 阶段评审与计划：`docs/stage1_assessment_and_plan.md`

## 5) 当前边界与风险
- 大规模 SWE-QA 批跑会带来仓库缓存膨胀（`data/external/repo_cache`）。
- 远程 clone/fetch 失败时目前以显式报错为主，重试策略仍可增强。
