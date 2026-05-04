'use client'

import { useCallback, useMemo, useState } from 'react'
import { useAppStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'

function SessionList({ collapsed }: { collapsed: boolean }) {
  const sessions = useAppStore((s) => s.sessions)
  const currentSessionId = useAppStore((s) => s.currentSessionId)
  const setCurrentSession = useAppStore((s) => s.setCurrentSession)
  const deleteSession = useAppStore((s) => s.deleteSession)
  const updateSessionName = useAppStore((s) => s.updateSessionName)
  const [searchQuery, setSearchQuery] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

  const sessionList = useMemo(() => {
    const list = Object.values(sessions).sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    )
    if (!searchQuery.trim()) return list
    return list.filter((s) => s.name.toLowerCase().includes(searchQuery.toLowerCase()))
  }, [sessions, searchQuery])

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2 py-2">
        {sessionList.slice(0, 5).map((session) => (
          <button
            key={session.id}
            onClick={() => setCurrentSession(session.id)}
            className={cn(
              'flex h-10 w-10 items-center justify-center rounded-xl border text-sm transition-all',
              session.id === currentSessionId
                ? 'border-purple-500/50 bg-purple-500/30'
                : 'border-white/20 bg-white/30 hover:bg-white/50 dark:bg-white/5 dark:hover:bg-white/10',
            )}
            title={session.name}
          >
            {session.name.slice(0, 1).toUpperCase()}
          </button>
        ))}
      </div>
    )
  }

  if (sessionList.length === 0) {
    return (
      <div className="px-4 py-8 text-center text-sm text-muted-foreground">
        No sessions
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="p-2">
        <Input
          placeholder="Search sessions"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-8 bg-white/30 text-sm dark:bg-white/5"
        />
      </div>

      <ScrollArea className="flex-1">
        {sessionList.map((session) => (
          <div
            key={session.id}
            className={cn(
              'group flex cursor-pointer items-center gap-2 px-3 py-2 text-sm transition-all',
              session.id === currentSessionId
                ? 'bg-purple-500/20 text-purple-700 dark:text-purple-300'
                : 'hover:bg-white/30 dark:hover:bg-white/5',
            )}
            onClick={() => {
              if (editingId !== session.id) setCurrentSession(session.id)
            }}
            onDoubleClick={() => {
              setEditingId(session.id)
              setEditName(session.name)
            }}
          >
            {editingId === session.id ? (
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && editName.trim()) {
                    updateSessionName(session.id, editName.trim())
                    setEditingId(null)
                  } else if (e.key === 'Escape') {
                    setEditingId(null)
                  }
                }}
                onBlur={() => {
                  if (editName.trim() && editName !== session.name) {
                    updateSessionName(session.id, editName.trim())
                  }
                  setEditingId(null)
                }}
                className="flex-1 rounded bg-white/50 px-1 outline-none dark:bg-white/10"
                autoFocus
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <>
                <span className="flex-1 truncate">{session.name}</span>
                <div className="flex gap-2 opacity-0 group-hover:opacity-100">
                  <button
                    className="text-muted-foreground hover:text-foreground"
                    onClick={(e) => {
                      e.stopPropagation()
                      setEditingId(session.id)
                      setEditName(session.name)
                    }}
                    title="Rename"
                  >
                    Edit
                  </button>
                  <button
                    className="text-muted-foreground hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteSession(session.id)
                    }}
                    title="Delete"
                  >
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </ScrollArea>
    </div>
  )
}

export function CollapsibleSidebar() {
  const [collapsed, setCollapsed] = useState(true)
  const createSession = useAppStore((s) => s.createSession)

  const handleNewSession = useCallback(() => {
    createSession(Date.now().toString(36), 'New chat')
  }, [createSession])

  return (
    <div
      className={cn(
        'flex h-full flex-col border-r transition-all duration-300 ease-in-out',
        'border-white/10 bg-gradient-to-b from-purple-500/5 to-indigo-500/5 backdrop-blur-xl dark:border-white/5',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      <div className={cn('flex items-center p-3', collapsed ? 'justify-center' : 'justify-between')}>
        {!collapsed && <h2 className="text-sm font-semibold">Sessions</h2>}
        <div className={cn('flex', collapsed ? 'flex-col gap-1' : 'gap-1')}>
          <button
            onClick={handleNewSession}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-500/20 text-purple-600 transition-all hover:bg-purple-500/30 dark:text-purple-400"
            title="New chat"
          >
            +
          </button>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/30 transition-all hover:bg-white/50 dark:bg-white/5 dark:hover:bg-white/10"
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? '>' : '<'}
          </button>
        </div>
      </div>

      <div className={cn('h-px bg-white/10 dark:bg-white/5', collapsed && 'mx-2')} />
      <SessionList collapsed={collapsed} />
    </div>
  )
}
