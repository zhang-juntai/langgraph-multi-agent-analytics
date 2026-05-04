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
