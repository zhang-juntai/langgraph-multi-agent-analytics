"""
MCP Chart Server - 图表生成服务器

提供各种图表生成功能。
"""
from __future__ import annotations

import base64
import io
import json
import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 数据存储引用（与 mcp-data 共享）
_data_store: dict[str, pd.DataFrame] = {}


def set_data_store(store: dict[str, pd.DataFrame]):
    """设置数据存储（由外部调用）"""
    global _data_store
    _data_store = store


def bar_plot(
    dataset_id: str,
    x: str,
    y: str | None = None,
    orientation: str = "vertical",
    color: str = "steelblue",
    title: str | None = None,
    show_values: bool = True,
    **kwargs,
) -> dict[str, Any]:
    """
    生成条形图

    Args:
        dataset_id: 数据集 ID
        x: X 轴列名
        y: Y 轴列名（可选，默认计数）
        orientation: 方向 (vertical/horizontal)
        color: 颜色
        title: 标题
        show_values: 是否显示数值
    """
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    try:
        df = _data_store[dataset_id]

        # 数据聚合
        if y:
            data = df.groupby(x)[y].sum().sort_values(ascending=False)
        else:
            data = df[x].value_counts()

        # 创建图表
        fig, ax = plt.subplots(figsize=(10, 6))

        if orientation == "horizontal":
            bars = ax.barh(data.index.astype(str), data.values, color=color, edgecolor="black")
            ax.set_xlabel(y if y else "数量")
            ax.set_ylabel(x)
            if show_values:
                ax.bar_label(bars, fmt="%.0f", padding=3)
        else:
            bars = ax.bar(data.index.astype(str), data.values, color=color, edgecolor="black")
            ax.set_xlabel(x)
            ax.set_ylabel(y if y else "数量")
            if show_values:
                ax.bar_label(bars, fmt="%.0f", padding=3)
            plt.xticks(rotation=45, ha="right")

        ax.set_title(title or f"{x} 分布", fontsize=14)
        plt.tight_layout()

        # 保存
        figure_path, figure_base64 = _save_figure(fig)

        return {
            "success": True,
            "figure_path": figure_path,
            "figure_base64": figure_base64,
            "data_summary": {
                "categories": len(data),
                "total": float(data.sum()),
                "max": float(data.max()),
                "min": float(data.min()),
            },
        }

    except Exception as e:
        logger.error(f"bar_plot failed: {e}")
        return {"success": False, "error": str(e)}


