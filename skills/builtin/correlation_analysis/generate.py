"""
相关性分析代码生成器

生成Pearson相关性分析代码，包括相关系数矩阵、热力图和高相关性特征对识别。
包含 Sanity Check 确保数据有效性。
"""

def generate_code(**kwargs) -> str:
    """
    生成相关性分析代码

    Returns:
        str: 生成的Python代码字符串
    """
    return '''
# 相关性分析
print("=" * 60)
print("📊 相关性分析")
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

    numeric_df = df.select_dtypes(include=["number"])

    if numeric_df.shape[1] < 2:
        print(f"⚠️ 数值列不足 2 列（当前 {numeric_df.shape[1]} 列），无法计算相关性")
        print(f"   当前列: {df.columns.tolist()}")
        print(f"   数值列: {numeric_df.columns.tolist()}")
    else:
        print(f"✅ 找到 {numeric_df.shape[1]} 个数值列: {numeric_df.columns.tolist()}")

        corr = numeric_df.corr().round(3)

        print("\\n【Pearson 相关系数矩阵】")
        print(corr.to_string())

        # 热力图
        fig, ax = plt.subplots(figsize=(max(8, numeric_df.shape[1]), max(6, numeric_df.shape[1] * 0.8)))
        sns.heatmap(corr, annot=True, cmap="RdBu_r", center=0, fmt=".2f",
                    square=True, linewidths=0.5, ax=ax)
        ax.set_title("相关性热力图")
        plt.tight_layout()
        plt.show()

        # 高相关性警告
        print("\\n【高相关性特征对 (|r| > 0.7)】")
        high_corr = []
        for i in range(len(corr.columns)):
            for j in range(i + 1, len(corr.columns)):
                if abs(corr.iloc[i, j]) > 0.7:
                    high_corr.append((corr.columns[i], corr.columns[j], corr.iloc[i, j]))
        if high_corr:
            for c1, c2, r in high_corr:
                print(f"  {c1} <-> {c2}: r = {r:.3f}")
        else:
            print("  无高相关性特征对")
'''
