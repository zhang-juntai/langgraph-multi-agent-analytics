"""
分类变量分析代码生成器

生成分类变量值分布统计和条形图代码。
包含 Sanity Check 确保数据有效性。
"""

def generate_code(**kwargs) -> str:
    """
    生成分类变量分析代码

    Returns:
        str: 生成的Python代码字符串
    """
    return '''
# 分类变量分析
print("=" * 60)
print("📊 分类变量分析")
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

    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    if not cat_cols:
        print("⚠️ 没有分类变量列")
        print(f"   当前列类型: {df.dtypes.value_counts().to_dict()}")
    else:
        print(f"✅ 找到 {len(cat_cols)} 个分类列: {cat_cols}")

        for col in cat_cols:
            print(f"\\n【{col} 的值分布】")
            vc = df[col].value_counts()
            print(vc.head(15).to_string())

            if len(vc) <= 20:
                fig, ax = plt.subplots(figsize=(10, 5))
                vc.plot(kind="bar", ax=ax, edgecolor="black", alpha=0.7)
                ax.set_title(f"{col} 值分布")
                ax.set_xlabel(col)
                ax.set_ylabel("数量")
                plt.xticks(rotation=45, ha="right")
                plt.tight_layout()
                plt.show()
            else:
                print(f"   (共 {len(vc)} 个唯一值，跳过图表)")
'''
