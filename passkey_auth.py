"""
Passkey (WebAuthn) 认证模块
用于保护网站访问，只有注册过 Passkey 的用户才能查看数据
"""

import os
import json
import secrets
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

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
)

# ==================== 配置 ====================

# 你的域名配置（部署时需要修改）
RP_ID = os.getenv("PASSKEY_RP_ID", "localhost")  # 域名，如 "example.com"
RP_NAME = os.getenv("PASSKEY_RP_NAME", "血糖PK")
ORIGIN = os.getenv("PASSKEY_ORIGIN", "http://localhost:5010")  # 完整 URL

# 用户数据存储文件
USERS_FILE = ".passkey_users.json"


# ==================== 数据模型 ====================

@dataclass
class PasskeyCredential:
    """存储的 Passkey 凭据"""
    credential_id: str  # base64url 编码
    public_key: str     # base64url 编码
    sign_count: int
    created_at: str
    device_name: str = ""


@dataclass  
class PasskeyUser:
    """Passkey 用户"""
    user_id: str
    username: str
    display_name: str
    credentials: list  # List[PasskeyCredential]
    created_at: str
    

# ==================== 存储 ====================

def _load_users() -> dict:
    """加载用户数据"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_users(users: dict):
    """保存用户数据"""
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def get_user(username: str) -> Optional[dict]:
    """获取用户"""
    users = _load_users()
    return users.get(username)


def get_user_by_credential_id(credential_id: str) -> Optional[dict]:
    """通过凭据 ID 查找用户"""
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
    """获取所有用户"""
    users = _load_users()
    return [
        {"username": u["username"], "display_name": u["display_name"], "credential_count": len(u.get("credentials", []))}
        for u in users.values()
    ]


def has_any_user() -> bool:
    """检查是否有任何用户"""
    return len(_load_users()) > 0


# ==================== 注册流程 ====================

# 临时存储注册挑战（生产环境应用 Redis）
_registration_challenges = {}

def start_registration(username: str, display_name: str = None) -> dict:
    """
    开始 Passkey 注册流程
    返回要发送给浏览器的选项
    """
    if not display_name:
        display_name = username
    
    user_id = secrets.token_bytes(32)
    
    # 检查用户是否已存在
    existing_user = get_user(username)
    if existing_user:
        user_id = base64url_to_bytes(existing_user["user_id"])
        exclude_credentials = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"]))
            for c in existing_user.get("credentials", [])
        ]
    else:
        exclude_credentials = []
    
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user_id,
        user_name=username,
        user_display_name=display_name,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    
    # 保存挑战用于验证
    _registration_challenges[username] = {
        "challenge": bytes_to_base64url(options.challenge),
        "user_id": bytes_to_base64url(user_id),
        "display_name": display_name,
    }
    
    return json.loads(options_to_json(options))


def complete_registration(username: str, credential_json: dict, device_name: str = "") -> bool:
    """
    完成 Passkey 注册
    验证浏览器返回的凭据
    """
    if username not in _registration_challenges:
        raise ValueError("未找到注册会话，请重新开始")
    
    challenge_data = _registration_challenges.pop(username)
    
    try:
        verification = verify_registration_response(
            credential=credential_json,
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
        )
    except Exception as e:
        raise ValueError(f"验证失败: {e}")
    
    # 创建或更新用户
    existing_user = get_user(username)
    
    new_credential = {
        "credential_id": bytes_to_base64url(verification.credential_id),
        "public_key": bytes_to_base64url(verification.credential_public_key),
        "sign_count": verification.sign_count,
        "created_at": datetime.now().isoformat(),
        "device_name": device_name or "未命名设备",
    }
    
    if existing_user:
        existing_user["credentials"].append(new_credential)
        save_user(existing_user)
    else:
        new_user = {
            "user_id": challenge_data["user_id"],
            "username": username,
            "display_name": challenge_data["display_name"],
            "credentials": [new_credential],
            "created_at": datetime.now().isoformat(),
        }
        save_user(new_user)
    
    return True


# ==================== 登录流程 ====================

_authentication_challenges = {}

def start_authentication(username: str = None) -> dict:
    """
    开始 Passkey 登录流程
    username 为空则允许任何已注册用户登录
    """
    allow_credentials = []
    
    if username:
        user = get_user(username)
        if not user:
            raise ValueError("用户不存在")
        allow_credentials = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"]))
            for c in user.get("credentials", [])
        ]
    
    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow_credentials if allow_credentials else None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    
    challenge_key = username or "_anonymous_"
    _authentication_challenges[challenge_key] = {
        "challenge": bytes_to_base64url(options.challenge),
        "username": username,
    }
    
    return json.loads(options_to_json(options))


def complete_authentication(credential_json: dict, username: str = None) -> dict:
    """
    完成 Passkey 登录
    返回用户信息
    """
    challenge_key = username or "_anonymous_"
    
    if challenge_key not in _authentication_challenges:
        raise ValueError("未找到登录会话，请重新开始")
    
    challenge_data = _authentication_challenges.pop(challenge_key)
    
    # 查找凭据对应的用户
    credential_id = credential_json.get("id", "")
    user = get_user(username) if username else get_user_by_credential_id(credential_id)
    
    if not user:
        raise ValueError("未找到用户")
    
    # 找到对应的凭据
    credential = None
    for c in user.get("credentials", []):
        if c["credential_id"] == credential_id:
            credential = c
            break
    
    if not credential:
        raise ValueError("凭据不存在")
    
    try:
        verification = verify_authentication_response(
            credential=credential_json,
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=base64url_to_bytes(credential["public_key"]),
            credential_current_sign_count=credential["sign_count"],
        )
    except Exception as e:
        raise ValueError(f"验证失败: {e}")
    
    # 更新 sign_count
    credential["sign_count"] = verification.new_sign_count
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
    
    user["credentials"] = [c for c in user["credentials"] if c["credential_id"] != credential_id]
    save_user(user)
    return True


def delete_user(username: str) -> bool:
    """删除用户"""
    users = _load_users()
    if username in users:
        del users[username]
        _save_users(users)
        return True
    return False
