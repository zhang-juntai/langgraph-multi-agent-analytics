'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useAppStore, type CodeArtifact, type FigureArtifact } from '@/lib/store'
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
  const session = currentSessionId ? sessions[currentSessionId] : null
  const codeArtifacts = session?.codeArtifacts || []
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selectedCode = codeArtifacts.find(c => c.id === selectedId) || codeArtifacts[codeArtifacts.length - 1]

  const handleDownload = (artifact: CodeArtifact) => {
    const blob = new Blob([artifact.code], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${artifact.name}.py`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadAll = () => {
    const allCode = codeArtifacts.map(a => `# ${a.name}\n\n${a.code}`).join('\n\n---\n\n')
    const blob = new Blob([allCode], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '所有分析代码.py'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (codeArtifacts.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground p-4">
        执行分析后，代码将在此显示
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* 代码列表 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <div className="flex gap-1 overflow-x-auto">
          {codeArtifacts.map((artifact) => (
            <button
              key={artifact.id}
              onClick={() => setSelectedId(artifact.id)}
              className={cn(
                'px-2 py-1 text-xs rounded-md whitespace-nowrap transition-all',
                (selectedId === artifact.id || (!selectedId && artifact === selectedCode))
                  ? 'bg-purple-500/30 text-purple-700 dark:text-purple-300'
                  : 'bg-white/20 hover:bg-white/30'
              )}
            >
              {artifact.name}
            </button>
          ))}
        </div>
        <Button variant="ghost" size="sm" onClick={handleDownloadAll}>下载全部</Button>
      </div>

      {/* 代码预览 - 修复滚动问题 */}
      <div className="flex-1 overflow-auto">
        {selectedCode && (
          <div className="relative">
            <div className="absolute right-2 top-2 z-10">
              <Button variant="ghost" size="sm" onClick={() => handleDownload(selectedCode)}>
                下载
              </Button>
            </div>
            <SyntaxHighlighter
              language="python"
              style={oneDark}
              customStyle={{
                margin: 0,
                fontSize: '0.75rem',
                background: 'transparent',
                minHeight: '100%',
              }}
              showLineNumbers
              wrapLines={true}
              wrapLongLines={true}
            >
              {selectedCode.code}
            </SyntaxHighlighter>
          </div>
        )}
      </div>
    </div>
  )
}

function ChartGallery() {
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const sessions = useAppStore((s) => s.sessions)
  const session = currentSessionId ? sessions[currentSessionId] : null
  const figures = session?.figures || []
  const [selected, setSelected] = useState<string | null>(null)

  const handleDownload = (fig: FigureArtifact) => {
    const a = document.createElement('a')
    a.href = `http://localhost:8000${fig.path}`
    a.download = fig.name
    a.click()
  }

  if (figures.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground p-4">
        图表将在此显示
      </div>
    )
  }

  const selectedFig = figures.find(f => f.id === selected) || figures[0]

  return (
    <div className="flex h-full flex-col">
      {/* 图表列表 */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-white/10 overflow-x-auto">
        {figures.map((fig) => (
          <button
            key={fig.id}
            onClick={() => setSelected(fig.id)}
            className={cn(
              'px-2 py-1 text-xs rounded-md whitespace-nowrap transition-all',
              (selected === fig.id || (!selected && fig === figures[0]))
                ? 'bg-purple-500/30 text-purple-700 dark:text-purple-300'
                : 'bg-white/20 hover:bg-white/30'
            )}
          >
            {fig.name}
          </button>
        ))}
      </div>

      {/* 图片预览 */}
      <div className="flex-1 overflow-auto p-2">
        <div className="grid grid-cols-2 gap-2">
          {figures.map((fig) => (
            <button
              key={fig.id}
              onClick={() => handleDownload(fig)}
              className={cn(
                'aspect-square rounded-lg overflow-hidden border-2 transition-all relative group',
                selected === fig.id ? 'border-purple-500' : 'border-transparent hover:border-white/30'
              )}
            >
              <img
                src={`http://localhost:8000${fig.path}`}
                alt={fig.name}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <span className="text-white text-xs">点击下载</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function ReportView() {
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const sessions = useAppStore((s) => s.sessions)
  const session = currentSessionId ? sessions[currentSessionId] : null
  const reports = session?.reports || []
  const [selectedIdx, setSelectedIdx] = useState(0)

  const latestReport = reports[reports.length - 1] || session?.report

  if (!latestReport) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground p-4">
        分析完成后，报告将在此显示
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {reports.length > 1 && (
        <div className="flex items-center gap-1 px-3 py-2 border-b border-white/10 overflow-x-auto">
          {reports.map((_, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedIdx(idx)}
              className={cn(
                'px-2 py-1 text-xs rounded-md whitespace-nowrap transition-all',
                selectedIdx === idx
                  ? 'bg-purple-500/30 text-purple-700 dark:text-purple-300'
                  : 'bg-white/20 hover:bg-white/30'
              )}
            >
              报告 #{idx + 1}
            </button>
          ))}
        </div>
      )}
      <ScrollArea className="flex-1 p-4">
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown>
            {reports[selectedIdx] || latestReport}
          </ReactMarkdown>
        </div>
      </ScrollArea>
    </div>
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
        width: expanded ? 400 : 200,
        height: expanded ? 520 : 48,
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
          <TabsContent value="code" className="flex-1 overflow-hidden m-0 data-[state=active]:flex flex-col">
            <CodePreview />
          </TabsContent>
          <TabsContent value="charts" className="flex-1 overflow-hidden m-0 data-[state=active]:flex flex-col">
            <ChartGallery />
          </TabsContent>
          <TabsContent value="report" className="flex-1 overflow-hidden m-0 data-[state=active]:flex flex-col">
            <ReportView />
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
