# 血糖 PK 应用 - 部署与使用指南

## 📁 项目结构

```
glucose-pk/
├── app.py                    # Flask 主应用
├── config.py                 # 配置（阈值、游戏设置）
├── cgm_manager.py            # CGM 设备管理器 (新)
├── cgm_api.py                # 设备管理 API (新)
├── data_fetcher.py           # 数据获取模块
├── sync_service.py           # 后台同步服务
├── passkey_auth.py           # Passkey 认证模块
├── password_manager.py       # 密码管理工具
├── requirements.txt          # Python 依赖
├── requirements.lock         # 锁定版本
├── .env.example              # 配置模板
│
├── cgm_providers/            # CGM Provider 抽象层 (新)
│   ├── __init__.py           # 设备类型注册
│   ├── base.py               # 基类定义
│   ├── dexcom.py             # Dexcom Provider
│   └── libre.py              # Libre Provider
│
├── data/
│   └── cgm_devices/          # 用户设备配置 (新)
│       └── {username}.json
│
├── glucose_data/             # 血糖数据缓存
│   └── {player_id}.json
│
└── static/
    ├── login.html            # 登录页
    ├── account.html          # 账户管理（含设备管理）
    ├── pk.html               # 赛跑游戏
    ├── castle.html           # 城堡游戏
    ├── river.html            # 漂流游戏
    └── js/、css/             # 前端资源
```

---

## 🚀 部署步骤（管理员）

### 第一步：准备服务器

```bash
# 1. 克隆代码
git clone <your-repo-url> glucose-pk
cd glucose-pk

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 或使用锁定版本
pip install -r requirements.lock
```

### 第二步：配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置
nano .env
```

**.env 文件内容：**

```env
# ==================== Flask 配置 ====================
FLASK_SECRET_KEY=your-random-secret-key-here
FLASK_PORT=5010
FLASK_DEBUG=false

# ==================== Passkey 配置 ====================
# 本地开发
PASSKEY_RP_ID=localhost
PASSKEY_RP_NAME=血糖PK
PASSKEY_ORIGIN=http://localhost:5010

# 生产环境（部署时修改）
# PASSKEY_RP_ID=your-domain.com
# PASSKEY_ORIGIN=https://your-domain.com

# ==================== 认证配置 ====================
# 设为 false 可跳过登录（仅开发用）
AUTH_REQUIRED=true

# ==================== 加密密钥 ====================
# 用于加密 CGM 设备凭证（可选，不设置则自动生成）
# ENCRYPTION_KEY=your-fernet-key

# ==================== 游戏配置 ====================
# 默认首页
DEFAULT_PAGE=/river.html

# 数据刷新间隔（秒）
DATA_REFRESH_INTERVAL=30
```

### 第三步：创建数据目录

```bash
mkdir -p data/cgm_devices
mkdir -p glucose_data
```

### 第四步：配置 HTTPS（生产环境必须）

Passkey 要求 HTTPS（localhost 除外）。

**Nginx + Let's Encrypt 配置：**

```nginx
# /etc/nginx/sites-available/glucose-pk
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/glucose-pk /etc/nginx/sites-enabled/

# 获取 SSL 证书
sudo certbot --nginx -d your-domain.com

# 重启 Nginx
sudo systemctl restart nginx
```

### 第五步：启动应用

**开发模式：**
```bash
python app.py
```

**生产模式（使用 gunicorn）：**
```bash
pip install gunicorn
gunicorn -w 4 -b 127.0.0.1:5010 app:app
```

**使用 systemd 自动启动：**

```ini
# /etc/systemd/system/glucose-pk.service
[Unit]
Description=Glucose PK App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/glucose-pk
Environment="PATH=/path/to/glucose-pk/venv/bin"
ExecStart=/path/to/glucose-pk/venv/bin/gunicorn -w 4 -b 127.0.0.1:5010 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable glucose-pk
sudo systemctl start glucose-pk

