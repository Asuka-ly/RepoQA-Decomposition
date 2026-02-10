"""模式检测器 - 行为分析"""
from typing import List, Dict

class PatternDetector:
    """检测 Agent 的行为模式（Stage 1 仅做日志记录）"""
    
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.detections = []
    
    def detect_lost(self, recent_messages: List[Dict]) -> bool:
        """检测迷失模式
        
        迷失信号：
        1. 连续 3 次 grep 结果为空
        2. 重复搜索相同关键词
        
        Args:
            recent_messages: 最近的消息列表
            
        Returns:
            是否迷失
        """
        if len(recent_messages) < 3:
            return False
        
        # 模式 1: 连续空结果
        empty_count = 0
        for msg in recent_messages[-self.window_size:]:
            if msg.get('role') == 'user' and '<output>\n</output>' in msg.get('content', ''):
                empty_count += 1
        
        if empty_count >= 3:
            self.detections.append({'type': 'lost', 'reason': 'empty_searches'})
            return True
        
        # 模式 2: 重复搜索
        search_keywords = []
        for msg in recent_messages[-self.window_size:]:
            content = msg.get('content', '')
            if 'grep' in content:
                # 简单提取关键词
                import re
                match = re.search(r'grep\s+["\']?(\w+)', content)
                if match:
                    search_keywords.append(match.group(1))
        
        if len(search_keywords) >= 3:
            unique_ratio = len(set(search_keywords)) / len(search_keywords)
            if unique_ratio < 0.5:  # 重复度超过50%
                self.detections.append({'type': 'lost', 'reason': 'repetitive_searches'})
                return True
        
        return False
    
    def detect_completion(self, aspects: List[Dict], viewed_files: set) -> bool:
        """检测是否完成所有切面探索（简化版）
        
        Args:
            aspects: 分解的切面列表
            viewed_files: 已查看的文件集合
            
        Returns:
            是否完成
        """
        # 简单启发式：查看的文件数 >= 切面数 * 2
        return len(viewed_files) >= len(aspects) * 2 if aspects else False
    
    def get_stats(self) -> Dict:
        """获取检测统计"""
        return {
            'total_detections': len(self.detections),
            'lost_count': sum(1 for d in self.detections if d['type'] == 'lost')
        }
