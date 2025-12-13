"""
密码管理工具 - 多后端支持
支持：
1. 系统 Keyring（macOS Keychain / Windows Credential Manager / Linux Secret Service）
2. Fernet 加密文件（.env 方式）
3. 环境变量（Docker/云部署）
"""

import os
import sys

# ==================== 后端选择 ====================

BACKEND = os.getenv("PASSWORD_BACKEND", "auto")  # auto, keyring, fernet, env

def get_backend():
    """自动选择最佳后端"""
    if BACKEND != "auto":
        return BACKEND
    
    # 优先使用系统 keyring
    try:
        import keyring
        # 测试 keyring 是否可用
        keyring.get_keyring()
        return "keyring"
    except:
        pass
    
    # 其次使用 Fernet 加密
    try:
        from cryptography.fernet import Fernet
        return "fernet"
    except:
        pass
    
    # 最后用环境变量
    return "env"


# ==================== Keyring 后端 ====================

class KeyringBackend:
    """使用系统 Keyring 存储密码"""
    
    SERVICE_NAME = "glucose-pk"
    
    @staticmethod
    def is_available():
        try:
            import keyring
            return True
        except ImportError:
            return False
    
    @staticmethod
    def set_password(user_id: str, password: str):
        import keyring
        keyring.set_password(KeyringBackend.SERVICE_NAME, user_id, password)
        print(f"✅ 密码已保存到系统 Keyring: {user_id}")
    
    @staticmethod
    def get_password(user_id: str) -> str:
        import keyring
        return keyring.get_password(KeyringBackend.SERVICE_NAME, user_id)
    
    @staticmethod
    def delete_password(user_id: str):
        import keyring
        try:
            keyring.delete_password(KeyringBackend.SERVICE_NAME, user_id)
            print(f"✅ 已删除: {user_id}")
        except keyring.errors.PasswordDeleteError:
            print(f"⚠️ 未找到: {user_id}")


# ==================== Fernet 后端 ====================

class FernetBackend:
    """使用 Fernet 加密存储密码"""
    
    @staticmethod
    def is_available():
        try:
            from cryptography.fernet import Fernet
            return True
        except ImportError:
            return False
    
    @staticmethod
    def get_key():
        from cryptography.fernet import Fernet
        
        # 优先环境变量
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            return env_key.encode()
        
        # 其次文件
        key_file = ".secret_key"
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        
        # 生成新密钥
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
        print(f"✅ 已生成密钥: {key_file}")
        return key
    
    @staticmethod
    def encrypt(password: str) -> str:
        from cryptography.fernet import Fernet
        f = Fernet(FernetBackend.get_key())
        return f.encrypt(password.encode()).decode()
    
    @staticmethod
    def decrypt(encrypted: str) -> str:
        from cryptography.fernet import Fernet
        f = Fernet(FernetBackend.get_key())
        return f.decrypt(encrypted.encode()).decode()


# ==================== 环境变量后端 ====================

class EnvBackend:
    """从环境变量读取（明文，不推荐）"""
    
    @staticmethod
    def is_available():
        return True
    
    @staticmethod
    def get_password(user_id: str) -> str:
        # USER_1_PASSWORD 或 USER_1_PASSWORD_ENCRYPTED
        user_num = user_id.replace("user", "")
        return os.getenv(f"USER_{user_num}_PASSWORD")


# ==================== 统一接口 ====================

def store_password(user_id: str, password: str):
    """存储密码"""
    backend = get_backend()
    
    if backend == "keyring" and KeyringBackend.is_available():
        KeyringBackend.set_password(user_id, password)
    elif backend == "fernet" and FernetBackend.is_available():
        encrypted = FernetBackend.encrypt(password)
        print(f"\n用户 {user_id} 的加密密码：")
        print(f"USER_{user_id.upper().replace('USER', '')}_PASSWORD_ENCRYPTED={encrypted}")
        print("\n请将上面这行添加到 .env 文件")
    else:
        print("⚠️ 请手动设置环境变量：")
        print(f"USER_{user_id.upper().replace('USER', '')}_PASSWORD={password}")


def retrieve_password(user_id: str, encrypted_value: str = None) -> str:
    """获取密码"""
    backend = get_backend()
    
    # Keyring
    if backend == "keyring" and KeyringBackend.is_available():
        pwd = KeyringBackend.get_password(user_id)
        if pwd:
            return pwd
    
    # Fernet 解密
    if encrypted_value and encrypted_value.startswith("gAAAAA"):
        if FernetBackend.is_available():
            try:
                return FernetBackend.decrypt(encrypted_value)
            except Exception as e:
                print(f"⚠️ 解密失败: {e}")
    
    # 明文
    if encrypted_value:
        return encrypted_value
    
    return None


# ==================== 命令行工具 ====================

def print_status():
    """打印当前状态"""
    print("=" * 50)
    print("🔐 密码管理工具")
    print("=" * 50)
    
    backend = get_backend()
    print(f"\n当前后端: {backend}")
    
    print(f"\nKeyring: {'✅ 可用' if KeyringBackend.is_available() else '❌ 不可用 (pip install keyring)'}")
    print(f"Fernet:  {'✅ 可用' if FernetBackend.is_available() else '❌ 不可用 (pip install cryptography)'}")
    print(f"Env:     ✅ 可用（明文，不推荐）")
    
    if backend == "keyring":
        print("\n💡 密码存储在系统 Keyring 中，迁移时需要重新设置")
    elif backend == "fernet":
        print("\n💡 密码加密存储在 .env 中，迁移时需要复制 .secret_key 或设置 ENCRYPTION_KEY")


def interactive_menu():
    """交互式菜单"""
    print_status()
    
    print("\n操作：")
    print("1. 存储密码")
    print("2. 测试获取密码")
    print("3. 批量设置用户密码")
    print("4. 退出")
    
    choice = input("\n请选择 (1-4): ").strip()
    
    if choice == "1":
        user_id = input("用户ID (如 user1): ").strip() or "user1"
        password = input("Dexcom 密码: ").strip()
        if password:
            store_password(user_id, password)
    
    elif choice == "2":
        user_id = input("用户ID (如 user1): ").strip() or "user1"
        pwd = retrieve_password(user_id)
        if pwd:
            print(f"✅ 密码: {pwd[:3]}{'*' * (len(pwd)-3)}")
        else:
            print("❌ 未找到密码")
    
    elif choice == "3":
        print("\n输入格式：用户ID,密码（每行一个，空行结束）")
        print("示例：user1,mypassword123")
        print("-" * 30)
        
        while True:
            line = input().strip()
            if not line:
                break
            if "," in line:
                user_id, password = line.split(",", 1)
                store_password(user_id.strip(), password.strip())
    
    elif choice == "4":
        return
    
    else:
        print("无效选择")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            print_status()
        elif cmd == "set" and len(sys.argv) >= 4:
            store_password(sys.argv[2], sys.argv[3])
        elif cmd == "get" and len(sys.argv) >= 3:
            pwd = retrieve_password(sys.argv[2])
            print(pwd if pwd else "未找到")
        else:
            print("用法：")
            print("  python password_manager.py          # 交互模式")
            print("  python password_manager.py status   # 查看状态")
            print("  python password_manager.py set user1 password")
            print("  python password_manager.py get user1")
    else:
        interactive_menu()
