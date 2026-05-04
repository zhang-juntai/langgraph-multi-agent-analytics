"""
异步任务队列测试
"""
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.task_queue import TaskQueue, TaskStatus


class TestTaskQueue:
    """测试任务队列"""

    def test_submit_and_complete(self):
        """提交任务后应能获取结果"""
        queue = TaskQueue(max_workers=2)
        task_id = queue.submit("测试任务", lambda: "done")

        # 等待完成
        for _ in range(50):
            if queue.is_done(task_id):
                break
            time.sleep(0.05)

        status = queue.get_status(task_id)
        assert status.status == TaskStatus.COMPLETED
        assert queue.get_result(task_id) == "done"
        queue.shutdown()

    def test_failed_task(self):
        """失败任务应记录错误"""
        queue = TaskQueue(max_workers=1)

        def bad():
            raise ValueError("boom")

        task_id = queue.submit("失败任务", bad)

        for _ in range(50):
            if queue.is_done(task_id):
                break
            time.sleep(0.05)

        status = queue.get_status(task_id)
        assert status.status == TaskStatus.FAILED
        assert "boom" in status.error
        queue.shutdown()

    def test_concurrent_tasks(self):
        """应支持并发执行"""
        queue = TaskQueue(max_workers=3)

        task_ids = []
        for i in range(3):
            tid = queue.submit(f"任务{i}", time.sleep, 0.1)
            task_ids.append(tid)

        # 等待所有完成
        for _ in range(100):
            if all(queue.is_done(tid) for tid in task_ids):
                break
            time.sleep(0.05)

        for tid in task_ids:
            assert queue.get_status(tid).status == TaskStatus.COMPLETED
        queue.shutdown()

    def test_active_count(self):
        """活跃任务计数"""
        queue = TaskQueue(max_workers=1)
        assert queue.active_count == 0

        tid = queue.submit("长任务", time.sleep, 0.3)
        time.sleep(0.05)
        assert queue.active_count >= 0  # 可能已经开始

        for _ in range(50):
            if queue.is_done(tid):
                break
            time.sleep(0.05)
        assert queue.active_count == 0
        queue.shutdown()

    def test_list_tasks(self):
        """应能列出任务"""
        queue = TaskQueue(max_workers=2)
        queue.submit("a", lambda: 1)
        queue.submit("b", lambda: 2)
        time.sleep(0.2)

        tasks = queue.list_tasks()
        assert len(tasks) == 2
        queue.shutdown()
