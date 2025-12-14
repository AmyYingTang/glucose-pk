"""
Passkey (WebAuthn) 认证模块 - 改进版
支持：
1. Passkey 认证（WebAuthn）
2. 传统用户名/密码认证（备选方案）
3. 多设备支持
4. 重新注册 Passkey
"""

import os
import json
import secrets
import hashlib
from datetime import datetime
from typing import Optional

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    AuthenticationCredential,
    AuthenticatorAttachment,
    AttestationConveyancePreference,
)

# ==================== 配置 ====================

# 你的域名配置（部署时需要修改）
RP_ID = os.getenv("PASSKEY_RP_ID", "localhost")  # 域名，如 "example.com"
RP_NAME = os.getenv("PASSKEY_RP_NAME", "血糖PK")
ORIGIN = os.getenv("PASSKEY_ORIGIN", "http://localhost:5010")  # 完整 URL

# 用户数据存储文件
USERS_FILE = ".passkey_users.json"


# ==================== 密码哈希 ====================

def hash_password(password: str) -> str:
    """使用 SHA-256 哈希密码（生产环境建议用 bcrypt）"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == password_hash


# ==================== 存储 ====================

def _load_users() -> dict:
    """加载用户数据"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载用户数据失败: {e}")
            return {}
    return {}


def _save_users(users: dict):
    """保存用户数据"""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ 保存用户数据失败: {e}")


def get_user(username: str) -> Optional[dict]:
    """获取用户"""
    users = _load_users()
    return users.get(username)


def get_user_by_credential_id(credential_id: str) -> Optional[dict]:
    """通过凭据 ID 查找用户（用于无用户名登录）"""
    users = _load_users()
    for username, user in users.items():
        for cred in user.get("credentials", []):
            if cred["credential_id"] == credential_id:
                return user
    return None


def save_user(user: dict):
    """保存用户"""
    users = _load_users()
    users[user["username"]] = user
    _save_users(users)


def get_all_users() -> list:
    """获取所有用户（不含敏感信息）"""
    users = _load_users()
    return [
        {
            "username": u["username"],
            "display_name": u["display_name"],
            "credential_count": len(u.get("credentials", [])),
            "has_password": "password_hash" in u,
            "created_at": u.get("created_at", "")
        }
        for u in users.values()
    ]


def has_any_user() -> bool:
    """检查是否有任何用户"""
    return len(_load_users()) > 0


# ==================== 传统密码认证 ====================

def register_with_password(username: str, password: str, display_name: str = None) -> bool:
    """
    使用用户名/密码注册
    """
    if not username or not password:
        raise ValueError("用户名和密码不能为空")
    
    if len(password) < 6:
        raise ValueError("密码至少 6 个字符")
    
    # 检查用户是否已存在
    existing_user = get_user(username)
    if existing_user:
        raise ValueError(f"用户名 '{username}' 已被使用")
    
    user = {
        "user_id": bytes_to_base64url(secrets.token_bytes(32)),
        "username": username,
        "display_name": display_name or username,
        "password_hash": hash_password(password),
        "credentials": [],
        "created_at": datetime.now().isoformat(),
    }
    
    save_user(user)
    return True


def login_with_password(username: str, password: str) -> dict:
    """
    使用用户名/密码登录
    返回用户信息
    """
    user = get_user(username)
    if not user:
        raise ValueError("用户名或密码错误")
    
    if "password_hash" not in user:
        raise ValueError("该用户未设置密码，请使用 Passkey 登录")
    
    if not verify_password(password, user["password_hash"]):
        raise ValueError("用户名或密码错误")
    
    return {
        "username": user["username"],
        "display_name": user["display_name"],
    }


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """修改密码"""
    user = get_user(username)
    if not user:
        raise ValueError("用户不存在")
    
    if "password_hash" in user:
        if not verify_password(old_password, user["password_hash"]):
            raise ValueError("原密码错误")
    
    if len(new_password) < 6:
        raise ValueError("新密码至少 6 个字符")
    
    user["password_hash"] = hash_password(new_password)
    save_user(user)
    return True


