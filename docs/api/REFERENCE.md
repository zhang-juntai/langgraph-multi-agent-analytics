# API 参考文档

## 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://localhost:8000` |
| API 前缀 | `/api` |
| 文档 | `/docs` (Swagger UI) |
| OpenAPI | `/openapi.json` |

---

## 认证

当前版本无需认证（开发环境）。生产环境建议添加 API Key 认证。

---

## 端点总览

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/health/detailed` | 详细状态 |
| POST | `/api/sessions` | 创建会话 |
| GET | `/api/sessions` | 列出会话 |
| GET | `/api/sessions/{id}` | 获取会话详情 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| PATCH | `/api/sessions/{id}/name` | 重命名会话 |
| POST | `/api/chat` | 发送消息 (同步) |
| WS | `/ws/chat/{session_id}` | WebSocket 连接 |
| POST | `/api/upload/{session_id}` | 上传文件 |

---

## 健康检查

### GET /health

简单的健康检查端点。

**响应**:
```json
{
  "status": "healthy"
}
```

### GET /health/detailed

详细的系统状态检查。

**响应**:
```json
{
  "status": "healthy",
  "timestamp": "2026-04-04T12:00:00",
  "components": {
    "database": {
      "status": "ok",
      "type": "sqlite"
    },
    "postgres": {
      "status": "ok"
    },
    "llm": {
      "status": "configured",
      "model": "deepseek-chat"
    },
    "disk": {
      "status": "ok",
      "free_gb": 50.5,
      "used_percent": 45.2
    }
  }
}
```

**状态值**:
- `healthy` - 所有组件正常
- `degraded` - 部分非关键组件异常
- `unhealthy` - 关键组件异常

---

## 会话管理

### POST /api/sessions

创建新会话。

**请求体**:
```json
{
  "name": "数据分析会话"
}
```

**响应**:
```json
{
  "id": "abc123",
  "name": "数据分析会话",
  "created_at": "2026-04-04T12:00:00",
  "updated_at": "2026-04-04T12:00:00",
  "messages": [],
  "datasets": [],
  "figures": [],
  "current_code": "",
  "report": ""
}
```

### GET /api/sessions

列出所有会话。

**响应**:
```json
[
  {
    "id": "abc123",
    "name": "数据分析会话",
    "created_at": "2026-04-04T12:00:00",
    "updated_at": "2026-04-04T12:00:00",
    "message_count": 5
  }
]
```

### GET /api/sessions/{session_id}

获取会话详情。

**响应**:
```json
{
  "id": "abc123",
  "name": "数据分析会话",
  "messages": [
    {
      "role": "user",
      "content": "分析这个数据",
      "timestamp": 1712232000000
    },
    {
      "role": "assistant",
      "content": "好的，我来分析...",
      "timestamp": 1712232001000
    }
  ],
  "datasets": [
    {
      "file_name": "data.csv",
      "file_path": "/uploads/abc123/data.csv",
      "num_rows": 100,
      "num_cols": 5,
      "columns": ["name", "age", "score", "date", "category"]
    }
  ],
  "figures": ["/static/figures/figures_xxx/chart1.png"],
  "current_code": "import pandas as pd\n...",
  "report": "# 分析报告\n..."
}
```

### DELETE /api/sessions/{session_id}

删除会话。

**响应**:
```json
{
  "status": "deleted",
  "session_id": "abc123"
}
```

### PATCH /api/sessions/{session_id}/name

重命名会话。

**请求体**:
```json
{
  "name": "新名称"
}
```

**响应**:
```json
{
  "id": "abc123",
  "name": "新名称",
  "updated_at": "2026-04-04T12:30:00"
}
```

---

## 聊天 API

### POST /api/chat

发送消息并获取同步响应。

**请求体**:
```json
{
  "session_id": "abc123",
  "message": "帮我分析这个数据的分布情况"
}
```

**响应**:
```json
{
  "session_id": "abc123",
  "response": "我来帮你分析数据分布...\n\n1. 数值型列统计...\n2. 类别型列分布...",
  "code": "import pandas as pd\n...",
  "figures": ["/static/figures/figures_xxx/chart1.png"]
}
```

---

## WebSocket API

### WS /ws/chat/{session_id}

建立 WebSocket 连接进行实时通信。

**连接**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat/abc123');
```

### 消息格式

#### 客户端 → 服务器

**发送消息**:
```json
{
  "type": "message",
  "message": "分析数据"
}
```

**心跳**:
```json
{
  "type": "ping"
}
```

#### 服务器 → 客户端

**连接确认**:
```json
{
  "type": "connected",
  "session_id": "abc123"
}
```

**开始处理**:
```json
{
  "type": "start",
  "session_id": "abc123",
  "agent": "coordinator"
}
```

**流式内容**:
```json
{
  "type": "chunk",
  "content": "正在分析数据...",
  "node": "code_generator"
}
```

**处理完成**:
```json
{
  "type": "done",
  "session_id": "abc123",
  "final_state": {
    "messages": [...],
    "figures": [...]
  }
}
```

**错误**:
```json
{
  "type": "error",
  "message": "处理失败",
  "details": "Error: ..."
}
```

**心跳响应**:
```json
{
  "type": "pong"
}
```

### 示例代码

```typescript
import { ChatWebSocket } from '@/lib/websocket'

const ws = new ChatWebSocket(sessionId, (data) => {
  switch (data.type) {
    case 'start':
      console.log('Agent started:', data.agent)
      break
    case 'chunk':
      appendContent(data.content)
      break
    case 'done':
      updateState(data.final_state)
      break
    case 'error':
      showError(data.message)
      break
  }
})

await ws.connect()
ws.send('分析这个数据')
```

---

## 文件上传

### POST /api/upload/{session_id}

上传数据文件。

**请求**: `multipart/form-data`
- `file`: 文件 (CSV, Excel, JSON)

**响应**:
```json
{
  "file_name": "sales_data.csv",
  "file_path": "/uploads/abc123/sales_data.csv",
  "num_rows": 1000,
  "num_cols": 8,
  "columns": ["date", "product", "region", "sales", "quantity", "price", "category", "profit"],
  "dtypes": {
    "date": "object",
    "product": "object",
    "sales": "float64",
    "quantity": "int64"
  },
  "preview": [
    ["2024-01-01", "Product A", "North", 1500.0, 100],
    ["2024-01-02", "Product B", "South", 2300.0, 150]
  ]
}
```

**支持的文件格式**:
- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)
- JSON (`.json`)
- TSV (`.tsv`)

**文件大小限制**: 200MB

---

## 静态文件

### GET /static/figures/{path}

访问生成的图表文件。

**示例**:
```
GET /static/figures/figures_abc123/chart1.png
```

**响应**: 图片文件 (PNG)

---

## 错误处理

### 错误响应格式

```json
{
  "detail": "错误描述",
  "error_code": "SESSION_NOT_FOUND"
}
```

### 常见错误码

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 404 | `SESSION_NOT_FOUND` | 会话不存在 |
| 400 | `INVALID_FILE_FORMAT` | 不支持的文件格式 |
| 413 | `FILE_TOO_LARGE` | 文件超过大小限制 |
| 500 | `INTERNAL_ERROR` | 服务器内部错误 |
| 503 | `SERVICE_UNAVAILABLE` | 服务暂时不可用 |

---

## 速率限制

生产环境建议配置:
- API 请求: 100 req/min
- 文件上传: 10 req/min
- WebSocket: 无限制

---

## CORS 配置

当前允许所有来源 (`*`)。生产环境应限制:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PATCH"],
    allow_headers=["*"],
)
```

---

*最后更新: 2026-04-04*
