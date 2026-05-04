const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export type WsMessageHandler = (data: {
  type: string
  content?: string | string[]
  message?: string
  agent?: string
  agent_display?: string
  skill?: string
  skill_display?: string
  pending?: number
  completed?: number
}) => void

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting'

export interface WebSocketOptions {
  heartbeatInterval?: number
  maxReconnectDelay?: number
  initialReconnectDelay?: number
  accessToken?: string
  getAccessToken?: () => string | null | undefined
}

export class ChatWebSocket {
  private ws: WebSocket | null = null
  private sessionId: string
  private onMessage: WsMessageHandler
  private stopped = false
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private reconnectDelay: number
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private messageQueue: string[] = []
  private options: Required<Omit<WebSocketOptions, 'accessToken' | 'getAccessToken'>> &
    Pick<WebSocketOptions, 'accessToken' | 'getAccessToken'>

  constructor(sessionId: string, onMessage: WsMessageHandler, options?: WebSocketOptions) {
    this.sessionId = sessionId
    this.onMessage = onMessage
    this.options = {
      heartbeatInterval: options?.heartbeatInterval ?? 30000,
      maxReconnectDelay: options?.maxReconnectDelay ?? 30000,
      initialReconnectDelay: options?.initialReconnectDelay ?? 1000,
      accessToken: options?.accessToken,
      getAccessToken: options?.getAccessToken,
    }
    this.reconnectDelay = this.options.initialReconnectDelay
  }

  connect(): Promise<void> {
    this.stopped = false
    return new Promise((resolve, reject) => {
      const url = this.buildUrl()
      this.ws = new WebSocket(url)

      const timeout = setTimeout(() => {
        if (this.ws?.readyState !== WebSocket.OPEN) {
          this.ws?.close()
          reject(new Error('Connection timeout'))
        }
      }, 10000)

      this.ws.onopen = () => {
        clearTimeout(timeout)
        this.reconnectAttempts = 0
        this.reconnectDelay = this.options.initialReconnectDelay
        this.startHeartbeat()
        this.flushMessageQueue()
        resolve()
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'pong') return
          this.onMessage(data)
        } catch {
          // Ignore malformed messages.
        }
      }

      this.ws.onerror = () => {
        clearTimeout(timeout)
        reject(new Error('WebSocket connection failed'))
      }

      this.ws.onclose = () => {
        clearTimeout(timeout)
        this.stopHeartbeat()
        if (!this.stopped) this.scheduleReconnect()
      }
    })
  }

  private buildUrl(): string {
    const base = `${WS_BASE}/ws/chat/${this.sessionId}`
    const token = this.getToken()
    if (!token) return base
    const separator = base.includes('?') ? '&' : '?'
    return `${base}${separator}access_token=${encodeURIComponent(token)}`
  }

  private getToken(): string {
    const provided = this.options.getAccessToken?.() || this.options.accessToken
    if (provided) return provided
    if (typeof window === 'undefined') return ''
    return (
      window.localStorage.getItem('access_token') ||
      window.localStorage.getItem('id_token') ||
      window.localStorage.getItem('data_agent_access_token') ||
      ''
    )
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectAttempts += 1
    this.reconnectTimer = setTimeout(() => {
      this.connect().catch(() => undefined)
    }, this.reconnectDelay)
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.options.maxReconnectDelay)
  }

  private startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, this.options.heartbeatInterval)
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private flushMessageQueue() {
    while (this.messageQueue.length > 0 && this.ws?.readyState === WebSocket.OPEN) {
      const message = this.messageQueue.shift()
      if (message) this.send(message)
    }
  }

  send(message: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const accessToken = this.getToken()
      this.ws.send(JSON.stringify({ type: 'message', message, access_token: accessToken || undefined }))
    } else {
      this.messageQueue.push(message)
    }
  }

  disconnect() {
    this.stopped = true
    this.stopHeartbeat()
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close()
    this.ws = null
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  get status(): ConnectionStatus {
    if (this.stopped) return 'disconnected'
    if (!this.ws) return 'disconnected'
    if (this.ws.readyState === WebSocket.CONNECTING) return 'connecting'
    if (this.ws.readyState === WebSocket.OPEN) return 'connected'
    return 'reconnecting'
  }
}

export type { ChatWebSocket as WebSocket }
