"""
CGM 设备管理 API
提供设备的增删改查接口

路由：
- GET  /api/cgm/devices              - 获取当前用户的设备列表
- POST /api/cgm/devices              - 添加新设备
- GET  /api/cgm/devices/<id>         - 获取单个设备
- PUT  /api/cgm/devices/<id>         - 更新设备
- DELETE /api/cgm/devices/<id>       - 删除设备
- POST /api/cgm/devices/<id>/test    - 测试设备连接
- POST /api/cgm/devices/<id>/default - 设为默认设备
- POST /api/cgm/test-credentials     - 测试凭证（添加前验证）
- GET  /api/cgm/supported-devices    - 获取支持的设备类型
- GET  /api/cgm/players              - 获取所有活跃玩家（用于 PK）
"""

from flask import Blueprint, jsonify, request, session
from cgm_manager import cgm_manager
from cgm_providers import get_supported_devices

cgm_bp = Blueprint('cgm', __name__, url_prefix='/api/cgm')


def _require_login(f):
    """登录验证装饰器"""
    from functools import wraps
    
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "未登录", "login_required": True}), 401
        return f(*args, **kwargs)
    
    return decorated


# ==================== 设备列表 ====================

@cgm_bp.route('/devices', methods=['GET'])
@_require_login
def list_devices():
    """获取当前用户的设备列表"""
    username = session.get("username")
    devices = cgm_manager.get_devices(username)
    
    return jsonify({
        "success": True,
        "devices": devices,
        "has_devices": len(devices) > 0
    })


