/**
 * 城堡攻防游戏引擎
 * 根据血糖值决定城堡的建设/攻击状态
 */

class CastleGame {
    constructor(canvasId, playerId, playerInfo) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.playerId = playerId;
        this.playerInfo = playerInfo;
        
        // 加载头像图片
        this.avatarImage = new Image();
        this.avatarImage.src = playerInfo.avatar;
        this.avatarLoaded = false;
        this.avatarImage.onload = () => {
            this.avatarLoaded = true;
        };
        
        // 城堡状态
        this.state = {
            health: 100,           // 城堡生命值 0-100
            level: 1,              // 城堡等级 1-5
            buildProgress: 0,      // 建设进度 0-100
            isUnderAttack: false,  // 是否被攻击
            attackIntensity: 0,    // 攻击强度 0-1
            particles: [],         // 粒子效果
            lastGlucose: 5.6       // 上次血糖值 (mmol/L)
        };
        
        // 动画帧 ID
        this.animationId = null;
        
        // 设置 canvas 尺寸
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }

    resize() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this.width = this.canvas.width;
        this.height = this.canvas.height;
    }

    /**
     * 根据血糖值更新城堡状态 (输入 mmol/L)
     */
    updateWithGlucose(glucoseValue) {
        const oldHealth = this.state.health;
        this.state.lastGlucose = glucoseValue;
        
        if (glucoseValue < 3.9) {
            // 低血糖 - 资源不足，建设缓慢，轻微损耗
            this.state.isUnderAttack = false;
            this.state.attackIntensity = 0;
            this.state.buildProgress += 0.2;
            this.state.health = Math.max(0, this.state.health - 0.1);
            this.addParticle('tired');
        } 
        else if (glucoseValue <= 7.8) {
            // 正常范围 - 快速建设
            this.state.isUnderAttack = false;
            this.state.attackIntensity = 0;
            this.state.buildProgress += 1;
            this.state.health = Math.min(100, this.state.health + 0.3);
            
            if (Math.random() < 0.1) {
                this.addParticle('build');
            }
        } 
        else if (glucoseValue <= 10.0) {
            // 偏高 - 轻微攻击
            this.state.isUnderAttack = true;
            this.state.attackIntensity = 0.3;
            this.state.health = Math.max(0, this.state.health - 0.3);
            
            if (Math.random() < 0.15) {
                this.addParticle('attack');
            }
        } 
        else if (glucoseValue <= 11.1) {
            // 警告 - 中等攻击
            this.state.isUnderAttack = true;
            this.state.attackIntensity = 0.6;
            this.state.health = Math.max(0, this.state.health - 0.6);
            
            if (Math.random() < 0.25) {
                this.addParticle('attack');
            }
        } 
        else {
            // 危险 - 猛烈攻击
            this.state.isUnderAttack = true;
            this.state.attackIntensity = 1;
            this.state.health = Math.max(0, this.state.health - 1);
            
            if (Math.random() < 0.4) {
                this.addParticle('attack');
                this.addParticle('fire');
            }
        }
        
        // 检查升级
        if (this.state.buildProgress >= 100) {
            this.state.buildProgress = 0;
            if (this.state.level < 5) {
                this.state.level++;
                this.addParticle('levelup');
            }
        }
        
        return this.state;
    }

    /**
     * 添加粒子效果
     */
    addParticle(type) {
        const particle = {
            type,
            x: this.width / 2 + (Math.random() - 0.5) * 100,
            y: this.height * 0.5,
            vx: (Math.random() - 0.5) * 3,
            vy: -Math.random() * 3 - 1,
            life: 1,
            maxLife: 60 + Math.random() * 30
        };
        
        if (type === 'attack') {
            particle.x = Math.random() * this.width;
            particle.y = 0;
            particle.vy = Math.random() * 3 + 2;
            particle.vx = (Math.random() - 0.5) * 2;
        }
        
        if (type === 'fire') {
            particle.y = this.height * 0.6;
            particle.vy = -Math.random() * 2 - 1;
        }
        
        this.state.particles.push(particle);
    }

    /**
     * 更新粒子
     */
    updateParticles() {
        this.state.particles = this.state.particles.filter(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.life -= 1 / p.maxLife;
            
            if (p.type === 'attack') {
                p.vy += 0.1; // 重力
            }
            
            return p.life > 0;
        });
    }

    /**
     * 绘制城堡
     */
    draw() {
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        
        // 清空画布
        ctx.clearRect(0, 0, w, h);
        
        // 绘制天空背景
        this.drawSky();
        
        // 绘制地面
        this.drawGround();
        
        // 绘制城堡
        this.drawCastle();
        
        // 绘制粒子效果
        this.drawParticles();
        
        // 绘制 UI
        this.drawUI();
    }

    drawSky() {
        const ctx = this.ctx;
        const h = this.height;
        const w = this.width;
        
        // 根据攻击强度改变天空颜色
        let skyColor1, skyColor2;
        if (this.state.isUnderAttack) {
            const intensity = this.state.attackIntensity;
            skyColor1 = `rgb(${50 + intensity * 100}, ${20 + intensity * 20}, ${40})`;
            skyColor2 = `rgb(${100 + intensity * 50}, ${50}, ${50})`;
        } else {
            skyColor1 = '#1a1a2e';
            skyColor2 = '#16213e';
        }
        
        const gradient = ctx.createLinearGradient(0, 0, 0, h * 0.7);
        gradient.addColorStop(0, skyColor1);
        gradient.addColorStop(1, skyColor2);
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, w, h * 0.7);
        
        // 星星
        if (!this.state.isUnderAttack) {
            ctx.fillStyle = 'rgba(255,255,255,0.5)';
            for (let i = 0; i < 20; i++) {
                const x = (i * 37) % w;
                const y = (i * 23) % (h * 0.5);
                ctx.beginPath();
                ctx.arc(x, y, 1, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    drawGround() {
        const ctx = this.ctx;
        const h = this.height;
        const w = this.width;
        
        // 草地
        const gradient = ctx.createLinearGradient(0, h * 0.7, 0, h);
        gradient.addColorStop(0, '#2d5016');
        gradient.addColorStop(1, '#1f3a0f');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, h * 0.7, w, h * 0.3);
    }

    drawCastle() {
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const level = this.state.level;
        const health = this.state.health;
        
        const baseY = h * 0.7;
        const centerX = w / 2;
        
        // 城堡尺寸随等级增加
        const castleWidth = 80 + level * 20;
        const castleHeight = 60 + level * 15;
        const towerHeight = 80 + level * 20;
        
        // 城墙颜色（根据生命值变化）
        const healthRatio = health / 100;
        const wallR = Math.floor(139 + (100 - health));
        const wallG = Math.floor(119 * healthRatio);
        const wallB = Math.floor(101 * healthRatio);
        const wallColor = `rgb(${wallR}, ${wallG}, ${wallB})`;
        
        // 抖动效果（被攻击时）
        let shakeX = 0, shakeY = 0;
        if (this.state.isUnderAttack) {
            shakeX = (Math.random() - 0.5) * 4 * this.state.attackIntensity;
            shakeY = (Math.random() - 0.5) * 2 * this.state.attackIntensity;
        }
        
        ctx.save();
        ctx.translate(shakeX, shakeY);
        
        // 主城墙
        ctx.fillStyle = wallColor;
        ctx.fillRect(
            centerX - castleWidth / 2, 
            baseY - castleHeight, 
            castleWidth, 
            castleHeight
        );
        
        // 城垛
        const battlementWidth = 15;
        const battlementHeight = 15;
        const numBattlements = Math.floor(castleWidth / (battlementWidth * 1.5));
        for (let i = 0; i < numBattlements; i++) {
            const x = centerX - castleWidth / 2 + i * (battlementWidth * 1.5) + 5;
            ctx.fillRect(x, baseY - castleHeight - battlementHeight, battlementWidth, battlementHeight);
        }
        
        // 左塔
        if (level >= 2) {
            ctx.fillRect(
                centerX - castleWidth / 2 - 20, 
                baseY - towerHeight, 
                30, 
                towerHeight
            );
            // 塔顶
            ctx.beginPath();
            ctx.moveTo(centerX - castleWidth / 2 - 25, baseY - towerHeight);
            ctx.lineTo(centerX - castleWidth / 2 - 5, baseY - towerHeight - 25);
            ctx.lineTo(centerX - castleWidth / 2 + 15, baseY - towerHeight);
            ctx.fill();
        }
        
        // 右塔
        if (level >= 2) {
            ctx.fillRect(
                centerX + castleWidth / 2 - 10, 
                baseY - towerHeight, 
                30, 
                towerHeight
            );
            // 塔顶
            ctx.beginPath();
            ctx.moveTo(centerX + castleWidth / 2 - 15, baseY - towerHeight);
            ctx.lineTo(centerX + castleWidth / 2 + 5, baseY - towerHeight - 25);
            ctx.lineTo(centerX + castleWidth / 2 + 25, baseY - towerHeight);
            ctx.fill();
        }
        
        // 中央塔（等级3+）
        if (level >= 3) {
            const mainTowerHeight = towerHeight + 30;
            ctx.fillRect(
                centerX - 20, 
                baseY - castleHeight - mainTowerHeight + 20, 
                40, 
                mainTowerHeight
            );
            // 塔顶
            ctx.beginPath();
            ctx.moveTo(centerX - 25, baseY - castleHeight - mainTowerHeight + 20);
            ctx.lineTo(centerX, baseY - castleHeight - mainTowerHeight - 20);
            ctx.lineTo(centerX + 25, baseY - castleHeight - mainTowerHeight + 20);
            ctx.fill();
        }
        
        // 大门
        ctx.fillStyle = '#4a3728';
        const gateWidth = 25 + level * 3;
        const gateHeight = 35 + level * 5;
        ctx.beginPath();
        ctx.moveTo(centerX - gateWidth / 2, baseY);
        ctx.lineTo(centerX - gateWidth / 2, baseY - gateHeight + 10);
        ctx.arc(centerX, baseY - gateHeight + 10, gateWidth / 2, Math.PI, 0);
        ctx.lineTo(centerX + gateWidth / 2, baseY);
        ctx.fill();
        
        // 旗帜（等级4+）
        if (level >= 4) {
            this.drawFlag(centerX, baseY - castleHeight - (level >= 3 ? towerHeight + 50 : 30));
        }
        
        // 护城河（等级5）
        if (level >= 5) {
            ctx.fillStyle = 'rgba(30, 100, 180, 0.6)';
            ctx.fillRect(centerX - castleWidth - 20, baseY, castleWidth * 2 + 40, 15);
        }
        
        // 裂缝效果（生命值低时）
        if (health < 50) {
            this.drawCracks(centerX, baseY, castleWidth, castleHeight, health);
        }
        
        ctx.restore();
    }

    drawFlag(x, y) {
        const ctx = this.ctx;
        const time = Date.now() / 200;
        
        // 旗杆
        ctx.strokeStyle = '#666';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x, y - 40);
        ctx.stroke();
        
        // 旗帜（飘动效果）
        ctx.fillStyle = this.playerInfo.color || '#e74c3c';
        ctx.beginPath();
        ctx.moveTo(x, y - 40);
        ctx.quadraticCurveTo(
            x + 15 + Math.sin(time) * 5, 
            y - 35 + Math.cos(time) * 2,
            x + 25 + Math.sin(time) * 3, 
            y - 30
        );
        ctx.quadraticCurveTo(
            x + 15 + Math.sin(time + 1) * 5, 
            y - 25 + Math.cos(time) * 2,
            x, 
            y - 20
        );
        ctx.fill();
    }

    drawCracks(centerX, baseY, castleWidth, castleHeight, health) {
        const ctx = this.ctx;
        ctx.strokeStyle = '#2a2a2a';
        ctx.lineWidth = 2;
        
        const numCracks = Math.floor((100 - health) / 15);
        for (let i = 0; i < numCracks; i++) {
            const startX = centerX - castleWidth / 2 + Math.random() * castleWidth;
            const startY = baseY - Math.random() * castleHeight;
            
            ctx.beginPath();
            ctx.moveTo(startX, startY);
            
            let x = startX, y = startY;
            for (let j = 0; j < 3; j++) {
                x += (Math.random() - 0.5) * 20;
                y += Math.random() * 15;
                ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
    }

    drawParticles() {
        const ctx = this.ctx;
        
        this.state.particles.forEach(p => {
            ctx.globalAlpha = p.life;
            
            if (p.type === 'build') {
                // 建设粒子 - 绿色星星
                ctx.fillStyle = '#4CAF50';
                ctx.beginPath();
                ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#8BC34A';
                ctx.font = '16px Arial';
                ctx.fillText('✨', p.x - 8, p.y + 5);
            } 
            else if (p.type === 'attack') {
                // 攻击粒子 - 火球
                ctx.fillStyle = '#f44336';
                ctx.beginPath();
                ctx.arc(p.x, p.y, 6, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#FF9800';
                ctx.beginPath();
                ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
                ctx.fill();
            } 
            else if (p.type === 'fire') {
                // 火焰粒子
                ctx.fillStyle = `rgba(255, ${Math.floor(100 + Math.random() * 100)}, 0, ${p.life})`;
                ctx.beginPath();
                ctx.arc(p.x, p.y, 5 + Math.random() * 3, 0, Math.PI * 2);
                ctx.fill();
            } 
            else if (p.type === 'levelup') {
                // 升级粒子
                ctx.fillStyle = '#FFD700';
                ctx.font = '20px Arial';
                ctx.fillText('⬆️', p.x - 10, p.y);
            } 
            else if (p.type === 'tired') {
                // 疲劳粒子
                ctx.fillStyle = '#9E9E9E';
                ctx.font = '14px Arial';
                ctx.fillText('💤', p.x - 7, p.y);
            }
            
            ctx.globalAlpha = 1;
        });
    }

    drawUI() {
        const ctx = this.ctx;
        const w = this.width;
        
        // 玩家名称和头像背景
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.beginPath();
        ctx.roundRect(10, 10, 110, 35, 10);
        ctx.fill();
        
        // 绘制头像图片
        if (this.avatarLoaded) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(30, 27, 12, 0, Math.PI * 2);
            ctx.closePath();
            ctx.clip();
            ctx.drawImage(this.avatarImage, 18, 15, 24, 24);
            ctx.restore();
        }
        
        // 玩家名称
        ctx.fillStyle = 'white';
        ctx.font = '14px Arial';
        ctx.fillText(this.playerInfo.name || 'Player', 48, 33);
        
        // 生命条
        const barWidth = 100;
        const barHeight = 8;
        const barX = 10;
        const barY = 50;
        
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.fillRect(barX, barY, barWidth, barHeight);
        
        const healthWidth = (this.state.health / 100) * barWidth;
        const healthColor = this.state.health > 60 ? '#4CAF50' : 
                           this.state.health > 30 ? '#FF9800' : '#f44336';
        ctx.fillStyle = healthColor;
        ctx.fillRect(barX, barY, healthWidth, barHeight);
        
        ctx.fillStyle = 'white';
        ctx.font = '10px Arial';
        ctx.fillText(`HP: ${Math.round(this.state.health)}%`, barX, barY + 20);
        
        // 等级
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.roundRect(w - 50, 10, 40, 35, 10);
        ctx.fill();
        
        ctx.fillStyle = '#FFD700';
        ctx.font = '12px Arial';
        ctx.fillText('Lv.', w - 45, 25);
        ctx.font = 'bold 16px Arial';
        ctx.fillText(this.state.level, w - 35, 40);
        
        // 建设进度条（正常状态时显示）
        if (!this.state.isUnderAttack && this.state.lastGlucose >= 3.9 && this.state.lastGlucose <= 7.8) {
            ctx.fillStyle = 'rgba(0,0,0,0.5)';
            ctx.fillRect(barX, barY + 25, barWidth, 6);
            
            ctx.fillStyle = '#2196F3';
            ctx.fillRect(barX, barY + 25, (this.state.buildProgress / 100) * barWidth, 6);
            
            ctx.fillStyle = 'white';
            ctx.font = '10px Arial';
            ctx.fillText(`建设: ${Math.round(this.state.buildProgress)}%`, barX, barY + 45);
        }
        
        // 状态提示
        let statusText = '';
        let statusColor = 'white';
        
        if (this.state.lastGlucose < 3.9) {
            statusText = '⚡ 资源不足';
            statusColor = '#2196F3';
        } else if (this.state.lastGlucose <= 7.8) {
            statusText = '🔨 建设中...';
            statusColor = '#4CAF50';
        } else if (this.state.lastGlucose <= 10.0) {
            statusText = '⚔️ 遭受攻击';
            statusColor = '#FF9800';
        } else {
            statusText = '🔥 猛烈攻击!';
            statusColor = '#f44336';
        }
        
        ctx.fillStyle = statusColor;
        ctx.font = '12px Arial';
        ctx.fillText(statusText, 10, this.height - 15);
    }

    /**
     * 开始动画循环
     */
    start() {
        const animate = () => {
            this.updateParticles();
            this.draw();
            this.animationId = requestAnimationFrame(animate);
        };
        animate();
    }

    /**
     * 停止动画
     */
    stop() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    /**
     * 重置游戏状态
     */
    reset() {
        this.state = {
            health: 100,
            level: 1,
            buildProgress: 0,
            isUnderAttack: false,
            attackIntensity: 0,
            particles: [],
            lastGlucose: 5.6  // mmol/L
        };
    }

    /**
     * 获取当前状态
     */
    getState() {
        return { ...this.state };
    }
}

// 辅助方法：为 canvas context 添加 roundRect（如果不存在）
if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
        if (w < 2 * r) r = w / 2;
        if (h < 2 * r) r = h / 2;
        this.beginPath();
        this.moveTo(x + r, y);
        this.arcTo(x + w, y, x + w, y + h, r);
        this.arcTo(x + w, y + h, x, y + h, r);
        this.arcTo(x, y + h, x, y, r);
        this.arcTo(x, y, x + w, y, r);
        this.closePath();
        return this;
    };
}

// 导出
window.CastleGame = CastleGame;
