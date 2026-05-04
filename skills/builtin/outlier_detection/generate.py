"""
异常值检测代码生成器

使用IQR方法生成异常值检测代码，包括统计和箱线图。
包含 Sanity Check 确保数据有效性。
"""

def generate_code(**kwargs) -> str:
    """
    生成异常值检测代码

    Returns:
        str: 生成的Python代码字符串
    """
    return '''
# 异常值检测 (IQR 方法)
print("=" * 60)
print("📊 异常值检测")
print("=" * 60)

import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# === Sanity Check: 验证数据 ===
if df is None:
    print("❌ 数据未加载 (df is None)")
elif df.empty:
    print("❌ 数据为空 (df is empty)")
else:
    # 清理列名中的 BOM 字符（Excel 导出的 CSV 常见问题）
    df.columns = [col.replace('\\ufeff', '') if isinstance(col, str) else col for col in df.columns]

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if not numeric_cols:
        print("⚠️ 没有数值型列，无法进行异常值检测")
        print(f"   当前列类型: {df.dtypes.value_counts().to_dict()}")
    else:
        print(f"✅ 找到 {len(numeric_cols)} 个数值列: {numeric_cols}")

        print("\\n【IQR 异常值检测】")
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            outliers = df[(df[col] < lower) | (df[col] > upper)]
            pct = len(outliers) / len(df) * 100
            print(f"  {col}: {len(outliers)} 个异常值 ({pct:.1f}%), 范围=[{lower:.2f}, {upper:.2f}]")

        # 箱线图
        n_cols = len(numeric_cols)
        fig, axes = plt.subplots(1, min(n_cols, 5), figsize=(4 * min(n_cols, 5), 5))
        if n_cols == 1:
            axes = [axes]
        for i, col in enumerate(numeric_cols[:5]):
            axes[i].boxplot(df[col].dropna())
            axes[i].set_title(col)
        plt.suptitle("箱线图 (异常值检测)", fontsize=13)
        plt.tight_layout()
        plt.show()
'''
