---
name: code_generator
display_name: 代码架构师
version: 2.0.0
description: 根据用户自然语言需求，动态生成并执行 Python 分析代码

capabilities:
  - natural_language_to_code
  - skill_context_injection
  - sandbox_execution
  - code_extraction

dependencies:
  skills:
    - name: (dynamic)
      required: false
      description: 动态注入所有可用 Skill 描述
  mcp_servers:
    - mcp-data

inputs:
  - name: state
    type: AnalysisState
    required: true
    description: 包含用户消息和数据集的状态

outputs:
  - name: current_code
    type: str
    description: 生成的 Python 代码
  - name: code_result
    type: dict
    description: 执行结果
  - name: figures
    type: list
    description: 生成的图表列表

guardrails:
  max_code_length: 10000
  execution_timeout_seconds: 60
---

# Code Generator Agent

## Role

你是一个代码架构师，负责将用户的自然语言需求转换为可执行的 Python 分析代码。

## Core Principle

> **开发层不包含任何数据分析算法，100% 由 LLM 生成。**

## Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  构建上下文 │ ──▶ │  调用 LLM   │ ──▶ │  提取代码   │ ──▶ │  沙箱执行   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Step 1: 构建上下文

```python
system_prompt = CODE_GEN_SYSTEM_PROMPT.format(
    dataset_info=_build_dataset_info(state),
    skill_descriptions=registry.get_skill_descriptions(),
)
```

注入信息：
- 当前数据集结构（行数、列名、类型）
- 可用 Skill 列表及描述
- 执行环境配置

### Step 2: 调用 LLM

```python
llm_messages = [
    SystemMessage(content=system_prompt),
    *recent_user_messages
]
response = llm.invoke(llm_messages)
```

### Step 3: 提取代码

```python
def _extract_code_from_response(content: str) -> str:
    """处理多种响应格式"""

    # 1. 移除 <think/> 标签
    content = re.sub(r"<think.*?</think >", "", content, flags=re.DOTALL)

    # 2. 提取 ```python 块
    if blocks := re.findall(r"```(?:python|py)\s*\n(.*?)```", content, re.DOTALL):
        return max(blocks, key=len).strip()

    # 3. 无标记，返回原始内容
    return content.strip()
```

### Step 4: 沙箱执行

```python
result = execute_code(
    code=generated_code,
    datasets=datasets,
)

return {
    "current_code": generated_code,
    "code_result": result,
    "figures": result.get("figures", []),
}
```

## System Prompt Template

```python
CODE_GEN_SYSTEM_PROMPT = """你是一个专业的 Python 数据分析代码生成器。

## 执行环境
- 数据已加载为 DataFrame，变量名为 `df`
- 已导入：pandas as pd, numpy as np, matplotlib, seaborn
- matplotlib 的 plt.show() 会自动保存图表
- 中文字体已配置

## 当前数据集信息
{dataset_info}

## 可用的分析技能（参考）
{skill_descriptions}

## 代码规范
1. 只输出纯 Python 代码，不要 markdown 标记
2. 使用 print() 输出关键结果
3. 图表务必调用 plt.show()
4. 处理可能的异常（空值、类型不匹配）
"""
```

## Error Handling

### 代码为空

```python
if not generated_code:
    return {
        "messages": [AIMessage(content="⚠️ 代码生成失败，请重新描述需求")],
        "error": "代码为空"
    }
```

### 执行失败

```python
if not result["success"]:
    # 触发 Debugger Agent
    return {
        "messages": ["⚠️ 代码执行出错，正在尝试自动修复..."],
        "retry_count": 0,
    }
```

## Examples

### Example 1: 简单统计

**Input:**
```
用户: "统计各区域的销售总额"
```

**Output Code:**
```python
# 统计各区域销售总额
region_sales = df.groupby('region')['amount'].sum().sort_values(ascending=False)
print("各区域销售总额:")
print(region_sales.to_string())

# 可视化
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
region_sales.plot(kind='bar')
plt.title('各区域销售总额')
plt.xlabel('区域')
plt.ylabel('销售额')
plt.tight_layout()
plt.show()
```

### Example 2: 复杂分析

**Input:**
```
用户: "分析销售趋势，找出异常点"
```

**Output Code:**
```python
# 时间序列分析
df['date'] = pd.to_datetime(df['date'])
daily_sales = df.groupby('date')['amount'].sum()

# 移动平均
ma_7 = daily_sales.rolling(window=7).mean()

# 异常检测 (IQR 方法)
Q1, Q3 = daily_sales.quantile([0.25, 0.75])
IQR = Q3 - Q1
lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
anomalies = daily_sales[(daily_sales < lower) | (daily_sales > upper)]

print(f"检测到 {len(anomalies)} 个异常点")
print(anomalies.to_string())

# 可视化
plt.figure(figsize=(14, 6))
plt.plot(daily_sales.index, daily_sales.values, label='日销售额')
plt.plot(ma_7.index, ma_7.values, label='7日移动平均', color='red')
plt.scatter(anomalies.index, anomalies.values, color='orange', s=100, label='异常点')
plt.legend()
plt.title('销售趋势与异常检测')
plt.tight_layout()
plt.show()
```

## V2 Enhancement

在 V2 架构中，CodeGenerator 可以通过 MCP 调用预定义的分析模板：

```python
# Before (V1) - 完全由 LLM 生成
response = llm.invoke(messages)

# After (V2) - 可选模板 + LLM 补充
template = mcp.call("mcp-data", "get_template", {"name": "trend_analysis"})
code = llm.invoke(messages + [HumanMessage(content=f"参考模板:\n{template}")])
```

**好处**:
- 复杂分析有模板参考
- 减少幻觉
- 提高代码质量