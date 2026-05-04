/**
 * Zustand Store 测试
 */
import { act } from '@testing-library/react'
import { useAppStore } from '../store'

describe('App Store', () => {
  // 使用独立的 session ID 避免冲突

  describe('Session Management', () => {
    it('should create a new session', () => {
      const { createSession, sessions } = useAppStore.getState()

      act(() => {
        createSession('test-session-1', 'Test Session')
      })

      const newState = useAppStore.getState()
      expect(newState.sessions['test-session-1']).toBeDefined()
      expect(newState.sessions['test-session-1'].name).toBe('Test Session')
    })

    it('should delete a session', () => {
      const { createSession, deleteSession, sessions } = useAppStore.getState()

      act(() => {
        createSession('test-session-2', 'To Be Deleted')
      })

      act(() => {
        deleteSession('test-session-2')
      })

      const newState = useAppStore.getState()
      expect(newState.sessions['test-session-2']).toBeUndefined()
    })

    it('should set current session', () => {
      const { createSession, setCurrentSession, currentSessionId } = useAppStore.getState()

      act(() => {
        createSession('test-session-3', 'Current Session')
        setCurrentSession('test-session-3')
      })

      const newState = useAppStore.getState()
      expect(newState.currentSessionId).toBe('test-session-3')
    })
  })

  describe('Message Management', () => {
    it('should add message to session', () => {
      const { createSession, addMessage, setCurrentSession } = useAppStore.getState()

      act(() => {
        createSession('msg-session', 'Message Test')
        setCurrentSession('msg-session')
      })

      act(() => {
        addMessage('msg-session', {
          role: 'user',
          content: 'Hello'
        })
      })

      const newState = useAppStore.getState()
      const messages = newState.sessions['msg-session']?.messages || []
      expect(messages).toHaveLength(1)
      expect(messages[0].content).toBe('Hello')
    })

    it('should add assistant message', () => {
      const { createSession, addMessage, setCurrentSession } = useAppStore.getState()

      act(() => {
        createSession('assistant-session', 'Assistant Test')
        setCurrentSession('assistant-session')
      })

      act(() => {
        addMessage('assistant-session', {
          role: 'assistant',
          content: 'Analysis complete'
        })
      })

      const newState = useAppStore.getState()
      const messages = newState.sessions['assistant-session']?.messages || []
      expect(messages).toHaveLength(1)
      expect(messages[0].role).toBe('assistant')
    })
  })

  describe('Dataset Management', () => {
    it('should add dataset to session', () => {
      const { createSession, addDataset } = useAppStore.getState()

      act(() => {
        createSession('dataset-session', 'Dataset Test')
      })

      act(() => {
        addDataset('dataset-session', {
          file_name: 'test.csv',
          file_path: '/uploads/test.csv',
          num_rows: 100,
          num_cols: 5,
          columns: ['a', 'b', 'c', 'd', 'e']
        })
      })

      const newState = useAppStore.getState()
      const datasets = newState.sessions['dataset-session']?.datasets || []
      expect(datasets).toHaveLength(1)
      expect(datasets[0].file_name).toBe('test.csv')
      expect(datasets[0].num_rows).toBe(100)
    })
  })

  describe('Streaming State', () => {
    it('should toggle streaming state', () => {
      const { setStreaming } = useAppStore.getState()

      act(() => {
        setStreaming(true)
      })

      expect(useAppStore.getState().isStreaming).toBe(true)

      act(() => {
        setStreaming(false)
      })

      expect(useAppStore.getState().isStreaming).toBe(false)
    })
  })

  describe('Code and Figures', () => {
    it('should update current code', () => {
      const { createSession, setCode } = useAppStore.getState()

      act(() => {
        createSession('code-session', 'Code Test')
      })

      act(() => {
        setCode('code-session', 'print("Hello")')
      })

      const newState = useAppStore.getState()
      expect(newState.sessions['code-session']?.currentCode).toBe('print("Hello")')
    })

    it('should set figures', () => {
      const { createSession, setFigures } = useAppStore.getState()

      act(() => {
        createSession('figure-session', 'Figure Test')
      })

      act(() => {
        setFigures('figure-session', ['/figures/chart1.png', '/figures/chart2.png'])
      })

      const newState = useAppStore.getState()
      const figures = newState.sessions['figure-session']?.figures || []
      expect(figures).toHaveLength(2)
    })
  })
})
