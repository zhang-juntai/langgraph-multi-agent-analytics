"""
HITL 审批系统测试
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.hitl.approval import (
    analyze_code_risk,
    ApprovalManager,
    ApprovalLevel,
    ApprovalStatus,
    ApprovalRequest,
)


class TestCodeRiskAnalysis:
    """测试代码风险分析"""

    def test_safe_code_no_approval(self):
        """安全代码不需要审批"""
        result = analyze_code_risk("import pandas as pd\nprint(df.describe())")
        assert result is None

    def test_block_os_system(self):
        """os.system 应被 BLOCK"""
        result = analyze_code_risk("os.system('rm -rf /')")
        assert result is not None
        assert result.level == ApprovalLevel.BLOCK

    def test_block_subprocess(self):
        """subprocess 应被 BLOCK"""
        result = analyze_code_risk("import subprocess\nsubprocess.run(['ls'])")
        assert result is not None
        assert result.level == ApprovalLevel.BLOCK

    def test_block_eval(self):
        """eval 应被 BLOCK"""
        result = analyze_code_risk("eval('1+1')")
        assert result is not None
        assert result.level == ApprovalLevel.BLOCK

    def test_confirm_file_write(self):
        """文件写入应需要 CONFIRM"""
        result = analyze_code_risk("df.to_csv('output.csv')")
        assert result is not None
        assert result.level == ApprovalLevel.CONFIRM

    def test_confirm_large_loop(self):
        """大循环应需要 CONFIRM"""
        result = analyze_code_risk("for i in range(1000000): pass")
        assert result is not None
        assert result.level == ApprovalLevel.CONFIRM


class TestApprovalManager:
    """测试审批管理器"""

    def test_auto_approve_mode(self):
        """自动审批模式下 CONFIRM 自动通过"""
        manager = ApprovalManager(auto_approve=True)
        req = ApprovalRequest(
            id="test1",
            level=ApprovalLevel.CONFIRM,
            agent="code_generator",
            action="执行代码",
            detail="print('hello')",
        )
        result = manager.submit(req)
        assert result.status == ApprovalStatus.AUTO

    def test_block_always_rejected(self):
        """BLOCK 级别即使自动审批也拒绝"""
        manager = ApprovalManager(auto_approve=True)
        req = ApprovalRequest(
            id="test2",
            level=ApprovalLevel.BLOCK,
            agent="sandbox",
            action="危险操作",
            detail="os.system('rm -rf /')",
        )
        result = manager.submit(req)
        assert result.status == ApprovalStatus.REJECTED

    def test_manual_approve(self):
        """手动审批流程"""
        manager = ApprovalManager(auto_approve=False)
        req = ApprovalRequest(
            id="test3",
            level=ApprovalLevel.CONFIRM,
            agent="code_generator",
            action="执行代码",
            detail="df.to_csv('out.csv')",
        )
        manager.submit(req)
        assert manager.has_pending

        manager.approve("test3", "确认执行")
        assert not manager.has_pending

    def test_manual_reject(self):
        """手动拒绝流程"""
        manager = ApprovalManager(auto_approve=False)
        req = ApprovalRequest(
            id="test4",
            level=ApprovalLevel.CONFIRM,
            agent="code_generator",
            action="执行代码",
            detail="大量计算",
        )
        manager.submit(req)
        manager.reject("test4", "不执行")
        assert not manager.has_pending

    def test_get_pending(self):
        """应能获取所有待审批请求"""
        manager = ApprovalManager(auto_approve=False)
        for i in range(3):
            manager.submit(ApprovalRequest(
                id=f"req{i}",
                level=ApprovalLevel.CONFIRM,
                agent="test",
                action=f"操作{i}",
                detail="",
            ))
        assert len(manager.get_pending()) == 3
