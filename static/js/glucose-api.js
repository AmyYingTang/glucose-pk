/**
 * 血糖数据 API 模块
 * 统一处理数据获取，支持实时和 Demo 模式
 */

class GlucoseAPI {
    constructor() {
        // 从 localStorage 读取保存的模式，默认 demo
        this.mode = localStorage.getItem('glucose_pk_mode') || 'live';
        this.demoData = {};  // demo 模式下的模拟数据
        this.players = [];
        this.onDataUpdate = null;  // 数据更新回调
    }

    /**
     * 初始化 - 加载玩家列表
     */
    async init() {
        try {
            const response = await fetch('/api/users');
            const result = await response.json();
            if (result.success) {
                this.players = result.users;
                // 初始化 demo 数据 (mmol/L)
                this.players.forEach(p => {
                    this.demoData[p.id] = {
                        value: 5.6,  // mmol/L
                        trend_arrow: '→',
                        trend_description: 'steady'
                    };
                });
            }
        } catch (e) {
            console.warn('无法获取用户列表，使用默认玩家');
            this.players = [
                { id: 'user1', name: '小明', avatar: 'images/avatar1.svg', color: '#4CAF50' },
                { id: 'user2', name: '小红', avatar: 'images/avatar2.svg', color: '#E91E63' },
            ];
            this.players.forEach(p => {
                this.demoData[p.id] = {
                    value: 5.6,  // mmol/L
                    trend_arrow: '→',
                    trend_description: 'steady'
                };
            });
        }
        return this.players;
    }

    /**
     * 获取所有玩家数据
     */
    async getAllPlayersData() {
        if (this.mode === 'demo') {
            return this.getDemoAllData();
        } else {
            return await this.fetchLiveAllData();
        }
    }

    /**
     * 获取实时数据
     */
    async fetchLiveAllData() {
        try {
            const response = await fetch('/api/pk/all');
            const result = await response.json();
            
            if (result.success) {
                const data = {};
                result.players.forEach(p => {
                    if (p.success && p.data) {
                        data[p.user_id] = {
                            ...p.data,
                            name: p.user_name,
                            avatar: p.avatar,
                            color: p.color
                        };
                    }
                });
                return { success: true, data };
            }
            return { success: false, error: 'API 返回失败' };
        } catch (e) {
            console.error('获取实时数据失败:', e);
            return { success: false, error: e.message };
        }
    }

    /**
     * 获取 Demo 数据
     */
    getDemoAllData() {
        const data = {};
        this.players.forEach(p => {
            data[p.id] = {
                ...this.demoData[p.id],
                name: p.name,
                avatar: p.avatar,
                color: p.color
            };
        });
        return { success: true, data };
    }

    /**
     * 设置 Demo 数据 (输入 mmol/L)
     */
    setDemoValue(playerId, value) {
        if (this.demoData[playerId]) {
            this.demoData[playerId].value = value;
        }
    }

    /**
     * 设置模式（并保存到 localStorage）
     */
    setMode(mode) {
        this.mode = mode;
        localStorage.setItem('glucose_pk_mode', mode);
    }

    /**
     * 获取当前模式
     */
    getMode() {
        return this.mode;
    }

    /**
     * 获取玩家列表
     */
    getPlayers() {
        return this.players;
    }
}

// 血糖相关的工具函数
const GlucoseUtils = {
    // 阈值 (mmol/L)
    THRESHOLDS: {
        LOW: 3.9,        // 70 mg/dL
        NORMAL_LOW: 4.4, // 80 mg/dL
        NORMAL_HIGH: 7.8, // 140 mg/dL
        WARNING: 10.0,    // 180 mg/dL
        DANGER: 11.1      // 200 mg/dL
    },

    /**
     * 获取血糖状态 (输入 mmol/L)
     */
    getStatus(value) {
        if (value < this.THRESHOLDS.LOW) return 'low';
        if (value < this.THRESHOLDS.NORMAL_HIGH) return 'normal';
        if (value < this.THRESHOLDS.DANGER) return 'warning';
        return 'danger';
    },

    /**
     * 获取状态颜色
     */
    getStatusColor(value) {
        const status = this.getStatus(value);
        const colors = {
            low: '#2196F3',
            normal: '#4CAF50',
            warning: '#FF9800',
            danger: '#f44336'
        };
        return colors[status];
    },

    /**
     * 趋势翻译
     */
    translateTrend(trend) {
        const translations = {
            'rising quickly': '快速上升',
            'rising': '上升',
            'rising slightly': '缓慢上升',
            'steady': '平稳',
            'falling slightly': '缓慢下降',
            'falling': '下降',
            'falling quickly': '快速下降',
        };
        return translations[trend] || trend || '平稳';
    },

    /**
     * mg/dL 转 mmol/L
     */
    toMmol(mgdl) {
        return Math.round(mgdl / 18 * 10) / 10;
    },

    /**
     * mmol/L 转 mg/dL
     */
    toMgdl(mmol) {
        return Math.round(mmol * 18);
    }
};

// 导出
window.GlucoseAPI = GlucoseAPI;
window.GlucoseUtils = GlucoseUtils;
