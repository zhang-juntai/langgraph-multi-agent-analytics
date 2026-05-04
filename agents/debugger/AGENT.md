---
name: debugger
display_name: 代码纠错专家
version: 2.0.0
description: 自动分析执行失败的代码，调用 LLM 修复并重新执行

capabilities:
  - error_analysis
  - code_repair
  - retry_management
  - fallback_handling

dependencies:
  agents:
    - name: code_generator
      relation: receives_failures_from

inputs:
  - name: state
    type: AnalysisState
    required: true
    description: 包含失败代码和错误信息的状态

outputs:
  - name: current_code
    type: str
    description: 修复后的代码
  - name: code_result
    type: dict
    description: 重新执行的结果
  - name: retry_count
    type: int
    description: 当前重试次数

guardrails:
  max_retries: 3
  max_fix_attempts_per_error: 2
---

# Debugger Agent

## Role

你是一个代码纠错专家，当代码执行失败时自动分析错误、修复代码并重新执行。

## Design Principle

> **独立于 CodeGenerator，形成"生成 → 执行 → 失败 → 修复 → 重试"闭环**

## Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  检查重试   │ ──▶ │  构建调试   │ ──▶ │  LLM 修复   │ ──▶ │  重新执行   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Step 1: 检查重试次数

```python
if retry_count >= MAX_RETRIES:
    return {
        "messages": [AIMessage(
            content=f"⚠️ 代码经过 {MAX_RETRIES} 次自动修复仍然失败。\n"
                    f"建议：\n"
                    f"1. 请用更具体的语言描述你的需求\n"
                    f"2. 检查数据文件格式是否正确\n"
                    f"3. 尝试将复杂需求拆分为多个简单步骤"
        )],
        "retry_count": 0,  # 重置
    }
```

### Step 2: 构建调试上下文

```python
debug_context = f"""
## 原始代码
```python
{original_code}
```

## 错误信息
```
{stderr}
```

## 数据集信息
文件: {file_name}, 列: {columns}, 类型: {dtypes}

请修复代码并输出完整的可运行版本。
"""
```

### Step 3: LLM 修复

```python
response = llm.invoke([
    SystemMessage(content=DEBUGGER_SYSTEM_PROMPT),
    HumanMessage(content=debug_context),
])
fixed_code = _extract_code(response.content)
```

### Step 4: 重新执行

```python
result = execute_code(code=fixed_code, datasets=datasets)

if result["success"]:
    return {
        "messages": [AIMessage(content=f"🔧 代码已自动修复并执行成功")],
        "current_code": fixed_code,
        "code_result": result,
        "retry_count": 0,
    }
else:
    return {
        "retry_count": retry_count + 1,
        # 继续修复循环
    }
```

## Common Fix Patterns

| 错误类型 | 修复策略 |
|---------|---------|
| 列名不存在 | 检查实际列名并修正 |
| TypeError | 添加类型转换 |
| KeyError | 使用 df.get() 或检查列存在 |
| 缺失值 NaN | 添加 dropna() 或 fillna() |
| 编码问题 | 指定 encoding='utf-8-sig' |
| 图表中文乱码 | 配置 SimHei 字体 |
| 空数据 | 添加数据检查 |

## System Prompt

```python
DEBUGGER_SYSTEM_PROMPT = """你是一个 Python 代码调试专家。

## 修复规范
1. 只输出修复后的完整 Python 代码，不要 markdown 标记
2. 不要只修改出错的那一行，要给出完整可运行的代码
3. 常见问题处理：
   - 列名不存在 → 检查实际列名并修正
   - 类型错误 → 添加类型转换
   - 缺失值 → 添加 dropna() 或 fillna()
   - 编码问题 → 指定 encoding
   - 图表中文乱码 → 检查字体配置
4. 在修复代码的关键位置添加注释说明修复内容
"""
```

## Routing Logic

```python
def should_retry(state: AnalysisState) -> str:
    """条件路由函数"""
    code_result = state.get("code_result", {})
    retry_count = state.get("retry_count", 0)

    # 执行成功 → 结束
    if code_result.get("success", False):
        return "done"

    # 超过重试次数 → 结束
    if retry_count >= MAX_RETRIES:
        return "done"

    # 继续修复
    return "retry"
```

## Examples

### Example 1: 列名错误修复

**原始代码:**
```python
df.groupby('Region')['Sales'].sum()  # 列名大小写错误
```

**错误信息:**
```
KeyError: "Column 'Region' not found. Available columns: ['region', 'sales']"
```

**修复后代码:**
```python
# 修复: 使用正确的列名
df.groupby('region')['sales'].sum()
```

### Example 2: 类型错误修复

**原始代码:**
```python
df['amount'].mean()  # amount 列是字符串类型
```

**错误信息:**
```
TypeError: Could not convert string to float
```

**修复后代码:**
```python
# 修复: 转换为数值类型
df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
df['amount'].mean()
```

## V2 Enhancement

在 V2 架构中，Debugger 可以访问更多上下文：

```python
# V2: 通过 MCP 获取数据诊断信息
diagnosis = await mcp.call("mcp-data", "diagnose", {
    "dataset_id": active_dataset["id"],
    "error_type": error_type,
})

# 使用诊断结果辅助修复
system_prompt += f"\n\n## 数据诊断\n{diagnosis}"
```

**好处**:
- 更精准的错误定位
- 数据类型建议
- 列名映射建议