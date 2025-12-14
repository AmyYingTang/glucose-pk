/**
 * 血糖曲线图组件
 * 可复用的多人血糖趋势图
 * 支持可配置的时间范围
 */

class GlucoseChart {
    // 预设的时间范围选项
    static TIME_RANGES = {
        '3h':  { hours: 3,  label: '3小时',  points: 36 },
        '6h':  { hours: 6,  label: '6小时',  points: 72 },
        '12h': { hours: 12, label: '12小时', points: 144 },
        '24h': { hours: 24, label: '24小时', points: 288 }
    };

    constructor(options) {
        this.canvasId = options.canvasId;
        this.legendId = options.legendId;
        this.timeRangeSelectorId = options.timeRangeSelectorId || null;  // 新增：时间选择器容器ID
        this.players = options.players || [];
        this.updateInterval = options.updateInterval || 300000;  // 默认5分钟更新（匹配CGM数据）
        
        // 时间范围设置 - 从 localStorage 读取或使用默认值
        const savedRange = localStorage.getItem('glucose_chart_time_range') || '3h';
        this.currentTimeRange = savedRange;
        this.maxPoints = GlucoseChart.TIME_RANGES[savedRange]?.points || 36;
        
        this.chart = null;
        this.historyData = {};  // playerId -> [{value, datetime}]
        this.updateTimer = null;
        this.isLoading = false;  // 防止重复加载
        
        // 初始化历史数据
        this.players.forEach(p => {
            this.historyData[p.id] = [];
        });
    }

    /**
     * 初始化图表
     */
    init() {
        this.renderTimeRangeSelector();
        this.renderLegend();
        this.createChart();
    }

