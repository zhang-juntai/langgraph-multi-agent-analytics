"""
MCP Client - 模型上下文协议客户端

提供与 MCP 服务器通信的统一接口。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class MCPServerType(Enum):
    """MCP 服务器类型"""
    DATA = "mcp-data"
    CHART = "mcp-chart"
    ML = "mcp-ml"
    FILEIO = "mcp-fileio"


@dataclass
class MCPResponse:
    """MCP 响应"""
    success: bool
    data: dict[str, Any]
    error: str | None = None


class MCPClient:
    """
    MCP 客户端

    提供与 MCP 服务器通信的统一接口。
    支持本地函数调用和远程 HTTP 调用。
    """

    def __init__(self, mode: str = "local"):
        """
        初始化 MCP 客户端

        Args:
            mode: 运行模式
                - "local": 本地函数调用（开发/测试）
                - "http": HTTP 远程调用（生产）
        """
        self.mode = mode
        self._local_handlers: dict[str, Callable] = {}
        self._connections: dict[str, Any] = {}

        # 本地模式下加载处理器
        if mode == "local":
            self._load_local_handlers()

    def _load_local_handlers(self):
        """加载本地处理器（直接调用函数）"""
        try:
            import sys
            from pathlib import Path

            # 添加项目根目录到 path
            project_root = Path(__file__).parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            # 加载 mcp-data 处理器
            from mcp_servers.mcp_data.main import TOOLS as data_tools, _data_store
            self._local_handlers["mcp-data"] = data_tools

            # 加载 mcp-chart 处理器并共享数据存储
            from mcp_servers.mcp_chart.main import TOOLS as chart_tools, set_data_store
            self._local_handlers["mcp-chart"] = chart_tools

            # 共享数据存储
            set_data_store(_data_store)

            logger.info("Local MCP handlers loaded")

        except ImportError as e:
            logger.warning(f"Could not load local handlers: {e}")

    async def call(
        self,
        server: str | MCPServerType,
        tool: str,
        **params,
    ) -> MCPResponse:
        """
        调用 MCP 工具

        Args:
            server: 服务器名称或类型
            tool: 工具名称
            **params: 工具参数

        Returns:
            MCPResponse
        """
        server_name = server.value if isinstance(server, MCPServerType) else server

        if self.mode == "local":
            return await self._call_local(server_name, tool, params)
        else:
            return await self._call_http(server_name, tool, params)

    async def _call_local(
        self,
        server: str,
        tool: str,
        params: dict,
    ) -> MCPResponse:
        """本地函数调用"""
        try:
            handlers = self._local_handlers.get(server)
            if not handlers:
                return MCPResponse(
                    success=False,
                    data={},
                    error=f"Unknown server: {server}",
                )

            handler = handlers.get(tool)
            if not handler:
                return MCPResponse(
                    success=False,
                    data={},
                    error=f"Unknown tool: {tool}",
                )

            # 调用处理函数
            result = handler(**params)

            return MCPResponse(
                success=result.get("success", True),
                data=result,
                error=result.get("error"),
            )

        except Exception as e:
            logger.error(f"MCP call failed: {e}")
            return MCPResponse(
                success=False,
                data={},
                error=str(e),
            )

    async def _call_http(
        self,
        server: str,
        tool: str,
        params: dict,
    ) -> MCPResponse:
        """HTTP 远程调用"""
        import aiohttp

        # 获取服务器 URL
        server_url = self._get_server_url(server)
        if not server_url:
            return MCPResponse(
                success=False,
                data={},
                error=f"Unknown server: {server}",
            )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{server_url}/tools/{tool}",
                    json=params,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    data = await response.json()

                    return MCPResponse(
                        success=response.status == 200,
                        data=data,
                        error=data.get("error") if response.status != 200 else None,
                    )

        except asyncio.TimeoutError:
            return MCPResponse(
                success=False,
                data={},
                error="Request timeout",
            )
        except Exception as e:
            return MCPResponse(
                success=False,
                data={},
                error=str(e),
            )

    def _get_server_url(self, server: str) -> str | None:
        """获取服务器 URL"""
        # 从配置或环境变量读取
        import os

        urls = {
            "mcp-data": os.getenv("MCP_DATA_URL", "http://localhost:8001"),
            "mcp-chart": os.getenv("MCP_CHART_URL", "http://localhost:8002"),
            "mcp-ml": os.getenv("MCP_ML_URL", "http://localhost:8003"),
        }

        return urls.get(server)

    async def batch_call(
        self,
        calls: list[dict[str, Any]],
    ) -> list[MCPResponse]:
        """
        批量调用 MCP 工具

        Args:
            calls: 调用列表，每个包含 server, tool, params

        Returns:
            响应列表
        """
        tasks = [
            self.call(call["server"], call["tool"], **call.get("params", {}))
            for call in calls
        ]

        return await asyncio.gather(*tasks)


# 全局实例
_mcp_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """获取全局 MCP 客户端实例"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient(mode="local")
    return _mcp_client


async def mcp_call(server: str, tool: str, **params) -> MCPResponse:
    """便捷函数：调用 MCP 工具"""
    return await get_mcp_client().call(server, tool, **params)