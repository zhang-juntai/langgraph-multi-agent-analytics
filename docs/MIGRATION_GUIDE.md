# Migration Guide: LangGraph → Two-Layer Architecture

> 从当前 LangGraph 架构迁移到 Two-Layer (Skills + MCP) 架构

## 当前架构 vs 目标架构

| Aspect | 当前 (V1) | 目标 (V2) |
|--------|----------|----------|
| Agent 定义 | Python 类 + 硬编码 | AGENT.md (Markdown) |
| Skill 发现 | 硬编码列表 | 动态发现 (SkillSelector) |
| 工具执行 | 内联代码 | MCP 服务器 |
| 配置管理 | Python dict | YAML + Markdown |
| Token 成本 | 高 (全在 context) | 低 (~100x 减少) |

## Migration Phases

### Phase 1: 无破坏性准备 (Week 1)

**目标**: 建立新架构基础，不影响现有功能

#### Step 1.1: 创建 Agent 定义文件

```bash
# 为每个现有 Agent 创建 AGENT.md
agents/
├── coordinator/AGENT.md
├── data_parser/AGENT.md
├── data_profiler/AGENT.md
├── code_generator/AGENT.md
└── debugger/AGENT.md
```

**任务**:
- [ ] 从现有 Python 代码提取 workflow
- [ ] 编写 YAML frontmatter
- [ ] 添加 Examples

#### Step 1.2: 实现 Agent Loader

```python
# src/agents/loader.py
from src.agents.loader import AgentLoader

loader = AgentLoader()
agents = loader.load_all()

# 验证加载成功
assert "data_profiler" in agents
assert agents["data_profiler"].meta.version == "2.0.0"
```

**任务**:
- [x] 实现 AgentLoader 类
- [ ] 编写单元测试
- [ ] 集成到现有启动流程

#### Step 1.3: 增强 Skill 元数据

```yaml
# skills/builtin/describe_statistics/SKILL.md
---
name: describe_statistics
# ... 现有字段 ...
mcp_dependencies:  # NEW
  - mcp-data.validate_data
capabilities:     # NEW
  - statistics
  - summary
---
```

**任务**:
- [ ] 更新 5 个现有 Skill 的 SKILL.md
- [ ] 添加 capabilities 字段
- [ ] 添加 mcp_dependencies 字段

---

### Phase 2: MCP 服务器实现 (Week 2)

**目标**: 实现执行层，与现有代码并行运行

#### Step 2.1: mcp-data 服务器

```python
# mcp-servers/mcp-data/main.py
from mcp import MCPServer

server = MCPServer("mcp-data", port=8001)

@server.tool("load_csv")
async def load_csv(file_path: str, encoding: str = "utf-8-sig"):
    """加载 CSV，自动处理 BOM"""
    import pandas as pd

    # BOM 处理逻辑
    df = pd.read_csv(file_path, encoding=encoding)
    df.columns = [col.replace('\ufeff', '') for col in df.columns]

    return {
        "success": True,
        "row_count": len(df),
        "columns": list(df.columns),
        "preview": df.head().to_dict()
    }

if __name__ == "__main__":
    server.start()
```

**任务**:
- [ ] 实现 load_csv 工具
- [ ] 实现 load_excel 工具
- [ ] 实现 validate_data 工具
- [ ] 实现 get_metadata 工具

#### Step 2.2: mcp-chart 服务器

```python
# mcp-servers/mcp-chart/main.py
@server.tool("bar_plot")
async def bar_plot(dataset_id: str, x: str, y: str = None, **kwargs):
    """生成条形图"""
    # 获取数据
    df = data_registry.get(dataset_id)

    # 生成图表
    fig, ax = plt.subplots(figsize=(10, 6))
    df[x].value_counts().plot(kind='bar', ax=ax)

    # 保存并返回
    path = save_figure(fig)
    return {"success": True, "figure_path": path}
```

**任务**:
- [ ] 实现 bar_plot 工具
- [ ] 实现 histogram 工具
- [ ] 实现 heatmap 工具
- [ ] 实现 boxplot 工具

#### Step 2.3: MCP 客户端

```python
# src/mcp/client.py
class MCPClient:
    """MCP 客户端 - 与 MCP 服务器通信"""

    def __init__(self):
        self.connections = {}

    async def call(self, server: str, tool: str, **params):
        """调用 MCP 工具"""
        conn = await self.get_connection(server)
        return await conn.call_tool(tool, params)
```

**任务**:
- [ ] 实现 MCP 客户端
- [ ] 实现连接池
- [ ] 实现错误重试

