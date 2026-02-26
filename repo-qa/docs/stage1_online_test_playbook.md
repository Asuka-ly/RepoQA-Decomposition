# Stage1 在线测试手册（精简版）

> 只保留“可执行步骤 + 排障入口”。

## 1) 环境准备
```bash
cd repo-qa
bash setup.sh --yes
pip install -r requirements.txt
```

配置 `.env`：
- `OPENAI_API_KEY`
- `OPENAI_API_BASE`（若使用代理网关）

---

## 2) SWE-QA 前置
```bash
python scripts/fetch_swe_qa_bench.py --max-questions 200
```
输出：`data/questions/swe_qa_bench/index.jsonl`（包含 repo/commit 绑定）。

---

## 3) 运行命令

### 3.1 单题
```bash
python scripts/run_single.py --config baseline --question-file swe_qa_bench/swe_qa_0001.txt
```

### 3.2 批量
```bash
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions
python scripts/run_batch.py --mode both --question-source auto --all-questions
python scripts/run_batch.py --mode ablation --question-source stage1 --all-questions
```

### 3.3 离线验证
```bash
python scripts/run_offline_smoke.py
```

---

## 4) 核心检查点
- 运行日志中应出现题目绑定信息（repo/commit 或 binding mode）。
- strategic 轨迹应含 `tool_calls`、`subquestion_trace`。
- 最终 answer 应出现 `file.py:line` 证据引用。

---

## 5) 失败排查（按顺序）
1. **环境问题**：先看 `.env` 与 API 可用性。
2. **绑定问题**：检查 `index.jsonl` 是否包含当前题目的 repo/commit。
3. **执行问题**：看 batch 报告中的 `stderr_tail`。
4. **证据不足问题**：用 `python scripts/analyze_trajectory.py --config baseline` 查看证据与提交门槛指标。

---

## 6) 最小回归命令
```bash
pytest -q tests/test_run_batch.py tests/test_run_single_binding.py tests/test_run_offline_smoke.py
pytest -q
```
