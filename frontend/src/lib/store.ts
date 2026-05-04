import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ---- Types ----

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
}

export interface DatasetMeta {
  file_name: string
  file_path: string
  num_rows: number
  num_cols: number
  columns: string[]
  dtypes: Record<string, string>
  preview: string[][]
}

export interface CodeArtifact {
  id: string
  name: string
  code: string
  timestamp: number
}

export interface FigureArtifact {
  id: string
  path: string
  name: string
  timestamp: number
}

export interface Session {
  id: string
  name: string
  messages: Message[]
  datasets: DatasetMeta[]
  codeArtifacts: CodeArtifact[]
  reports: string[]
  figures: FigureArtifact[]
  createdAt: string
  updatedAt: string
  // 保留旧字段用于兼容
  currentCode?: string
  report?: string
}

export interface AppStore {
  // State
  sessions: Record<string, Session>
  currentSessionId: string | null
  isStreaming: boolean
  wsConnected: boolean
  // Agent execution tracking
  currentAgent: string | null
  currentAgentDisplay: string | null
  currentSkill: string | null
  currentSkillDisplay: string | null
  executionLog: ExecutionLogEntry[]

  // Session actions
  createSession: (id: string, name: string) => void
  deleteSession: (id: string) => void
  setCurrentSession: (id: string | null) => void
  updateSessionName: (id: string, name: string) => void

  // Message actions
  addMessage: (sessionId: string, message: Message) => void
  setStreamingContent: (sessionId: string, content: string) => void

  // Dataset actions
  addDataset: (sessionId: string, dataset: DatasetMeta) => void

  // Artifact actions (新)
  addCodeArtifact: (sessionId: string, code: string, name?: string) => void
  addReport: (sessionId: string, report: string) => void
  addFigures: (sessionId: string, figures: string[]) => void

  // 旧方法 (保留兼容)
  setCode: (sessionId: string, code: string) => void
  setReport: (sessionId: string, report: string) => void
  setFigures: (sessionId: string, figures: string[]) => void

  // Connection state
  setStreaming: (streaming: boolean) => void
  setWsConnected: (connected: boolean) => void

  // Agent execution tracking
  setCurrentAgent: (agent: string | null, display: string | null) => void
  setCurrentSkill: (skill: string | null, display: string | null) => void
  addExecutionLog: (entry: ExecutionLogEntry) => void
  clearExecutionLog: () => void

  // Upload state
  uploadProgress: Record<string, UploadProgress>
  uploadedFiles: UploadedFileMeta[]
  activeFileId: string | null

  // Upload actions
  setUploadProgress: (tempId: string, progress: UploadProgress) => void
  clearUploadProgress: (tempId: string) => void
  setUploadedFiles: (files: UploadedFileMeta[]) => void
  setActiveFileId: (fileId: string | null) => void
  removeUploadedFile: (fileId: string) => void

  // Hydration from API
  loadSessionFromApi: (session: Session) => void
}

export interface ExecutionLogEntry {
  timestamp: number
  type: 'agent' | 'skill' | 'chunk' | 'error'
  agent?: string
  agentDisplay?: string
  skill?: string
  skillDisplay?: string
  content?: string
}

export interface UploadProgress {
  fileName: string
  progress: number
  status: 'uploading' | 'success' | 'error'
  errorMessage?: string
}

export interface UploadedFileMeta {
  id: string
  filename: string
  size_bytes: number
  rows: number
  columns: number
  uploaded_at: string
  is_active: boolean
}

