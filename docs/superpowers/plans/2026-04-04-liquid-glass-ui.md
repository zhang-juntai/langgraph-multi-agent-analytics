# Liquid Glass UI 重构实施计划

> **状态: ✅ 已完成 (v1: 2026-04-04, v2: 2026-04-05)**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将多Agent数据分析平台的UI从传统三栏布局升级为2026年液态玻璃风格，包含可折叠边栏、浮动抽屉和Agent状态卡片组。

**Architecture:**
- 使用 Tailwind CSS + CSS变量实现玻璃效果 (backdrop-blur, rgba背景)
- 左侧边栏改为可折叠设计，默认60px折叠态
- 右侧面板改为浮动抽屉，可拖拽位置
- Agent状态在聊天区顶部横向显示为发光卡片组

**Tech Stack:** Next.js 15, Tailwind CSS 4, shadcn/ui, React 19

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/app/globals.css` | 修改 | 添加玻璃效果CSS变量、动画 |
| `frontend/src/components/ui/glass.tsx` | 创建 | 玻璃效果复用组件 |
| `frontend/src/components/agents/AgentStatusCards.tsx` | 创建 | Agent状态卡片组组件 |
| `frontend/src/components/sidebar/CollapsibleSidebar.tsx` | 创建 | 可折叠边栏组件 |
| `frontend/src/components/panel/FloatingDrawer.tsx` | 创建 | 浮动抽屉组件 |
| `frontend/src/app/page.tsx` | 修改 | 更新主布局，整合新组件 |
| `frontend/src/components/chat/ChatInterface.tsx` | 修改 | 集成Agent状态卡片 |
| `frontend/src/lib/store.ts` | 修改 | 添加边栏/抽屉状态 |

---

### Task 1: 添加玻璃效果CSS变量和动画

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: 添加玻璃效果CSS变量到 :root 和 .dark**

在 `globals.css` 的 `:root` 块末尾添加：

```css
  /* Liquid Glass Effect */
  --glass-bg: rgba(255, 255, 255, 0.6);
  --glass-bg-hover: rgba(255, 255, 255, 0.8);
  --glass-border: rgba(255, 255, 255, 0.3);
  --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);

  /* Gradient backgrounds */
  --gradient-primary: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15));
  --gradient-accent: linear-gradient(135deg, #8b5cf6, #6366f1);

  /* Agent colors */
  --agent-coordinator: #8b5cf6;
  --agent-data-parser: #3b82f6;
  --agent-data-profiler: #06b6d4;
  --agent-code-generator: #f59e0b;
  --agent-debugger: #f97316;
  --agent-visualizer: #ec4899;
  --agent-report-writer: #6366f1;
```

在 `.dark` 块末尾添加：

```css
  /* Liquid Glass Effect - Dark */
  --glass-bg: rgba(255, 255, 255, 0.08);
  --glass-bg-hover: rgba(255, 255, 255, 0.12);
  --glass-border: rgba(255, 255, 255, 0.1);
  --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);

  /* Gradient backgrounds - Dark */
  --gradient-primary: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(168, 85, 247, 0.2));
```

- [ ] **Step 2: 添加玻璃效果工具类和动画**

在 `@layer base` 块之后添加：

```css
@layer components {
  .glass {
    background: var(--glass-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--glass-border);
    box-shadow: var(--glass-shadow);
  }

  .glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--glass-shadow);
  }

  .glass-hover {
    transition: all 200ms ease;
  }

  .glass-hover:hover {
    background: var(--glass-bg-hover);
    border-color: rgba(139, 92, 246, 0.3);
  }
}

