#!/usr/bin/env python3
"""
密码管理工具 - 统一接口
自动检测环境，选择最佳存储后端

使用方法：
    # 自动检测环境
    python password_manager.py set user1
    python password_manager.py get user1
    python password_manager.py list
    
    # 强制指定后端
    python password_manager.py set user1 --backend=keyring
    python password_manager.py set user1 --backend=encrypted
    
    # 交互模式
    python password_manager.py
"""

import os
import sys
import getpass
import json
import argparse
from pathlib import Path

# ==================== 配置 ====================

SERVICE_NAME = "glucose-pk"
SECRET_KEY_FILE = ".secret_key"
ENV_FILE = ".env"


# ==================== 后端检测 ====================

def detect_best_backend() -> str:
    """
    自动检测最佳后端
    返回: 'keyring' | 'encrypted'
    """
    # 1. 检查是否有可用的 Keyring
    if _is_keyring_available():
        return "keyring"
    
    # 2. 回退到加密文件
    return "encrypted"


def _is_keyring_available() -> bool:
    """检测 Keyring 是否可用"""
    try:
        import keyring
        from keyring.backends import fail
        
        # 获取当前后端
        backend = keyring.get_keyring()
        
        # 如果是 fail 后端，说明没有可用的 keyring
        if isinstance(backend, fail.Keyring):
            return False
        
        # 尝试一次测试写入
        try:
            test_key = f"{SERVICE_NAME}.__test__"
            keyring.set_password(SERVICE_NAME, test_key, "test")
            keyring.delete_password(SERVICE_NAME, test_key)
            return True
        except Exception:
            return False
            
    except ImportError:
        return False
    except Exception:
        return False


def get_backend_info() -> dict:
    """获取后端信息"""
    info = {
        "detected": detect_best_backend(),
        "keyring_available": _is_keyring_available(),
        "keyring_backend": None,
    }
    
    try:
        import keyring
        info["keyring_backend"] = str(keyring.get_keyring())
    except:
        pass
    
    return info


# ==================== Keyring 后端 ====================

class KeyringBackend:
    """系统 Keyring 存储"""
    
    name = "keyring"
    description = "系统钥匙串 (macOS Keychain / Windows Credential Manager / Linux Secret Service)"
    
    @staticmethod
    def is_available() -> bool:
        return _is_keyring_available()
    
    @staticmethod
    def set_password(user_id: str, password: str) -> bool:
        import keyring
        keyring.set_password(SERVICE_NAME, user_id, password)
        return True
    
    @staticmethod
    def get_password(user_id: str) -> str:
        import keyring
        return keyring.get_password(SERVICE_NAME, user_id)
    
    @staticmethod
    def delete_password(user_id: str) -> bool:
        import keyring
        try:
            keyring.delete_password(SERVICE_NAME, user_id)
            return True
        except keyring.errors.PasswordDeleteError:
            return False
    
    @staticmethod
    def list_passwords() -> list:
        """Keyring 不支持列出所有密码，返回空"""
        return []


# ==================== 加密文件后端 ====================

