# 血糖 PK - 多设备支持版

## 📋 功能概览

### 核心功能
- ✅ **多 CGM 设备支持** - Dexcom G6/G7、FreeStyle Libre
- ✅ **用户自助添加设备** - 无需管理员手动配置
- ✅ **Passkey 认证** - 安全的无密码登录
- ✅ **传统密码认证** - 备用登录方式
- ✅ **多人 PK 游戏** - 漂流、城堡、赛跑三种模式
- ✅ **实时数据同步** - 后台每 3 分钟自动同步

### 新增功能（v3.0）
- 🆕 **CGM Provider 抽象层** - 统一接口支持多种设备
- 🆕 **设备管理界面** - 用户可自行添加/删除/管理设备
- 🆕 **凭证加密存储** - 设备密码安全加密
- 🆕 **Guest 模式** - 无设备用户可观战

---

## 🏗️ 系统架构

### 用户身份体系

```
App 账户（Passkey/密码登录）
    │
    ├── CGM 设备 1 (Dexcom)     → player_id: amy_dexcom_abc123
    ├── CGM 设备 2 (Libre)      → player_id: amy_libre_xyz789
    └── Guest 模式              → 观战，不参与 PK
```

### 数据流

```
用户添加设备（账户管理页面）
    │
    ▼
cgm_manager.py 保存设备配置
    │ 存储到 data/cgm_devices/{username}.json
    ▼
sync_service.py 后台同步（每 3 分钟）
    │ 调用 cgm_providers/dexcom.py 或 libre.py
    ▼
glucose_data/{player_id}.json
    │
    ▼
data_fetcher.py 读取数据
    │
    ▼
前端展示 (pk.html, river.html, castle.html)
```

### 目录结构

```
glucose-pk/
├── app.py                    # Flask 主应用
├── config.py                 # 配置（阈值、游戏设置）
├── cgm_manager.py            # CGM 设备管理器
├── cgm_api.py                # 设备管理 API
├── data_fetcher.py           # 数据获取模块
├── sync_service.py           # 后台同步服务
├── passkey_auth.py           # Passkey 认证
├── password_manager.py       # 密码加密工具
│
├── cgm_providers/            # CGM Provider 抽象层
│   ├── __init__.py
│   ├── base.py               # 基类定义
│   ├── dexcom.py             # Dexcom Provider
│   └── libre.py              # Libre Provider
│
├── data/
│   └── cgm_devices/          # 用户设备配置
│       ├── amy.json
│       └── bob.json
│
├── glucose_data/             # 血糖数据缓存
│   ├── amy_dexcom_abc123.json
│   └── bob_libre_xyz789.json
│
└── static/
    ├── login.html            # 登录页
    ├── account.html          # 账户管理（含设备管理）
    ├── pk.html               # 赛跑游戏
    ├── castle.html           # 城堡游戏
    └── river.html            # 漂流游戏
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

requirements.txt 内容：
```
flask
python-dotenv
pydexcom
pylibrelinkup
py_webauthn
cryptography
```

### 2. 配置环境变量

```bash
cp .env.example .env
nano .env
```

必需的配置：
```env
# Flask
FLASK_SECRET_KEY=your-random-secret-key
FLASK_PORT=5010

# Passkey（部署时修改）
PASSKEY_RP_ID=localhost
PASSKEY_RP_NAME=血糖PK
PASSKEY_ORIGIN=http://localhost:5010

# 可选：禁用认证（开发时）
AUTH_REQUIRED=true
```

### 3. 启动服务

```bash
python app.py
```

### 4. 首次使用

1. 访问 `http://localhost:5010`
2. 创建账户（Passkey 或密码）
3. 进入账户管理页面
4. 添加你的 CGM 设备
5. 开始 PK！

---

## 📊 支持的 CGM 设备

### Dexcom G6/G7

