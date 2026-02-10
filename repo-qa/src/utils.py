"""工具函数集合"""
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

# ============================================================
# 路径配置管理器
# ============================================================

class PathConfig:
    """统一路径管理器"""
    
    def __init__(self):
        # 自动检测项目根目录
        self.project_root = self._find_project_root()
        
        # 加载 .env（优先从项目根目录）
        env_path = self.project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✓ Loaded .env from: {env_path}")
        else:
            # 回退到用户级配置
            user_config = Path.home() / ".config" / "mini-swe-agent" / ".env"
            if user_config.exists():
                load_dotenv(user_config)
                print(f"✓ Loaded .env from: {user_config}")
            else:
                print("⚠️  No .env file found")
        
        # 设置关键路径
        self.mini_swe_agent_root = self.project_root / "mini-swe-agent"
        self.repo_qa_root = self.project_root / "repo-qa"
        
        # 将路径添加到 sys.path
        self._setup_python_path()
    
    def _find_project_root(self) -> Path:
        """向上查找包含 mini-swe-agent 和 repo-qa 的根目录"""
        current = Path(__file__).resolve()
        
        # 从当前文件向上查找
        for parent in [current] + list(current.parents):
            if (parent / "mini-swe-agent").exists() and (parent / "repo-qa").exists():
                return parent
        
        # 回退到环境变量
        if project_root := os.getenv("PROJECT_ROOT"):
            return Path(project_root)
        
        # 最后尝试硬编码路径
        fallback = Path("/root/RepoQA-Project")
        if fallback.exists():
            return fallback
        
        raise RuntimeError("Cannot find project root! Please set PROJECT_ROOT in .env")
    
    def _setup_python_path(self):
        """配置 Python 导入路径"""
        paths_to_add = [
            str(self.mini_swe_agent_root / "src"),  # mini-swe-agent 源码
            str(self.repo_qa_root),                  # repo-qa 根目录
        ]
        
        for p in paths_to_add:
            if p not in sys.path:
                sys.path.insert(0, p)
                print(f"✓ Added to sys.path: {p}")
    
    def get_test_repo_path(self) -> str:
        """获取测试仓库路径"""
        return os.getenv(
            "TEST_REPO_PATH",
            str(self.mini_swe_agent_root / "src" / "minisweagent")
        )
    
    def validate(self) -> bool:
        """验证所有路径是否存在"""
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

# 全局路径配置实例
PATH_CONFIG = PathConfig()

# ============================================================
# 原有的工具函数
# ============================================================

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """配置日志器
    
    Args:
        name: Logger 名称
        level: 日志级别
        
    Returns:
        配置好的 Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加 handler
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def build_task_prompt(task: str, repo_path: str, decomposition: Dict = None, config = None) -> str:
    """构建精简版增强任务 Prompt"""
    
    # 安全处理 None
    decomp_data = decomposition if decomposition is not None else {}
    aspects_list = decomp_data.get('aspects', [])
    aspects = sorted(aspects_list, key=lambda x: x.get('priority', 99))
    
    lines = [
        "You are a CODE ANALYSIS SPECIALIST solving a repository-level question in READ-ONLY mode.",
        "",
        "⚠️ IMPORTANT WORKFLOW:",
        "1. EXPLORE the codebase step-by-step using the tools below",
        "2. READ relevant files to understand the logic",
        "3. ONLY after gathering enough evidence, provide your final answer",
        "4. DO NOT guess or provide answers before reading the actual code",
        "",
        "📌 ALLOWED TOOLS:",
        "- Navigation: cd, ls, find",
        "- Reading: cat, grep, head, tail, nl, sed",
        "You are free to choose any of the tools above for efficient and precise exploration",
        "",
        f"🎯 TARGET REPOSITORY: {repo_path}",
        f" ▸ Start with: cd {repo_path}",
        "",
        "📋 INVESTIGATION STRATEGY:",
        ""
    ]
    
    if aspects:
        for i, aspect in enumerate(aspects, 1):
            lines.append(f" ASPECT {i}: {aspect.get('description', 'N/A')}")
            lines.append(f" Entry Point: {aspect.get('entry_point', 'Unknown')}")
            lines.append("")
    else:
        lines.append(" Explore the directory structure and locate main logic.")
    
    lines.extend([
        "",
        "📍 SUBMISSION RULES (STRICT):",
        " 1. You MUST read and analyze the code using commands FIRST.",
        " 2. You CANNOT submit before you have concrete findings.",
        " 3. A valid FINAL ANSWER must include:",
        "    ✅ For EACH aspect/sub-question:",
        "       - Exact file path and line numbers",
        "       - The actual code snippet or function name",
        "       - A brief explanation of its role",
        "    ✅ A synthesis that connects all aspects into a complete flow.",
        "",
        "    ❌ INVALID answers that will be rejected:",
        "       - \"I am ready to read...\" (you haven't read yet)",
        "       - \"Next steps would be...\" (give answers, not plans)",
        "       - Generic descriptions without file paths",
        "",
        " 4. Submission format:",
        "    - Provide your complete analysis with ## FINAL ANSWER marker",
        "    - Then execute: `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`",
        "",
        "❌ DO NOT chain echo with other analysis commands.",
        "📝 FORMAT: Thought + One ```bash block per turn.",
        "🚀 BEGIN INVESTIGATION:"
    ])

    
    if config and config.enable_graph_injection:
        lines.append("\n💡 Note: [GRAPH HINT] will be provided when viewing code.")
        
    return "\n".join(lines)
