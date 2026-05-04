"""
描述性统计分析代码生成器

生成完整的描述性统计分析代码，包括基本统计量、数据类型分布、
缺失值统计和唯一值统计。

包含 Sanity Check 确保数据有效性。
"""

def generate_code(**kwargs) -> str:
    """
    生成描述性统计代码

    Args:
        **kwargs: 关键字参数
            - columns: 指定分析的列名（可选，默认"None"）

    Returns:
        str: 生成的Python代码字符串
    """
    columns = kwargs.get('columns', 'None')

    return f'''
# 描述性统计分析
print("=" * 60)
print("📊 描述性统计分析")
print("=" * 60)

# === Sanity Check: 验证数据 ===
if df is None:
    print("❌ 数据未加载 (df is None)")
elif df.empty:
    print("❌ 数据为空 (df is empty)")
else:
    # 清理列名中的 BOM 字符（Excel 导出的 CSV 常见问题）
    df.columns = [col.replace('\\ufeff', '') if isinstance(col, str) else col for col in df.columns]
    print(f"✅ 数据有效: {{len(df)}} 行, {{len(df.columns)}} 列")

    cols = {columns}

    # 获取目标列
    if cols:
        target = df[cols]
    else:
        target = df.select_dtypes(include=["number"])

    if target.empty or len(target.columns) == 0:
        print("\\n⚠️ 没有数值型列，尝试分析所有列")
        target = df

    print("\\n【基本统计量】")
    try:
        print(target.describe().round(2).to_string())
    except Exception as e:
        print(f"统计计算失败: {{e}}")

    print("\\n【数据类型分布】")
    print(df.dtypes.value_counts().to_string())

    print("\\n【缺失值统计】")
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    missing_df = pd.DataFrame({{"缺失数": missing, "缺失率(%)": missing_pct}})
    print(missing_df[missing_df["缺失数"] > 0].to_string() if missing.sum() > 0 else "无缺失值 ✅")

    print("\\n【唯一值统计】")
    for col in df.columns:
        print(f"  {{col}}: {{df[col].nunique()}} 个唯一值")
'''
