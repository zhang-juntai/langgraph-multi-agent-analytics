"""Subprocess-based Python sandbox for deterministic analysis execution."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from configs.settings import settings
from src.graph.state import CodeResult

logger = logging.getLogger(__name__)

DANGEROUS_PATTERNS = [
    "os.system",
    "subprocess",
    "shutil.rmtree",
    "__import__",
    "exec(",
    "eval(",
    "compile(",
    "open('/etc",
    "open('/proc",
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "importlib",
    "ctypes",
    "socket.",
    "requests.",
    "urllib.",
    "http.client",
]

WRAPPER_TEMPLATE = '''
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

FIGURE_DIR = "{figure_dir}"
DATA_FILES = {data_files}
_figure_paths = []


def _save_all_figures():
    import uuid as _uuid

    for _fig_num in plt.get_fignums():
        _fig = plt.figure(_fig_num)
        _fig_path = os.path.join(FIGURE_DIR, f"fig_{{_uuid.uuid4().hex[:8]}}.png")
        _fig.savefig(_fig_path, dpi=150, bbox_inches="tight")
        _figure_paths.append(_fig_path)
        print(f"[FIGURE_SAVED]{{_fig_path}}")
    plt.close("all")


plt.show = lambda *args, **kwargs: _save_all_figures()

_loaded_dataframes = {{}}
for _name, _path in DATA_FILES.items():
    try:
        _lower = _path.lower()
        if _lower.endswith(".csv") or _lower.endswith(".tsv"):
            _sep = "\\t" if _lower.endswith(".tsv") else ","
            _loaded_dataframes[_name] = pd.read_csv(_path, encoding="utf-8-sig", sep=_sep)
        elif _lower.endswith(".xlsx") or _lower.endswith(".xls"):
            _loaded_dataframes[_name] = pd.read_excel(_path)
        elif _lower.endswith(".json"):
            _loaded_dataframes[_name] = pd.read_json(_path)
    except Exception as _e:
        print(f"[WARNING] failed to load dataset {{_name}}: {{_e}}", file=sys.stderr)

if len(_loaded_dataframes) == 1:
    df = list(_loaded_dataframes.values())[0]
elif len(_loaded_dataframes) > 1:
    for _k, _v in _loaded_dataframes.items():
        globals()[_k] = _v

{user_code}

if plt.get_fignums():
    _save_all_figures()
'''


def _check_code_safety(code: str) -> list[str]:
    warnings: list[str] = []
    code_lower = code.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in code_lower:
            warnings.append(f"Blocked dangerous pattern: {pattern}")
    return warnings


def _resolve_dataset_path(ds: dict, index: int, materialized_files: list[str]) -> str:
    """Return a local path for a dataset, materializing db:// files when needed."""
    file_path = ds.get("file_path", "") or ""
    if file_path and not file_path.startswith("db://"):
        return file_path

    file_id = ds.get("file_storage_id")
    if file_path.startswith("db://"):
        file_id = file_path.removeprefix("db://")

    if not file_id:
        return file_path

    from src.storage.file_store import get_file_store

    store = get_file_store()
    content = store.get_file(file_id)
    if content is None:
        raise FileNotFoundError(f"Stored dataset not found: {file_id}")

    info = store.get_file_info(file_id) or {}
    filename = info.get("filename") or ds.get("file_name") or f"dataset_{index}.csv"
    suffix = Path(filename).suffix or ".csv"

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        suffix=suffix,
        prefix=f"sandbox_data_{file_id[:8]}_",
        dir=str(settings.DATA_DIR),
    )
    with os.fdopen(fd, "wb") as f:
        f.write(content)

    materialized_files.append(temp_path)
    return temp_path


def _cleanup(paths: list[str]) -> None:
    for path in paths:
        try:
            os.unlink(path)
        except OSError:
            pass


def execute_code(
    code: str,
    datasets: list[dict] | None = None,
    timeout: int | None = None,
) -> CodeResult:
    """Execute generated Python code and return traceable stdout/errors/figures."""
    timeout = timeout or settings.SANDBOX_TIMEOUT

    safety_warnings = _check_code_safety(code)
    if safety_warnings:
        logger.warning("Sandbox safety check blocked code: %s", safety_warnings)
        return CodeResult(
            code=code,
            stdout="",
            stderr="\n".join(safety_warnings),
            success=False,
            figures=[],
            dataframes={},
        )

    exec_id = uuid.uuid4().hex[:8]
    figure_dir = settings.OUTPUT_DIR / f"figures_{exec_id}"
    figure_dir.mkdir(parents=True, exist_ok=True)

    materialized_files: list[str] = []
    script_path = tempfile.mktemp(suffix=".py", prefix=f"sandbox_{exec_id}_")

    try:
        data_files = {}
        for i, ds in enumerate(datasets or []):
            name = ds.get("file_name", f"dataset_{i}").replace(".", "_").replace(" ", "_")
            var_name = Path(name).stem
            data_files[var_name] = _resolve_dataset_path(ds, i, materialized_files)

        wrapped_code = WRAPPER_TEMPLATE.format(
            figure_dir=str(figure_dir).replace("\\", "/"),
            data_files=repr({k: v.replace("\\", "/") for k, v in data_files.items()}),
            user_code=code,
        )

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(wrapped_code)

        logger.info("Executing sandbox code [id=%s, timeout=%ss]", exec_id, timeout)
        result = subprocess.run(
            [sys.executable, "-X", "utf8", script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(settings.DATA_DIR),
            env={
                **os.environ,
                "PYTHONHASHSEED": "0",
                "MPLBACKEND": "Agg",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
        )

        figures: list[str] = []
        clean_stdout_lines: list[str] = []
        for line in result.stdout.splitlines():
            if line.startswith("[FIGURE_SAVED]"):
                fig_path = line.replace("[FIGURE_SAVED]", "").strip()
                if Path(fig_path).exists():
                    figures.append(fig_path)
            else:
                clean_stdout_lines.append(line)

        clean_stdout = "\n".join(clean_stdout_lines).strip()
        success = result.returncode == 0
        logger.info(
            "Sandbox finished [id=%s, success=%s, figures=%s]",
            exec_id,
            success,
            len(figures),
        )

        return CodeResult(
            code=code,
            stdout=clean_stdout,
            stderr=result.stderr.strip(),
            success=success,
            figures=figures,
            dataframes={},
        )

    except subprocess.TimeoutExpired:
        logger.warning("Sandbox timeout [id=%s, timeout=%ss]", exec_id, timeout)
        return CodeResult(
            code=code,
            stdout="",
            stderr=f"Code execution timed out after {timeout} seconds.",
            success=False,
            figures=[],
            dataframes={},
        )
    except Exception as e:
        logger.error("Sandbox execution failed [id=%s]: %s", exec_id, e)
        return CodeResult(
            code=code,
            stdout="",
            stderr=f"Code execution failed: {str(e)}",
            success=False,
            figures=[],
            dataframes={},
        )
    finally:
        _cleanup([script_path, *materialized_files])
