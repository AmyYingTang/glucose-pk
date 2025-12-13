"""
评论存储模块
- 存储最近 20 条评论
- 使用 JSON 文件持久化
- 支持多用户访问
"""

import os
import json
import threading
from datetime import datetime
from typing import List, Optional

# 配置
COMMENTS_FILE = os.path.join(os.path.dirname(__file__), ".comments.json")
MAX_COMMENTS = 20
MAX_COMMENT_LENGTH = 200  # 弹幕不宜太长

# 线程锁，防止并发写入冲突
_lock = threading.Lock()


def _load_comments() -> List[dict]:
    """加载评论数据"""
    if os.path.exists(COMMENTS_FILE):
        try:
            with open(COMMENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_comments(comments: List[dict]):
    """保存评论数据"""
    with open(COMMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)


def add_comment(username: str, content: str, avatar: Optional[str] = None) -> dict:
    """
    添加评论
    
    Args:
        username: 用户名
        content: 评论内容
        avatar: 头像（可选，默认用用户名首字符）
    
    Returns:
        新添加的评论对象
    """
    # 验证输入
    username = username.strip()[:20]  # 限制用户名长度
    content = content.strip()[:MAX_COMMENT_LENGTH]
    
    if not username or not content:
        raise ValueError("用户名和评论内容不能为空")
    
    # 创建评论对象
    comment = {
        "id": int(datetime.now().timestamp() * 1000),  # 毫秒时间戳作为 ID
        "username": username,
        "content": content,
        "avatar": avatar or username[0].upper(),
        "timestamp": datetime.now().isoformat(),
        "created_at": datetime.now().strftime("%H:%M")
    }
    
    with _lock:
        comments = _load_comments()
        comments.append(comment)
        
        # 只保留最近 20 条
        if len(comments) > MAX_COMMENTS:
            comments = comments[-MAX_COMMENTS:]
        
        _save_comments(comments)
    
    return comment


def get_comments(since_id: Optional[int] = None) -> List[dict]:
    """
    获取评论列表
    
    Args:
        since_id: 可选，只返回此 ID 之后的评论（用于增量更新）
    
    Returns:
        评论列表
    """
    comments = _load_comments()
    
    if since_id:
        comments = [c for c in comments if c["id"] > since_id]
    
    return comments


def get_latest_comments(count: int = 20) -> List[dict]:
    """获取最近 N 条评论"""
    comments = _load_comments()
    return comments[-count:]


def clear_comments():
    """清空所有评论（管理功能）"""
    with _lock:
        _save_comments([])