@keyframes pulse-glow {
  0%, 100% {
    opacity: 1;
    box-shadow: 0 0 8px currentColor;
  }
  50% {
    opacity: 0.7;
    box-shadow: 0 0 16px currentColor;
  }
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-pulse-glow {
  animation: pulse-glow 2s ease-in-out infinite;
}

.animate-fade-in {
  animation: fade-in 200ms ease-out;
}
```

- [ ] **Step 3: 验证CSS编译**

Run: `cd frontend && npm run build 2>&1 | head -20`
Expected: Build succeeds without CSS errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "style: add liquid glass CSS variables and animations

- Add glass effect CSS variables for light/dark mode
- Add glass utility classes (.glass, .glass-card, .glass-hover)
- Add pulse-glow animation for agent status indicators
- Add fade-in animation for smooth transitions"
```

---

### Task 2: 创建玻璃效果复用组件

**Files:**
- Create: `frontend/src/components/ui/glass.tsx`

- [ ] **Step 1: 创建GlassPanel组件**

创建文件 `frontend/src/components/ui/glass.tsx`：

```tsx
import { cn } from '@/lib/utils'
import { ReactNode, forwardRef, HTMLAttributes } from 'react'

interface GlassPanelProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  variant?: 'default' | 'card' | 'floating'
  hover?: boolean
}

export const GlassPanel = forwardRef<HTMLDivElement, GlassPanelProps>(
  ({ children, className, variant = 'default', hover = false, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'backdrop-blur-xl border shadow-lg',
          variant === 'default' && 'bg-white/60 dark:bg-white/8 border-white/30 dark:border-white/10',
          variant === 'card' && 'bg-white/50 dark:bg-white/6 border-white/40 dark:border-white/8 rounded-xl',
          variant === 'floating' && 'bg-white/70 dark:bg-white/10 border-white/30 dark:border-white/10 rounded-2xl shadow-2xl',
          hover && 'transition-all duration-200 hover:bg-white/80 dark:hover:bg-white/12 hover:border-purple-500/30',
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

GlassPanel.displayName = 'GlassPanel'

interface GlassButtonProps extends HTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  active?: boolean
}

export const GlassButton = forwardRef<HTMLButtonElement, GlassButtonProps>(
  ({ children, className, active = false, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'px-3 py-1.5 rounded-lg backdrop-blur-md border transition-all duration-200',
          'bg-white/40 dark:bg-white/8 border-white/30 dark:border-white/10',
          'hover:bg-white/60 dark:hover:bg-white/12 hover:border-purple-500/30',
          active && 'bg-purple-500/30 border-purple-500/50 text-purple-700 dark:text-purple-300',
          className
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)

GlassButton.displayName = 'GlassButton'
```

- [ ] **Step 2: 验证组件导入**

Run: `cd frontend && npx tsc --noEmit src/components/ui/glass.tsx 2>&1`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/glass.tsx
git commit -m "feat(ui): add GlassPanel and GlassButton components

- GlassPanel with default, card, floating variants
- GlassButton with active state styling
- Full dark mode support"
```

---

### Task 3: 创建Agent状态卡片组组件

**Files:**
- Create: `frontend/src/components/agents/AgentStatusCards.tsx`

- [ ] **Step 1: 创建AgentStatusCards组件**

创建文件 `frontend/src/components/agents/AgentStatusCards.tsx`：

```tsx
'use client'

import { cn } from '@/lib/utils'
import { useAppStore } from '@/lib/store'

const AGENT_CONFIG = {
  coordinator: { icon: '🎯', name: 'Coordinator', color: 'bg-purple-500' },
  data_parser: { icon: '📄', name: 'Parser', color: 'bg-blue-500' },
  data_profiler: { icon: '🔍', name: 'Profiler', color: 'bg-cyan-500' },
  code_generator: { icon: '💻', name: 'Code Gen', color: 'bg-amber-500' },
  debugger: { icon: '🔧', name: 'Debugger', color: 'bg-orange-500' },
  visualizer: { icon: '📊', name: 'Visualizer', color: 'bg-pink-500' },
  report_writer: { icon: '📝', name: 'Reporter', color: 'bg-indigo-500' },
}

type AgentName = keyof typeof AGENT_CONFIG

interface AgentStatusCardsProps {
  activeAgents?: AgentName[]
  className?: string
}

export function AgentStatusCards({ activeAgents = [], className }: AgentStatusCardsProps) {
  const isStreaming = useAppStore((s) => s.isStreaming)

  // 如果没有活跃agent但正在streaming，默认显示coordinator
  const displayAgents: AgentName[] = isStreaming && activeAgents.length === 0
    ? ['coordinator']
    : activeAgents.length > 0
      ? activeAgents
      : Object.keys(AGENT_CONFIG) as AgentName[]

  if (!isStreaming && activeAgents.length === 0) {
    return null
  }

  return (
    <div className={cn('flex flex-wrap gap-2 px-4 py-2', className)}>
      {displayAgents.map((agent) => {
        const config = AGENT_CONFIG[agent]
        const isActive = activeAgents.includes(agent) || (isStreaming && agent === 'coordinator')

        return (
          <div
            key={agent}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium',
              'backdrop-blur-md border transition-all duration-300',
              isActive
                ? 'bg-purple-500/20 border-purple-500/40 text-purple-700 dark:text-purple-300'
                : 'bg-white/30 dark:bg-white/5 border-white/20 dark:border-white/10 text-gray-500 dark:text-gray-400'
            )}
          >
            <span className="text-sm">{config.icon}</span>
            <span>{config.name}</span>
            <span
              className={cn(
                'w-2 h-2 rounded-full',
                isActive ? config.color : 'bg-gray-400',
                isActive && 'animate-pulse-glow'
              )}
              style={isActive ? { color: config.color.replace('bg-', '') } : undefined}
            />
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: 验证组件类型**

Run: `cd frontend && npx tsc --noEmit src/components/agents/AgentStatusCards.tsx 2>&1`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/agents/AgentStatusCards.tsx
git commit -m "feat(agents): add AgentStatusCards component

- Horizontal pill-shaped status cards
- Active state with glow animation
- Integrates with useAppStore streaming state"
```

---

### Task 4: 创建可折叠边栏组件

**Files:**
- Create: `frontend/src/components/sidebar/CollapsibleSidebar.tsx`

- [ ] **Step 1: 创建可折叠边栏组件**

创建文件 `frontend/src/components/sidebar/CollapsibleSidebar.tsx`：

```tsx
'use client'

import { useState, useCallback, useMemo } from 'react'
import { useAppStore, type DatasetMeta } from '@/lib/store'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const AGENT_ICONS = {
  coordinator: '🎯',
  data_parser: '📄',
  data_profiler: '🔍',
  code_generator: '💻',
  debugger: '🔧',
  visualizer: '📊',
  report_writer: '📝',
}

function SessionList({ collapsed }: { collapsed: boolean }) {
  const sessions = useAppStore((s) => s.sessions)
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const setCurrentSession = useAppStore((s) => s.setCurrentSession)
  const deleteSession = useAppStore((s) => s.deleteSession)
  const [searchQuery, setSearchQuery] = useState('')

  const sessionList = useMemo(() => {
    const list = Object.values(sessions).sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    )
    if (!searchQuery.trim()) return list
    return list.filter(s => s.name.toLowerCase().includes(searchQuery.toLowerCase()))
  }, [sessions, searchQuery])

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2 py-2">
        {sessionList.slice(0, 5).map((session) => (
          <button
            key={session.id}
            onClick={() => setCurrentSession(session.id)}
            className={cn(
              'w-10 h-10 rounded-xl flex items-center justify-center text-lg',
              'backdrop-blur-md border transition-all duration-200',
              session.id === currentSessionId
                ? 'bg-purple-500/30 border-purple-500/50'
                : 'bg-white/30 dark:bg-white/5 border-white/20 hover:bg-white/50 dark:hover:bg-white/10'
            )}
          >
            💬
          </button>
        ))}
      </div>
    )
  }

  if (Object.keys(sessions).length === 0) {
    return (
      <div className="px-4 py-8 text-center text-sm text-muted-foreground">
        暂无会话
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="p-2">
        <div className="relative">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
          </svg>
          <Input
            placeholder="搜索会话..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 h-8 text-sm bg-white/30 dark:bg-white/5 border-white/20"
          />
        </div>
      </div>

      <ScrollArea className="flex-1">
        {sessionList.map((session) => (
          <div
            key={session.id}
            className={cn(
              'group flex items-center gap-2 px-3 py-2 text-sm cursor-pointer',
              'transition-all duration-200',
              session.id === currentSessionId
                ? 'bg-purple-500/20 text-purple-700 dark:text-purple-300'
                : 'hover:bg-white/30 dark:hover:bg-white/5'
            )}
            onClick={() => setCurrentSession(session.id)}
          >
            <span className="truncate flex-1">{session.name}</span>
            <button
              className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
              onClick={(e) => { e.stopPropagation(); deleteSession(session.id) }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
              </svg>
            </button>
          </div>
        ))}
      </ScrollArea>
    </div>
  )
}

function FileUploader({ collapsed }: { collapsed: boolean }) {
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const addDataset = useAppStore((s) => s.addDataset)
  const [uploading, setUploading] = useState(false)

  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !currentSessionId) return
    setUploading(true)
    try {
      const res = await api.uploadFile(currentSessionId, file)
      if (res.ok && res.data) {
        addDataset(currentSessionId, res.data as DatasetMeta)
      }
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }, [currentSessionId, addDataset])

  if (collapsed) {
    return (
      <div className="p-2">
        <input type="file" accept=".csv,.tsv,.xlsx,.xls,.json" className="hidden" id="file-upload-collapsed" onChange={handleUpload} />
        <button
          disabled={!currentSessionId || uploading}
          onClick={() => document.getElementById('file-upload-collapsed')?.click()}
          className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/30 dark:bg-white/5 border border-white/20 hover:bg-white/50 dark:hover:bg-white/10 transition-all"
        >
          📁
        </button>
      </div>
    )
  }

  return (
    <div className="p-3">
      <input type="file" accept=".csv,.tsv,.xlsx,.xls,.json" className="hidden" id="file-upload" onChange={handleUpload} />
      <Button
        variant="outline"
        size="sm"
        className="w-full bg-white/30 dark:bg-white/5 border-white/20"
        disabled={!currentSessionId || uploading}
        onClick={() => document.getElementById('file-upload')?.click()}
      >
        {uploading ? '上传中...' : '上传数据文件'}
      </Button>
    </div>
  )
}

export function CollapsibleSidebar() {
  const [collapsed, setCollapsed] = useState(true)
  const createSession = useAppStore((s) => s.createSession)

  const handleNewSession = useCallback(async () => {
    const id = Date.now().toString(36)
    try {
      const res = await api.createSession('新对话')
      if (res.ok && res.data?.id) {
        createSession(res.data.id, res.data.name)
        return
      }
    } catch {}
    createSession(id, '新对话')
  }, [createSession])

  return (
    <div
      className={cn(
        'flex h-full flex-col border-r transition-all duration-300 ease-in-out',
        'bg-gradient-to-b from-purple-500/5 to-indigo-500/5',
        'backdrop-blur-xl border-white/10 dark:border-white/5',
        collapsed ? 'w-16' : 'w-64'
      )}
      onMouseEnter={() => setCollapsed(false)}
      onMouseLeave={() => setCollapsed(true)}
    >
      {/* Header */}
      <div className={cn('flex items-center p-3', collapsed ? 'justify-center' : 'justify-between')}>
        {!collapsed && <h2 className="text-sm font-semibold">会话</h2>}
        <button
          onClick={handleNewSession}
          className="w-9 h-9 rounded-xl flex items-center justify-center bg-purple-500/20 hover:bg-purple-500/30 text-purple-600 dark:text-purple-400 transition-all"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14"/><path d="M5 12h14"/>
          </svg>
        </button>
      </div>

      <div className={cn('h-px bg-white/10 dark:bg-white/5', collapsed && 'mx-2')} />

      {/* Session list */}
      <SessionList collapsed={collapsed} />

      <div className={cn('h-px bg-white/10 dark:bg-white/5', collapsed && 'mx-2')} />

      {/* File upload */}
      <FileUploader collapsed={collapsed} />
    </div>
  )
}
```

- [ ] **Step 2: 验证组件类型**

Run: `cd frontend && npx tsc --noEmit src/components/sidebar/CollapsibleSidebar.tsx 2>&1`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/sidebar/CollapsibleSidebar.tsx
git commit -m "feat(sidebar): add CollapsibleSidebar with hover expand

- 60px collapsed state, 256px expanded
- Hover to expand, auto-collapse on leave
- Glass morphism styling with purple gradient"
```

---

### Task 5: 创建浮动抽屉组件

**Files:**
- Create: `frontend/src/components/panel/FloatingDrawer.tsx`

- [ ] **Step 1: 创建浮动抽屉组件**

创建文件 `frontend/src/components/panel/FloatingDrawer.tsx`：

```tsx
'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useAppStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import ReactMarkdown from 'react-markdown'

interface Position {
  x: number
  y: number
}

function CodePreview() {
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const sessions = useAppStore((s) => s.sessions)
  const code = currentSessionId ? sessions[currentSessionId]?.currentCode : ''

  const handleDownload = () => {
    if (!code) return
    const blob = new Blob([code], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '数据分析.py'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!code) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground p-4">
        执行分析后，代码将在此显示
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">数据分析.py</span>
          <span className="text-xs text-muted-foreground">{code.length} 字符</span>
        </div>
        <Button variant="ghost" size="sm" onClick={handleDownload}>下载</Button>
      </div>
      <ScrollArea className="flex-1">
        <SyntaxHighlighter
          language="python"
          style={oneDark}
          customStyle={{ margin: 0, fontSize: '0.75rem', background: 'transparent' }}
          showLineNumbers
        >
          {code}
        </SyntaxHighlighter>
      </ScrollArea>
    </div>
  )
}

function ChartGallery() {
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const sessions = useAppStore((s) => s.sessions)
  const figures = currentSessionId ? sessions[currentSessionId]?.figures : []
  const [selected, setSelected] = useState<string | null>(null)

  if (!figures || figures.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground p-4">
        图表将在此显示
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <ScrollArea className="flex-1 p-2">
        <div className="grid grid-cols-2 gap-2">
          {figures.map((fig: string, i: number) => (
            <button
              key={i}
              onClick={() => setSelected(selected === fig ? null : fig)}
              className={cn(
                'aspect-square rounded-lg overflow-hidden border-2 transition-all',
                selected === fig ? 'border-purple-500' : 'border-transparent hover:border-white/30'
              )}
            >
              <img
                src={`http://localhost:8000${fig}`}
                alt={`Chart ${i + 1}`}
                className="w-full h-full object-cover"
              />
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

function ReportView() {
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const sessions = useAppStore((s) => s.sessions)
  const report = currentSessionId ? sessions[currentSessionId]?.report : ''

  if (!report) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground p-4">
        分析完成后，报告将在此显示
      </div>
    )
  }

  return (
    <ScrollArea className="flex-1 p-4">
      <ReactMarkdown className="prose prose-sm dark:prose-invert max-w-none">
        {report}
      </ReactMarkdown>
    </ScrollArea>
  )
}

