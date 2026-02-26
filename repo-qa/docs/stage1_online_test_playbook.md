# Stage1 在线测试操作手册（含依赖安装、API 配置、批量测试）

> 目标：给你和 pwh 一份“拿来就跑”的在线测试手册，覆盖环境准备、依赖安装、API 配置、单题/消融/批量测试、结果检查与常见故障排查。

## 0. 前置条件

- Python 3.10+
- 可访问模型 API（默认 OpenAI 兼容）
- 仓库根目录：`repo-qa/`

---

## 1. 环境准备

### 1.1 初始化

```bash
cd repo-qa
bash setup.sh --yes
```

如果你的密钥在单独文件：

```bash
bash setup.sh --yes --env-file /path/to/secure.env
```

### 1.2 安装依赖

```bash
pip install -r requirements.txt
```

> 建议在虚拟环境中执行（conda/venv 均可）。

---

## 2. API 配置

在 `repo-qa/.env` 中至少配置：

```bash
OPENAI_API_KEY=sk-xxxx
OPENAI_API_BASE=https://api.openai.com/v1
```

若使用代理或公司网关，可设置：

```bash
HTTP_PROXY=http://your-proxy
HTTPS_PROXY=http://your-proxy
```

脚本默认会清理代理变量；若你必须保留代理，运行时添加 `--keep-proxy`。

---


## 2.1 Strategy/tool switches (YAML)

You can now control decomposition/graph tool behavior from `configs/*.yaml`:

- `enable_decomposition_tool`: turn decomposition tool on/off.
- `decompose_on_start`: if `false`, decomposition is lazy/on-demand (triggered during execution).
- `enable_dynamic_redecompose`: allow quality-triggered re-decompose.
- `max_decompose_calls`: upper bound for decomposition tool calls.
- `enable_graph_tools`: turn graph retrieve/validate tool calls on/off.
- `enable_dynamic_graph_tool_calls`: if `true`, call graph tools based on action intent/stagnation.
- `graph_tool_stagnation_steps`: threshold for stagnation-triggered graph tool calls.

Recommended baseline for online tests: keep `enable_decomposition_tool=true` and set `decompose_on_start=false` to test dynamic tool usage.

---

## 3. 运行前自检

### 3.1 语法检查

```bash
python -m py_compile \
  src/decomposition_action.py \
  src/subquestion_manager.py \
  src/graph_tools.py \
  src/agents/strategic_agent.py \
  scripts/run_single.py \
  scripts/run_ablation.py \
  scripts/run_batch.py \
  scripts/analyze_trajectory.py
```

### 3.2 单元测试（推荐）

```bash
pytest -q \
  tests/test_graph_tools.py \
  tests/test_decomposition_action.py \
  tests/test_analyze_trajectory.py \
  tests/test_subquestion_manager.py \
  tests/test_base_submit_gate.py \
  tests/test_decomposer.py \
  tests/test_graph.py \
  tests/test_filters.py \
  tests/test_run_batch.py \
  tests/test_tool_registry.py
```

---

## 4. 在线测试命令

### 4.1 单题（baseline）

```bash
python scripts/run_single.py --config baseline --question-file q1_timeout_exception.txt
python scripts/run_single.py --config baseline --question-file q2_config_loading.txt
python scripts/run_single.py --config baseline --question-file q3_default_agent_action_flow.txt
python scripts/run_single.py --config baseline --question-file q4_message_history_flow.txt
```

### 4.2 单题消融（baseline vs vanilla）

```bash
python scripts/run_ablation.py --question-file q1_timeout_exception.txt
python scripts/run_ablation.py --question-file q2_config_loading.txt
python scripts/run_ablation.py --question-file q3_default_agent_action_flow.txt
python scripts/run_ablation.py --question-file q4_message_history_flow.txt
```

### 4.3 批量测试（新增）

#### 一次跑完 q1~q4 的消融（推荐）

```bash
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions
```

#### 一次跑完 q1~q4 的 single + ablation

```bash
python scripts/run_batch.py --mode both --question-source auto --all-questions
```

#### 指定问题子集

```bash
python scripts/run_batch.py --mode ablation --question-source stage1 --question-files q2_config_loading.txt,q4_message_history_flow.txt
```

---

## 5. 结果分析

### 5.1 单条轨迹分析

```bash
python scripts/analyze_trajectory.py --config baseline
python scripts/analyze_trajectory.py --config vanilla
```

关注指标：
- `trajectory_schema_version`（应为 `stage1_v2.3`）
- `decomposition_quality`
- `decomposition_contract_version`
- `tool_call_count` / `tool_call_counter`
- `posterior_quality.evidence_yield`
- `posterior_quality.completion_rate`
- `quality_flags.missing_evidence_refs`

### 5.2 批量结果文件

`run_batch.py` 会在以下目录保存汇总：

- `experiments/comparison_reports/batch_run_<timestamp>.json`

建议比较：
- 不同题目下 baseline / vanilla 的失败率
- 失败任务的 `stderr_tail`
- 失败是否与代理/API/网络相关

---

## 6. 离线兜底（无 API）

如 API 不稳定，先走离线验证链路：

```bash
python scripts/run_batch.py --mode both --question-source auto --all-questions --offline
python scripts/run_offline_smoke.py
```

---

## 7. 常见问题排查

1. `OPENAI_API_KEY` 未设置
   - 检查 `.env` 是否加载，或显式 `export OPENAI_API_KEY=...`
2. 网络代理导致请求异常
   - 默认脚本会清代理；如必须代理，显式加 `--keep-proxy`
3. 任务完成但证据不足
   - 用 `analyze_trajectory.py` 看 `missing_evidence_refs`
4. 分解质量高但产出差
   - 检查 `entry_candidates` 是否可执行、`graph_tool_calls` 是否有效

---

## 8. 给 pwh 的最短路径（复制即用）

```bash
cd repo-qa
bash setup.sh --yes
pip install -r requirements.txt

# 写入 API 后先做快速检查
python -m py_compile src/decomposition_action.py src/subquestion_manager.py src/graph_tools.py src/agents/strategic_agent.py scripts/run_batch.py
pytest -q tests/test_decomposition_action.py tests/test_subquestion_manager.py tests/test_graph_tools.py tests/test_run_batch.py

# 在线批量测试
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions

# 看结果
python scripts/analyze_trajectory.py --config baseline
python scripts/analyze_trajectory.py --config vanilla
```


## SWE-QA 绑定前置步骤

在批量跑 SWE-QA 前，先生成带 repo/commit 绑定的题目索引：

```bash
python scripts/fetch_swe_qa_bench.py --max-questions 200
```

随后可直接运行：

```bash
python scripts/run_single.py --config baseline --question-file swe_qa_bench/swe_qa_0001.txt
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions
```
