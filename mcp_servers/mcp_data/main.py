"""
MCP Data Server - 数据加载与处理服务器

提供数据加载、验证、元信息提取等功能。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据存储（简单实现，生产环境用 Redis/数据库）
_data_store: dict[str, pd.DataFrame] = {}
_metadata_store: dict[str, dict] = {}


def load_csv(file_path: str, encoding: str = "utf-8-sig", **kwargs) -> dict[str, Any]:
    """
    加载 CSV 文件，自动处理编码问题（包括 BOM）

    Args:
        file_path: CSV 文件路径
        encoding: 文件编码，默认 utf-8-sig 处理 BOM

    Returns:
        包含数据和元信息的结果
    """
    try:
        # 尝试多种编码
        encodings_to_try = [encoding]
        if encoding != "utf-8-sig":
            encodings_to_try.append("utf-8-sig")
        encodings_to_try.extend(["utf-8", "gbk", "gb2312", "latin-1"])

        df = None
        used_encoding = None

        for enc in encodings_to_try:
            try:
                df = pd.read_csv(file_path, encoding=enc, **kwargs)
                used_encoding = enc
                break
            except UnicodeDecodeError:
                continue

        if df is None:
            return {"success": False, "error": "无法解码文件"}

        # 清理 BOM 字符（双重保险）
        df.columns = [
            col.replace("\ufeff", "") if isinstance(col, str) else col
            for col in df.columns
        ]

        # 生成数据集 ID
        dataset_id = Path(file_path).stem + "_" + str(hash(file_path) % 10000)

        # 存储数据
        _data_store[dataset_id] = df

        # 生成元信息
        metadata = _generate_metadata(df, file_path)
        _metadata_store[dataset_id] = metadata

        logger.info(f"Loaded {file_path}: {len(df)} rows, {len(df.columns)} columns")

        return {
            "success": True,
            "dataset_id": dataset_id,
            "encoding_used": used_encoding,
            "dataframe_info": {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            },
            "preview": df.head(5).to_dict(orient="records"),
        }

    except FileNotFoundError:
        return {"success": False, "error": f"文件不存在: {file_path}"}
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return {"success": False, "error": str(e)}


def load_excel(file_path: str, sheet_name: str | None = None, **kwargs) -> dict[str, Any]:
    """加载 Excel 文件"""
    try:
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name, **kwargs)
        else:
            df = pd.read_excel(file_path, **kwargs)

        # 清理 BOM
        df.columns = [
            col.replace("\ufeff", "") if isinstance(col, str) else col
            for col in df.columns
        ]

        dataset_id = Path(file_path).stem + "_" + str(hash(file_path) % 10000)
        _data_store[dataset_id] = df

        metadata = _generate_metadata(df, file_path)
        _metadata_store[dataset_id] = metadata

        # 获取所有 sheet 名称
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names

        return {
            "success": True,
            "dataset_id": dataset_id,
            "sheet_names": sheet_names,
            "dataframe_info": {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
            },
            "preview": df.head(5).to_dict(orient="records"),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def load_json(file_path: str, orient: str = "records", **kwargs) -> dict[str, Any]:
    """加载 JSON 文件"""
    try:
        df = pd.read_json(file_path, orient=orient, **kwargs)

        dataset_id = Path(file_path).stem + "_" + str(hash(file_path) % 10000)
        _data_store[dataset_id] = df

        metadata = _generate_metadata(df, file_path)
        _metadata_store[dataset_id] = metadata

        return {
            "success": True,
            "dataset_id": dataset_id,
            "dataframe_info": {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
            },
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def validate_data(dataset_id: str) -> dict[str, Any]:
    """
    验证数据质量

    检查:
    - 空值统计
    - 重复行
    - 数据类型一致性
    - 异常值标记
    """
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    df = _data_store[dataset_id]
    issues = []

    # 空值检查
    missing = df.isnull().sum()
    missing_cols = {col: int(count) for col, count in missing.items() if count > 0}
    if missing_cols:
        issues.append({
            "type": "missing_values",
            "severity": "warning",
            "details": missing_cols,
        })

    # 重复行检查
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        issues.append({
            "type": "duplicates",
            "severity": "info",
            "details": {"count": int(duplicates)},
        })

    # 类型混合检查
    for col in df.columns:
        if df[col].dtype == "object":
            types = df[col].dropna().apply(type).nunique()
            if types > 1:
                issues.append({
                    "type": "mixed_types",
                    "severity": "warning",
                    "details": {"column": col, "type_count": types},
                })

    # 计算质量分数
    quality_score = 100
    for issue in issues:
        if issue["severity"] == "error":
            quality_score -= 20
        elif issue["severity"] == "warning":
            quality_score -= 10
        else:
            quality_score -= 5

    return {
        "success": True,
        "dataset_id": dataset_id,
        "quality_score": max(0, quality_score),
        "issues": issues,
        "is_valid": quality_score >= 60,
    }


def get_metadata(dataset_id: str) -> dict[str, Any]:
    """获取数据集详细元信息"""
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    df = _data_store[dataset_id]
    metadata = _metadata_store.get(dataset_id, {})

    # 增强元信息
    enhanced = {
        **metadata,
        "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
        "columns_detail": [],
    }

    for col in df.columns:
        col_info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isnull().sum()),
            "null_pct": round(df[col].isnull().sum() / len(df) * 100, 2),
            "unique_count": int(df[col].nunique()),
        }

        # 类型特定信息
        if df[col].dtype in ["int64", "float64"]:
            col_info.update({
                "min": float(df[col].min()) if not df[col].isnull().all() else None,
                "max": float(df[col].max()) if not df[col].isnull().all() else None,
                "mean": float(df[col].mean()) if not df[col].isnull().all() else None,
            })
        elif df[col].dtype == "object":
            col_info["sample_values"] = df[col].dropna().head(3).tolist()

        enhanced["columns_detail"].append(col_info)

    return {"success": True, "metadata": enhanced}


def clean_column_names(dataset_id: str, case: str = "snake") -> dict[str, Any]:
    """
    清理列名

    Args:
        dataset_id: 数据集 ID
        case: 目标格式 (snake/camel/lower/upper)
    """
    if dataset_id not in _data_store:
        return {"success": False, "error": f"数据集不存在: {dataset_id}"}

    df = _data_store[dataset_id]
    old_names = list(df.columns)
    new_names = []

    for col in old_names:
        # 移除 BOM
        name = col.replace("\ufeff", "") if isinstance(col, str) else str(col)

        # 转换格式
        if case == "lower":
            name = name.lower()
        elif case == "upper":
            name = name.upper()
        elif case == "snake":
            name = name.lower().replace(" ", "_").replace("-", "_")
        elif case == "camel":
            parts = name.lower().replace("_", " ").replace("-", " ").split()
            name = parts[0] + "".join(p.capitalize() for p in parts[1:]) if parts else name

        new_names.append(name)

    df.columns = new_names

    return {
        "success": True,
        "old_names": old_names,
        "new_names": new_names,
    }


def get_dataframe(dataset_id: str) -> pd.DataFrame | None:
    """获取 DataFrame（内部使用）"""
    return _data_store.get(dataset_id)


def _generate_metadata(df: pd.DataFrame, file_path: str) -> dict[str, Any]:
    """生成数据集元信息"""
    path = Path(file_path)

    missing = df.isnull().sum()
    missing_info = {col: int(count) for col, count in missing.items() if count > 0}

    return {
        "file_name": path.name,
        "file_path": str(path.absolute()),
        "num_rows": len(df),
        "num_cols": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_info": missing_info,
        "has_numeric": len(df.select_dtypes(include=["number"]).columns) > 0,
        "has_categorical": len(df.select_dtypes(include=["object", "category"]).columns) > 0,
        "has_datetime": len(df.select_dtypes(include=["datetime"]).columns) > 0,
        "numeric_columns": list(df.select_dtypes(include=["number"]).columns),
        "categorical_columns": list(df.select_dtypes(include=["object", "category"]).columns),
    }


# MCP Server Tool Registry
TOOLS = {
    "load_csv": load_csv,
    "load_excel": load_excel,
    "load_json": load_json,
    "validate_data": validate_data,
    "get_metadata": get_metadata,
    "clean_column_names": clean_column_names,
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
    import sys

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        result = load_csv(file_path)
        print(json.dumps(result, indent=2, default=str))