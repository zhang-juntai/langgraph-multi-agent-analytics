"""
数据加载与健康检查代码生成器

功能：
1. 编码检测（优先 utf-8-sig）
2. BOM 清理（列名中的 \ufeff）
3. 数据加载（CSV/Excel/JSON）
4. 元信息生成
5. 健康检查

是数据进入分析流程的第一道关卡。
"""

def generate_code(**kwargs) -> str:
    """
    生成数据加载与健康检查代码

    Args:
        **kwargs: 关键字参数
            - file_path: 文件路径（可选）
            - encoding: 编码方式（默认 auto）

    Returns:
        str: 生成的Python代码字符串
    """
    file_path = kwargs.get('file_path', 'None')
    encoding = kwargs.get('encoding', 'auto')

    return f'''
# 数据加载与健康检查
import pandas as pd
import os

print("=" * 60)
print("📁 数据加载与健康检查")
print("=" * 60)

# === Step 1: 编码检测与 BOM 处理 ===
def _detect_encoding(file_path):
    """检测文件编码，优先 utf-8-sig 处理 BOM"""
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read(4096)
                # 检查是否成功读取且无乱码
                if '\\ufffd' not in content:
                    return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8-sig"  # 默认使用 utf-8-sig

def _clean_bom(df):
    """清理 DataFrame 列名和数据中的 BOM 字符"""
    # 清理列名
    new_columns = []
    for col in df.columns:
        if isinstance(col, str):
            cleaned = col.replace('\\ufeff', '')
            new_columns.append(cleaned)
        else:
            new_columns.append(col)
    df.columns = new_columns

    # 清理字符串列数据中的 BOM
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                df[col] = df[col].apply(
                    lambda x: x.replace('\\ufeff', '') if isinstance(x, str) else x
                )
            except:
                pass

    return df

# === Step 2: 数据加载 ===
_file_path = {file_path}
_encoding = "{encoding}"

if df is not None:
    # df 已存在（从外部传入）
    print("✅ 使用已加载的数据集")
    df = _clean_bom(df)
elif _file_path and _file_path != "None":
    # 从文件加载
    print(f"📂 加载文件: {{_file_path}}")

    if _encoding == "auto":
        _encoding = _detect_encoding(_file_path)
        print(f"   检测到编码: {{_encoding}}")

    try:
        if _file_path.endswith('.csv'):
            df = pd.read_csv(_file_path, encoding=_encoding)
        elif _file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(_file_path)
        elif _file_path.endswith('.json'):
            df = pd.read_json(_file_path)
        else:
            print(f"❌ 不支持的文件格式")
            df = None

        if df is not None:
            df = _clean_bom(df)
            print(f"✅ 数据加载成功")
    except Exception as e:
        print(f"❌ 加载失败: {{e}}")
        df = None
else:
    print("⚠️ 未提供文件路径且 df 为空")

# === Step 3: 数据有效性检查 ===
if df is None:
    print("\\n❌ 数据未加载 (df is None)")
elif df.empty:
    print("\\n❌ 数据为空 (df is empty)")
else:
    print(f"\\n✅ 数据有效: {{len(df)}} 行, {{len(df.columns)}} 列")

    # === Step 4: 基本信息报告 ===
    print("\\n【基本信息】")
    print(f"  行数: {{len(df):,}}")
    print(f"  列数: {{len(df.columns)}}")
    print(f"  内存: {{df.memory_usage(deep=True).sum() / 1024:.1f}} KB")

    # === Step 5: 列信息 ===
    print("\\n【列信息】")
    print(f"  {{'列名':<20}} {{'类型':<10}} {{'非空数':>10}} {{'唯一值':>10}}")
    print("  " + "-" * 52)
    for col in df.columns:
        dtype = str(df[col].dtype)
        non_null = df[col].count()
        unique = df[col].nunique()
        print(f"  {{col:<20}} {{dtype:<10}} {{non_null:>10,}} {{unique:>10,}}")

    # === Step 6: 健康检查 ===
    print("\\n【健康检查】")

    issues = []
    suggestions = []

    # 检查空数据
    if len(df) == 0:
        issues.append("❌ 数据为空")
    else:
        print("  ✅ 数据不为空")

    # 检查空列
    empty_cols = [col for col in df.columns if df[col].isnull().all()]
    if empty_cols:
        issues.append(f"❌ 发现空列: {{empty_cols}}")
        suggestions.append(f"删除空列: {{empty_cols}}")
    else:
        print("  ✅ 无全空列")

    # 检查缺失值
    missing = df.isnull().sum()
    total_cells = len(df) * len(df.columns)
    total_missing = missing.sum()
    if total_missing > 0:
        missing_pct = total_missing / total_cells * 100
        print(f"  ⚠️ 发现 {{total_missing}} 个缺失值 ({{missing_pct:.2f}}%)")
        missing_cols = missing[missing > 0].sort_values(ascending=False)
        for col, count in missing_cols.head(5).items():
            print(f"     - {{col}}: {{count}}")
        suggestions.append("考虑处理缺失值（填充或删除）")
    else:
        print("  ✅ 无缺失值")

    # 检查重复行
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        dup_pct = dup_count / len(df) * 100
        print(f"  ⚠️ 发现 {{dup_count}} 行重复数据 ({{dup_pct:.1f}}%)")
        suggestions.append("考虑去重处理")
    else:
        print("  ✅ 无重复行")

    # 检查数值列
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if numeric_cols:
        print(f"  ✅ 发现 {{len(numeric_cols)}} 个数值列")
    else:
        print("  ⚠️ 没有数值列（无法进行数值分析）")
        suggestions.append("检查是否有数值列被误识别为字符串")

    # 检查分类列
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    if cat_cols:
        print(f"  ✅ 发现 {{len(cat_cols)}} 个分类列")

    # === Step 7: 建议 ===
    if suggestions:
        print("\\n【建议】")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {{i}}. {{suggestion}}")

    # === Step 8: 数据摘要（供 LLM 参考）===
    print("\\n【数据摘要（前5行）】")
    print(df.head().to_string())
'''
