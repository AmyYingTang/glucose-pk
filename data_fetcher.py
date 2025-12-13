"""
数据获取模块
这个文件负责从 Dexcom 获取数据，不需要频繁修改
"""
from pydexcom import Dexcom
from config import USERS
import threading

# 缓存所有用户的 Dexcom 客户端
_clients = {}
_lock = threading.Lock()


def get_client(user_id: str) -> Dexcom:
    """
    获取指定用户的 Dexcom 客户端（带缓存）
    
    Args:
        user_id: 用户ID（config.py 中的 key）
    
    Returns:
        Dexcom 客户端实例
    """
    global _clients
    
    if user_id not in USERS:
        raise ValueError(f"未知用户: {user_id}")
    
    with _lock:
        if user_id not in _clients:
            user = USERS[user_id]
            _clients[user_id] = Dexcom(
                username=user["username"],
                password=user["password"],
                region=user.get("region", "us")
            )
    
    return _clients[user_id]


def get_current_glucose(user_id: str) -> dict:
    """
    获取指定用户的当前血糖数据
    
    Args:
        user_id: 用户ID
    
    Returns:
        血糖数据字典（血糖值使用 mmol/L 单位）
    """
    try:
        client = get_client(user_id)
        reading = client.get_current_glucose_reading()
        
        if reading:
            user_info = USERS[user_id]
            return {
                "success": True,
                "user_id": user_id,
                "user_name": user_info["name"],
                "avatar": user_info["avatar"],
                "color": user_info["color"],
                "data": {
                    "value": reading.mmol_l,          # mmol/L（主要使用）
                    "value_mgdl": reading.value,      # mg/dL（备用）
                    "trend": reading.trend,
                    "trend_direction": reading.trend_direction,
                    "trend_description": reading.trend_description,
                    "trend_arrow": reading.trend_arrow,
                    "datetime": reading.datetime.isoformat(),
                }
            }
        else:
            return {
                "success": False,
                "user_id": user_id,
                "user_name": USERS[user_id]["name"],
                "error": "暂无数据"
            }
            
    except Exception as e:
        return {
            "success": False,
            "user_id": user_id,
            "user_name": USERS.get(user_id, {}).get("name", user_id),
            "error": str(e)
        }


def get_glucose_history(user_id: str, minutes: int = 180, max_count: int = 36) -> dict:
    """
    获取指定用户的历史血糖数据
    
    Args:
        user_id: 用户ID
        minutes: 获取多少分钟内的数据
        max_count: 最大数据条数
    
    Returns:
        历史数据字典（血糖值使用 mmol/L 单位）
    """
    try:
        client = get_client(user_id)
        readings = client.get_glucose_readings(minutes=minutes, max_count=max_count)
        
        data = []
        for reading in readings:
            data.append({
                "value": reading.mmol_l,          # mmol/L（主要使用）
                "value_mgdl": reading.value,      # mg/dL（备用）
                "trend_arrow": reading.trend_arrow,
                "datetime": reading.datetime.isoformat(),
            })
        
        user_info = USERS[user_id]
        return {
            "success": True,
            "user_id": user_id,
            "user_name": user_info["name"],
            "avatar": user_info["avatar"],
            "color": user_info["color"],
            "data": data
        }
        
    except Exception as e:
        return {
            "success": False,
            "user_id": user_id,
            "user_name": USERS.get(user_id, {}).get("name", user_id),
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
