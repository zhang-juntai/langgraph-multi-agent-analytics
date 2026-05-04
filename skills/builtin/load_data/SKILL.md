---
name: load_data
display_name: 数据加载与健康检查
description: 智能加载数据文件，自动处理编码问题（BOM），生成数据集元信息和健康报告
version: 1.0.0
category: utility
tags: [加载, 编码, BOM, 解析, CSV, Excel, JSON, 健康检查]
input_description: 文件路径或 DataFrame
output_description: 加载状态 + 数据集元信息
code_template_file: generate.py
inputs:
  - name: file_path
    type: string
    required: false
    description: 要加载的文件路径（如果已有 df 则不需要）
  - name: encoding
    type: string
    required: false
    default: "auto"
    description: 文件编码，auto 为自动检测
outputs:
  - type: metadata
    description: 数据集元信息（行数、列数、类型等）
  - type: health_report
    description: 数据健康检查报告
capabilities:
  - load_csv
  - load_excel
  - load_json
  - detect_encoding
  - clean_bom
  - health_check
data_requirements:
  min_rows: 0
  required_columns: 0
---

# 数据加载与健康检查 Skill

## 功能概述

智能加载数据文件并生成健康报告，包括：

1. **编码检测**：自动检测文件编码，优先处理 BOM（utf-8-sig）
2. **BOM 清理**：清理列名中的 BOM 字符（`\ufeff`）
3. **数据加载**：支持 CSV、Excel、JSON 格式
4. **元信息生成**：行数、列数、数据类型、缺失值统计
5. **健康检查**：空数据、空列、重复行、异常类型检测

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| file_path | str | None | 文件路径（可选，如果已有 df） |
| encoding | str | "auto" | 编码方式，auto 自动检测 |

## 使用场景

- 数据加载后的第一步
- 数据质量检查
- 为后续分析准备数据上下文
- 处理来自 Excel 导出的带 BOM 的 CSV

## BOM 处理机制

BOM（Byte Order Mark）是 UTF-8 文件开头的不可见字符 `\ufeff`。

**问题**：
- Excel 导出的 CSV 通常带 BOM
- BOM 会污染第一列的列名
- 导致 `select_dtypes()` 等操作失败

**解决方案**：
1. 优先使用 `utf-8-sig` 编码读取
2. 读取后清理列名中的 `\ufeff`
3. 双重保障确保 BOM 被移除

## 示例输出

```
============================================================
📁 数据加载与健康检查
============================================================

【基本信息】
文件名: orders.csv
行数: 1,000
列数: 8
内存占用: 62.5 KB

【列信息】
列名              类型      非空数    唯一值
order_id         int64     1000      1000
customer_name    object    1000      156
region           object    1000      5
amount           float64   998       423
status           object    1000      3

【健康检查】
✅ 数据不为空
✅ 无全空列
⚠️ 发现 2 个缺失值 (0.02%)
⚠️ 发现 5 行重复数据 (0.5%)
✅ 无可疑的类型混合

【建议】
- 考虑处理 amount 列的缺失值
- 考虑去重处理
```

## 代码实现

本技能的代码生成函数位于 `generate.py` 文件中。
