"""通用工具模块。

包含两类能力：
1) 路径/环境初始化（PathConfig）；
2) 运行时日志与任务提示词构建（setup_logger / build_task_prompt）。
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv


class PathConfig:
    """统一路径管理器。

输入：
    - 当前文件位置、环境变量（PROJECT_ROOT / TEST_REPO_PATH）。
输出：
    - project_root / mini_swe_agent_root / repo_qa_root 等关键路径。

功能：
    - 自动发现项目根目录；
    - 自动加载 `.env`；
    - 自动补充 Python 导入路径，减少脚本运行前手动配置。
    """

    def __init__(self):
        self.project_root = self._find_project_root()

        env_path = self.project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✓ Loaded .env from: {env_path}")
        else:
            user_config = Path.home() / ".config" / "mini-swe-agent" / ".env"
            if user_config.exists():
                load_dotenv(user_config)
                print(f"✓ Loaded .env from: {user_config}")
            else:
                print("⚠️  No .env file found")

        self.mini_swe_agent_root = self.project_root / "mini-swe-agent"
        self.repo_qa_root = self.project_root / "repo-qa"
        self._setup_python_path()

    def _find_project_root(self) -> Path:
        """向上搜索项目根目录（包含 mini-swe-agent 与 repo-qa）。"""
        current = Path(__file__).resolve()
        for parent in [current] + list(current.parents):
            if (parent / "mini-swe-agent").exists() and (parent / "repo-qa").exists():
                return parent

        if project_root := os.getenv("PROJECT_ROOT"):
            return Path(project_root)

        fallback = Path("/root/RepoQA-Project")
        if fallback.exists():
            return fallback

        raise RuntimeError("Cannot find project root! Please set PROJECT_ROOT in .env")

    def _setup_python_path(self):
        """把项目源码路径插入 `sys.path`，保证脚本可直接运行。"""
        paths_to_add = [
            str(self.mini_swe_agent_root / "src"),
            str(self.repo_qa_root),
        ]
        for p in paths_to_add:
            if p not in sys.path:
                sys.path.insert(0, p)
                print(f"✓ Added to sys.path: {p}")

    def get_test_repo_path(self) -> str:
        """返回默认测试仓库路径，可被 `TEST_REPO_PATH` 覆盖。"""
        return os.getenv("TEST_REPO_PATH", str(self.mini_swe_agent_root / "src" / "minisweagent"))

    def validate(self) -> bool:
        """检查关键路径是否存在，供运行前快速自检。"""
        checks = {
            "Project Root": self.project_root,
            "mini-swe-agent": self.mini_swe_agent_root,
            "repo-qa": self.repo_qa_root,
        }

        all_ok = True
        for name, path in checks.items():
            if path.exists():
                print(f"✓ {name}: {path}")
            else:
                print(f"✗ {name} NOT FOUND: {path}")
                all_ok = False
        return all_ok


PATH_CONFIG = PathConfig()


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """创建 stdout logger（避免重复注册 handler）。"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def build_task_prompt(task: str, repo_path: str, decomposition: Dict = None, config=None) -> str:
    """构建执行阶段任务提示词。

Args:
    task: 原始用户问题文本。
    repo_path: 待分析仓库根目录（会写入提示词）。
    decomposition: 可选的分解结果（含 sub_questions / aspects）。
    config: ExperimentConfig，用于控制工具提示与流程提示。

Returns:
    str: 供 agent.run(...) 使用的完整 prompt。

设计说明（最小侵入）：
    - 当分解存在时，提示词展示分解锚点；
    - 当分解未初始化时，提示词明确“可动态触发”；
    - 强化 FINAL ANSWER 的证据格式约束，减少空泛回答。
    """
    decomp_data = decomposition if decomposition is not None else {}
    subq_list = decomp_data.get("sub_questions")
    if isinstance(subq_list, list) and subq_list:
        aspects = sorted(subq_list, key=lambda x: x.get("priority", 99))
        use_subq = True
    else:
        aspects_list = decomp_data.get("aspects", [])
        aspects = sorted(aspects_list, key=lambda x: x.get("priority", 99))
        use_subq = False

    lines = [
        "You are a repository code-analysis agent operating in STRICT READ-ONLY mode.",
        "",
        "GOAL:",
        "- Answer the user question with verifiable code evidence.",
        "- Do not speculate. Every important claim must map to code locations.",
        "",
        "ALLOWED COMMANDS:",
        "- Navigation: cd, ls, find",
        "- Reading/Search: cat, grep, head, tail, nl, sed",
        "",
        f"TARGET REPOSITORY: {repo_path}",
        f"Start with: cd {repo_path}",
        "",
        "WORKFLOW:",
        "1) Explore structure and identify candidate files/functions.",
        "2) Collect evidence using exact file paths and line numbers.",
        "3) Synthesize only after evidence is sufficient.",
        "",
    ]

    if getattr(config, "enable_decomposition_tool", True):
        if getattr(config, "decompose_on_start", True):
            lines.extend([
                "DECOMPOSITION TOOL STATUS:",
                "- Decomposition may already be initialized by the system.",
                "- Use sub-questions below as execution anchors, not as final truth.",
                "",
            ])
        else:
            lines.extend([
                "DECOMPOSITION TOOL STATUS:",
                "- Decomposition is optional and may be triggered dynamically.",
                "- Continue exploring normally; decomposition can be injected later if needed.",
                "",
            ])

    if aspects:
        lines.append("CURRENT INVESTIGATION ANCHORS:")
        for i, aspect in enumerate(aspects, 1):
            if use_subq:
                lines.append(f"- SUB-QUESTION {i} [{aspect.get('id', f'SQ{i}')}]: {aspect.get('sub_question', 'N/A')}")
                lines.append(f"  Hypothesis: {aspect.get('hypothesis', 'N/A')}")
                lines.append(f"  Entry candidates: {', '.join(aspect.get('entry_candidates', [])) or 'Unknown'}")
                lines.append(f"  Required evidence: {', '.join(aspect.get('required_evidence', [])) or 'N/A'}")
                lines.append(f"  Exit criterion: {aspect.get('exit_criterion', 'N/A')}")
            else:
                lines.append(f"- ASPECT {i}: {aspect.get('description', 'N/A')}")
                lines.append(f"  Entry point: {aspect.get('entry_point', 'Unknown')}")
        lines.append("")

    lines.extend([
        "SUBMISSION RULES (STRICT):",
        "1. Submit only after reading code and collecting traceable evidence.",
        "2. FINAL ANSWER must cover all critical sub-questions/aspects.",
        "3. For each sub-question/aspect include:",
        "   - exact file path + line numbers (file.py:line)",
        "   - concrete symbol/function/class reference",
        "   - short role explanation",
        "4. Use this final format:",
        "   - write your answer under '## FINAL ANSWER'",
        "   - then run: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
        "5. Never chain COMPLETE_TASK with other shell commands.",
        "",
        "RESPONSE FORMAT PER TURN:",
        "- Thought (brief)",
        "- Exactly one ```bash``` block",
        "",
        "BEGIN INVESTIGATION:",
    ])

    if config and config.enable_graph_injection:
        lines.append("Note: runtime [GRAPH HINT] messages may appear in observations.")
    if config and getattr(config, "enable_graph_tools", True):
        lines.append("Note: graph tool feedback may appear as [GRAPH TOOL] metrics.")

    return "\n".join(lines)