def line_plot(
    dataset_id: str,
    x: str,
    y: str,
    hue: str | None = None,
    style: str | None = None,
    markers: bool = True,
    title: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """生成折线图"""
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    try:
        df = _data_store[dataset_id]
        fig, ax = plt.subplots(figsize=(12, 6))

        if hue:
            for name, group in df.groupby(hue):
                ax.plot(group[x], group[y], marker="o" if markers else None, label=str(name))
            ax.legend()
        else:
            ax.plot(df[x], df[y], marker="o" if markers else None)

        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.set_title(title or f"{y} 趋势", fontsize=14)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        figure_path, figure_base64 = _save_figure(fig)

        return {
            "success": True,
            "figure_path": figure_path,
            "figure_base64": figure_base64,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def scatter_plot(
    dataset_id: str,
    x: str,
    y: str,
    hue: str | None = None,
    size: str | None = None,
    alpha: float = 0.6,
    title: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """生成散点图"""
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    try:
        df = _data_store[dataset_id]
        fig, ax = plt.subplots(figsize=(10, 8))

        sizes = df[size] * 100 if size else None

        if hue:
            for name, group in df.groupby(hue):
                ax.scatter(
                    group[x], group[y],
                    s=sizes.loc[group.index] if sizes is not None else None,
                    alpha=alpha,
                    label=str(name),
                )
            ax.legend()
        else:
            ax.scatter(df[x], df[y], s=sizes, alpha=alpha)

        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.set_title(title or f"{x} vs {y}", fontsize=14)
        plt.tight_layout()

        figure_path, figure_base64 = _save_figure(fig)

        # 计算相关性
        corr = df[[x, y]].corr().iloc[0, 1]

        return {
            "success": True,
            "figure_path": figure_path,
            "figure_base64": figure_base64,
            "correlation": float(corr),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def histogram(
    dataset_id: str,
    column: str,
    bins: int = 30,
    kde: bool = True,
    title: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """生成直方图"""
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    try:
        df = _data_store[dataset_id]
        fig, ax = plt.subplots(figsize=(10, 6))

        data = df[column].dropna()

        # 直方图
        n, bins_out, patches = ax.hist(data, bins=bins, edgecolor="black", alpha=0.7, density=kde)

        # KDE 曲线
        if kde:
            try:
                from scipy import stats
                kde_x = np.linspace(data.min(), data.max(), 100)
                kde_y = stats.gaussian_kde(data)(kde_x)
                ax.plot(kde_x, kde_y, color="red", linewidth=2, label="KDE")
                ax.legend()
            except ImportError:
                pass

        ax.set_xlabel(column)
        ax.set_ylabel("密度" if kde else "频数")
        ax.set_title(title or f"{column} 分布", fontsize=14)
        plt.tight_layout()

        figure_path, figure_base64 = _save_figure(fig)

        return {
            "success": True,
            "figure_path": figure_path,
            "figure_base64": figure_base64,
            "stats": {
                "mean": float(data.mean()),
                "median": float(data.median()),
                "std": float(data.std()),
                "skew": float(data.skew()),
            },
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def boxplot(
    dataset_id: str,
    columns: list[str],
    by: str | None = None,
    title: str = "箱线图 (异常值检测)",
    **kwargs,
) -> dict[str, Any]:
    """生成箱线图"""
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    try:
        df = _data_store[dataset_id]

        # 过滤存在的列
        cols = [c for c in columns if c in df.columns]
        if not cols:
            return {"success": False, "error": "没有有效的数值列"}

        fig, ax = plt.subplots(figsize=(max(8, len(cols) * 2), 6))

        if by:
            df.boxplot(column=cols, by=by, ax=ax)
            plt.suptitle("")
        else:
            df[cols].boxplot(ax=ax)

        ax.set_title(title, fontsize=14)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        figure_path, figure_base64 = _save_figure(fig)

        # 检测异常值
        outliers_info = {}
        for col in cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            outliers = df[(df[col] < lower) | (df[col] > upper)][col]
            outliers_info[col] = {
                "count": len(outliers),
                "pct": round(len(outliers) / len(df) * 100, 2),
            }

        return {
            "success": True,
            "figure_path": figure_path,
            "figure_base64": figure_base64,
            "outliers": outliers_info,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def heatmap(
    matrix: list[list[float]],
    labels: list[str],
    annot: bool = True,
    cmap: str = "RdBu_r",
    center: float = 0,
    title: str = "热力图",
    **kwargs,
) -> dict[str, Any]:
    """生成热力图"""
    try:
        import seaborn as sns

        matrix_arr = np.array(matrix)
        n = len(labels)

        fig, ax = plt.subplots(figsize=(max(8, n), max(6, n * 0.8)))

        sns.heatmap(
            matrix_arr,
            annot=annot,
            cmap=cmap,
            center=center,
            xticklabels=labels,
            yticklabels=labels,
            fmt=".2f",
            square=True,
            linewidths=0.5,
            ax=ax,
        )

        ax.set_title(title, fontsize=14)
        plt.tight_layout()

        figure_path, figure_base64 = _save_figure(fig)

        return {
            "success": True,
            "figure_path": figure_path,
            "figure_base64": figure_base64,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def pie_chart(
    dataset_id: str,
    column: str,
    top_n: int = 10,
    show_pct: bool = True,
    title: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """生成饼图"""
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    try:
        df = _data_store[dataset_id]
        data = df[column].value_counts().head(top_n)

        # 如果超过 top_n，归为"其他"
        if len(df[column].unique()) > top_n:
            other_count = len(df) - data.sum()
            data["其他"] = other_count

        fig, ax = plt.subplots(figsize=(10, 10))

        colors = plt.cm.Set3(np.linspace(0, 1, len(data)))

        wedges, texts, autotexts = ax.pie(
            data.values,
            labels=data.index,
            autopct="%1.1f%%" if show_pct else None,
            colors=colors,
            startangle=90,
        )

        ax.set_title(title or f"{column} 占比分布", fontsize=14)
        plt.tight_layout()

        figure_path, figure_base64 = _save_figure(fig)

        return {
            "success": True,
            "figure_path": figure_path,
            "figure_base64": figure_base64,
            "categories": len(data),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def _save_figure(fig) -> tuple[str, str]:
    """保存图表到文件和 base64"""
    import uuid

    # 生成文件名
    filename = f"chart_{uuid.uuid4().hex[:8]}.png"
    filepath = OUTPUT_DIR / filename

    # 保存文件
    fig.savefig(filepath, dpi=100, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # 生成 base64
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight", facecolor="white")
    buffer.seek(0)
    figure_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    plt.close(fig)

    logger.info(f"Saved figure: {filepath}")

    return str(filepath), figure_base64


# MCP Server Tool Registry
TOOLS = {
    "bar_plot": bar_plot,
    "line_plot": line_plot,
    "scatter_plot": scatter_plot,
    "histogram": histogram,
    "boxplot": boxplot,
    "heatmap": heatmap,
    "pie_chart": pie_chart,
}


def handle_request(tool_name: str, params: dict) -> dict[str, Any]:
    """处理 MCP 请求"""
    if tool_name not in TOOLS:
        return {"success": False, "error": f"未知工具: {tool_name}"}

    try:
        result = TOOLS[tool_name](**params)
        return result
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # 测试
    print("MCP Chart Server ready")
    print(f"Output directory: {OUTPUT_DIR}")