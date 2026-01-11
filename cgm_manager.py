"""
CGM 设备管理器
管理用户的 CGM 设备配置，支持加密存储凭证

数据存储结构：
data/cgm_devices/
├── {username}.json    # 每个用户一个配置文件
└── ...

每个用户的配置文件格式：
{
    "devices": [
        {
            "id": "dexcom_001",
            "type": "dexcom",
            "name": "我的 Dexcom G7",
            "credentials": {
                "username": "加密后的用户名",
                "password": "加密后的密码",
                "region": "ous"
            },
            "display": {
                "avatar": "🩸",
                "color": "#4CAF50"
            },
            "is_active": true,
            "added_at": "2025-01-11T10:00:00"
        }
    ],
    "default_device": "dexcom_001"
}
"""

import os
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from cgm_providers import get_provider, get_supported_devices, PROVIDER_TYPES
from cgm_providers.base import BaseCGMProvider


# ==================== 配置 ====================

# 设备配置目录
CGM_DEVICES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "data", 
    "cgm_devices"
)

# 默认头像和颜色
DEFAULT_AVATARS = ["🩸", "💉", "📊", "🎯", "⭐", "🌟", "💫", "🔥"]
DEFAULT_COLORS = ["#4CAF50", "#2196F3", "#FF9800", "#E91E63", "#9C27B0", "#00BCD4"]


# ==================== 加密工具 ====================

def _get_cipher():
    """获取加密器（复用 password_manager 的逻辑）"""
    from cryptography.fernet import Fernet
    
    # 优先从环境变量读取
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        key = env_key.encode() if isinstance(env_key, str) else env_key
    else:
        # 从文件读取或创建
        key_file = Path(".secret_key")
        if key_file.exists():
            key = key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            print(f"✅ 已生成加密密钥: .secret_key")
    
    return Fernet(key)


def _encrypt(value: str) -> str:
    """加密字符串"""
    cipher = _get_cipher()
    return cipher.encrypt(value.encode()).decode()


def _decrypt(encrypted: str) -> str:
    """解密字符串"""
    cipher = _get_cipher()
    return cipher.decrypt(encrypted.encode()).decode()


def _encrypt_credentials(credentials: dict) -> dict:
    """加密凭证中的敏感字段"""
    encrypted = {}
    for key, value in credentials.items():
        if key in ('password',) and value:  # 只加密密码
            encrypted[key] = _encrypt(value)
        else:
            encrypted[key] = value
    return encrypted


def _decrypt_credentials(credentials: dict) -> dict:
    """解密凭证中的敏感字段"""
    decrypted = {}
    for key, value in credentials.items():
        if key in ('password',) and value and value.startswith('gAAAAA'):
            try:
                decrypted[key] = _decrypt(value)
            except Exception:
                decrypted[key] = value  # 解密失败保留原值
        else:
            decrypted[key] = value
    return decrypted


# ==================== CGM 管理器 ====================

