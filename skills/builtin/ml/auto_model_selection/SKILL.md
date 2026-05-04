---
name: auto_model_selection
display_name: 自动模型选择
version: 1.0.0
description: 自动比较多个机器学习算法，选择最佳模型

category: ml
tags:
  - machine_learning
  - model_selection
  - auto_ml
  - classification
  - regression

inputs:
  - name: target_column
    type: str
    required: true
    description: 目标变量列名
  - name: feature_columns
    type: list[str]
    required: false
    description: 特征列名（可选，默认使用所有数值列）
  - name: task_type
    type: str
    required: false
    default: "auto"
    enum: [auto, classification, regression]
    description: 任务类型
  - name: algorithms
    type: list[str]
    required: false
    default: ["random_forest", "xgboost", "lightgbm", "logistic_regression"]
    description: 要比较的算法列表
  - name: cv_folds
    type: int
    required: false
    default: 5
    description: 交叉验证折数

outputs:
  - type: model_info
    description: 最佳模型信息
  - type: comparison_table
    description: 所有算法比较表
  - type: figure
    description: 模型比较图表

capabilities:
  - auto_task_detection
  - multi_model_comparison
  - cross_validation
  - hyperparameter_tuning

data_requirements:
  min_rows: 50
  required_columns: 2
  column_types: [numeric]

mcp_dependencies:
  - mcp-ml.train_model
  - mcp-ml.cross_validate
---

# 自动模型选择

## Purpose

自动比较多个机器学习算法，选择最适合当前数据的模型。

## Algorithm

```
1. 检测任务类型（分类 vs 回归）
   - 目标变量唯一值 <= 10 → 分类
   - 目标变量唯一值 > 10 或连续 → 回归

2. 准备数据
   - 自动选择特征列
   - 处理缺失值
   - 标准化（如需要）

3. 训练多个模型
   - Random Forest
   - XGBoost
   - LightGBM
   - Logistic/Linear Regression

4. 交叉验证比较
   - 5-fold CV (默认)
   - 记录 mean ± std

5. 选择最佳模型
   - 分类: 最高 F1 / AUC
   - 回归: 最低 RMSE / 最高 R²

6. 输出结果
   - 比较表
   - 最佳模型信息
   - 可视化
```

## Usage Examples

### 基础用法

```python
skill = registry.get("auto_model_selection")
code = skill.generate_code(
    target_column="sales",
    task_type="auto"
)
result = execute_code(code, df=data)
```

### 指定算法

```python
code = skill.generate_code(
    target_column="churn",
    algorithms=["random_forest", "xgboost"],
    cv_folds=10
)
```

## Output Format

```
📊 模型比较结果

任务类型: 二分类 (churn: 0/1)
特征数量: 15
交叉验证: 5-fold

┌────────────────────┬───────────┬───────────┬───────────┐
│ 算法               │ F1 Score  │ AUC       │ 训练时间  │
├────────────────────┼───────────┼───────────┼───────────┤
│ XGBoost            │ 0.87±0.03 │ 0.92±0.02 │ 2.3s      │
│ LightGBM           │ 0.86±0.04 │ 0.91±0.03 │ 1.1s      │
│ Random Forest      │ 0.84±0.05 │ 0.89±0.04 │ 5.7s      │
│ Logistic Regress.  │ 0.79±0.06 │ 0.84±0.05 │ 0.3s      │
└────────────────────┴───────────┴───────────┴───────────┘

✅ 最佳模型: XGBoost
   - F1 Score: 0.87
   - AUC: 0.92
   - 建议使用此模型进行预测
```

## Error Handling

| 错误 | 处理 |
|-----|------|
| 目标列不存在 | 返回可用列列表 |
| 数据行数 < 50 | 警告结果不可靠 |
| 无数值特征 | 建议先做特征工程 |