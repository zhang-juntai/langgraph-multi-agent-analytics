# Multi-Agent Data Analysis System - Architecture V2

> 2026 Engineering-Grade Agent Architecture Design
>
> Two-Layer Model: Skills (Knowledge) + MCP (Execution)

## Design Philosophy

### Core Principles

1. **Separation of Concerns**: Skills handle knowledge/workflows, MCP handles execution
2. **Git-Versioned Everything**: All configurations are markdown/yaml, PR-reviewable
3. **Token Efficiency**: Skills ~200 tokens vs MCP servers ~23,000-50,000 tokens
4. **Dynamic Discovery**: No hardcoded agent-skill mappings
5. **Observability First**: Built-in tracing, metrics, and debugging

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     Agent Orchestrator                           ││
│  │         (LangGraph State Machine - Lightened)                    ││
│  └─────────────────────────────────────────────────────────────────┘│
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  AGENTS.md    │    │  AGENTS.md    │    │  AGENTS.md    │
│  (Knowledge)  │    │  (Knowledge)  │    │  (Knowledge)  │
│               │    │               │    │               │
│ • Intent      │    │ • Workflow    │    │ • Decision    │
│ • Workflow    │    │ • Validation  │    │   Logic       │
│ • Guardrails  │    │ • Aggregation │    │ • Routing     │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SKILL LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Skill Registry                                ││
│  │   skills/builtin/*/SKILL.md  +  skills/custom/*/SKILL.md       ││
│  │                                                                  ││
│  │   • describe_statistics    • distribution_analysis              ││
│  │   • correlation_analysis   • categorical_analysis               ││
│  │   • outlier_detection      • load_data (NEW)                    ││
│  └─────────────────────────────────────────────────────────────────┘│
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER (MCP)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │   mcp-data  │  │  mcp-chart  │  │  mcp-sql    │  │ mcp-fileio  ││
│  │   Server    │  │   Server    │  │   Server    │  │   Server    ││
│  │             │  │             │  │             │  │             ││
│  │ • load_csv  │  │ • bar_plot  │  │ • query     │  │ • read      ││
│  │ • load_json │  │ • line_plot │  │ • insert    │  │ • write     ││
│  │ • validate  │  │ • heatmap   │  │ • execute   │  │ • exists    ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Agent Definition Format (AGENTS.md)

Each agent is defined in a markdown file with structured frontmatter:

```markdown
---
name: data_profiler
display_name: 数据探索分析专家
version: 2.0.0
description: 自动执行数据探索分析，选择合适的分析技能
capabilities:
  - intent_recognition
  - skill_selection
  - result_aggregation
dependencies:
  skills:
    - describe_statistics
    - distribution_analysis
    - correlation_analysis
    - categorical_analysis
    - outlier_detection
  mcp_servers:
    - mcp-data
    - mcp-chart
inputs:
  - name: state
    type: AnalysisState
    required: true
outputs:
  - name: profile_result
    type: ProfileResult
  - name: selected_skills
    type: list[str]
guardrails:
  max_iterations: 5
  timeout_seconds: 120
  fallback_agent: debugger
---

# Data Profiler Agent

## Role
你是一个数据分析专家，负责自动探索数据集的特征。

## Workflow

1. **接收意图**: 从 Coordinator 获取分析意图
2. **构建上下文**: 提取数据特征（行数、列类型、缺失值等）
3. **选择技能**: 使用 SkillSelector 动态选择合适的分析技能
4. **执行技能**: 调用选中的 Skills 生成代码
5. **汇总结果**: 整理分析报告

## Decision Logic

### 意图 → 技能映射

| 意图关键词 | 推荐技能 | 优先级 |
|-----------|---------|-------|
| 统计, 概览, 描述 | describe_statistics | P0 |
| 分布, 直方图 | distribution_analysis | P0 |
| 相关性, 关系 | correlation_analysis | P1 |
| 分类, 分组, 排名 | categorical_analysis | P1 |
| 异常值, 离群 | outlier_detection | P2 |

### 数据要求检查

```python
# 在执行前验证
def validate_data_context(context):
    if context.row_count == 0:
        return False, "数据为空"
    if not context.has_numeric and needs_numeric_analysis(intent):
        return False, "需要数值列"
    return True, ""
