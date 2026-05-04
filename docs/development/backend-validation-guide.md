# 后端验证指南

## 🎯 验证目标

在开始前端开发前，确保后端所有功能正常工作。

## 🧪 测试套件

### 后端测试 (pytest)

```bash
# 运行所有后端测试
python -m pytest tests/ -v

# 仅运行 WebSocket 测试
python -m pytest tests/backend/test_websocket.py -v

# 运行 API 验证脚本
python tests/backend/test_backend_api.py
```

### 前端测试 (Jest)

```bash
# 运行所有前端测试
cd frontend && npm test

# 监听模式
cd frontend && npm run test:watch

# 覆盖率报告
cd frontend && npm run test:coverage
```

## 📋 验证清单

### 阶段 1: 环境准备

- [ ] **PostgreSQL 运行中**
  ```bash
  docker-compose up -d postgres
  # 检查: docker ps
  ```

- [ ] **Python 依赖已安装**
  ```bash
  pip install -r requirements.txt
  pip install psycopg2-binary
  ```

- [ ] **后端服务运行中**
  ```bash
  python -m uvicorn backend.api.main:app --reload --host 0.0.0.0
  # 应该看到: Uvicorn running on http://0.0.0.0:8000
  ```

### 阶段 2: 功能验证

- [ ] **健康检查**
  ```bash
  curl http://localhost:8000/health
  # 预期输出: {"status": "healthy"}
  ```

- [ ] **创建会话**
  ```bash
  curl -X POST http://localhost:8000/api/sessions \
    -H "Content-Type: application/json" \
    -d '{"name": "测试会话"}'
  # 预期输出: {"id": "...", "name": "测试会话", ...}
  ```

- [ ] **列出所有会话**
  ```bash
  curl http://localhost:8000/api/sessions
  # 预期输出: [{"id": "...", "name": "测试会话", ...}]
  ```

- [ ] **获取会话详情**
  ```bash
  curl http://localhost:8000/api/sessions/{session_id}
  # 预期输出: 包含 messages, datasets, figures 等
  ```

- [ ] **发送聊天消息**
  ```bash
  curl -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d '{
    "session_id": "{session_id}",
    "message": "你好"
  }'
  # 预期输出: {"session_id": "...", "response": "你好！...", ...}
  ```

- [ ] **文件上传**
  ```bash
  curl -X POST http://localhost:8000/api/upload/{session_id} \
    -F "file=@test.csv"
  # 预期输出: {"file_name": "test.csv", "num_rows": 3, ...}
  ```

### 阶段 3: 集成验证

- [ ] **与 LangGraph 集成**
  ```python
  python -c "from src.graph.builder import get_graph; print(get_graph())"
  # 预期: 不报错，能成功构建 Graph
  ```

- [ ] **SessionStore 持久化**
  ```python
  python -c "
  from src.persistence.session_store import SessionStore
  store = SessionStore()
  print(store.list_sessions())
  "
  # 预期: 能成功查询会话列表
  ```

---

## 🔧 自动化验证

### 方法 1: 运行验证脚本

```bash
# 运行自动化测试
python tests/backend/test_backend_api.py
```

脚本会自动：
1. ✅ 检查 PostgreSQL 连接
2. ✅ 检查后端服务
3. ✅ 测试会话管理
4. ✅ 测试聊天 API
5. ✅ 测试文件上传
6. ✅ 测试 WebSocket
7. ✅ 测试 LangGraph 集成

### 方法 2: 手动验证

如果自动化脚本有问题，可以手动验证：

```bash
# 1. 健康检查
curl http://localhost:8000/health

# 2. 创建会话
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "验证测试"}' | jq -r '.id')

echo "会话 ID: $SESSION_ID"

# 3. 发送消息
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"message\": \"测试消息\"}"

# 4. 获取会话详情
curl http://localhost:8000/api/sessions/$SESSION_ID
```

---

## 🐛 常见问题

### 问题 1: PostgreSQL 连接失败

**错误**: `connection refused` 或 `could not connect`

**解决方案**:
```bash
# 启动 PostgreSQL
docker-compose up -d postgres

# 等待启动
sleep 5

# 验证连接
docker-compose logs postgres
```

### 问题 2: 后端启动失败

**错误**: `ModuleNotFoundError: No module named 'backend'`

**解决方案**:
```bash
# 确保在项目根目录
cd /path/to/multi-agent-data-analysis

# 设置 PYTHONPATH
export PYTHONPATH=${PYTHONPATH}:$(pwd)

# 启动后端
python -m uvicorn backend.api.main:app --reload
```

### 问题 3: 聊天返回错误

**错误**: `会话不存在` 或 `Graph 执行错误`

**解决方案**:
1. 确保已创建会话
2. 检查 SessionStore 数据库是否正常
3. 查看后端日志了解详细错误

### 问题 4: WebSocket 连接失败

**错误**: WebSocket 握手失败

**解决方案**:
1. 检查防火墙设置
2. 确保 8000 端口未被占用
3. 查看 uvicorn 日志

---

## 📊 验证标准

### ✅ 所有测试通过的条件

1. **环境检查** ✅
   - PostgreSQL 运行正常
   - 后端服务启动成功
   - 依赖包全部安装

2. **功能测试** ✅
   - 会话管理: 创建、查询、删除
   - 聊天 API: 同步响应正常
   - 文件上传: CSV/Excel 文件能解析
   - WebSocket: 能建立连接和收发消息

3. **集成测试** ✅
   - LangGraph Graph 能正常构建
   - SessionStore 持久化正常工作
   - 与现有代码无缝集成

### ⚠️ 部分失败可接受的情况

以下情况下可以继续前端开发：
- WebSocket 测试跳过（可以先不用流式响应）
- 集成测试有警告（不影响核心功能）

以下情况下需要修复后再继续：
- PostgreSQL 连接失败
- 会话管理失败
- 聊天 API 失败

---

## 🎯 验证完成标志

当你看到以下输出时，后端验证完成：

```
============================================================
📊 测试结果总结
============================================================
✅ 通过 - 前置条件检查
✅ 通过 - 会话管理
✅ 通过 - 聊天 API
✅ 通过 - 文件上传
✅ 通过 - WebSocket
✅ 通过 - 集成测试

总计: 6/6 通过

🎉 所有测试通过！后端功能正常，可以开始前端开发。
```

---

## 📝 验证笔记模板

验证过程中请记录：

```
验证日期: 2026-04-02
验证人: 你的名字
环境: Windows 11 / Python 3.11 / PostgreSQL 16

测试结果:
✅ 通过: ...
⚠️  跳过: ...
❌ 失败: ...

发现的问题:
1. ...
2. ...

解决方案:
1. ...
2. ...

下一步计划:
- [ ] ...
- [ ] ...
```

---

*最后更新: 2026-04-02*
