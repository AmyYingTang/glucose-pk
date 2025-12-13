/**
 * 血糖曲线图组件
 * 可复用的多人血糖趋势图
 */

class GlucoseChart {
    constructor(options) {
        this.canvasId = options.canvasId;
        this.legendId = options.legendId;
        this.players = options.players || [];
        this.maxPoints = options.maxPoints || 36;  // 最多显示36个点（3小时，每5分钟1个）
        this.updateInterval = options.updateInterval || 300000;  // 默认5分钟更新（匹配CGM数据）
        
        this.chart = null;
        this.historyData = {};  // playerId -> [{value, datetime}]
        this.updateTimer = null;
        
        // 初始化历史数据
        this.players.forEach(p => {
            this.historyData[p.id] = [];
        });
    }

    /**
     * 初始化图表
     */
    init() {
        this.renderLegend();
        this.createChart();
    }

    /**
     * 从 API 加载历史数据（实时模式）
     */
    async loadHistoryFromAPI() {
        try {
            const response = await fetch('/api/pk/history?minutes=180&max_count=36');
            const result = await response.json();
            
            if (result.success && result.players) {
                // 清空当前数据
                this.clear();
                
                // 收集所有时间点
                const allTimes = new Set();
                const playerDataMap = {};
                
                result.players.forEach(player => {
                    if (player.success && player.data) {
                        playerDataMap[player.user_id] = {};
                        // 数据是倒序的（最新的在前），需要反转
                        const sortedData = [...player.data].reverse();
                        sortedData.forEach(reading => {
                            const time = new Date(reading.datetime);
                            const timeKey = time.toLocaleTimeString('zh-CN', { 
                                hour: '2-digit', 
                                minute: '2-digit'
                            });
                            allTimes.add(timeKey);
                            playerDataMap[player.user_id][timeKey] = reading.value;
                        });
                    }
                });
                
                // 按时间排序
                const sortedTimes = Array.from(allTimes).sort();
                
                // 填充图表数据
                this.chart.data.labels = sortedTimes;
                
                this.players.forEach((player, index) => {
                    const data = sortedTimes.map(time => 
                        playerDataMap[player.id]?.[time] ?? null
                    );
                    this.chart.data.datasets[index].data = data;
                    this.historyData[player.id] = data.filter(v => v !== null).map((value, i) => ({
                        value,
                        time: sortedTimes[i]
                    }));
                });
                
                this.chart.update('none');
                return true;
            }
            return false;
        } catch (e) {
            console.error('加载历史数据失败:', e);
            return false;
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
        
        const datasets = this.players.map((player, index) => ({
            label: player.name,
            data: [],
            borderColor: player.color,
            backgroundColor: player.color + '20',
            borderWidth: 3,
            fill: false,
            tension: 0.3,
            pointRadius: 2,
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
                            maxTicksLimit: 8
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
        const timeLabel = now.toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit'
        });
        
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
