# Stage1 v2 交接说明（精简）

## 架构关键点
- 题目来源切换到 SWE-QA 绑定路径：`fetch -> index -> run_single/run_batch`。
- 题目索引持久化 `repo/commit/instance_id`，执行时按绑定仓库与提交运行。
- 批量入口统一 `--question-source swe_qa|stage1|auto`，默认推荐 `swe_qa`。

## 已修复问题
- 题目与目标仓库错配：已通过题目索引绑定解决。
- run_batch 题源固化：已支持多来源显式切换。
- offline smoke 在当前 submit gate 约束下可稳定跑完 strategic/vanilla。

## 未解决问题
- 大规模批量时仓库缓存膨胀与网络失败重试策略需持续观察。
- 在线环境对代理/API 质量敏感，可能出现间歇性失败。

## 接手优先级
1. 保持 SWE-QA 主路径稳定，避免回到“固定 repo 跑题”。
2. 维护最小验证集合，优先保证核心链路可复现。
3. 控制文档和日志体积，新增内容必须有替代价值。

## 最小命令模板
```bash
# SWE-QA 主路径
python scripts/fetch_swe_qa_bench.py --max-questions 200
python scripts/run_single.py --question-file swe_qa_bench/swe_qa_0001.txt
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions

# stage1 回退路径
python scripts/run_batch.py --mode single --question-source stage1 --all-questions
```

## 交接 Checklist（<=8）
- [ ] 确认 `data/questions/swe_qa_bench/index.jsonl` 存在且含 repo/commit 字段。
- [ ] run_single 首题可按绑定仓库执行。
- [ ] run_batch 在 `swe_qa` 题源可批量启动。
- [ ] run_batch 在 `stage1` 题源可回退执行。
- [ ] 最小测试集通过（batch/binding/offline smoke）。
- [ ] offline smoke 成功结束。
- [ ] README 与任务书命令保持一致。
- [ ] 新增文档前先删除冗余段落。
