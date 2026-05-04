---
name: describe_statistics
display_name: 描述性统计分析
description: 对数据集进行全面的描述性统计，包括均值、标准差、分位数、缺失值和唯一值统计
version: 2.0.0
category: analysis
tags: [统计, 描述, 概览, 缺失值, mean, std, describe]
input_description: DataFrame
output_description: 统计摘要文本
code_template_file: generate.py
---

# 描述性统计分析

## 功能概述

生成完整的描述性统计分析代码，包括：
- 基本统计量（均值、标准差、最小值、最大值、分位数）
- 数据类型分布统计
- 缺失值检测和分析
- 唯一值统计

## 参数说明

- `columns`: 指定分析的列名（可选，默认所有数值列）
  - 类型: str 或 list
  - 默认值: "None"（分析所有数值列）
  - 示例: `columns="['age', 'salary']"` 或 `columns="None"`

## 输出内容

### 1. 基本统计量
使用 `df.describe()` 生成：
- count（非空值数量）
- mean（均值）
- std（标准差）
- min（最小值）
- 25%, 50%, 75%（分位数）
- max（最大值）

### 2. 数据类型分布
统计每列的数据类型及其数量

### 3. 缺失值统计
- 每列的缺失值数量
- 缺失值百分比
- 只显示有缺失值的列

### 4. 唯一值统计
- 每列的唯一值数量（nunique）
- 帮助识别分类变量和连续变量

## 使用场景

- 数据加载后的初步探索
- 数据质量检查
- 特征筛选前的统计分析
- 识别数据中的异常模式

## 示例输出

```
============================================================
📊 描述性统计分析
============================================================

【基本统计量】
              count        mean        std   min    25%   50%    75%   max
age          1000.0       35.50       12.30  18.0  28.0  35.0  43.0  65.0
salary       1000.0    50000.0    15000.0  20000 40000 50000 60000 90000

【数据类型分布】
int64      5
object     2
float64    1

【缺失值统计】
           缺失数  缺失率(%)
phone        50        5.0
email        20        2.0

【唯一值统计】
  age: 48 个唯一值
  salary: 856 个唯一值
  department: 5 个唯一值
```

## 代码实现

本技能的代码生成函数位于 `generate.py` 文件中，调用方式：

```python
from skills.builtin.describe_statistics.generate import generate_code

# 生成分析所有数值列的代码
code = generate_code(columns="None")

# 生成分析指定列的代码
code = generate_code(columns="['age', 'salary']")
```