# ==================== Passkey 注册流程 ====================

# 临时存储注册挑战（生产环境应用 Redis）
_registration_challenges = {}


def start_registration(username: str, display_name: str = None) -> dict:
    """
    开始 Passkey 注册流程
    可以为新用户注册，也可以为现有用户添加新设备
    """
    if not display_name:
        display_name = username
    
    # 检查用户是否已存在
    existing_user = get_user(username)
    if existing_user:
        # 现有用户，添加新设备
        user_id = base64url_to_bytes(existing_user["user_id"])
        exclude_credentials = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"]))
            for c in existing_user.get("credentials", [])
        ]
    else:
        # 新用户
        user_id = secrets.token_bytes(32)
        exclude_credentials = []
    
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user_id,
        user_name=username,
        user_display_name=display_name,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,  # 使用枚举
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        # 支持多种算法
        supported_pub_key_algs=[-7, -257],  # ES256, RS256
        timeout=60000,
        attestation=AttestationConveyancePreference.NONE,  # 使用枚举
    )
    
    # 保存挑战用于验证
    _registration_challenges[username] = {
        "challenge": bytes_to_base64url(options.challenge),
        "user_id": bytes_to_base64url(user_id),
        "display_name": display_name,
        "is_new_user": existing_user is None,
    }
    
    # 转换为字典，兼容不同版本的 options_to_json
    result = options_to_json(options)
    if isinstance(result, str):
        return json.loads(result)
    else:
        return result  # 已经是字典


def complete_registration(username: str, credential_json: dict, device_name: str = "") -> dict:
    """
    完成 Passkey 注册
    验证浏览器返回的凭据
    """
    if username not in _registration_challenges:
        raise ValueError("未找到注册会话，请重新开始注册")
    
    challenge_data = _registration_challenges.pop(username)
    
    try:
        # 将字典转换为 RegistrationCredential 对象
        # 兼容不同版本的 webauthn
        try:
            # 尝试 Pydantic v2 方法
            credential = RegistrationCredential.model_validate_json(json.dumps(credential_json))
        except AttributeError:
            try:
                # 尝试 Pydantic v1 方法
                credential = RegistrationCredential.parse_raw(json.dumps(credential_json))
            except AttributeError:
                # 如果都不行，尝试直接使用字典
                credential = credential_json
        
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
        )
    except Exception as e:
        raise ValueError(f"Passkey 验证失败: {e}")
    
    # 从验证结果中提取信息，兼容不同的属性名
    try:
        credential_id = getattr(verification, 'credential_id', None) or \
                        getattr(verification, 'credentialId', None)
        
        public_key = getattr(verification, 'credential_public_key', None) or \
                     getattr(verification, 'credentialPublicKey', None)
        
        sign_count = getattr(verification, 'sign_count', 0) or \
                     getattr(verification, 'signCount', 0)
        
        if not credential_id or not public_key:
            raise ValueError("无法从验证结果中提取凭据信息")
    except Exception as e:
        raise ValueError(f"提取验证信息失败: {e}")
    
    # 创建凭据记录
    credential = {
        "credential_id": bytes_to_base64url(credential_id),
        "public_key": bytes_to_base64url(public_key),
        "sign_count": sign_count,
        "created_at": datetime.now().isoformat(),
        "device_name": device_name or "未命名设备",
    }
    
    # 保存用户
    if challenge_data["is_new_user"]:
        # 新用户
        user = {
            "user_id": challenge_data["user_id"],
            "username": username,
            "display_name": challenge_data["display_name"],
            "credentials": [credential],
            "created_at": datetime.now().isoformat(),
        }
    else:
        # 现有用户，添加新凭据
        user = get_user(username)
        user["credentials"].append(credential)
    
    save_user(user)
    
    return {
        "username": user["username"],
        "display_name": user["display_name"],
        "is_new_user": challenge_data["is_new_user"],
    }


# ==================== Passkey 登录流程 ====================

# 临时存储认证挑战
_authentication_challenges = {}


