# Agent Registry

> Multi-Agent Data Analysis System - Agent Definitions

## Overview

本系统采用 **Two-Layer Architecture**:
- **Agents (AGENTS.md)**: 知识层 - 工作流、决策逻辑、guardrails
- **MCP Servers**: 执行层 - API 调用、数据处理、外部系统

## Registered Agents

| Agent | Role | Primary Skills | MCP Dependencies |
|-------|------|----------------|------------------|
| [coordinator](./coordinator/AGENT.md) | 意图识别与路由 | - | - |
| [planner](./planner/AGENT.md) | 分析规划与任务分解 | Task Templates | - |
| [data_parser](./data_parser/AGENT.md) | 数据加载与解析 | load_data | mcp-data |
| [data_profiler](./data_profiler/AGENT.md) | 数据探索分析 | describe_statistics, distribution_analysis, correlation_analysis, categorical_analysis, outlier_detection | mcp-data, mcp-chart |
| [code_generator](./code_generator/AGENT.md) | 代码生成 | (dynamic) | mcp-data |
| [debugger](./debugger/AGENT.md) | 故障排除与自修复 | (diagnostic) | mcp-data |
| [visualizer](./visualizer/AGENT.md) | 可视化生成 | (chart skills) | mcp-chart |

## Agent Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Loading   │ ──▶ │  Register   │ ──▶ │   Ready     │
│  (from md)  │     │  (to graph) │     │  (execute)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Convention

1. **One Agent = One Directory**: 每个 Agent 有独立的目录
2. **AGENT.md Required**: 必须包含 Agent 定义文件
3. **YAML Frontmatter**: 元数据使用 YAML 格式
4. **Git-Versioned**: 所有配置纳入版本控制

## Usage

```python
from src.agents.loader import AgentLoader

loader = AgentLoader()
agents = loader.load_all()

# 获取特定 Agent
profiler = agents.get("data_profiler")

# 执行 Agent
result = await profiler.execute(state)
```

## Adding New Agent

1. 创建目录: `agents/my_agent/`
2. 创建定义: `agents/my_agent/AGENT.md`
3. 实现逻辑: `src/agents/my_agent.py` (可选)
4. 注册到本文件

---

*Version: 2.0.0 | Last Updated: 2026-04-04*