class CGMManager:
    """CGM 设备管理器"""
    
    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._provider_cache: Dict[str, BaseCGMProvider] = {}
        
        # 确保目录存在
        os.makedirs(CGM_DEVICES_DIR, exist_ok=True)
    
    def _get_lock(self, username: str) -> threading.Lock:
        """获取用户的文件锁"""
        if username not in self._locks:
            self._locks[username] = threading.Lock()
        return self._locks[username]
    
    def _get_user_file(self, username: str) -> Path:
        """获取用户配置文件路径"""
        return Path(CGM_DEVICES_DIR) / f"{username}.json"
    
    def _load_user_config(self, username: str) -> dict:
        """加载用户配置"""
        filepath = self._get_user_file(username)
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 加载 {username} 设备配置失败: {e}")
        
        return {"devices": [], "default_device": None}
    
    def _save_user_config(self, username: str, config: dict):
        """保存用户配置"""
        filepath = self._get_user_file(username)
        with self._get_lock(username):
            try:
                # 原子写入
                temp_file = str(filepath) + ".tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                os.replace(temp_file, filepath)
            except Exception as e:
                print(f"❌ 保存 {username} 设备配置失败: {e}")
                raise
    
    def _generate_device_id(self, device_type: str) -> str:
        """生成设备 ID"""
        short_uuid = uuid.uuid4().hex[:8]
        return f"{device_type}_{short_uuid}"
    
    # ==================== 设备管理 ====================
    
    def add_device(
        self, 
        username: str, 
        device_type: str, 
        credentials: dict,
        device_name: str = None,
        avatar: str = None,
        color: str = None
    ) -> dict:
        """
        添加新设备
        
        Args:
            username: 用户名
            device_type: 设备类型 ('dexcom', 'libre')
            credentials: 凭证（用户名、密码等）
            device_name: 设备名称（可选）
            avatar: 头像 emoji（可选）
            color: 颜色（可选）
        
        Returns:
            新添加的设备信息
        """
        if device_type not in PROVIDER_TYPES:
            raise ValueError(f"不支持的设备类型: {device_type}")
        
        config = self._load_user_config(username)
        devices = config.get("devices", [])
        
        # 生成 ID
        device_id = self._generate_device_id(device_type)
        
        # 默认名称
        if not device_name:
            device_name = f"我的 {PROVIDER_TYPES[device_type]['name']}"
        
        # 默认头像和颜色
        device_index = len(devices)
        if not avatar:
            avatar = DEFAULT_AVATARS[device_index % len(DEFAULT_AVATARS)]
        if not color:
            color = DEFAULT_COLORS[device_index % len(DEFAULT_COLORS)]
        
        # 加密凭证
        encrypted_creds = _encrypt_credentials(credentials)
        
        new_device = {
            "id": device_id,
            "type": device_type,
            "name": device_name,
            "credentials": encrypted_creds,
            "display": {
                "avatar": avatar,
                "color": color
            },
            "is_active": True,
            "added_at": datetime.now().isoformat()
        }
        
        devices.append(new_device)
        config["devices"] = devices
        
        # 如果是第一个设备，设为默认
        if config.get("default_device") is None:
            config["default_device"] = device_id
        
        self._save_user_config(username, config)
        
        # 清除缓存
        cache_key = f"{username}_{device_id}"
        if cache_key in self._provider_cache:
            del self._provider_cache[cache_key]
        
        # 返回时不包含加密凭证
        safe_device = {**new_device}
        safe_device["credentials"] = {k: "***" for k in credentials.keys()}
        
        return safe_device
    
    def remove_device(self, username: str, device_id: str) -> bool:
        """删除设备"""
        config = self._load_user_config(username)
        devices = config.get("devices", [])
        
        # 查找并删除
        new_devices = [d for d in devices if d["id"] != device_id]
        
        if len(new_devices) == len(devices):
            return False  # 没找到
        
        config["devices"] = new_devices
        
        # 如果删除的是默认设备，重新选择
        if config.get("default_device") == device_id:
            config["default_device"] = new_devices[0]["id"] if new_devices else None
        
        self._save_user_config(username, config)
        
        # 清除缓存
        cache_key = f"{username}_{device_id}"
        if cache_key in self._provider_cache:
            del self._provider_cache[cache_key]
        
        return True
    
    def update_device(
        self, 
        username: str, 
        device_id: str, 
        updates: dict
    ) -> Optional[dict]:
        """
        更新设备信息
        
        可更新的字段：name, display (avatar, color), is_active
        凭证更新请使用 update_device_credentials
        """
        config = self._load_user_config(username)
        devices = config.get("devices", [])
        
        for device in devices:
            if device["id"] == device_id:
                # 更新允许的字段
                if "name" in updates:
                    device["name"] = updates["name"]
                if "display" in updates:
                    device["display"] = {**device.get("display", {}), **updates["display"]}
                if "is_active" in updates:
                    device["is_active"] = updates["is_active"]
                
                self._save_user_config(username, config)
                
                # 返回安全版本
                safe_device = {**device}
                safe_device["credentials"] = {k: "***" for k in device["credentials"].keys()}
                return safe_device
        
        return None
    
    def update_device_credentials(
        self, 
        username: str, 
        device_id: str, 
        credentials: dict
    ) -> bool:
        """更新设备凭证"""
        config = self._load_user_config(username)
        devices = config.get("devices", [])
        
        for device in devices:
            if device["id"] == device_id:
                device["credentials"] = _encrypt_credentials(credentials)
                self._save_user_config(username, config)
                
                # 清除缓存
                cache_key = f"{username}_{device_id}"
                if cache_key in self._provider_cache:
                    del self._provider_cache[cache_key]
                
                return True
        
        return False
    
    def set_default_device(self, username: str, device_id: str) -> bool:
        """设置默认设备"""
        config = self._load_user_config(username)
        devices = config.get("devices", [])
        
        # 检查设备是否存在
        if not any(d["id"] == device_id for d in devices):
            return False
        
        config["default_device"] = device_id
        self._save_user_config(username, config)
        return True
    
    # ==================== 查询 ====================
    
    def get_devices(self, username: str) -> List[dict]:
        """
        获取用户的所有设备（不包含凭证）
        """
        config = self._load_user_config(username)
        devices = config.get("devices", [])
        
        # 移除敏感信息
        safe_devices = []
        for device in devices:
            safe_device = {**device}
            safe_device["credentials"] = {k: "***" for k in device.get("credentials", {}).keys()}
            safe_device["is_default"] = (device["id"] == config.get("default_device"))
            safe_devices.append(safe_device)
        
        return safe_devices
    
    def get_device(self, username: str, device_id: str) -> Optional[dict]:
        """获取单个设备（不包含凭证）"""
        devices = self.get_devices(username)
        for device in devices:
            if device["id"] == device_id:
                return device
        return None
    
    def get_default_device(self, username: str) -> Optional[dict]:
        """获取用户的默认设备"""
        config = self._load_user_config(username)
        default_id = config.get("default_device")
        
        if not default_id:
            return None
        
        return self.get_device(username, default_id)
    
    def has_devices(self, username: str) -> bool:
        """检查用户是否有设备"""
        config = self._load_user_config(username)
        return len(config.get("devices", [])) > 0
    
    # ==================== Provider 获取 ====================
    
    def get_provider(self, username: str, device_id: str = None) -> Optional[BaseCGMProvider]:
        """
        获取设备的 Provider 实例（带缓存）
        
        Args:
            username: 用户名
            device_id: 设备 ID（可选，默认使用用户的默认设备）
        
        Returns:
            BaseCGMProvider 实例或 None
        """
        config = self._load_user_config(username)
        devices = config.get("devices", [])
        
        # 确定要使用的设备
        target_id = device_id or config.get("default_device")
        if not target_id:
            return None
        
        # 查找设备
        target_device = None
        for device in devices:
            if device["id"] == target_id:
                target_device = device
                break
        
        if not target_device:
            return None
        
        # 检查缓存
        cache_key = f"{username}_{target_id}"
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]
        
        # 创建 Provider
        try:
            decrypted_creds = _decrypt_credentials(target_device["credentials"])
            provider = get_provider(target_device["type"], decrypted_creds)
            self._provider_cache[cache_key] = provider
            return provider
        except Exception as e:
            print(f"❌ 创建 Provider 失败 ({target_id}): {e}")
            return None
    
    def get_all_active_devices(self) -> List[dict]:
        """
        获取所有用户的活跃设备（用于 PK）
        
        Returns:
            列表，每个元素包含：
            {
                "username": "amy",
                "device_id": "dexcom_001",
                "device_name": "Amy's Dexcom",
                "device_type": "dexcom",
                "avatar": "🩸",
                "color": "#4CAF50",
                "player_id": "amy_dexcom_001"  # 用于 API 的唯一标识
            }
        """
        all_devices = []
        
        # 遍历所有用户配置文件
        for filepath in Path(CGM_DEVICES_DIR).glob("*.json"):
            username = filepath.stem
            
            try:
                config = self._load_user_config(username)
                devices = config.get("devices", [])
                
                for device in devices:
                    if device.get("is_active", True):
                        all_devices.append({
                            "username": username,
                            "device_id": device["id"],
                            "device_name": device["name"],
                            "device_type": device["type"],
                            "avatar": device.get("display", {}).get("avatar", "🩸"),
                            "color": device.get("display", {}).get("color", "#666"),
                            "player_id": f"{username}_{device['id']}"
                        })
            except Exception as e:
                print(f"⚠️ 加载 {username} 设备失败: {e}")
                continue
        
        return all_devices
    
    def test_device_connection(self, username: str, device_id: str) -> dict:
        """测试设备连接"""
        provider = self.get_provider(username, device_id)
        if provider:
            return provider.test_connection()
        return {
            "success": False,
            "message": "设备不存在或无法创建连接"
        }
    
    def test_credentials(self, device_type: str, credentials: dict) -> dict:
        """
        测试凭证（添加设备前验证）
        
        Args:
            device_type: 设备类型
            credentials: 凭证（明文）
        
        Returns:
            {
                "success": bool,
                "message": str,
                "current_reading": dict (如果成功)
            }
        """
        try:
            provider = get_provider(device_type, credentials)
            return provider.test_connection()
        except Exception as e:
            return {
                "success": False,
                "message": f"创建连接失败: {str(e)}"
            }


# ==================== 全局实例 ====================

cgm_manager = CGMManager()