def start_authentication(username: str = None) -> dict:
    """
    开始 Passkey 登录流程
    username: 可选，如果提供则只允许该用户登录
    """
    challenge = secrets.token_bytes(32)
    
    # 准备 allowCredentials
    if username:
        user = get_user(username)
        if not user:
            raise ValueError(f"用户 '{username}' 不存在")
        
        if not user.get("credentials"):
            raise ValueError(f"用户 '{username}' 没有注册 Passkey，请先注册或使用密码登录")
        
        allow_credentials = [
            PublicKeyCredentialDescriptor(
                id=base64url_to_bytes(c["credential_id"]),
                transports=["internal", "hybrid"]  # 增加传输方式选项
            )
            for c in user["credentials"]
        ]
    else:
        # 无用户名登录（发现式登录）
        allow_credentials = []
    
    options = generate_authentication_options(
        rp_id=RP_ID,
        challenge=challenge,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
        timeout=60000,
    )
    
    # 保存挑战
    session_id = secrets.token_urlsafe(16)
    _authentication_challenges[session_id] = {
        "challenge": bytes_to_base64url(challenge),
        "username": username,  # 可能为 None
    }
    
    # 转换为字典，兼容不同版本的 options_to_json
    result = options_to_json(options)
    if isinstance(result, str):
        response = json.loads(result)
    else:
        response = result  # 已经是字典
    
    response["session_id"] = session_id  # 返回 session ID
    
    return response


def complete_authentication(credential_json: dict, session_id: str, username: str = None) -> dict:
    """
    完成 Passkey 登录
    验证浏览器返回的凭据
    """
    if session_id not in _authentication_challenges:
        raise ValueError("未找到登录会话，请重新开始登录")
    
    challenge_data = _authentication_challenges.pop(session_id)
    
    # 获取 credential ID
    credential_id = credential_json.get("id") or credential_json.get("rawId")
    if not credential_id:
        raise ValueError("缺少 credential ID")
    
    # 查找用户
    if username:
        # 指定用户名登录
        user = get_user(username)
        if not user:
            raise ValueError(f"用户 '{username}' 不存在")
    else:
        # 无用户名登录，通过 credential ID 查找
        user = get_user_by_credential_id(credential_id)
        if not user:
            raise ValueError("找不到对应的 Passkey，可能已被删除")
    
    # 找到对应的凭据
    credential = None
    for c in user.get("credentials", []):
        if c["credential_id"] == credential_id:
            credential = c
            break
    
    if not credential:
        raise ValueError("凭据不存在或已被删除")
    
    try:
        # 将字典转换为 AuthenticationCredential 对象
        # 兼容不同版本的 webauthn
        try:
            # 尝试 Pydantic v2 方法
            auth_credential = AuthenticationCredential.model_validate_json(json.dumps(credential_json))
        except AttributeError:
            try:
                # 尝试 Pydantic v1 方法
                auth_credential = AuthenticationCredential.parse_raw(json.dumps(credential_json))
            except AttributeError:
                # 如果都不行，尝试直接使用字典
                auth_credential = credential_json
        
        verification = verify_authentication_response(
            credential=auth_credential,
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=base64url_to_bytes(credential["public_key"]),
            credential_current_sign_count=credential["sign_count"],
        )
    except Exception as e:
        raise ValueError(f"Passkey 验证失败: {e}")
    
    # 更新 sign_count（防止重放攻击），兼容不同的属性名
    try:
        new_sign_count = getattr(verification, 'new_sign_count', None) or \
                         getattr(verification, 'newSignCount', None) or \
                         credential["sign_count"]
        
        credential["sign_count"] = new_sign_count
    except Exception:
        # 如果无法更新 sign_count，至少不要失败
        pass
    
    save_user(user)
    
    return {
        "username": user["username"],
        "display_name": user["display_name"],
    }


# ==================== 管理功能 ====================

def delete_credential(username: str, credential_id: str) -> bool:
    """删除指定凭据"""
    user = get_user(username)
    if not user:
        return False
    
    original_count = len(user.get("credentials", []))
    user["credentials"] = [
        c for c in user.get("credentials", [])
        if c["credential_id"] != credential_id
    ]
    
    if len(user["credentials"]) < original_count:
        save_user(user)
        return True
    return False