# 查看状态
sudo systemctl status glucose-pk
```

---

## 👤 用户操作指南

### 首次使用

1. **访问网站**
   - 打开 `https://your-domain.com`
   - 自动跳转到登录页

2. **创建账户**
   - 输入用户名和显示名称
   - 选择 Passkey 或密码注册
   - Passkey：使用指纹/Face ID 创建
   - 密码：输入密码（至少 6 位）

3. **添加 CGM 设备**
   - 登录后进入账户管理页面（点击右上角设置）
   - 点击「添加 CGM 设备」
   - 选择设备类型（Dexcom 或 Libre）
   - 输入设备账户凭证
   - 点击「测试连接」验证
   - 保存设备

4. **开始 PK**
   - 返回首页
   - 选择游戏模式
   - 享受比赛！

### 添加 Dexcom 设备

1. 确保已启用 **Dexcom Share** 功能
2. 在账户管理页面点击「添加 CGM 设备」
3. 选择「Dexcom G6/G7」
4. 输入：
   - 用户名：Dexcom 账户邮箱或用户名
   - 密码：Dexcom 账户密码
   - 地区：美国 或 非美国（国际）
5. 测试连接 → 保存

### 添加 FreeStyle Libre 设备

1. 确保已设置 **LibreLinkUp 分享**
   - 在 LibreLinkUp 应用中添加分享
   - 接受分享邀请
2. 在账户管理页面点击「添加 CGM 设备」
3. 选择「FreeStyle Libre」
4. 输入：
   - 邮箱：LibreLinkUp 账户邮箱
   - 密码：LibreLinkUp 账户密码
5. 测试连接 → 保存

### 管理多个设备

- 每个用户可添加多个 CGM 设备
- 可以设置默认设备
- 可以启用/禁用特定设备
- 在 PK 时可选择使用哪个设备

### 观战模式（Guest）

没有 CGM 设备的用户可以：
- 注册账户
- 以 Guest 身份进入游戏
- 观看其他玩家的数据
- 不参与排名

---

## 🔧 常见问题

### Q: 本地开发时不想每次登录？

在 `.env` 中设置：
```env
AUTH_REQUIRED=false
```

### Q: 忘记了 Passkey / 设备丢失？

1. 如果设置了密码：使用密码登录
2. 如果没有密码：联系管理员删除账户

管理员操作：
```bash
python passkey_auth.py delete <username>
```

### Q: CGM 设备凭证错误怎么办？

1. 进入账户管理页面
2. 删除旧设备
3. 重新添加正确凭证

### Q: 迁移到新服务器？

需要迁移的文件：
```bash
# 必需
.env                      # 配置文件
.secret_key               # 加密密钥（重要！）
.passkey_users.json       # 用户账户数据

# 可选（可重新生成）
data/cgm_devices/         # 设备配置
glucose_data/             # 血糖缓存数据
```

迁移命令：
```bash
scp .env .secret_key .passkey_users.json user@new-server:/path/to/app/
scp -r data/cgm_devices user@new-server:/path/to/app/data/
```

⚠️ **重要**：`.secret_key` 必须迁移，否则无法解密设备凭证！

### Q: Passkey 提示"域名不匹配"？

确保 `.env` 中的配置正确：
```env
PASSKEY_RP_ID=your-domain.com          # 域名，不含协议
PASSKEY_ORIGIN=https://your-domain.com  # 完整 URL，含协议
```

### Q: 如何查看同步状态？

```bash
# 查看同步日志
tail -f /var/log/glucose-pk.log

# 或访问 API
curl https://your-domain.com/api/sync/status
```

### Q: 数据同步失败？

1. 检查设备凭证是否正确
2. 确认 Dexcom Share / LibreLinkUp 已启用
3. 检查网络连接
4. 查看服务器日志

```bash
# 手动测试设备连接
curl -X POST https://your-domain.com/api/cgm/devices/<device_id>/test \
  -H "Cookie: session=..."
```

