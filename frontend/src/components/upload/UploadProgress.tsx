'use client'

import { cn } from '@/lib/utils'

export interface UploadProgressProps {
  fileName: string
  progress: number // 0-100
  status: 'uploading' | 'success' | 'error'
  errorMessage?: string
  onRetry?: () => void
}

export function UploadProgress({
  fileName,
  progress,
  status,
  errorMessage,
  onRetry,
}: UploadProgressProps) {
  return (
    <div className="flex flex-col gap-2 p-3 rounded-lg bg-white/30 dark:bg-white/5 border border-white/20">
      {/* File name */}
      <div className="flex items-center gap-2 text-sm">
        <span className="truncate flex-1">{fileName}</span>
        {status === 'success' && (
          <span className="text-green-500 animate-pulse">✓</span>
        )}
        {status === 'error' && (
          <span className="text-red-500">✗</span>
        )}
      </div>

      {/* Progress bar */}
      {status === 'uploading' && (
        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-purple-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* Error message and retry */}
      {status === 'error' && errorMessage && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-red-500 flex-1 truncate">{errorMessage}</span>
          {onRetry && (
            <button
              onClick={onRetry}
              className="text-xs text-purple-500 hover:text-purple-600"
            >
              重试
            </button>
          )}
        </div>
      )}
    </div>
  )
}