    /**
     * 渲染时间范围选择器
     */
    renderTimeRangeSelector() {
        const container = document.getElementById(this.timeRangeSelectorId);
        if (!container) return;
        
        const buttons = Object.entries(GlucoseChart.TIME_RANGES).map(([key, range]) => {
            const isActive = key === this.currentTimeRange;
            return `<button 
                class="time-range-btn ${isActive ? 'active' : ''}" 
                data-range="${key}"
                title="显示最近${range.label}的数据"
            >${range.label}</button>`;
        }).join('');
        
        container.innerHTML = `
            <div class="time-range-selector">
                ${buttons}
            </div>
        `;
        
        // 绑定点击事件
        container.querySelectorAll('.time-range-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const range = e.target.dataset.range;
                this.setTimeRange(range);
            });
        });
    }

    /**
     * 设置时间范围
     * @param {string} rangeKey - 时间范围键名 ('3h', '6h', '12h', '24h')
     */
    async setTimeRange(rangeKey) {
        if (this.isLoading) return;
        
        const range = GlucoseChart.TIME_RANGES[rangeKey];
        if (!range) {
            console.warn('无效的时间范围:', rangeKey);
            return;
        }
        
        this.currentTimeRange = rangeKey;
        this.maxPoints = range.points;
        
        // 保存到 localStorage
        localStorage.setItem('glucose_chart_time_range', rangeKey);
        
        // 更新按钮状态
        const container = document.getElementById(this.timeRangeSelectorId);
        if (container) {
            container.querySelectorAll('.time-range-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.range === rangeKey);
            });
        }
        
        // 重新加载数据
        await this.loadHistoryFromAPI();
    }

    /**
     * 获取当前时间范围配置
     */
    getTimeRange() {
        return {
            key: this.currentTimeRange,
            ...GlucoseChart.TIME_RANGES[this.currentTimeRange]
        };
    }

    /**
     * 从 API 加载历史数据（实时模式）
     */
    async loadHistoryFromAPI() {
        if (this.isLoading) return false;
        
        this.isLoading = true;
        
        // 显示加载状态
        this.showLoadingState(true);
        
        try {
            const range = GlucoseChart.TIME_RANGES[this.currentTimeRange];
            const minutes = range.hours * 60;
            const maxCount = range.points;
            
            const response = await fetch(`/api/pk/history?minutes=${minutes}&max_count=${maxCount}`);
            const result = await response.json();
            
            if (result.success && result.players) {
                // 清空当前数据
                this.clear();
                
                // 收集所有时间点（使用时间戳作为key，确保正确排序和对齐）
                const allTimestamps = new Set();
                const playerDataMap = {};
                
                result.players.forEach(player => {
                    if (player.success && player.data) {
                        playerDataMap[player.user_id] = {};
                        // 数据是倒序的（最新的在前），需要反转
                        const sortedData = [...player.data].reverse();
                        sortedData.forEach(reading => {
                            const time = new Date(reading.datetime);
                            // 将时间对齐到5分钟边界（CGM数据通常每5分钟一次）
                            const alignedTime = this.alignToInterval(time, 5);
                            const timestamp = alignedTime.getTime();
                            allTimestamps.add(timestamp);
                            playerDataMap[player.user_id][timestamp] = reading.value;
                        });
                    }
                });
                
                // 按时间戳排序
                const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);
                
                // 生成显示用的时间标签
                const timeLabels = sortedTimestamps.map(ts => 
                    this.formatTimeLabel(new Date(ts))
                );
                
                // 填充图表数据
                this.chart.data.labels = timeLabels;
                
                this.players.forEach((player, index) => {
                    const data = sortedTimestamps.map(ts => 
                        playerDataMap[player.id]?.[ts] ?? null
                    );
                    this.chart.data.datasets[index].data = data;
                    this.historyData[player.id] = data.filter(v => v !== null).map((value, i) => ({
                        value,
                        time: timeLabels[i]
                    }));
                });
                
                // 根据数据量调整X轴标签数量
                this.updateXAxisTicks();
                
                this.chart.update('none');
                this.isLoading = false;
                this.showLoadingState(false);
                return true;
            }
            this.isLoading = false;
            this.showLoadingState(false);
            return false;
        } catch (e) {
            console.error('加载历史数据失败:', e);
            this.isLoading = false;
            this.showLoadingState(false);
            return false;
        }
    }

    /**
     * 格式化时间标签（根据时间范围调整格式）
     */
    formatTimeLabel(date) {
        const range = GlucoseChart.TIME_RANGES[this.currentTimeRange];
        
        if (range.hours <= 6) {
            // 6小时以内：只显示 HH:mm
            return date.toLocaleTimeString('zh-CN', { 
                hour: '2-digit', 
                minute: '2-digit'
            });
        } else {
            // 超过6小时：显示 MM-DD HH:mm
            return date.toLocaleString('zh-CN', {
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            }).replace(/\//g, '-');
        }
    }

    /**
     * 将时间对齐到指定分钟间隔（用于合并不同玩家的数据点）
     * 例如：11:03 和 11:04 都会对齐到 11:05（如果间隔是5分钟）
     */
    alignToInterval(date, intervalMinutes) {
        const ms = date.getTime();
        const intervalMs = intervalMinutes * 60 * 1000;
        // 向下取整到最近的间隔
        const aligned = Math.floor(ms / intervalMs) * intervalMs;
        return new Date(aligned);
    }

    /**
     * 根据数据量调整X轴标签数量
     */
    updateXAxisTicks() {
        if (!this.chart) return;
        
        const range = GlucoseChart.TIME_RANGES[this.currentTimeRange];
        let maxTicks;
        
        // 根据时间范围设置合适的标签数量
        switch(this.currentTimeRange) {
            case '3h':  maxTicks = 8;  break;
            case '6h':  maxTicks = 8;  break;
            case '12h': maxTicks = 8; break;
            case '24h': maxTicks = 8; break;
            default:    maxTicks = 8;
        }
        
        this.chart.options.scales.x.ticks.maxTicksLimit = maxTicks;
    }

    /**
     * 显示/隐藏加载状态
     */
    showLoadingState(isLoading) {
        const canvas = document.getElementById(this.canvasId);
        if (!canvas) return;
        
        const container = canvas.parentElement;
        
        if (isLoading) {
            // 添加加载遮罩
            if (!container.querySelector('.chart-loading')) {
                const overlay = document.createElement('div');
                overlay.className = 'chart-loading';
                overlay.innerHTML = '<div class="loading-spinner"></div><span>加载中...</span>';
                container.style.position = 'relative';
                container.appendChild(overlay);
            }
        } else {
            // 移除加载遮罩
            const overlay = container.querySelector('.chart-loading');
            if (overlay) {
                overlay.remove();
            }
        }
    }

    /**
     * 渲染图例
     */
    renderLegend() {
        const container = document.getElementById(this.legendId);
        if (!container) return;
        
        // 不同的线条样式标记
        const lineMarkers = ['●', '■', '▲', '★'];
        
        container.innerHTML = this.players.map((p, index) => `
            <div class="legend-item">
                <span style="color: ${p.color}; font-size: 8px; margin-right: 2px;">${lineMarkers[index % lineMarkers.length]}</span>
                <div class="legend-line" style="
                    width: 20px; 
                    height: 3px; 
                    background: ${p.color};
                    border-radius: 2px;
                    ${index % 2 === 1 ? 'background: repeating-linear-gradient(90deg, ' + p.color + ' 0px, ' + p.color + ' 6px, transparent 6px, transparent 10px);' : ''}
                "></div>
                <img src="${p.avatar}" class="legend-avatar" alt="${p.name}">
                <span>${p.name}</span>
            </div>
        `).join('');
    }

    /**
     * 创建 Chart.js 图表
     */
    createChart() {
        const canvas = document.getElementById(this.canvasId);
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // 不同的线条样式用于区分玩家（色盲友好）
        const lineStyles = [
            { borderDash: [], pointStyle: 'circle' },       // 实线 + 圆点
            { borderDash: [8, 4], pointStyle: 'rect' },     // 长虚线 + 方块
            { borderDash: [4, 4], pointStyle: 'triangle' }, // 短虚线 + 三角
            { borderDash: [12, 4, 4, 4], pointStyle: 'star' }, // 点划线 + 星形
        ];
        
        // 根据数据点数量调整点的大小
        const pointRadius = this.maxPoints > 100 ? 1 : 2;
        
        const datasets = this.players.map((player, index) => ({
            label: player.name,
            data: [],
            borderColor: player.color,
            backgroundColor: player.color + '20',
            borderWidth: this.maxPoints > 100 ? 2 : 3,  // 数据多时线条稍细
            fill: false,
            tension: 0.3,
            pointRadius: pointRadius,
            pointHoverRadius: 7,
            spanGaps: true,
            // 不同线条样式
            borderDash: lineStyles[index % lineStyles.length].borderDash,
            pointStyle: lineStyles[index % lineStyles.length].pointStyle,
        }));
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: (item) => `${item.dataset.label}: ${item.raw} mmol/L`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { 
                            font: { size: 10 },
                            maxTicksLimit: 8,
                            maxRotation: 45,
                            minRotation: 0
                        }
                    },
                    y: {
                        min: 2.8,
                        max: 16.7,
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: { font: { size: 10 } }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            },
            plugins: [{
                // 绘制参考区域
                beforeDraw: (chart) => {
                    const ctx = chart.ctx;
                    const yAxis = chart.scales.y;
                    const xAxis = chart.scales.x;
                    
                    // 正常区域 - 浅绿 (3.9-7.8)
                    ctx.fillStyle = 'rgba(76, 175, 80, 0.1)';
                    const y39 = yAxis.getPixelForValue(3.9);
                    const y78 = yAxis.getPixelForValue(7.8);
                    ctx.fillRect(xAxis.left, y78, xAxis.width, y39 - y78);
                    
                    // 警告区域 - 浅黄 (7.8-11.1)
                    ctx.fillStyle = 'rgba(255, 152, 0, 0.1)';
                    const y111 = yAxis.getPixelForValue(11.1);
                    ctx.fillRect(xAxis.left, y111, xAxis.width, y78 - y111);
                    
                    // 危险区域 - 浅红 (>11.1)
                    ctx.fillStyle = 'rgba(244, 67, 54, 0.1)';
                    const yMax = yAxis.getPixelForValue(16.7);
                    ctx.fillRect(xAxis.left, yMax, xAxis.width, y111 - yMax);
                    
                    // 低血糖区域 - 浅蓝 (<3.9)
                    ctx.fillStyle = 'rgba(33, 150, 243, 0.1)';
                    const yMin = yAxis.getPixelForValue(2.8);
                    ctx.fillRect(xAxis.left, y39, xAxis.width, yMin - y39);
                }
            }]
        });
    }

    /**
     * 添加数据点
     * @param {Object} playersData - { playerId: value, ... }
     */
    addDataPoint(playersData) {
        if (!this.chart) return;
        
        const now = new Date();
        const timeLabel = this.formatTimeLabel(now);
        
        // 添加时间标签
        this.chart.data.labels.push(timeLabel);
        if (this.chart.data.labels.length > this.maxPoints) {
            this.chart.data.labels.shift();
        }
        
        // 更新每个玩家的数据
        this.players.forEach((player, index) => {
            const value = playersData[player.id];
            if (value !== undefined) {
                // 保存到历史
                this.historyData[player.id].push({ value, time: timeLabel });
                if (this.historyData[player.id].length > this.maxPoints) {
                    this.historyData[player.id].shift();
                }
                
                // 更新图表
                this.chart.data.datasets[index].data.push(value);
                if (this.chart.data.datasets[index].data.length > this.maxPoints) {
                    this.chart.data.datasets[index].data.shift();
                }
            }
        });
        
        this.chart.update('none');
    }

    /**
     * 清空图表数据
     */
    clear() {
        if (!this.chart) return;
        
        this.chart.data.labels = [];
        this.chart.data.datasets.forEach(ds => ds.data = []);
        this.players.forEach(p => {
            this.historyData[p.id] = [];
        });
        this.chart.update('none');
    }

    /**
     * 更新玩家列表
     */
    updatePlayers(players) {
        this.players = players;
        players.forEach(p => {
            if (!this.historyData[p.id]) {
                this.historyData[p.id] = [];
            }
        });
        this.renderLegend();
        
        // 重新创建图表
        if (this.chart) {
            this.chart.destroy();
        }
        this.createChart();
    }

    /**
     * 销毁图表
     */
    destroy() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
    }
}

// 导出
window.GlucoseChart = GlucoseChart;