---

## 📊 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                       用户浏览器                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 登录页    │  │ 账户管理  │  │ 游戏页面  │  │ PK 排行   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                      Nginx (HTTPS)                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       Flask App                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ passkey_auth   │  │   cgm_api      │  │ data_fetcher │  │
│  │ (认证)         │  │ (设备管理)     │  │ (数据获取)    │  │
│  └────────────────┘  └───────┬────────┘  └──────┬───────┘  │
│                              │                   │          │
│  ┌───────────────────────────┼───────────────────┤          │
│  │                 cgm_manager                   │          │
│  │              (设备配置管理)                    │          │
│  └───────────────────────────┬───────────────────┘          │
│                              │                              │
│  ┌───────────────────────────┼───────────────────┐          │
│  │              cgm_providers/                   │          │
│  │  ┌─────────────┐  ┌─────────────┐            │          │
│  │  │ DexcomProv  │  │ LibreProv   │  ...       │          │
│  │  └──────┬──────┘  └──────┬──────┘            │          │
│  └─────────┼────────────────┼────────────────────┘          │
└────────────┼────────────────┼───────────────────────────────┘
             │                │
             ▼                ▼
┌─────────────────┐  ┌─────────────────┐
│   Dexcom API    │  │ LibreLinkUp API │
│   (Share)       │  │                 │
└─────────────────┘  └─────────────────┘
```

---

## 🔒 安全清单

### 已实现
- [x] CGM 凭证 Fernet (AES-128) 加密存储
- [x] Passkey 无密码登录
- [x] HTTPS 加密传输
- [x] Session Cookie 加密
- [x] 敏感文件已加入 .gitignore

### 建议配置
- [ ] 定期备份 `.passkey_users.json` 和 `data/cgm_devices/`
- [ ] 设置防火墙只开放 80/443 端口
- [ ] 配置日志轮转
- [ ] 设置监控告警

### 生产环境建议

**使用 bcrypt 替代 SHA-256：**
```bash
pip install bcrypt
```

```python
# 修改 passkey_auth.py
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
```

---

## 📝 日志管理

### 配置日志

```python
# 在 app.py 中添加
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'glucose-pk.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s'
))
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
```

### 查看日志

```bash
# 实时查看
tail -f glucose-pk.log

# 搜索错误
grep ERROR glucose-pk.log

# 查看同步日志
grep "同步" glucose-pk.log
```

---

## 🔄 备份策略

### 自动备份脚本

```bash
#!/bin/bash
# /path/to/backup.sh

BACKUP_DIR="/path/to/backups"
APP_DIR="/path/to/glucose-pk"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份关键文件
tar -czf $BACKUP_DIR/glucose-pk-$DATE.tar.gz \
    $APP_DIR/.env \
    $APP_DIR/.secret_key \
    $APP_DIR/.passkey_users.json \
    $APP_DIR/data/cgm_devices/

# 保留最近 30 天的备份
find $BACKUP_DIR -name "glucose-pk-*.tar.gz" -mtime +30 -delete

echo "备份完成: glucose-pk-$DATE.tar.gz"
```

```bash
# 添加 cron 任务（每天凌晨 3 点）
crontab -e
# 添加：
0 3 * * * /path/to/backup.sh >> /var/log/glucose-pk-backup.log 2>&1
```

---

## 📞 技术支持

遇到问题时：
1. 查看服务器日志
2. 检查浏览器控制台
3. 使用命令行工具调试
4. 参考本文档的常见问题

### 有用的命令

```bash
# 检查服务状态
sudo systemctl status glucose-pk

# 重启服务
sudo systemctl restart glucose-pk

# 查看用户列表
python passkey_auth.py list

# 测试同步
python sync_service.py

# 查看设备配置
cat data/cgm_devices/<username>.json
```

---

**版本：** 3.0
**更新日期：** 2025-01-11
