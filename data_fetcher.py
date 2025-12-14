"""
数据获取模块
优先从本地缓存读取，如果本地数据不存在或过期则 fallback 到 Dexcom API

数据流：
1. sync_service.py 后台线程定时从 Dexcom 拉数据存到本地
2. 本模块优先从本地读取（毫秒级响应）
3. 如果本地无数据，fallback 到直接调用 Dexcom API
"""
from datetime import datetime, timedelta
from config import USERS
import threading

# 尝试导入同步服务
try:
    from sync_service import (
        get_current_from_local,
        get_history_from_local,
        load_user_data
    )
    SYNC_SERVICE_AVAILABLE = True
except ImportError:
    SYNC_SERVICE_AVAILABLE = False
    print("⚠️ sync_service 未找到，将直接调用 Dexcom API")

# Dexcom 客户端缓存（fallback 用）
_clients = {}
_lock = threading.Lock()


def _get_dexcom_client(user_id: str):
    """
    获取指定用户的 Dexcom 客户端（带缓存）- Fallback 用
    """
    global _clients
    
    if user_id not in USERS:
        raise ValueError(f"未知用户: {user_id}")
    
    with _lock:
        if user_id not in _clients:
            from pydexcom import Dexcom
            user = USERS[user_id]
            _clients[user_id] = Dexcom(
                username=user["username"],
                password=user["password"],
                region=user.get("region", "us")
            )
    
    return _clients[user_id]


def _is_data_fresh(last_updated_str, max_age_minutes=10):
    """检查数据是否新鲜"""
    if not last_updated_str:
        return False
    
    try:
        last_updated = datetime.fromisoformat(last_updated_str)
        age = datetime.now() - last_updated
        return age < timedelta(minutes=max_age_minutes)
    except:
        return False


def get_current_glucose(user_id: str) -> dict:
    """
    获取指定用户的当前血糖数据
    优先从本地读取，如果无数据则 fallback 到 API
    
    Returns:
        血糖数据字典（血糖值使用 mmol/L 单位）
    """
    user_info = USERS.get(user_id, {})
    
    # 1. 尝试从本地读取
    if SYNC_SERVICE_AVAILABLE:
        try:
            local_data = load_user_data(user_id)
            current = local_data.get("current")
            
            # 检查数据是否存在且新鲜（10分钟内）
            if current and _is_data_fresh(local_data.get("last_updated"), 10):
                return {
                    "success": True,
                    "user_id": user_id,
                    "user_name": user_info.get("name", user_id),
                    "avatar": user_info.get("avatar", ""),
                    "color": user_info.get("color", "#666"),
                    "data": current,
                    "source": "local"
                }
        except Exception as e:
            print(f"⚠️ 从本地读取 {user_id} 失败: {e}")
    
    # 2. Fallback: 直接调用 Dexcom API
    try:
        client = _get_dexcom_client(user_id)
        reading = client.get_current_glucose_reading()
        
        if reading:
            return {
                "success": True,
                "user_id": user_id,
                "user_name": user_info.get("name", user_id),
                "avatar": user_info.get("avatar", ""),
                "color": user_info.get("color", "#666"),
                "data": {
                    "value": reading.mmol_l,
                    "value_mgdl": reading.value,
                    "trend": reading.trend,
                    "trend_direction": reading.trend_direction,
                    "trend_description": reading.trend_description,
                    "trend_arrow": reading.trend_arrow,
                    "datetime": reading.datetime.isoformat(),
                },
                "source": "api"
            }
        else:
            return {
                "success": False,
                "user_id": user_id,
                "user_name": user_info.get("name", user_id),
                "error": "暂无数据"
            }
            
    except Exception as e:
        return {
            "success": False,
            "user_id": user_id,
            "user_name": user_info.get("name", user_id),
            "error": str(e)
        }


def get_glucose_history(user_id: str, minutes: int = 180, max_count: int = 36) -> dict:
    """
    获取指定用户的历史血糖数据
    优先从本地读取，如果无数据则 fallback 到 API
    
    Args:
        user_id: 用户ID
        minutes: 获取多少分钟内的数据
        max_count: 最大数据条数
    
    Returns:
        历史数据字典（血糖值使用 mmol/L 单位）
    """
    user_info = USERS.get(user_id, {})
    
    # 1. 尝试从本地读取
    if SYNC_SERVICE_AVAILABLE:
        try:
            history = get_history_from_local(user_id, minutes, max_count)
            
            if history:
                return {
                    "success": True,
                    "user_id": user_id,
                    "user_name": user_info.get("name", user_id),
                    "avatar": user_info.get("avatar", ""),
                    "color": user_info.get("color", "#666"),
                    "history": history,
                    "source": "local"
                }
        except Exception as e:
            print(f"⚠️ 从本地读取 {user_id} 历史失败: {e}")
    
    # 2. Fallback: 直接调用 Dexcom API
    try:
        client = _get_dexcom_client(user_id)
        readings = client.get_glucose_readings(minutes=minutes, max_count=max_count)
        
        data = []
        for reading in readings:
            data.append({
                "value": reading.mmol_l,
                "value_mgdl": reading.value,
                "trend_arrow": reading.trend_arrow,
                "datetime": reading.datetime.isoformat(),
            })
        
        return {
            "success": True,
            "user_id": user_id,
            "user_name": user_info.get("name", user_id),
            "avatar": user_info.get("avatar", ""),
            "color": user_info.get("color", "#666"),
            "history": data,
            "source": "api"
        }
        
    except Exception as e:
        return {
            "success": False,
            "user_id": user_id,
            "user_name": user_info.get("name", user_id),
            "error": str(e)
        }


def get_all_users_glucose() -> list:
    """
    获取所有用户的当前血糖数据（用于PK）
    
    Returns:
        所有用户的血糖数据列表
    """
    results = []
    for user_id in USERS.keys():
        result = get_current_glucose(user_id)
        results.append(result)
    return results


def get_user_list() -> list:
    """
    获取所有用户的基本信息
    
    Returns:
        用户信息列表
    """
    return [
        {
            "id": user_id,
            "name": info["name"],
            "avatar": info["avatar"],
            "color": info["color"]
        }
        for user_id, info in USERS.items()
    ]
