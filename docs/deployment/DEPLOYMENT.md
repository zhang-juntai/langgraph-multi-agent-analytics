# 部署指南

## 部署方式概览

| 方式 | 适用场景 | 复杂度 | 成本 |
|------|---------|--------|------|
| **本地运行** | 开发/演示 | ⭐ | 免费 |
| **Docker 开发环境** | 本地测试 | ⭐⭐ | 免费 |
| **Docker 生产环境** | 生产部署 | ⭐⭐⭐ | 中 |
| **云服务器** | 生产环境 | ⭐⭐⭐ | 中 |

---

## 方式 1：本地运行（开发）

### 环境要求
- Python 3.10+
- Node.js 18+
- Docker (可选，用于 PostgreSQL)

### 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/aspiring0/multi-agent-data-analysis.git
cd multi-agent-data-analysis

# 2. 启动 PostgreSQL (Docker)
docker-compose up -d postgres

# 3. 启动后端 (新终端)
conda activate multi_agent
pip install -r requirements.txt
python -m uvicorn backend.api.main:app --reload --port 8000

# 4. 启动前端 (新终端)
cd frontend && npm install && npm run dev
```

### 访问地址

| 服务 | 地址 |
|-----|------|
| 前端界面 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

---

## 方式 2：Docker 开发环境

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

## 方式 3：Docker 生产部署

### 架构

```
                    ┌─────────────┐
                    │   Nginx     │ :80
                    │ (Reverse    │
                    │  Proxy)     │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  Frontend   │ │   Backend   │ │  PostgreSQL │
    │  (Next.js)  │ │  (FastAPI)  │ │   :5432     │
    │   :3000     │ │   :8000     │ │             │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### 部署步骤

```bash
# 1. 配置环境变量
cat > .env.prod << EOF
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-chat
LOG_LEVEL=INFO
NEXT_PUBLIC_WS_URL=ws://your-domain.com
NEXT_PUBLIC_API_URL=http://your-domain.com
EOF

# 2. 构建并启动
docker-compose -f docker-compose.prod.yml up -d --build

# 3. 健康检查
./scripts/health_check.sh

# 4. 查看日志
docker-compose -f docker-compose.prod.yml logs -f
```

### Docker 文件说明

| 文件 | 用途 |
|------|------|
| `Dockerfile.backend` | FastAPI 后端镜像 |
| `Dockerfile.frontend` | Next.js 前端镜像 (多阶段构建) |
| `docker-compose.yml` | 开发环境配置 |
| `docker-compose.prod.yml` | 生产环境配置 (含 Nginx) |
| `nginx.conf` | Nginx 反向代理配置 |
| `.dockerignore` | Docker 构建排除文件 |

---

## 方式 4：云服务器部署

### 推荐配置

| 资源 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 磁盘 | 20 GB | 50 GB SSD |
| 系统 | Ubuntu 22.04 | Ubuntu 22.04 |

### 部署步骤

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. 克隆代码
git clone https://github.com/aspiring0/multi-agent-data-analysis.git
cd multi-agent-data-analysis

# 3. 配置环境变量
cp .env.example .env.prod
# 编辑 .env.prod，填入配置

# 4. 启动生产环境
docker-compose -f docker-compose.prod.yml up -d --build

# 5. 验证部署
curl http://localhost/health
```

### HTTPS 配置 (推荐)

```bash
# 使用 Certbot 获取 SSL 证书
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

---

## 健康检查与监控

### 手动检查

```bash
# 运行健康检查脚本
./scripts/health_check.sh

# 或手动检查各服务
curl http://localhost:8000/health           # 后端
curl http://localhost:8000/health/detailed  # 详细状态
curl http://localhost:3000                  # 前端
curl http://localhost/health                # Nginx
```

### 详细健康检查端点

`GET /health/detailed` 返回:

```json
{
  "status": "healthy",
  "timestamp": "2026-04-04T12:00:00",
  "components": {
    "database": {"status": "ok", "type": "sqlite"},
    "postgres": {"status": "ok"},
    "llm": {"status": "configured", "model": "deepseek-chat"},
    "disk": {"status": "ok", "free_gb": 50.5, "used_percent": 45.2}
  }
}
```

---

## 生产化清单

### 安全
- [x] API Key 通过环境变量注入
- [x] 沙箱已拦截危险操作
- [x] HITL 审批已启用
- [x] Nginx 安全头配置
- [ ] HTTPS 证书配置
- [ ] 防火墙规则设置

### 可靠性
- [x] PostgreSQL Checkpointer 持久化
- [x] WebSocket 指数退避重连
- [x] Docker 健康检查
- [x] 自动重启 (restart: unless-stopped)
- [ ] 定期数据库备份

### 性能
- [x] 前端静态资源缓存
- [x] Gzip 压缩
- [x] 多 worker (uvicorn --workers 4)
- [ ] CDN 配置 (可选)

### 监控
- [x] 健康检查端点
- [x] 结构化日志
- [ ] Prometheus 指标 (可选)
- [ ] Grafana 仪表板 (可选)

---

## 环境变量参考

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | ✅ | - | DeepSeek API 密钥 |
| `DEEPSEEK_MODEL` | - | `deepseek-chat` | 模型名称 |
| `POSTGRES_URI` | - | `postgresql://...` | PostgreSQL 连接串 |
| `CHECKPOINTER_TYPE` | - | `postgres` | 检查点存储类型 |
| `LOG_LEVEL` | - | `INFO` | 日志级别 |
| `NEXT_PUBLIC_WS_URL` | - | `ws://localhost` | WebSocket 地址 |
| `NEXT_PUBLIC_API_URL` | - | `http://localhost` | API 地址 |

---

## 常见问题

### 端口被占用
```bash
# 查找并终止占用端口的进程
netstat -ano | findstr :3000
taskkill /PID <进程ID> /F
```

### PostgreSQL 连接失败
```bash
docker-compose restart postgres
docker-compose logs postgres
```

### 前端构建失败
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run build
```

---

*最后更新: 2026-04-04*
