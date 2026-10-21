import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { IconX } from './Icons'

export function Spinner({ size = 22 }: { size?: number }) {
  return (
    <span
      className="spinner"
      style={{ width: size, height: size, borderWidth: size > 26 ? 3 : 2.5 }}
    />
  )
}

export function Loading({ label }: { label?: string }) {
  return (
    <div className="center-box">
      <Spinner size={26} />
      {label && <span style={{ fontSize: 13, color: 'var(--ink-3)' }}>{label}</span>}
    </div>
  )
}

export function Empty({
  icon,
  title,
  desc,
  action,
}: {
  icon?: ReactNode
  title: string
  desc?: string
  action?: ReactNode
}) {
  return (
    <div className="empty">
      {icon && <div className="empty__icon">{icon}</div>}
      <div className="empty__title">{title}</div>
      {desc && <div className="empty__desc">{desc}</div>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  )
}

export function Sheet({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  if (!open) return null
  return (
    <div className="overlay" onClick={onClose}>
      <div className="sheet" onClick={(event) => event.stopPropagation()}>
        <div className="sheet__head">
          <div className="sheet__title">{title}</div>
          <button className="sheet__close" onClick={onClose} aria-label="关闭">
            <IconX size={16} />
          </button>
        </div>
        <div className="sheet__body">{children}</div>
        {footer && <div className="sheet__foot">{footer}</div>}
      </div>
    </div>
  )
}

const STATUS_TEXT: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  stopped: '已停止',
  exhausted: '超时未抢到',
  failed: '失败',
  expired: '已过期',
  success: '成功',
}

const STATUS_TONE: Record<string, string> = {
  pending: 'pill--info',
  running: 'pill--ok',
  completed: 'pill--ok',
  success: 'pill--ok',
  stopped: 'pill--muted',
  exhausted: 'pill--warn',
  failed: 'pill--bad',
  expired: 'pill--muted',
}

export function StatusPill({ status }: { status: string }) {
  return (
    <span className={`pill ${STATUS_TONE[status] || 'pill--muted'}`}>
      {STATUS_TEXT[status] || status}
    </span>
  )
}

export function Btn({
  variant = 'ghost',
  size,
  className = '',
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'soft' | 'danger'
  size?: 'sm' | 'lg'
}) {
  const cls = [
    'btn',
    `btn--${variant}`,
    size === 'sm' ? 'btn--sm' : '',
    size === 'lg' ? 'btn--lg' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  )
}

export function Row({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="task__row">
      <span className="task__key">{label}</span>
      <span className="task__val">{children}</span>
    </div>
  )
}

export function notice(text: string, tone: 'warn' | 'info' = 'warn', icon?: ReactNode) {
  return (
    <div className={`notice ${tone === 'info' ? 'notice--info' : ''}`}>
      {icon}
      <span>{text}</span>
    </div>
  )
}
