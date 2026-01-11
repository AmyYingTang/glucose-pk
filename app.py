"""
Dexcom 血糖可视化 - Flask 后端（多人版 + Passkey 认证）
"""
import os
import json
import functools
import threading
from datetime import datetime, timedelta
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

# 导入同步服务
try:
    from sync_service import start_sync_service, get_sync_status
    SYNC_SERVICE_ENABLED = True
except ImportError:
    SYNC_SERVICE_ENABLED = False
    print("⚠️  同步服务模块未找到，将直接调用 Dexcom API")

# 导入评论 API
try:
    from comments_api import comments_bp
    COMMENTS_ENABLED = True
except ImportError:
    COMMENTS_ENABLED = False
    print("⚠️  评论模块未找到，弹幕功能禁用")

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
if COMMENTS_ENABLED:
    app.register_blueprint(comments_bp)
    print("✅ 弹幕评论功能已启用")

# Session 密钥（生产环境请使用环境变量）
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32))

# 是否启用认证（可通过环境变量禁用，方便本地开发）
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"


# ==================== 打卡和分数数据文件 ====================

CHECKINS_FILE = os.path.join(BASE_DIR, "checkins.json")

# 线程锁（保证并发安全）
checkins_lock = threading.Lock()


def _load_json_file(filepath, default=None):
    """加载 JSON 文件"""
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载 {filepath} 失败: {e}")
            return default
    return default


def _save_json_file(filepath, data):
    """保存 JSON 文件"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ 保存 {filepath} 失败: {e}")


# ==================== 日期辅助函数 ====================

def get_today_str():
    """获取今天的日期字符串 YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def get_recent_days(days=15):
    """获取最近 N 天的日期列表（从今天往前）"""
    today = datetime.now().date()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


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
        "display_name": session.get("display_name"),
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
        
        # 获取用户信息（包括 display_name）
        user = passkey_auth.get_user(username)
        
        # 自动登录
        session["logged_in"] = True
        session["username"] = username
        session["display_name"] = user.get("display_name", username) if user else username
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
    session_id = data.get("session_id")
    username = data.get("username")  # 可选
    credential = data.get("credential")
    
    if not session_id or not credential:
        return jsonify({"error": "缺少凭据"}), 400
    
    try:
        user_info = passkey_auth.complete_authentication(credential, session_id, username)
        
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
    """首页重定向到默认游戏页面"""
    # 每次请求时读取，修改 .env 后无需重启
    from dotenv import dotenv_values
    config = dotenv_values('.env')
    default_page = config.get('DEFAULT_PAGE', '/river.html')
    return redirect(default_page)


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
        "timestamp": datetime.now().isoformat(),
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
        "timestamp": datetime.now().isoformat(),
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


@app.route('/api/sync/status')
@login_required
def api_sync_status():
    """获取数据同步状态"""
    if SYNC_SERVICE_ENABLED:
        status = get_sync_status()
        return jsonify({
            "success": True,
            "enabled": True,
            **status
        })
    else:
        return jsonify({
            "success": True,
            "enabled": False,
            "message": "同步服务未启用"
        })


@app.route('/api/pk/players')
@login_required
def api_pk_players():
    """获取可选的 Dexcom 玩家列表（用于身份选择）"""
    players = []
    for user_id, info in USERS.items():
        players.append({
            "id": user_id,
            "name": info["name"],
            "avatar": info["avatar"],
            "color": info["color"]
        })
    return jsonify({
        "success": True,
        "players": players
    })


# ==================== 打卡 API ====================

