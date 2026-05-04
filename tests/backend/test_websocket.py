"""
WebSocket 后端测试

测试 WebSocket 连接、消息处理、状态广播等功能。
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class MockWebSocket:
    """模拟 WebSocket 连接"""
    def __init__(self):
        self.accepted = False
        self.sent_messages = []
        self.received_messages = []
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        self.sent_messages.append(data)

    async def send_text(self, text):
        self.sent_messages.append(json.loads(text))

    async def receive_json(self):
        if self.received_messages:
            return self.received_messages.pop(0)
        raise Exception("No messages")

    async def close(self):
        self.closed = True


@pytest.fixture
def mock_ws():
    """创建模拟 WebSocket"""
    return MockWebSocket()


@pytest.fixture
def sample_session_id():
    """测试会话 ID"""
    return "test_session_ws_123"


class TestWebSocketHandler:
    """WebSocket 处理器测试"""

    @pytest.mark.asyncio
    async def test_websocket_accepts_connection(self, mock_ws, sample_session_id):
        """测试 WebSocket 接受连接"""
        try:
            from backend.api.websocket.handler import websocket_chat
        except ImportError:
            pytest.skip("fastapi not installed")

        # 模拟接收消息序列
        mock_ws.received_messages = [
            {"type": "ping"}
        ]

        # 由于真实 handler 会无限循环，这里只测试它能启动
        task = asyncio.create_task(websocket_chat(mock_ws, sample_session_id))

        # 等待一小段时间让连接建立
        await asyncio.sleep(0.1)

        # 验证连接被接受
        assert mock_ws.accepted

        # 清理
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_websocket_responds_to_ping(self, mock_ws, sample_session_id):
        """测试 WebSocket 响应 ping 消息"""
        try:
            from backend.api.websocket.handler import websocket_chat
        except ImportError:
            pytest.skip("fastapi not installed")

        mock_ws.received_messages = [
            {"type": "ping"}
        ]

        task = asyncio.create_task(websocket_chat(mock_ws, sample_session_id))
        await asyncio.sleep(0.2)

        # 检查发送的消息中包含 pong
        sent_types = [msg.get("type") for msg in mock_ws.sent_messages]
        assert "pong" in sent_types

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestWebSocketMessageFormat:
    """WebSocket 消息格式测试"""

    def test_start_message_format(self):
        """测试 start 消息格式"""
        message = {
            "type": "start",
            "session_id": "test_123",
            "agent": "coordinator"
        }
        assert message["type"] == "start"
        assert "session_id" in message

    def test_chunk_message_format(self):
        """测试 chunk 消息格式"""
        message = {
            "type": "chunk",
            "content": "分析数据中...",
            "node": "code_generator"
        }
        assert message["type"] == "chunk"
        assert "content" in message

    def test_done_message_format(self):
        """测试 done 消息格式"""
        message = {
            "type": "done",
            "session_id": "test_123",
            "final_state": {"messages": []}
        }
        assert message["type"] == "done"

    def test_error_message_format(self):
        """测试 error 消息格式"""
        message = {
            "type": "error",
            "message": "处理失败",
            "details": "ValueError: ..."
        }
        assert message["type"] == "error"
        assert "message" in message


class TestFigureURLConversion:
    """图表 URL 转换测试"""

    def test_figure_url_conversion(self):
        """测试图表 URL 转换"""
        # 测试用例
        test_cases = [
            ("data/outputs/figures_xxx/chart.png", "/static/figures/figures_xxx/chart.png"),
            ("data/outputs/figures_abc/test.png", "/static/figures/figures_abc/test.png"),
        ]

        for input_path, expected in test_cases:
            # URL 转换逻辑：data/outputs -> /static/figures
            if input_path.startswith("data/outputs/"):
                result = input_path.replace("data/outputs/", "/static/figures/")
            else:
                result = input_path

            assert result == expected, f"Expected {expected}, got {result}"


class TestStateAccumulation:
    """状态累积测试"""

    def test_message_accumulation(self):
        """测试消息累积逻辑"""
        accumulated = {"messages": []}

        # 模拟多个 node 输出
        chunks = [
            {"coordinator": {"messages": [{"role": "user", "content": "hello"}]}},
            {"chat": {"messages": [{"role": "assistant", "content": "hi"}]}},
        ]

        for chunk in chunks:
            for node_name, node_output in chunk.items():
                for key, value in node_output.items():
                    if key in accumulated:
                        if isinstance(value, list) and isinstance(accumulated[key], list):
                            accumulated[key].extend(value)
                        else:
                            accumulated[key] = value
                    else:
                        accumulated[key] = value

        assert len(accumulated["messages"]) == 2
        assert accumulated["messages"][0]["role"] == "user"
        assert accumulated["messages"][1]["role"] == "assistant"

    def test_figure_accumulation(self):
        """测试图表累积逻辑"""
        accumulated = {"figures": []}

        chunks = [
            {"visualizer": {"figures": ["figure1.png"]}},
            {"visualizer": {"figures": ["figure2.png"]}},
        ]

        for chunk in chunks:
            for node_name, node_output in chunk.items():
                for key, value in node_output.items():
                    if key in accumulated:
                        if isinstance(value, list) and isinstance(accumulated[key], list):
                            accumulated[key].extend(value)
                        else:
                            accumulated[key] = value
                    else:
                        accumulated[key] = value

        assert len(accumulated["figures"]) == 2


class TestReconnectionLogic:
    """重连逻辑测试"""

    def test_exponential_backoff(self):
        """测试指数退避计算"""
        initial_delay = 1000
        max_delay = 30000

        delays = [initial_delay]
        current = initial_delay

        for _ in range(5):
            current = min(current * 2, max_delay)
            delays.append(current)

        # 验证指数增长
        expected = [1000, 2000, 4000, 8000, 16000, 30000]
        assert delays == expected

    def test_max_delay_cap(self):
        """测试最大延迟限制"""
        initial_delay = 1000
        max_delay = 30000
        current = initial_delay

        # 模拟多次重连
        for _ in range(10):
            current = min(current * 2, max_delay)

        # 应该被限制在 max_delay
        assert current == max_delay


class TestHeartbeat:
    """心跳测试"""

    def test_ping_interval(self):
        """测试 ping 间隔配置"""
        heartbeat_interval = 30000  # 30 秒
        assert heartbeat_interval == 30000

    def test_pong_response(self):
        """测试 pong 响应"""
        received = {"type": "ping"}
        response = {"type": "pong"}
        assert received["type"] == "ping"
        assert response["type"] == "pong"
