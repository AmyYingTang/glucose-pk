# Dexcom 血糖可视化

实时获取 Dexcom CGM 血糖数据，并通过动画可视化展示。

## 项目结构

```
dexcom-project/
├── app.py              # Flask 后端
├── requirements.txt    # Python 依赖
├── .env               # 账号配置（需自己创建）
├── .env.example       # 配置示例
├── .gitignore
└── static/
    ├── index.html     # 前端页面
    ├── normal.mp4     # 正常状态视频（需自己添加）
    ├── warning.mp4    # 偏高状态视频（需自己添加）
    └── danger.mp4     # 危险状态视频（需自己添加）
```

## 快速开始

### 1. 创建虚拟环境

```bash
cd dexcom-project
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置账号

复制示例配置并填入你的 Dexcom 账号：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
DEXCOM_USERNAME=你的用户名
DEXCOM_PASSWORD=你的密码
DEXCOM_REGION=us
```

### 4. 添加视频文件

将 3 个视频文件放入 `static/` 目录：
- `normal.mp4` - 血糖正常时播放
- `warning.mp4` - 血糖偏高时播放  
- `danger.mp4` - 血糖危险时播放

### 5. 启动服务

```bash
python app.py
```

打开浏览器访问：http://localhost:5000

## API 接口

| 接口 | 说明 |
|------|------|
| `GET /` | 主页 |
| `GET /api/glucose` | 获取当前血糖数据 |
| `GET /api/glucose/history` | 获取最近3小时历史数据 |

### 返回示例

```json
{
  "success": true,
  "data": {
    "value": 120,
    "mmol_l": 6.7,
    "trend": 4,
    "trend_direction": "Flat",
    "trend_description": "steady",
    "trend_arrow": "→",
    "datetime": "2024-01-15T10:30:00"
  }
}
```

## 血糖阈值

| 范围 | 状态 | 颜色 |
|------|------|------|
| < 140 mg/dL | 正常 | 蓝色 |
| 140-200 mg/dL | 偏高 | 黄色 |
| > 200 mg/dL | 危险 | 红色 |

## 注意事项

- 需要在 Dexcom 手机 App 中启用 Share 功能
- Share 功能需要至少设置一个 follower 才能启用
- 使用你自己的 Dexcom 账号，不是 follower 的账号
- 血糖数据每 5 分钟更新一次，前端每 30 秒刷新
