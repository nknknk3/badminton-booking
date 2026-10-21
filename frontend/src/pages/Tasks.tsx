import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createTask,
  deleteTask,
  getDates,
  getSlots,
  getSystemInfo,
  getTasks,
  updateTask,
  type Slot,
  type Task,
} from '../api'
import { errorMessage } from '../api/client'
import {
  IconAlert,
  IconBolt,
  IconCalendar,
  IconClock,
  IconPlus,
  IconTrash,
} from '../components/Icons'
import { Btn, Empty, Loading, Row, Sheet, Spinner, StatusPill } from '../components/ui'
import { useToast } from '../components/Toast'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const FALLBACK_SLOTS: Slot[] = Array.from({ length: 12 }, (_, index) => {
  const begin = 10 + index
  return {
    begin_time: `${String(begin).padStart(2, '0')}:00`,
    end_time: `${String(begin + 1).padStart(2, '0')}:00`,
    field_state: 0,
    time_status: 0,
  }
})

function weekdayOf(mmdd: string) {
  const [month, day] = mmdd.split('-').map(Number)
  const now = new Date()
  let date = new Date(now.getFullYear(), month - 1, day)
  if (date < new Date(now.getFullYear(), now.getMonth(), now.getDate())) {
    date = new Date(now.getFullYear() + 1, month - 1, day)
  }
  return WEEKDAYS[date.getDay()]
}

