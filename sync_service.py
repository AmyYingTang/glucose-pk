"""
CGM 数据同步服务（纯净模式）
后台线程定时从各种 CGM 设备拉取数据，存储到本地 JSON 文件

特性：
- 每 3 分钟同步一次
- 支持多种 CGM 设备（Dexcom、Libre 等）
- 本地 JSON 存储，按 player_id 分文件
- 保留 48 小时历史数据
- 线程安全的读写
- 自动清理过期数据

数据存储结构：
glucose_data/
├── {player_id}.json    # 例如 amy_dexcom_001.json
└── ...
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from cgm_manager import cgm_manager


# ==================== 配置 ====================

# 同步间隔（秒）
SYNC_INTERVAL = 180  # 3 分钟

# 本地数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glucose_data")

# 保留多少小时的历史数据
HISTORY_HOURS = 48


# ==================== 全局状态 ====================

# 数据读写锁（每个玩家一个）
_data_locks: Dict[str, threading.Lock] = {}

# 同步状态
sync_status = {
    "last_sync": None,
    "last_success": None,
    "errors": [],
    "is_running": False,
    "player_count": 0
}


def _get_data_lock(player_id: str) -> threading.Lock:
    """获取玩家的数据锁"""
    if player_id not in _data_locks:
        _data_locks[player_id] = threading.Lock()
    return _data_locks[player_id]


def _get_player_data_file(player_id: str) -> str:
    """获取玩家数据文件路径"""
    os.makedirs(DATA_DIR, exist_ok=True)
    # 替换可能的非法字符
    safe_id = player_id.replace("/", "_").replace("\\", "_")
    return os.path.join(DATA_DIR, f"{safe_id}.json")


# ==================== 数据读写 ====================

def load_player_data(player_id: str) -> dict:
    """
    从本地文件加载玩家数据
    
    Returns:
        dict: {
            "player_id": "amy_dexcom_001",
            "last_updated": "2025-01-11T14:35:00",
            "current": { ... },
            "history": [ ... ]
        }
    """
    filepath = _get_player_data_file(player_id)
    lock = _get_data_lock(player_id)
    
    with lock:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 加载 {player_id} 数据失败: {e}")
    
    # 返回空数据结构
    return {
        "player_id": player_id,
        "last_updated": None,
        "current": None,
        "history": []
    }


def save_player_data(player_id: str, data: dict):
    """保存玩家数据到本地文件"""
    filepath = _get_player_data_file(player_id)
    lock = _get_data_lock(player_id)
    
    with lock:
        try:
            # 先写临时文件，再重命名（原子操作）
            temp_file = filepath + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, filepath)
        except Exception as e:
            print(f"❌ 保存 {player_id} 数据失败: {e}")


def clean_old_history(history: list, hours: int = HISTORY_HOURS) -> list:
    """清理过期的历史数据"""
    if not history:
        return []
    
    cutoff = datetime.now() - timedelta(hours=hours)
    
    cleaned = []
    for item in history:
        try:
            dt_str = item.get("datetime", "")
            item_time = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            # 转为无时区比较
            if item_time.replace(tzinfo=None) > cutoff:
                cleaned.append(item)
        except:
            continue
    
    return cleaned


# ==================== 数据同步 ====================

def sync_player_data(player_id: str, warmup: bool = False) -> bool:
    """
    从 CGM 设备同步单个玩家的数据
    
    Args:
        player_id: 玩家 ID（格式：{username}_{device_id}）
        warmup: 是否为预热模式（拉取更多历史数据）
    
    Returns:
        bool: 是否成功
    """
    try:
        # 解析 player_id
        parts = player_id.rsplit("_", 2)
        if len(parts) < 3:
            print(f"⚠️ 无效的 player_id: {player_id}")
            return False
        
        username = parts[0] if len(parts) == 3 else "_".join(parts[:-2])
        device_id = f"{parts[-2]}_{parts[-1]}"
        
        # 获取 Provider
        provider = cgm_manager.get_provider(username, device_id)
        if not provider:
            print(f"⚠️ 无法获取 {player_id} 的 Provider")
            return False
        
        # 获取当前血糖
        current_reading = provider.get_current_reading()
        
        # 预热模式拉取 24 小时，正常模式拉取 3 小时
        if warmup:
            history_minutes = 1440  # 24 小时
            history_count = 288     # 24 小时 × 12 个/小时
        else:
            history_minutes = 180   # 3 小时
            history_count = 36
        
        history_readings = provider.get_readings(minutes=history_minutes, max_count=history_count)
        
        # 加载现有本地数据
        local_data = load_player_data(player_id)
        
        # 更新当前值
        if current_reading:
            local_data["current"] = current_reading.to_dict()
        
        # 合并历史数据（去重）
        existing_times = set()
        for item in local_data.get("history", []):
            existing_times.add(item.get("datetime"))
        
        new_history = list(local_data.get("history", []))
        
        for reading in history_readings:
            dt_str = reading.timestamp.isoformat()
            if dt_str not in existing_times:
                new_history.append(reading.to_dict())
                existing_times.add(dt_str)
        
        # 按时间排序（最新在前）
        new_history.sort(key=lambda x: x.get("datetime", ""), reverse=True)
        
        # 清理过期数据
        new_history = clean_old_history(new_history)
        
        local_data["history"] = new_history
        local_data["last_updated"] = datetime.now().isoformat()
        
        # 保存到本地
        save_player_data(player_id, local_data)
        
        return True
        
    except Exception as e:
        print(f"❌ 同步 {player_id} 失败: {e}")
        return False


def check_needs_warmup(player_id: str) -> bool:
    """
    检查玩家是否需要预热（本地数据为空或不足 24 小时）
    """
    local_data = load_player_data(player_id)
    history = local_data.get("history", [])
    
    if not history:
        return True
    
    # 检查数据是否覆盖 24 小时
    try:
        oldest = min(history, key=lambda x: x.get("datetime", ""))
        oldest_time = datetime.fromisoformat(oldest["datetime"].replace("Z", "+00:00"))
        age = datetime.now() - oldest_time.replace(tzinfo=None)
        
        # 如果最老的数据不到 20 小时，需要预热
        if age < timedelta(hours=20):
            return True
    except:
        return True
    
    return False


def warmup_all_players():
    """预热所有玩家数据（拉取 24 小时历史）"""
    print("🔥 检查是否需要预热数据...")
    
    all_devices = cgm_manager.get_all_active_devices()
    
    for device in all_devices:
        player_id = device["player_id"]
        
        if check_needs_warmup(player_id):
            print(f"   📥 预热 {player_id} 数据（拉取24小时历史）...")
            if sync_player_data(player_id, warmup=True):
                local_data = load_player_data(player_id)
                print(f"   ✅ {player_id} 预热完成，共 {len(local_data.get('history', []))} 条数据")
            else:
                print(f"   ❌ {player_id} 预热失败")
        else:
            print(f"   ✓ {player_id} 数据充足，无需预热")


def sync_all_players():
    """同步所有玩家的数据"""
    global sync_status
    
    all_devices = cgm_manager.get_all_active_devices()
    
    sync_status["last_sync"] = datetime.now().isoformat()
    sync_status["is_running"] = True
    sync_status["player_count"] = len(all_devices)
    
    success_count = 0
    errors = []
    
    for device in all_devices:
        player_id = device["player_id"]
        
        try:
            if sync_player_data(player_id, warmup=False):
                success_count += 1
            else:
                errors.append(f"{player_id}: 同步失败")
        except Exception as e:
            errors.append(f"{player_id}: {str(e)}")
    
    if success_count == len(all_devices) and len(all_devices) > 0:
        sync_status["last_success"] = datetime.now().isoformat()
    
    sync_status["errors"] = errors[-10:]  # 只保留最近 10 条错误
    sync_status["is_running"] = False
    
    if all_devices:
        print(f"✅ 数据同步完成: {success_count}/{len(all_devices)} 成功 ({datetime.now().strftime('%H:%M:%S')})")
    else:
        print(f"⚠️ 没有活跃的 CGM 设备 ({datetime.now().strftime('%H:%M:%S')})")


# ==================== 后台线程 ====================

def _sync_loop():
    """后台同步循环"""
    print(f"🔄 CGM 同步服务启动，间隔: {SYNC_INTERVAL}秒")
    
    # 启动时先预热（补足 24 小时数据）
    warmup_all_players()
    
    # 然后正常同步一次
    sync_all_players()
    
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            sync_all_players()
        except Exception as e:
            print(f"❌ 同步循环异常: {e}")


_sync_thread = None


def start_sync_service():
    """启动后台同步服务"""
    global _sync_thread
    
    if _sync_thread is not None and _sync_thread.is_alive():
        print("⚠️ 同步服务已在运行")
        return
    
    _sync_thread = threading.Thread(target=_sync_loop, daemon=True)
    _sync_thread.start()
    print("🚀 后台同步服务已启动")


def get_sync_status() -> dict:
    """获取同步状态"""
    return sync_status.copy()


# ==================== 供 data_fetcher 调用的接口 ====================

def get_current_from_local(player_id: str) -> Optional[dict]:
    """
    从本地获取当前血糖（供 data_fetcher 调用）
    
    Returns:
        dict: 当前血糖数据，或 None
    """
    data = load_player_data(player_id)
    return data.get("current")


def get_history_from_local(player_id: str, minutes: int = 180, max_count: int = 36) -> list:
    """
    从本地获取历史数据（供 data_fetcher 调用）
    
    Args:
        player_id: 玩家 ID
        minutes: 获取多少分钟内的数据
        max_count: 最大条数
    
    Returns:
        list: 历史数据列表
    """
    data = load_player_data(player_id)
    history = data.get("history", [])
    
    if not history:
        return []
    
    # 过滤时间范围
    cutoff = datetime.now() - timedelta(minutes=minutes)
    filtered = []
    
    for item in history:
        try:
            dt_str = item.get("datetime", "")
            item_time = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            if item_time.replace(tzinfo=None) > cutoff:
                filtered.append(item)
        except:
            continue
    
    # 按时间排序（最新在前），限制条数
    filtered.sort(key=lambda x: x.get("datetime", ""), reverse=True)
    
    return filtered[:max_count]


# ==================== 测试入口 ====================

if __name__ == "__main__":
    print("测试 CGM 同步服务...")
    print(f"数据目录: {DATA_DIR}")
    
    all_devices = cgm_manager.get_all_active_devices()
    print(f"活跃设备: {len(all_devices)}")
    
    for device in all_devices:
        print(f"  - {device['player_id']}: {device['device_name']}")
    
    if all_devices:
        # 同步一次
        sync_all_players()
        
        # 显示结果
        for device in all_devices:
            player_id = device["player_id"]
            data = load_player_data(player_id)
            print(f"\n{player_id}:")
            print(f"  最后更新: {data.get('last_updated')}")
            if data.get('current'):
                print(f"  当前血糖: {data['current'].get('value')} mmol/L")
            print(f"  历史条数: {len(data.get('history', []))}")
    else:
        print("\n没有配置任何 CGM 设备。")
        print("请先添加设备：")
        print("1. 登录系统")
        print("2. 进入账户管理页面")
        print("3. 添加 CGM 设备")
