"""
密码加密/解密工具
使用 Fernet 对称加密（基于 AES-128-CBC）
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def get_or_create_key(key_file: str = ".secret_key") -> bytes:
    """
    获取或创建加密密钥
    密钥存储在 .secret_key 文件中（请加入 .gitignore）
    """
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
        print(f"✅ 已生成新密钥并保存到 {key_file}")
        print(f"⚠️  请将 {key_file} 加入 .gitignore！")
        return key


def encrypt_password(password: str, key: bytes = None) -> str:
    """
    加密密码
    返回 base64 编码的加密字符串
    """
    if key is None:
        key = get_or_create_key()
    
    f = Fernet(key)
    encrypted = f.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password: str, key: bytes = None) -> str:
    """
    解密密码
    """
    if key is None:
        key = get_or_create_key()
    
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_password.encode())
    return decrypted.decode()


# ==================== 命令行工具 ====================
if __name__ == "__main__":
    import sys
    
    print("=" * 50)
    print("🔐 密码加密工具")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # 命令行模式
        if sys.argv[1] == "encrypt" and len(sys.argv) > 2:
            password = sys.argv[2]
            encrypted = encrypt_password(password)
            print(f"\n原密码: {password}")
            print(f"加密后: {encrypted}")
            print(f"\n将此加密字符串放入 .env 文件中")
        
        elif sys.argv[1] == "decrypt" and len(sys.argv) > 2:
            encrypted = sys.argv[2]
            try:
                decrypted = decrypt_password(encrypted)
                print(f"\n加密串: {encrypted}")
                print(f"解密后: {decrypted}")
            except Exception as e:
                print(f"❌ 解密失败: {e}")
        
        else:
            print("用法:")
            print("  python crypto_utils.py encrypt <密码>")
            print("  python crypto_utils.py decrypt <加密串>")
    
    else:
        # 交互模式
        print("\n选择操作:")
        print("1. 加密密码")
        print("2. 解密密码")
        print("3. 批量加密多个用户")
        
        choice = input("\n请选择 (1/2/3): ").strip()
        
        if choice == "1":
            password = input("请输入要加密的密码: ")
            encrypted = encrypt_password(password)
            print(f"\n✅ 加密成功!")
            print(f"加密后: {encrypted}")
            print(f"\n请将此字符串放入 .env 文件")
        
        elif choice == "2":
            encrypted = input("请输入加密字符串: ")
            try:
                decrypted = decrypt_password(encrypted)
                print(f"\n✅ 解密成功!")
                print(f"原密码: {decrypted}")
            except Exception as e:
                print(f"\n❌ 解密失败: {e}")
        
        elif choice == "3":
            print("\n批量加密用户密码")
            print("输入格式: 用户ID,密码 (每行一个，输入空行结束)")
            print("-" * 30)
            
            users = []
            while True:
                line = input()
                if not line.strip():
                    break
                parts = line.split(",", 1)
                if len(parts) == 2:
                    user_id, password = parts[0].strip(), parts[1].strip()
                    encrypted = encrypt_password(password)
                    users.append((user_id, encrypted))
            
            if users:
                print("\n" + "=" * 50)
                print("将以下内容复制到 .env 文件:")
                print("=" * 50 + "\n")
                for user_id, encrypted in users:
                    print(f"{user_id.upper()}_PASSWORD_ENCRYPTED={encrypted}")
        
        else:
            print("无效选择")