```python
# 使用 pydexcom 库
Provider: DexcomProvider
需要：Dexcom Share 账户用户名和密码
地区选项：
  - us: 美国
  - ous: 非美国（国际）
```

### FreeStyle Libre

```python
# 使用 pylibrelinkup 库
Provider: LibreProvider
需要：LibreLinkUp 账户邮箱和密码
前提：已在 LibreLinkUp 应用中设置分享
```

### 添加新设备支持

创建 `cgm_providers/new_device.py`：

```python
from .base import BaseCGMProvider, CGMReading

class NewDeviceProvider(BaseCGMProvider):
    PROVIDER_TYPE = "new_device"
    PROVIDER_NAME = "New Device Name"
    
    def authenticate(self) -> bool:
        # 实现认证逻辑
        pass
    
    def get_current_reading(self) -> CGMReading:
        # 实现获取当前读数
        pass
    
    def get_readings(self, minutes, max_count) -> list:
        # 实现获取历史数据
        pass
```

在 `cgm_providers/__init__.py` 中注册：

```python
PROVIDER_TYPES = {
    'new_device': {
        'class': NewDeviceProvider,
        'name': 'New Device Name',
        'description': '设备说明',
        'fields': [
            {'name': 'username', 'label': '用户名', 'type': 'text', 'required': True},
            {'name': 'password', 'label': '密码', 'type': 'password', 'required': True},
        ]
    },
    # ...
}
```

---

## 🔐 认证系统

### Passkey 认证（推荐）

- 使用 WebAuthn 标准
- 支持指纹、Face ID、安全密钥
- 无需记忆密码

### 密码认证（备选）

- 传统用户名密码
- SHA-256 哈希存储（生产环境建议改用 bcrypt）

### 双重认证

用户可同时设置 Passkey 和密码，登录时任选其一。

---

## 🎮 游戏模式

### 漂流 (river.html)
- 血糖在范围内时小船平稳前进
- 血糖过高/过低时遇到障碍

### 城堡 (castle.html)
- 血糖稳定时建造城堡
- 血糖波动时城堡受损

### 赛跑 (pk.html)
- 血糖越稳定跑得越快
- 15 天滚动积分排名

---

## 📡 API 端点

### 设备管理 API

```
GET  /api/cgm/devices              - 获取用户设备列表
POST /api/cgm/devices              - 添加新设备
GET  /api/cgm/devices/<id>         - 获取单个设备
PUT  /api/cgm/devices/<id>         - 更新设备
DELETE /api/cgm/devices/<id>       - 删除设备
POST /api/cgm/devices/<id>/test    - 测试设备连接
POST /api/cgm/devices/<id>/default - 设为默认设备
POST /api/cgm/test-credentials     - 测试凭证
GET  /api/cgm/supported-devices    - 获取支持的设备类型
GET  /api/cgm/players              - 获取所有活跃玩家
```

### 血糖数据 API

```
GET /api/glucose/<player_id>           - 获取当前血糖
GET /api/glucose/<player_id>/history   - 获取历史数据
GET /api/pk/data                       - 获取所有玩家数据
GET /api/pk/players                    - 获取玩家列表
```

### 认证 API

```
POST /api/auth/register/start        - 开始 Passkey 注册
POST /api/auth/register/complete     - 完成 Passkey 注册
POST /api/auth/register/password     - 密码注册
POST /api/auth/login/start           - 开始 Passkey 登录
POST /api/auth/login/complete        - 完成 Passkey 登录
POST /api/auth/login/password        - 密码登录
POST /api/auth/logout                - 登出
GET  /api/auth/status                - 登录状态
```

---

## 🛠️ 命令行工具

### 密码管理

```bash
# 查看状态
python password_manager.py status

# 存储密码（用于旧版迁移）
python password_manager.py set user1
```

### 用户管理

```bash
# 列出所有用户
python passkey_auth.py list

# 查看用户详情
python passkey_auth.py info <username>

# 删除用户
python passkey_auth.py delete <username>
```

