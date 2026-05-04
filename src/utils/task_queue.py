"""
异步任务队列
支持长耗时分析任务的后台执行和并发处理。

设计：
- 基于 concurrent.futures.ThreadPoolExecutor（无外部依赖）
- 任务状态追踪：pending → running → completed / failed
- 结果缓存：任务完成后结果保留，供前端轮询
- 可扩展：生产环境可替换为 Celery + Redis

使用示例：
    queue = get_task_queue()
    task_id = queue.submit("分析销售趋势", graph.invoke, state_input, config=config)
    status = queue.get_status(task_id)  # pending/running/completed/failed
    result = queue.get_result(task_id)  # 完成后获取结果
"""
from __future__ import annotations

import logging
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """任务信息"""
    id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0          # 0.0 ~ 1.0
    message: str = ""              # 状态消息
    result: Any = None             # 执行结果
    error: str = ""                # 错误信息
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""


class TaskQueue:
    """
    异步任务队列

    Args:
        max_workers: 最大并发线程数
        max_history: 保留的历史任务数
    """

    def __init__(self, max_workers: int = 3, max_history: int = 50):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, TaskInfo] = {}
        self._futures: dict[str, Future] = {}
        self._max_history = max_history

    def submit(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> str:
        """
        提交异步任务。

        Args:
            name: 任务名称（显示用）
            func: 要执行的函数
            *args, **kwargs: 函数参数

        Returns:
            任务 ID
        """
        task_id = uuid.uuid4().hex[:8]
        task = TaskInfo(
            id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
        )
        self._tasks[task_id] = task

        def _run():
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now().isoformat()
            task.message = "正在执行..."
            logger.info(f"任务开始: {task_id} - {name}")
            try:
                result = func(*args, **kwargs)
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.progress = 1.0
                task.message = "完成"
                task.completed_at = datetime.now().isoformat()
                logger.info(f"任务完成: {task_id} - {name}")
                return result
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.message = f"失败: {str(e)[:200]}"
                task.completed_at = datetime.now().isoformat()
                logger.error(f"任务失败: {task_id} - {name}: {e}")
                raise

        future = self._executor.submit(_run)
        self._futures[task_id] = future

        # 清理过多历史
        self._cleanup_history()

        return task_id

    def get_status(self, task_id: str) -> TaskInfo | None:
        """获取任务状态"""
        return self._tasks.get(task_id)

    def get_result(self, task_id: str) -> Any | None:
        """获取任务结果（仅 COMPLETED 状态有效）"""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.COMPLETED:
            return task.result
        return None

    def is_done(self, task_id: str) -> bool:
        """任务是否已完成（成功或失败）"""
        task = self._tasks.get(task_id)
        if task:
            return task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        return True

    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        future = self._futures.get(task_id)
        task = self._tasks.get(task_id)
        if future and task:
            cancelled = future.cancel()
            if cancelled:
                task.status = TaskStatus.CANCELLED
                task.message = "已取消"
            return cancelled
        return False

    def list_tasks(self, status: TaskStatus = None) -> list[TaskInfo]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    @property
    def active_count(self) -> int:
        """当前活跃任务数"""
        return sum(
            1 for t in self._tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        )

    def _cleanup_history(self):
        """清理超出上限的已完成任务"""
        completed = [
            (tid, t) for tid, t in self._tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        ]
        if len(completed) > self._max_history:
            # 按时间排序，删除最旧的
            completed.sort(key=lambda x: x[1].completed_at)
            for tid, _ in completed[: len(completed) - self._max_history]:
                del self._tasks[tid]
                self._futures.pop(tid, None)

    def shutdown(self, wait: bool = True):
        """关闭线程池"""
        self._executor.shutdown(wait=wait)


# 全局单例
_queue: TaskQueue | None = None


def get_task_queue(max_workers: int = 3) -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue(max_workers=max_workers)
    return _queue
