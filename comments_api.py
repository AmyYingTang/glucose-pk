"""
评论 API 路由
添加到 Flask app 中使用
"""

from flask import Blueprint, jsonify, request, session
from comments import add_comment, get_comments, get_latest_comments

# 创建 Blueprint
comments_bp = Blueprint('comments', __name__, url_prefix='/api/comments')


@comments_bp.route('', methods=['GET'])
def api_get_comments():
    """
    获取评论列表
    
    Query params:
        since_id: 可选，只返回此 ID 之后的评论
        count: 可选，返回数量（默认 20）
    """
    since_id = request.args.get('since_id', type=int)
    count = request.args.get('count', default=20, type=int)
    
    if since_id:
        comments = get_comments(since_id=since_id)
    else:
        comments = get_latest_comments(count=min(count, 20))
    
    return jsonify({
        "success": True,
        "comments": comments,
        "count": len(comments)
    })


@comments_bp.route('', methods=['POST'])
def api_add_comment():
    """
    添加评论
    
    Body (JSON):
        username: 用户名
        content: 评论内容
        avatar: 可选，头像
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400
    
    username = data.get('username', '').strip()
    content = data.get('content', '').strip()
    avatar = data.get('avatar')
    
    # 如果已登录，可以用 session 中的用户名
    if not username and session.get('username'):
        username = session.get('username')
    
    if not username:
        return jsonify({"success": False, "error": "请输入用户名"}), 400
    
    if not content:
        return jsonify({"success": False, "error": "请输入评论内容"}), 400
    
    if len(content) > 200:
        return jsonify({"success": False, "error": "评论不能超过200字"}), 400
    
    try:
        comment = add_comment(username, content, avatar)
        return jsonify({
            "success": True,
            "comment": comment
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": "服务器错误"}), 500
