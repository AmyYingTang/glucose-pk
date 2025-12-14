/**
 * 弹幕 + 评论系统
 * 
 * 功能：
 * - 可折叠的评论面板（浮动在屏幕上）
 * - 弹幕滚动显示（屏幕上方横向滚动）
 * - 自动轮询获取新评论
 * 
 * 使用方法：
 * 1. 引入此脚本
 * 2. 调用 DanmakuSystem.init() 初始化
 */

const DanmakuSystem = {
    // 配置
    config: {
        pollInterval: 5000,      // 轮询间隔（毫秒）
        danmakuDuration: 8000,   // 弹幕滚动时长（毫秒）
        danmakuSpacing: 2000,    // 弹幕间隔（毫秒）
        maxDanmakuLines: 3,      // 弹幕轨道数
        loopInterval: 3000,      // 循环播放时每条弹幕间隔（毫秒）
    },
    
    // 状态
    state: {
        lastCommentId: 0,
        comments: [],
        danmakuQueue: [],
        isPanelOpen: false,
        pollTimer: null,
        loopTimer: null,         // 循环播放定时器
        loopIndex: 0,            // 当前循环到第几条
        isLooping: localStorage.getItem('danmaku_loop') === 'true',  // 是否循环播放
        username: localStorage.getItem('danmaku_username') || '',
    },
    
    /**
     * 初始化弹幕系统
     */
    init() {
        this.createStyles();
        this.createUI();
        this.bindEvents();
        this.startPolling();
        this.loadComments();
        console.log('🎬 弹幕系统已初始化');
    },
    
    /**
     * 创建 CSS 样式
     */
    createStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* ==================== 弹幕区域 ==================== */
            .danmaku-container {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                height: 120px;
                pointer-events: none;
                overflow: hidden;
                z-index: 9998;
            }
            
            .danmaku-item {
                position: absolute;
                white-space: nowrap;
                font-size: 18px;
                font-weight: 500;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.8), -1px -1px 2px rgba(0,0,0,0.8);
                color: #fff;
                padding: 4px 12px;
                border-radius: 20px;
                background: rgba(0,0,0,0.3);
                animation: danmaku-scroll linear forwards;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .danmaku-item .avatar {
                width: 24px;
                height: 24px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                font-weight: bold;
                color: white;
            }
            
            .danmaku-item .username {
                color: #ffd700;
                font-weight: bold;
            }
            
            @keyframes danmaku-scroll {
                from { transform: translateX(100vw); }
                to { transform: translateX(-100%); }
            }
            
            /* ==================== 评论面板触发按钮 ==================== */
            .comment-toggle-btn {
                position: fixed;
                right: 20px;
                bottom: 100px;
                width: 56px;
                height: 56px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: transform 0.3s, box-shadow 0.3s;
            }
            
            .comment-toggle-btn:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
            }
            
            .comment-toggle-btn svg {
                width: 28px;
                height: 28px;
                fill: white;
            }
            
            .comment-toggle-btn .badge {
                position: absolute;
                top: -5px;
                right: -5px;
                background: #ff4757;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 10px;
                min-width: 18px;
                text-align: center;
            }
            
            /* ==================== 评论面板 ==================== */
            .comment-panel {
                position: fixed;
                right: 20px;
                bottom: 170px;
                width: 360px;
                max-height: 500px;
                background: rgba(20, 20, 40, 0.95);
                border-radius: 16px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                z-index: 9999;
                display: flex;
                flex-direction: column;
                transform: scale(0.9) translateY(20px);
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                border: 1px solid rgba(255,255,255,0.1);
            }
            
            .comment-panel.open {
                transform: scale(1) translateY(0);
                opacity: 1;
                visibility: visible;
            }
            
            .comment-panel-header {
                padding: 16px 20px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .comment-panel-header h3 {
                margin: 0;
                color: white;
                font-size: 16px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .comment-panel-close {
                background: none;
                border: none;
                color: rgba(255,255,255,0.6);
                cursor: pointer;
                font-size: 24px;
                line-height: 1;
                padding: 4px;
            }
            
            .comment-panel-close:hover {
                color: white;
            }
            
            /* 评论列表 */
            .comment-list {
                flex: 1;
                overflow-y: auto;
                padding: 12px 16px;
                max-height: 300px;
            }
            
            .comment-list::-webkit-scrollbar {
                width: 6px;
            }
            
            .comment-list::-webkit-scrollbar-thumb {
                background: rgba(255,255,255,0.2);
                border-radius: 3px;
            }
            
            .comment-item {
                display: flex;
                gap: 12px;
                padding: 10px 0;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            
            .comment-item:last-child {
                border-bottom: none;
            }
            
            .comment-item .avatar {
                width: 36px;
                height: 36px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                font-weight: bold;
                color: white;
                flex-shrink: 0;
            }
            
            .comment-item .content {
                flex: 1;
                min-width: 0;
            }
            
            .comment-item .meta {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 4px;
            }
            
            .comment-item .username {
                color: #ffd700;
                font-weight: 600;
                font-size: 13px;
            }
            
            .comment-item .time {
                color: rgba(255,255,255,0.4);
                font-size: 12px;
            }
            
            .comment-item .text {
                color: rgba(255,255,255,0.9);
                font-size: 14px;
                line-height: 1.4;
                word-break: break-word;
            }
            
            .comment-empty {
                text-align: center;
                color: rgba(255,255,255,0.4);
                padding: 40px 20px;
            }
            
            /* 输入区域 */
            .comment-input-area {
                padding: 16px;
                border-top: 1px solid rgba(255,255,255,0.1);
            }
            
            .comment-input-row {
                display: flex;
                gap: 8px;
                margin-bottom: 10px;
            }
            
            .comment-input-area input,
            .comment-input-area textarea {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 8px;
                padding: 10px 12px;
                color: white;
                font-size: 14px;
                outline: none;
                transition: border-color 0.2s;
            }
            
            .comment-input-area input:focus,
            .comment-input-area textarea:focus {
                border-color: #667eea;
            }
            
            .comment-input-area input::placeholder,
            .comment-input-area textarea::placeholder {
                color: rgba(255,255,255,0.4);
            }
            
            .comment-input-area input[name="username"] {
                width: 100px;
                flex-shrink: 0;
            }
            
            .comment-input-area textarea {
                flex: 1;
                resize: none;
                height: 40px;
                min-height: 40px;
            }
            
            .comment-submit-btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: opacity 0.2s, transform 0.2s;
                width: 100%;
            }
            
            .comment-submit-btn:hover {
                opacity: 0.9;
                transform: translateY(-1px);
            }
            
            .comment-submit-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            
            /* 循环播放开关 */
            .loop-toggle-container {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 12px 16px;
                border-top: 1px solid rgba(255,255,255,0.1);
                background: rgba(255,255,255,0.03);
            }
            
            .loop-toggle-label {
                color: rgba(255,255,255,0.8);
                font-size: 13px;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            
            .loop-toggle-switch {
                position: relative;
                width: 44px;
                height: 24px;
                background: rgba(255,255,255,0.2);
                border-radius: 12px;
                cursor: pointer;
                transition: background 0.3s;
            }
            
            .loop-toggle-switch.active {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            
            .loop-toggle-switch::after {
                content: '';
                position: absolute;
                top: 2px;
                left: 2px;
                width: 20px;
                height: 20px;
                background: white;
                border-radius: 50%;
                transition: transform 0.3s;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            
            .loop-toggle-switch.active::after {
                transform: translateX(20px);
            }
            
            /* 响应式 */
            @media (max-width: 480px) {
                .comment-panel {
                    right: 10px;
                    left: 10px;
                    width: auto;
                    bottom: 160px;
                }
                
                .comment-toggle-btn {
                    right: 15px;
                    bottom: 90px;
                    width: 50px;
                    height: 50px;
                }
            }
        `;
        document.head.appendChild(style);
    },
    
    /**
     * 创建 UI 元素
     */
    createUI() {
        // 弹幕容器
        const danmakuContainer = document.createElement('div');
        danmakuContainer.className = 'danmaku-container';
        danmakuContainer.id = 'danmaku-container';
        document.body.appendChild(danmakuContainer);
        
        // 评论面板触发按钮
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'comment-toggle-btn';
        toggleBtn.id = 'comment-toggle-btn';
        toggleBtn.innerHTML = `
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
            </svg>
            <span class="badge" id="comment-badge" style="display:none">0</span>
        `;
        document.body.appendChild(toggleBtn);
        
        // 评论面板
        const panel = document.createElement('div');
        panel.className = 'comment-panel';
        panel.id = 'comment-panel';
        panel.innerHTML = `
            <div class="comment-panel-header">
                <h3>💬 弹幕评论</h3>
                <button class="comment-panel-close" id="comment-panel-close">&times;</button>
            </div>
            <div class="loop-toggle-container">
                <span class="loop-toggle-label">
                    🔄 循环播放弹幕
                </span>
                <div class="loop-toggle-switch ${this.state.isLooping ? 'active' : ''}" id="loop-toggle"></div>
            </div>
            <div class="comment-list" id="comment-list">
                <div class="comment-empty">暂无评论，快来发第一条弹幕吧！</div>
            </div>
            <div class="comment-input-area">
                <div class="comment-input-row">
                    <input type="text" name="username" id="comment-username" 
                           placeholder="昵称" maxlength="20" 
                           value="${this.state.username}">
                    <textarea id="comment-content" placeholder="输入弹幕内容..." maxlength="200"></textarea>
                </div>
                <button class="comment-submit-btn" id="comment-submit">发送弹幕 🚀</button>
            </div>
        `;
        document.body.appendChild(panel);
    },
    
    /**
     * 绑定事件
     */
    bindEvents() {
        // 打开/关闭面板
        document.getElementById('comment-toggle-btn').addEventListener('click', () => {
            this.togglePanel();
        });
        
        document.getElementById('comment-panel-close').addEventListener('click', () => {
            this.togglePanel(false);
        });
        
        // 发送评论
        document.getElementById('comment-submit').addEventListener('click', () => {
            this.submitComment();
        });
        
        // 回车发送
        document.getElementById('comment-content').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.submitComment();
            }
        });
        
        // 保存用户名
        document.getElementById('comment-username').addEventListener('change', (e) => {
            this.state.username = e.target.value;
            localStorage.setItem('danmaku_username', e.target.value);
        });
        
        // 循环播放开关
        document.getElementById('loop-toggle').addEventListener('click', (e) => {
            this.toggleLoop();
        });
        
        // 点击面板外关闭
        document.addEventListener('click', (e) => {
            const panel = document.getElementById('comment-panel');
            const btn = document.getElementById('comment-toggle-btn');
            if (this.state.isPanelOpen && 
                !panel.contains(e.target) && 
                !btn.contains(e.target)) {
                this.togglePanel(false);
            }
        });
    },
    
    /**
     * 切换面板显示
     */
    togglePanel(open = null) {
        const panel = document.getElementById('comment-panel');
        this.state.isPanelOpen = open !== null ? open : !this.state.isPanelOpen;
        panel.classList.toggle('open', this.state.isPanelOpen);
        
        // 隐藏红点
        if (this.state.isPanelOpen) {
            document.getElementById('comment-badge').style.display = 'none';
        }
    },
    
    /**
     * 切换循环播放
     */
    toggleLoop(enable = null) {
        const toggle = document.getElementById('loop-toggle');
        this.state.isLooping = enable !== null ? enable : !this.state.isLooping;
        
        // 更新 UI
        toggle.classList.toggle('active', this.state.isLooping);
        
        // 保存设置
        localStorage.setItem('danmaku_loop', this.state.isLooping);
        
        if (this.state.isLooping) {
            this.startLoop();
            console.log('🔄 开始循环播放弹幕');
        } else {
            this.stopLoop();
            console.log('⏹️ 停止循环播放');
        }
    },
    
    /**
     * 开始循环播放
     */
    startLoop() {
        // 先停止之前的循环
        this.stopLoop();
        
        if (this.state.comments.length === 0) {
            console.log('没有评论可以循环播放');
            return;
        }
        
        // 重置索引
        this.state.loopIndex = 0;
        
        // 立即播放第一条
        this.playNextInLoop();
        
        // 设置循环定时器
        this.state.loopTimer = setInterval(() => {
            this.playNextInLoop();
        }, this.config.loopInterval);
    },
    
    /**
     * 播放循环中的下一条
     */
    playNextInLoop() {
        if (!this.state.isLooping || this.state.comments.length === 0) {
            return;
        }
        
        const comment = this.state.comments[this.state.loopIndex];
        this.showDanmaku(comment);
        
        // 移动到下一条，循环
        this.state.loopIndex = (this.state.loopIndex + 1) % this.state.comments.length;
    },
    
    /**
     * 停止循环播放
     */
    stopLoop() {
        if (this.state.loopTimer) {
            clearInterval(this.state.loopTimer);
            this.state.loopTimer = null;
        }
    },
    
    /**
     * 加载评论
     */
    async loadComments() {
        try {
            const response = await fetch('/api/comments');
            const data = await response.json();
            
            if (data.success) {
                this.state.comments = data.comments;
                this.renderCommentList();
                
                // 更新最后 ID
                if (data.comments.length > 0) {
                    this.state.lastCommentId = Math.max(...data.comments.map(c => c.id));
                }
                
                // 如果循环开关是开的，自动开始循环
                if (this.state.isLooping && data.comments.length > 0) {
                    this.startLoop();
                }
            }
        } catch (error) {
            console.error('加载评论失败:', error);
        }
    },
    
    /**
     * 轮询新评论
     */
    startPolling() {
        this.state.pollTimer = setInterval(async () => {
            try {
                const url = this.state.lastCommentId 
                    ? `/api/comments?since_id=${this.state.lastCommentId}`
                    : '/api/comments';
                
                const response = await fetch(url);
                const data = await response.json();
                
                if (data.success && data.comments.length > 0) {
                    // 添加新评论
                    data.comments.forEach(comment => {
                        // 避免重复
                        if (!this.state.comments.find(c => c.id === comment.id)) {
                            this.state.comments.push(comment);
                            this.showDanmaku(comment);
                        }
                    });
                    
                    // 保持最多 20 条
                    if (this.state.comments.length > 20) {
                        this.state.comments = this.state.comments.slice(-20);
                    }
                    
                    // 更新最后 ID
                    this.state.lastCommentId = Math.max(...data.comments.map(c => c.id));
                    
                    // 更新列表
                    this.renderCommentList();
                    
                    // 显示红点（如果面板关闭）
                    if (!this.state.isPanelOpen) {
                        const badge = document.getElementById('comment-badge');
                        badge.textContent = data.comments.length;
                        badge.style.display = 'block';
                    }
                }
            } catch (error) {
                console.error('轮询评论失败:', error);
            }
        }, this.config.pollInterval);
    },
    
    /**
     * 渲染评论列表
     */
    renderCommentList() {
        const list = document.getElementById('comment-list');
        
        if (this.state.comments.length === 0) {
            list.innerHTML = '<div class="comment-empty">暂无评论，快来发第一条弹幕吧！</div>';
            return;
        }
        
        list.innerHTML = this.state.comments.map(comment => `
            <div class="comment-item">
                <div class="avatar">${comment.avatar}</div>
                <div class="content">
                    <div class="meta">
                        <span class="username">${this.escapeHtml(comment.username)}</span>
                        <span class="time">${comment.created_at}</span>
                    </div>
                    <div class="text">${this.escapeHtml(comment.content)}</div>
                </div>
            </div>
        `).join('');
        
        // 滚动到底部
        list.scrollTop = list.scrollHeight;
    },
    
    /**
     * 提交评论
     */
    submitComment() {
        const usernameInput = document.getElementById('comment-username');
        const contentInput = document.getElementById('comment-content');
        const submitBtn = document.getElementById('comment-submit');
        
        const username = usernameInput.value.trim();
        const content = contentInput.value.trim();
        
        if (!username) {
            usernameInput.focus();
            usernameInput.style.borderColor = '#ff4757';
            setTimeout(() => usernameInput.style.borderColor = '', 2000);
            return;
        }
        
        if (!content) {
            contentInput.focus();
            return;
        }
        
        // 保存用户名
        this.state.username = username;
        localStorage.setItem('danmaku_username', username);
        
        // 创建评论对象
        const newComment = {
            id: Date.now(),
            username: username,
            content: content,
            avatar: username[0].toUpperCase(),
            created_at: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
            timestamp: new Date().toISOString()
        };
        
        // 🚀 立即添加到本地列表并显示
        this.state.comments.push(newComment);
        this.state.lastCommentId = newComment.id;
        this.renderCommentList();
        this.showDanmaku(newComment);
        
        // 清空输入
        contentInput.value = '';
        
        // 暂停循环播放（如果开启的话）
        const wasLooping = this.state.isLooping;
        if (wasLooping) {
            this.stopLoop();
        }
        
        // 后台异步发送到服务器
        fetch('/api/comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, content })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 用服务器返回的 ID 更新本地评论
                const localComment = this.state.comments.find(c => c.id === newComment.id);
                if (localComment) {
                    localComment.id = data.comment.id;
                    this.state.lastCommentId = data.comment.id;
                }
                console.log('✅ 评论已保存到服务器');
            } else {
                console.error('保存评论失败:', data.error);
            }
        })
        .catch(error => {
            console.error('发送评论失败:', error);
        })
        .finally(() => {
            // 恢复循环播放
            if (wasLooping) {
                setTimeout(() => this.startLoop(), 500);
            }
        });
    },
    
    /**
     * 显示弹幕
     */
    showDanmaku(comment) {
        const container = document.getElementById('danmaku-container');
        
        // 创建弹幕元素
        const danmaku = document.createElement('div');
        danmaku.className = 'danmaku-item';
        danmaku.innerHTML = `
            <div class="avatar">${comment.avatar}</div>
            <span class="username">${this.escapeHtml(comment.username)}:</span>
            <span>${this.escapeHtml(comment.content)}</span>
        `;
        
        // 随机轨道
        const track = Math.floor(Math.random() * this.config.maxDanmakuLines);
        danmaku.style.top = `${10 + track * 38}px`;
        danmaku.style.animationDuration = `${this.config.danmakuDuration}ms`;
        
        // 随机颜色变化（可选）
        const colors = ['#fff', '#ffd700', '#7bed9f', '#70a1ff', '#ff6b81'];
        danmaku.style.color = colors[Math.floor(Math.random() * colors.length)];
        
        container.appendChild(danmaku);
        
        // 动画结束后移除
        danmaku.addEventListener('animationend', () => {
            danmaku.remove();
        });
    },
    
    /**
     * HTML 转义
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    /**
     * 销毁
     */
    destroy() {
        if (this.state.pollTimer) {
            clearInterval(this.state.pollTimer);
        }
        if (this.state.loopTimer) {
            clearInterval(this.state.loopTimer);
        }
        document.getElementById('danmaku-container')?.remove();
        document.getElementById('comment-toggle-btn')?.remove();
        document.getElementById('comment-panel')?.remove();
    }
};

// 页面加载完成后自动初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => DanmakuSystem.init());
} else {
    DanmakuSystem.init();
}
