# 项目技能文档

## 概述

本项目实现了一个完整的技能体系，支持 SKILL.md + generate.py 的标准格式。所有技能通过全局注册表 [`SkillRegistry`](src/skills/base.py#L129) 进行管理，支持渐进式披露（Progressive Disclosure）设计。

### 技能分类体系

```python
class SkillCategory(str, Enum):
    ANALYSIS = "analysis"           # 数据分析类
    TRANSFORM = "transform"         # 数据变换类
    VISUALIZATION = "visualization" # 可视化类
    MODELING = "modeling"          # 建模类
    UTILITY = "utility"            # 工具类
```

### 技能统计

| 分类 | 数量 | 说明 |
|------|------|------|
| 内置技能 | 5 | 核心数据分析技能 |
| 官方技能 | 3 | Claude 官方文件处理技能 |
| 社区技能 | 1 | 分析指标技能 |
| 示例技能 | 1 | 时间序列分析示例 |
| **总计** | **10** | 完整可用的技能 |

---

## 技能格式标准

### 目录结构

每个技能遵循统一的目录结构：

```
skill_name/
├── SKILL.md           # 必需：技能描述文档
└── generate.py        # 可选：代码生成函数
```

### SKILL.md 格式

```yaml
---
name: skill_name
display_name: 技能显示名称
description: 技能功能描述
version: 2.0.0
category: analysis
tags: [标签1, 标签2]
input_description: 输入说明
output_description: 输出说明
code_template_file: generate.py  # 可选
---

# 技能标题

## 功能概述
详细的功能说明...

## 参数说明
- 参数1: 说明
- 参数2: 说明

## 使用场景
- 场景1
- 场景2

## 示例输出
输出示例...
```

### generate.py 格式

```python
def generate_code(**kwargs) -> str:
    """
    生成技能代码

    Args:
        **kwargs: 技能参数

    Returns:
        str: 生成的 Python 代码字符串
    """
    # 实现代码生成逻辑
    return generated_code
```

### Sanity Check 模式（推荐）

所有内置 Skill 模板均包含 **Sanity Check**，用于在执行前验证数据有效性：

```python
def generate_code(**kwargs) -> str:
    return '''
# === Sanity Check: 验证数据 ===
if df is None:
    print("❌ 数据未加载 (df is None)")
elif df.empty:
    print("❌ 数据为空 (df is empty)")
else:
    print(f"✅ 数据有效: {len(df)} 行, {len(df.columns)} 列")

    # 执行实际分析逻辑...
    # ...
'''
```

**Sanity Check 的作用**：
- 提前检测空数据或未加载状态
- 提供清晰的错误提示给用户
- 避免后续代码因数据问题崩溃产生难以理解的错误

**已实现的 Skill**：
- `describe_statistics` - [generate.py](skills/builtin/describe_statistics/generate.py)
- `distribution_analysis` - [generate.py](skills/builtin/distribution_analysis/generate.py)
- `correlation_analysis` - [generate.py](skills/builtin/correlation_analysis/generate.py)

---

## 内置技能

### 1. 描述性统计分析 (describe_statistics)

**基本信息**
- **名称**: `describe_statistics`
- **显示名称**: 描述性统计分析
- **功能**: 对数据集进行全面的描述性统计，包括均值、标准差、分位数、缺失值和唯一值统计
- **分类**: analysis
- **标签**: ["统计", "描述", "概览", "缺失值", "mean", "std", "describe"]
- **版本**: 2.0.0
- **目录**: [`skills/builtin/describe_statistics/`](skills/builtin/describe_statistics/)

**测试状态**: ✅ 已测试

**被使用于**:
- Data Profiler - 实际执行
- Coordinator/CodeGenerator/Visualizer - 提示词增强

**功能特点**
- 基本统计量（均值、标准差、分位数）
- 数据类型分布统计
- 缺失值详细统计
- 唯一值统计

**使用场景**
- 数据加载后的初步探索
- 数据质量检查
- 特征筛选前的统计分析

**源文件**:
- [SKILL.md](skills/builtin/describe_statistics/SKILL.md)
- [generate.py](skills/builtin/describe_statistics/generate.py)

---

### 2. 数据分布分析 (distribution_analysis)

**基本信息**
- **名称**: `distribution_analysis`
- **显示名称**: 数据分布分析
- **功能**: 分析数值特征的分布情况，生成直方图，计算偏度和峰度
- **分类**: analysis
- **标签**: ["分布", "直方图", "偏度", "峰度", "histogram", "skew"]
- **版本**: 2.0.0
- **目录**: [`skills/builtin/distribution_analysis/`](skills/builtin/distribution_analysis/)

**测试状态**: ✅ 已测试

**被使用于**:
- Data Profiler - 实际执行
- Coordinator/CodeGenerator/Visualizer - 提示词增强

**功能特点**
- 生成直方图可视化分布
- 计算偏度（skewness）- 衡量分布对称性
- 计算峰度（kurtosis）- 衡量尾部厚度
- 多子图布局（3列网格）

**使用场景**
- 了解数值特征的分布形态
- 检测正态分布假设的违反
- 识别偏态和峰态异常

**源文件**:
- [SKILL.md](skills/builtin/distribution_analysis/SKILL.md)
- [generate.py](skills/builtin/distribution_analysis/generate.py)

---

### 3. 相关性分析 (correlation_analysis)

**基本信息**
- **名称**: `correlation_analysis`
- **显示名称**: 相关性分析
- **功能**: 计算数值特征间的 Pearson 相关系数，生成热力图，识别高相关性特征对
- **分类**: analysis
- **标签**: ["相关性", "热力图", "correlation", "heatmap", "pearson"]
- **版本**: 2.0.0
- **目录**: [`skills/builtin/correlation_analysis/`](skills/builtin/correlation_analysis/)

**测试状态**: ✅ 已测试

**被使用于**:
- Data Profiler - 实际执行
- Coordinator/CodeGenerator/Visualizer - 提示词增强

**功能特点**
- Pearson 相关系数矩阵
- 相关性热力图（红色正相关，蓝色负相关）
- 高相关性特征对识别（|r| > 0.7）
- 相关系数范围解释

**使用场景**
- 特征选择（去除高相关特征）
- 多重共线性检测
- 变量关系探索

**源文件**:
- [SKILL.md](skills/builtin/correlation_analysis/SKILL.md)
- [generate.py](skills/builtin/correlation_analysis/generate.py)

---

### 4. 分类变量分析 (categorical_analysis)

**基本信息**
- **名称**: `categorical_analysis`
- **显示名称**: 分类变量分析
- **功能**: 统计分类变量的值分布，生成条形图
- **分类**: analysis
- **标签**: ["分类", "类别", "value_counts", "bar chart"]
- **版本**: 2.0.0
- **目录**: [`skills/builtin/categorical_analysis/`](skills/builtin/categorical_analysis/)

**测试状态**: ✅ 已测试（但未被 Data Profiler 执行）

**被使用于**:
- Coordinator/CodeGenerator/Visualizer - 提示词增强
- ⚠️ 未被 Data Profiler 执行

**功能特点**
- 统计每个分类变量的唯一值数量
- Top 15 最常见的值及其计数
- 当唯一值 ≤ 20 时自动生成条形图
- 45度旋转标签，避免重叠

**使用场景**
- 理解分类变量的分布
- 检测类别不平衡
- 识别罕见类别
- 数据清洗前的探索

**源文件**:
- [SKILL.md](skills/builtin/categorical_analysis/SKILL.md)
- [generate.py](skills/builtin/categorical_analysis/generate.py)

---

### 5. 异常值检测 (outlier_detection)

**基本信息**
- **名称**: `outlier_detection`
- **显示名称**: 异常值检测
- **功能**: 使用 IQR 方法检测数值特征中的异常值，生成箱线图
- **分类**: analysis
- **标签**: ["异常值", "离群点", "IQR", "boxplot", "outlier"]
- **版本**: 2.0.0
- **目录**: [`skills/builtin/outlier_detection/`](skills/builtin/outlier_detection/)

**测试状态**: ✅ 已测试（但未被 Data Profiler 执行）

**被使用于**:
- Coordinator/CodeGenerator/Visualizer - 提示词增强
- ⚠️ 未被 Data Profiler 执行

**功能特点**
- IQR（四分位距）方法检测异常值
- 计算异常值数量和百分比
- 提供异常值的合理范围
- 生成箱线图可视化（最多5个数值列）

**使用场景**
- 数据清洗前检测异常值
- 识别数据录入错误
- 统计建模前的异常值处理
- 质量控制

**源文件**:
- [SKILL.md](skills/builtin/outlier_detection/SKILL.md)
- [generate.py](skills/builtin/outlier_detection/generate.py)

---

## 官方技能 (anthropics)

来自 [anthropics/skills](https://github.com/anthropics/skills) 官方仓库的文件处理技能。

### 1. Excel 处理 (xlsx)

**基本信息**
- **名称**: `xlsx`
- **功能**: Excel 文件处理和分析
- **来源**: anthropics/skills
- **目录**: [`skills/anthropics/xlsx/`](skills/anthropics/xlsx/)

**测试状态**: ✅ 已加载

**功能**
- Excel 文件读取和写入
- 数据透视表生成
- 格式化和样式设置

### 2. PDF 处理 (pdf)

**基本信息**
- **名称**: `pdf`
- **功能**: PDF 文件处理和分析
- **来源**: anthropics/skills
- **目录**: [`skills/anthropics/pdf/`](skills/anthropics/pdf/)

**测试状态**: ✅ 已加载

**功能**
- PDF 文本提取
- 表格数据提取
- PDF 文档分析

### 3. Word 处理 (docx)

**基本信息**
- **名称**: `docx`
- **功能**: Word 文档处理
- **来源**: anthropics/skills
- **目录**: [`skills/anthropics/docx/`](skills/anthropics/docx/)

**测试状态**: ✅ 已加载

**功能**
- Word 文档读取和编辑
- 样式设置
- 文档生成

---

## 社区技能 (hoodini)

来自 [hoodini/ai-agents-skills](https://github.com/hoodini/ai-agents-skills) 的社区技能。

### 1. 分析指标 (analytics-metrics)

**基本信息**
- **名称**: `analytics-metrics`
- **功能**: 分析指标和度量
- **来源**: hoodini/ai-agents-skills
- **目录**: [`skills/hoodini/analytics-metrics/`](skills/hoodini/analytics-metrics/)

**测试状态**: ✅ 已加载

**功能**
- 业务指标计算
- 数据分析指标
- 性能度量

---

## 示例技能 (examples)

项目示例技能，展示如何创建自定义技能。

### 1. 时间序列分析 (time-series-analysis)

**基本信息**
- **名称**: `time-series-analysis`
- **显示名称**: 时间序列分析
- **功能**: 对时间序列数据进行趋势分析、季节性分解和移动平均计算
- **分类**: analysis
- **标签**: ["时间序列", "趋势", "季节性", "移动平均"]
- **版本**: 1.0.0
- **目录**: [`skills/examples/time-series-analysis/`](skills/examples/time-series-analysis/)

**测试状态**: ✅ 已加载

**功能特点**
- 自动检测日期列
- 趋势分析（移动平均）
- 季节性分解
- 周期性分析

**使用场景**
- 用户数据包含日期/时间列
- 需要分析数据随时间的变化趋势
- 需要识别周期性模式

---

## 智能体集成矩阵

| Agent | 技能使用方式 | 使用的技能 | 源文件位置 |
|-------|------------|-----------|-----------|
| **Coordinator** | 提示词增强 | 所有技能的描述文本（前500字符） | [`coordinator.py:98`](src/agents/coordinator.py#L98) |
| **Data Profiler** | 实际执行 | describe_statistics, distribution_analysis, correlation_analysis | [`data_profiler.py:58`](src/agents/data_profiler.py#L58) |
| **Code Generator** | 提示词增强 | 所有技能的完整描述 | [`code_generator.py:150`](src/agents/code_generator.py#L150) |
| **Visualizer** | 提示词增强 | 搜索可视化相关技能 | [`visualizer.py:123`](src/agents/visualizer.py#L123) |
| **Report Writer** | 不使用 | - | - |
| **Chat** | 不使用 | - | - |

### 智能体技能使用详情

**Coordinator Agent (调度中心)**
```python
registry = get_registry()
skill_context = registry.get_skill_descriptions()[:500]
```
- 仅用于提示词增强，不实际执行技能
- 注入到系统提示词中供 LLM 参考
- 帮助 LLM 了解可用的数据分析能力

**Data Profiler Agent (数据探索专家)**
```python
skill_names = [
    "describe_statistics",
    "distribution_analysis",
    "correlation_analysis",
]
for skill_name in skill_names:
    skill = registry.get(skill_name)
    if skill and skill.generate_code:
        code = skill.generate_code()
        result = execute_code(code=code, datasets=datasets)
```
- **唯一实际执行技能的智能体**
- 遍历指定技能，调用 `skill.generate_code()` 生成代码
- 在沙箱中执行生成的代码
- 收集输出结果和图表

**Code Generator Agent (代码架构师)**
```python
skill_descriptions = registry.get_skill_descriptions()
system_prompt = CODE_GEN_SYSTEM_PROMPT.format(
    dataset_info=dataset_info,
    skill_descriptions=skill_descriptions,
)
```
- 将所有可用技能描述注入到 LLM 提示词中
- LLM 根据这些信息生成自定义的 Python 分析代码
- 不直接执行任何技能，而是生成全新的代码

**Visualizer Agent (可视化专家)**
```python
viz_skills = registry.search("可视化") + registry.search("visualization")
viz_descs = "\n".join(f"- {s.display_name}: {s.description}" for s in viz_skills)
system_prompt = VIZ_SYSTEM_PROMPT.format(
    dataset_info=dataset_info,
    skill_descriptions=viz_descs,
)
```
- 搜索并过滤可视化相关的技能
- 将这些技能注入到系统提示词中，指导 LLM 生成可视化代码
- 不直接调用技能，而是基于技能描述生成新代码

---

## 测试覆盖详情

### ✅ 已测试技能 (5/10)

| 技能名称 | 测试文件 | 测试函数 |
|---------|---------|---------|
| describe_statistics | [test_new_skills.py:26](tests/test_new_skills.py#L26) | `test_describe_statistics_code_generation` |
| distribution_analysis | [test_new_skills.py:43](tests/test_new_skills.py#L43) | `test_distribution_analysis_code_generation` |
| correlation_analysis | [test_new_skills.py:58](tests/test_new_skills.py#L58) | `test_correlation_analysis_code_generation` |
| categorical_analysis | [test_new_skills.py:72](tests/test_new_skills.py#L72) | `test_categorical_analysis_code_generation` |
| outlier_detection | [test_new_skills.py:86](tests/test_new_skills.py#L86) | `test_outlier_detection_code_generation` |

### ⚠️ 已加载但功能未测试 (5/10)

**官方技能 (3个)**
- `xlsx` - Excel 处理
- `pdf` - PDF 处理
- `docx` - Word 处理

**社区技能 (1个)**
- `analytics-metrics` - 分析指标

**示例技能 (1个)**
- `time-series-analysis` - 时间序列分析

---

## 技能执行模式

### 实际执行技能的智能体

**Data Profiler Agent** - 系统中唯一实际执行技能的智能体
- 调用 `skill.generate_code()` 生成代码模板
- 在沙箱中执行生成的代码
- 收集输出结果和图表

### 仅用于提示词增强的智能体

- **Coordinator**: 注入技能信息用于路由决策
- **Code Generator**: 注入技能信息用于代码生成参考
- **Visualizer**: 注入可视化技能用于指导图表生成

---

## 技能选择指南

### 数据分析工作流

```
数据加载 → 探索分析 → 深度分析 → 可视化 → 报告生成
    ↓           ↓          ↓          ↓          ↓
data_parser  describe_  correlation  charts   report_
             statistics  analysis            writer
```

### 内置技能选择

| 需求 | 推荐技能 | 用途 |
|------|---------|------|
| 初步探索 | describe_statistics | 基本统计、缺失值、数据类型 |
| 分布分析 | distribution_analysis | 直方图、偏度、峰度 |
| 相关性 | correlation_analysis | 相关系数、热力图 |
| 分类变量 | categorical_analysis | 值分布、条形图 |
| 异常检测 | outlier_detection | IQR 方法、箱线图 |

### 文件处理技能

| 文件类型 | 技能 | 来源 |
|---------|------|------|
| Excel | xlsx | anthropics |
| PDF | pdf | anthropics |
| Word | docx | anthropics |

---

## 开发新技能

### 创建技能步骤

1. **创建技能目录**
   ```bash
   mkdir -p skills/your_skill_name
   cd skills/your_skill_name
   ```

2. **编写 SKILL.md**
   ```markdown
   ---
   name: your_skill_name
   display_name: 你的技能名称
   description: 技能功能描述
   version: 1.0.0
   category: analysis
   tags: [标签1, 标签2]
   code_template_file: generate.py
   ---

   # 技能标题

   ## 功能概述
   ...

   ## 参数说明
   ...

   ## 使用场景
   ...
   ```

3. **编写 generate.py**（可选）
   ```python
   def generate_code(**kwargs) -> str:
       """生成技能代码"""
       # 实现代码生成逻辑
       return generated_code
   ```

4. **测试技能**
   ```python
   from src.skills.base import get_registry
   registry = get_registry()
   loaded = registry.load_from_directory("skills/your_skill_name")
   print(f"加载了 {loaded} 个技能")
   ```

### 技能开发最佳实践

1. **SKILL.md 编写**
   - 提供清晰的功能描述
   - 包含详细的使用场景
   - 添加参数说明和示例
   - 说明输入输出格式

2. **代码生成**
   - 代码应包含完整的导入语句
   - 添加详细的注释
   - 处理常见错误情况
   - 生成可执行的完整代码

3. **测试**
   - 为技能编写单元测试
   - 测试代码生成功能
   - 验证生成的代码能正确执行

---

## 技能加载流程

### 自动加载

内置技能在模块导入时自动加载：

```python
from src.skills.builtin_skills import register_builtin_skills
register_builtin_skills()  # 自动加载 skills/builtin/ 下的所有技能
```

### 手动加载

社区技能需要手动加载：

```python
from src.skills.base import get_registry

registry = get_registry()

# 加载官方技能
registry.load_from_directory("skills/anthropics")

# 加载社区技能
registry.load_from_directory("skills/hoodini")

# 加载示例技能
registry.load_from_directory("skills/examples")
```

### 使用技能

```python
# 获取技能
skill = registry.get("describe_statistics")

# 生成代码
if skill and skill.generate_code:
    code = skill.generate_code(columns="['age', 'salary']")
    print(code)

# 执行代码
result = execute_code(code=code, datasets=datasets)
```

---

## 技能架构优势

1. **标准化**: 所有技能遵循统一的 SKILL.md 格式
2. **模块化**: 每个技能独立文件夹，易于管理
3. **可扩展**: 支持动态加载和技能发现
4. **可测试**: 完整的测试覆盖
5. **渐进式披露**: 注册时只加载元信息，使用时才读取完整内容
6. **向后兼容**: 保持 API 接口稳定

---

## 相关文档

- [技能重构总结](skills-refactoring-summary.md) - 技能体系重构的详细记录
- [部署指南](DEPLOYMENT.md) - 项目部署相关文档
- [技能基础架构](src/skills/base.py) - 技能系统核心代码
- [内置技能加载器](src/skills/builtin_skills.py) - 内置技能加载逻辑
- [图构建器](src/graph/builder.py) - 技能在工作流中的集成
- [测试文件](tests/test_new_skills.py) - 技能系统测试

---

*最后更新: 2026-04-04*
*总技能数: 10 (5 内置 + 3 官方 + 1 社区 + 1 示例)*
*测试覆盖率: 50% (5/10)*
*技能格式: SKILL.md + generate.py*
*特性: 所有内置 Skill 包含 Sanity Check 数据验证*
