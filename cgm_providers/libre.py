"""
FreeStyle Libre CGM Provider
使用 pylibrelinkup 库连接 LibreLinkUp API

安装: pip install pylibrelinkup
"""

from typing import List, Optional
from datetime import datetime
from .base import BaseCGMProvider, CGMReading


class LibreProvider(BaseCGMProvider):
    """FreeStyle Libre Provider (通过 LibreLinkUp)"""
    
    PROVIDER_TYPE = "libre"
    PROVIDER_NAME = "FreeStyle Libre"
    
    def __init__(self, credentials: dict):
        super().__init__(credentials)
        self._client = None
        self._patient = None
    
    def _get_client(self):
        """获取或创建 LibreLinkUp 客户端"""
        if self._client is None:
            try:
                from pylibrelinkup import PyLibreLinkUp
            except ImportError:
                raise ImportError(
                    "需要安装 pylibrelinkup 库: pip install pylibrelinkup"
                )
            
            email = self.credentials.get("username")
            password = self.credentials.get("password")
            
            if not email or not password:
                raise ValueError("缺少 LibreLinkUp 邮箱或密码")
            
            self._client = PyLibreLinkUp(email=email, password=password)
        
        return self._client
    
    def _ensure_authenticated(self):
        """确保已认证并获取患者"""
        client = self._get_client()
        
        # 调用 authenticate() 方法
        client.authenticate()
        
        if self._patient is None:
            # 获取关联的患者列表
            patients = client.get_patients()
            if not patients:
                raise ValueError("未找到关联的 Libre 设备，请确认已在 LibreLinkUp 中设置分享")
            
            # 使用第一个患者
            self._patient = patients[0]
    
    def authenticate(self) -> bool:
        """验证 LibreLinkUp 凭证"""
        try:
            self._ensure_authenticated()
            return True
        except Exception as e:
            print(f"⚠️ Libre 认证失败: {e}")
            return False
    
    def _convert_trend(self, trend_value) -> tuple:
        """
        转换 Libre 趋势值为标准格式
        
        pylibrelinkup 可能返回数值或字符串
        """
        # 数值映射
        trend_map_int = {
            1: ("falling_fast", 1, "↓↓", "rapidly falling"),
            2: ("falling", 2, "↓", "falling"),
            3: ("stable", 3, "→", "stable"),
            4: ("rising", 4, "↑", "rising"),
            5: ("rising_fast", 5, "↑↑", "rapidly rising"),
        }
        
        if isinstance(trend_value, int) and trend_value in trend_map_int:
            return trend_map_int[trend_value]
        
        # 尝试转换字符串
        if isinstance(trend_value, str):
            try:
                trend_int = int(trend_value)
                if trend_int in trend_map_int:
                    return trend_map_int[trend_int]
            except ValueError:
                pass
        
        return ("unknown", None, "?", "unknown")
    
    def get_current_reading(self) -> Optional[CGMReading]:
        """获取当前血糖读数"""
        try:
            self._ensure_authenticated()
            client = self._get_client()
            
            # 使用 latest() 方法获取最新读数
            data = client.latest(patient_identifier=self._patient)
            
            if data is None:
                return None
            
            # pylibrelinkup 返回的 value 是 mg/dL
            value_mgdl = data.value
            value_mmol = round(value_mgdl / 18.0, 1)
            
            # 获取趋势
            trend_raw = getattr(data, 'trend', None) or getattr(data, 'trend_arrow', 3)
            trend, trend_dir, arrow, desc = self._convert_trend(trend_raw)
            
            # 获取时间戳
            timestamp = getattr(data, 'timestamp', None) or datetime.now()
            
            return CGMReading(
                value=value_mmol,
                value_mgdl=int(value_mgdl),
                timestamp=timestamp,
                trend=trend,
                trend_direction=trend_dir,
                trend_arrow=arrow,
                trend_description=desc,
            )
        except Exception as e:
            print(f"❌ Libre 获取当前读数失败: {e}")
            return None
    
    def get_readings(self, minutes: int = 180, max_count: int = 36) -> List[CGMReading]:
        """获取历史血糖读数"""
        try:
            self._ensure_authenticated()
            client = self._get_client()
            
            # 使用 graph() 方法获取最近 12 小时的数据
            history = client.graph(patient_identifier=self._patient)
            
            if not history:
                return []
            
            result = []
            for item in history[:max_count]:
                value_mgdl = item.value
                value_mmol = round(value_mgdl / 18.0, 1)
                
                # 获取时间戳
                timestamp = getattr(item, 'timestamp', None) or \
                           getattr(item, 'factory_timestamp', None) or \
                           datetime.now()
                
                result.append(CGMReading(
                    value=value_mmol,
                    value_mgdl=int(value_mgdl),
                    timestamp=timestamp,
                    trend_arrow="→",  # 历史数据通常没有趋势
                ))
            
            # 按时间降序排列
            result.sort(key=lambda x: x.timestamp, reverse=True)
            
            return result
        except Exception as e:
            print(f"❌ Libre 获取历史读数失败: {e}")
            return []
