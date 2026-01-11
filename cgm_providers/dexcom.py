"""
Dexcom CGM Provider
使用 pydexcom 库连接 Dexcom Share API
"""

from typing import List, Optional
from .base import BaseCGMProvider, CGMReading


class DexcomProvider(BaseCGMProvider):
    """Dexcom G6/G7 Provider"""
    
    PROVIDER_TYPE = "dexcom"
    PROVIDER_NAME = "Dexcom G6/G7"
    
    def __init__(self, credentials: dict):
        super().__init__(credentials)
        self._client = None
    
    def _get_client(self):
        """获取或创建 Dexcom 客户端"""
        if self._client is None:
            from pydexcom import Dexcom
            
            username = self.credentials.get("username")
            password = self.credentials.get("password")
            region = self.credentials.get("region", "ous")
            
            if not username or not password:
                raise ValueError("缺少 Dexcom 用户名或密码")
            
            # region 参数：'us' 为美国，其他为国际版
            self._client = Dexcom(
                username=username,
                password=password,
                region=region if region else "ous"
            )
        
        return self._client
    
    def authenticate(self) -> bool:
        """验证 Dexcom 凭证"""
        try:
            client = self._get_client()
            # 尝试获取数据来验证凭证
            client.get_current_glucose_reading()
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if "account" in error_msg or "password" in error_msg or "auth" in error_msg:
                return False
            # 其他错误可能是网络问题，但凭证本身可能是对的
            # 为了安全起见，还是返回 False
            return False
    
    def get_current_reading(self) -> Optional[CGMReading]:
        """获取当前血糖读数"""
        try:
            client = self._get_client()
            reading = client.get_current_glucose_reading()
            
            if reading is None:
                return None
            
            return CGMReading(
                value=reading.mmol_l,
                value_mgdl=reading.value,
                timestamp=reading.datetime,
                trend=reading.trend,
                trend_direction=reading.trend_direction,
                trend_arrow=reading.trend_arrow,
                trend_description=reading.trend_description,
            )
        except Exception as e:
            print(f"❌ Dexcom 获取当前读数失败: {e}")
            return None
    
    def get_readings(self, minutes: int = 180, max_count: int = 36) -> List[CGMReading]:
        """获取历史血糖读数"""
        try:
            client = self._get_client()
            readings = client.get_glucose_readings(minutes=minutes, max_count=max_count)
            
            result = []
            for reading in readings:
                result.append(CGMReading(
                    value=reading.mmol_l,
                    value_mgdl=reading.value,
                    timestamp=reading.datetime,
                    trend_arrow=reading.trend_arrow,
                ))
            
            return result
        except Exception as e:
            print(f"❌ Dexcom 获取历史读数失败: {e}")
            return []