export function FloatingDrawer() {
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const [expanded, setExpanded] = useState(true)
  const [position, setPosition] = useState<Position>({ x: 20, y: 60 })
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef<{ startX: number; startY: number; startPos: Position } | null>(null)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) return
    setIsDragging(true)
    dragRef.current = { startX: e.clientX, startY: e.clientY, startPos: position }
  }, [position])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragRef.current) return
      const dx = e.clientX - dragRef.current.startX
      const dy = e.clientY - dragRef.current.startY
      setPosition({
        x: Math.max(0, dragRef.current.startPos.x + dx),
        y: Math.max(0, dragRef.current.startPos.y + dy),
      })
    }

    const handleMouseUp = () => setIsDragging(false)

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  if (!currentSessionId) return null

  return (
    <div
      className={cn(
        'fixed z-50 transition-all duration-300',
        'backdrop-blur-2xl bg-white/70 dark:bg-white/10',
        'border border-white/30 dark:border-white/10 rounded-2xl shadow-2xl',
        isDragging && 'cursor-grabbing'
      )}
      style={{
        right: position.x,
        top: position.y,
        width: expanded ? 360 : 200,
        height: expanded ? 480 : 48,
      }}
    >
      {/* Drag header */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b border-white/10 cursor-grab"
        onMouseDown={handleMouseDown}
      >
        <div className="flex gap-1">
          <div className="w-3 h-3 rounded-full bg-red-400/60" />
          <div className="w-3 h-3 rounded-full bg-yellow-400/60" />
          <div className="w-3 h-3 rounded-full bg-green-400/60" />
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {expanded ? '收起' : '展开'}
        </button>
      </div>

      {expanded && (
        <Tabs defaultValue="code" className="flex flex-col h-[calc(100%-40px)]">
          <TabsList className="mx-2 mt-2 grid w-auto grid-cols-3 bg-white/30 dark:bg-white/5">
            <TabsTrigger value="code" className="text-xs">代码</TabsTrigger>
            <TabsTrigger value="charts" className="text-xs">图表</TabsTrigger>
            <TabsTrigger value="report" className="text-xs">报告</TabsTrigger>
          </TabsList>
          <TabsContent value="code" className="flex-1 overflow-hidden m-0">
            <CodePreview />
          </TabsContent>
          <TabsContent value="charts" className="flex-1 overflow-hidden m-0">
            <ChartGallery />
          </TabsContent>
          <TabsContent value="report" className="flex-1 overflow-hidden m-0">
            <ReportView />
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 验证组件类型**

Run: `cd frontend && npx tsc --noEmit src/components/panel/FloatingDrawer.tsx 2>&1`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/panel/FloatingDrawer.tsx
git commit -m "feat(panel): add FloatingDrawer with drag support

- Draggable floating panel
- Expandable/collapsible
- Code, charts, report tabs
- Glass morphism styling"
```

---

### Task 6: 更新主布局页面

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: 替换主布局为新组件**

将 `frontend/src/app/page.tsx` 完整替换为：

```tsx
'use client'

import { CollapsibleSidebar } from '@/components/sidebar/CollapsibleSidebar'
import { ChatInterface } from '@/components/chat/ChatInterface'
import { FloatingDrawer } from '@/components/panel/FloatingDrawer'

export default function Home() {
  return (
    <div className="flex h-full overflow-hidden bg-gradient-to-br from-slate-50 via-purple-50/30 to-indigo-50 dark:from-slate-950 dark:via-purple-950/20 dark:to-indigo-950">
      {/* Left collapsible sidebar */}
      <CollapsibleSidebar />

      {/* Center: chat */}
      <main className="flex-1 min-w-0 flex flex-col overflow-hidden relative">
        <ChatInterface />
      </main>

      {/* Floating drawer panel */}
      <FloatingDrawer />
    </div>
  )
}
```

- [ ] **Step 2: 验证页面编译**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat(layout): integrate CollapsibleSidebar and FloatingDrawer

- Replace fixed three-column with new layout
- Add gradient background
- Floating drawer for code/charts/report"
```

---

### Task 7: 集成Agent状态卡片到聊天界面

**Files:**
- Modify: `frontend/src/components/chat/ChatInterface.tsx`

- [ ] **Step 1: 在ChatInterface中添加AgentStatusCards**

在 `ChatInterface.tsx` 文件中：
1. 添加导入:
```tsx
import { AgentStatusCards } from '@/components/agents/AgentStatusCards'
```

2. 在 `<ExecutionPanel />` 之前添加:
```tsx
<AgentStatusCards className="border-b border-white/10 dark:border-white/5 bg-gradient-to-r from-purple-500/5 to-transparent" />
```

3. 移除 `<ExecutionPanel />` 或将其注释掉（已被AgentStatusCards替代）

- [ ] **Step 2: 验证编译**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/ChatInterface.tsx
git commit -m "feat(chat): integrate AgentStatusCards into ChatInterface

- Replace ExecutionPanel with AgentStatusCards
- Add gradient background for agent status area"
```

---

### Task 8: 最终验证和清理

**Files:**
- Verify all changes

- [ ] **Step 1: 运行完整构建**

Run: `cd frontend && npm run build`
Expected: Build succeeds without errors

- [ ] **Step 2: 启动开发服务器验证UI**

Run: `cd frontend && npm run dev &`
Then open http://localhost:3000 in browser

- [ ] **Step 3: 验证功能清单**

手动检查:
- [ ] 左侧边栏默认折叠，hover展开
- [ ] 右侧浮动抽屉可拖拽
- [ ] Agent状态卡片在聊天区顶部显示
- [ ] 玻璃效果正确应用
- [ ] 暗色模式正常切换

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(ui): complete Liquid Glass UI redesign

- Collapsible sidebar with hover expand
- Floating draggable drawer panel
- Agent status cards with glow animation
- Glass morphism effects throughout
- Purple-blue gradient color scheme

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 验收标准

1. **视觉**: 玻璃效果清晰可见，渐变背景美观
2. **交互**: 边栏点击展开流畅，抽屉可拖拽
3. **Agent可视化**: 状态卡片正确显示活跃Agent
4. **响应式**: 在不同屏幕尺寸下布局正常
5. **暗色模式**: 所有组件在暗色模式下表现正常

---

## v2 交互改进 (2026-04-05)

基于用户反馈的改进：

### 已完成改进

1. **侧边栏交互** ✅
   - 从悬停展开改为点击展开/收缩
   - 添加展开/收缩按钮 (箭头图标)
   - 折叠状态下也能新建对话

2. **对话标题管理** ✅
   - 自动生成标题: 从第一条消息提取前20字符
   - 支持重命名: 双击会话项或点击编辑图标
   - API: `PATCH /api/sessions/{id}/name`

3. **浮动面板重构** ✅
   - 代码预览支持滚动 (`overflow-auto`)
   - 支持多个代码块 (保留历史分析代码)
   - Tab 切换不同代码块
   - "下载全部" 按钮
   - 图表画廊: 点击下载，悬停预览
   - 报告: 支持多份报告历史

4. **Store 数据结构** ✅
   ```typescript
   interface Session {
     codeArtifacts: CodeArtifact[]  // 多个代码产物
     figures: FigureArtifact[]      // 多个图表
     reports: string[]              // 多个报告
   }
   ```

### 文件变更

| 文件 | 变更 |
|------|------|
| `CollapsibleSidebar.tsx` | 点击展开 + 重命名 |
| `FloatingDrawer.tsx` | 多产物列表 + 滚动 |
| `store.ts` | CodeArtifact/FigureArtifact 类型 |
| `api.ts` | updateSessionName API |
| `useChat.ts` | 自动生成标题 |

### 提交记录

```
d62f8c8 feat(ui): 完善 UI 交互体验
a2b874a refactor(ui): integrate Liquid Glass components into main layout
ab86a09 feat(ui): complete Liquid Glass UI redesign
```
