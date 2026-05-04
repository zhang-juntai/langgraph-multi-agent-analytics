# 全栈架构 - 实施完成报告

## 项目状态: ✅ 完成

**架构改造已完成**，项目已从 Streamlit 单体架构迁移至 FastAPI + Next.js 全栈架构。

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面 (Next.js)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Sidebar    │  │   Chat      │  │ RightPanel  │              │
│  │  会话管理    │  │   界面      │  │  代码/图表   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket + REST API
┌──────────────────────────▼──────────────────────────────────────┐
│                    后端 API (FastAPI)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  /api/chat  │  │ /api/upload │  │ /api/sessions│              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    LangGraph Agent 系统                           │
│  ┌───────────────────────────────────────────────────────┐       │
│  │                  Coordinator (调度中心)                 │       │
│  │            意图识别 → 任务分类 → Agent 路由             │       │
│  └────┬───────┬────────┬─────────┬──────────┬────────────┘       │
│       │       │        │         │          │                    │
│       ▼       ▼        ▼         ▼          ▼                    │
│    Data     Data    Code Gen  Visualizer  Report                 │
│    Parser   Profiler   │          │        Writer                │
│       │       │    ┌───┴───┐  ┌───┴───┐                          │
│       │       │    │Debugger│  │Debugger│                         │
│       └───────┴────┴───────┴──┴───────┴──────────────────────────│
│                           │                                      │
│               ┌───────────▼───────────┐                          │
│               │   Skill Registry      │                          │
│               │   Code Sandbox        │                          │
│               └───────────────────────┘                          │
└──────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    数据层 (PostgreSQL)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Sessions   │  │  Messages   │  │ Checkpoints │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **前端** | Next.js | 16.x |
| | React | 19.x |
| | Zustand | 5.x |
| | Tailwind CSS | 4.x |
| | Shadcn/ui | 最新 |
| **后端** | FastAPI | 0.115+ |
| | LangGraph | 0.3+ |
| | DeepSeek | V3 |
| **数据库** | PostgreSQL | 16 |
| **部署** | Docker + Nginx | 最新 |

---

## 完成状态

### Phase 1: 架构统一 ✅

| 任务 | 状态 |
|------|------|
| PostgreSQL Checkpointer 集成 | ✅ |
| 废弃 Streamlit 前端 (保留兼容) | ✅ |
| 后端 API 完善 | ✅ |
| 健康检查端点 | ✅ |

### Phase 2: 前端开发 ✅

| 任务 | 状态 |
|------|------|
| WebSocket 重连逻辑 | ✅ |
| Markdown 渲染 + 代码高亮 | ✅ |
| Sidebar 会话搜索 + 分组 | ✅ |
| RightPanel 代码/图表/报告 | ✅ |

### Phase 3: 测试 ✅

| 任务 | 状态 |
|------|------|
| 后端 WebSocket 测试 | ✅ 13 tests |
| 前端 Jest 测试 | ✅ 18 tests |
| E2E 流程测试 | ✅ |

### Phase 4: 生产部署 ✅

| 任务 | 状态 |
|------|------|
| Dockerfile.frontend | ✅ |
| Dockerfile.backend | ✅ |
| docker-compose.prod.yml | ✅ |
| Nginx 反向代理 | ✅ |
| 健康监控脚本 | ✅ |

---

## 目录结构

```
multi-agent-data-analysis/
├── backend/                    # FastAPI 后端
│   └── api/
│       ├── main.py            # 应用入口
│       ├── routes/            # API 路由
│       │   ├── chat.py
│       │   ├── sessions.py
│       │   └── upload.py
│       └── websocket/         # WebSocket
│           └── handler.py
├── frontend/                   # Next.js 前端
│   ├── src/
│   │   ├── components/        # UI 组件
│   │   │   ├── chat/         # 聊天界面
│   │   │   ├── sidebar/      # 侧边栏
│   │   │   └── panel/        # 右侧面板
│   │   ├── lib/              # 工具库
│   │   │   ├── store.ts      # Zustand 状态
│   │   │   ├── api.ts        # API 客户端
│   │   │   └── websocket.ts  # WebSocket 客户端
│   │   └── hooks/            # React Hooks
│   └── package.json
├── src/                        # LangGraph Agent 系统
│   ├── agents/                # 8 个 Agent
│   ├── graph/                 # StateGraph 定义
│   ├── skills/                # 13 个 Skill
│   ├── sandbox/               # 代码沙箱
│   ├── persistence/           # 会话持久化
│   ├── memory/                # 记忆系统
│   └── hitl/                  # 人机审批
├── tests/                      # 测试套件
│   ├── backend/               # 后端测试
│   └── ...                    # Agent 测试
├── docs/                       # 文档
│   ├── architecture/          # 架构文档
│   ├── deployment/            # 部署文档
│   ├── development/           # 开发文档
│   └── skills/                # 技能文档
├── docker-compose.yml          # 开发环境
├── docker-compose.prod.yml     # 生产环境
├── Dockerfile.backend          # 后端镜像
├── Dockerfile.frontend         # 前端镜像
└── nginx.conf                  # Nginx 配置
```

