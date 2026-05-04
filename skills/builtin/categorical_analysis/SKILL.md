---
name: categorical_analysis
display_name: 分类变量分析
description: 统计分类变量的值分布，生成条形图
version: 2.0.0
category: analysis
tags: [分类, 类别, value_counts, bar chart]
input_description: DataFrame with categorical columns
output_description: Value distribution and bar charts
code_template_file: generate.py
---

# 分类变量分析

## 功能概述

对分类变量（object、category类型）进行分析：
- 统计每个类别的值分布
- 生成条形图可视化
- 自动识别分类变量

## 输出内容

### 1. 值分布统计
- 每个分类变量的唯一值数量
- Top 15 最常见的值及其计数

### 2. 条形图可视化
- 当唯一值数量 ≤ 20 时自动生成
- 显示所有类别的计数
- 45度旋转标签，避免重叠

## 使用场景

- 理解分类变量的分布
- 检测类别不平衡
- 识别罕见类别
- 数据清洗前的探索

## 示例输出

```
【department 的值分布】
Sales         450
Engineering   350
Marketing     200
HR            150
Finance       100
```

## 注意事项

⚠️ **高基数分类变量**
- 如果唯一值 > 20，不会生成图表
- 建议考虑聚合或分组

⚠️ **缺失值**
- 缺失值会被包含在统计中
- 可以考虑在分析前处理缺失值

## 代码实现

本技能的代码生成函数位于 `generate.py` 文件中。