@cgm_bp.route('/devices', methods=['POST'])
@_require_login
def add_device():
    """添加新设备"""
    username = session.get("username")
    data = request.get_json()
    
    device_type = data.get("type")
    credentials = data.get("credentials", {})
    device_name = data.get("name")
    avatar = data.get("avatar")
    color = data.get("color")
    
    if not device_type:
        return jsonify({"error": "缺少设备类型"}), 400
    
    if not credentials.get("username") or not credentials.get("password"):
        return jsonify({"error": "缺少用户名或密码"}), 400
    
    # 先测试凭证
    test_result = cgm_manager.test_credentials(device_type, credentials)
    if not test_result.get("success"):
        return jsonify({
            "error": test_result.get("message", "凭证验证失败"),
            "test_failed": True
        }), 400
    
    try:
        device = cgm_manager.add_device(
            username=username,
            device_type=device_type,
            credentials=credentials,
            device_name=device_name,
            avatar=avatar,
            color=color
        )
        
        return jsonify({
            "success": True,
            "device": device,
            "message": "设备添加成功！",
            "current_reading": test_result.get("current_reading")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ==================== 单个设备操作 ====================

@cgm_bp.route('/devices/<device_id>', methods=['GET'])
@_require_login
def get_device(device_id):
    """获取单个设备"""
    username = session.get("username")
    device = cgm_manager.get_device(username, device_id)
    
    if not device:
        return jsonify({"error": "设备不存在"}), 404
    
    return jsonify({
        "success": True,
        "device": device
    })


@cgm_bp.route('/devices/<device_id>', methods=['PUT'])
@_require_login
def update_device(device_id):
    """更新设备信息"""
    username = session.get("username")
    data = request.get_json()
    
    updates = {}
    if "name" in data:
        updates["name"] = data["name"]
    if "avatar" in data or "color" in data:
        updates["display"] = {}
        if "avatar" in data:
            updates["display"]["avatar"] = data["avatar"]
        if "color" in data:
            updates["display"]["color"] = data["color"]
    if "is_active" in data:
        updates["is_active"] = data["is_active"]
    
    device = cgm_manager.update_device(username, device_id, updates)
    
    if not device:
        return jsonify({"error": "设备不存在"}), 404
    
    return jsonify({
        "success": True,
        "device": device,
        "message": "设备更新成功"
    })


@cgm_bp.route('/devices/<device_id>', methods=['DELETE'])
@_require_login
def delete_device(device_id):
    """删除设备"""
    username = session.get("username")
    
    if cgm_manager.remove_device(username, device_id):
        return jsonify({
            "success": True,
            "message": "设备已删除"
        })
    else:
        return jsonify({"error": "设备不存在"}), 404


@cgm_bp.route('/devices/<device_id>/test', methods=['POST'])
@_require_login
def test_device(device_id):
    """测试设备连接"""
    username = session.get("username")
    
    result = cgm_manager.test_device_connection(username, device_id)
    
    return jsonify(result)


@cgm_bp.route('/devices/<device_id>/default', methods=['POST'])
@_require_login
def set_default(device_id):
    """设为默认设备"""
    username = session.get("username")
    
    if cgm_manager.set_default_device(username, device_id):
        return jsonify({
            "success": True,
            "message": "已设为默认设备"
        })
    else:
        return jsonify({"error": "设备不存在"}), 404


@cgm_bp.route('/devices/<device_id>/credentials', methods=['PUT'])
@_require_login
def update_credentials(device_id):
    """更新设备凭证"""
    username = session.get("username")
    data = request.get_json()
    
    credentials = data.get("credentials", {})
    
    if not credentials.get("username") or not credentials.get("password"):
        return jsonify({"error": "缺少用户名或密码"}), 400
    
    # 获取设备类型
    device = cgm_manager.get_device(username, device_id)
    if not device:
        return jsonify({"error": "设备不存在"}), 404
    
    # 测试新凭证
    test_result = cgm_manager.test_credentials(device["type"], credentials)
    if not test_result.get("success"):
        return jsonify({
            "error": test_result.get("message", "凭证验证失败"),
            "test_failed": True
        }), 400
    
    if cgm_manager.update_device_credentials(username, device_id, credentials):
        return jsonify({
            "success": True,
            "message": "凭证更新成功"
        })
    else:
        return jsonify({"error": "更新失败"}), 400


# ==================== 通用接口 ====================

@cgm_bp.route('/test-credentials', methods=['POST'])
@_require_login
def test_credentials():
    """测试凭证（添加设备前验证）"""
    data = request.get_json()
    
    device_type = data.get("type")
    credentials = data.get("credentials", {})
    
    if not device_type:
        return jsonify({"error": "缺少设备类型"}), 400
    
    result = cgm_manager.test_credentials(device_type, credentials)
    
    return jsonify(result)


@cgm_bp.route('/supported-devices', methods=['GET'])
def supported_devices():
    """获取支持的设备类型"""
    devices = get_supported_devices()
    
    return jsonify({
        "success": True,
        "devices": devices
    })


@cgm_bp.route('/players', methods=['GET'])
def get_players():
    """获取所有活跃玩家（用于 PK 身份选择）"""
    all_devices = cgm_manager.get_all_active_devices()
    
    players = [
        {
            "id": device["player_id"],
            "name": device["display_name"],
            "avatar": device["avatar"],
            "color": device["color"],
            "type": "player",
            "device_type": device["device_type"],
            "owner": device["username"]
        }
        for device in all_devices
    ]
    
    # 添加 Guest 选项
    players.append({
        "id": "guest",
        "name": "观战模式",
        "avatar": "/static/images/guest.png",
        "color": "#888888",
        "type": "guest"
    })
    
    return jsonify({
        "success": True,
        "players": players
    })


# ==================== 用户头像 ====================

@cgm_bp.route('/avatar', methods=['POST'])
@_require_login
def upload_avatar():
    """上传用户头像"""
    import os
    from werkzeug.utils import secure_filename
    from passkey_auth import update_user_avatar
    
    username = session.get("username")
    
    if 'avatar' not in request.files:
        return jsonify({"success": False, "error": "没有上传文件"}), 400
    
    file = request.files['avatar']
    
    if file.filename == '':
        return jsonify({"success": False, "error": "没有选择文件"}), 400
    
    # 检查文件类型
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    
    if ext not in allowed_extensions:
        return jsonify({
            "success": False, 
            "error": f"不支持的文件格式，请使用: {', '.join(allowed_extensions)}"
        }), 400
    
    # 检查文件大小（限制 2MB）
    file.seek(0, 2)  # 移到文件末尾
    size = file.tell()
    file.seek(0)  # 移回开头
    
    if size > 2 * 1024 * 1024:
        return jsonify({"success": False, "error": "文件太大，最大 2MB"}), 400
    
    # 确保上传目录存在
    upload_dir = os.path.join('static', 'uploads', 'avatars')
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存文件（用用户名命名，覆盖旧头像）
    filename = f"{secure_filename(username)}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    
    # 删除旧头像（可能是不同扩展名）
    for old_ext in allowed_extensions:
        old_file = os.path.join(upload_dir, f"{secure_filename(username)}.{old_ext}")
        if os.path.exists(old_file) and old_file != filepath:
            try:
                os.remove(old_file)
            except:
                pass
    
    file.save(filepath)
    
    # 更新用户数据
    avatar_url = f"/static/uploads/avatars/{filename}"
    update_user_avatar(username, avatar_url)
    
    return jsonify({
        "success": True,
        "avatar": avatar_url,
        "message": "头像上传成功"
    })


@cgm_bp.route('/avatar', methods=['DELETE'])
@_require_login
def delete_avatar():
    """删除用户头像"""
    import os
    from passkey_auth import update_user_avatar, get_user_avatar
    
    username = session.get("username")
    
    # 获取当前头像路径
    avatar_path = get_user_avatar(username)
    
    if avatar_path and avatar_path.startswith('/static/uploads/avatars/'):
        # 删除文件
        file_path = avatar_path.lstrip('/')
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
    
    # 清空头像设置
    update_user_avatar(username, "")
    
    return jsonify({
        "success": True,
        "message": "头像已删除"
    })


@cgm_bp.route('/color', methods=['POST'])
@_require_login
def update_color():
    """更新用户颜色"""
    from passkey_auth import update_user_color
    
    username = session.get("username")
    data = request.get_json() or {}
    color = data.get("color", "").strip()
    
    # 简单验证颜色格式
    if not color or not color.startswith('#') or len(color) not in [4, 7]:
        return jsonify({"success": False, "error": "无效的颜色格式"}), 400
    
    update_user_color(username, color)
    
    return jsonify({
        "success": True,
        "color": color,
        "message": "颜色已更新"
    })


# ==================== 用户设备状态 ====================

@cgm_bp.route('/my-status', methods=['GET'])
@_require_login
def my_status():
    """获取当前用户的设备状态"""
    username = session.get("username")
    
    has_devices = cgm_manager.has_devices(username)
    default_device = cgm_manager.get_default_device(username)
    
    return jsonify({
        "success": True,
        "has_devices": has_devices,
        "default_device": default_device,
        "is_player": has_devices,  # 有设备就是玩家
        "player_id": f"{username}_{default_device['id']}" if default_device else None
    })
