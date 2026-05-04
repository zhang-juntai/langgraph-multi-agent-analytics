---
name: correlation_analysis
display_name: 相关性分析
description: 计算数值特征间的Pearson相关系数，生成热力图，识别高相关性特征对
version: 2.0.0
category: analysis
tags: [相关性, 热力图, correlation, heatmap, pearson]
input_description: DataFrame with 2+ numeric columns
output_description: Correlation matrix and heatmap
code_template_file: generate.py
---

# 相关性分析

## 功能概述

计算并可视化数值特征之间的线性关系：
- Pearson 相关系数矩阵
- 相关性热力图
- 高相关性特征对识别（|r| > 0.7）

## 相关系数解释

Pearson 相关系数 r 的范围是 [-1, 1]：

- **r = 1**: 完全正线性相关
- **r > 0.7**: 强正相关
- **0.4 < r ≤ 0.7**: 中等正相关
- **0 < r ≤ 0.4**: 弱正相关
- **r = 0**: 无线性相关
- **-0.4 ≤ r < 0**: 弱负相关
- **-0.7 ≤ r < -0.4**: 中等负相关
- **r < -0.7**: 强负相关
- **r = -1**: 完全负线性相关

## 输出内容

### 1. 相关系数矩阵
显示所有数值列两两之间的相关系数

### 2. 相关性热力图
- 颜色映射：红色（正相关）↔ 蓝色（负相关）
- 数值标注：精确到小数点后2位
- 对称矩阵：只需关注上三角或下三角

### 3. 高相关性警告
自动识别 |r| > 0.7 的特征对，用于：
- 特征选择（去除冗余特征）
- 多重共线性检测
- 理解特征关系

## 使用场景

- 特征选择（去除高相关特征）
- 多重共线性检测（回归分析前）
- 变量关系探索
- 数据理解

## 注意事项

⚠️ **相关性 ≠ 因果性**
- 相关性只衡量线性关系
- 可能存在虚假相关（spurious correlation）
- 需要结合领域知识解释

⚠️ **前提假设**
- 线性关系（非线性关系需要其他方法）
- 连续变量（分类变量需要其他相关系数）
- 近似正态分布（极端值会影响结果）

## 示例输出

```
【Pearson 相关系数矩阵】
          age    salary  experience
age      1.00     0.65        0.92
salary   0.65     1.00        0.71
experience 0.92     0.71        1.00

【高相关性特征对 (|r| > 0.7)】
  age ↔ experience: r = 0.920
  experience ↔ salary: r = 0.710
```

## 代码实现

本技能的代码生成函数位于 `generate.py` 文件中。