```

## Error Handling

- **技能执行失败**: 记录错误，继续执行其他技能
- **超时**: 返回已完成的结果 + 超时警告
- **数据不兼容**: 返回建议的替代技能

## Examples

### Input
```json
{
  "intent": "各大区订单数排名",
  "datasets": [{"name": "sales.csv", "rows": 1000}],
  "data_context": {
    "row_count": 1000,
    "has_categorical": true,
    "categorical_columns": ["region", "product"]
  }
}
```

### Output
```json
{
  "selected_skills": ["categorical_analysis"],
  "execution_results": [
    {
      "skill": "categorical_analysis",
      "status": "success",
      "output": "region 列有 5 个唯一值..."
    }
  ],
  "summary": "数据包含 5 个区域，华东地区订单最多..."
}
```
```

### 2. MCP Server Specifications

#### mcp-data Server

```yaml
# mcp-servers/mcp-data/server.yaml
name: mcp-data
version: 1.0.0
description: 数据加载与处理 MCP 服务器

tools:
  - name: load_csv
    description: 加载 CSV 文件，自动处理编码问题
    parameters:
      - name: file_path
        type: string
        required: true
      - name: encoding
        type: string
        default: "utf-8-sig"  # 自动处理 BOM
    returns:
      - name: dataframe
        type: pandas.DataFrame
      - name: metadata
        type: DataMetadata

  - name: load_excel
    description: 加载 Excel 文件
    parameters:
      - name: file_path
        type: string
      - name: sheet_name
        type: string
        default: null
    returns:
      - name: dataframe
        type: pandas.DataFrame

  - name: validate_data
    description: 验证数据质量
    parameters:
      - name: dataframe
        type: pandas.DataFrame
    returns:
      - name: validation_result
        type: ValidationResult

  - name: get_metadata
    description: 获取数据集元信息
    parameters:
      - name: dataframe
        type: pandas.DataFrame
    returns:
      - name: metadata
        type: DataMetadata
        fields:
          - row_count
          - column_count
          - column_types
          - missing_values
          - unique_counts
```

#### mcp-chart Server

```yaml
# mcp-servers/mcp-chart/server.yaml
name: mcp-chart
version: 1.0.0
description: 图表生成 MCP 服务器

tools:
  - name: bar_plot
    description: 生成条形图
    parameters:
      - name: data
        type: dict
      - name: x
        type: string
      - name: y
        type: string
      - name: title
        type: string
    returns:
      - name: figure
        type: matplotlib.figure.Figure

  - name: heatmap
    description: 生成热力图
    parameters:
      - name: correlation_matrix
        type: numpy.ndarray
      - name: labels
        type: list[string]
    returns:
      - name: figure
        type: matplotlib.figure.Figure

  - name: boxplot
    description: 生成箱线图
    parameters:
      - name: data
        type: pandas.DataFrame
      - name: columns
        type: list[string]
    returns:
      - name: figure
        type: matplotlib.figure.Figure
```

---

### 3. Skill Definition Format (Enhanced SKILL.md)

```markdown
---
name: categorical_analysis
display_name: 分类变量分析
version: 2.0.0
description: 分析分类变量的分布和统计量
category: analysis
tags:
  - 分类
  - 分组
  - 聚合
  - 排名

inputs:
  - name: group_by_column
    type: categorical
    required: false
    description: 分组依据的列（可选，默认分析所有分类列）

outputs:
  - type: table
    description: 值分布统计表
  - type: figure
    description: 条形图（当唯一值 <= 20 时）
    optional: true

capabilities:
  - group_by
  - count
  - rank
  - percentage
  - top_n

data_requirements:
  min_rows: 1
  required_columns: 1
  column_types:
    - categorical
    - string
    - object

mcp_dependencies:
  - mcp-data.validate_data
  - mcp-chart.bar_plot

conflicts:
  - time_series_analysis  # 不适用于时间序列
---

# 分类变量分析

## Purpose
分析数据集中的分类变量，统计各值的分布情况。

## Algorithm

1. 识别所有分类类型列 (object, category)
2. 对每列计算值频次
3. 计算百分比分布
4. 生成可视化（当唯一值 <= 20 时）

## Code Template

```python
def generate_code(**kwargs) -> str:
    return '''
# 分类变量分析
# ... (现有实现)
'''
```

## Usage Examples

### 基础用法
```python
skill = registry.get("categorical_analysis")
code = skill.generate_code()
result = execute_code(code, df=loaded_data)
```

### 指定列
```python
code = skill.generate_code(columns=["region", "category"])
```

## Error Handling

| 错误场景 | 处理方式 |
|---------|---------|
| 无分类列 | 返回警告，列出当前列类型 |
| 唯一值过多 | 仅显示统计表，跳过图表 |
| 数据为空 | Sanity Check 拒绝执行 |
```

---

## Directory Structure (V2)

