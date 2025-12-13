"""
Dexcom 血糖可视化 - Flask 后端（多人版 + Passkey 认证 + 弹幕评论）
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

# 导入评论 API
from comments_api import comments_bp

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

# 注册评论 Blueprint
app.register_blueprint(comments_bp)

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
    
    if not username or not credential:
        return jsonify({"error": "参数不完整"}), 400
    
    try:
        result = passkey_auth.complete_registration(username, credential)
        if result:
            session["logged_in"] = True
            session["username"] = username
            return jsonify({"success": True, "message": "注册成功"})
        else:
            return jsonify({"error": "注册失败"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/login/start', methods=['POST'])
def auth_login_start():
    """开始 Passkey 登录"""
    if not PASSKEY_ENABLED:
        return jsonify({"error": "Passkey 未启用"}), 400
    
    data = request.get_json() or {}
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
    credential = data.get("credential")
    
    if not credential:
        return jsonify({"error": "参数不完整"}), 400
    
    try:
        username = passkey_auth.complete_authentication(credential)
        if username:
            session["logged_in"] = True
            session["username"] = username
            return jsonify({"success": True, "username": username})
        else:
            return jsonify({"error": "登录失败"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 401


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """退出登录"""
    session.clear()
    return jsonify({"success": True})


# ==================== 页面路由 ====================

@app.route('/')
@login_required
def index():
    """主页"""
    return send_from_directory(STATIC_DIR, 'index.html')


@app.route('/pk')
@login_required
def pk_page():
    """多人PK页面"""
    return send_from_directory(STATIC_DIR, 'pk.html')


@app.route('/river')
@login_required
def river_page():
    """河流主题页面"""
    return send_from_directory(STATIC_DIR, 'river.html')


@app.route('/castle')
@login_required
def castle_page():
    """城堡主题页面"""
    return send_from_directory(STATIC_DIR, 'castle.html')


@app.route('/login.html')
def login_page():
    """登录页面（不需要认证）"""
    return send_from_directory(STATIC_DIR, 'login.html')


@app.route('/<path:filename>')
def static_files(filename):
    """其他静态文件"""
    # 登录相关页面不需要认证
    if filename in ['login.html', 'js/passkey-auth.js']:
        return send_from_directory(STATIC_DIR, filename)
    
    # 其他静态资源（CSS、JS、图片）不需要认证
    if filename.endswith(('.css', '.js', '.png', '.jpg', '.gif', '.svg', '.ico', '.mp4', '.webm')):
        return send_from_directory(STATIC_DIR, filename)
    
    # HTML 页面需要认证
    if AUTH_REQUIRED and PASSKEY_ENABLED and not session.get("logged_in"):
        return redirect("/login.html")
    
    return send_from_directory(STATIC_DIR, filename)


# ==================== 血糖 API ====================

@app.route('/api/glucose/current')
@login_required
def api_current_glucose():
    """获取当前血糖（单人模式）"""
    user = request.args.get('user', 'default')
    data = get_current_glucose(user)
    return jsonify(data)


@app.route('/api/glucose/history')
@login_required
def api_glucose_history():
    """获取血糖历史（单人模式）"""
    user = request.args.get('user', 'default')
    minutes = request.args.get('minutes', 180, type=int)
    data = get_glucose_history(user, minutes=minutes)
    return jsonify(data)


@app.route('/api/glucose/all')
@login_required
def api_all_glucose():
    """获取所有用户的血糖数据（多人PK模式）"""
    players = []
    
    for user_id, user_config in USERS.items():
        glucose_data = get_current_glucose(user_id)
        
        if glucose_data.get("success"):
            value = glucose_data["data"]["mmol_l"]
            
            # 判断状态
            if value < THRESHOLDS["low"]:
                status = "low"
            elif value > THRESHOLDS["high"]:
                status = "high"
            else:
                status = "normal"
            
            players.append({
                "id": user_id,
                "name": user_config["display_name"],
                "avatar": user_config.get("avatar", "🙂"),
                "value": value,
                "trend": glucose_data["data"].get("trend_arrow", "→"),
                "status": status,
                "timestamp": glucose_data["data"].get("datetime")
            })
        else:
            players.append({
                "id": user_id,
                "name": user_config["display_name"],
                "avatar": user_config.get("avatar", "🙂"),
                "value": None,
                "trend": "?",
                "status": "unknown",
                "error": glucose_data.get("error"),
                "timestamp": __import__('datetime').datetime.now().isoformat()
            })
    
    return jsonify({
        "success": True,
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "players": players
    })


@app.route('/api/config')
@login_required
def api_config():
    """获取配置信息"""
    return jsonify({
        "thresholds": THRESHOLDS,
        "pk_settings": PK_SETTINGS,
        "users": {
            uid: {
                "display_name": u["display_name"],
                "avatar": u.get("avatar", "🙂")
            } for uid, u in USERS.items()
        }
    })


if __name__ == '__main__':
    print("=" * 50)
    print("血糖可视化服务启动中...")
    print(f"认证模式: {'开启' if AUTH_REQUIRED and PASSKEY_ENABLED else '关闭'}")
    print("单人界面: http://localhost:5010/")
    print("多人PK: http://localhost:5010/pk")
    print("河流主题: http://localhost:5010/river")
    print("城堡主题: http://localhost:5010/castle")
    if AUTH_REQUIRED and PASSKEY_ENABLED:
        print("登录页面: http://localhost:5010/login.html")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5010)
