"""工具函数集合"""
import logging
import sys
from typing import Dict

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

def build_task_prompt(task: str, repo_path: str, 
                     decomposition: Dict, config) -> str:
    """构建增强任务 Prompt
    
    Args:
        task: 原始问题
        repo_path: 仓库路径
        decomposition: 分解结果
        config: 实验配置
        
    Returns:
        增强后的任务描述
    """
    lines = [
        "You are a CODE ANALYSIS SPECIALIST.",
        "",
        # 修改：改为正面引导，而非负面禁止
        "📌 YOUR TOOLS:",
        "- Navigation: cd, ls, find",
        "- Reading: cat, grep, head, tail",
        "- Analysis: Use these tools to understand code logic",
        "",
        f"🎯 TARGET REPOSITORY: {repo_path}",
        f"   ▸ Start with: cd {repo_path}",
        "",
        "📋 INVESTIGATION STRATEGY:",
        ""
    ]
    
    # 添加分解的切面
    aspects = decomposition.get('aspects', [])
    if aspects:
        for i, aspect in enumerate(aspects, 1):
            lines.append(f"  ASPECT {i}: {aspect.get('description', 'N/A')}")
            lines.append(f"  Entry Point: {aspect.get('entry_point', 'Unknown')}")
            if aspect.get('symbols'):
                lines.append(f"  Related Symbols: {', '.join(aspect['symbols'][:3])}")
            lines.append("")
    
    lines.extend([
        f"🎯 SYNTHESIS GOAL:",
        f"   {decomposition.get('synthesis', 'Understand and explain the code logic')}",
        "",
        f"❓ ORIGINAL QUESTION:",
        f"   {task}",
        "",
    ])
    
    # 根据配置添加提示
    if config.enable_graph_injection:
        lines.append("💡 NOTE: I will provide [GRAPH HINT] when you view code files.")
        lines.append("")
    
    lines.extend([
        "📍 COMPLETION INSTRUCTION:",
        "   When you have the answer, use:",
        "   echo \"FINAL ANSWER: <your detailed analysis>\"",
        "   Then submit.",
    ])
    
    return "\n".join(lines)