@app.route('/api/checkin', methods=['POST'])
@login_required
def api_checkin():
    """打卡（运动或睡眠）"""
    data = request.get_json()
    player_id = data.get("player_id")  # Dexcom user_id，如 "user1"
    checkin_type = data.get("type")  # "exercise" 或 "sleep"
    
    if not player_id or not checkin_type:
        return jsonify({"error": "缺少参数"}), 400
    
    if player_id not in USERS:
        return jsonify({"error": "玩家不存在"}), 400
    
    if checkin_type not in ["exercise", "sleep"]:
        return jsonify({"error": "无效的打卡类型"}), 400
    
    today = get_today_str()
    
    with checkins_lock:
        checkins = _load_json_file(CHECKINS_FILE, {})
        
        if today not in checkins:
            checkins[today] = {}
        
        if player_id not in checkins[today]:
            checkins[today][player_id] = {}
        
        # 记录打卡
        checkins[today][player_id][checkin_type] = {
            "checked": True,
            "time": datetime.now().isoformat()
        }
        
        _save_json_file(CHECKINS_FILE, checkins)
    
    return jsonify({
        "success": True,
        "message": f"{USERS[player_id]['name']} 打卡成功：{checkin_type}",
        "date": today,
        "player_id": player_id,
        "type": checkin_type
    })


@app.route('/api/checkin/cancel', methods=['POST'])
@login_required
def api_checkin_cancel():
    """取消打卡"""
    data = request.get_json()
    player_id = data.get("player_id")
    checkin_type = data.get("type")
    
    if not player_id or not checkin_type:
        return jsonify({"error": "缺少参数"}), 400
    
    today = get_today_str()
    
    with checkins_lock:
        checkins = _load_json_file(CHECKINS_FILE, {})
        
        if today in checkins and player_id in checkins[today]:
            if checkin_type in checkins[today][player_id]:
                del checkins[today][player_id][checkin_type]
                _save_json_file(CHECKINS_FILE, checkins)
    
    return jsonify({
        "success": True,
        "message": "已取消打卡"
    })


@app.route('/api/checkin/today')
@login_required
def api_checkin_today():
    """获取今日所有人的打卡状态"""
    today = get_today_str()
    
    with checkins_lock:
        checkins = _load_json_file(CHECKINS_FILE, {})
    
    today_checkins = checkins.get(today, {})
    
    # 构建返回数据
    result = {}
    for user_id, info in USERS.items():
        player_checkins = today_checkins.get(user_id, {})
        result[user_id] = {
            "name": info["name"],
            "exercise": player_checkins.get("exercise", {}).get("checked", False),
            "exercise_time": player_checkins.get("exercise", {}).get("time"),
            "sleep": player_checkins.get("sleep", {}).get("checked", False),
            "sleep_time": player_checkins.get("sleep", {}).get("time"),
        }
    
    return jsonify({
        "success": True,
        "date": today,
        "checkins": result
    })


@app.route('/api/checkin/week')
@login_required
def api_checkin_week():
    """获取最近 7 天打卡日历"""
    today = datetime.now().date()
    
    with checkins_lock:
        checkins = _load_json_file(CHECKINS_FILE, {})
    
    # 构建最近 7 天的数据
    week_data = {}
    for i in range(6, -1, -1):  # 从 6 天前到今天
        current = today - timedelta(days=i)
        date_str = current.strftime("%Y-%m-%d")
        day_checkins = checkins.get(date_str, {})
        
        # 获取星期几
        weekday_index = current.weekday()  # Monday=0, Sunday=6
        weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][weekday_index]
        
        week_data[date_str] = {
            "weekday": current.strftime("%a"),
            "weekday_cn": weekday_cn,
            "players": {}
        }
        
        for user_id in USERS.keys():
            player_checkins = day_checkins.get(user_id, {})
            exercise = player_checkins.get("exercise", {}).get("checked", False)
            sleep = player_checkins.get("sleep", {}).get("checked", False)
            
            if exercise and sleep:
                status = "complete"
            elif exercise or sleep:
                status = "partial"
            else:
                status = "empty"
            
            week_data[date_str]["players"][user_id] = {
                "exercise": exercise,
                "sleep": sleep,
                "status": status
            }
    
    return jsonify({
        "success": True,
        "today": get_today_str(),
        "data": week_data
    })


# ==================== TIR 计算 ====================

