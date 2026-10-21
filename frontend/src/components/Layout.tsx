import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { checkStatus, getSystemInfo, shutdownService, type AuthStatus, type SystemInfo } from '../api'
import { Sheet, Btn } from './ui'
import { useToast } from './Toast'
import { errorMessage } from '../api/client'
import {
  IconClock,
  IconCourt,
  IconHome,
  IconList,
  IconSettings,
  IconShuttle,
  IconLogout,
} from './Icons'

const TABS = [
  { to: '/', label: '首页', icon: IconHome },
  { to: '/venues', label: '场地', icon: IconCourt },
  { to: '/tasks', label: '任务', icon: IconClock },
  { to: '/bookings', label: '记录', icon: IconList },
  { to: '/settings', label: '设置', icon: IconSettings },
]

export default function Layout() {
  const [auth, setAuth] = useState<AuthStatus | null>(null)
  const [info, setInfo] = useState<SystemInfo | null>(null)
  const [confirmExit, setConfirmExit] = useState(false)
  const [exiting, setExiting] = useState(false)
  const toast = useToast()

  const exit = async () => {
    setExiting(true)
    try {
      await shutdownService()
    } catch (err) {
      setExiting(false)
      toast.error(errorMessage(err, '退出失败，请重试'))
    }
  }

  useEffect(() => {
    let alive = true
    const load = () => {
      checkStatus()
        .then((data) => alive && setAuth(data))
        .catch(() => alive && setAuth(null))
      getSystemInfo()
        .then((data) => alive && setInfo(data))
        .catch(() => undefined)
    }
    load()
    window.addEventListener('auth-changed', load)
    const timer = window.setInterval(load, 60_000)
    return () => {
      alive = false
      window.removeEventListener('auth-changed', load)
      window.clearInterval(timer)
    }
  }, [])

  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail__brand">
          <div className="rail__logo">
            <IconShuttle size={22} />
          </div>
          <div>
            <div className="rail__title">羽约 · 西电</div>
            <div className="rail__sub">COURT RESERVATION</div>
          </div>
        </div>

        <div className="rail__caption">我的运动空间</div>
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === '/'}
            className={({ isActive }) => `rail__link${isActive ? ' is-active' : ''}`}
          >
            <tab.icon size={18} />
            {tab.label}
          </NavLink>
        ))}

        <div className="rail__spacer" />
        <div className="rail__note">把时间留给球场。<span>南校区 · 远望谷体育馆</span></div>

        <div className="rail__foot">
          <strong>{auth?.logged_in ? '登录有效' : '未登录'}</strong>
          {auth?.logged_in
            ? `已加载 ${auth.cookie_count} 条 cookie`
            : auth?.message || '在设置页导入 session'}
          <div style={{ marginTop: 8, opacity: 0.7 }}>
            v{info?.version ?? '2.0.0'}
          </div>
        </div>
        <button className="service-exit" onClick={() => setConfirmExit(true)}><IconLogout size={17} />退出整个服务</button>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="topbar__brand">
            <div className="topbar__logo">
              <IconShuttle size={19} />
            </div>
            <div>
              <div className="topbar__title">羽毛球预约</div>
              <div className="topbar__sub">远望谷体育馆</div>
            </div>
          </div>
          <div className="topbar__actions"><span
            className={`pill ${auth?.logged_in ? 'pill--ok' : 'pill--bad'}`}
            style={{ fontSize: 11 }}
          >
            {auth?.logged_in ? '在线' : '离线'}
          </span><button className="btn btn--ghost btn--sm" onClick={() => setConfirmExit(true)}><IconLogout size={15} />退出服务</button></div>
        </div>

        <div className="page">
          <Outlet />
        </div>
      </main>

      <nav className="tabbar">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === '/'}
            className={({ isActive }) => `tabbar__item${isActive ? ' is-active' : ''}`}
          >
            <tab.icon size={20} />
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Sheet open={confirmExit} title="退出整个服务" onClose={() => !exiting && setConfirmExit(false)}
        footer={<><Btn onClick={() => setConfirmExit(false)} disabled={exiting}>继续使用</Btn><Btn variant="danger" onClick={exit} disabled={exiting}>{exiting ? '正在退出…' : '退出程序与后台服务'}</Btn></>}>
        <p>退出后，桌面窗口和后台服务会一起关闭，正在执行的抢场任务将停止。</p>
        <p style={{ color: 'var(--ink-3)' }}>已保存的任务与预约记录会保留，下次启动时自动恢复任务。</p>
      </Sheet>
    </div>
  )
}
