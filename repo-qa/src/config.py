"""实验配置管理"""
import yaml
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

@dataclass
class ExperimentConfig:
    """实验配置类（简化版）"""
    
    # === 核心开关 ===
    enable_graph: bool = True
    enable_graph_injection: bool = True
    enable_command_filter: bool = True
    enable_pattern_detection: bool = False
    
    # === 参数 ===
    injection_min_length: int = 6
    max_steps: int = 50
    
    # === 元信息 ===
    name: str = "default"
    description: str = ""
    
    @classmethod
    def from_yaml(cls, path: str) -> 'ExperimentConfig':
        """从 YAML 加载配置"""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ExperimentConfig':
        """从字典创建配置"""
        return cls(**data)
    
    def to_yaml(self, path: str):
        """保存为 YAML"""
        with open(path, 'w') as f:
            yaml.dump(asdict(self), f, indent=2)
    
    def to_dict(self) -> dict:
        """转为字典"""
        return asdict(self)
    
    def __str__(self) -> str:
        """打印配置摘要"""
        return (
            f"Config: {self.name}\n"
            f"  Graph: {'✅' if self.enable_graph else '❌'}\n"
            f"  Injection: {'✅' if self.enable_graph_injection else '❌'}\n"
            f"  Filter: {'✅' if self.enable_command_filter else '❌'}\n"
            f"  Detection: {'✅' if self.enable_pattern_detection else '❌'}\n"
            f"  Max Steps: {self.max_steps}"
        )