---

## 快速启动

### 开发环境

```bash
# 1. 启动 PostgreSQL
docker-compose up -d postgres

# 2. 启动后端
python -m uvicorn backend.api.main:app --reload --port 8000

# 3. 启动前端 (新终端)
cd frontend && npm run dev
```

### 生产环境

```bash
# 一键启动
docker-compose -f docker-compose.prod.yml up -d --build

# 健康检查
./scripts/health_check.sh
```

### 访问地址

| 服务 | 开发环境 | 生产环境 |
|------|---------|---------|
| 前端 | http://localhost:3000 | http://localhost |
| 后端 API | http://localhost:8000 | http://localhost/api |
| API 文档 | http://localhost:8000/docs | http://localhost/api/docs |

---

## 测试

```bash
# 后端测试
python -m pytest tests/ -v

# 前端测试
cd frontend && npm test

# 测试覆盖率
cd frontend && npm run test:coverage
```

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **8 个 Agent** | Coordinator, DataParser, DataProfiler, CodeGenerator, Debugger, Visualizer, ReportWriter, Chat |
| **13 个 Skill** | 内置分析技能 + 社区技能 |
| **代码自修复** | CodeGenerator → Debugger 最多 3 次重试 |
| **HITL 审批** | 3 级风险拦截 |
| **会话持久化** | PostgreSQL Checkpointer |
| **跨会话记忆** | 偏好/知识/模式积累 |
| **WebSocket** | 实时流式响应 + 指数退避重连 |

---

## 关键机制详解

### 1. Coordinator 路由规则（优先级）

Coordinator 使用优先级路由确保任务分发给正确的 Agent：

| 优先级 | 规则 | 目标 Agent | 示例 |
|--------|------|------------|------|
| 1（最高） | 具体分析任务 | code_generator | "分析占比"、"计算排名"、"对比趋势" |
| 2 | 整体概览 | data_profiler | "看看数据"、"数据概况" |
| 3 | 可视化 | visualizer | "画图"、"图表"、"可视化" |
| 4 | 数据加载 | data_parser | 上传文件、加载数据 |
| 5 | 报告生成 | report_writer | "生成报告"、"总结" |
| 6（最低） | 兜底对话 | chat | 与数据分析无关的闲聊 |

**路由代码参考**: [`src/agents/coordinator.py`](src/agents/coordinator.py)

### 2. Sanity Check 模式

所有 Skill 模板均包含 Sanity Check，确保数据有效性：

```python
# === Sanity Check: 验证数据 ===
if df is None:
    print("❌ 数据未加载 (df is None)")
elif df.empty:
    print("❌ 数据为空 (df is empty)")
else:
    print(f"✅ 数据有效: {len(df)} 行, {len(df.columns)} 列")
    # 执行实际分析逻辑...
```

**作用**：
- 提前检测空数据或未加载状态
- 提供清晰的错误提示
- 避免后续代码因数据问题崩溃

**应用文件**：
- [`skills/builtin/describe_statistics/generate.py`](skills/builtin/describe_statistics/generate.py)
- [`skills/builtin/distribution_analysis/generate.py`](skills/builtin/distribution_analysis/generate.py)
- [`skills/builtin/correlation_analysis/generate.py`](skills/builtin/correlation_analysis/generate.py)

### 3. 错误恢复流程

```
CodeGenerator/Visualizer
        │
        ▼ 执行代码
    ┌───────────┐
    │ 成功？    │
    └─────┬─────┘
          │
     No   │   Yes
   ┌──────┴──────┐
   ▼             ▼
Debugger      END
   │
   ▼ 最多 3 次
┌────────────┐
│ LLM 修复   │
└─────┬──────┘
      │
      ▼
  重新执行
```

**重试机制**：
- `MAX_RETRIES = 3`：最多重试 3 次
- 每次修复提供完整错误上下文（原始代码 + stderr + 数据信息）
- 超过重试次数后降级到人工提示

**参考文件**：[`src/agents/debugger.py`](src/agents/debugger.py)

---

*最后更新: 2026-04-04*
*状态: 全栈架构改造完成*