def delete_user(username: str) -> bool:
    """删除用户（慎用！）"""
    users = _load_users()
    if username in users:
        del users[username]
        _save_users(users)
        return True
    return False


def add_password_to_existing_user(username: str, password: str) -> bool:
    """为已有用户（只有 Passkey）添加密码"""
    user = get_user(username)
    if not user:
        raise ValueError("用户不存在")
    
    if "password_hash" in user:
        raise ValueError("该用户已有密码，请使用修改密码功能")
    
    if len(password) < 6:
        raise ValueError("密码至少 6 个字符")
    
    user["password_hash"] = hash_password(password)
    save_user(user)
    return True


# ==================== 命令行工具 ====================

def cli():
    """命令行管理工具"""
    import sys
    
    if len(sys.argv) < 2:
        print("""
血糖PK - Passkey 用户管理工具

用法:
  python passkey_auth.py list                     列出所有用户
  python passkey_auth.py info <用户名>             查看用户详情
  python passkey_auth.py delete <用户名>           删除用户（危险！）
  python passkey_auth.py delete-cred <用户名> <credential_id>  删除指定凭据
  python passkey_auth.py add-password <用户名>     为用户添加密码
        """)
        return
    
    command = sys.argv[1]
    
    if command == "list":
        users = get_all_users()
        if not users:
            print("暂无用户")
        else:
            print(f"\n共 {len(users)} 个用户:\n")
            for u in users:
                pwd_status = "✓ 密码" if u["has_password"] else "✗ 无密码"
                print(f"  👤 {u['username']} ({u['display_name']})")
                print(f"     {pwd_status} | {u['credential_count']} 个 Passkey")
    
    elif command == "info":
        if len(sys.argv) < 3:
            print("请指定用户名: python passkey_auth.py info <用户名>")
            return
        username = sys.argv[2]
        user = get_user(username)
        if user:
            print(f"\n👤 {user['username']}")
            print(f"   显示名: {user['display_name']}")
            print(f"   创建时间: {user['created_at']}")
            print(f"   密码: {'已设置' if 'password_hash' in user else '未设置'}")
            print(f"   Passkey 数: {len(user.get('credentials', []))}")
            for i, cred in enumerate(user.get('credentials', []), 1):
                print(f"   📱 Passkey {i}: {cred.get('device_name', '未命名')}")
                print(f"      ID: {cred['credential_id'][:20]}...")
                print(f"      创建于: {cred['created_at'][:10]}")
        else:
            print(f"❌ 用户不存在: {username}")
    
    elif command == "delete":
        if len(sys.argv) < 3:
            print("请指定用户名: python passkey_auth.py delete <用户名>")
            return
        username = sys.argv[2]
        confirm = input(f"⚠️ 确定要删除用户 '{username}' 吗？此操作不可恢复！(yes/no): ")
        if confirm.lower() == "yes":
            if delete_user(username):
                print(f"✅ 已删除用户: {username}")
            else:
                print(f"❌ 用户不存在: {username}")
        else:
            print("已取消")
    
    elif command == "delete-cred":
        if len(sys.argv) < 4:
            print("用法: python passkey_auth.py delete-cred <用户名> <credential_id>")
            return
        username = sys.argv[2]
        cred_id = sys.argv[3]
        if delete_credential(username, cred_id):
            print(f"✅ 已删除凭据")
        else:
            print(f"❌ 凭据不存在")
    
    elif command == "add-password":
        if len(sys.argv) < 3:
            print("请指定用户名: python passkey_auth.py add-password <用户名>")
            return
        username = sys.argv[2]
        import getpass
        password = getpass.getpass("请输入密码: ")
        password2 = getpass.getpass("再次输入密码: ")
        if password != password2:
            print("❌ 两次密码不一致")
            return
        try:
            add_password_to_existing_user(username, password)
            print(f"✅ 已为用户 {username} 设置密码")
        except Exception as e:
            print(f"❌ {e}")
    
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    cli()
