# Natural Language Driven Complex Analysis

> 基于自然语言的复杂数据分析与建模能力设计

## Capability Spectrum

```
┌────────────────────────────────────────────────────────────────────┐
│                    Capability Levels                                │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Level 1: Single Skill      "显示销售额分布"                        │
│  ─────────────────────      → distribution_analysis                │
│                                                                    │
│  Level 2: Multi-Skill       "分析各区域销售情况，找出异常值"         │
│  ─────────────────────      → categorical_analysis + outlier       │
│                                                                    │
│  Level 3: Pipeline          "清洗数据，建模预测下月销量"             │
│  ─────────────────────      → transform → feature_eng → ml_train   │
│                                                                    │
│  Level 4: Iterative         "帮我找一个最好的模型预测销量"           │
│  ─────────────────────      → try models → compare → optimize      │
│                                                                    │
│  Level 5: Conversational    "为什么华东区下降了？" (多轮对话)        │
│  ─────────────────────      → drill_down → explain → suggest       │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Architecture Enhancement

### 1. 新增 Planner Agent

```yaml
# agents/planner/AGENT.md
---
name: planner
display_name: 分析规划师
version: 2.0.0
description: 将复杂自然语言需求分解为可执行的 Skill 管道

capabilities:
  - task_decomposition
  - pipeline_generation
  - dependency_resolution
  - iterative_refinement
---
```

**核心逻辑**：

```python
# src/agents/planner.py
class AnalysisPlanner:
    """分析规划器 - NL → Execution Pipeline"""

    def plan(self, request: str, data_context: dict) -> ExecutionPipeline:
        """
        将自然语言请求转换为执行计划

        "清洗数据，建模预测下月销量"
        ↓
        Pipeline([
            Step("validate_data", mcp="mcp-data"),
            Step("clean_missing", skill="data_cleaner"),
            Step("feature_engineering", skill="feature_builder"),
            Step("train_model", skill="ml_regressor"),
            Step("predict", skill="ml_predict"),
            Step("visualize", mcp="mcp-chart")
        ])
        """
        # 1. 识别任务类型
        task_type = self._classify_task(request)
        # → "ml_prediction"

        # 2. 获取任务模板
        template = self._get_template(task_type)
        # → ML_PREDICTION_TEMPLATE

        # 3. 绑定数据上下文
        pipeline = template.bind(data_context)

        # 4. 优化执行顺序
        pipeline = self._optimize(pipeline)

        return pipeline
```

### 2. 任务模板库

```yaml
# config/task_templates.yaml

templates:
  # ==================== 数据分析类 ====================
  exploratory_analysis:
    name: "探索性数据分析"
    triggers: ["分析", "概览", "探索", "analyze", "eda"]
    steps:
      - skill: describe_statistics
        required: true
      - skill: distribution_analysis
        condition: "has_numeric"
      - skill: categorical_analysis
        condition: "has_categorical"
      - skill: correlation_analysis
        condition: "numeric_cols >= 2"

  segmentation_analysis:
    name: "客群细分分析"
    triggers: ["细分", "客群", "用户分群", "segment"]
    steps:
      - skill: clustering_preprocess
      - skill: kmeans_clustering
      - skill: cluster_profiling
      - mcp: mcp-chart.scatter_plot
        params:
          x: "PC1"
          y: "PC2"
          hue: "cluster"

  # ==================== 机器学习类 ====================
  ml_prediction:
    name: "预测建模"
    triggers: ["预测", "建模", "predict", "model", "forecast"]
    steps:
      - mcp: mcp-data.validate_data
      - skill: feature_engineering
      - skill: train_test_split
      - skill: auto_model_selection
      - skill: model_evaluation
      - mcp: mcp-chart.confusion_matrix
        condition: "task_type == classification"
      - skill: feature_importance
      - skill: model_explanation

  time_series_forecast:
    name: "时间序列预测"
    triggers: ["时间序列", "预测未来", "forecast", "trend"]
    steps:
      - skill: ts_decomposition
      - skill: stationarity_test
      - skill: arima_model
      - skill: forecast_plot

  # ==================== 数据处理类 ====================
  data_cleaning:
    name: "数据清洗"
    triggers: ["清洗", "清理", "clean", "处理缺失"]
    steps:
      - skill: missing_value_analysis
      - skill: outlier_detection
      - skill: data_imputation
      - skill: data_validation

  # ==================== 解释性分析类 ====================
  root_cause_analysis:
    name: "根因分析"
    triggers: ["为什么", "原因", "下降", "上升", "why"]
    steps:
      - skill: trend_decomposition
      - skill: dimension_drilldown
      - skill: statistical_test
      - skill: contribution_analysis
