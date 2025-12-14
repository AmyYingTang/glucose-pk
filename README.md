# 血糖 PK - 认证系统改进版

## 📋 改进概览

这个改进版本解决了以下问题：
1. ✅ **修复了安卓注销后无法登录的问题**
2. ✅ **添加了重新注册 Passkey 功能**
3. ✅ **添加了传统用户名/密码认证**
4. ✅ **提供了完整的账户管理界面**

---

## 🔍 问题分析与解决

### 问题 1: 注销后找不到 Passkey

**原因：**
- 安卓上的 Passkey 实现可能使用了 `residentKey: "required"`
- 某些浏览器（特别是 Chrome）对此支持不稳定
- `allowCredentials` 列表可能没有正确传递

**解决方案：**
```python
# passkey_auth_improved.py 中的关键改进

# 1. 使用更兼容的配置
authenticator_selection=AuthenticatorSelectionCriteria(
    authenticator_attachment="platform",
    resident_key=ResidentKeyRequirement.PREFERRED,  # 从 REQUIRED 改为 PREFERRED
    user_verification=UserVerificationRequirement.PREFERRED,
)

# 2. 支持多种加密算法
supported_pub_key_algs=[-7, -257],  # ES256, RS256

# 3. 在登录时提供完整的 allowCredentials
allow_credentials = [
    PublicKeyCredentialDescriptor(
        id=base64url_to_bytes(c["credential_id"]),
        transports=["internal", "hybrid"]  # 增加传输方式
    )
    for c in user["credentials"]
]
```

### 问题 2: 用户数据管理混乱

**改进：**
- 注销只清除 session，不删除用户数据
- 用户数据持久化到 `.passkey_users.json`
- credentials 和用户信息分开管理

```python
@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """登出（只清除 session，不删除用户数据）"""
    session.clear()  # ✅ 只清除 session
    return jsonify({"success": True})
    # ❌ 不会删除 users_db 中的数据
```

---

## 🆕 新功能

### 1. 双重认证支持

用户可以选择：
- **Passkey 认证**（推荐）：使用生物识别或安全密钥
- **密码认证**（备选）：传统用户名密码

### 2. 重新注册 Passkey

用户可以在账户管理页面：
- 添加新设备的 Passkey
- 删除旧的 Passkey
- 管理多个 Passkey

### 3. 灵活的密码管理

- 纯 Passkey 用户可以添加密码
- 有密码的用户可以修改密码
- 支持混合使用 Passkey 和密码

---

## 📁 文件说明

### 核心文件

1. **passkey_auth_improved.py** - 改进的认证模块
   - 支持 Passkey 和密码双重认证
   - 更好的浏览器兼容性
   - 完善的错误处理

2. **login_improved.html** - 改进的登录页面
   - 支持 Passkey 和密码登录
   - 支持 Passkey 和密码注册
   - 浏览器兼容性检测

3. **account.html** - 账户管理页面
   - 管理 Passkey 设备
   - 添加/修改密码
   - 删除凭据

4. **app_routes_improved.py** - Flask 路由示例
   - 完整的 API 端点
   - 登录验证装饰器
   - 会话管理

---

## 🚀 使用指南

### 安装依赖

```bash
pip install flask py_webauthn python-dotenv --break-system-packages
```

### 文件部署

1. 替换 `passkey_auth.py`:
```bash
cp passkey_auth_improved.py passkey_auth.py
```

2. 替换登录页面:
```bash
cp login_improved.html static/login.html
```

3. 添加账户管理页面:
```bash
cp account.html static/account.html
```

4. 更新 Flask 路由:
```bash
# 将 app_routes_improved.py 中的路由添加到你的 app.py
```

### 配置环境变量

在 `.env` 文件中配置：

```bash
# Passkey 配置
PASSKEY_RP_ID=localhost  # 部署时改为你的域名，如 "example.com"
PASSKEY_RP_NAME=血糖PK
PASSKEY_ORIGIN=http://localhost:5010  # 部署时改为 https://example.com
```

### 启动服务

```bash
python app.py
```

访问：
- 登录页面: http://localhost:5010/login
- 主页: http://localhost:5010/
- 账户管理: http://localhost:5010/account

---

## 🔐 安全建议

### 密码哈希

当前使用 SHA-256，**生产环境建议使用 bcrypt**：

```bash
pip install bcrypt --break-system-packages
```

```python
# 在 passkey_auth.py 中修改
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
```

### HTTPS 部署

Passkey **必须**在 HTTPS 环境下工作（localhost 除外）：

```nginx
# Nginx 配置示例
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:5010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Session 密钥

修改 `app.py` 中的 secret_key：

```python
import secrets

app.secret_key = secrets.token_hex(32)  # 生成随机密钥
# 或从环境变量读取
app.secret_key = os.getenv("SECRET_KEY")
```

---

## 📱 浏览器兼容性

### 完全支持
- ✅ Chrome (Windows/Mac/Android)
- ✅ Safari (macOS/iOS)
- ✅ Edge (Windows/Mac)
- ✅ Firefox (Windows/Mac)

### 部分支持
- ⚠️ iOS Chrome - Passkey 可能不稳定，建议使用密码登录
- ⚠️ 旧版浏览器 - 不支持 Passkey，只能使用密码

### 降级策略

登录页面会自动检测浏览器兼容性：
1. 不支持 Passkey → 只显示密码登录
2. iOS Chrome → 显示警告，推荐使用 Safari
3. 完全支持 → 两种方式都可用

---

## 🛠️ 命令行工具

### 列出所有用户

```bash
python passkey_auth.py list
```

输出示例：
```
共 2 个用户:

  👤 amy (Amy Chen)
     ✓ 密码 | 2 个 Passkey
  👤 bob (Bob)
     ✗ 无密码 | 1 个 Passkey
