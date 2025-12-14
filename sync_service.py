"""
Dexcom 数据同步服务
后台线程定时从 Dexcom API 拉取数据，存储到本地 JSON 文件

特性：
- 每 3 分钟同步一次（Dexcom 数据每 5 分钟更新）
- 本地 JSON 存储，按用户分文件
- 保留 48 小时历史数据
- 线程安全的读写
- 自动清理过期数据
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from pydexcom import Dexcom
from config import USERS

# ==================== 配置 ====================

# 同步间隔（秒）
SYNC_INTERVAL = 180  # 3 分钟

# 本地数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glucose_data")

# 保留多少小时的历史数据
HISTORY_HOURS = 48

# ==================== 全局状态 ====================

# Dexcom 客户端缓存
_dexcom_clients = {}
_clients_lock = threading.Lock()

# 数据读写锁（每个用户一个）
_data_locks = {}

# 同步状态
sync_status = {
    "last_sync": None,
    "last_success": None,
    "errors": [],
    "is_running": False
}


def _get_data_lock(user_id):
    """获取用户的数据锁"""
    if user_id not in _data_locks:
        _data_locks[user_id] = threading.Lock()
    return _data_locks[user_id]


def _get_dexcom_client(user_id):
    """获取 Dexcom 客户端（带缓存）"""
    global _dexcom_clients
    
    if user_id not in USERS:
        raise ValueError(f"未知用户: {user_id}")
    
    with _clients_lock:
        if user_id not in _dexcom_clients:
            user = USERS[user_id]
            _dexcom_clients[user_id] = Dexcom(
                username=user["username"],
                password=user["password"],
                region=user.get("region", "us")
            )
    
    return _dexcom_clients[user_id]


def _get_user_data_file(user_id):
    """获取用户数据文件路径"""
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"{user_id}.json")


# ==================== 数据读写 ====================

def load_user_data(user_id):
    """
    从本地文件加载用户数据
    
    Returns:
        dict: {
            "user_id": "user1",
            "last_updated": "2025-01-15T14:35:00",
            "current": { ... },
            "history": [ ... ]
        }
    """
    filepath = _get_user_data_file(user_id)
    lock = _get_data_lock(user_id)
    
    with lock:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 加载 {user_id} 数据失败: {e}")
    
    # 返回空数据结构
    return {
        "user_id": user_id,
        "last_updated": None,
        "current": None,
        "history": []
    }


def save_user_data(user_id, data):
    """保存用户数据到本地文件"""
    filepath = _get_user_data_file(user_id)
    lock = _get_data_lock(user_id)
    
    with lock:
        try:
            # 先写临时文件，再重命名（原子操作）
            temp_file = filepath + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, filepath)
        except Exception as e:
            print(f"❌ 保存 {user_id} 数据失败: {e}")


def clean_old_history(history, hours=HISTORY_HOURS):
    """清理过期的历史数据"""
    if not history:
        return []
    
    cutoff = datetime.now() - timedelta(hours=hours)
    
    cleaned = []
    for item in history:
        try:
            item_time = datetime.fromisoformat(item["datetime"].replace("Z", "+00:00"))
            # 转为无时区比较
            if item_time.replace(tzinfo=None) > cutoff:
                cleaned.append(item)
        except:
            continue
    
    return cleaned


# ==================== Dexcom 同步 ====================

def sync_user_data(user_id, warmup=False):
    """
    从 Dexcom 同步单个用户的数据
    
    Args:
        user_id: 用户 ID
        warmup: 是否为预热模式（拉取更多历史数据）
    
    Returns:
        bool: 是否成功
    """
    try:
        client = _get_dexcom_client(user_id)
        
        # 获取当前血糖
        current_reading = client.get_current_glucose_reading()
        
        # 预热模式拉取 24 小时，正常模式拉取 3 小时
        if warmup:
            history_minutes = 1440  # 24 小时
            history_count = 288     # 24 小时 × 12 个/小时
        else:
            history_minutes = 180   # 3 小时
            history_count = 36
        
        history_readings = client.get_glucose_readings(minutes=history_minutes, max_count=history_count)
        
        # 加载现有本地数据
        local_data = load_user_data(user_id)
        
        # 更新当前值
        if current_reading:
            local_data["current"] = {
                "value": current_reading.mmol_l,
                "value_mgdl": current_reading.value,
                "trend": current_reading.trend,
                "trend_direction": current_reading.trend_direction,
                "trend_description": current_reading.trend_description,
                "trend_arrow": current_reading.trend_arrow,
                "datetime": current_reading.datetime.isoformat(),
            }
        
        # 合并历史数据（去重）
        existing_times = set()
        for item in local_data.get("history", []):
            existing_times.add(item.get("datetime"))
        
        new_history = list(local_data.get("history", []))
        
        for reading in history_readings:
            dt_str = reading.datetime.isoformat()
            if dt_str not in existing_times:
                new_history.append({
                    "value": reading.mmol_l,
                    "value_mgdl": reading.value,
                    "trend_arrow": reading.trend_arrow,
                    "datetime": dt_str,
                })
                existing_times.add(dt_str)
        
        # 按时间排序（最新在前）
        new_history.sort(key=lambda x: x["datetime"], reverse=True)
        
        # 清理过期数据
        new_history = clean_old_history(new_history)
        
        local_data["history"] = new_history
        local_data["last_updated"] = datetime.now().isoformat()
        
        # 保存到本地
        save_user_data(user_id, local_data)
        
        return True
        
    except Exception as e:
        print(f"❌ 同步 {user_id} 失败: {e}")
        return False


def check_needs_warmup(user_id):
    """
    检查用户是否需要预热（本地数据为空或不足 24 小时）
    """
    local_data = load_user_data(user_id)
    history = local_data.get("history", [])
    
    if not history:
        return True
    
    # 检查数据是否覆盖 24 小时
    try:
        oldest = min(history, key=lambda x: x["datetime"])
        oldest_time = datetime.fromisoformat(oldest["datetime"].replace("Z", "+00:00"))
        age = datetime.now() - oldest_time.replace(tzinfo=None)
        
        # 如果最老的数据不到 20 小时，需要预热
        if age < timedelta(hours=20):
            return True
    except:
        return True
    
    return False


def warmup_all_users():
    """预热所有用户数据（拉取 24 小时历史）"""
    print("🔥 检查是否需要预热数据...")
    
    for user_id in USERS.keys():
        if check_needs_warmup(user_id):
            print(f"   📥 预热 {user_id} 数据（拉取24小时历史）...")
            if sync_user_data(user_id, warmup=True):
                local_data = load_user_data(user_id)
                print(f"   ✅ {user_id} 预热完成，共 {len(local_data.get('history', []))} 条数据")
            else:
                print(f"   ❌ {user_id} 预热失败")
        else:
            print(f"   ✓ {user_id} 数据充足，无需预热")


def sync_all_users():
    """同步所有用户的数据"""
    global sync_status
    
    sync_status["last_sync"] = datetime.now().isoformat()
    sync_status["is_running"] = True
    
    success_count = 0
    errors = []
    
    for user_id in USERS.keys():
        try:
            if sync_user_data(user_id, warmup=False):
                success_count += 1
            else:
                errors.append(f"{user_id}: 同步失败")
        except Exception as e:
            errors.append(f"{user_id}: {str(e)}")
    
    if success_count == len(USERS):
        sync_status["last_success"] = datetime.now().isoformat()
    
    sync_status["errors"] = errors[-10:]  # 只保留最近 10 条错误
    sync_status["is_running"] = False
    
    print(f"✅ 数据同步完成: {success_count}/{len(USERS)} 成功 ({datetime.now().strftime('%H:%M:%S')})")


# ==================== 后台线程 ====================

def _sync_loop():
    """后台同步循环"""
    print(f"🔄 Dexcom 同步服务启动，间隔: {SYNC_INTERVAL}秒")
    
    # 启动时先预热（补足 24 小时数据）
    warmup_all_users()
    
    # 然后正常同步一次
    sync_all_users()
    
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            sync_all_users()
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


def get_sync_status():
    """获取同步状态"""
    return sync_status.copy()


# ==================== 供 data_fetcher 调用的接口 ====================

def get_current_from_local(user_id):
    """
    从本地获取当前血糖（供 data_fetcher 调用）
    
    Returns:
        dict: 当前血糖数据，或 None
    """
    data = load_user_data(user_id)
    return data.get("current")


def get_history_from_local(user_id, minutes=180, max_count=36):
    """
    从本地获取历史数据（供 data_fetcher 调用）
    
    Args:
        user_id: 用户 ID
        minutes: 获取多少分钟内的数据
        max_count: 最大条数
    
    Returns:
        list: 历史数据列表
    """
    data = load_user_data(user_id)
    history = data.get("history", [])
    
    if not history:
        return []
    
    # 过滤时间范围
    cutoff = datetime.now() - timedelta(minutes=minutes)
    filtered = []
    
    for item in history:
        try:
            item_time = datetime.fromisoformat(item["datetime"].replace("Z", "+00:00"))
            if item_time.replace(tzinfo=None) > cutoff:
                filtered.append(item)
        except:
            continue
    
    # 按时间排序（最新在前），限制条数
    filtered.sort(key=lambda x: x["datetime"], reverse=True)
    
    return filtered[:max_count]


# ==================== 测试入口 ====================

if __name__ == "__main__":
    print("测试 Dexcom 同步服务...")
    print(f"数据目录: {DATA_DIR}")
    print(f"用户列表: {list(USERS.keys())}")
    
    # 同步一次
    sync_all_users()
    
    # 显示结果
    for user_id in USERS.keys():
        data = load_user_data(user_id)
        print(f"\n{user_id}:")
        print(f"  最后更新: {data.get('last_updated')}")
        if data.get('current'):
            print(f"  当前血糖: {data['current'].get('value')} mmol/L")
        print(f"  历史条数: {len(data.get('history', []))}")