```

### 3. 新增 ML Skills

```
skills/builtin/
├── ml/
│   ├── feature_engineering/
│   │   ├── SKILL.md
│   │   └── generate.py
│   ├── auto_model_selection/
│   │   ├── SKILL.md
│   │   └── generate.py
│   ├── model_evaluation/
│   │   ├── SKILL.md
│   │   └── generate.py
│   └── model_explanation/
│       ├── SKILL.md
│       └── generate.py
├── time_series/
│   ├── ts_decomposition/
│   ├── arima_forecast/
│   └── trend_analysis/
└── data_cleaning/
    ├── missing_value_handler/
    ├── outlier_handler/
    └── data_transform/
```

### 4. MCP Server: mcp-ml

```yaml
# mcp-servers/mcp-ml/server.yaml

name: mcp-ml
version: 1.0.0
description: 机器学习执行服务器

tools:
  - name: train_model
    description: 训练机器学习模型
    parameters:
      - name: dataset_id
        type: string
      - name: target_column
        type: string
      - name: feature_columns
        type: array
      - name: model_type
        type: string
        enum: [auto, regression, classification, clustering]
      - name: algorithms
        type: array
        default: ["random_forest", "xgboost", "lightgbm"]
    returns:
      - name: model_id
      - name: metrics
      - name: best_algorithm

  - name: predict
    description: 使用训练好的模型进行预测
    parameters:
      - name: model_id
        type: string
      - name: data
        type: dataframe
    returns:
      - name: predictions
      - name: probabilities

  - name: explain_model
    description: 解释模型 (SHAP values)
    parameters:
      - name: model_id
        type: string
      - name: method
        type: string
        enum: [shap, lime, feature_importance]
    returns:
      - name: explanation
      - name: feature_importance_plot

  - name: cross_validate
    description: 交叉验证
    parameters:
      - name: model_id
        type: string
      - name: cv_folds
        type: integer
        default: 5
    returns:
      - name: cv_scores
      - name: mean_score
      - name: std_score
```

## Conversation Flow

### Example: "帮我预测下个月销量"

```
┌─────────────────────────────────────────────────────────────────┐
│ User: "帮我预测下个月销量"                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Coordinator:                                                    │
│   intent: "ml_prediction"                                       │
│   next_agent: "planner"                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Planner:                                                        │
│   task_type: "time_series_forecast"                             │
│   pipeline: [validate → features → train → predict → plot]      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator (执行管道):                                         │
│                                                                 │
│   [1/5] mcp-data.validate_data ✓                                │
│   [2/5] feature_engineering ✓                                   │
│   [3/5] mcp-ml.train_model                                      │
│         → Selected: Prophet                                     │
│         → MAPE: 8.2%                                            │
│   [4/5] mcp-ml.predict ✓                                        │
│   [5/5] mcp-chart.line_plot ✓                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Response:                                                       │
│   "已完成销量预测建模。使用 Prophet 模型，MAPE 8.2%。            │
│    预测下月销量: 12,500 单位 (置信区间: 11,200 - 13,800)。       │
│    [查看预测图表]"                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Example: "为什么华东区销量下降了？"

```
User: "为什么华东区销量下降了？"
        │
        ▼
Planner: task_type = "root_cause_analysis"
        │
        ▼
Pipeline:
  1. filter_region("华东") → 获取华东数据
  2. trend_decomposition → 分解趋势/季节/残差
  3. dimension_drilldown → 下钻到产品/渠道
  4. contribution_analysis → 计算各因素贡献
        │
        ▼
Response:
  "华东区销量下降 15%，主要原因：
   1. 产品A (-8%): 竞品降价影响
   2. 渠道B (-5%): 门店关闭 3 家
   3. 季节因素 (-2%): 正常波动

   建议：关注产品A定价策略，拓展渠道B线上覆盖。"
```

## Implementation Priority

| Phase | Capability | Effort |
|-------|------------|--------|
| P0 | Task templates + Planner Agent | 2 weeks |
| P1 | ML Skills (feature_eng, train, evaluate) | 2 weeks |
| P1 | mcp-ml server | 1 week |
| P2 | Time series Skills | 1 week |
| P2 | Root cause analysis Skills | 1 week |
| P3 | Conversational refinement (多轮) | 2 weeks |

## Key Design Decisions

1. **Template-first**: 常见任务用模板，复杂任务用 LLM 生成计划
2. **Skill 组合**: 每个 Skill 单一职责，通过管道组合
3. **MCP 执行**: 重计算（ML）在 MCP Server，轻量逻辑在 Skill
4. **渐进式反馈**: 长任务提供进度更新
5. **可解释**: 每步都生成可审计的日志

---

*Version: 2.0.0 | Last Updated: 2026-04-04*