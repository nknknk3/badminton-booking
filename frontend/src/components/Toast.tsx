import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { IconAlert, IconCheck, IconInfo } from './Icons'

type ToastKind = 'ok' | 'err' | 'info'

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

interface ToastApi {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const seq = useRef(0)

  const push = useCallback((kind: ToastKind, message: string) => {
    const id = ++seq.current
    setItems((prev) => [...prev.slice(-2), { id, kind, message }])
    window.setTimeout(() => {
      setItems((prev) => prev.filter((item) => item.id !== id))
    }, 3800)
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      success: (message: string) => push('ok', message),
      error: (message: string) => push('err', message),
      info: (message: string) => push('info', message),
    }),
    [push]
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toasts">
        {items.map((item) => (
          <div key={item.id} className={`toast toast--${item.kind}`}>
            <span className="toast__icon">
              {item.kind === 'ok' ? (
                <IconCheck size={17} />
              ) : item.kind === 'err' ? (
                <IconAlert size={17} />
              ) : (
                <IconInfo size={17} />
              )}
            </span>
            <span>{item.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