class EncryptedBackend:
    """加密文件存储（使用 Fernet）"""
    
    name = "encrypted"
    description = "加密文件存储 (AES-128)"
    
    @staticmethod
    def is_available() -> bool:
        try:
            from cryptography.fernet import Fernet
            return True
        except ImportError:
            return False
    
    @staticmethod
    def _get_key() -> bytes:
        """获取或创建加密密钥"""
        from cryptography.fernet import Fernet
        
        # 优先从环境变量读取
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            return env_key.encode() if isinstance(env_key, str) else env_key
        
        # 从文件读取或创建
        key_path = Path(SECRET_KEY_FILE)
        if key_path.exists():
            return key_path.read_bytes()
        
        # 生成新密钥
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        print(f"✅ 已生成加密密钥: {SECRET_KEY_FILE}")
        return key
    
    @staticmethod
    def encrypt(password: str) -> str:
        """加密密码"""
        from cryptography.fernet import Fernet
        key = EncryptedBackend._get_key()
        f = Fernet(key)
        return f.encrypt(password.encode()).decode()
    
    @staticmethod
    def decrypt(encrypted: str) -> str:
        """解密密码"""
        from cryptography.fernet import Fernet
        key = EncryptedBackend._get_key()
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
    
    @staticmethod
    def set_password(user_id: str, password: str) -> bool:
        """加密并保存到 .env"""
        encrypted = EncryptedBackend.encrypt(password)
        user_num = user_id.replace("user", "")
        env_key = f"USER_{user_num}_PASSWORD_ENCRYPTED"
        
        _update_env_file(env_key, encrypted)
        return True
    
    @staticmethod
    def get_password(user_id: str) -> str:
        """从 .env 读取并解密"""
        user_num = user_id.replace("user", "")
        env_key = f"USER_{user_num}_PASSWORD_ENCRYPTED"
        
        encrypted = _read_env_value(env_key)
        if encrypted:
            try:
                return EncryptedBackend.decrypt(encrypted)
            except Exception as e:
                print(f"⚠️  解密失败: {e}")
        return None
    
    @staticmethod
    def delete_password(user_id: str) -> bool:
        """从 .env 删除密码"""
        user_num = user_id.replace("user", "")
        env_key = f"USER_{user_num}_PASSWORD_ENCRYPTED"
        return _remove_env_key(env_key)
    
    @staticmethod
    def list_passwords() -> list:
        """列出 .env 中的加密密码"""
        result = []
        env_path = Path(ENV_FILE)
        if env_path.exists():
            content = env_path.read_text()
            import re
            for match in re.finditer(r'USER_(\d+)_PASSWORD_ENCRYPTED=', content):
                result.append(f"user{match.group(1)}")
        return result


# ==================== .env 文件操作 ====================

def _read_env_value(key: str) -> str:
    """从 .env 读取值"""
    env_path = Path(ENV_FILE)
    if not env_path.exists():
        return None
    
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line[len(key) + 1:]
    return None


def _update_env_file(key: str, value: str):
    """更新 .env 文件中的值"""
    env_path = Path(ENV_FILE)
    lines = []
    found = False
    
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    
    if not found:
        lines.append(f"{key}={value}")
    
    env_path.write_text("\n".join(lines) + "\n")


def _remove_env_key(key: str) -> bool:
    """从 .env 删除键"""
    env_path = Path(ENV_FILE)
    if not env_path.exists():
        return False
    
    lines = []
    found = False
    for line in env_path.read_text().splitlines():
        if line.strip().startswith(f"{key}="):
            found = True
        else:
            lines.append(line)
    
    if found:
        env_path.write_text("\n".join(lines) + "\n")
    return found


# ==================== 统一接口 ====================

def get_backend(backend_name: str = None):
    """获取后端实例"""
    if backend_name is None:
        backend_name = detect_best_backend()
    
    if backend_name == "keyring":
        if not KeyringBackend.is_available():
            print("⚠️  Keyring 不可用，切换到加密文件后端")
            return EncryptedBackend
        return KeyringBackend
    else:
        return EncryptedBackend


def set_password(user_id: str, password: str, backend_name: str = None) -> bool:
    """存储密码"""
    backend = get_backend(backend_name)
    success = backend.set_password(user_id, password)
    if success:
        print(f"✅ 密码已保存 [{backend.name}]: {user_id}")
    return success


def get_password(user_id: str, backend_name: str = None) -> str:
    """获取密码（会尝试所有后端）"""
    # 如果指定了后端，只用那个
    if backend_name:
        backend = get_backend(backend_name)
        return backend.get_password(user_id)
    
    # 否则按优先级尝试
    # 1. Keyring
    if KeyringBackend.is_available():
        pwd = KeyringBackend.get_password(user_id)
        if pwd:
            return pwd
    
    # 2. 加密文件
    if EncryptedBackend.is_available():
        pwd = EncryptedBackend.get_password(user_id)
        if pwd:
            return pwd
    
    return None


def delete_password(user_id: str, backend_name: str = None) -> bool:
    """删除密码"""
    backend = get_backend(backend_name)
    success = backend.delete_password(user_id)
    if success:
        print(f"✅ 密码已删除 [{backend.name}]: {user_id}")
    else:
        print(f"⚠️  未找到密码: {user_id}")
    return success