---

### Phase 3: Agent 迁移 (Week 3)

**目标**: 逐个迁移 Agent 到新架构

#### Step 3.1: 迁移 DataProfiler

**Before (V1)**:
```python
# src/agents/data_profiler.py
def data_profiler_node(state: AnalysisState) -> dict:
    # 硬编码 skill 列表
    skills_to_run = ["describe_statistics", "distribution_analysis"]

    for skill_name in skills_to_run:
        skill = registry.get(skill_name)
        code = skill.generate_code()
        result = execute_code(code)
```

**After (V2)**:
```python
# src/agents/data_profiler.py (refactored)
from src.agents.loader import load_agent
from src.skills.selector import SkillSelector
from src.mcp.client import MCPClient

def data_profiler_node(state: AnalysisState) -> dict:
    # 1. 加载 Agent 定义
    agent_def = load_agent("data_profiler")

    # 2. 动态选择 Skills
    selector = SkillSelector()
    selected = selector.select_skills_for_intent(
        intent=state["intent"],
        data_context=build_context(state)
    )

    # 3. 通过 MCP 执行
    mcp = MCPClient()
    results = []

    for skill in selected[:agent_def.meta.guardrails["max_skills_per_run"]]:
        result = await mcp.call("mcp-data", skill.meta.name, **state)
        results.append(result)

    return {"results": results}
```

**任务**:
- [ ] 重构 data_profiler_node
- [ ] 验证功能一致
- [ ] 性能测试

#### Step 3.2: 迁移 DataParser

**Before**:
```python
# 硬编码数据加载逻辑
def data_parser_node(state):
    df = pd.read_csv(file_path, encoding='utf-8-sig')
    # ... BOM 处理 ...
```

**After**:
```python
# 委托给 MCP
def data_parser_node(state):
    mcp = MCPClient()
    result = await mcp.call("mcp-data", "load_csv",
        file_path=state["file_path"],
        encoding="utf-8-sig"
    )
    return {"dataset_info": result}
```

**任务**:
- [ ] 重构 data_parser_node
- [ ] 迁移 BOM 处理到 mcp-data
- [ ] 验证加载逻辑

#### Step 3.3: 迁移其他 Agents

按优先级迁移:
1. [x] DataProfiler
2. [ ] DataParser
3. [ ] CodeGenerator
4. [ ] Debugger
5. [ ] Coordinator

---

### Phase 4: 清理与测试 (Week 4)

**目标**: 移除旧代码，完善测试

#### Step 4.1: 移除冗余代码

```bash
# 删除已迁移的硬编码逻辑
git rm src/agents/data_profiler_v1.py
git rm src/agents/data_parser_v1.py
```

**任务**:
- [ ] 移除硬编码 skill 列表
- [ ] 移除内联 BOM 处理
- [ ] 更新 import 路径

#### Step 4.2: 集成测试

```python
# tests/integration/test_v2_architecture.py
def test_skill_dynamic_discovery():
    """测试动态 Skill 发现"""
    selector = SkillSelector()
    skills = selector.select_skills_for_intent("排名", {"has_categorical": True})
    assert "categorical_analysis" in [s.meta.name for s in skills]

def test_mcp_data_loading():
    """测试 MCP 数据加载"""
    mcp = MCPClient()
    result = await mcp.call("mcp-data", "load_csv", file_path="test.csv")
    assert result["success"] is True
```

**任务**:
- [ ] 编写集成测试
- [ ] 性能基准测试
- [ ] 文档更新

---

## Rollback Plan

如果迁移出现问题:

```bash
# 1. 回滚到 V1
git checkout v1.x.x

# 2. 禁用 MCP
export DISABLE_MCP=true

# 3. 重启服务
python main.py --use-v1-agents
```

## Metrics to Track

| Metric | V1 Baseline | V2 Target |
|--------|-------------|-----------|
| Token per request | ~15,000 | ~1,500 |
| Agent load time | ~200ms | ~50ms |
| Skill selection accuracy | N/A (hardcoded) | >90% |
| MCP call latency | N/A | <100ms |

## Checklist

### Pre-Migration
- [ ] 所有 AGENT.md 文件创建完成
- [ ] AgentLoader 测试通过
- [ ] MCP 服务器本地测试通过

### During Migration
- [ ] 每个 Agent 迁移后独立测试
- [ ] 保持 V1 代码可用作 fallback
- [ ] 记录所有 API 变更

### Post-Migration
- [ ] 移除所有 V1 代码
- [ ] 更新文档
- [ ] 性能验证

---

*Last Updated: 2026-04-04*