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
