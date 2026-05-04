'use client'

import { useRef, useEffect, useState, useCallback, KeyboardEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useAppStore } from '@/lib/store'
import { useChat } from '@/hooks/useChat'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import { AgentStatusCards } from '@/components/agents/AgentStatusCards'

// ---- Code Block with Syntax Highlighting ----

function CodeBlock({
  code,
  language = 'python',
  inline = false
}: {
  code: string
  language?: string
  inline?: boolean
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (inline) {
    return (
      <code className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-sm font-mono">
        {code}
      </code>
    )
  }

  return (
    <div className="my-2 rounded-lg overflow-hidden border border-slate-700">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-800 text-slate-300">
        <span className="text-xs font-medium">{language || 'code'}</span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs text-slate-400 hover:text-white"
          onClick={handleCopy}
        >
          {copied ? '✓ 已复制' : '复制'}
        </Button>
      </div>
      {/* Code */}
      <SyntaxHighlighter
        language={language || 'text'}
        style={oneDark}
        customStyle={{
          margin: 0,
          padding: '0.75rem',
          fontSize: '0.8rem',
          maxHeight: '400px',
          overflow: 'auto',
        }}
        showLineNumbers={code.split('\n').length > 5}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

// ---- Markdown Renderer ----

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <ReactMarkdown
        components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '')
          const codeString = String(children).replace(/\n$/, '')
          const isInline = !match && !codeString.includes('\n')

          if (isInline) {
            return <code className={className} {...props}>{children}</code>
          }

          return (
            <CodeBlock
              code={codeString}
              language={match ? match[1] : 'text'}
            />
          )
        },
        pre({ children }) {
          return <>{children}</>
        },
        a({ href, children }) {
          return (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              {children}
            </a>
          )
        },
        table({ children }) {
          return (
            <div className="overflow-x-auto my-2">
              <table className="min-w-full border-collapse border border-slate-300 dark:border-slate-600">
                {children}
              </table>
            </div>
          )
        },
        th({ children }) {
          return (
            <th className="border border-slate-300 dark:border-slate-600 px-3 py-2 bg-slate-100 dark:bg-slate-800 font-semibold text-left">
              {children}
            </th>
          )
        },
        td({ children }) {
          return (
            <td className="border border-slate-300 dark:border-slate-600 px-3 py-2">
              {children}
            </td>
          )
        },
      }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

// ---- Single message bubble ----

function MessageBubble({
  role,
  content,
  streaming,
}: {
  role: string
  content: string
  streaming?: boolean
}) {
  const isUser = role === 'user'

  return (
    <div className={cn('flex gap-3 px-4 py-3', isUser ? 'justify-end' : 'justify-start')}>
      {!isUser && (
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="bg-primary text-primary-foreground text-xs">AI</AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          'max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-foreground',
        )}
      >
        {isUser ? (
          <span className="whitespace-pre-wrap">{content}</span>
        ) : (
          <MarkdownContent content={content} />
        )}
        {streaming && <span className="animate-pulse">▊</span>}
      </div>
      {isUser && (
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">U</AvatarFallback>
        </Avatar>
      )}
    </div>
  )
}

// ---- Chat input area ----

function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (msg: string) => void
  disabled?: boolean
}) {
  const [value, setValue] = useState('')

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }, [value, disabled, onSend])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  return (
    <div className="border-t bg-background p-4">
      <div className="mx-auto flex max-w-3xl gap-2">
        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的分析需求... (Shift+Enter 换行)"
          disabled={disabled}
          className="min-h-[44px] max-h-[200px] resize-none"
          rows={1}
        />
        <Button onClick={handleSend} disabled={disabled || !value.trim()} size="icon" className="shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m5 12 7-7 7 7" /><path d="M12 19V5" />
          </svg>
        </Button>
      </div>
    </div>
  )
}

// ---- Main chat interface ----

export function ChatInterface() {
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const sessions = useAppStore((s) => s.sessions)
  const isStreaming = useAppStore((s) => s.isStreaming)
  const createSession = useAppStore((s) => s.createSession)
  const { sendMessage, connect, disconnect } = useChat()

  const bottomRef = useRef<HTMLDivElement>(null)

  const currentSession = currentSessionId ? sessions[currentSessionId] : null
  const messages = currentSession?.messages || []

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-connect when session changes
  useEffect(() => {
    if (currentSessionId) {
      connect(currentSessionId)
    }
    return () => disconnect()
  }, [currentSessionId, connect, disconnect])

  // Welcome screen
  if (!currentSession) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
        <div className="text-5xl">🤖</div>
        <h2 className="text-2xl font-semibold">多 Agent 数据分析平台</h2>
        <p className="text-muted-foreground text-center max-w-md leading-relaxed">
          上传你的数据文件，用自然语言描述分析需求，<br />
          AI Agent 团队会自动协作完成分析。
        </p>
        <div className="flex gap-3 mt-2">
          <Button onClick={() => createSession(Date.now().toString(36), '新对话')}>
            开始新对话
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b px-4 py-3 flex items-center justify-between">
        <h3 className="font-medium truncate">{currentSession.name}</h3>
        <span className="text-xs text-muted-foreground">
          {isStreaming ? (
            <span className="flex items-center gap-1">
              <span className="animate-spin">⏳</span> 分析中...
            </span>
          ) : (
            `${messages.length} 条消息`
          )}
        </span>
      </div>

      {/* Agent Status Cards */}
      <AgentStatusCards className="border-b border-white/10 dark:border-white/5 bg-gradient-to-r from-purple-500/5 to-transparent" />

      {/* Messages */}
      <ScrollArea className="flex-1 h-0">
        <div className="py-4">
          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              role={msg.role}
              content={msg.content}
              streaming={isStreaming && i === messages.length - 1 && msg.role === 'assistant'}
            />
          ))}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  )
}
