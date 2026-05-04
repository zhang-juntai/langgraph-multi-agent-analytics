"""
MCP Protocol - 协议定义

定义 MCP 服务器和客户端之间的通信协议。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MCPMessageType(Enum):
    """MCP 消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


@dataclass
class MCPToolDefinition:
    """MCP 工具定义"""
    name: str
    description: str
    parameters: list[dict[str, Any]]
    returns: list[dict[str, Any]]
    version: str = "1.0.0"


@dataclass
class MCPRequest:
    """MCP 请求"""
    id: str
    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    timeout: int = 60


@dataclass
class MCPResult:
    """MCP 结果"""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: int | None = None


@dataclass
class MCPServerInfo:
    """MCP 服务器信息"""
    name: str
    version: str
    description: str
    tools: list[MCPToolDefinition]
    status: str = "running"


# 标准错误代码
class MCPErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_START = -32000
    SERVER_ERROR_END = -32099