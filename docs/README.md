# 多 Agent 数据分析平台 - 文档中心

## 快速导航

| 分类 | 说明 | 文档 |
|-----|------|------|
| **架构 V2** | Two-Layer (Skills + MCP) | [查看 →](ARCHITECTURE_V2.md) |
| **迁移指南** | V1 → V2 迁移 | [查看 →](MIGRATION_GUIDE.md) |
| **NL 分析** | 自然语言驱动分析 | [查看 →](NL_DRIVEN_ANALYSIS.md) |
| **API 参考** | REST API + WebSocket | [查看 →](api/REFERENCE.md) |
| **架构设计** | 系统架构和技术选型 | [查看 →](architecture/) |
| **部署指南** | 部署和配置 | [查看 →](deployment/) |

---

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- Conda (推荐)
- Docker (可选，用于 PostgreSQL)

### 一键启动

```bash
# 1. 启动 PostgreSQL (Docker)
docker-compose up -d postgres

# 2. 启动后端 (新终端)
conda activate multi_agent
python -m uvicorn backend.api.main:app --reload --port 8000

# 3. 启动前端 (新终端)
cd frontend && npm run dev
```

### 访问地址

| 服务 | 地址 |
|-----|------|
| **前端界面** | http://localhost:3000 |
| **后端 API** | http://localhost:8000 |
| **API 文档** | http://localhost:8000/docs |

### 使用流程

1. 打开 http://localhost:3000
2. 点击 **"+"** 创建新会话
3. 上传数据文件 (CSV/Excel/JSON)
4. 输入分析需求，AI 自动分析

---

## 架构 V2 (2026-04 更新)

### Two-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                     │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│   │  AGENT.md   │    │  SKILL.md   │    │ MCP Server  │         │
│   │ (Knowledge) │    │ (Knowledge) │    │ (Execution) │         │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│          │                  │                  │                       │
│          └──────────────────┼──────────────────┘                       │
│                             │                                          │
│                     ┌───────▼───────┐                                  │
│                     │  MCP Client   │                                  │
│                     │ (Local/HTTP)  │                                  │
│                     └───────────────┘                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 组件状态

| 组件 | V1 (Legacy) | V2 (New) | 说明 |
|------|-------------|----------|------|
| Agents | ✅ Active | ✅ Ready | V2 从 AGENT.md 加载 |
| Skills | ✅ Active | ✅ Active | 动态发现已实现 |
| MCP Servers | N/A | ✅ Active | mcp-data, mcp-chart |
| Skill Selector | N/A | ✅ Active | 意图 → Skill 映射 |

### 目录结构

```
├── agents/                    # Agent 定义 (V2)
│   ├── AGENTS.md             # 注册表
│   └── */AGENT.md            # 各 Agent 定义
│
├── skills/builtin/           # Skill 定义
│   └── */SKILL.md + generate.py
│
├── mcp_servers/              # MCP 服务器
│   ├── mcp_data/             # 数据处理
│   └── mcp_chart/            # 图表生成
│
└── src/
    ├── agents/               # Agent 实现 (V1 + V2)
    ├── skills/               # Skill 注册表
    └── mcp/                  # MCP 客户端
```

---

## 当前版本功能

### 前端 UI (Phase 2.2 已完成)

| 组件 | 功能 |
|------|------|
| **ChatInterface** | Markdown 渲染 + 代码语法高亮 + 复制按钮 |
| **Sidebar** | 会话搜索 + 日期分组 + 批量管理 |
| **RightPanel** | 代码高亮 + 图表预览 + 报告渲染 |

### 后端架构

| 模块 | 状态 |
|------|------|
| 8 个核心 Agent | ✅ 完成 |
| 13 个 Skill 体系 | ✅ 完成 |
| PostgreSQL Checkpointer | ✅ 完成 |
| WebSocket 实时通信 | ✅ 完成 |

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
```

### 会话不存在
现已自动修复 - 系统会自动创建缺失的会话

---

## 文档分类

### API 参考
- [API 参考文档](api/REFERENCE.md) - REST API + WebSocket 完整文档

### 架构设计
- [全栈架构进度](architecture/fullstack-progress.md) - FastAPI + Next.js 架构

### 部署指南
- [部署指南](deployment/DEPLOYMENT.md) - 多种部署方式

### 开发指南
- [后端验证指南](development/backend-validation-guide.md) - 功能验证清单

### 技能系统
- [技能文档](skills/skills.md) - 技能体系核心
- [重构总结](skills/skills-refactoring-summary.md) - 技能重构记录

### 解决方案
- [生产解决方案](solutions/production-solutions.md) - 技术选型对比

---

## 技能目录结构

```
skills/
├── builtin/              # 内置技能
│   ├── describe_statistics/
│   ├── distribution_analysis/
│   └── ...
├── anthropics/           # Claude 官方技能
└── examples/            # 示例技能
```

---

*最后更新：2026-04-04*
