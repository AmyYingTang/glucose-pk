"""
诊断脚本 - 检查认证相关的错误
"""

print("=" * 60)
print("血糖 PK - 认证系统诊断")
print("=" * 60)

# 1. 检查 passkey_auth.py 是否存在
import os
if os.path.exists('passkey_auth.py'):
    print("✅ passkey_auth.py 文件存在")
else:
    print("❌ passkey_auth.py 文件不存在")
    exit(1)

# 2. 尝试导入模块
try:
    import passkey_auth
    print("✅ passkey_auth 模块导入成功")
except Exception as e:
    print(f"❌ passkey_auth 模块导入失败: {e}")
    exit(1)

# 3. 检查关键函数
functions = [
    'start_registration',
    'complete_registration',
    'start_authentication',
    'complete_authentication'
]

print("\n检查关键函数:")
for func in functions:
    if hasattr(passkey_auth, func):
        print(f"✅ {func}")
    else:
        print(f"❌ {func} - 缺失")

# 4. 检查用户数据文件
if os.path.exists('.passkey_users.json'):
    print("\n✅ 用户数据文件存在")
    import json
    try:
        with open('.passkey_users.json', 'r') as f:
            users = json.load(f)
        print(f"   用户数量: {len(users)}")
        for username in users.keys():
            print(f"   - {username}")
    except Exception as e:
        print(f"   ⚠️ 读取用户数据失败: {e}")
else:
    print("\n⚠️ 用户数据文件不存在（首次使用正常）")

# 5. 测试注册流程（模拟）
print("\n" + "=" * 60)
print("测试注册流程")
print("=" * 60)

try:
    options = passkey_auth.start_registration("test_user", "测试用户")
    print("✅ start_registration 调用成功")
    print(f"   返回类型: {type(options)}")
    print(f"   返回键: {list(options.keys()) if isinstance(options, dict) else 'N/A'}")
except Exception as e:
    print(f"❌ start_registration 调用失败:")
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
