# 弹幕评论系统集成指南

## 📁 新增文件

```
glucose-pk/
├── comments.py          # 评论存储模块
├── comments_api.py      # 评论 API 路由
├── .comments.json       # 评论数据文件（自动生成）
└── static/
    └── js/
        └── danmaku.js   # 弹幕前端组件
```

## 🚀 快速集成

只需在你的 HTML 页面底部（`</body>` 之前）添加一行：

```html
<!-- 在 river.html 或 castle.html 的 </body> 前添加 -->
<script src="/js/danmaku.js"></script>
```

就这么简单！弹幕系统会自动：
- 创建浮动评论按钮（右下角）
- 创建可折叠评论面板
- 创建弹幕滚动区域（屏幕顶部）
- 开始轮询新评论

## 🎨 效果预览

```
┌──────────────────────────────────────────────────────┐
│  [弹幕滚动区域 - 屏幕顶部 120px 高]                    │
│  ← 小明: 加油！血糖稳住！                              │
│       ← Amy: 今天状态不错~                            │
├──────────────────────────────────────────────────────┤
│                                                      │
│                                                      │
│              [ 你的主页面内容 ]                        │
│              [ river / castle ]                      │
│                                                      │
│                                                      │
│                                          ┌─────┐    │
│                                          │ 💬  │    │  ← 浮动按钮
│                                          └─────┘    │
│                                    ┌─────────────┐  │
│                                    │ 💬 弹幕评论  │  │
│                                    ├─────────────┤  │
│                                    │ 小明: 加油！ │  │  ← 评论面板
│                                    │ Amy: 不错~  │  │    (点击按钮展开)
│                                    ├─────────────┤  │
│                                    │ [昵称][评论]│  │
│                                    │ [发送弹幕🚀] │  │
│                                    └─────────────┘  │
└──────────────────────────────────────────────────────┘
```

## 🔧 自定义配置

如果你想自定义弹幕行为，可以在引入脚本前修改配置：

```html
<script>
// 可选：自定义配置
window.DanmakuConfig = {
    pollInterval: 5000,      // 轮询间隔（毫秒）
    danmakuDuration: 8000,   // 弹幕滚动时长
    danmakuSpacing: 2000,    // 弹幕间隔
    maxDanmakuLines: 3,      // 弹幕轨道数
};
</script>
<script src="/js/danmaku.js"></script>
```

## 📡 API 接口

### 获取评论
```
GET /api/comments
GET /api/comments?since_id=123456  # 增量获取
GET /api/comments?count=10         # 指定数量
```

### 发送评论
```
POST /api/comments
Content-Type: application/json

{
    "username": "小明",
    "content": "加油！"
}
```

## 🎯 功能特点

1. **自动轮询** - 每 5 秒检查新评论
2. **弹幕显示** - 新评论自动变成弹幕从右向左滚动
3. **评论面板** - 可折叠，显示最近 20 条
4. **用户名记忆** - 使用 localStorage 记住昵称
5. **跨用户共享** - 评论存储在服务端 JSON 文件
6. **响应式设计** - 适配手机屏幕

## 🔒 与 Passkey 集成

评论 API 默认不需要 Passkey 登录（因为用户名是自己输入的）。

如果你想要求登录才能评论，可以在 `comments_api.py` 中添加装饰器：

```python
from app import login_required

@comments_bp.route('', methods=['POST'])
@login_required  # 添加这行
def api_add_comment():
    ...
```

## 🧪 测试

启动服务后：

```bash
# 发送测试评论
curl -X POST http://localhost:5010/api/comments \
  -H "Content-Type: application/json" \
  -d '{"username": "测试用户", "content": "Hello 弹幕！"}'

# 获取评论
curl http://localhost:5010/api/comments
```

## 📝 数据存储

评论存储在 `.comments.json` 文件中：

```json
[
  {
    "id": 1702459200000,
    "username": "小明",
    "content": "加油！",
    "avatar": "小",
    "timestamp": "2024-12-13T12:00:00",
    "created_at": "12:00"
  }
]
```

最多保留 20 条评论，超出自动删除最早的。
