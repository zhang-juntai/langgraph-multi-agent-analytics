"""
数据分布分析代码生成器

生成数值特征分布分析代码，包括直方图、偏度和峰度计算。
包含 Sanity Check 确保数据有效性。
"""

def generate_code(**kwargs) -> str:
    """
    生成数据分布分析代码

    Returns:
        str: 生成的Python代码字符串
    """
    return '''
# 数据分布分析
print("=" * 60)
print("📊 数据分布分析")
print("=" * 60)

import matplotlib.pyplot as plt
import seaborn as sns

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
    n_cols = len(numeric_cols)

    if n_cols == 0:
        print("⚠️ 没有数值型列，无法进行分布分析")
        print(f"   当前列类型: {df.dtypes.value_counts().to_dict()}")
    else:
        print(f"✅ 找到 {n_cols} 个数值列: {numeric_cols}")

        # 直方图
        n_rows = (n_cols + 2) // 3
        fig, axes = plt.subplots(n_rows, min(3, n_cols), figsize=(5 * min(3, n_cols), 4 * n_rows))
        if n_cols == 1:
            axes = [axes]
        elif n_rows == 1:
            axes = [axes] if n_cols == 1 else list(axes)
        else:
            axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

        for i, col in enumerate(numeric_cols):
            if i < len(axes):
                ax = axes[i]
                df[col].dropna().hist(bins=30, ax=ax, edgecolor="black", alpha=0.7)
                ax.set_title(col)
                ax.set_xlabel("")

        # 隐藏多余子图
        for j in range(n_cols, len(axes)):
            axes[j].set_visible(False)

        plt.suptitle("数值特征分布直方图", fontsize=14, y=1.02)
        plt.tight_layout()
        plt.show()

        # 偏度和峰度
        print("\\n【偏度和峰度】")
        for col in numeric_cols:
            try:
                skew = df[col].skew()
                kurt = df[col].kurtosis()
                print(f"  {col}: 偏度={skew:.3f}, 峰度={kurt:.3f}")
            except Exception as e:
                print(f"  {col}: 计算失败 - {e}")
'''