def calculate_daily_tir(user_id, date_str):
    """
    计算某用户某天的 TIR (Time in Range)
    优先从本地同步数据计算
    
    Returns:
        float: 0-1 之间的比例，或 None（无数据）
    """
    try:
        # 从本地数据获取
        if SYNC_SERVICE_ENABLED:
            from sync_service import load_user_data
            local_data = load_user_data(user_id)
            history = local_data.get("history", [])
        else:
            # Fallback: 从 API 获取
            result = get_glucose_history(user_id, minutes=1440, max_count=288)
            if not result.get("success"):
                return None
            history = result.get("history", [])
        
        if not history:
            return None
        
        # 过滤出指定日期的数据
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        day_readings = []
        
        for reading in history:
            try:
                dt_str = reading.get("datetime", "")
                reading_time = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if reading_time.date() == target_date:
                    day_readings.append(reading["value"])
            except:
                continue
        
        if not day_readings:
            return None
        
        # 计算在范围内的比例 (3.9 - 7.8 mmol/L)
        in_range = sum(1 for v in day_readings if 3.9 <= v <= 7.8)
        tir = in_range / len(day_readings)
        
        return tir
    
    except Exception as e:
        print(f"计算 TIR 失败 ({user_id}, {date_str}): {e}")
        return None


# ==================== 每日 TIR 分数 API ====================

@app.route('/api/scores/daily')
@login_required
def api_scores_daily():
    """获取最近 15 天的每日 TIR 分数"""
    days = request.args.get('days', 15, type=int)
    days = min(days, 15)  # 最多 15 天
    
    recent_dates = get_recent_days(days)
    
    with checkins_lock:
        checkins = _load_json_file(CHECKINS_FILE, {})
    
    # 构建每个玩家的数据
    players_data = {}
    for user_id, info in USERS.items():
        players_data[user_id] = {
            "name": info["name"],
            "avatar": info["avatar"],
            "color": info["color"],
            "daily": [],
            "total_tir_score": 0,
            "total_checkin_score": 0,
            "total_score": 0,
            "days_with_data": 0
        }
    
    # 遍历每一天
    for date_str in reversed(recent_dates):  # 从最早到最近
        day_checkins = checkins.get(date_str, {})
        
        for user_id in USERS.keys():
            day_data = {
                "date": date_str,
                "tir": None,
                "tir_score": 0,
                "exercise": False,
                "sleep": False,
                "checkin_score": 0,
                "total": 0
            }
            
            # TIR 分数（0-70）
            tir = calculate_daily_tir(user_id, date_str)
            if tir is not None:
                day_data["tir"] = round(tir * 100, 1)  # 百分比
                day_data["tir_score"] = round(tir * 70, 1)
                players_data[user_id]["days_with_data"] += 1
            
            # 打卡分数
            player_checkins = day_checkins.get(user_id, {})
            if player_checkins.get("exercise", {}).get("checked"):
                day_data["exercise"] = True
                day_data["checkin_score"] += 15
            if player_checkins.get("sleep", {}).get("checked"):
                day_data["sleep"] = True
                day_data["checkin_score"] += 15
            
            day_data["total"] = day_data["tir_score"] + day_data["checkin_score"]
            
            players_data[user_id]["daily"].append(day_data)
            players_data[user_id]["total_tir_score"] += day_data["tir_score"]
            players_data[user_id]["total_checkin_score"] += day_data["checkin_score"]
            players_data[user_id]["total_score"] += day_data["total"]
    
    # 转换为列表并排序
    result = []
    for user_id, data in players_data.items():
        result.append({
            "user_id": user_id,
            **data
        })
    
    result.sort(key=lambda x: x["total_score"], reverse=True)
    
    # 标记领先者
    if result:
        result[0]["is_leader"] = True
    
    return jsonify({
        "success": True,
        "days": days,
        "date_range": {
            "start": recent_dates[-1],
            "end": recent_dates[0]
        },
        "players": result,
        "max_daily_score": 100,  # 70 TIR + 30 打卡
        "max_total_score": days * 100
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
            "datetime": datetime.now().isoformat()
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
                    "datetime": datetime.now().isoformat()
                }
            })
    
    return jsonify({
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "players": players
    })

