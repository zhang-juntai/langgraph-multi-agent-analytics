# 常见错误排查指南

本文档记录了使用数据分析平台时常见的错误及其解决方案。

---

## 1. 数据未加载 (df is None)

### 错误表现

```
❌ 数据未加载 (df is None)
```

或

```
NameError: name 'df' is not defined
```

### 原因

- 未上传或加载任何数据文件
- 文件路径不正确
- 数据解析失败但未提示

### 解决方案

1. **先加载数据文件**
   ```
   请加载 data/orders.csv 文件
   ```

2. **检查文件路径**
   - 确保文件存在于 `data/` 目录下
   - 使用相对路径或绝对路径

3. **查看已加载的数据集**
   ```
   当前有哪些数据集？
   ```

### 代码参考

- [`src/agents/data_parser.py`](../../src/agents/data_parser.py) - 数据解析逻辑
- [`src/sandbox/executor.py`](../../src/sandbox/executor.py) - 数据注入逻辑

---

## 2. 没有数值列 (No Numeric Columns)

### 错误表现

```
⚠️ 没有数值型列，无法进行分布分析
   当前列类型: {'object': 5}
```

或

```
ValueError: cannot convert string to float
```

### 原因

- 数据文件中所有列都是字符串类型
- 数值列被识别为 object 类型（可能包含非数字字符）
- CSV 文件格式问题导致类型推断失败

### 解决方案

1. **检查数据类型**
   ```python
   print(df.dtypes)
   ```

2. **手动转换类型**
   ```python
   df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
   ```

3. **使用正确的分析方式**
   - 对于分类数据，使用 `value_counts()` 或 `categorical_analysis` 技能
   - 对于需要转换的数据，先进行数据清洗

### 相关技能

- `describe_statistics` - 包含自动类型检测
- `categorical_analysis` - 适用于分类变量

---

## 3. CSV BOM 编码问题

### 错误表现

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xef in position 0
```

或

```
列名显示为 \ufeffcolumn_name
```

### 原因

CSV 文件使用 UTF-8 with BOM 编码保存，导致：
- 首列名称前有不可见的 BOM 字符 (`\ufeff`)
- 编码解析失败

### 解决方案

**已内置修复**：系统自动使用 `utf-8-sig` 编码读取文件

```python
# 自动处理 BOM
encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"]
```

**手动修复文件**：
1. 用记事本打开 CSV 文件
2. 另存为 → 选择 "UTF-8"（不带 BOM）
3. 或使用 VS Code：右下角选择编码 → Save with Encoding → UTF-8

### 代码参考

- [`src/agents/data_parser.py:_detect_encoding()`](../../src/agents/data_parser.py) - 编码检测逻辑
- [`src/sandbox/executor.py`](../../src/sandbox/executor.py) - 沙箱中的数据加载

---

## 4. 路由错误 (Wrong Agent Selected)

### 错误表现

用户请求具体分析（如"分析订单占比"），但系统路由到了错误的 Agent：
- 路由到 `data_profiler` 只显示概况
- 路由到 `chat` 直接回复文本

### 原因

Coordinator 意图识别失败，可能因为：
- 请求表述模糊
- 包含多个意图
- LLM 输出格式异常

### 解决方案

1. **使用更明确的表述**
   ```
   # 模糊（可能错误路由）
   看看订单数据

   # 明确（正确路由到 code_generator）
   分析已完成订单的占比，显示百分比
   ```

2. **包含关键词**
   - 分析类：占比、比例、百分比、排名、趋势、对比、计算
   - 可视化类：画图、图表、柱状图、折线图
   - 报告类：生成报告、总结分析

3. **检查路由日志**
   ```
   查看后端日志：
   Coordinator 路由决策: intent=..., task_type=..., next_agent=...
   ```

### 路由优先级

| 优先级 | 关键词 | 目标 Agent |
|--------|--------|------------|
| 1 | 占比、比例、趋势、对比、计算 | code_generator |
| 2 | 概况、整体、看看数据 | data_profiler |
| 3 | 图、图表、可视化 | visualizer |
| 4 | 报告、总结 | report_writer |

### 代码参考

- [`src/agents/coordinator.py`](../../src/agents/coordinator.py) - 路由逻辑和优先级规则

---

## 5. 代码执行超时

### 错误表现

```
⏰ 代码执行超时（30秒），请优化代码效率或减少数据量。
```

### 原因

- 数据量过大
- 代码效率问题（如嵌套循环）
- 死循环或阻塞操作

### 解决方案

1. **减少数据量**
   ```python
   df_sample = df.sample(n=10000, random_state=42)
   ```

2. **优化代码**
   - 避免在循环中操作 DataFrame
   - 使用向量化操作替代 iterrows()

3. **分步执行**
   - 将复杂分析拆分为多个简单请求

### 配置参考

```python
# configs/settings.py
SANDBOX_TIMEOUT = 30  # 秒
```

---

## 6. 图表中文乱码

### 错误表现

图表中的中文显示为方块或乱码。

### 原因

系统缺少中文字体或未正确配置。

### 解决方案

代码中已自动配置：
```python
plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
```

如果仍有问题：
1. 确保系统安装了 SimHei 字体
2. 或使用其他可用中文字体：`["Microsoft YaHei", "WenQuanYi Micro Hei"]`

---

## 快速诊断清单

| 问题 | 检查项 | 解决方案 |
|------|--------|----------|
| 数据未加载 | 是否上传/加载数据 | 先执行数据加载 |
| 没有数值列 | df.dtypes 输出 | 类型转换或使用分类分析 |
| BOM 编码 | 列名是否有 \ufeff | 已自动处理，或重新保存文件 |
| 路由错误 | 请求是否包含明确关键词 | 使用更具体的表述 |
| 执行超时 | 数据量/代码复杂度 | 减少数据或分步执行 |
| 中文乱码 | 系统字体 | 已自动配置，检查字体安装 |

---

*最后更新: 2026-04-04*