export default function Tasks() {
  const toast = useToast()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [dates, setDates] = useState<string[]>([])
  const [systemLead, setSystemLead] = useState(150)
  const [defaultInterval, setDefaultInterval] = useState(3)

  const [showCreate, setShowCreate] = useState(false)
  const [deleting, setDeleting] = useState<Task | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [name, setName] = useState('')
  const [date, setDate] = useState('')
  const [times, setTimes] = useState<string[]>([])
  const [interval, setIntervalValue] = useState(3)
  const [startAt, setStartAt] = useState('')
  const [slotOptions, setSlotOptions] = useState<Slot[]>([])
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [slotError, setSlotError] = useState('')

  const loadTasks = useCallback(async () => {
    try {
      setTasks(await getTasks())
    } catch (err) {
      toast.error(errorMessage(err, '获取任务失败'))
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    loadTasks()
    getSystemInfo()
      .then((info) => {
        setSystemLead(info.lead_minutes)
        setDefaultInterval(info.poll_default)
        setIntervalValue(info.poll_default)
      })
      .catch(() => undefined)
  }, [loadTasks])

  const openCreate = async () => {
    setName('')
    setTimes([])
    setStartAt('')
    setIntervalValue(defaultInterval)
    setShowCreate(true)
    try {
      const result = await getDates()
      setDates(result.dates)
      setDate(result.dates[0] || '')
    } catch (err) {
      toast.error(errorMessage(err, '获取日期失败'))
      setDates([])
    }
  }

  useEffect(() => {
    if (!showCreate || !date) return
    let alive = true
    setLoadingSlots(true)
    getSlots(date, true)
      .then((result) => {
        if (!alive) return
        setSlotError(result.error || '')
        setSlotOptions(result.slots.length > 0 ? result.slots : FALLBACK_SLOTS)
      })
      .catch(() => alive && setSlotOptions(FALLBACK_SLOTS))
      .finally(() => alive && setLoadingSlots(false))
    return () => {
      alive = false
    }
  }, [showCreate, date])

  const submit = async () => {
    if (!name.trim()) return toast.error('给任务起个名字')
    if (!date) return toast.error('请选择目标日期')
    if (times.length === 0) return toast.error('至少选一个时段')

    setSubmitting(true)
    try {
      await createTask({
        name: name.trim(),
        target_date: date,
        target_times: times,
        poll_interval: interval,
        start_at: startAt || null,
      })
      toast.success('任务已创建')
      setShowCreate(false)
      await loadTasks()
    } catch (err) {
      toast.error(errorMessage(err, '创建失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const toggle = async (task: Task) => {
    setBusyId(task.id)
    try {
      await updateTask(task.id, { enabled: !task.enabled })
      toast.success(task.enabled ? '已停用该任务' : '已启用该任务')
      await loadTasks()
    } catch (err) {
      toast.error(errorMessage(err, '操作失败'))
    } finally {
      setBusyId(null)
    }
  }

  const remove = async () => {
    if (!deleting) return
    setBusyId(deleting.id)
    try {
      await deleteTask(deleting.id)
      toast.success('任务已删除')
      setDeleting(null)
      await loadTasks()
    } catch (err) {
      toast.error(errorMessage(err, '删除失败'))
    } finally {
      setBusyId(null)
    }
  }

  const toggleTime = (value: string) => {
    setTimes((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]
    )
  }

  const activeCount = useMemo(
    () => tasks.filter((task) => task.enabled && ['pending', 'running'].includes(task.status)).length,
    [tasks]
  )

  if (loading) return <Loading label="正在读取任务…" />

  return (
    <div>
      <div className="page-head">
        <h1 className="page-title">自动任务</h1>
        <p className="page-sub">
          {tasks.length === 0
            ? '到点自动帮你盯着，一放场就下单'
            : `共 ${tasks.length} 个任务 · ${activeCount} 个进行中`}
        </p>
      </div>

      {tasks.length === 0 ? (
        <Empty
          icon={<IconBolt size={22} />}
          title="还没有自动任务"
          desc="定好日期和时段，让它替你准点开抢"
          action={
            <Btn variant="primary" onClick={openCreate}>
              <IconPlus size={15} />
              新建任务
            </Btn>
          }
        />
      ) : (
        tasks.map((task) => (
          <div className="task rise" key={task.id}>
            <div className="task__head">
              <div className="task__name">{task.name}</div>
              <StatusPill status={task.status} />
            </div>

            <div className="task__rows">
              <Row label="目标日期">
                {task.target_date} · {weekdayOf(task.target_date)}
              </Row>
              <Row label="目标时段">
                <span className="task__tags">
                  {task.target_times.map((time) => (
                    <span key={time} className="pill pill--muted">
                      {time}
                    </span>
                  ))}
                </span>
              </Row>
              <Row label="轮询间隔">{task.poll_interval}s</Row>
              <Row label="启动时间">
                {task.next_run_at
                  ? task.next_run_at
                  : task.start_at || `自动（最早时段前 ${systemLead} 分钟）`}
              </Row>
            </div>

            <div className="task__foot">
              <label className="switch">
                <input
                  type="checkbox"
                  checked={task.enabled}
                  disabled={busyId === task.id}
                  onChange={() => toggle(task)}
                />
                <span className="switch__track" />
                <span className="switch__text">
                  {task.enabled ? '已启用' : '已停用'}
                </span>
              </label>
              <Btn
                variant="danger"
                size="sm"
                onClick={() => setDeleting(task)}
                disabled={busyId === task.id}
              >
                <IconTrash size={14} />
                删除
              </Btn>
            </div>
          </div>
        ))
      )}

      {tasks.length > 0 && (
        <button className="fab" onClick={openCreate}>
          <IconPlus size={17} />
          新建任务
        </button>
      )}

      <Sheet
        open={showCreate}
        title="新建抢场任务"
        onClose={() => !submitting && setShowCreate(false)}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowCreate(false)} disabled={submitting}>
              取消
            </Btn>
            <Btn variant="primary" onClick={submit} disabled={submitting}>
              {submitting ? <Spinner size={15} /> : <IconBolt size={15} />}
              {submitting ? '创建中' : '创建任务'}
            </Btn>
          </>
        }
      >
        <div className="form-row">
          <label className="field-label">任务名称</label>
          <input
            className="input"
            placeholder="例如：周三晚场"
            value={name}
            maxLength={40}
            onChange={(event) => setName(event.target.value)}
          />
        </div>

        <div className="form-row">
          <label className="field-label">目标日期</label>
          <div className="datestrip" style={{ paddingBottom: 4 }}>
            {dates.map((item) => (
              <button
                key={item}
                className={`date-chip${item === date ? ' is-active' : ''}`}
                onClick={() => {
                  setDate(item)
                  setTimes([])
                }}
                style={{ width: 54 }}
              >
                <span>{weekdayOf(item)}</span>
                <b>{item.split('-')[1]}</b>
              </button>
            ))}
          </div>
          {dates.length === 0 && (
            <div style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>暂无可用日期</div>
          )}
        </div>

        <div className="form-row">
          <label className="field-label">
            目标时段（可多选）
            {times.length > 0 && (
              <span style={{ color: 'var(--brand)', marginLeft: 6 }}>
                已选 {times.length}
              </span>
            )}
          </label>
          {loadingSlots ? (
            <div className="center-box" style={{ padding: 18 }}>
              <Spinner size={18} />
            </div>
          ) : (
            <div className="time-grid">
              {slotOptions.map((slot) => {
                const value = slot.begin_time
                const free = slot.field_state === 0 && slot.time_status === 1
                const label = free ? '可订' : slot.field_state !== 0 ? '已满' : '未开放'
                return (
                  <button
                    key={value}
                    className={`time-opt${times.includes(value) ? ' is-on' : ''}`}
                    onClick={() => toggleTime(value)}
                  >
                    <b>{value}</b>
                    <span>{label}</span>
                  </button>
                )
              })}
            </div>
          )}
          {slotError && (
            <div style={{ fontSize: 12, color: 'var(--warn)', marginTop: 8 }}>
              {slotError}
            </div>
          )}
        </div>

        <div className="form-row">
          <label className="field-label">轮询间隔（秒）</label>
          <input
            className="input"
            type="number"
            min={0.5}
            max={60}
            step={0.5}
            value={interval}
            onChange={(event) => setIntervalValue(Number(event.target.value))}
          />
          <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 6 }}>
            太小容易被限流，建议 2–5 秒
          </div>
        </div>

        <div className="form-row">
          <label className="field-label">启动时间（可选）</label>
          <input
            className="input"
            type="datetime-local"
            value={startAt}
            onChange={(event) => setStartAt(event.target.value)}
          />
          <div
            style={{
              display: 'flex',
              gap: 8,
              alignItems: 'flex-start',
              fontSize: 12,
              color: 'var(--ink-3)',
              marginTop: 7,
            }}
          >
            <IconClock size={14} />
            <span>
              留空则自动在最早时段开放前 {systemLead} 分钟启动，抢满所选时段后结束。
            </span>
          </div>
        </div>

        <div className="notice" style={{ marginBottom: 6 }}>
          <IconAlert size={15} />
          <span>
            同一日期同一时段只允许一个启用中的任务，避免重复下单。运行最长{' '}
            4 小时。
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 2px 2px' }}>
          <IconCalendar size={14} color="var(--ink-3)" />
          <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>
            预约窗口通常提前约 2 小时开放
          </span>
        </div>
      </Sheet>

      <Sheet
        open={Boolean(deleting)}
        title="删除任务"
        onClose={() => !busyId && setDeleting(null)}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setDeleting(null)} disabled={Boolean(busyId)}>
              取消
            </Btn>
            <Btn variant="danger" onClick={remove} disabled={Boolean(busyId)}>
              {busyId ? <Spinner size={15} /> : <IconTrash size={15} />}
              确认删除
            </Btn>
          </>
        }
      >
        <p style={{ fontSize: 14, color: 'var(--ink-2)', lineHeight: 1.7 }}>
          确定删除任务「{deleting?.name}」吗？如果它正在运行会立即停止轮询，此操作不可撤销。
        </p>
      </Sheet>
    </div>
  )
}