# ==================== 密码认证路由 ====================

@app.route('/api/auth/register/password', methods=['POST'])
def auth_register_password():
    """使用密码注册"""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    display_name = data.get("display_name")
    
    if not username or not password:
        return jsonify({"error": "缺少用户名或密码"}), 400
    
    try:
        passkey_auth.register_with_password(username, password, display_name)
        
        # 自动登录
        session["logged_in"] = True
        session["username"] = username
        session["display_name"] = display_name or username
        session.permanent = True
        
        return jsonify({"success": True, "username": username})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/login/password', methods=['POST'])
def auth_login_password():
    """使用密码登录"""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return jsonify({"error": "缺少用户名或密码"}), 400
    
    try:
        user_info = passkey_auth.login_with_password(username, password)
        
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


# ==================== 账户管理路由 ====================

@app.route('/api/auth/add-passkey/start', methods=['POST'])
@login_required
def add_passkey_start():
    """为已登录用户添加新 Passkey"""
    username = session.get('username')
    device_name = request.get_json().get('device_name', '')
    
    try:
        user = passkey_auth.get_user(username)
        options = passkey_auth.start_registration(username, user['display_name'])
        session['pending_device_name'] = device_name
        return jsonify(options)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/add-passkey/complete', methods=['POST'])
@login_required
def add_passkey_complete():
    """完成添加新 Passkey"""
    username = session.get('username')
    credential = request.get_json().get('credential')
    device_name = session.pop('pending_device_name', '新设备')
    
    if not credential:
        return jsonify({"error": "缺少凭据"}), 400
    
    try:
        passkey_auth.complete_registration(username, credential, device_name)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/add-password', methods=['POST'])
@login_required
def add_password():
    """为已登录用户添加密码"""
    username = session.get('username')
    password = request.get_json().get('password')
    
    if not password:
        return jsonify({"error": "缺少密码"}), 400
    
    try:
        passkey_auth.add_password_to_existing_user(username, password)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password_route():
    """修改密码"""
    username = session.get('username')
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not new_password:
        return jsonify({"error": "缺少新密码"}), 400
    
    try:
        passkey_auth.change_password(username, old_password or '', new_password)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/delete-credential', methods=['POST'])
@login_required
def delete_credential_route():
    """删除 Passkey 凭据"""
    username = session.get('username')
    credential_id = request.get_json().get('credential_id')
    
    if not credential_id:
        return jsonify({"error": "缺少凭据 ID"}), 400
    
    try:
        if passkey_auth.delete_credential(username, credential_id):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "凭据不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/auth/user-info')
@login_required
def user_info():
    """获取当前用户信息"""
    username = session.get('username')
    user = passkey_auth.get_user(username)
    
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    
    return jsonify({
        "username": user["username"],
        "display_name": user["display_name"],
        "has_password": "password_hash" in user,
        "avatar": user.get("avatar", ""),
        "color": user.get("color", "#4CAF50"),
        "credentials": [
            {
                "id": cred["credential_id"],
                "device_name": cred.get("device_name", "未命名设备"),
                "created_at": cred.get("created_at", "")
            }
            for cred in user.get("credentials", [])
        ]
    })


@app.route('/account')
@login_required
def account_page():
    """账户管理页面"""
    return send_from_directory('static', 'account.html')


if __name__ == '__main__':
    print("=" * 50)
    print("血糖可视化服务启动中...")
    print(f"认证模式: {'开启' if AUTH_REQUIRED and PASSKEY_ENABLED else '关闭'}")
    
    # 启动后台同步服务
    if SYNC_SERVICE_ENABLED:
        start_sync_service()
        print("✅ 后台数据同步服务已启动")
    else:
        print("⚠️  后台同步服务未启用，将直接调用 Dexcom API")
    
    print("单人界面: http://localhost:5010/")
    print("多人PK: http://localhost:5010/pk")
    if AUTH_REQUIRED and PASSKEY_ENABLED:
        print("登录页面: http://localhost:5010/login.html")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5010)
