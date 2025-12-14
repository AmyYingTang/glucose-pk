#!/usr/bin/env python3
"""
最小化测试 - 逐步测试每个函数
"""

import sys
import os

print("="*60)
print("最小化测试 - 逐步检查")
print("="*60)

# 步骤 1: 检查文件
print("\n步骤 1: 检查文件")
print("-"*60)
files_to_check = ['passkey_auth.py', '.passkey_users.json']
for f in files_to_check:
    if os.path.exists(f):
        print(f"✅ {f} 存在")
    else:
        print(f"❌ {f} 不存在")

# 步骤 2: 导入基础库
print("\n步骤 2: 导入基础库")
print("-"*60)
try:
    import json
    print("✅ json")
except Exception as e:
    print(f"❌ json: {e}")
    sys.exit(1)

try:
    import secrets
    print("✅ secrets")
except Exception as e:
    print(f"❌ secrets: {e}")
    sys.exit(1)

try:
    import hashlib
    print("✅ hashlib")
except Exception as e:
    print(f"❌ hashlib: {e}")
    sys.exit(1)

# 步骤 3: 导入 webauthn
print("\n步骤 3: 导入 webauthn")
print("-"*60)
try:
    from webauthn import (
        generate_registration_options,
        verify_registration_response,
        generate_authentication_options,
        verify_authentication_response,
        options_to_json,
    )
    print("✅ webauthn 所有函数导入成功")
except Exception as e:
    print(f"❌ webauthn 导入失败: {e}")
    print("\n可能需要安装:")
    print("  pip install webauthn --break-system-packages")
    sys.exit(1)

try:
    from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
    print("✅ webauthn.helpers")
except Exception as e:
    print(f"❌ webauthn.helpers: {e}")
    sys.exit(1)

try:
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        UserVerificationRequirement,
        ResidentKeyRequirement,
        PublicKeyCredentialDescriptor,
    )
    print("✅ webauthn.helpers.structs")
except Exception as e:
    print(f"❌ webauthn.helpers.structs: {e}")
    sys.exit(1)

# 步骤 4: 导入 passkey_auth
print("\n步骤 4: 导入 passkey_auth")
print("-"*60)
try:
    import passkey_auth
    print("✅ passkey_auth 导入成功")
except Exception as e:
    print(f"❌ passkey_auth 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤 5: 测试 _load_users
print("\n步骤 5: 测试 _load_users()")
print("-"*60)
try:
    users = passkey_auth._load_users()
    print(f"✅ _load_users() 成功")
    print(f"   类型: {type(users)}")
    print(f"   内容: {users}")
except Exception as e:
    print(f"❌ _load_users() 失败: {e}")
    import traceback
    traceback.print_exc()

# 步骤 6: 测试 has_any_user
print("\n步骤 6: 测试 has_any_user()")
print("-"*60)
try:
    result = passkey_auth.has_any_user()
    print(f"✅ has_any_user() = {result}")
except Exception as e:
    print(f"❌ has_any_user() 失败: {e}")
    import traceback
    traceback.print_exc()

# 步骤 7: 测试 get_all_users
print("\n步骤 7: 测试 get_all_users()")
print("-"*60)
try:
    all_users = passkey_auth.get_all_users()
    print(f"✅ get_all_users() 成功")
    print(f"   类型: {type(all_users)}")
    print(f"   内容: {all_users}")
except Exception as e:
    print(f"❌ get_all_users() 失败: {e}")
    print("\n这可能就是你的错误!")
    import traceback
    traceback.print_exc()

# 步骤 8: 测试 start_registration
print("\n步骤 8: 测试 start_registration('testuser', 'Test User')")
print("-"*60)
try:
    options = passkey_auth.start_registration('testuser', 'Test User')
    print(f"✅ start_registration() 成功")
    print(f"   类型: {type(options)}")
    if isinstance(options, dict):
        print(f"   键: {list(options.keys())}")
    else:
        print(f"   ⚠️ 不是字典!")
except Exception as e:
    print(f"❌ start_registration() 失败: {e}")
    print("\n这可能就是你的错误!")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("测试完成")
print("="*60)
