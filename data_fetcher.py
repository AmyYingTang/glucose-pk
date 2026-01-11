"""
数据获取模块（纯净模式）
使用 CGM Manager 统一管理所有设备

数据流：
1. sync_service.py 后台线程定时从各种 CGM 设备拉数据存到本地
2. 本模块优先从本地读取（毫秒级响应）
3. 如果本地无数据，fallback 到直接调用 Provider API

player_id 格式：{username}_{device_id}
例如：amy_dexcom_001
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict
import threading

from cgm_manager import cgm_manager

# 尝试导入同步服务
try:
    from sync_service import (
        get_current_from_local,
        get_history_from_local,
        load_player_data
    )
    SYNC_SERVICE_AVAILABLE = True
except ImportError:
    SYNC_SERVICE_AVAILABLE = False
    print("⚠️ sync_service 未找到，将直接调用 CGM API")


def _parse_player_id(player_id: str) -> tuple:
    """
    解析 player_id 为 (username, device_id)
    
    player_id 格式: {username}_{device_type}_{uuid}
    例如: amy_dexcom_abc12345
    
    注意：username 可能包含下划线，但 device_id 的格式是固定的 {type}_{uuid}
    """
    if not player_id or "_" not in player_id:
        return None, None
    
    # 从右边找，因为 device_id 格式固定
    parts = player_id.rsplit("_", 2)
    
    if len(parts) >= 3:
        # 正常情况：username_devicetype_uuid
        username = "_".join(parts[:-2]) if len(parts) > 3 else parts[0]
        device_id = f"{parts[-2]}_{parts[-1]}"
        return username, device_id
    elif len(parts) == 2:
        # 可能是简单格式：username_deviceid
        return parts[0], parts[1]
    
    return None, None


def _is_data_fresh(last_updated_str: str, max_age_minutes: int = 10) -> bool:
    """检查数据是否新鲜"""
    if not last_updated_str:
        return False
    
    try:
        last_updated = datetime.fromisoformat(last_updated_str)
        age = datetime.now() - last_updated
        return age < timedelta(minutes=max_age_minutes)
    except:
        return False


def _get_player_info(player_id: str) -> dict:
    """获取玩家信息（从 CGM Manager）"""
    username, device_id = _parse_player_id(player_id)
    if not username or not device_id:
        return {
            "user_id": player_id,
            "user_name": player_id,
            "avatar": "🩸",
            "color": "#666"
        }
    
    device = cgm_manager.get_device(username, device_id)
    if device:
        return {
            "user_id": player_id,
            "user_name": device.get("name", player_id),
            "avatar": device.get("display", {}).get("avatar", "🩸"),
            "color": device.get("display", {}).get("color", "#666")
        }
    
    return {
        "user_id": player_id,
        "user_name": player_id,
        "avatar": "🩸",
        "color": "#666"
    }


def get_current_glucose(player_id: str) -> dict:
    """
    获取指定玩家的当前血糖数据
    
    Args:
        player_id: 玩家 ID（格式：{username}_{device_id}）
    
    Returns:
        血糖数据字典（血糖值使用 mmol/L 单位）
    """
    player_info = _get_player_info(player_id)
    username, device_id = _parse_player_id(player_id)
    
    # 1. 尝试从本地读取
    if SYNC_SERVICE_AVAILABLE:
        try:
            local_data = load_player_data(player_id)
            current = local_data.get("current")
            
            # 检查数据是否存在且新鲜（10分钟内）
            if current and _is_data_fresh(local_data.get("last_updated"), 10):
                return {
                    "success": True,
                    **player_info,
                    "data": current,
                    "source": "local"
                }
        except Exception as e:
            print(f"⚠️ 从本地读取 {player_id} 失败: {e}")
    
    # 2. Fallback: 直接调用 Provider API
    if username and device_id:
        try:
            provider = cgm_manager.get_provider(username, device_id)
            if provider:
                reading = provider.get_current_reading()
                
                if reading:
                    return {
                        "success": True,
                        **player_info,
                        "data": reading.to_dict(),
                        "source": "api"
                    }
                else:
                    return {
                        "success": False,
                        **player_info,
                        "error": "暂无数据"
                    }
        except Exception as e:
            return {
                "success": False,
                **player_info,
                "error": str(e)
            }
    
    return {
        "success": False,
        **player_info,
        "error": "无效的玩家 ID"
    }


def get_glucose_history(player_id: str, minutes: int = 180, max_count: int = 36) -> dict:
    """
    获取指定玩家的历史血糖数据
    
    Args:
        player_id: 玩家 ID
        minutes: 获取多少分钟内的数据
        max_count: 最大数据条数
    
    Returns:
        历史数据字典（血糖值使用 mmol/L 单位）
    """
    player_info = _get_player_info(player_id)
    username, device_id = _parse_player_id(player_id)
    
    # 1. 尝试从本地读取
    if SYNC_SERVICE_AVAILABLE:
        try:
            history = get_history_from_local(player_id, minutes, max_count)
            
            if history:
                return {
                    "success": True,
                    **player_info,
                    "history": history,
                    "source": "local"
                }
        except Exception as e:
            print(f"⚠️ 从本地读取 {player_id} 历史失败: {e}")
    
    # 2. Fallback: 直接调用 Provider API
    if username and device_id:
        try:
            provider = cgm_manager.get_provider(username, device_id)
            if provider:
                readings = provider.get_readings(minutes=minutes, max_count=max_count)
                
                data = [r.to_dict() for r in readings]
                
                return {
                    "success": True,
                    **player_info,
                    "history": data,
                    "source": "api"
                }
        except Exception as e:
            return {
                "success": False,
                **player_info,
                "error": str(e)
            }
    
    return {
        "success": False,
        **player_info,
        "error": "无效的玩家 ID"
    }


def get_all_players_glucose() -> list:
    """
    获取所有活跃玩家的当前血糖数据（用于 PK）
    
    Returns:
        所有玩家的血糖数据列表
    """
    results = []
    
    # 从 CGM Manager 获取所有活跃设备
    all_devices = cgm_manager.get_all_active_devices()
    
    for device in all_devices:
        player_id = device["player_id"]
        result = get_current_glucose(player_id)
        results.append(result)
    
    return results


def get_player_list() -> list:
    """
    获取所有活跃玩家的基本信息
    
    Returns:
        玩家信息列表
    """
    all_devices = cgm_manager.get_all_active_devices()
    
    return [
        {
            "id": device["player_id"],
            "name": device["device_name"],
            "avatar": device["avatar"],
            "color": device["color"],
            "username": device["username"],
            "device_type": device["device_type"]
        }
        for device in all_devices
    ]


# ==================== 兼容旧 API ====================
# 这些函数保留以兼容现有代码，但内部使用新逻辑

def get_user_list() -> list:
    """获取所有用户的基本信息（兼容旧 API）"""
    return get_player_list()


def get_all_users_glucose() -> list:
    """获取所有用户的当前血糖数据（兼容旧 API）"""
    return get_all_players_glucose()