# ==================== CLI ====================

def print_status():
    """打印状态信息"""
    info = get_backend_info()
    
    print("=" * 55)
    print("🔐 密码管理工具")
    print("=" * 55)
    print()
    print(f"自动检测后端: {info['detected']}")
    print()
    print("后端状态:")
    print(f"  • Keyring:   {'✅ 可用' if info['keyring_available'] else '❌ 不可用'}")
    if info['keyring_backend']:
        print(f"               {info['keyring_backend']}")
    print(f"  • Encrypted: {'✅ 可用' if EncryptedBackend.is_available() else '❌ 不可用'}")
    print()
    
    # 显示已存储的密码
    print("已存储的密码:")
    found = False
    
    if info['keyring_available']:
        # Keyring 不支持列出，但可以尝试检测 .env 中的用户
        pass
    
    encrypted_users = EncryptedBackend.list_passwords()
    if encrypted_users:
        for user in encrypted_users:
            print(f"  • {user} [encrypted]")
            found = True
    
    if not found:
        print("  (无，或存储在 Keyring 中)")


def interactive_mode():
    """交互模式"""
    print_status()
    
    print()
    print("操作:")
    print("  1. 存储密码")
    print("  2. 获取密码")
    print("  3. 删除密码")
    print("  4. 退出")
    print()
    
    choice = input("请选择 [1-4]: ").strip()
    
    if choice == "1":
        user_id = input("用户 ID (如 user1): ").strip() or "user1"
        password = getpass.getpass("Dexcom 密码: ")
        if password:
            set_password(user_id, password)
    
    elif choice == "2":
        user_id = input("用户 ID (如 user1): ").strip() or "user1"
        pwd = get_password(user_id)
        if pwd:
            # 只显示部分
            masked = pwd[:2] + "*" * (len(pwd) - 4) + pwd[-2:] if len(pwd) > 4 else "****"
            print(f"✅ 密码: {masked}")
        else:
            print("❌ 未找到密码")
    
    elif choice == "3":
        user_id = input("用户 ID (如 user1): ").strip() or "user1"
        delete_password(user_id)
    
    elif choice == "4":
        return


def main():
    parser = argparse.ArgumentParser(
        description="密码管理工具 - 统一存储 Dexcom 密码",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 交互模式
  %(prog)s status                   # 查看状态
  %(prog)s set user1                # 存储密码（会提示输入）
  %(prog)s set user1 -p PASSWORD    # 存储密码（直接指定）
  %(prog)s get user1                # 获取密码
  %(prog)s delete user1             # 删除密码
  
  # 强制使用特定后端
  %(prog)s set user1 --backend=keyring
  %(prog)s set user1 --backend=encrypted
        """
    )
    
    parser.add_argument("command", nargs="?", choices=["status", "set", "get", "delete"],
                        help="命令")
    parser.add_argument("user_id", nargs="?", help="用户 ID (如 user1)")
    parser.add_argument("-p", "--password", help="密码（不指定则提示输入）")
    parser.add_argument("-b", "--backend", choices=["keyring", "encrypted"],
                        help="强制使用指定后端")
    
    args = parser.parse_args()
    
    # 无参数时进入交互模式
    if args.command is None:
        interactive_mode()
        return
    
    # status 命令
    if args.command == "status":
        print_status()
        return
    
    # 其他命令需要 user_id
    if not args.user_id:
        parser.error(f"命令 '{args.command}' 需要指定 user_id")
    
    if args.command == "set":
        password = args.password or getpass.getpass("Dexcom 密码: ")
        if password:
            set_password(args.user_id, password, args.backend)
        else:
            print("❌ 密码不能为空")
    
    elif args.command == "get":
        pwd = get_password(args.user_id, args.backend)
        if pwd:
            masked = pwd[:2] + "*" * (len(pwd) - 4) + pwd[-2:] if len(pwd) > 4 else "****"
            print(f"✅ 密码: {masked}")
        else:
            print("❌ 未找到密码")
    
    elif args.command == "delete":
        delete_password(args.user_id, args.backend)


if __name__ == "__main__":
    main()
