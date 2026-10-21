import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  checkStatus,
  getHistory,
  getSlots,
  getTasks,
  type AuthStatus,
  type BookingRecord,
  type Task,
} from '../api'
import {
  IconBolt,
  IconCalendar,
  IconChevron,
  IconCourt,
  IconList,
  IconRefresh,
} from '../components/Icons'
import { Btn, Empty, Spinner } from '../components/ui'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function greeting() {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

function todayLabel() {
  const now = new Date()
  return `${now.getMonth() + 1} 月 ${now.getDate()} 日 · ${WEEKDAYS[now.getDay()]}`
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [auth, setAuth] = useState<AuthStatus | null>(null)
  const [slots, setSlots] = useState<number | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [history, setHistory] = useState<BookingRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)

    const now = new Date()
    const today = `${String(now.getMonth() + 1).padStart(2, '0')}-${String(
      now.getDate()
    ).padStart(2, '0')}`

    checkStatus().then(result => {
      setAuth(result)
      if (result.logged_in) {
        getSlots(today).then(result => setSlots(result.slots.filter(
          slot => slot.field_state === 0 && slot.time_status === 1
        ).length)).catch(() => setSlots(null))
      } else setSlots(null)
    }).catch(() => setAuth(null))

    const [taskResult, historyResult] = await Promise.allSettled([
      getTasks(),
      getHistory(20),
    ])
    if (taskResult.status === 'fulfilled') setTasks(taskResult.value)
    if (historyResult.status === 'fulfilled') setHistory(historyResult.value)

    setLoading(false)
    setRefreshing(false)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const activeTasks = tasks.filter(
    (task) => task.enabled && ['pending', 'running'].includes(task.status)
  ).length
  const successCount = history.filter((item) => item.status === 'success').length
  const recent = history.slice(0, 4)

  return (
    <div className="dashboard">
      <div className="page-head">
        <div className="page-eyebrow">YOUR COURT, YOUR TIME</div>
        <h1 className="page-title">{greeting()}，准备上场</h1>
        <p className="page-sub">{todayLabel()} · 西电远望谷体育馆</p>
      </div>

      <section className="hero rise">
        <div className="hero__row">
          <div>
            <div className="hero__label">南校区 · 羽毛球</div>
            <div className="hero__title">
              {slots === null ? '下一场精彩，从这里开始' : slots > 0 ? `现在有 ${slots} 个时段可订` : '好场地，值得再等等'}
            </div>
            <div className="hero__meta">
              {auth?.logged_in ? '账号已就绪 · 查看空场，安排你的运动时间' : '登录校园账号，开启你的球场预约'}
            </div>
          </div>
          <span className={`status-dot${auth?.logged_in ? '' : ' is-off'}`}>
            <i />
            {auth?.logged_in ? '已登录' : '未登录'}
          </span>
        </div>

        <div className="hero__stats">
          <div className="hero__stat">
            <b>{slots ?? '—'}</b>
            <span>今日可订时段</span>
          </div>
          <div className="hero__stat">
            <b>{loading ? '—' : successCount}</b>
            <span>近期成功预约</span>
          </div>
          <div className="hero__stat">
            <b>{loading ? '—' : activeTasks}</b>
            <span>进行中任务</span>
          </div>
        </div>
      </section>

      <div className="quick">
        <button className="quick__btn" onClick={() => navigate('/venues')}>
          <span className="quick__icon">
            <IconCourt size={18} />
          </span>
          <span>
            <span className="quick__title">浏览场地</span>
            <span className="quick__desc">挑时段直接下单</span>
          </span>
        </button>
        <button className="quick__btn" onClick={() => navigate('/tasks')}>
          <span className="quick__icon">
            <IconBolt size={18} />
          </span>
          <span>
            <span className="quick__title">定时抢场</span>
            <span className="quick__desc">自动盯着准时开抢</span>
          </span>
        </button>
      </div>

      {!auth?.logged_in && (
        <div className="card card--pad rise" style={{ marginTop: 14 }}>
          <div className="notice" style={{ background: 'var(--warn-soft)' }}>
            <IconCalendar size={16} />
            <span>
              {auth?.message || '还没有可用的登录状态'}。
              <a
                href="/settings"
                onClick={(event) => {
                  event.preventDefault()
                  navigate('/settings')
                }}
                style={{ fontWeight: 600, textDecoration: 'underline' }}
              >
                前往设置登录
              </a>
              。
            </span>
          </div>
        </div>
      )}

      <section className="section">
        <div className="section__head">
          <h2 className="section__title">最近预约</h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => load(true)}
              disabled={refreshing}
            >
              {refreshing ? <Spinner size={13} /> : <IconRefresh size={14} />}
              刷新
            </button>
            <button
              className="btn btn--soft btn--sm"
              onClick={() => navigate('/bookings')}
            >
              全部
              <IconChevron size={13} />
            </button>
          </div>
        </div>

        {recent.length === 0 ? (
          <Empty
            icon={<IconList size={22} />}
            title="还没有预约记录"
            desc="去场地页看看今天有没有空位"
            action={
              <Btn variant="primary" size="sm" onClick={() => navigate('/venues')}>
                去预约
              </Btn>
            }
          />
        ) : (
          <div className="card" style={{ overflow: 'hidden' }}>
            {recent.map((item) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '13px 16px',
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <div
                  style={{
                    width: 6,
                    height: 34,
                    borderRadius: 4,
                    background:
                      item.status === 'success' ? 'var(--brand)' : 'var(--danger)',
                    opacity: item.status === 'success' ? 1 : 0.6,
                    flex: 'none',
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 650, fontSize: 14 }}>
                    {item.field_name}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                    {item.date} · {item.begin_time}-{item.end_time}
                  </div>
                </div>
                <span
                  className={`pill ${
                    item.status === 'success' ? 'pill--ok' : 'pill--bad'
                  }`}
                >
                  {item.status === 'success' ? '成功' : '失败'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
