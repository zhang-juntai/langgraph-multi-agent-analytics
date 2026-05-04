# 多智能体数据分析平台 - 生产级差距分析报告

> 分析时间: 2026-04-04
> 分析范围: 核心架构、8个Agent、沙箱执行器、WebSocket处理器

---

## 目录

1. [可靠性差距](#1-可靠性差距)
2. [可观测性差距](#2-可观测性差距)
3. [安全差距](#3-安全差距)
4. [恢复机制差距](#4-恢复机制差距)
5. [用户体验差距](#5-用户体验差距)
6. [总结与优先级建议](#6-总结与优先级建议)

---

## 1. 可靠性差距

### 1.1 LLM 返回无效 JSON 的处理

**当前状态:**
- `src/agents/coordinator.py` (第139-155行): 使用正则表达式提取 JSON，支持 `\`\`\`json\`\`\`` 包裹和裸 JSON
- JSON 解析失败时回退到 chat 模式，返回 `{"task_type": "chat", "next_agent": "chat"}`
- `src/agents/code_generator.py` (第86-120行): `_extract_code_from_response()` 可处理多种格式

**问题:**
1. 仅做日志记录 (`logger.warning`)，无告警机制
2. 回退策略过于简单，丢失用户意图上下文
3. 无重试机制 —— 一次失败即放弃
4. JSON schema 验证缺失，可能解析出不完整字段

**风险等级:** 🟡 中 (功能降级但不会崩溃)

**建议修复:**
```python
# 1. 添加 JSON Schema 验证
from pydantic import BaseModel, ValidationError

class CoordinatorResponse(BaseModel):
    intent: str
    task_type: Literal["parse", "explore", "code", "visualize", "report", "chat"]
    next_agent: str
    reasoning: str

# 2. 使用 retry_with_backoff 重试
@retry_with_backoff(max_retries=2, exceptions=(json.JSONDecodeError, ValidationError))
def parse_coordinator_response(content: str) -> CoordinatorResponse:
    ...

# 3. 失败时携带原始响应到 chat agent
return {
    "intent": "JSON 解析失败",
    "task_type": "chat",
    "next_agent": "chat",
    "raw_llm_response": content,  # 新增：保留原始响应用于上下文
}
```

**实现工作量:** S (1-2天)

---

### 1.2 代码执行超时处理

**当前状态:**
- `src/sandbox/executor.py` (第258-267行): 使用 `subprocess.TimeoutExpired` 捕获超时
- 超时后返回友好错误消息: `"代码执行超时（{timeout}秒），请优化代码效率或减少数据量。"`
- 超时时间通过 `settings.SANDBOX_TIMEOUT` 配置（默认30秒）

**问题:**
1. 超时后进程可能未完全清理（虽然 Python subprocess 会 kill）
2. 无分级超时 —— 简单查询和复杂分析共用相同超时
3. 无超时后的自动降级方案（如采样数据）
4. 用户无法主动取消长时间执行

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 分级超时策略
TIMEOUT_TIERS = {
    "quick": 10,      # 快速查询
    "normal": 30,     # 常规分析
    "heavy": 120,     # 复杂计算
}

# 2. 超时后的数据采样降级
def execute_with_fallback(code, datasets, timeout=30):
    result = execute_code(code, datasets, timeout)
    if result["success"] or "超时" not in result["stderr"]:
        return result

    # 尝试数据采样后重试
    sampled_datasets = [sample_dataset(ds, max_rows=1000) for ds in datasets]
    return execute_code(code, sampled_datasets, timeout)

# 3. 确保进程清理
try:
    result = subprocess.run(..., timeout=timeout)
except subprocess.TimeoutExpired as e:
    if e.timeout:
        # 显式 kill 进程组
        os.killpg(os.getpgid(result.pid), signal.SIGKILL)
```

**实现工作量:** M (3-5天)

---

### 1.3 数据库连接失败处理

**当前状态:**
- `src/graph/builder.py` (第69-86行): PostgreSQL Checkpointer 初始化失败时降级到 `InMemorySaver`
- `src/persistence/session_store.py`: 使用 SQLite，无连接池，每次操作新建连接

**问题:**
1. PostgreSQL 降级时无告警，仅 `logger.warning`
2. SQLite 无连接池，高并发下可能遇到 `SQLITE_BUSY`
3. 无数据库健康检查机制
4. 连接断开后无自动重连

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 添加数据库健康检查端点
async def health_check() -> dict:
    return {
        "postgres": await check_postgres_connection(),
        "sqlite": check_sqlite_connection(),
    }

# 2. SQLite 连接池（使用 aiosqlite）
import aiosqlite
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_sqlite_conn():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        yield conn

# 3. PostgreSQL 断线重连
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_postgres_checkpointer():
    ...
```

**实现工作量:** M (3-5天)

---

### 1.4 熔断与限流

**当前状态:**
- **无熔断机制**: LLM 调用失败会无限重试（仅 `LLM_MAX_RETRIES=2`）
- **无限流机制**: 无 API 调用频率限制
- `src/utils/error_recovery.py`: 提供 `retry_with_backoff` 装饰器，但未被各 Agent 使用

**问题:**
1. LLM 服务不可用时可能雪崩
2. 恶意用户可无限制调用系统资源
3. 无请求队列深度限制
4. WebSocket 连接无速率限制

**风险等级:** 🔴 高

**建议修复:**
```python
# 1. 使用 circuitbreaker 熔断器
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
def call_llm_with_circuit(messages):
    return llm.invoke(messages)

# 2. API 限流（FastAPI 中间件）
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat_endpoint(...):
    ...

# 3. WebSocket 消息限流
class RateLimitedWebSocket:
    def __init__(self, max_messages_per_minute=20):
        self.message_times = []

    async def receive(self):
        now = time.time()
        self.message_times = [t for t in self.message_times if now - t < 60]
        if len(self.message_times) >= self.max_messages_per_minute:
            raise RateLimitError()
        self.message_times.append(now)
        ...
```

**实现工作量:** M (3-5天)

---

## 2. 可观测性差距

### 2.1 结构化日志

**当前状态:**
- 使用 Python 标准 `logging` 模块
- 日志格式未配置，输出为纯文本
- 无 correlation ID 追踪请求链路
- 关键业务事件无结构化记录

**问题:**
```python
# 当前日志示例 (src/agents/coordinator.py)
logger.info(f"Coordinator 路由决策: intent={intent}, task_type={task_type}")
# 问题：无法被 ELK/Loki 解析，无法按字段查询
```

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 使用 structlog 结构化日志
import structlog

log = structlog.get_logger()

# 2. 添加 correlation ID
from contextvars import ContextVar
request_id: ContextVar[str] = ContextVar("request_id")

@structlog.processor
def add_request_id(logger, method_name, event_dict):
    event_dict["request_id"] = request_id.get(None)
    return event_dict

# 3. 结构化业务日志
log.info(
    "coordinator_route",
    intent=intent,
    task_type=task_type,
    next_agent=next_agent,
    reasoning=reasoning,
    session_id=session_id,
    latency_ms=latency,
)
```

**实现工作量:** S (1-2天)

---

### 2.2 指标与计数器

**当前状态:**
- **无任何 Metrics 收集**
- 无请求延迟统计
- 无 Agent 执行成功率统计
- 无代码执行耗时分布

**问题:**
无法回答以下运营问题:
- "过去1小时 LLM 调用成功率是多少？"
- "哪个 Agent 最常被调用？"
- "代码执行的平均耗时是多少？"

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 使用 Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# 定义指标
llm_calls_total = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["agent", "status"]
)

agent_execution_seconds = Histogram(
    "agent_execution_seconds",
    "Agent execution time",
    ["agent_name"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60]
)

code_execution_total = Counter(
    "code_execution_total",
    "Sandbox code executions",
    ["status"]  # success, timeout, error
)

active_websockets = Gauge(
    "active_websockets",
    "Number of active WebSocket connections"
)

# 2. 在 Agent 中埋点
def coordinator_node(state):
    start_time = time.time()
    try:
        result = ...
        llm_calls_total.labels(agent="coordinator", status="success").inc()
        return result
    except Exception as e:
        llm_calls_total.labels(agent="coordinator", status="error").inc()
        raise
    finally:
        agent_execution_seconds.labels(agent_name="coordinator").observe(
            time.time() - start_time
        )

# 3. 暴露 metrics 端点
from prometheus_client import make_asgi_app
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

**实现工作量:** M (3-5天)

---

### 2.3 端到端请求追踪

**当前状态:**
- 无分布式追踪 (Distributed Tracing)
- 无法追踪一个请求从 WebSocket → Coordinator → Agent → Sandbox 的完整链路
- 各组件独立记录日志，无关联

**问题:**
- 故障排查困难，需要手动关联多个日志文件
- 无法定位性能瓶颈具体在哪个组件

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 使用 OpenTelemetry
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

# 2. 在 WebSocket handler 中创建根 span
async def websocket_chat(websocket, session_id):
    with tracer.start_as_current_span(
        "websocket_chat",
        attributes={"session_id": session_id}
    ) as root_span:
        request_id.set(trace.span_context.trace_id)
        ...

# 3. 在各 Agent 中创建子 span
def coordinator_node(state):
    with tracer.start_as_current_span("coordinator.route") as span:
        span.set_attribute("user_message", user_message[:100])
        result = llm.invoke(messages)
        span.set_attribute("task_type", result["task_type"])
        return result

# 4. 导出 traces 到 Jaeger/Zipkin
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

trace_exporter = OTLPSpanExporter(endpoint="http://localhost:4317")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(trace_exporter))
```

**实现工作量:** M (3-5天)

---

### 2.4 错误捕获与上报

**当前状态:**
- `src/utils/error_recovery.py`: 提供 `user_friendly_error()` 转换错误消息
- 各 Agent 使用 try/except 捕获异常，记录 `logger.error`
- **无集中错误追踪服务** (如 Sentry)

**问题:**
1. 错误信息分散在日志中，难以聚合分析
2. 无错误趋势分析
3. 无错误告警机制

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 集成 Sentry
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://xxx@sentry.io/xxx",
    traces_sample_rate=0.1,
    integrations=[FastApiIntegration()],
)

# 2. 在关键路径添加 span
def code_generator_node(state):
    with sentry_sdk.start_span(op="agent", description="code_generator"):
        try:
            ...
        except Exception as e:
            sentry_sdk.capture_exception(e)
            sentry_sdk.set_context("state", {
                "datasets_count": len(state.get("datasets", [])),
                "retry_count": state.get("retry_count", 0),
            })
            raise

# 3. 配置告警规则 (Sentry UI)
# - 1小时内超过 10 次 LLM 调用失败 -> 发送 Slack 通知
```

**实现工作量:** S (1-2天)

---

## 3. 安全差距

### 3.1 沙箱隔离性评估

**当前状态:**
- `src/sandbox/executor.py`: 使用 `subprocess` 隔离执行
- 危险模式检测 (`DANGEROUS_PATTERNS`): 静态字符串匹配
- 执行环境变量限制: `PYTHONHASHSEED`, `MPLBACKEND`, `PYTHONIOENCODING`

**问题:**
1. **subprocess 非真正的沙箱** —— 代码仍在同一操作系统用户下运行
2. 危险模式检测可被绕过:
   ```python
   # 绕过示例
   __import__("o"+"s").system("rm -rf /")  # 字符串拼接绕过
   getattr(__builtins__, "ex" + "ec")("...")  # 动态构建
   ```
3. 无文件系统隔离 —— 可访问任意文件
4. 无网络隔离 —— 可建立 Socket 连接
5. 无资源隔离 (CPU/内存) —— Windows 不支持 `resource` 模块

**风险等级:** 🔴 高

**建议修复:**
```python
# 方案 A: 使用 RestrictedPython AST 过滤
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins

def execute_with_restricted_python(code, allowed_modules=None):
    # AST 层面禁止危险语法
    byte_code = compile_restricted(code, "<sandbox>", "exec")
    # 限制可用模块
    safe_globals = {"__builtins__": safe_builtins}
    exec(byte_code, safe_globals)

# 方案 B: 使用 Docker 容器隔离 (推荐生产环境)
import docker

client = docker.from_env()

def execute_in_docker(code, timeout=30):
    container = client.containers.run(
        "python:3.11-slim",
        command=["python", "-c", code],
        mem_limit="512m",
        cpu_period=100000,
        cpu_quota=50000,  # 50% CPU
        network_disabled=True,
        read_only=True,
        timeout=timeout,
        remove=True,
    )
    return container.output

# 方案 C: 使用 gVisor 或 Firecracker 进一步隔离
```

**实现工作量:** L (1-2周)

---

### 3.2 输入验证

**当前状态:**
- `src/agents/data_parser.py`: 验证文件格式 (`.csv`, `.xlsx`, `.json`)
- `backend/api/websocket/handler.py`: 仅验证消息非空
- **无用户输入 sanitization**

**问题:**
1. 文件路径可被注入访问任意文件:
   ```python
   # 恶意输入
   "请分析 /etc/passwd"
   "../../../etc/shadow"
   ```
2. 用户消息无长度限制 —— 可发送超大消息
3. 文件大小无限制 —— 可上传超大文件导致 DoS

**风险等级:** 🔴 高

**建议修复:**
```python
# 1. 文件路径白名单
ALLOWED_DATA_DIRS = [settings.UPLOAD_DIR, settings.DATA_DIR / "sample"]

def validate_file_path(file_path: str) -> str | None:
    path = Path(file_path).resolve()
    if not any(str(path).startswith(str(allowed)) for allowed in ALLOWED_DATA_DIRS):
        raise SecurityError(f"禁止访问路径: {file_path}")
    return str(path)

# 2. 消息长度限制
MAX_MESSAGE_LENGTH = 10000

async def websocket_chat(websocket, session_id):
    data = await websocket.receive_json()
    message = data.get("message", "")
    if len(message) > MAX_MESSAGE_LENGTH:
        await websocket.send_json({
            "type": "error",
            "message": f"消息长度超过限制 ({MAX_MESSAGE_LENGTH})"
        })
        return

# 3. 文件大小限制
MAX_FILE_SIZE_MB = 100

def validate_file_size(file_path: str):
    size_mb = Path(file_path).stat().st_size / 1024 / 1024
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValidationError(f"文件过大: {size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB")
```

**实现工作量:** S (1-2天)

---

### 3.3 WebSocket 安全

**当前状态:**
- WebSocket 连接无认证
- 会话 ID 可被猜测 (UUID)
- 无连接来源验证

**问题:**
1. 任何人可连接任意会话
2. 会话劫持风险
3. 无 CSRF 防护

**风险等级:** 🔴 高

**建议修复:**
```python
# 1. WebSocket 认证
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return payload["user_id"]

@app.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    user_id: str = Depends(verify_token),
):
    # 验证用户有权访问该会话
    if not user_owns_session(user_id, session_id):
        await websocket.close(code=1008, reason="Forbidden")
        return
    ...

# 2. Origin 验证
ALLOWED_ORIGINS = ["https://yourdomain.com", "http://localhost:3000"]

async def websocket_chat(websocket: WebSocket, session_id: str):
    origin = websocket.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008, reason="Invalid origin")
        return
    ...
```

**实现工作量:** M (3-5天)

---

### 3.4 Rate Limiting

**当前状态:**
- **无任何速率限制**

**问题:**
1. 可无限调用 LLM API 导致费用失控
2. 可无限执行沙箱代码导致资源耗尽
3. WebSocket 可被洪水攻击

**风险等级:** 🔴 高

**建议修复:**
(参见 1.4 熔断与限流)

**实现工作量:** M (3-5天)

---

## 4. 恢复机制差距

### 4.1 执行中断恢复

**当前状态:**
- `src/graph/builder.py`: 使用 LangGraph Checkpointer (PostgreSQL/InMemory)
- WebSocket 断开后可从 checkpoint 恢复状态
- `src/utils/task_queue.py`: 任务队列记录执行状态

**问题:**
1. Checkpoint 仅保存 State，不保存执行位置
2. 代码执行中断后无法续跑，只能重新开始
3. 长时间分析任务中断后无法断点续传

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 分析任务分阶段 + 中间态持久化
def long_running_analysis(state):
    stages = ["load_data", "preprocess", "analyze", "generate_report"]
    completed_stages = state.get("completed_stages", [])

    for stage in stages:
        if stage in completed_stages:
            continue
        result = execute_stage(stage, state)
        state["completed_stages"].append(stage)
        save_checkpoint(state)  # 每阶段保存
    return state

# 2. 添加任务恢复 API
@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    task = task_queue.get_status(task_id)
    if task and task.status == TaskStatus.FAILED:
        return task_queue.submit(task.name, resume_from_checkpoint, task.last_state)
    return {"error": "Task cannot be resumed"}
```

**实现工作量:** M (3-5天)

---

### 4.2 Dead Letter Queue

**当前状态:**
- **无死信队列机制**
- 失败任务仅记录到日志和 `TaskInfo.error`
- 无失败任务重试/归档机制

**问题:**
1. 失败任务无法事后分析
2. 无法批量重试失败任务
3. 无法统计失败模式

**风险等级:** 🟢 低

**建议修复:**
```python
# 1. 实现 DLQ
class DeadLetterQueue:
    def __init__(self, max_size=1000):
        self._queue = deque(maxlen=max_size)

    def add(self, task: TaskInfo, error: Exception):
        dlq_entry = {
            "task_id": task.id,
            "name": task.name,
            "error": str(error),
            "state": task.result,
            "timestamp": datetime.now().isoformat(),
        }
        self._queue.append(dlq_entry)
        save_to_db(dlq_entry)  # 持久化

    def retry_all(self):
        for entry in self._queue:
            resubmit_task(entry)

    def get_statistics(self):
        # 统计失败模式
        ...
```

**实现工作量:** S (1-2天)

---

### 4.3 会话恢复

**当前状态:**
- `src/persistence/session_store.py`: 完整的会话持久化 (SQLite)
- 支持消息历史、数据集、产物的存储
- LangGraph Checkpointer 支持 PostgreSQL 持久化

**优点:**
- 会话状态完整可恢复
- 页面刷新后可继续

**剩余问题:**
1. Checkpointer 和 SessionStore 未同步 —— 可能不一致
2. 无会话过期清理机制

**风险等级:** 🟢 低

**建议修复:**
```python
# 1. 统一状态管理
class UnifiedStateManager:
    def __init__(self):
        self.session_store = SessionStore()
        self.checkpointer = get_checkpointer()

    def save_state(self, session_id: str, state: AnalysisState):
        # 同时保存到两处，确保一致性
        self.session_store.save_state(session_id, state)
        self.checkpointer.put(session_id, state)

    def load_state(self, session_id: str) -> AnalysisState:
        # 优先从 checkpointer 加载
        state = self.checkpointer.get(session_id)
        if not state:
            state = self.session_store.load_state(session_id)
        return state

# 2. 会话过期清理
def cleanup_expired_sessions(max_age_days=30):
    cutoff = datetime.now() - timedelta(days=max_age_days)
    expired = session_store.list_sessions_oldr_than(cutoff)
    for session in expired:
        session_store.delete_session(session["id"])
```

**实现工作量:** S (1-2天)

---

## 5. 用户体验差距

### 5.1 进度指示器

**当前状态:**
- `backend/api/websocket/handler.py`: 发送 Agent 执行状态
  ```python
  await websocket.send_json({
      "type": "agent",
      "agent": node_name,
      "agent_display": agent_display
  })
  ```
- 无细粒度进度百分比
- 无预估剩余时间

**问题:**
1. 用户不知道任务执行到哪一步
2. 长时间任务用户可能误以为卡死
3. 无取消按钮

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 分阶段进度报告
PROGRESS_STAGES = {
    "coordinator": {"weight": 0.05, "label": "分析意图"},
    "data_parser": {"weight": 0.15, "label": "加载数据"},
    "code_generator": {"weight": 0.40, "label": "生成代码"},
    "debugger": {"weight": 0.20, "label": "修复代码"},
    "report_writer": {"weight": 0.20, "label": "生成报告"},
}

async def report_progress(websocket, completed_agents, total_agents):
    progress = sum(
        PROGRESS_STAGES.get(agent, {"weight": 0})["weight"]
        for agent in completed_agents
    )
    await websocket.send_json({
        "type": "progress",
        "progress": progress,
        "completed": completed_agents,
        "remaining": total_agents - len(completed_agents),
    })

# 2. 代码执行进度 (通过流式输出)
def execute_code_streaming(code, progress_callback):
    for line in code.split("\n"):
        result = execute_line(line)
        progress_callback(percentage=...)

# 3. 前端取消按钮
@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    return task_queue.cancel(task_id)
```

**实现工作量:** M (3-5天)

---

### 5.2 错误消息清晰度

**当前状态:**
- `src/utils/error_recovery.py`: `user_friendly_error()` 提供友好错误消息
- 各 Agent 返回带 emoji 的错误提示
- 沙箱超时返回: `"⏰ 代码执行超时（{timeout}秒），请优化代码效率或减少数据量。"`

**优点:**
- 已有基础的用户友好错误处理

**问题:**
1. 技术错误仍可能暴露给用户
2. 无错误恢复建议
3. 无多语言支持

**风险等级:** 🟢 低

**建议修复:**
```python
# 1. 错误类型分类 + 建议
ERROR_SOLUTIONS = {
    "encoding": {
        "message": "文件编码不兼容",
        "suggestions": [
            "将文件另存为 UTF-8 编码",
            "或尝试上传 Excel 格式 (.xlsx)",
        ],
    },
    "timeout": {
        "message": "分析耗时过长",
        "suggestions": [
            "减少数据量 (当前 {rows} 行)",
            "简化分析需求",
            "联系管理员增加超时时间",
        ],
    },
}

def format_error_with_solutions(error_type: str, **context) -> str:
    error_info = ERROR_SOLUTIONS.get(error_type, {"message": "未知错误", "suggestions": []})
    message = error_info["message"]
    suggestions = "\n".join(f"• {s.format(**context)}" for s in error_info["suggestions"])
    return f"❌ {message}\n\n💡 建议:\n{suggestions}"
```

**实现工作量:** S (1-2天)

---

### 5.3 超时处理体验

**当前状态:**
- 沙箱超时 30 秒后返回错误消息
- LLM 调用无独立超时 (依赖 HTTP 客户端默认)
- 无前端超时 UI 反馈

**问题:**
1. 用户等待 30 秒后才看到超时，体验差
2. 无"正在处理，请稍候"的持续反馈
3. 无"您可以选择取消"的提示

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 前端超时提示
# WebSocket 消息
await websocket.send_json({
    "type": "status",
    "status": "executing",
    "elapsed_seconds": elapsed,
    "message": "代码执行中..." if elapsed < 10 else "执行时间较长，您可以取消后简化需求",
})

# 2. 分级超时警告
async def execute_with_progress(code, websocket, timeout=30):
    start_time = time.time()
    task = asyncio.create_task(execute_code_async(code))

    while not task.done():
        elapsed = time.time() - start_time
        if elapsed > timeout * 0.5:
            await websocket.send_json({
                "type": "warning",
                "message": f"已执行 {elapsed:.0f} 秒，可能需要更长时间",
            })
        if elapsed > timeout * 0.8:
            await websocket.send_json({
                "type": "warning",
                "message": "即将超时，建议取消并简化需求",
                "cancel_available": True,
            })
        await asyncio.sleep(1)

    return task.result()
```

**实现工作量:** M (3-5天)

---

### 5.4 优雅降级

**当前状态:**
- PostgreSQL 不可用时降级到 InMemorySaver
- Coordinator 解析失败时降级到 chat 模式
- LLM 调用失败时返回错误消息

**问题:**
1. 降级决策不透明 —— 用户不知道为什么功能受限
2. 无渐进式功能降级
3. 无离线模式

**风险等级:** 🟡 中

**建议修复:**
```python
# 1. 功能降级状态通知
class SystemStatus:
    def __init__(self):
        self.llm_available = True
        self.sandbox_available = True
        self.postgres_available = True

    def get_degraded_features(self) -> list[str]:
        features = []
        if not self.postgres_available:
            features.append("会话持久化 (页面刷新后丢失)")
        if not self.llm_available:
            features.append("智能分析 (仅基础统计)")
        return features

# 2. 降级时通知用户
if system_status.llm_available is False:
    await websocket.send_json({
        "type": "degraded_mode",
        "message": "AI 服务暂时不可用，已切换到基础模式",
        "unavailable_features": ["智能代码生成", "自然语言分析"],
    })

# 3. 基础模式 fallback
def analyze_without_llm(state):
    """LLM 不可用时的基础分析"""
    return {
        "messages": [AIMessage(content="仅提供基础统计信息")],
        "basic_stats": calculate_basic_stats(state["datasets"]),
    }
```

**实现工作量:** M (3-5天)

---

## 6. 总结与优先级建议

### 风险矩阵

| 差距项 | 风险等级 | 工作量 | 建议优先级 |
|--------|----------|--------|------------|
| 沙箱隔离性 | 🔴 高 | L | P0 |
| WebSocket 认证 | 🔴 高 | M | P0 |
| 输入验证 | 🔴 高 | S | P0 |
| 熔断与限流 | 🔴 高 | M | P0 |
| Metrics 收集 | 🟡 中 | M | P1 |
| 结构化日志 | 🟡 中 | S | P1 |
| 分布式追踪 | 🟡 中 | M | P1 |
| 代码执行分级超时 | 🟡 中 | M | P1 |
| 进度指示器 | 🟡 中 | M | P1 |
| 错误追踪 (Sentry) | 🟡 中 | S | P1 |
| LLM JSON 重试 | 🟡 中 | S | P2 |
| 数据库连接池 | 🟡 中 | M | P2 |
| Dead Letter Queue | 🟢 低 | S | P2 |
| 会话过期清理 | 🟢 低 | S | P2 |
| 错误消息优化 | 🟢 低 | S | P3 |

### 建议实施顺序

**Phase 1 (安全加固) - 1-2 周:**
1. 实现文件路径白名单和输入验证
2. 添加 WebSocket 认证
3. 实现基础 Rate Limiting
4. 升级沙箱为 Docker 隔离

**Phase 2 (可观测性) - 1 周:**
1. 引入 structlog 结构化日志
2. 添加 Prometheus Metrics
3. 集成 Sentry 错误追踪
4. 配置基础告警

**Phase 3 (可靠性增强) - 1 周:**
1. 实现熔断器模式
2. 分级超时策略
3. LLM 调用重试优化
4. 数据库连接池

**Phase 4 (体验优化) - 1 周:**
1. 实时进度指示器
2. 超时预警机制
3. 优雅降级通知
4. 错误消息优化

---

## 附录: 关键文件路径

- Agent 实现: `src/agents/*.py`
- Graph 构建: `src/graph/builder.py`
- 状态定义: `src/graph/state.py`
- 沙箱执行: `src/sandbox/executor.py`
- WebSocket 处理: `backend/api/websocket/handler.py`
- 配置管理: `configs/settings.py`
- 会话存储: `src/persistence/session_store.py`
- 错误恢复: `src/utils/error_recovery.py`
- 任务队列: `src/utils/task_queue.py`
