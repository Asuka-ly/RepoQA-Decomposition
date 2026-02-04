"""命令过滤器 - 修复正则版"""
import re
from typing import Tuple, List, Dict

class CommandFilter:
    """命令安全过滤器"""
    
    # 核心禁止模式 - 极其简化的正则，防止转义问题
    FORBIDDEN_PATTERNS = [
        ('sleep', "Sleep is for testing timeouts, not analyzing code"),
        ('timeout', "Timeout command is not needed for code analysis"),
        ('python -c', "Direct execution via python -c is forbidden"),
        ('<<EOF', "Heredoc creates files, analysis should only read"),
        ('def test_', "Test function definitions are not allowed"),
    ]
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.blocked_history: List[Dict] = []
    
    def should_block(self, command: str) -> Tuple[bool, str]:
        """
        兼容mini-swe-agent v2版本：
        v2中command是dict → {'command': '实际命令', 'tool_call_id': 'xxx'}
        v1中command是字符串 → '实际命令'
        先提取真正的命令字符串，再进行过滤
        """
        # 核心修复：从dict中提取实际的command字符串，兼容字符串格式
        if isinstance(command, dict):
            # 是v2的dict格式，提取command字段
            cmd_str = command.get("command", "")  # 无command字段则置空
        else:
            # 是v1的字符串格式，直接使用
            cmd_str = str(command)
        
        cmd_clean = command.strip().lower()
        for pattern, reason in self.FORBIDDEN_PATTERNS:
            # 使用最简单的字符串包含检查，防止正则失效
            if pattern in cmd_clean:
                self.blocked_history.append({
                    'command': command,
                    'reason': reason,
                    'pattern': pattern
                })
                return True, reason
        
        return False, ""
    
    def get_suggestion(self, command: str, reason: str) -> str:
        return (
            f"❌ Blocked: {reason}\n"
            "💡 SUGGESTION: This is a CODE ANALYSIS task. \n"
            "Please use 'cat', 'grep', or 'ls' to understand the logic. \n"
            "Do NOT try to run scripts or wait for timeouts."
        )
    
    def get_stats(self) -> Dict:
        return {
            'total_blocked': len(self.blocked_history),
            'unique_patterns': len(set(b['pattern'] for b in self.blocked_history)),
            'most_common': self.blocked_history[0]['pattern'] if self.blocked_history else None
        }
