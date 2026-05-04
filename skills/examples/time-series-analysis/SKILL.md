---
name: time-series-analysis
display_name: 时间序列分析
description: 对时间序列数据进行趋势分析、季节性分解和移动平均计算
version: 1.0.0
category: analysis
tags: [时间序列, 趋势, 季节性, 移动平均, time series, trend]
---

# 时间序列分析

## 适用场景
- 用户数据包含日期/时间列
- 需要分析数据随时间的变化趋势
- 需要识别周期性模式

## 分析步骤

### 1. 数据准备
```python
# 确保日期列为 datetime 类型
date_col = df.select_dtypes(include=["datetime"]).columns
if len(date_col) == 0:
    # 尝试自动检测日期列
    for col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col])
            date_col = [col]
            break
        except:
            continue
```

### 2. 趋势分析
- 使用移动平均（7日/30日窗口）平滑数据
- 绘制原始数据 + 移动平均线

### 3. 季节性分解
- 使用 `seasonal_decompose` 分解为趋势、季节性和残差
- 如果 statsmodels 不可用，使用简单的周期聚合

### 4. 输出要求
- print() 输出关键统计数字
- plt.show() 显示趋势图
- 标注重要转折点
