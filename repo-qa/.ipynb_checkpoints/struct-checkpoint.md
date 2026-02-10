# 代码架构和工作流

## 代码结构：

```
/root/repo-qa/
│
├── README.md                          # 项目说明（包含快速开始）
├── requirements.txt                   # 依赖列表
├── setup.sh                           # 一键环境配置
│
├── src/                               # 核心源代码
│   ├── __init__.py
│   │
│   ├── graph.py                       # 代码图构建（单文件，258行）
│   ├── decomposer.py                  # 问题分解器（单文件，180行）
│   ├── filters.py                     # 命令过滤器（单文件，120行）
│   ├── injectors.py                   # 图知识注入器（单文件，150行）
│   ├── detectors.py                   # 模式检测器（单文件，100行）
│   │
│   ├── agent.py                       # 统一Agent（核心，300行）
│   ├── config.py                      # 配置类（单文件，80行）
│   │
│   └── utils.py                       # 工具函数（日志、Prompt模板等）
│
├── configs/                           # 实验配置文件
│   ├── baseline.yaml                  # 基线配置（全开）
│   ├── no_graph.yaml                  # 关闭图注入
│   ├── no_filter.yaml                 # 关闭命令过滤
│   └── minimal.yaml                   # 最小配置（用于调试）
│
├── scripts/                           # 可执行脚本
│   ├── run_single.py                  # 单问题测试
│   ├── run_ablation.py                # 消融实验（核心）
│   └── analyze_trajectory.py          # 轨迹分析
│
├── data/                              # 数据目录
│   ├── questions/                     # 测试问题集
│   │   ├── q1_timeout_exception.txt
│   │   ├── q2_config_loading.txt
│   │   └── q3_multi_module.txt
│   │
│   ├── trajectories/                  # 运行轨迹（自动生成）
│   │   └── 20250202_143022_baseline.json
│   │
│   └── results/                       # 实验结果（自动生成）
│       └── ablation_20250202.csv
│
├── tests/                             # 单元测试
│   ├── test_graph.py
│   ├── test_decomposer.py
│   └── test_filters.py
│
└── docs/                              # 文档
    ├── architecture.md                # 架构说明
    ├── experiment_guide.md            # 实验指南
    └── stage1_report.md               # Stage 1 总结（论文素材）
```

## 工作流

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 用户启动                                                  │
│    python scripts/run_single.py                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 初始化阶段                                                │
│    ├─ 加载配置 (configs/baseline.yaml)                      │
│    ├─ 初始化模型 (gpt-4o-mini)                              │
│    ├─ 创建环境 (LocalEnvironment)                           │
│    └─ 创建 RepoQAAgent                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Agent.run() 执行                                         │
│                                                             │
│  3a. 构建代码图 (如果 enable_graph=true)                    │
│      └─ CodeGraph.build(repo_path)                         │
│         ├─ 扫描 .py 文件                                    │
│         ├─ 提取类/函数定义 (节点)                           │
│         └─ 提取调用关系 (边)                                │
│                                                             │
│  3b. 战略分解                                               │
│      └─ StrategicDecomposer.decompose(question)            │
│         ├─ 提取关键符号 (DefaultAgent, TimeoutError...)    │
│         ├─ 从图中查询符号的邻居 (calls/called_by)          │
│         ├─ 构建 Code Graph Context                         │
│         ├─ 调用 LLM 分解问题                                │
│         └─ 返回 aspects + synthesis + estimated_hops       │
│                                                             │
│  3c. 构造增强任务 Prompt                                    │
│      └─ build_task_prompt()                                │
│         ├─ 添加路径引导 (cd /root/...)                      │
│         ├─ 列出所有 aspects 和 entry points                │
│         ├─ 添加命令约束 (不允许 sleep, python -c...)       │
│         └─ 添加完成指令 (echo "FINAL ANSWER: ...")         │
│                                                             │
│  3d. 调用父类 DefaultAgent.run()                           │
│      开始 LLM Agent 的观察-行动循环                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 观察-行动循环 (每一步)                                   │
│                                                             │
│  ┌─────────────────────────────────────────────────┐       │
│  │ Agent 生成 Action                               │       │
│  │ 例如: "cat environments/local.py"               │       │
│  └───────────────────┬─────────────────────────────┘       │
│                      │                                     │
│                      ▼                                     │
│  ┌─────────────────────────────────────────────────┐       │
│  │ get_observation() - 拦截点                      │       │
│  │                                                 │       │
│  │ Step 4a: 命令过滤 (CommandFilter)              │       │
│  │   ├─ 检查是否匹配禁止模式                       │       │
│  │   ├─ 如果是 sleep/timeout/python -c            │       │
│  │   │   └─ 返回 blocked message + 建议           │       │
│  │   └─ 否则继续                                  │       │
│  │                                               │       │
│  │ Step 4b: 执行命令                              │       │
│  │   └─ 调用 DefaultAgent.get_observation()      │       │
│  │      └─ 在 LocalEnvironment 中执行命令         │       │
│  │                                               │       │
│  │ Step 4c: 知识注入 (GraphInjector)             │       │
│  │   ├─ 检测命令是否是查看代码 (cat/grep)         │       │
│  │   ├─ 从命令中提取符号名                        │       │
│  │   ├─ 在图中查找符号的邻居                      │       │
│  │   └─ 追加 [GRAPH HINT] 到 observation         │       │
│  │                                               │       │
│  │ Step 4d: 模式检测 (PatternDetector)            │       │
│  │   ├─ 检查是否连续空搜索 (迷失)                   │       │
│  │   └─ 仅记录日志 (Stage 1)                        │       │
│  │                                                  │       │
│  │ Step 4e: 追踪状态                                │       │
│  │   └─ 记录 viewed_files                          │       │
│  └───────────────────┬─────────────────────────────┘       │
│                      │                                     │
│                      ▼                                     │
│  ┌─────────────────────────────────────────────────┐       │
│  │ 返回 observation 给 Agent                       │       │
│  └─────────────────────────────────────────────────┘       │
│                                                             │
│  循环直到 Agent 提交答案或超过 max_steps                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 结束阶段                                                  │
│    ├─ 保存轨迹 (data/trajectories/)                          │
│    │   └─ 包含：messages, decomposition, statistics          │
│    ├─ 打印统计报告                                           │
│    │   └─ total_steps, blocked_commands, injections...      │
│    └─ 返回 (status, output)                                 │
└─────────────────────────────────────────────────────────────┘
```
