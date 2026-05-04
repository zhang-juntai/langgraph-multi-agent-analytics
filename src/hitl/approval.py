"""
HITL (Human-in-the-Loop) 审批模块
在关键操作前请求人工确认，防止 LLM 生成的代码造成意外。

审批级别：
- INFO: 信息通知（不阻塞，仅展示）
- CONFIRM: 需要确认（用户点确认后继续）
- BLOCK: 强制拦截（安全违规，无法继续）

设计原则：
- 审批请求通过 State 传递（approval_request / approval_response）
- Streamlit 前端渲染确认弹窗
- 支持自动审批模式（开发/测试时跳过确认）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ApprovalLevel(str, Enum):
    """审批级别"""
    INFO = "info"          # 信息通知
    CONFIRM = "confirm"    # 需要确认
    BLOCK = "block"        # 强制拦截


class ApprovalStatus(str, Enum):
    """审批状态"""
    PENDING = "pending"      # 等待审批
    APPROVED = "approved"    # 已批准
    REJECTED = "rejected"    # 已拒绝
    AUTO = "auto"            # 自动审批


@dataclass
class ApprovalRequest:
    """审批请求"""
    id: str                           # 唯一 ID
    level: ApprovalLevel              # 审批级别
    agent: str                        # 发起 Agent
    action: str                       # 操作描述（如 "执行代码"）
    detail: str                       # 详细内容（如代码片段）
    risks: list[str] = field(default_factory=list)  # 风险点
    status: ApprovalStatus = ApprovalStatus.PENDING
    response_message: str = ""        # 审批回复


# ============================================================
# 代码安全分析（决定是否需要审批）
# ============================================================

# 需要 CONFIRM 级别的代码模式
CONFIRM_PATTERNS = [
    ("文件写入", ["open(", "to_csv", "to_excel", "to_json", "write("]),
    ("大量计算", ["for i in range(1000", "while True", "itertools.product"]),
    ("外部数据", ["read_csv(", "read_excel(", "read_json("]),
]

# 需要 BLOCK 级别的代码模式（和 sandbox 的安全检查对齐）
BLOCK_PATTERNS = [
    ("系统命令", ["os.system", "subprocess", "os.remove", "shutil.rmtree"]),
    ("危险操作", ["exec(", "eval(", "__import__", "importlib"]),
    ("网络请求", ["requests.", "urllib.", "socket.", "http.client"]),
]


def analyze_code_risk(code: str) -> ApprovalRequest | None:
    """
    分析代码风险，决定是否需要人工审批。

    Args:
        code: 待执行的代码

    Returns:
        ApprovalRequest 如果需要审批，None 如果不需要
    """
    import uuid

    code_lower = code.lower()

    # 检查 BLOCK 级别
    for category, patterns in BLOCK_PATTERNS:
        for pattern in patterns:
            if pattern.lower() in code_lower:
                return ApprovalRequest(
                    id=uuid.uuid4().hex[:8],
                    level=ApprovalLevel.BLOCK,
                    agent="sandbox",
                    action=f"拦截危险代码: {category}",
                    detail=code[:500],
                    risks=[f"检测到 {category} 操作: {pattern}"],
                )

    # 检查 CONFIRM 级别
    risks = []
    for category, patterns in CONFIRM_PATTERNS:
        for pattern in patterns:
            if pattern.lower() in code_lower:
                risks.append(f"{category}: {pattern}")

    if risks:
        return ApprovalRequest(
            id=uuid.uuid4().hex[:8],
            level=ApprovalLevel.CONFIRM,
            agent="code_generator",
            action="执行代码前需要确认",
            detail=code[:500],
            risks=risks,
        )

    return None  # 不需要审批


# ============================================================
# 审批管理器
# ============================================================

class ApprovalManager:
    """
    审批管理器
    管理审批请求队列和自动审批策略。
    """

    def __init__(self, auto_approve: bool = False):
        """
        Args:
            auto_approve: 是否自动审批所有 CONFIRM 级别的请求
                         （开发/测试模式下使用）
        """
        self.auto_approve = auto_approve
        self._pending: dict[str, ApprovalRequest] = {}

    def submit(self, request: ApprovalRequest) -> ApprovalRequest:
        """提交审批请求"""
        if request.level == ApprovalLevel.BLOCK:
            # BLOCK 级别直接拒绝
            request.status = ApprovalStatus.REJECTED
            request.response_message = "安全违规，操作已被拦截。"
            logger.warning(f"HITL BLOCKED: {request.action} - {request.risks}")
            return request

        if self.auto_approve and request.level == ApprovalLevel.CONFIRM:
            # 自动审批模式
            request.status = ApprovalStatus.AUTO
            request.response_message = "自动审批（开发模式）"
            logger.info(f"HITL AUTO-APPROVED: {request.action}")
            return request

        # 加入待审批队列
        request.status = ApprovalStatus.PENDING
        self._pending[request.id] = request
        logger.info(f"HITL PENDING: {request.id} - {request.action}")
        return request

    def approve(self, request_id: str, message: str = "") -> bool:
        """批准审批请求"""
        if request_id in self._pending:
            req = self._pending.pop(request_id)
            req.status = ApprovalStatus.APPROVED
            req.response_message = message or "已批准"
            logger.info(f"HITL APPROVED: {request_id}")
            return True
        return False

    def reject(self, request_id: str, message: str = "") -> bool:
        """拒绝审批请求"""
        if request_id in self._pending:
            req = self._pending.pop(request_id)
            req.status = ApprovalStatus.REJECTED
            req.response_message = message or "已拒绝"
            logger.info(f"HITL REJECTED: {request_id}")
            return True
        return False

    def get_pending(self) -> list[ApprovalRequest]:
        """获取所有待审批请求"""
        return list(self._pending.values())

    @property
    def has_pending(self) -> bool:
        return len(self._pending) > 0


# 全局单例
_manager: ApprovalManager | None = None


def get_approval_manager(auto_approve: bool = False) -> ApprovalManager:
    global _manager
    if _manager is None:
        _manager = ApprovalManager(auto_approve=auto_approve)
    return _manager
