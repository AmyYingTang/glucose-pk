"""
Dexcom 血糖可视化 - Flask 后端（多人版 + Passkey 认证）
"""
import os
import functools
from flask import Flask, jsonify, send_from_directory, request, session, redirect, url_for
from dotenv import load_dotenv

# 导入数据获取模块
from data_fetcher import (
    get_current_glucose,
    get_glucose_history, 
    get_all_users_glucose,
    get_user_list
)
from config import USERS, THRESHOLDS, PK_SETTINGS

# 导入 Passkey 认证模块
try:
    import passkey_auth
    PASSKEY_ENABLED = True
except ImportError:
    PASSKEY_ENABLED = False
    print("⚠️  Passkey 模块未找到，认证功能禁用")

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR)

# Session 密钥（生产环境请使用环境变量）
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32))

# 是否启用认证（可通过环境变量禁用，方便本地开发）
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"


# ==================== 认证装饰器 ====================

def login_required(f):
    """要求登录的装饰器"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_REQUIRED:
            return f(*args, **kwargs)
        
        if not PASSKEY_ENABLED:
            return f(*args, **kwargs)
        
        if not session.get("logged_in"):
            # API 请求返回 401
            if request.path.startswith("/api/"):
                return jsonify({"error": "未登录", "login_required": True}), 401
            # 页面请求重定向到登录页
            return redirect("/login.html")
        
        return f(*args, **kwargs)
    return decorated_function


# ==================== 认证 API ====================

@app.route('/api/auth/status')
def auth_status():
    """获取认证状态"""
    if not PASSKEY_ENABLED:
        return jsonify({
            "passkey_enabled": False,
            "auth_required": False,
            "logged_in": True,
            "has_users": True,
        })
    
    return jsonify({
        "passkey_enabled": True,
        "auth_required": AUTH_REQUIRED,
        "logged_in": session.get("logged_in", False),
        "username": session.get("username"),
        "has_users": passkey_auth.has_any_user(),
    })


@app.route('/api/auth/register/start', methods=['POST'])
def auth_register_start():
    """开始 Passkey 注册"""
    if not PASSKEY_ENABLED:
        return jsonify({"error": "Passkey 未启用"}), 400
    
    data = request.get_json()
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    
    if not username:
        return jsonify({"error": "用户名不能为空"}), 400
    
    if len(username) < 2:
        return jsonify({"error": "用户名至少2个字符"}), 400
    
    try:
        options = passkey_auth.start_registration(username, display_name)
        return jsonify(options)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/register/complete', methods=['POST'])
def auth_register_complete():
    """完成 Passkey 注册"""
    if not PASSKEY_ENABLED:
        return jsonify({"error": "Passkey 未启用"}), 400
    
    data = request.get_json()
    username = data.get("username")
    credential = data.get("credential")
    device_name = data.get("device_name", "")
    
    if not username or not credential:
        return jsonify({"error": "缺少参数"}), 400
    
    try:
        passkey_auth.complete_registration(username, credential, device_name)
        
        # 自动登录
        session["logged_in"] = True
        session["username"] = username
        session.permanent = True
        
        return jsonify({"success": True, "username": username})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/login/start', methods=['POST'])
def auth_login_start():
    """开始 Passkey 登录"""
    if not PASSKEY_ENABLED:
        return jsonify({"error": "Passkey 未启用"}), 400
    
    data = request.get_json()
    username = data.get("username")  # 可选
    
    try:
        options = passkey_auth.start_authentication(username)
        return jsonify(options)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/login/complete', methods=['POST'])
def auth_login_complete():
    """完成 Passkey 登录"""
    if not PASSKEY_ENABLED:
        return jsonify({"error": "Passkey 未启用"}), 400
    
    data = request.get_json()
    username = data.get("username")  # 可选
    credential = data.get("credential")
    
    if not credential:
        return jsonify({"error": "缺少凭据"}), 400
    
    try:
        user_info = passkey_auth.complete_authentication(credential, username)
        
        # 设置登录 session
        session["logged_in"] = True
        session["username"] = user_info["username"]
        session["display_name"] = user_info["display_name"]
        session.permanent = True
        
        return jsonify({
            "success": True,
            "username": user_info["username"],
            "display_name": user_info["display_name"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """登出"""
    session.clear()
    return jsonify({"success": True})


@app.route('/api/auth/users')
@login_required
def auth_users():
    """获取所有用户（管理用）"""
    if not PASSKEY_ENABLED:
        return jsonify({"users": []})
    
    return jsonify({"users": passkey_auth.get_all_users()})


# ==================== 页面路由 ====================

@app.route('/')
@login_required
def index():
    """单人主页"""
    return send_from_directory(STATIC_DIR, 'index.html')


@app.route('/pk')
@login_required
def pk_page():
    """多人PK页面"""
    return send_from_directory(STATIC_DIR, 'pk.html')


@app.route('/pk/<scene>')
@login_required
def pk_scene(scene):
    """特定场景的PK页面"""
    return send_from_directory(STATIC_DIR, 'pk.html')


@app.route('/login.html')
def login_page():
    """登录页面（不需要认证）"""
    return send_from_directory(STATIC_DIR, 'login.html')


@app.route('/<path:filename>')
def serve_static(filename):
    """提供静态文件"""
    # 登录页和静态资源不需要认证
    if filename in ['login.html'] or filename.startswith(('js/', 'css/', 'images/')):
        return send_from_directory(STATIC_DIR, filename)
    
    # 其他页面需要认证
    if AUTH_REQUIRED and PASSKEY_ENABLED and not session.get("logged_in"):
        if filename.endswith('.html'):
            return redirect("/login.html")
    
    return send_from_directory(STATIC_DIR, filename)


# ==================== 单人 API ====================

@app.route('/api/glucose')
@login_required
def get_glucose():
    """获取默认用户（user1）的当前血糖"""
    result = get_current_glucose("user1")
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify(result), 500


@app.route('/api/glucose/history')
@login_required
def get_history():
    """获取默认用户（user1）的历史数据"""
    result = get_glucose_history("user1")
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify(result), 500


# ==================== 多人 API ====================

@app.route('/api/users')
@login_required
def api_get_users():
    """获取所有用户列表"""
    return jsonify({
        "success": True,
        "users": get_user_list()
    })


@app.route('/api/user/<user_id>/glucose')
@login_required
def api_user_glucose(user_id):
    """获取指定用户的当前血糖"""
    if user_id not in USERS:
        return jsonify({
            "success": False,
            "error": f"用户 {user_id} 不存在"
        }), 404
    
    result = get_current_glucose(user_id)
    return jsonify(result)


@app.route('/api/user/<user_id>/history')
@login_required
def api_user_history(user_id):
    """获取指定用户的历史数据"""
    if user_id not in USERS:
        return jsonify({
            "success": False,
            "error": f"用户 {user_id} 不存在"
        }), 404
    
    minutes = request.args.get('minutes', 180, type=int)
    max_count = request.args.get('max_count', 36, type=int)
    
    result = get_glucose_history(user_id, minutes, max_count)
    return jsonify(result)


@app.route('/api/pk/all')
@login_required
def api_pk_all():
    """获取所有用户的当前血糖（用于PK）"""
    results = get_all_users_glucose()
    return jsonify({
        "success": True,
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "players": results
    })


@app.route('/api/pk/history')
@login_required
def api_pk_history():
    """获取所有用户的历史血糖数据（用于PK曲线图）"""
    minutes = request.args.get('minutes', 180, type=int)
    max_count = request.args.get('max_count', 36, type=int)
    
    results = []
    for user_id in USERS.keys():
        result = get_glucose_history(user_id, minutes, max_count)
        results.append(result)
    
    return jsonify({
        "success": True,
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "players": results
    })


@app.route('/api/pk/settings')
@login_required
def api_pk_settings():
    """获取PK游戏设置"""
    return jsonify({
        "success": True,
        "thresholds": THRESHOLDS,
        "pk_settings": PK_SETTINGS
    })


# ==================== Demo 数据 API ====================

demo_data = {}

@app.route('/api/demo/set', methods=['POST'])
@login_required
def set_demo_data():
    """设置 demo 模式的血糖值（输入 mmol/L）"""
    data = request.get_json()
    user_id = data.get('user_id')
    value = data.get('value')
    
    if user_id and value:
        demo_data[user_id] = {
            "value": value,
            "value_mgdl": round(value * 18),
            "trend_arrow": "→",
            "trend_description": "steady",
            "datetime": __import__('datetime').datetime.now().isoformat()
        }
        return jsonify({"success": True})
    
    return jsonify({"success": False, "error": "缺少参数"}), 400


@app.route('/api/demo/all')
@login_required
def get_demo_all():
    """获取所有用户的 demo 数据"""
    players = []
    for user_id, info in USERS.items():
        if user_id in demo_data:
            players.append({
                "success": True,
                "user_id": user_id,
                "user_name": info["name"],
                "avatar": info["avatar"],
                "color": info["color"],
                "data": demo_data[user_id]
            })
        else:
            players.append({
                "success": True,
                "user_id": user_id,
                "user_name": info["name"],
                "avatar": info["avatar"],
                "color": info["color"],
                "data": {
                    "value": 5.6,
                    "value_mgdl": 100,
                    "trend_arrow": "→",
                    "trend_description": "steady",
                    "datetime": __import__('datetime').datetime.now().isoformat()
                }
            })
    
    return jsonify({
        "success": True,
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "players": players
    })


if __name__ == '__main__':
    print("=" * 50)
    print("血糖可视化服务启动中...")
    print(f"认证模式: {'开启' if AUTH_REQUIRED and PASSKEY_ENABLED else '关闭'}")
    print("单人界面: http://localhost:5010/")
    print("多人PK: http://localhost:5010/pk")
    if AUTH_REQUIRED and PASSKEY_ENABLED:
        print("登录页面: http://localhost:5010/login.html")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5010)