```
multi-agent-data-analysis/
├── agents/                      # Agent 定义 (NEW)
│   ├── AGENTS.md               # Agent 注册表
│   ├── coordinator/
│   │   └── AGENT.md            # Coordinator Agent 定义
│   ├── data_parser/
│   │   └── AGENT.md
│   ├── data_profiler/
│   │   └── AGENT.md
│   ├── code_generator/
│   │   └── AGENT.md
│   ├── debugger/
│   │   └── AGENT.md
│   └── visualizer/
│       └── AGENT.md
│
├── skills/                      # Skill 定义 (Enhanced)
│   ├── builtin/
│   │   ├── load_data/
│   │   │   ├── SKILL.md        # Enhanced metadata
│   │   │   └── generate.py
│   │   ├── describe_statistics/
│   │   ├── distribution_analysis/
│   │   ├── correlation_analysis/
│   │   ├── categorical_analysis/
│   │   └── outlier_detection/
│   └── custom/                  # 用户自定义 Skills
│       └── .gitkeep
│
├── mcp-servers/                 # MCP 服务器 (NEW)
│   ├── mcp-data/
│   │   ├── server.yaml
│   │   ├── main.py
│   │   └── tests/
│   ├── mcp-chart/
│   │   ├── server.yaml
│   │   ├── main.py
│   │   └── tests/
│   └── mcp-fileio/
│       ├── server.yaml
│       └── main.py
│
├── src/
│   ├── core/
│   │   ├── orchestrator.py     # 轻量级编排器
│   │   ├── state.py            # 状态管理
│   │   └── context.py          # 上下文构建
│   ├── agents/
│   │   ├── loader.py           # Agent 加载器
│   │   ├── executor.py         # Agent 执行器
│   │   └── router.py           # 路由逻辑
│   ├── skills/
│   │   ├── registry.py         # Skill 注册表
│   │   ├── selector.py         # 智能选择器
│   │   ├── validator.py        # 数据验证器
│   │   └── executor.py         # Skill 执行器
│   ├── mcp/
│   │   ├── client.py           # MCP 客户端
│   │   ├── discovery.py        # MCP 服务发现
│   │   └── protocol.py         # MCP 协议实现
│   └── utils/
│       ├── encoding.py         # 编码处理 (BOM 等)
│       ├── logging.py          # 日志工具
│       └── tracing.py          # 追踪工具
│
├── config/
│   ├── agents.yaml             # Agent 配置
│   ├── mcp.yaml                # MCP 服务器配置
│   └── logging.yaml            # 日志配置
│
├── tests/
│   ├── agents/
│   ├── skills/
│   └── mcp/
│
└── docs/
    ├── ARCHITECTURE_V2.md      # 本文档
    ├── MIGRATION_GUIDE.md      # 迁移指南
    └── MCP_DEVELOPMENT.md      # MCP 开发指南
```

---

## Token Cost Comparison

| Layer | Token Count | Use Case |
|-------|-------------|----------|
| Agent (AGENTS.md) | ~300-500 | Workflow, decision logic |
| Skill (SKILL.md) | ~150-250 | Knowledge, templates |
| MCP Server | ~23,000-50,000 | Execution, API calls |

**Cost Optimization**: By using Skills for knowledge problems and MCP for execution, we achieve ~100x token reduction compared to putting all logic in MCP servers.

---

## Migration Path

### Phase 1: Foundation (Week 1)
- [ ] Create AGENTS.md format specification
- [ ] Implement Agent loader
- [ ] Enhance SKILL.md metadata format

### Phase 2: MCP Integration (Week 2)
- [ ] Implement mcp-data server
- [ ] Implement mcp-chart server
- [ ] Create MCP client

### Phase 3: Refactor Agents (Week 3)
- [ ] Migrate DataParser to AGENT.md + mcp-data
- [ ] Migrate DataProfiler to AGENT.md + dynamic skills
- [ ] Migrate CodeGenerator to AGENT.md

### Phase 4: Testing & Validation (Week 4)
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] Documentation

---

## Benefits

1. **Engineering Excellence**
   - Git-versioned configurations
   - PR-reviewable changes
   - Testable components

2. **Scalability**
   - Add new Skills without code changes
   - Add new MCP servers for new capabilities
   - Horizontal scaling of MCP servers

3. **Observability**
   - Clear separation of concerns
   - Traceable execution paths
   - Measurable performance

4. **Cost Efficiency**
   - ~100x token reduction
   - Smaller context windows
   - Faster inference

5. **Maintainability**
   - Declarative configurations
   - Clear ownership boundaries
   - Easy debugging