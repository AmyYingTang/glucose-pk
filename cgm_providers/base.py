"""
CGM Provider 基类
定义统一的接口，所有具体的 Provider 都继承此类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class CGMReading:
    """
    标准化的血糖读数
    所有 Provider 都返回这个格式
    """
    value: float           # 血糖值 (mmol/L)
    value_mgdl: int        # 血糖值 (mg/dL)
    timestamp: datetime    # 读数时间
    trend: Optional[str] = None           # 趋势名称
    trend_direction: Optional[int] = None  # 趋势方向数值
    trend_arrow: Optional[str] = None      # 趋势箭头符号
    trend_description: Optional[str] = None  # 趋势描述
    
    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "value": self.value,
            "value_mgdl": self.value_mgdl,
            "datetime": self.timestamp.isoformat(),
            "trend": self.trend,
            "trend_direction": self.trend_direction,
            "trend_arrow": self.trend_arrow,
            "trend_description": self.trend_description,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CGMReading':
        """从字典创建实例"""
        return cls(
            value=data.get("value"),
            value_mgdl=data.get("value_mgdl"),
            timestamp=datetime.fromisoformat(data.get("datetime")),
            trend=data.get("trend"),
            trend_direction=data.get("trend_direction"),
            trend_arrow=data.get("trend_arrow"),
            trend_description=data.get("trend_description"),
        )


class BaseCGMProvider(ABC):
    """
    CGM 设备 Provider 基类
    
    所有具体的 Provider（如 DexcomProvider、LibreProvider）
    都必须继承此类并实现抽象方法
    """
    
    # 子类必须定义这些属性
    PROVIDER_TYPE: str = None  # 'dexcom', 'libre' 等
    PROVIDER_NAME: str = None  # '显示名称'
    
    def __init__(self, credentials: dict):
        """
        初始化 Provider
        
        Args:
            credentials: 凭证字典，包含用户名、密码等
        """
        self.credentials = credentials
        self._client = None
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        验证凭证是否有效
        
        Returns:
            bool: 认证是否成功
        """
        pass
    
    @abstractmethod
    def get_current_reading(self) -> Optional[CGMReading]:
        """
        获取当前血糖读数
        
        Returns:
            CGMReading 或 None
        """
        pass
    
    @abstractmethod
    def get_readings(self, minutes: int = 180, max_count: int = 36) -> List[CGMReading]:
        """
        获取历史血糖读数
        
        Args:
            minutes: 获取多少分钟内的数据
            max_count: 最大条数
        
        Returns:
            CGMReading 列表（按时间降序，最新在前）
        """
        pass
    
    def test_connection(self) -> dict:
        """
        测试连接（用于添加设备时验证）
        
        Returns:
            {
                "success": bool,
                "message": str,
                "current_reading": CGMReading (如果成功)
            }
        """
        try:
            if self.authenticate():
                reading = self.get_current_reading()
                if reading:
                    return {
                        "success": True,
                        "message": f"连接成功！当前血糖: {reading.value} mmol/L",
                        "current_reading": reading.to_dict()
                    }
                else:
                    return {
                        "success": True,
                        "message": "连接成功，但暂无血糖数据",
                        "current_reading": None
                    }
            else:
                return {
                    "success": False,
                    "message": "认证失败，请检查用户名和密码"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接失败: {str(e)}"
            }