export const useAppStore = create<AppStore>()(
  persist(
    (set, get) => ({
      sessions: {},
      currentSessionId: null,
      isStreaming: false,
      wsConnected: false,
      executionLog: [],
      currentAgent: null,
      currentAgentDisplay: null,
      currentSkill: null,
      currentSkillDisplay: null,
      uploadProgress: {},
      uploadedFiles: [],
      activeFileId: null,

      // ---- Session actions ----

      createSession: (id, name) =>
        set((state) => ({
          sessions: {
            ...state.sessions,
            [id]: {
              id,
              name,
              messages: [],
              datasets: [],
              codeArtifacts: [],
              reports: [],
              figures: [],
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
          },
          currentSessionId: id,
        })),

      deleteSession: (id) =>
        set((state) => {
          const { [id]: _, ...rest } = state.sessions
          return {
            sessions: rest,
            currentSessionId:
              state.currentSessionId === id
                ? Object.keys(rest)[0] || null
                : state.currentSessionId,
          }
        }),

      setCurrentSession: (id) => set({ currentSessionId: id }),

      updateSessionName: (id, name) =>
        set((state) => ({
          sessions: {
            ...state.sessions,
            [id]: { ...state.sessions[id], name, updatedAt: new Date().toISOString() },
          },
        })),

      // ---- Message actions ----

      addMessage: (sessionId, message) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...session,
                messages: [...session.messages, message],
                updatedAt: new Date().toISOString(),
              },
            },
          }
        }),

      setStreamingContent: (sessionId, content) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          const messages = [...session.messages]
          const lastMsg = messages[messages.length - 1]
          if (lastMsg?.role === 'assistant') {
            messages[messages.length - 1] = { ...lastMsg, content }
          }
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: { ...session, messages },
            },
          }
        }),

      // ---- Dataset actions ----

      addDataset: (sessionId, dataset) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...session,
                datasets: [...session.datasets, dataset],
                updatedAt: new Date().toISOString(),
              },
            },
          }
        }),

      // ---- Artifact actions (新) ----

      addCodeArtifact: (sessionId, code, name) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          const artifact: CodeArtifact = {
            id: Date.now().toString(36),
            name: name || `分析代码 #${session.codeArtifacts.length + 1}`,
            code,
            timestamp: Date.now(),
          }
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...session,
                codeArtifacts: [...session.codeArtifacts, artifact],
                updatedAt: new Date().toISOString(),
              },
            },
          }
        }),

      addReport: (sessionId, report) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...session,
                reports: [...session.reports, report],
                updatedAt: new Date().toISOString(),
              },
            },
          }
        }),

      addFigures: (sessionId, figures) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          const newFigures: FigureArtifact[] = figures.map((path, i) => ({
            id: `${Date.now()}-${i}`,
            path,
            name: `图表 #${session.figures.length + i + 1}`,
            timestamp: Date.now(),
          }))
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...session,
                figures: [...session.figures, ...newFigures],
                updatedAt: new Date().toISOString(),
              },
            },
          }
        }),

      // ---- 旧方法 (兼容) ----

      setCode: (sessionId, code) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          const artifact: CodeArtifact = {
            id: Date.now().toString(36),
            name: `分析代码 #${(session.codeArtifacts?.length || 0) + 1}`,
            code,
            timestamp: Date.now(),
          }
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...session,
                codeArtifacts: [...(session.codeArtifacts || []), artifact],
                currentCode: code,
              },
            },
          }
        }),

      setReport: (sessionId, report) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...session,
                reports: [...(session.reports || []), report],
                report,
              },
            },
          }
        }),

      setFigures: (sessionId, figures) =>
        set((state) => {
          const session = state.sessions[sessionId]
          if (!session) return state
          const newFigures: FigureArtifact[] = figures.map((path, i) => ({
            id: `${Date.now()}-${i}`,
            path,
            name: `图表 #${(session.figures?.length || 0) + i + 1}`,
            timestamp: Date.now(),
          }))
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...session,
                figures: [...(session.figures || []), ...newFigures],
              },
            },
          }
        }),

      // ---- Connection state ----

      setStreaming: (streaming) => set({ isStreaming: streaming }),
      setWsConnected: (connected) => set({ wsConnected: connected }),

      // ---- Agent Execution Tracking ----

      setCurrentAgent: (agent, display) =>
        set({ currentAgent: agent, currentAgentDisplay: display }),
      setCurrentSkill: (skill, display) =>
        set({ currentSkill: skill, currentSkillDisplay: display }),

      // ---- Execution Log ----

      addExecutionLog: (entry) =>
        set((state) => ({
          executionLog: [...state.executionLog, entry],
        })),
      clearExecutionLog: () => set({ executionLog: [] }),

      // ---- Upload actions ----

      setUploadProgress: (tempId, progress) =>
        set((state) => ({
          uploadProgress: {
            ...state.uploadProgress,
            [tempId]: progress,
          },
        })),

      clearUploadProgress: (tempId) =>
        set((state) => {
          const { [tempId]: _, ...rest } = state.uploadProgress
          return { uploadProgress: rest }
        }),

      setUploadedFiles: (files) => set({ uploadedFiles: files }),

      setActiveFileId: (fileId) => set({ activeFileId: fileId }),

      removeUploadedFile: (fileId) =>
        set((state) => ({
          uploadedFiles: state.uploadedFiles.filter((f) => f.id !== fileId),
          activeFileId: state.activeFileId === fileId ? null : state.activeFileId,
        })),

      // ---- Hydration ----

      loadSessionFromApi: (session) =>
        set((state) => ({
          sessions: {
            ...state.sessions,
            [session.id]: session,
          },
        })),
    }),
    {
      name: 'multi-agent-storage',
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
        activeFileId: state.activeFileId,
      }),
    },
  ),
)
