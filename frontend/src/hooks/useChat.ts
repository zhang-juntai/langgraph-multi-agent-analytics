'use client'

import { useCallback, useRef, useState } from 'react'
import { useAppStore } from '@/lib/store'
import { ChatWebSocket, type WsMessageHandler } from '@/lib/websocket'

export function useChat() {
  const wsRef = useRef<ChatWebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const sessions = useAppStore((s) => s.sessions)
  const isStreaming = useAppStore((s) => s.isStreaming)
  const addMessage = useAppStore((s) => s.addMessage)
  const setStreamingContent = useAppStore((s) => s.setStreamingContent)
  const setStreaming = useAppStore((s) => s.setStreaming)
  const setWsConnected = useAppStore((s) => s.setWsConnected)
  const setCode = useAppStore((s) => s.setCode)
  const setReport = useAppStore((s) => s.setReport)
  const setFigures = useAppStore((s) => s.setFigures)
  const addExecutionLog = useAppStore((s) => s.addExecutionLog)
  const clearExecutionLog = useAppStore((s) => s.clearExecutionLog)
  const updateSessionName = useAppStore((s) => s.updateSessionName)

  const generateTitle = (message: string): string => {
    const cleaned = message.trim().replace(/\s+/g, ' ')
    return cleaned.length > 20 ? `${cleaned.slice(0, 20)}...` : cleaned || 'New chat'
  }

  const connect = useCallback(
    async (sessionId: string) => {
      wsRef.current?.disconnect()

      const handler: WsMessageHandler = (data) => {
        switch (data.type) {
          case 'connected':
            setIsConnected(true)
            setWsConnected(true)
            break
          case 'start':
            setStreaming(true)
            clearExecutionLog()
            addMessage(sessionId, {
              role: 'assistant',
              content: '',
              timestamp: Date.now(),
            })
            break
          case 'agent':
            addExecutionLog({
              timestamp: Date.now(),
              type: 'agent',
              agent: data.agent,
              agentDisplay: data.agent_display,
            })
            break
          case 'skill':
            addExecutionLog({
              timestamp: Date.now(),
              type: 'skill',
              skill: data.skill,
              skillDisplay: data.skill_display,
            })
            break
          case 'chunk':
            if (typeof data.content === 'string') {
              setStreamingContent(sessionId, data.content)
              addExecutionLog({
                timestamp: Date.now(),
                type: 'chunk',
                content: data.content.substring(0, 100),
                agent: data.agent,
              })
            }
            break
          case 'code':
            if (typeof data.content === 'string') setCode(sessionId, data.content)
            break
          case 'report':
            if (typeof data.content === 'string') setReport(sessionId, data.content)
            break
          case 'figures':
            if (Array.isArray(data.content)) setFigures(sessionId, data.content)
            break
          case 'task_status':
            addExecutionLog({
              timestamp: Date.now(),
              type: 'chunk',
              content: `Pending tasks: ${data.pending ?? 0}, completed: ${data.completed ?? 0}`,
              agent: 'coordinator_p1',
            })
            break
          case 'validation_failed': {
            const content = formatValidationFailure(data.content)
            setStreamingContent(sessionId, content)
            addExecutionLog({
              timestamp: Date.now(),
              type: 'error',
              content,
              agent: 'sql_validator',
            })
            break
          }
          case 'validation':
            addExecutionLog({
              timestamp: Date.now(),
              type: 'chunk',
              content: `Validation records: ${Array.isArray(data.content) ? data.content.length : 0}`,
              agent: 'coordinator_p1',
            })
            break
          case 'audit':
            addExecutionLog({
              timestamp: Date.now(),
              type: 'chunk',
              content: `Audit events: ${Array.isArray(data.content) ? data.content.length : 0}`,
              agent: 'coordinator_p1',
            })
            break
          case 'memory_candidates':
            addExecutionLog({
              timestamp: Date.now(),
              type: 'chunk',
              content: `Memory candidates: ${Array.isArray(data.content) ? data.content.length : 0}`,
              agent: 'memory_extractor',
            })
            break
          case 'done':
            setStreaming(false)
            break
          case 'error':
            setStreaming(false)
            addExecutionLog({
              timestamp: Date.now(),
              type: 'error',
              content: data.message || 'WebSocket error',
            })
            break
        }
      }

      const ws = new ChatWebSocket(sessionId, handler)
      wsRef.current = ws

      try {
        await ws.connect()
      } catch (err) {
        setIsConnected(false)
        setWsConnected(false)
        throw err
      }
    },
    [
      addMessage,
      setStreamingContent,
      setStreaming,
      setWsConnected,
      setCode,
      setReport,
      setFigures,
      addExecutionLog,
      clearExecutionLog,
    ],
  )

  const sendMessage = useCallback(
    async (content: string) => {
      if (!currentSessionId) return

      addMessage(currentSessionId, {
        role: 'user',
        content,
        timestamp: Date.now(),
      })

      const session = sessions[currentSessionId]
      if (session && session.messages.length === 0 && session.name === 'New chat') {
        updateSessionName(currentSessionId, generateTitle(content))
      }

      try {
        if (!wsRef.current?.connected) {
          await connect(currentSessionId)
        }
        wsRef.current?.send(content)
      } catch (err) {
        setStreaming(false)
        addMessage(currentSessionId, {
          role: 'assistant',
          content: `WebSocket connection failed: ${err instanceof Error ? err.message : 'unknown error'}`,
          timestamp: Date.now(),
        })
      }
    },
    [
      currentSessionId,
      sessions,
      addMessage,
      setStreaming,
      updateSessionName,
      connect,
    ],
  )

  const disconnect = useCallback(() => {
    wsRef.current?.disconnect()
    wsRef.current = null
    setIsConnected(false)
    setWsConnected(false)
  }, [setWsConnected])

  return {
    isConnected,
    isStreaming,
    connect,
    disconnect,
    sendMessage,
  }
}

function formatValidationFailure(content: unknown): string {
  const failure = isRecord(content) ? content : {}
  const summary = typeof failure.summary === 'string' ? failure.summary : 'SQL validation failed.'
  const reasons = Array.isArray(failure.reasons) ? failure.reasons : []
  const reasonLines = reasons
    .filter(isRecord)
    .map((reason, index) => {
      const code = typeof reason.code === 'string' ? reason.code : `reason_${index + 1}`
      const message = typeof reason.message === 'string' ? reason.message : 'Validation check failed.'
      return `${index + 1}. ${code}: ${message}`
    })
  const sql = typeof failure.sql === 'string' && failure.sql ? `\n\nSQL:\n\`\`\`sql\n${failure.sql}\n\`\`\`` : ''
  return [`SQL Validator rejected the query.`, summary, ...reasonLines, sql].filter(Boolean).join('\n')
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
