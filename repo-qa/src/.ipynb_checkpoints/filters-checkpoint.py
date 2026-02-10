"""命令过滤器 - 智能版：区分重定向操作符与文本内容"""
import re
from typing import Tuple, Dict

class CommandFilter:
    """智能命令过滤器：只拦截真正的写操作，不误伤 echo 输出"""
    
    # 精准拦截模式
    FORBIDDEN_PATTERNS = [
        # 文件写入操作（Shell 重定向，必须在引号外）
        (r'\s+>\s+\S+', "File writing via redirection is forbidden"),  # 修改：只匹配 '> filename' 格式
        (r'\s+>>\s+\S+', "File appending via redirection is forbidden"),
        
        # 危险的文件创建命令
        (r'\bcat\s+<<', "Heredoc file creation is forbidden"),  # cat <<EOF
        (r'\btouch\b', "Creating files is forbidden"),
        (r'\brm\s+', "Deleting files is forbidden"),
        (r'\bmv\s+', "Moving files is forbidden"),
        
        # 执行类命令
        (r'\bsleep\s+\d', "Sleep is for testing, not analyzing"),
        (r'\bpython\s+-c\b', "Direct code execution is forbidden"),
        (r'\bpython\s+\w+\.py', "Script execution is forbidden"),
        (r'\bpip\s+install', "Installing packages is forbidden"),
        
        # 危险的系统操作
        (r'\bchmod\b', "Changing permissions is forbidden"),
        (r'\bwget\b', "Downloading is forbidden"),
        (r'\bcurl\s+-O', "Downloading is forbidden"),
    ]
    
    # 明确允许的命令（白名单，即使包含 > 也放行）
    ALLOWED_COMMANDS = [
        r'^echo\b',      # echo 输出到标准输出（即使内容包含 >）
        r'^printf\b',    # printf 同理
        r'^cat\s+\S+$',  # cat 单个文件（不带重定向）
    ]
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.blocked_history = []
    
    def should_block(self, command: str) -> Tuple[bool, str]:
        """智能检查：区分真实重定向和文本内容"""
        if not self.enabled:
            return False, ""
        
        cmd_clean = command.strip()
        
        # 优先检查白名单（快速放行）
        for allowed in self.ALLOWED_COMMANDS:
            if re.match(allowed, cmd_clean, re.IGNORECASE):
                return False, ""
        
        # 检查黑名单模式
        for pattern, reason in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                # 额外验证：确保 > 不在引号内
                if pattern in [r'\s+>\s+\S+', r'\s+>>\s+\S+']:
                    if self._is_redirect_in_quotes(cmd_clean):
                        continue  # 在引号内，放行
                
                self.blocked_history.append({
                    'command': command,
                    'pattern': pattern,
                    'reason': reason
                })
                return True, reason
        
        return False, ""
    
    def _is_redirect_in_quotes(self, command: str) -> bool:
        """检查重定向符是否在引号内"""
        # 移除所有引号内的内容
        without_quotes = re.sub(r'''(['"]).*?\1''', '', command)
        # 如果移除引号后没有 > 了，说明原命令的 > 都在引号内
        return '>' not in without_quotes and '>>' not in without_quotes
    
    def get_suggestion(self, command: str, reason: str) -> str:
        """提供替代建议"""
        if 'redirection' in reason:
            return "Hint: Use 'echo' to display text without writing files."
        if 'execution' in reason:
            return "Hint: Read code with 'cat' or 'grep' instead of executing."
        return "Use read-only tools: cd, ls, cat, grep, find, head, tail."
    
    def get_stats(self) -> Dict:
        return {
            'total_blocked': len(self.blocked_history),
            'unique_patterns': len(set(b['pattern'] for b in self.blocked_history)),
            'most_common': self.blocked_history[0]['pattern'] if self.blocked_history else None
        }
