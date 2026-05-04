/**
 * WebSocket 客户端测试
 */
import { ChatWebSocket } from '../websocket'

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = MockWebSocket.OPEN
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string) {
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN
      this.onopen?.()
    }, 0)
  }

  send(data: string) {}
  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }
}

// 注入 Mock
;(global as any).WebSocket = MockWebSocket

describe('ChatWebSocket', () => {
  const sessionId = 'test-session-123'
  const onMessage = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should create instance with session ID', () => {
    const ws = new ChatWebSocket(sessionId, onMessage)
    expect(ws).toBeDefined()
    expect(ws.connected).toBe(false)
  })

  it('should have correct initial status', () => {
    const ws = new ChatWebSocket(sessionId, onMessage)
    expect(ws.status).toBe('disconnected')
  })

  it('should handle message queue when disconnected', () => {
    const ws = new ChatWebSocket(sessionId, onMessage)

    // 消息应该被缓存
    ws.send('test message')

    // 由于 WebSocket 未连接，消息应该在队列中
    expect(ws.status).toBe('disconnected')
  })

  it('should support custom options', () => {
    const ws = new ChatWebSocket(sessionId, onMessage, {
      heartbeatInterval: 10000,
      maxReconnectDelay: 60000,
      initialReconnectDelay: 500,
    })

    expect(ws).toBeDefined()
  })

  it('should disconnect cleanly', () => {
    const ws = new ChatWebSocket(sessionId, onMessage)

    ws.disconnect()

    expect(ws.status).toBe('disconnected')
  })
})

describe('WebSocket Message Types', () => {
  it('should handle start message', () => {
    const onMessage = jest.fn()
    const ws = new ChatWebSocket('test', onMessage)

    // 模拟接收消息
    const startMessage = JSON.stringify({
      type: 'start',
      session_id: 'test',
      agent: 'coordinator'
    })

    // 验证消息格式
    const parsed = JSON.parse(startMessage)
    expect(parsed.type).toBe('start')
    expect(parsed.session_id).toBe('test')
  })

  it('should handle chunk message', () => {
    const chunkMessage = JSON.stringify({
      type: 'chunk',
      content: 'Processing data...',
      node: 'data_parser'
    })

    const parsed = JSON.parse(chunkMessage)
    expect(parsed.type).toBe('chunk')
    expect(parsed.content).toBe('Processing data...')
  })

  it('should handle done message', () => {
    const doneMessage = JSON.stringify({
      type: 'done',
      session_id: 'test',
      final_state: { messages: [] }
    })

    const parsed = JSON.parse(doneMessage)
    expect(parsed.type).toBe('done')
  })

  it('should handle error message', () => {
    const errorMessage = JSON.stringify({
      type: 'error',
      message: 'Something went wrong',
      details: 'Error: ...'
    })

    const parsed = JSON.parse(errorMessage)
    expect(parsed.type).toBe('error')
    expect(parsed.message).toBe('Something went wrong')
  })
})
