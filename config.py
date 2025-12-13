"""
用户配置文件
从 .env 文件读取配置，密码使用加密存储
"""

import os
import re
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 尝试导入加密工具
try:
    from crypto_utils import decrypt_password, get_or_create_key
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    print("⚠️  crypto_utils 未找到，将使用明文密码（不推荐）")


def _get_env(key: str, default: str = None) -> str:
    """获取环境变量"""
    return os.getenv(key, default)


def _decrypt_if_needed(value: str) -> str:
    """如果是加密的密码则解密"""
    if not value:
        return value
    
    # 检查是否是 Fernet 加密格式（以 gAAAAA 开头）
    if ENCRYPTION_AVAILABLE and value.startswith("gAAAAA"):
        try:
            return decrypt_password(value)
        except Exception as e:
            print(f"⚠️  密码解密失败: {e}")
            return value
    
    return value


def _get_password_from_keyring(user_id: str) -> str:
    """从系统 Keyring 获取密码"""
    try:
        import keyring
        password = keyring.get_password("glucose-pk", user_id)
        if password:
            return password
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️  从 Keyring 读取密码失败: {e}")
    return None


def _load_users_from_env() -> dict:
    """
    从环境变量动态加载用户配置
    支持格式: USER_<ID>_<FIELD>=value
    """
    users = {}
    
    # 查找所有 USER_*_NAME 来确定有哪些用户
    user_pattern = re.compile(r'^USER_(\d+)_NAME$')
    
    for key in os.environ:
        match = user_pattern.match(key)
        if match:
            user_num = match.group(1)
            user_id = f"user{user_num}"
            
            # 获取该用户的所有配置
            name = _get_env(f"USER_{user_num}_NAME")
            username = _get_env(f"USER_{user_num}_USERNAME")
            
            # 获取密码（优先级：Keyring > 加密密码 > 明文密码）
            password = None
            
            # 1. 先尝试 Keyring
            password = _get_password_from_keyring(user_id)
            
            # 2. 再尝试 .env 中的加密密码
            if not password:
                password_encrypted = _get_env(f"USER_{user_num}_PASSWORD_ENCRYPTED")
                if password_encrypted:
                    password = _decrypt_if_needed(password_encrypted)
            
            # 3. 最后尝试明文密码（不推荐）
            if not password:
                password_plain = _get_env(f"USER_{user_num}_PASSWORD")
                if password_plain:
                    print(f"⚠️  用户 {name} 使用明文密码，建议使用 Keyring 或加密密码")
                    password = password_plain
            
            region = _get_env(f"USER_{user_num}_REGION", "ous")
            avatar = _get_env(f"USER_{user_num}_AVATAR", f"images/avatar{user_num}.svg")
            color = _get_env(f"USER_{user_num}_COLOR", "#0077BB")
            
            if name and username and password:
                users[user_id] = {
                    "name": name,
                    "username": username,
                    "password": password,
                    "region": region,
                    "avatar": avatar,
                    "color": color,
                }
            else:
                missing = []
                if not name: missing.append("NAME")
                if not username: missing.append("USERNAME")
                if not password: missing.append("PASSWORD")
                print(f"⚠️  用户 {user_num} 配置不完整，缺少: {', '.join(missing)}")
    
    return users


# ==================== 加载配置 ====================

# 用户配置
USERS = _load_users_from_env()

if not USERS:
    print("=" * 50)
    print("⚠️  未找到用户配置！")
    print("请按以下步骤配置：")
    print("1. 复制 .env.example 为 .env")
    print("2. 运行 python crypto_utils.py 加密密码")
    print("3. 将加密后的密码填入 .env")
    print("=" * 50)
    
    # 提供默认演示用户（无真实凭据）
    USERS = {
        "user1": {
            "name": "演示用户1",
            "username": "demo1",
            "password": "demo",
            "region": "ous",
            "avatar": "images/avatar1.svg",
            "color": "#0077BB"
        },
        "user2": {
            "name": "演示用户2",
            "username": "demo2",
            "password": "demo",
            "region": "ous",
            "avatar": "images/avatar2.svg",
            "color": "#EE7733"
        },
    }

# 打印加载的用户（不显示敏感信息）
print(f"✅ 已加载 {len(USERS)} 个用户: {', '.join(u['name'] for u in USERS.values())}")


# ==================== 其他配置 ====================

# 血糖阈值设置（mmol/L）
THRESHOLDS = {
    "low": 3.9,          # 低血糖
    "normal_low": 4.4,
    "normal_high": 7.8,  # 正常上限
    "warning": 10.0,     # 警告
    "danger": 11.1       # 危险
}

# PK 游戏设置
PK_SETTINGS = {
    # 赛跑场景
    "race": {
        "track_length": 1000,
        "base_speed": 2,
        "optimal_range": (3.9, 7.8),
        "speed_penalty": 0.5,
    },
    
    # 漂流场景
    "river": {
        "optimal_range": (3.9, 7.8),
        "spawn_interval": 1500,
    },
    
    # 城堡场景
    "castle": {
        "optimal_range": (3.9, 7.8),
        "build_rate": 1.0,
        "damage_rate": 0.5,
    },
}

# Flask 配置
FLASK_PORT = int(_get_env("FLASK_PORT", "5010"))
FLASK_DEBUG = _get_env("FLASK_DEBUG", "false").lower() == "true"
DATA_REFRESH_INTERVAL = int(_get_env("DATA_REFRESH_INTERVAL", "30"))