```

### 查看用户详情

```bash
python passkey_auth.py info amy
```

输出示例：
```
👤 amy
   显示名: Amy Chen
   创建时间: 2025-01-15T10:30:00
   密码: 已设置
   Passkey 数: 2
   📱 Passkey 1: iPhone 14 Pro
      ID: abc123def456...
      创建于: 2025-01-15
   📱 Passkey 2: MacBook Pro
      ID: xyz789uvw012...
      创建于: 2025-01-16
```

### 删除用户

```bash
python passkey_auth.py delete bob
```

会要求确认：
```
⚠️ 确定要删除用户 'bob' 吗？此操作不可恢复！(yes/no):
```

### 为用户添加密码

```bash
python passkey_auth.py add-password amy
```

会提示输入密码（两次确认）。

### 删除特定 Passkey

```bash
python passkey_auth.py delete-cred amy abc123def456...
```

---

## 🐛 调试指南

### 检查用户数据

查看 `.passkey_users.json`:

```bash
cat .passkey_users.json
```

应该看到类似结构：
```json
{
  "amy": {
    "user_id": "...",
    "username": "amy",
    "display_name": "Amy Chen",
    "password_hash": "...",
    "credentials": [
      {
        "credential_id": "...",
        "public_key": "...",
        "sign_count": 0,
        "created_at": "2025-01-15T10:30:00",
        "device_name": "iPhone 14 Pro"
      }
    ],
    "created_at": "2025-01-15T10:30:00"
  }
}
```

### 常见错误

#### 1. "未找到注册会话"

**原因：** session 丢失或过期

**解决：** 刷新页面重新开始注册

#### 2. "找不到对应的 Passkey"

**原因：**
- 用户数据被删除
- credential_id 不匹配

**解决：**
```bash
# 检查用户数据
python passkey_auth.py info <用户名>

# 如果数据丢失，删除用户重新注册
python passkey_auth.py delete <用户名>
```

#### 3. iOS Chrome "NotAllowedError"

**原因：** iOS Chrome 对 Passkey 支持不完善

**解决：** 使用 Safari 或密码登录

---

## 📊 API 端点

### 认证相关

```
POST /api/auth/register/start        - 开始 Passkey 注册
POST /api/auth/register/complete     - 完成 Passkey 注册
POST /api/auth/register/password     - 密码注册

POST /api/auth/login/start           - 开始 Passkey 登录
POST /api/auth/login/complete        - 完成 Passkey 登录
POST /api/auth/login/password        - 密码登录

POST /api/auth/logout                - 登出
GET  /api/auth/status                - 检查登录状态
```

### 账户管理

```
GET  /api/auth/user-info             - 获取用户信息
POST /api/auth/add-passkey/start     - 开始添加新 Passkey
POST /api/auth/add-passkey/complete  - 完成添加新 Passkey
POST /api/auth/add-password          - 添加密码
POST /api/auth/change-password       - 修改密码
POST /api/auth/delete-credential     - 删除 Passkey
```

---

## 🎯 使用场景

### 场景 1: 新用户注册

1. 访问 `/login`
2. 点击"注册"标签
3. 选择 Passkey 或密码注册
4. 完成后自动登录

### 场景 2: 现有用户添加新设备

1. 在设备 A 上登录
2. 访问 `/account`
3. 点击"添加新 Passkey"
4. 在设备 B 上扫码或直接创建

### 场景 3: 忘记 Passkey

1. 如果设置了密码：使用密码登录
2. 如果没有密码：联系管理员删除用户，重新注册

### 场景 4: 浏览器不支持 Passkey

1. 使用密码登录
2. 或更换支持的浏览器

---

## 📝 迁移步骤

### 从旧版本迁移

如果你已经有旧的 Passkey 用户数据：

1. 备份现有数据：
```bash
cp .passkey_users.json .passkey_users.json.backup
```

2. 替换文件：
```bash
cp passkey_auth_improved.py passkey_auth.py
```

3. 测试兼容性：
```bash
python passkey_auth.py list
```

4. 如果数据格式不兼容，可能需要：
```bash
# 删除旧数据重新开始
rm .passkey_users.json
```

---

## 🔄 后续优化建议

1. **使用 Redis 存储挑战**
   - 当前挑战存储在内存中
   - 多进程/多服务器环境需要 Redis

2. **添加速率限制**
   - 防止暴力破解
   - 使用 Flask-Limiter

3. **邮件验证**
   - 注册时发送验证邮件
   - 密码重置功能

4. **审计日志**
   - 记录登录/注销时间
   - 记录 IP 地址

5. **双因素认证**
   - TOTP (Google Authenticator)
   - SMS 验证码

---

## ❓ 常见问题

### Q: 可以只使用密码吗？

**A:** 可以！用户可以选择只用密码注册，完全不使用 Passkey。

### Q: 可以同时使用 Passkey 和密码吗？

**A:** 可以！用户可以两种方式都设置，登录时任选其一。

### Q: 如何重置密码？

**A:** 当前版本需要在账户管理页面修改。如果忘记密码且没有 Passkey，需要联系管理员删除账户重新注册。

### Q: Passkey 数据存在哪里？

**A:** 
- 私钥：存储在用户设备上（系统钥匙串）
- 公钥：存储在服务器的 `.passkey_users.json`

### Q: 可以在多个设备上使用同一个账户吗？

**A:** 可以！每个设备添加自己的 Passkey，或者在所有设备上使用密码登录。

---

## 📞 技术支持

如果遇到问题：

1. 查看浏览器控制台错误
2. 查看服务器日志
3. 使用命令行工具检查用户数据
4. 参考本文档的调试指南

---

**版本：** 2.0
**更新日期：** 2025-12-14
**作者：** Claude (Anthropic)
