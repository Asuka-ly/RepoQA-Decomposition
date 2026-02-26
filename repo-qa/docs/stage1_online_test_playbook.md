# Stage1 在线测试 Playbook（操作+排障）

## 1) 环境准备
```bash
cd repo-qa
bash setup.sh --yes
pip install -r requirements.txt
```

`.env` 至少配置：
```bash
OPENAI_API_KEY=sk-xxxx
OPENAI_API_BASE=https://api.openai.com/v1
```

## 2) 运行命令（统一 question-source 语义）
```bash
# 生成 SWE-QA 绑定题目
python scripts/fetch_swe_qa_bench.py --max-questions 200

# 单题（SWE-QA）
python scripts/run_single.py --config baseline --question-file swe_qa_bench/swe_qa_0001.txt

# 批量（SWE-QA 主路径）
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions
python scripts/run_batch.py --mode both --question-source swe_qa --all-questions

# 回退（stage1）
python scripts/run_batch.py --mode single --question-source stage1 --all-questions

# 离线兜底
python scripts/run_batch.py --mode both --question-source auto --all-questions --offline
python scripts/run_offline_smoke.py
```

## 3) 最小验证清单
```bash
pytest -q tests/test_run_batch.py tests/test_run_single_binding.py tests/test_run_offline_smoke.py
python scripts/run_offline_smoke.py
```

## 4) 失败后第一时间看哪里（固定模板）
1. **题目绑定是否存在**：检查 `data/questions/swe_qa_bench/index.jsonl` 是否有 `repo/commit/instance_id`。
2. **批量参数是否正确**：确认 `run_batch` 使用了正确的 `--question-source`。
3. **仓库准备是否失败**：查看 `run_single/run_batch` 日志中的 clone/checkout 报错。
4. **API/网络问题**：若在线失败，先加 `--offline` 验证非网络链路。
5. **结果定位**：查看 `experiments/comparison_reports/batch_run_*.json` 的 `stderr_tail`。

## 5) 常见故障速查
- `OPENAI_API_KEY` 未生效：重新确认 `.env` 或环境变量。
- 代理引发请求异常：默认会清理代理；必须代理时显式 `--keep-proxy`。
- 题目跑完但证据不足：使用 `python scripts/analyze_trajectory.py --config baseline` 检查质量标记。
