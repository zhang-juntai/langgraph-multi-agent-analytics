"""
自动模型选择代码生成器

自动比较多个机器学习算法，选择最佳模型。
支持分类和回归任务。
"""
from __future__ import annotations


def generate_code(**kwargs) -> str:
    """
    生成自动模型选择代码

    Args:
        target_column: 目标变量列名
        feature_columns: 特征列名列表（可选）
        task_type: 任务类型 (auto/classification/regression)
        algorithms: 要比较的算法列表
        cv_folds: 交叉验证折数

    Returns:
        str: 生成的Python代码字符串
    """
    target_column = kwargs.get("target_column", "target")
    feature_columns = kwargs.get("feature_columns", None)
    task_type = kwargs.get("task_type", "auto")
    algorithms = kwargs.get("algorithms", ["random_forest", "xgboost", "lightgbm"])
    cv_folds = kwargs.get("cv_folds", 5)

    # 处理特征列参数
    feature_cols_str = (
        feature_columns
        if feature_columns
        else "df.select_dtypes(include=['number']).columns.drop(target).tolist()"
    )

    return f'''
# 自动模型选择
print("=" * 60)
print("🤖 自动模型选择")
print("=" * 60)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score, mean_squared_error, r2_score
)
import warnings
warnings.filterwarnings('ignore')

plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# === Sanity Check ===
if df is None:
    print("❌ 数据未加载 (df is None)")
elif df.empty:
    print("❌ 数据为空 (df is empty)")
else:
    # 清理 BOM
    df.columns = [col.replace('\\ufeff', '') if isinstance(col, str) else col for col in df.columns]

    target = "{target_column}"
    if target not in df.columns:
        print(f"❌ 目标列 '{{target}}' 不存在")
        print(f"   可用列: {{df.columns.tolist()}}")
    else:
        # 确定特征列
        feature_cols = {feature_cols_str}
        feature_cols = [c for c in feature_cols if c != target and c in df.columns]

        if not feature_cols:
            print("❌ 没有可用的特征列")
        else:
            print(f"✅ 目标变量: {{target}}")
            print(f"✅ 特征数量: {{len(feature_cols)}}")

            # 准备数据
            X = df[feature_cols].copy()
            y = df[target].copy()

            # 处理缺失值
            X = X.fillna(X.median())
            y = y.fillna(y.median() if y.dtype in ['float64', 'int64'] else y.mode()[0])

            # 自动检测任务类型
            task_type = "{task_type}"
            if task_type == "auto":
                unique_values = y.nunique()
                if unique_values <= 10 and y.dtype == 'object':
                    task_type = "classification"
                elif unique_values <= 10:
                    task_type = "classification"
                else:
                    task_type = "regression"

            print(f"\\n📋 任务类型: {{'分类' if task_type == 'classification' else '回归'}}")
            print(f"   目标变量唯一值: {{y.nunique()}}")

            # 编码目标变量（分类任务）
            if task_type == "classification" and y.dtype == 'object':
                le = LabelEncoder()
                y = pd.Series(le.fit_transform(y), index=y.index)
                print(f"   类别映射: {{dict(zip(le.classes_, range(len(le.classes_))))}}")

            # 标准化
            scaler = StandardScaler()
            X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

            # 定义模型
            models = {{}}

            if task_type == "classification":
                if "logistic_regression" in {algorithms}:
                    models["Logistic Regression"] = LogisticRegression(max_iter=1000, random_state=42)
                if "random_forest" in {algorithms}:
                    models["Random Forest"] = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
                if "xgboost" in {algorithms}:
                    try:
                        from xgboost import XGBClassifier
                        models["XGBoost"] = XGBClassifier(n_estimators=100, random_state=42, n_jobs=-1, verbosity=0)
                    except ImportError:
                        print("   ⚠️ XGBoost 未安装，跳过")
                if "lightgbm" in {algorithms}:
                    try:
                        from lightgbm import LGBMClassifier
                        models["LightGBM"] = LGBMClassifier(n_estimators=100, random_state=42, n_jobs=-1, verbose=-1)
                    except ImportError:
                        print("   ⚠️ LightGBM 未安装，跳过")

                cv = StratifiedKFold(n_splits={cv_folds}, shuffle=True, random_state=42)
                scoring = 'f1_weighted'
            else:
                if "linear_regression" in {algorithms} or "ridge" in {algorithms}:
                    models["Ridge"] = Ridge(random_state=42)
                if "random_forest" in {algorithms}:
                    models["Random Forest"] = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
                if "xgboost" in {algorithms}:
                    try:
                        from xgboost import XGBRegressor
                        models["XGBoost"] = XGBRegressor(n_estimators=100, random_state=42, n_jobs=-1, verbosity=0)
                    except ImportError:
                        print("   ⚠️ XGBoost 未安装，跳过")
                if "lightgbm" in {algorithms}:
                    try:
                        from lightgbm import LGBMRegressor
                        models["LightGBM"] = LGBMRegressor(n_estimators=100, random_state=42, n_jobs=-1, verbose=-1)
                    except ImportError:
                        print("   ⚠️ LightGBM 未安装，跳过")

                cv = KFold(n_splits={cv_folds}, shuffle=True, random_state=42)
                scoring = 'r2'

            if not models:
                print("❌ 没有可用的模型")
            else:
                print(f"\\n📊 比较 {{len(models)}} 个模型 ({{cv_folds}}-fold CV)")
                print("-" * 50)

                # 存储结果
                results = {{}}

                for name, model in models.items():
                    try:
                        scores = cross_val_score(model, X_scaled, y, cv=cv, scoring=scoring, n_jobs=-1)
                        mean_score = scores.mean()
                        std_score = scores.std()

                        results[name] = {{
                            "mean": mean_score,
                            "std": std_score,
                            "scores": scores
                        }}

                        metric_name = "F1" if task_type == "classification" else "R²"
                        print(f"  {{name:20s}}: {{metric_name}} = {{mean_score:.4f}} ± {{std_score:.4f}}")
                    except Exception as e:
                        print(f"  {{name:20s}}: ❌ {{str(e)[:30]}}")

                if results:
                    # 找到最佳模型
                    best_model = max(results.keys(), key=lambda x: results[x]["mean"])
                    best_score = results[best_model]["mean"]

                    print("-" * 50)
                    print(f"\\n✅ 最佳模型: {{best_model}}")
                    metric_name = "F1" if task_type == "classification" else "R²"
                    print(f"   {{metric_name}} Score: {{best_score:.4f}}")

                    # 可视化比较
                    fig, ax = plt.subplots(figsize=(10, 6))

                    names = list(results.keys())
                    means = [results[n]["mean"] for n in names]
                    stds = [results[n]["std"] for n in names]

                    bars = ax.barh(names, means, xerr=stds, capsize=5, alpha=0.7, edgecolor='black')

                    # 标记最佳模型
                    best_idx = names.index(best_model)
                    bars[best_idx].set_color('green')
                    bars[best_idx].set_alpha(0.9)

                    ax.set_xlabel(metric_name + " Score")
                    ax.set_title("模型比较 (" + ("分类" if task_type == "classification" else "回归") + ")")
                    ax.axvline(x=0, color='gray', linestyle='--', alpha=0.3)

                    plt.tight_layout()
                    plt.show()

                    # 推荐建议
                    print("\\n📝 建议:")
                    if best_score > 0.8:
                        print(f"   模型表现优秀 ({{metric_name}} > 0.8)，可以用于预测")
                    elif best_score > 0.6:
                        print(f"   模型表现良好，建议尝试特征工程提升性能")
                    else:
                        print(f"   模型表现一般，建议:")
                        print("   - 增加数据量")
                        print("   - 特征工程")
                        print("   - 调参优化")
                else:
                    print("\\n❌ 所有模型训练失败")
'''