### 测试同步服务

```bash
python sync_service.py
```

---

## 🐛 调试指南

### 检查设备配置

```bash
cat data/cgm_devices/<username>.json
```

示例输出：
```json
{
  "devices": [
    {
      "id": "dexcom_abc12345",
      "type": "dexcom",
      "name": "我的 Dexcom G7",
      "credentials": {
        "username": "user@example.com",
        "password": "gAAAAA...(加密)",
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
  "default_device": "dexcom_abc12345"
}
```

### 检查血糖数据

```bash
cat glucose_data/<player_id>.json
```

### 常见错误

#### "设备连接失败"

1. 检查凭证是否正确
2. 确认 Dexcom Share / LibreLinkUp 已启用
3. 检查网络连接

#### "未找到关联的 Libre 设备"

需要先在 LibreLinkUp 应用中设置分享：
1. 打开 LibreLinkUp 应用
2. 添加要分享的 Libre 用户
3. 接受分享邀请

#### "Passkey 域名不匹配"

确保 `.env` 配置正确：
```env
PASSKEY_RP_ID=your-domain.com          # 不含协议
PASSKEY_ORIGIN=https://your-domain.com  # 含协议
```

---

## 📱 浏览器兼容性

### Passkey 支持

| 浏览器 | 状态 |
|--------|------|
| Chrome (桌面/Android) | ✅ 完全支持 |
| Safari (macOS/iOS) | ✅ 完全支持 |
| Edge | ✅ 完全支持 |
| Firefox | ✅ 完全支持 |
| iOS Chrome | ⚠️ 建议用 Safari |

### 降级策略

不支持 Passkey 的浏览器可使用密码登录。

---

## 🔄 从旧版本迁移

### 迁移步骤

1. **备份现有数据**
```bash
cp -r glucose_data glucose_data.backup
cp .passkey_users.json .passkey_users.json.backup
```

2. **更新文件**
```bash
# 替换核心文件
mv data_fetcher_new.py data_fetcher.py
mv sync_service_new.py sync_service.py
mv static/account_new.html static/account.html

# 添加新模块
# cgm_providers/ 目录
# cgm_manager.py
# cgm_api.py
```

3. **更新 app.py**
```python
# 添加导入
from cgm_api import cgm_bp

# 注册 Blueprint
app.register_blueprint(cgm_bp)
```

4. **创建数据目录**
```bash
mkdir -p data/cgm_devices
```

5. **迁移用户设备**

现有用户需要登录后在账户管理页面重新添加 CGM 设备。

### 数据格式变化

| 旧版 | 新版 |
|------|------|
| config.USERS 定义用户 | data/cgm_devices/{username}.json |
| user_id: "user1" | player_id: "amy_dexcom_abc123" |
| 管理员配置 | 用户自助管理 |

---

## ❓ 常见问题

### Q: 可以添加多个设备吗？

**A:** 可以！每个用户可以添加多个 CGM 设备，并设置默认设备。

### Q: 没有 CGM 设备能用吗？

**A:** 可以！没有设备的用户可以以 Guest 模式观战。

### Q: 设备凭证安全吗？

**A:** 设备密码使用 Fernet (AES-128) 加密存储，密钥保存在 `.secret_key` 文件中。

### Q: 支持哪些 CGM 设备？

**A:** 目前支持：
- Dexcom G6/G7（通过 Dexcom Share）
- FreeStyle Libre（通过 LibreLinkUp）

可以通过添加新的 Provider 扩展支持其他设备。

### Q: 数据多久同步一次？

**A:** 后台每 3 分钟同步一次（可在 sync_service.py 中调整 SYNC_INTERVAL）。

---

## 📞 技术支持

遇到问题时：
1. 查看浏览器控制台错误
2. 查看服务器日志
3. 使用命令行工具检查数据
4. 参考本文档的调试指南

---

**版本：** 3.0
**更新日期：** 2025-01-11
